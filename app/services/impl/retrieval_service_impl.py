# services/impl/retrieval_service_impl.py
#
# Async retrieval: on-disk FAISS + metadata pickle + structured LLM selection.

from pathlib import Path
from typing import Dict, Any, Optional, List
import asyncio
import logging
import re

import faiss
import pandas as pd
import numpy as np

from app.services.retrieval_service import RetrievalService
from app.services.impl.structured_llm import AsyncEmbeddingClient, AsyncStructuredLLM
from app.services.impl.optimized_query_guardrail import OptimizedQueryGuardrail
from app.config.settings import settings
from app.config.prompts import raq_query_former_prompt, svc_code_selector_prompt
from app.schemas.workflow_models import RAGQueryResult, ServiceCodeSelection

logger = logging.getLogger(__name__)

_faiss_index = None
_faiss_metadata: Optional[pd.DataFrame] = None

CODE_COL = "primary_svc_cd"
TYPE_COL = "servc_type"
DESC_COL = "Consumer-Friendly Description"


def _artifact_path(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else (Path.cwd() / p)


class RetrievalServiceImpl(RetrievalService):

    def __init__(self):
        self._embed_client = AsyncEmbeddingClient()
        self._rag_llm = AsyncStructuredLLM()
        self._selector_llm = AsyncStructuredLLM()
        self._query_guardrail = OptimizedQueryGuardrail()

    def _load_resources(self):
        global _faiss_index, _faiss_metadata
        if _faiss_index is None:
            idx_path = _artifact_path(settings.faiss_index_path)
            meta_path = _artifact_path(settings.faiss_metadata_path)
            if not idx_path.is_file():
                raise FileNotFoundError(
                    f"FAISS index not found at {idx_path} (set FAISS_INDEX_PATH or add the file)"
                )
            if not meta_path.is_file():
                raise FileNotFoundError(
                    f"Metadata pickle not found at {meta_path} (set FAISS_METADATA_PATH or add the file)"
                )
            logger.info("Loading FAISS index + metadata from %s", idx_path.parent)
            _faiss_index = faiss.read_index(str(idx_path))
            _faiss_metadata = pd.read_pickle(str(meta_path))

    def _faiss_df_by_code(self, service_code: str) -> pd.DataFrame:
        self._load_resources()
        assert _faiss_metadata is not None
        row = _faiss_metadata[_faiss_metadata[CODE_COL].astype(str) == service_code]
        return row.copy() if not row.empty else pd.DataFrame()

    def _faiss_topk(self, vec: List[float], k: int) -> pd.DataFrame:
        self._load_resources()
        assert _faiss_index is not None and _faiss_metadata is not None
        vector = np.array([vec], dtype=np.float32)
        distances, indices = _faiss_index.search(vector, k)
        if indices is None or len(indices) == 0 or len(indices[0]) == 0:
            return pd.DataFrame()
        top = _faiss_metadata.iloc[indices[0]].copy()
        if top.empty:
            return pd.DataFrame()
        top["similarity_score"] = 1.0 / (1.0 + distances[0])
        return top

    @staticmethod
    def _extract_service_code(user_query: str) -> Optional[str]:
        q = user_query.strip().upper()
        patterns = [r"^\d{5}$", r"^[A-Z]\d{4}$", r"^\d{4}[A-Z]$"]
        if any(re.fullmatch(p, q) for p in patterns):
            return q
        return None

    @staticmethod
    def _out_of_scope(reason: str) -> Dict[str, Any]:
        return {
            "service_code": "Out of Scope",
            "service_code_type": "",
            "description": "",
            "alternative_services": {},
            "assumptions": reason,
            "confidence": 0.0,
        }

    def _build_context(self, top: pd.DataFrame) -> str:
        return "\n".join(
            f"- Code: {r[CODE_COL]}, Description: {r[DESC_COL]}"
            for _, r in top.iterrows()
        )

    async def _check_safety(self, query: str) -> Optional[Dict[str, Any]]:
        is_blocked, details = await self._query_guardrail.check_query(query)
        if is_blocked:
            return {
                "service_code": "Blocked - Harmful Query",
                "service_code_type": "",
                "description": "",
                "alternative_services": {},
                "assumptions": (
                    f"Query blocked for safety. Category: {details.get('type', 'Unknown')}. "
                    "Please rephrase with a legitimate medical service inquiry."
                ),
                "blocked": True,
                "block_reason": details,
                "confidence": 0.0,
            }
        return None

    async def async_resolve_service_code(
        self, query: str, service_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resolve service codes — async path with FAISS ANN search."""

        safety = await self._check_safety(query)
        if safety:
            return safety

        self._load_resources()

        if service_code is None:
            detected = self._extract_service_code(query)
            if detected:
                service_code = detected

        if service_code:
            row = await asyncio.to_thread(self._faiss_df_by_code, service_code)
            if row.empty:
                return self._out_of_scope("No matching service codes found.")
            rag_query = row[DESC_COL].values[0]
        else:
            rag_result = await self._rag_llm.generate(
                prompt=raq_query_former_prompt.format(query=query),
                response_model=RAGQueryResult,
            )
            if rag_result.is_out_of_scope:
                return self._out_of_scope(rag_result.scope_reason or "Query is out of scope.")
            rag_query = rag_result.modified_query

        vec = await self._embed_client.embed(rag_query)
        top = await asyncio.to_thread(self._faiss_topk, vec, settings.top_k_results)
        if top.empty:
            return self._out_of_scope("No matching service codes found.")

        top["weighted_score"] = (
            settings.semantic_similarity_weight * top["similarity_score"]
            + settings.claim_volume_weight * top["total_claim_count"]
        )
        top = top.sort_values("weighted_score", ascending=False).reset_index(drop=True)

        context_str = self._build_context(top)
        selection: ServiceCodeSelection = await self._selector_llm.generate(
            prompt=svc_code_selector_prompt.format(
                query=query, service_code_context_str=context_str
            ),
            response_model=ServiceCodeSelection,
        )

        primary_code = selection.primary_svc_code
        primary_match = top[top[CODE_COL].astype(str) == primary_code]
        if primary_match.empty:
            logger.warning("Primary code %s not in retrieved results", primary_code)
            return self._out_of_scope(
                "Selected service code was not found in retrieved candidates."
            )
        primary_row = primary_match.iloc[0]

        alternative_services = {}
        for alt in selection.alternates[:3]:
            alt_row = top[top[CODE_COL].astype(str) == alt]
            if not alt_row.empty:
                alternative_services[alt] = {
                    "description": alt_row.iloc[0][DESC_COL],
                    "weighted_score": float(alt_row.iloc[0].get("weighted_score", 0)),
                }

        scores = top["weighted_score"].tolist()
        confidence = selection.confidence
        if len(scores) >= 2 and scores[0] > 0:
            gap = (scores[0] - scores[1]) / scores[0]
            score_confidence = min(1.0, 0.5 + gap)
            confidence = round((confidence + score_confidence) / 2, 3)

        return {
            "service_code": primary_code,
            "service_code_type": primary_row.get(TYPE_COL, ""),
            "description": primary_row.get(DESC_COL, ""),
            "alternative_services": alternative_services,
            "assumptions": selection.assumptions,
            "confidence": confidence,
        }

    def resolve_service_code(
        self, query: str, service_code: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run, self.async_resolve_service_code(query, service_code)
                ).result()
        return asyncio.run(self.async_resolve_service_code(query, service_code))

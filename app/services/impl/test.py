from typing import Dict, Any, Optional, List
import logging
import re

import faiss
import pandas as pd
import numpy as np
import json_repair

from services.retrieval_service import RetrievalService
from services.impl.llm_client import OpenAIEmbeddingClient, OpenAILLMClient

from config.retrieval_scoring import (
    FAISS_INDEX_PATH,
    FAISS_METADATA_PATH,
    TOP_K_RESULTS,
    SEMANTIC_SIMILARITY_WEIGHT,
    CLAIM_VOLUME_WEIGHT,
)
from config.llms import RAG_MODEL_NAME, SERVICE_RESOLVER_MODEL_NAME
from config.prompts import raq_query_former_prompt, svc_code_selector_prompt

logger = logging.getLogger(__name__)

CODE_COL = "primary_svc_cd"
TYPE_COL = "servc_type"
DESC_COL = "Consumer-Friendly Description"
TITLE_COL = "Consumer-Friendly Title"


class RetrievalServiceImpl(RetrievalService):

    def __init__(self):
        self._faiss_index = None
        self._faiss_metadata = None

        self._embed_client = OpenAIEmbeddingClient()
        self._rag_model = OpenAILLMClient(RAG_MODEL_NAME)
        self._selector_model = OpenAILLMClient(SERVICE_RESOLVER_MODEL_NAME)

    # --------------------------------------------------
    # Load FAISS + metadata once
    # --------------------------------------------------
    def _load_resources(self):
        if self._faiss_index is None:
            logger.info("Loading FAISS index and metadata")
            self._faiss_index = faiss.read_index(FAISS_INDEX_PATH)
            self._faiss_metadata = pd.read_pickle(FAISS_METADATA_PATH)
        return self._faiss_index, self._faiss_metadata

    # --------------------------------------------------
    # Detect service code in query
    # --------------------------------------------------
    def _extract_service_code_from_query(self, user_query: str) -> Optional[str]:
        q = user_query.strip().upper()
        patterns = [
            r"^\d{5}$",
            r"^[A-Z]\d{4}$",
            r"^\d{4}[A-Z]$",
        ]
        if any(re.fullmatch(p, q) for p in patterns):
            return q
        return None

    # --------------------------------------------------
    # Out-of-scope response
    # --------------------------------------------------
    def _out_of_scope_response(self, reason: str) -> Dict[str, Any]:
        return {
            "service_code": "Out of Scope",
            "service_code_type": "",
            "description": "",
            "alternative_services": {},
            "assumptions": reason,
        }

    # --------------------------------------------------
    # Build selector context string
    # --------------------------------------------------
    def _build_context_str(self, top: pd.DataFrame) -> str:
        lines = []
        for _, r in top.iterrows():
            lines.append(
                f"- Code: {r.get(CODE_COL)}, "
                f"Title: {r.get(TITLE_COL, '')}, "
                f"Description: {r.get(DESC_COL, '')}, "
                f"Claim Volume: {r.get('total_claim_count')}"
            )
        return "\n".join(lines)

    # --------------------------------------------------
    # Validate selector output
    # --------------------------------------------------
    def _validate_selector_output(self, output: Dict[str, Any], valid_codes: List[str]) -> Dict[str, Any]:
        if not isinstance(output, dict):
            raise ValueError("Selector output is not JSON")

        for k in ("primary_svc_code", "alternates", "assumptions"):
            if k not in output:
                raise ValueError(f"Missing field {k}")

        primary = str(output["primary_svc_code"]).strip()
        alternates = output["alternates"]
        assumptions = str(output["assumptions"]).strip()

        if primary not in valid_codes:
            raise ValueError("Primary code not in retrieved candidates")
                
        if not isinstance(alternates, list):
            raise ValueError("Selector alternates must be a list")

        if not assumptions:
            raise ValueError("Selector assumptions cannot be empty")

        clean_alts = []
        for a in alternates:
            a = str(a).strip()
            if a and a != primary and a in valid_codes and a not in clean_alts:
                clean_alts.append(a)

        return {
            "primary_svc_code": primary,
            "alternates": clean_alts,
            "assumptions": assumptions,
        }

    # --------------------------------------------------
    # MAIN ENTRY POINT
    # --------------------------------------------------
    def resolve_service_code(self, query: str, service_code: Optional[str] = None) -> Dict[str, Any]:

        index, metadata = self._load_resources()

        # Step 1: Detect direct code
        if service_code is None:
            detected = self._extract_service_code_from_query(query)
            if detected:
                service_code = detected

        # Step 2: Build RAG query
        rag_query = None

        if service_code:
            svc = service_code.strip().upper()
            row = metadata[metadata[CODE_COL].astype(str) == svc]
            if row.empty:
                return self._out_of_scope_response(
                    "No matching service codes were found for the provided service code."
                )
            rag_query = row[DESC_COL].values[0]
            service_code = svc
        else:
            prompt = raq_query_former_prompt.format(query=query)
            rag_query = self._rag_model.generate(prompt).strip()

            if rag_query.lower() == "out of scope":
                return self._out_of_scope_response(
                    "The user's query was determined to be out of scope."
                )

            if rag_query.lower().startswith("service_code:"):
                possible = rag_query.split(":", 1)[1].strip().upper()
                detected = self._extract_service_code_from_query(possible)
                if detected:
                    row = metadata[metadata[CODE_COL].astype(str) == detected]
                    if row.empty:
                        return self._out_of_scope_response(
                            "No matching service codes were found for the provided service code."
                        )
                    service_code = detected
                    rag_query = row[DESC_COL].values[0]

        if not rag_query or not str(rag_query).strip():
            return self._out_of_scope_response(
                "No valid query could be formed for service code resolution."
            )

        # --------------------------------------------------
        # VECTOR SEARCH
        # --------------------------------------------------
        vec = self._embed_client.embed(rag_query)
        vector = np.array([vec], dtype="float32")

        distances, indices = index.search(vector, TOP_K_RESULTS)
        top = metadata.iloc[indices[0]].copy()

        # --------------------------------------------------
        # 🔥 WEIGHTED SCORE LOGIC (CODE LEVEL)
        # --------------------------------------------------
        top["similarity_score"] = 1 / (1 + distances[0])

        top["weighted_score"] = (
            SEMANTIC_SIMILARITY_WEIGHT * top["similarity_score"]
            + CLAIM_VOLUME_WEIGHT * top["total_claim_count"]
        )

        top = top.sort_values("weighted_score", ascending=False).reset_index(drop=True)

        # --------------------------------------------------
        # SELECTOR LLM (NO WEIGHTED SCORE IN PROMPT)
        # --------------------------------------------------
        context_str = self._build_context_str(top)

        prompt2 = svc_code_selector_prompt.format(
            query=query,
            service_code_context_str=context_str,
        )

        selector_text = self._selector_model.generate(prompt2)
        selector_raw = json_repair.loads(selector_text)

        valid_codes = top[CODE_COL].astype(str).tolist()
        selector = self._validate_selector_output(selector_raw, valid_codes)

        if service_code:
            selector["primary_svc_code"] = service_code

        primary_row = top[top[CODE_COL].astype(str) == selector["primary_svc_code"]].iloc[0]

        # --------------------------------------------------
        # ALTERNATE RANKING
        # --------------------------------------------------
        alt_df = top[top[CODE_COL].astype(str).isin(selector["alternates"])].copy()
        alternative_services = {}

        if not alt_df.empty:
            alt_df = alt_df.sort_values("weighted_score", ascending=False)
            alt_df["weighted_score_rank"] = range(1, len(alt_df) + 1)

            alt_df = alt_df.sort_values("total_claim_count", ascending=False)
            alt_df["claim_volume_rank"] = range(1, len(alt_df) + 1)

            for _, r in alt_df.iterrows():
                alternative_services[str(r[CODE_COL])] = {
                    "description": r.get(DESC_COL, ""),
                    "weighted_score_rank": int(r["weighted_score_rank"]),
                    "claim_volume_rank": int(r["claim_volume_rank"]),
                }

        # --------------------------------------------------
        # FINAL RESPONSE (UNCHANGED)
        # --------------------------------------------------
        return {
            "service_code": str(primary_row[CODE_COL]),
            "service_code_type": str(primary_row.get(TYPE_COL, "")).strip(),
            "description": primary_row.get(DESC_COL, ""),
            "alternative_services": alternative_services,
            "assumptions": selector["assumptions"],
        }

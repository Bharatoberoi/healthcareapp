# services/impl/retrieval_service_impl.py

from typing import Dict, Any, Optional, List
import logging
import re

import faiss
import pandas as pd
import numpy as np
import json_repair

from app.services.retrieval_service import RetrievalService
from app.services.impl.llm_client import OpenAIEmbeddingClient, OpenAILLMClient
from app.services.impl.optimized_query_guardrail import OptimizedQueryGuardrail as QueryGuardrail
from app.config.retrieval_scoring import (
    FAISS_INDEX_PATH,
    FAISS_METADATA_PATH,
    TOP_K_RESULTS,
    SEMANTIC_SIMILARITY_WEIGHT,
    CLAIM_VOLUME_WEIGHT,
)
from app.config.llms import RAG_MODEL_NAME, SERVICE_RESOLVER_MODEL_NAME
from app.config.prompts import raq_query_former_prompt, svc_code_selector_prompt

# ---------------- LOGGER ----------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------- CONSTANTS ----------------
CODE_COL = "primary_svc_cd"
TYPE_COL = "servc_type"
DESC_COL = "Consumer-Friendly Description"
TITLE_COL = "Consumer-Friendly Title"

# ---------------- SAFETY RULES ----------------
SAFETY_RULES = {
    "medical_harm": "The text provides harmful or unsafe medical advice",
    "illegal_activity": "The text encourages illegal activity",
    "hallucination": "The text contains fabricated or unverifiable medical claims",
    "toxicity": "The text contains abusive or toxic language",
}


class RetrievalServiceImpl(RetrievalService):

    def __init__(self):
        self._faiss_index = None
        self._faiss_metadata = None
        self._embed_client = OpenAIEmbeddingClient()
        self._rag_model = OpenAILLMClient(RAG_MODEL_NAME)
        self._selector_model = OpenAILLMClient(SERVICE_RESOLVER_MODEL_NAME)
        self._query_guardrail = QueryGuardrail()

    # ---------------- LOAD RESOURCES ----------------
    def _load_resources(self):
        if self._faiss_index is None:
            self._faiss_index = faiss.read_index(FAISS_INDEX_PATH)
            self._faiss_metadata = pd.read_pickle(FAISS_METADATA_PATH)
        return self._faiss_index, self._faiss_metadata

    # ---------------- SERVICE CODE EXTRACTION ----------------
    def _extract_service_code_from_query(self, user_query: str) -> Optional[str]:
        q = user_query.strip().upper()
        patterns = [r"^\d{5}$", r"^[A-Z]\d{4}$", r"^\d{4}[A-Z]$"]
        if any(re.fullmatch(p, q) for p in patterns):
            return q
        return None

    # ---------------- OUT OF SCOPE ----------------
    def _out_of_scope_response(self, reason: str) -> Dict[str, Any]:
        return {
            "service_code": "Out of Scope",
            "service_code_type": "",
            "description": "",
            "alternative_services": {},
            "assumptions": reason,
        }

    # ---------------- CONTEXT STRING ----------------
    def _build_context_str(self, top: pd.DataFrame) -> str:
        return "\n".join(
            f"- Code: {r[CODE_COL]}, Description: {r[DESC_COL]}"
            for _, r in top.iterrows()
        )

    # ---------------- NLI GUARDRAIL ----------------
    def _run_nli_guardrail(self, description: str, code: str):
        logger.debug(f"NLI Guardrail Check for CODE={code}")

        for rule_name, rule_text in SAFETY_RULES.items():
            prompt = f"""
You are an NLI classifier.

Premise:
"{rule_text}"

Hypothesis:
"{description}"

Return JSON only:
{{"entailment": float, "neutral": float, "contradiction": float}}
"""
            try:
                raw = self._selector_model.generate(prompt)
                scores = json_repair.loads(raw)

                e = float(scores.get("entailment", 0))
                n = float(scores.get("neutral", 0))
                c = float(scores.get("contradiction", 0))

                status = "FAIL" if e > 0.6 else "PASS" if c > 0.6 else "UNCERTAIN"

                logger.debug(
                    f"[NLI-GUARD] CODE={code} | RULE={rule_name} | "
                    f"E={e:.2f} | N={n:.2f} | C={c:.2f} {status}"
                )

            except Exception as ex:
                print(f"[NLI-GUARD] CODE={code} | RULE={rule_name} | ERROR={ex}")
    # ----------------  HARMFUL QUERY GUARDRAIL ----------------
    def _check_query_safety(self, query: str) -> Dict[str, Any]:
        """
        Check if query is safe to process.
        Returns blocked response if harmful, None if safe.
        """
        is_blocked, details = self._query_guardrail.check_query(query)
        if is_blocked:
            return {
                "service_code": "Blocked - Harmful Query",
                "service_code_type": "",
                "description": "",
                "alternative_services": {},
                "assumptions": f"Query blocked for safety reasons. Category: {details.get('category', 'Unknown')}. Please rephrase your question with legitimate medical service inquiries.",
                "blocked": True,
                "block_reason": details,
            }
        return None
    # ---------------- MAIN ENTRY ----------------
    def resolve_service_code(self, query: str, service_code: Optional[str] = None) -> Dict[str, Any]:
        # ============ LAYER 1: INPUT QUERY SAFETY CHECK ============
        safety_response = self._check_query_safety(query)
        if safety_response:
            return safety_response
        index, metadata = self._load_resources()

        if service_code is None:
            detected = self._extract_service_code_from_query(query)
            if detected:
                service_code = detected

        if service_code:
            row = metadata[metadata[CODE_COL].astype(str) == service_code]
            if row.empty:
                return self._out_of_scope_response("No matching service codes found.")
            rag_query = row[DESC_COL].values[0]
        else:
            rag_query = self._rag_model.generate(
                raq_query_former_prompt.format(query=query)
            ).strip()

        vec = self._embed_client.embed(rag_query)
        vector = np.array([vec], dtype="float32")

        distances, indices = index.search(vector, TOP_K_RESULTS)
        top = metadata.iloc[indices[0]].copy()

        top["similarity_score"] = 1 / (1 + distances[0])
        top["weighted_score"] = (
            SEMANTIC_SIMILARITY_WEIGHT * top["similarity_score"]
            + CLAIM_VOLUME_WEIGHT * top["total_claim_count"]
        )

        top = top.sort_values("weighted_score", ascending=False).reset_index(drop=True)

        context_str = self._build_context_str(top)
        selector_text = self._selector_model.generate(
            svc_code_selector_prompt.format(
                query=query,
                service_code_context_str=context_str,
            )
        )

        selector = json_repair.loads(selector_text)
        primary_code = selector["primary_svc_code"]

        primary_row = top[top[CODE_COL].astype(str) == primary_code].iloc[0]

        # NLI FOR PRIMARY
        self._run_nli_guardrail(primary_row[DESC_COL], primary_code)

        # NLI FOR ALTERNATES
        alternative_services = {}
        for alt in selector.get("alternates", [])[:3]:
            row = top[top[CODE_COL].astype(str) == alt]
            if not row.empty:
                desc = row.iloc[0][DESC_COL]
                self._run_nli_guardrail(desc, alt)
                alternative_services[alt] = {"description": desc}

        return {
            "service_code": primary_code,
            "service_code_type": primary_row.get(TYPE_COL, ""),
            "description": primary_row.get(DESC_COL, ""),
            "alternative_services": alternative_services,
            "assumptions": selector.get("assumptions", ""),
        }

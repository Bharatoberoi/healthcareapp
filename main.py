from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import json_repair
import numpy as np
import pandas as pd

APP_DIR = Path(__file__).resolve().parent / "app"

from app.services.impl.llm_client import OpenAIEmbeddingClient, OpenAILLMClient
from app.config.retrieval_scoring import (
	FAISS_INDEX_PATH,
	FAISS_METADATA_PATH,
	TOP_K_RESULTS,
	SEMANTIC_SIMILARITY_WEIGHT,
	CLAIM_VOLUME_WEIGHT,
)
from app.config.llms import RAG_MODEL_NAME, SERVICE_RESOLVER_MODEL_NAME
from app.config.prompts import raq_query_former_prompt, svc_code_selector_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Column names in metadata
CODE_COL = "primary_svc_cd"
TYPE_COL = "servc_type"
DESC_COL = "Consumer-Friendly Description"
TITLE_COL = "Consumer-Friendly Title"


class RetrievalServiceImpl:
	def __init__(self):
		self._faiss_index = None
		self._faiss_metadata = None
		self._embed_client = OpenAIEmbeddingClient()
		self._rag_model = OpenAILLMClient(RAG_MODEL_NAME)
		self._selector_model = OpenAILLMClient(SERVICE_RESOLVER_MODEL_NAME)

	def _load_resources(self):
		if self._faiss_index is None:
			logger.info("Loading FAISS index + metadata")
			self._faiss_index = faiss.read_index(str(APP_DIR / FAISS_INDEX_PATH))
			self._faiss_metadata = pd.read_pickle(str(APP_DIR / FAISS_METADATA_PATH))
		return self._faiss_index, self._faiss_metadata

	def _out_of_scope_response(self, reason: str) -> Dict[str, Any]:
		return {
			"service_code": "Out of Scope",
			"service_code_type": "",
			"description": "",
			"alternative_services": {},
			"assumptions": reason,
		}

	def _extract_service_code_from_query(self, user_query: str) -> Optional[str]:
		q = user_query.strip().upper()
		q = re.sub(r'^"|"$', "", q)
		patterns = [r"^\d{5}$", r"^[A-Z]\d{4}$", r"^\d{4}[A-Z]$"]
		if any(re.fullmatch(p, q) for p in patterns):
			return q
		return None

	def _build_selector_context_str(self, top: pd.DataFrame) -> str:
		lines: List[str] = []
		for _, r in top.iterrows():
			lines.append(
				"- Code: {code}, Title: {title}, Description: {desc}, Claim Volume: {cv}, "
				"Claim Volume/Semantic Similarity Weighted Score: {ws}".format(
					code=r.get(CODE_COL),
					title=r.get(TITLE_COL, ""),
					desc=r.get(DESC_COL, ""),
					cv=r.get("total_claim_count"),
					ws=r.get("weighted_score"),
				)
			)
		return "\n".join(lines)

	def _validate_selector_output(self, output: Dict[str, Any], valid_codes: List[str]) -> Dict[str, Any]:
		if not isinstance(output, dict):
			raise ValueError("Selector LLM output is not a JSON object")

		for key in ("primary_svc_code", "alternates", "assumptions"):
			if key not in output:
				raise ValueError(f"Selector output missing required field: {key}")

		primary = str(output["primary_svc_code"]).strip()
		assumptions = str(output["assumptions"]).strip()
		alternates_raw = output["alternates"]

		if not primary or primary not in valid_codes:
			raise ValueError(f"Primary service code not in retrieved codes: {primary}")

		if not isinstance(alternates_raw, list):
			raise ValueError("Selector alternates must be a list")

		if not assumptions:
			raise ValueError("Selector assumptions cannot be empty")

		alternates: List[str] = []
		for a in alternates_raw:
			c = str(a).strip()
			if not c or c == primary:
				continue
			if c not in valid_codes:
				raise ValueError(f"Alternate code not in retrieved codes: {c}")
			if c not in alternates:
				alternates.append(c)

		return {"primary_svc_code": primary, "alternates": alternates, "assumptions": assumptions}

	def resolve_service_code(self, query: str, service_code: Optional[str] = None) -> Dict[str, Any]:
		index, metadata = self._load_resources()

		if service_code is None:
			detected = self._extract_service_code_from_query(query)
			if detected:
				service_code = detected

		if service_code:
			code = str(service_code).strip().upper()
			row = metadata[metadata[CODE_COL].astype(str) == code]
			if row.empty:
				return self._out_of_scope_response(
					"No matching service codes were found for the provided service code."
				)
			rag_query = row[DESC_COL].values[0]
		else:
			prompt = raq_query_former_prompt.format(query=query)
			rag_query = self._rag_model.generate(prompt).strip()

			if rag_query.strip().lower() == "out of scope":
				return self._out_of_scope_response(
					"The user's query was determined to be out of scope for service code resolution."
				)

			if rag_query.lower().startswith("service_code:"):
				possible = rag_query.split(":", 1)[1].strip().upper()
				detected = self._extract_service_code_from_query(possible)
				if detected:
					code = detected
					row = metadata[metadata[CODE_COL].astype(str) == code]
					if row.empty:
						return self._out_of_scope_response(
							"No matching service codes were found for the provided service code."
						)
					service_code = code
					rag_query = row[DESC_COL].values[0]

		vec = self._embed_client.embed(rag_query)
		vector = np.array([vec], dtype="float32")
		distances, indices = index.search(vector, TOP_K_RESULTS)
		if indices is None or len(indices) == 0 or len(indices[0]) == 0:
			return self._out_of_scope_response(
				"No matching service codes were found for the provided input."
			)
		top = metadata.iloc[indices[0]].copy()
		if top.empty:
			return self._out_of_scope_response(
				"No matching service codes were found for the provided input."
			)

		top["similarity_score"] = 1 / (1 + distances[0])
		top["weighted_score"] = (
			SEMANTIC_SIMILARITY_WEIGHT * top["similarity_score"]
			+ CLAIM_VOLUME_WEIGHT * top["total_claim_count"]
		)
		top = top.sort_values("weighted_score", ascending=False).reset_index(drop=True)

		context_str = self._build_selector_context_str(top)
		selector_prompt = svc_code_selector_prompt.format(
			query=query,
			service_code_context_str=context_str,
		)
		selector_text = self._selector_model.generate(selector_prompt)
		selector_raw = json_repair.loads(selector_text)

		valid_codes = top[CODE_COL].astype(str).tolist()
		try:
			selector = self._validate_selector_output(selector_raw, valid_codes)
		except Exception as exc:
			logger.error("Selector LLM output validation failed: %s | raw=%r", str(exc), selector_text)
			return self._out_of_scope_response(
				"Unable to confidently select a service code from retrieved candidates."
			)

		if service_code:
			selector["primary_svc_code"] = str(service_code).strip().upper()
			if selector["primary_svc_code"] not in valid_codes:
				return self._out_of_scope_response(
					"No matching service codes were found for the provided service code."
				)

		primary_code = selector["primary_svc_code"]
		primary_df = top[top[CODE_COL].astype(str) == primary_code]
		if primary_df.empty:
			return self._out_of_scope_response("Primary service code not found in retrieved codes.")
		primary_row = primary_df.iloc[0]

		alt_rows: List[Dict[str, Any]] = []
		for alt_code in selector["alternates"]:
			alt_df = top[top[CODE_COL].astype(str) == alt_code]
			if alt_df.empty:
				return self._out_of_scope_response(
					"Unable to confidently select alternate service codes from retrieved candidates."
				)
			alt_rows.append(alt_df.iloc[0].to_dict())

		alternative_services: Dict[str, Any] = {}
		if alt_rows:
			alt_df = pd.DataFrame(alt_rows).copy()
			alt_df = alt_df.sort_values("weighted_score", ascending=False).reset_index(drop=True)
			alt_df["weighted_score_rank"] = alt_df.index + 1

			alt_df = alt_df.sort_values("total_claim_count", ascending=False).reset_index(drop=True)
			alt_df["claim_volume_rank"] = alt_df.index + 1

			for _, r in alt_df.iterrows():
				c = str(r.get(CODE_COL))
				alternative_services[c] = {
					"description": r.get(DESC_COL, ""),
					"weighted_score_rank": int(r["weighted_score_rank"]),
					"claim_volume_rank": int(r["claim_volume_rank"]),
				}

		return {
			"service_code": str(primary_row.get(CODE_COL)),
			"service_code_type": str(primary_row.get(TYPE_COL, "")).strip(),
			"description": primary_row.get(DESC_COL, ""),
			"alternative_services": alternative_services,
			"assumptions": selector["assumptions"],
		}


def _ensure_openai_key():
	if not os.getenv("OPENAI_API_KEY"):
		raise RuntimeError(
			"OPENAI_API_KEY is not set. Please set it before running this script."
		)


def main():
	parser = argparse.ArgumentParser(description="Standalone service code resolver")
	parser.add_argument("--query", required=True, help="User query or description")
	parser.add_argument("--service-code", help="Optional explicit service code")
	args = parser.parse_args()

	_ensure_openai_key()
	service = RetrievalServiceImpl()
	result = service.resolve_service_code(args.query, args.service_code)
	print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
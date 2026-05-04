"""
Internal workflow state models for LangGraph.

These are NOT API-facing — they model the data flowing through graph nodes.
"""

from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel


# ── Pydantic models for structured LLM output ────────────────
class RAGQueryResult(BaseModel):
    """Output of the RAG query-former LLM call."""

    modified_query: str
    is_out_of_scope: bool = False
    scope_reason: str = ""


class ServiceCodeSelection(BaseModel):
    """Output of the service-code selector LLM call."""

    primary_svc_code: str
    alternates: List[str] = []
    assumptions: str = ""
    confidence: float = 0.8


class SafetyClassification(BaseModel):
    """Output of the LLM safety fallback (guardrail Layer 5)."""

    is_harmful: bool = False
    confidence: float = 0.0
    category: str = ""


# ── Trace / audit entries ────────────────────────────────────
class TraceEntry(TypedDict):
    step: str
    status: str
    duration_ms: float
    detail: str


class ErrorEntry(TypedDict):
    step: str
    error: str
    attempt: int


# ── LangGraph Workflow State ─────────────────────────────────
class WorkflowState(TypedDict):
    # Input
    user_query: str
    user_location: str
    insurance_network: str
    insurance_details: Dict[str, Any]
    request_id: str

    # Step 1: Guardrail
    guardrail_passed: bool
    guardrail_detail: str

    # Step 2: Service Code Resolution
    rag_query: str
    service_code_result: Dict[str, Any]
    primary_code: str
    service_description: str
    service_code_type: str
    alternative_services: Dict[str, Any]
    assumptions: str
    confidence_score: float
    retry_count: int
    needs_clarification: bool
    clarification_candidates: List[Dict[str, Any]]

    # Step 3: Provider Lookup
    provider_results: Dict[str, Any]
    selected_provider: Dict[str, Any]

    # Step 4: Cost Estimation
    cost_estimate: Dict[str, Any]

    # Meta
    workflow_trace: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    final_response: Dict[str, Any]

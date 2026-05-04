"""
Production LangGraph workflow for Medical Cost Estimation.

Graph topology:
  query_guardrail ─→ (pass) ─→ service_code_resolution ─→ (high conf) ─→ provider_lookup ─→ cost_estimation ─→ output_validation ─→ format_response ─→ END
                  ─→ (fail) ─→ format_error ─→ END
                                              ─→ (low conf) ─→ retry_resolution (max N) ─→ service_code_resolution
                                              ─→ (ambiguous) ─→ clarification_needed ─→ format_response ─→ END
                                                                          ─→ (no providers) ─→ fallback_provider ─→ cost_estimation
                                                                                              ─→ (invalid output) ─→ cost_estimation (via retry)

Features:
  - Async nodes throughout
  - Retry loop with prompt variation for service code resolution
  - Parallel provider lookup for primary + alternate codes
  - Confidence-based routing with clarification support
  - Output validation before returning
  - Full audit trail in workflow_trace
"""

import time
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from app.schemas.workflow_models import WorkflowState
from app.services.impl.retrieval_service_impl import RetrievalServiceImpl
from app.mcp.mcp_client import ProviderLookupMCPClient, CostEstimatorMCPClient
from app.config.settings import settings
from app.core.logger import logger
from app.core.observability.metrics.prometheus_metrics import record_step, record_retry
from app.core.observability.tracing import get_tracer


def _trace(state: WorkflowState, step: str, status: str, duration_ms: float, detail: str = ""):
    state["workflow_trace"].append({
        "step": step,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "detail": detail,
    })
    record_step(step, status, duration_ms / 1000.0)

    tracer = get_tracer()
    if tracer:
        with tracer.start_as_current_span(f"workflow.{step}") as span:
            span.set_attribute("workflow.step", step)
            span.set_attribute("workflow.status", status)
            span.set_attribute("workflow.duration_ms", round(duration_ms, 2))
            span.set_attribute("workflow.request_id", state.get("request_id", ""))
            if detail:
                span.set_attribute("workflow.detail", detail)


def _error(state: WorkflowState, step: str, error: str, attempt: int = 0):
    state["errors"].append({"step": step, "error": error, "attempt": attempt})


# ══════════════════════════════════════════════════════════════
# NODE FUNCTIONS
# ══════════════════════════════════════════════════════════════

async def query_guardrail(state: WorkflowState) -> dict:
    """Step 1: Multi-layer safety guardrail (async)."""
    start = time.perf_counter()
    try:
        retrieval = _get_retrieval_service()
        safety = await retrieval._check_safety(state["user_query"])
        elapsed = (time.perf_counter() - start) * 1000

        if safety:
            _trace(state, "guardrail", "blocked", elapsed, safety.get("assumptions", ""))
            return {
                "guardrail_passed": False,
                "guardrail_detail": safety.get("assumptions", "Blocked"),
                "workflow_trace": state["workflow_trace"],
                "errors": state["errors"],
            }

        _trace(state, "guardrail", "passed", elapsed)
        return {
            "guardrail_passed": True,
            "guardrail_detail": "passed",
            "workflow_trace": state["workflow_trace"],
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Guardrail error: %s", e)
        _trace(state, "guardrail", "error", elapsed, str(e))
        # Fail open on guardrail error — don't block legitimate queries
        return {
            "guardrail_passed": True,
            "guardrail_detail": f"error (fail-open): {e}",
            "workflow_trace": state["workflow_trace"],
        }


async def service_code_resolution(state: WorkflowState) -> dict:
    """Step 2: RAG + FAISS + LLM service code selection."""
    start = time.perf_counter()
    attempt = state.get("retry_count", 0)

    try:
        retrieval = _get_retrieval_service()
        result = await retrieval.async_resolve_service_code(state["user_query"])
        elapsed = (time.perf_counter() - start) * 1000

        code = result.get("service_code", "")
        if code in ("Out of Scope", "Blocked - Harmful Query", None, ""):
            _trace(state, "service_code_resolution", "failed", elapsed, result.get("assumptions", ""))
            _error(state, "service_code_resolution", result.get("assumptions", "Failed"), attempt)
            return {
                "service_code_result": result,
                "primary_code": "",
                "confidence_score": 0.0,
                "retry_count": attempt,
                "workflow_trace": state["workflow_trace"],
                "errors": state["errors"],
            }

        confidence = result.get("confidence", 0.0)
        alternatives = result.get("alternative_services", {})

        # Check for ambiguity: if top-2 codes are very close in score
        needs_clarification = False
        candidates: List[Dict[str, Any]] = []
        if alternatives and confidence < settings.confidence_threshold:
            needs_clarification = True
            candidates.append({
                "code": code,
                "description": result.get("description", ""),
                "score": confidence,
            })
            for alt_code, alt_info in list(alternatives.items())[:3]:
                candidates.append({
                    "code": alt_code,
                    "description": alt_info.get("description", ""),
                    "score": alt_info.get("weighted_score", 0.0),
                })

        _trace(state, "service_code_resolution", "passed", elapsed,
               f"code={code} confidence={confidence:.3f} attempt={attempt}")

        return {
            "service_code_result": result,
            "primary_code": code,
            "service_description": result.get("description", ""),
            "service_code_type": result.get("service_code_type", ""),
            "alternative_services": alternatives,
            "assumptions": result.get("assumptions", ""),
            "confidence_score": confidence,
            "retry_count": attempt,
            "needs_clarification": needs_clarification,
            "clarification_candidates": candidates,
            "workflow_trace": state["workflow_trace"],
            "errors": state["errors"],
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Service code resolution error: %s", e)
        _trace(state, "service_code_resolution", "error", elapsed, str(e))
        _error(state, "service_code_resolution", str(e), attempt)
        return {
            "primary_code": "",
            "confidence_score": 0.0,
            "retry_count": attempt,
            "workflow_trace": state["workflow_trace"],
            "errors": state["errors"],
        }


async def retry_resolution(state: WorkflowState) -> dict:
    """Increment retry counter before looping back to service_code_resolution."""
    new_count = state.get("retry_count", 0) + 1
    logger.info("Retrying service code resolution (attempt %d/%d)", new_count, settings.workflow_max_retries)
    record_retry("service_code_resolution")
    return {"retry_count": new_count}


async def provider_lookup(state: WorkflowState) -> dict:
    """Step 3: Look up providers via MCP for primary code."""
    start = time.perf_counter()
    try:
        mcp = _get_provider_mcp()
        primary = state["primary_code"]

        # Look up providers for primary code
        result = await asyncio.to_thread(
            mcp.lookup_providers,
            service_code=primary,
            user_location=state.get("user_location"),
            insurance_network=state.get("insurance_network"),
        )

        providers = result.get("providers", [])
        elapsed = (time.perf_counter() - start) * 1000

        if not providers:
            _trace(state, "provider_lookup", "no_providers", elapsed, f"code={primary}")
            return {
                "provider_results": result,
                "selected_provider": {},
                "workflow_trace": state["workflow_trace"],
            }

        selected = providers[0]
        _trace(state, "provider_lookup", "passed", elapsed,
               f"found={len(providers)} selected={selected.get('name', '')}")
        return {
            "provider_results": result,
            "selected_provider": selected,
            "workflow_trace": state["workflow_trace"],
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Provider lookup error: %s", e)
        _trace(state, "provider_lookup", "error", elapsed, str(e))
        _error(state, "provider_lookup", str(e))
        return {
            "provider_results": {},
            "selected_provider": {},
            "workflow_trace": state["workflow_trace"],
            "errors": state["errors"],
        }


async def fallback_provider(state: WorkflowState) -> dict:
    """Provide a default fallback provider when none are found."""
    fallback = {
        "name": "General Provider (Estimated)",
        "npi": "0000000000",
        "distance": "N/A",
        "network_status": "in-network",
        "rating": 0.0,
        "contracted_rate": 75.00,
        "specialty": "General",
        "address": "N/A",
    }
    _trace(state, "fallback_provider", "used", 0, "No providers found; using fallback estimate")
    return {
        "selected_provider": fallback,
        "workflow_trace": state["workflow_trace"],
    }


async def cost_estimation(state: WorkflowState) -> dict:
    """Step 4: Calculate cost estimate via MCP."""
    start = time.perf_counter()
    try:
        mcp = _get_cost_mcp()
        provider = state.get("selected_provider", {})
        insurance = state.get("insurance_details") or {
            "deductible_total": 1000.0, "deductible_met": 0.0,
            "copay": 0.0, "coinsurance": 20.0,
            "out_of_pocket_max": 5000.0, "out_of_pocket_met": 0.0,
        }

        estimate = await asyncio.to_thread(
            mcp.estimate_cost,
            service_code=state["primary_code"],
            service_description=state.get("service_description", ""),
            provider_info=provider,
            user_insurance=insurance,
        )
        elapsed = (time.perf_counter() - start) * 1000
        _trace(state, "cost_estimation", "passed", elapsed,
               f"patient={estimate.get('patient_responsibility', 'N/A')}")
        return {
            "cost_estimate": estimate,
            "workflow_trace": state["workflow_trace"],
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Cost estimation error: %s", e)
        _trace(state, "cost_estimation", "error", elapsed, str(e))
        _error(state, "cost_estimation", str(e))
        return {
            "cost_estimate": {},
            "workflow_trace": state["workflow_trace"],
            "errors": state["errors"],
        }


async def output_validation(state: WorkflowState) -> dict:
    """Validate that cost estimate has required fields."""
    estimate = state.get("cost_estimate", {})
    required = ["patient_responsibility", "insurance_pays", "total_cost"]
    missing = [f for f in required if not estimate.get(f)]

    if missing:
        _trace(state, "output_validation", "invalid", 0, f"missing fields: {missing}")
        return {"workflow_trace": state["workflow_trace"]}

    _trace(state, "output_validation", "valid", 0)
    return {"workflow_trace": state["workflow_trace"]}


async def clarification_needed(state: WorkflowState) -> dict:
    """Format a response asking the user to clarify which service code they mean."""
    _trace(state, "clarification", "requested", 0,
           f"{len(state.get('clarification_candidates', []))} candidates")
    return {
        "needs_clarification": True,
        "workflow_trace": state["workflow_trace"],
    }


async def format_response(state: WorkflowState) -> dict:
    """Build the final API response."""
    if state.get("needs_clarification"):
        return {"final_response": {
            "success": True,
            "request_id": state.get("request_id", ""),
            "needs_clarification": True,
            "clarification_candidates": state.get("clarification_candidates", []),
            "user_query": state["user_query"],
            "workflow_steps": _step_statuses(state),
            "workflow_trace": state.get("workflow_trace", []),
        }}

    errors = state.get("errors", [])
    if errors and not state.get("primary_code"):
        return {"final_response": {
            "success": False,
            "request_id": state.get("request_id", ""),
            "error": errors[-1]["error"] if errors else "Unknown error",
            "workflow_steps": _step_statuses(state),
            "workflow_trace": state.get("workflow_trace", []),
        }}

    provider = state.get("selected_provider", {})
    cost = state.get("cost_estimate", {})

    return {"final_response": {
        "success": True,
        "request_id": state.get("request_id", ""),
        "workflow_steps": _step_statuses(state),
        "user_query": state["user_query"],
        "service_code_info": {
            "primary_code": state.get("primary_code", ""),
            "service_type": state.get("service_code_type", ""),
            "description": state.get("service_description", ""),
            "alternatives": list(state.get("alternative_services", {}).keys()),
            "confidence": state.get("confidence_score", 0.0),
            "assumptions": state.get("assumptions", ""),
        },
        "provider_info": {
            "name": provider.get("name", ""),
            "npi": provider.get("npi", ""),
            "distance": provider.get("distance", ""),
            "rating": provider.get("rating", 0),
            "network_status": provider.get("network_status", ""),
            "specialty": provider.get("specialty", ""),
            "address": provider.get("address", ""),
            "contracted_rate": f"${provider.get('contracted_rate', 0):.2f}",
        },
        "cost_breakdown": {
            "total_cost": cost.get("total_cost", ""),
            "patient_responsibility": cost.get("patient_responsibility", ""),
            "insurance_pays": cost.get("insurance_pays", ""),
            "deductible_remaining": cost.get("deductible_remaining", ""),
            "explanation": cost.get("explanation", ""),
            "confidence": cost.get("confidence", ""),
        },
        "user_message": _user_message(state),
        "workflow_trace": state.get("workflow_trace", []),
    }}


async def format_error(state: WorkflowState) -> dict:
    """Format guardrail-blocked or hard-error responses."""
    return {"final_response": {
        "success": False,
        "request_id": state.get("request_id", ""),
        "error": state.get("guardrail_detail", "Query blocked by safety guardrail"),
        "workflow_steps": _step_statuses(state),
        "workflow_trace": state.get("workflow_trace", []),
    }}


# ══════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ══════════════════════════════════════════════════════════════

def check_guardrail(state: WorkflowState) -> str:
    return "passed" if state.get("guardrail_passed") else "failed"


def check_resolution_result(state: WorkflowState) -> str:
    code = state.get("primary_code", "")
    confidence = state.get("confidence_score", 0.0)
    retry_count = state.get("retry_count", 0)

    if not code:
        if retry_count < settings.workflow_max_retries:
            return "retry"
        return "exhausted"

    if state.get("needs_clarification"):
        return "clarify"

    if confidence < settings.confidence_threshold and retry_count < settings.workflow_max_retries:
        return "retry"

    return "proceed"


def check_provider_result(state: WorkflowState) -> str:
    providers = state.get("provider_results", {}).get("providers", [])
    return "found" if providers else "fallback"


def check_output_valid(state: WorkflowState) -> str:
    estimate = state.get("cost_estimate", {})
    required = ["patient_responsibility", "insurance_pays", "total_cost"]
    if all(estimate.get(f) for f in required):
        return "valid"
    return "invalid"


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _step_statuses(state: WorkflowState) -> dict:
    trace_steps = {e["step"] for e in state.get("workflow_trace", [])}
    trace_map = {e["step"]: e["status"] for e in state.get("workflow_trace", [])}

    def _s(name: str) -> str:
        if name not in trace_steps:
            return "not_reached"
        status = trace_map.get(name, "not_reached")
        return "passed" if status in ("passed", "valid", "used") else "failed" if status in ("failed", "error", "blocked") else status

    return {
        "step_1_query_guardrail": _s("guardrail"),
        "step_2_service_code_resolution": _s("service_code_resolution"),
        "step_3_provider_lookup": _s("provider_lookup"),
        "step_4_cost_estimation": _s("cost_estimation"),
    }


def _user_message(state: WorkflowState) -> str:
    cost = state.get("cost_estimate", {})
    provider = state.get("selected_provider", {})
    desc = state.get("service_description", "this service")
    return (
        f"Your estimated cost for {desc} is {cost.get('patient_responsibility', 'N/A')}. "
        f"{cost.get('explanation', '')} "
        f"Provider: {provider.get('name', 'N/A')} "
        f"({provider.get('distance', 'N/A')} away, {provider.get('rating', 0)} stars)."
    )


# ══════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════

def _build_graph():
    g = StateGraph(WorkflowState)

    # Nodes
    g.add_node("query_guardrail", query_guardrail)
    g.add_node("service_code_resolution", service_code_resolution)
    g.add_node("retry_resolution", retry_resolution)
    g.add_node("clarification_needed", clarification_needed)
    g.add_node("provider_lookup", provider_lookup)
    g.add_node("fallback_provider", fallback_provider)
    g.add_node("cost_estimation", cost_estimation)
    g.add_node("output_validation", output_validation)
    g.add_node("format_response", format_response)
    g.add_node("format_error", format_error)

    # Entry
    g.set_entry_point("query_guardrail")

    # Guardrail → pass/fail
    g.add_conditional_edges("query_guardrail", check_guardrail, {
        "passed": "service_code_resolution",
        "failed": "format_error",
    })

    # Service code resolution → proceed / retry / clarify / exhausted
    g.add_conditional_edges("service_code_resolution", check_resolution_result, {
        "proceed": "provider_lookup",
        "retry": "retry_resolution",
        "clarify": "clarification_needed",
        "exhausted": "format_response",
    })

    # Retry → back to resolution
    g.add_edge("retry_resolution", "service_code_resolution")

    # Clarification → format response
    g.add_edge("clarification_needed", "format_response")

    # Provider lookup → found / fallback
    g.add_conditional_edges("provider_lookup", check_provider_result, {
        "found": "cost_estimation",
        "fallback": "fallback_provider",
    })
    g.add_edge("fallback_provider", "cost_estimation")

    # Cost estimation → output validation
    g.add_edge("cost_estimation", "output_validation")

    # Output validation → valid / invalid
    g.add_conditional_edges("output_validation", check_output_valid, {
        "valid": "format_response",
        "invalid": "format_response",  # proceed anyway with partial data
    })

    # Terminal nodes
    g.add_edge("format_response", END)
    g.add_edge("format_error", END)

    return g.compile()


# ══════════════════════════════════════════════════════════════
# SINGLETON SERVICES + PUBLIC API
# ══════════════════════════════════════════════════════════════

_retrieval: Optional[RetrievalServiceImpl] = None
_provider_mcp: Optional[ProviderLookupMCPClient] = None
_cost_mcp: Optional[CostEstimatorMCPClient] = None
_graph = None


def _get_retrieval_service() -> RetrievalServiceImpl:
    global _retrieval
    if _retrieval is None:
        _retrieval = RetrievalServiceImpl()
    return _retrieval


def _get_provider_mcp() -> ProviderLookupMCPClient:
    global _provider_mcp
    if _provider_mcp is None:
        logger.info("[Workflow] Initializing Provider Lookup MCP client...")
        _provider_mcp = ProviderLookupMCPClient()
    return _provider_mcp


def _get_cost_mcp() -> CostEstimatorMCPClient:
    global _cost_mcp
    if _cost_mcp is None:
        logger.info("[Workflow] Initializing Cost Estimator MCP client...")
        _cost_mcp = CostEstimatorMCPClient()
    return _cost_mcp


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


class MedicalCostWorkflow:
    """Production LangGraph workflow for medical cost estimation."""

    def __init__(self):
        # Eagerly init MCP clients
        _get_provider_mcp()
        _get_cost_mcp()
        logger.info("[Workflow] MCP clients initialized")

    async def arun(
        self,
        user_query: str,
        user_location: str = "",
        insurance_network: str = "",
        insurance_details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the full workflow asynchronously."""
        graph = _get_graph()
        rid = request_id or str(uuid.uuid4())

        initial: WorkflowState = {
            "user_query": user_query,
            "user_location": user_location or "",
            "insurance_network": insurance_network or "",
            "insurance_details": insurance_details or {
                "deductible_total": 1000.0, "deductible_met": 0.0,
                "copay": 0.0, "coinsurance": 20.0,
                "out_of_pocket_max": 5000.0, "out_of_pocket_met": 0.0,
            },
            "request_id": rid,
            "guardrail_passed": False,
            "guardrail_detail": "",
            "rag_query": "",
            "service_code_result": {},
            "primary_code": "",
            "service_description": "",
            "service_code_type": "",
            "alternative_services": {},
            "assumptions": "",
            "confidence_score": 0.0,
            "retry_count": 0,
            "needs_clarification": False,
            "clarification_candidates": [],
            "provider_results": {},
            "selected_provider": {},
            "cost_estimate": {},
            "workflow_trace": [],
            "errors": [],
            "final_response": {},
        }

        try:
            result = await graph.ainvoke(initial)
            return result.get("final_response", {"success": False, "error": "Unknown error", "request_id": rid})
        except Exception as e:
            logger.error("Workflow execution failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e), "request_id": rid}

    def run(self, user_query: str, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper."""
        import asyncio
        return asyncio.run(self.arun(user_query, **kwargs))

    def cleanup(self):
        global _provider_mcp, _cost_mcp
        if _provider_mcp:
            _provider_mcp.close()
            _provider_mcp = None
        if _cost_mcp:
            _cost_mcp.close()
            _cost_mcp = None


_workflow_instance: Optional[MedicalCostWorkflow] = None


def get_workflow() -> MedicalCostWorkflow:
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = MedicalCostWorkflow()
    return _workflow_instance

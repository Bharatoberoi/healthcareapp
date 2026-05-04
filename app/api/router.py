# api/router.py — async endpoints with SSE streaming

import json
import time
import uuid

from fastapi import APIRouter, Query, Body, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.schemas.request import CompleteWorkflowRequest
from app.schemas.response import ErrorResponse
from app.services.impl.retrieval_service_impl import RetrievalServiceImpl
from app.workflows.medical_cost_workflow import get_workflow
from app.services.impl.rate_limiter import RateLimiter
from app.config.settings import settings
from app.core.logger import logger

router = APIRouter(prefix="/resolve-service-codes", tags=["Service Code Resolution"])

_retrieval_service: RetrievalServiceImpl | None = None
_rate_limiter = RateLimiter(settings.rate_limit_rpm)


def _get_retrieval() -> RetrievalServiceImpl:
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalServiceImpl()
    return _retrieval_service


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request):
    """Return an error JSONResponse if rate-limited, else None."""
    if not _rate_limiter.enabled:
        return None
    allowed, retry_after = _rate_limiter.allow(_client_ip(request))
    if not allowed:
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(
                error="Rate limit exceeded",
                error_code="RATE_LIMITED",
                detail=f"Try again in {retry_after}s",
            ).model_dump(),
            headers={"Retry-After": str(retry_after)},
        )
    return None


# ── GET: service code resolution only ─────────────────────────
@router.get("")
async def resolve_service_codes(
    request: Request,
    query: str = Query(..., min_length=1, max_length=2000,
                       description="Natural language query or service code"),
):
    """
    Step 2 only: resolve medical service codes from natural language.
    """
    rl = _check_rate_limit(request)
    if rl:
        return rl

    retrieval = _get_retrieval()
    result = await retrieval.async_resolve_service_code(query=query)
    return result


# ── POST: complete workflow ───────────────────────────────────
@router.post("/complete-workflow")
async def complete_workflow(
    request: Request,
    body: CompleteWorkflowRequest = Body(...),
):
    """
    Complete 4-step workflow: Guardrail -> Service Code -> Provider -> Cost.
    """
    rl = _check_rate_limit(request)
    if rl:
        return rl

    request_id = str(uuid.uuid4())
    workflow = get_workflow()

    insurance = None
    if body.insurance_details:
        insurance = body.insurance_details.model_dump(by_alias=False)

    result = await workflow.arun(
        user_query=body.query,
        user_location=body.user_location or "",
        insurance_network=body.insurance_network or "",
        insurance_details=insurance,
        request_id=request_id,
    )
    return result


# ── POST: streaming workflow via SSE ──────────────────────────
@router.post("/stream")
async def stream_workflow(
    request: Request,
    body: CompleteWorkflowRequest = Body(...),
):
    """
    Stream workflow progress via Server-Sent Events.

    Each step emits:
      event: step_started   data: {"step": "...", "step_number": N}
      event: step_completed data: {"step": "...", "duration_ms": ..., "result": "..."}

    Final event:
      event: workflow_complete data: { ... full response ... }
    """
    rl = _check_rate_limit(request)
    if rl:
        return rl

    request_id = str(uuid.uuid4())

    async def _event_generator():
        workflow = get_workflow()
        insurance = None
        if body.insurance_details:
            insurance = body.insurance_details.model_dump(by_alias=False)

        # Emit start
        yield {
            "event": "workflow_started",
            "data": json.dumps({"request_id": request_id, "query": body.query}),
        }

        # Run the full workflow
        start = time.perf_counter()
        result = await workflow.arun(
            user_query=body.query,
            user_location=body.user_location or "",
            insurance_network=body.insurance_network or "",
            insurance_details=insurance,
            request_id=request_id,
        )
        total_ms = (time.perf_counter() - start) * 1000

        # Emit per-step events from the workflow trace
        trace = result.get("workflow_trace", [])
        step_num = 0
        for entry in trace:
            step_num += 1
            yield {
                "event": "step_completed",
                "data": json.dumps({
                    "step": entry.get("step", ""),
                    "step_number": step_num,
                    "status": entry.get("status", ""),
                    "duration_ms": entry.get("duration_ms", 0),
                    "detail": entry.get("detail", ""),
                }),
            }

        # Final event
        event_type = "workflow_complete" if result.get("success") else "workflow_error"
        yield {
            "event": event_type,
            "data": json.dumps({
                "request_id": request_id,
                "total_duration_ms": round(total_ms, 2),
                **result,
            }),
        }

    return EventSourceResponse(_event_generator())

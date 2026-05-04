"""
Prometheus metrics — HTTP-level and per-workflow-step instrumentation.
"""

import time

from fastapi import Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ── HTTP-level metrics ────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_response_time_seconds", "HTTP response time", ["method", "path"]
)
ERROR_COUNT = Counter(
    "http_errors_total", "Total HTTP 5xx errors", ["method", "path", "status"]
)

# ── Workflow step metrics ─────────────────────────────────────
STEP_DURATION = Histogram(
    "workflow_step_duration_seconds",
    "Duration of each workflow step",
    ["step"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
STEP_STATUS = Counter(
    "workflow_step_status_total",
    "Outcome of each workflow step",
    ["step", "status"],
)
LLM_DURATION = Histogram(
    "llm_call_duration_seconds",
    "Duration of individual LLM API calls",
    ["model", "call_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
WORKFLOW_RETRIES = Counter(
    "workflow_retries_total",
    "Number of workflow retry loops triggered",
    ["step"],
)
CIRCUIT_BREAKER_STATE = Counter(
    "circuit_breaker_transitions_total",
    "Circuit breaker state transitions",
    ["name", "to_state"],
)
RATE_LIMIT_REJECTED = Counter(
    "rate_limit_rejected_total",
    "Requests rejected by rate limiter",
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        start = time.time()
        status = "500"
        try:
            resp = await call_next(request)
            status = str(resp.status_code)
            return resp
        except Exception:
            raise
        finally:
            elapsed = time.time() - start
            try:
                REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)
                REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
                if status.startswith("5"):
                    ERROR_COUNT.labels(method=method, path=path, status=status).inc()
            except Exception:
                pass


def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Convenience helpers for workflow code ─────────────────────
def record_step(step: str, status: str, duration_s: float):
    STEP_DURATION.labels(step=step).observe(duration_s)
    STEP_STATUS.labels(step=step, status=status).inc()


def record_llm_call(model: str, call_type: str, duration_s: float):
    LLM_DURATION.labels(model=model, call_type=call_type).observe(duration_s)


def record_retry(step: str):
    WORKFLOW_RETRIES.labels(step=step).inc()

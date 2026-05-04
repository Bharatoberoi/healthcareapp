# app/main.py — Production FastAPI application

import asyncio
import time
import uuid

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as service_code_router
from app.config.settings import settings
from app.core.logger import logger

app = FastAPI(
    title="Medical Cost Estimation API",
    description=(
        "Production workflow: Query Guardrail -> Service Code Resolution (FAISS) "
        "-> Provider Lookup -> Cost Estimation"
    ),
    version="2.0.0",
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Observability (Prometheus + OpenTelemetry) ────────────────
try:
    from app.core.observability.metrics.prometheus_metrics import (
        PrometheusMiddleware,
        metrics_endpoint,
    )
    from app.core.observability.tracing import initialize_tracing

    app.add_middleware(PrometheusMiddleware)
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])

    if settings.enable_tracing:
        initialize_tracing(app)
except Exception:
    logger.warning("Observability (Prometheus/OpenTelemetry) not fully available")


# ── Request ID + Timeout middleware ───────────────────────────
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    start = time.perf_counter()

    try:
        response = await asyncio.wait_for(
            call_next(request),
            timeout=settings.request_timeout_seconds,
        )
        response.headers["x-request-id"] = request_id
        elapsed = (time.perf_counter() - start) * 1000
        response.headers["x-response-time-ms"] = f"{elapsed:.2f}"
        return response
    except asyncio.TimeoutError:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Request timed out after %.0fms [%s %s]", elapsed, request.method, request.url.path)
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "error": "Request timed out",
                "error_code": "TIMEOUT",
                "request_id": request_id,
            },
            headers={"x-request-id": request_id},
        )
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
            headers={"x-request-id": request_id},
        )


# ── Routes ────────────────────────────────────────────────────
app.include_router(service_code_router)

_FRONTEND_HTML = Path(__file__).resolve().parent.parent / "frontend.html"


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    if _FRONTEND_HTML.exists():
        return HTMLResponse(content=_FRONTEND_HTML.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Medical Cost Estimation API</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": "2.0.0",
    }


@app.get("/ready")
async def readiness_check():
    try:
        from app.services.impl.retrieval_service_impl import RetrievalServiceImpl
        RetrievalServiceImpl()._load_resources()
        return {
            "ready": True,
            "vector_backend": "faiss",
            "faiss_ready": True,
        }
    except Exception as e:
        logger.warning("Readiness: FAISS retrieval not ready: %s", e)
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "vector_backend": "faiss",
                "faiss_ready": False,
                "error": str(e),
            },
        )


# ── Startup ───────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("=" * 80)
    logger.info("Medical Cost Estimation API starting")
    logger.info("  Environment : %s", settings.environment)
    logger.info("  LLM Model   : %s", settings.llm_model_name)
    logger.info("  Embedding   : %s", settings.embedding_model_name)
    logger.info("  Rate Limit  : %d RPM", settings.rate_limit_rpm)
    logger.info("=" * 80)

    if settings.preload_faiss:
        try:
            from app.services.impl.retrieval_service_impl import RetrievalServiceImpl

            logger.info("Warming FAISS index + metadata...")
            RetrievalServiceImpl()._load_resources()
            logger.info("FAISS retrieval warmed successfully")
        except Exception as ex:
            logger.exception("Failed to warm FAISS retrieval: %s", ex)

    # Eagerly init workflow (starts MCP servers)
    try:
        from app.workflows.medical_cost_workflow import get_workflow
        get_workflow()
    except Exception as ex:
        logger.exception("Workflow init error: %s", ex)

    logger.info("Endpoints:")
    logger.info("  GET  /health")
    logger.info("  GET  /ready")
    logger.info("  GET  /resolve-service-codes")
    logger.info("  POST /resolve-service-codes/complete-workflow")
    logger.info("  POST /resolve-service-codes/stream")
    logger.info("  GET  /metrics")
    logger.info("  GET  /docs")
    logger.info("=" * 80)

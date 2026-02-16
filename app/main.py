# main.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router as service_code_router
from app.core.logger import logger
import os
from app.services.impl.retrieval_service_impl import RetrievalServiceImpl

app = FastAPI(
    title="Medical Cost Estimation API",
    description="Complete workflow for medical cost estimation: Query Guardrail → Service Code Resolution → Provider Lookup → Cost Estimation",
    version="2.0.0",
)

# -------------------------
# CORS middleware
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Observability middleware & routes
# -------------------------
try:
    from app.core.observability.metrics.prometheus_metrics import (
        PrometheusMiddleware,
        metrics_endpoint,
    )
    from app.core.observability.tracing import initialize_tracing

    # Add Prometheus middleware (records latency, counts, errors)
    app.add_middleware(PrometheusMiddleware)

    # Expose /metrics for Prometheus scraping
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])  # noqa: E305

    # Initialize OpenTelemetry tracing (safe no-op if packages missing)
    initialize_tracing(app)
except Exception:
    # Observability should never prevent the app from starting
    logger.warning("Observability (Prometheus/OpenTelemetry) not fully available")

# -------------------------
# Global error handler middleware
# -------------------------
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Global error handler for all requests"""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(e)
            }
        )

# -------------------------
# Register routers
# -------------------------
app.include_router(service_code_router)

# -------------------------
# Health check
# -------------------------
@app.get("/health")
def health_check():
    """
    Lightweight health endpoint for readiness/liveness checks.
    """
    return {"status": "ok"}


# -------------------------
# Readiness & Startup
# -------------------------
@app.get("/ready")
def readiness_check():
    """
    Readiness endpoint: returns 200 only when FAISS index and metadata are loaded.
    This prevents the LB from sending traffic to a pod before vector index is memory-resident.
    """
    try:
        RetrievalServiceImpl()._load_resources()
        return {"ready": True, "faiss_loaded": True}
    except Exception as e:
        logger.warning("Readiness check: FAISS not loaded yet: %s", e)
        return JSONResponse(status_code=503, content={"ready": False, "faiss_loaded": False, "error": str(e)})


@app.on_event("startup")
def on_startup():
    logger.info("=" * 80)
    logger.info("Medical Cost Estimation API starting")
    logger.info("=" * 80)

    # Optionally preload FAISS (recommended for low first-request latency)
    preload = os.getenv("PRELOAD_FAISS", "true").lower() in ("1", "true", "yes")
    if preload:
        try:
            logger.info("Preloading FAISS index into memory (this may increase startup time)...")
            RetrievalServiceImpl()._load_resources()
            logger.info("FAISS index preloaded successfully")
        except Exception as ex:
            logger.exception("Failed to preload FAISS index on startup: %s", ex)

    logger.info("Architecture: Using MCP (Model Context Protocol)")
    logger.info("  • Step 1: Query Guardrail (Local)")
    logger.info("  • Step 2: Service Code Resolution (Local)")
    logger.info("  • Step 3: Provider Lookup (MCP Server)")
    logger.info("  • Step 4: Cost Estimator (MCP Server)")
    logger.info("\nAvailable endpoints:")
    logger.info("  GET  /health - Health check")
    logger.info("  GET  /ready  - Readiness (FAISS loaded)")
    logger.info("  GET  /resolve-service-codes - Step 2: Service code resolution only")
    logger.info("  POST /resolve-service-codes/complete-workflow - Steps 1-4: Complete workflow")
    logger.info("\nAPI Documentation: http://localhost:8000/docs")
    logger.info("=" * 80) 

"""OpenTelemetry tracing bootstrap (safe if packages missing).

Initializes tracing with conservative sampling and exporter fallback:
- Uses Cloud Trace exporter when available (best default on GCP)
- Falls back to OTLP exporter for custom backends
"""
import os

from app.config.settings import settings
from app.core.logger import logger

_tracer = None


def get_tracer():
    """Return the OTel tracer (or None if tracing is disabled)."""
    return _tracer


def initialize_tracing(app, service_name: str = "service-code-resolution-api"):
    global _tracer
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        sample_ratio = max(0.0, min(1.0, float(settings.trace_sample_ratio)))
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(TraceIdRatioBased(sample_ratio)),
        )

        span_exporter = None
        # Prefer GCP-native exporter on Cloud Run; fallback to OTLP otherwise.
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            span_exporter = CloudTraceSpanExporter()
            logger.info("Tracing exporter: Cloud Trace")
        except Exception:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            span_exporter = OTLPSpanExporter(
                endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            )
            logger.info("Tracing exporter: OTLP")

        provider.add_span_processor(BatchSpanProcessor(span_exporter))

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)

        FastAPIInstrumentor().instrument_app(app)

        logger.info(
            "OpenTelemetry tracing initialized (sample_ratio=%.2f)",
            sample_ratio,
        )
    except Exception as exc:
        logger.warning("OpenTelemetry tracing NOT enabled (%s). Proceeding without tracing.", exc)

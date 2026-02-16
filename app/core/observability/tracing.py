"""OpenTelemetry tracing bootstrap (safe if packages missing).

Initializes OTLP exporter + FastAPI instrumentation. Uses environment
variables to control OTLP endpoint (OTEL_EXPORTER_OTLP_ENDPOINT).
"""
from app.core.logger import logger


def initialize_tracing(app, service_name: str = "service-code-resolution-api"):
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        span_exporter = OTLPSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(span_exporter))

        trace.set_tracer_provider(provider)

        # Instrument FastAPI app + outgoing requests
        FastAPIInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()

        logger.info("OpenTelemetry tracing initialized (OTLP exporter)")
    except Exception as exc:
        logger.warning("OpenTelemetry tracing NOT enabled (%s). Proceeding without tracing.", exc)

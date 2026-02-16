# """
# OpenTelemetry metrics bootstrap.

# This file is SAFE to import even if OpenTelemetry
# packages are NOT installed.
# """

# from app.core.logger import logger

# # Metrics placeholders (safe defaults)
# meter = None
# request_counter = None
# error_counter = None
# response_time_histogram = None
# exception_counter = None


# def initialize_metrics():
#     """
#     Initialize OpenTelemetry metrics.

#     If OpenTelemetry is not installed, this function
#     logs a warning and safely exits.
#     """
#     global meter
#     global request_counter
#     global error_counter
#     global response_time_histogram
#     global exception_counter

#     try:
#         from opentelemetry import metrics
#         from opentelemetry.sdk.metrics import MeterProvider
#         from opentelemetry.sdk.resources import Resource
#         from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
#         from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
#             OTLPMetricExporter,
#         )

#         resource = Resource.create(
#             {"service.name": "service-code-resolution-api"}
#         )

#         exporter = OTLPMetricExporter()
#         reader = PeriodicExportingMetricReader(exporter)

#         provider = MeterProvider(resource=resource, metric_readers=[reader])
#         metrics.set_meter_provider(provider)

#         meter = metrics.get_meter(__name__)

#         request_counter = meter.create_counter(
#             "http_requests_total",
#             description="Total HTTP requests",
#         )

#         error_counter = meter.create_counter(
#             "http_errors_total",
#             description="Total HTTP errors",
#         )

#         exception_counter = meter.create_counter(
#             "exceptions_total",
#             description="Total exceptions",
#         )

#         response_time_histogram = meter.create_histogram(
#             "http_response_time_ms",
#             description="HTTP response time in milliseconds",
#         )

#         logger.info("OpenTelemetry metrics initialized successfully")

#     except Exception as exc:
#         logger.warning(
#             "OpenTelemetry metrics NOT enabled (%s). Running without metrics.",
#             str(exc),
#         )

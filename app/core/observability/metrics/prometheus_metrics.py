from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import time

# Metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_response_time_seconds", "HTTP response time (seconds)", ["method", "path"]
)
ERROR_COUNT = Counter(
    "http_errors_total", "Total HTTP errors", ["method", "path", "status"]
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count, latency and errors for Prometheus scraping.

    This is kept lightweight and safe if Prometheus client is not scraped.
    """

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        start = time.time()
        try:
            resp = await call_next(request)
            status = str(resp.status_code)
            return resp
        except Exception as exc:
            status = "500"
            raise
        finally:
            elapsed = time.time() - start
            # record
            try:
                REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)
                REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
                if status.startswith("5"):
                    ERROR_COUNT.labels(method=method, path=path, status=status).inc()
            except Exception:
                # metrics should never break request flow
                pass


def metrics_endpoint():
    """WAI for Prometheus to scrape metrics."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

from typing import Dict, Any, Optional
from fastapi import Request

from app.core.logger import logger
from app.core.observability.metrics.metrics_decorators import exception_handler
from app.exception.exceptions import ServiceCodeNotResolvedException


def produce_response_content(
    exc: Exception,
    headers: Optional[Dict[str, str]] = None,
    request: Optional[Request] = None,
) -> Dict[str, Any]:

    return {
        "correlationId": (
            headers.get("x-global-transaction-id")
            if headers and "x-global-transaction-id" in headers
            else request.headers.get("x-global-transaction-id", "")
            if request
            else ""
        ),
        "title": "Service code not resolved",
        "status": 422,
        "detail": str(exc),
        "message": "Service code could not be resolved for the given input",
    }


@exception_handler(
    exception_type="service_code_resolution",
    exception_name="ServiceCodeNotResolvedException",
)
def service_code_not_resolved_handler_logic(
    exc: ServiceCodeNotResolvedException,
    headers: Optional[Dict[str, str]] = None,
    request: Optional[Request] = None,
) -> Dict[str, Any]:

    logger.warning("Service code not resolved: %s", exc.message)
    return produce_response_content(exc, headers, request)

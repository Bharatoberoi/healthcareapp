import time
import functools
from typing import Callable, Any

from app.core.logger import logger


def exception_handler(exception_type: str, exception_name: str):
    """
    Decorator used to wrap service-layer functions and log exceptions consistently.

    This is SAFE even if OpenTelemetry is disabled.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                elapsed_ms = (time.time() - start_time) * 1000

                logger.error(
                    "[%s] %s raised after %.2f ms | %s",
                    exception_type,
                    exception_name,
                    elapsed_ms,
                    str(exc),
                    exc_info=True,
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                elapsed_ms = (time.time() - start_time) * 1000

                logger.error(
                    "[%s] %s raised after %.2f ms | %s",
                    exception_type,
                    exception_name,
                    elapsed_ms,
                    str(exc),
                    exc_info=True,
                )
                raise

        # Decide sync vs async automatically
        if callable(func) and func.__code__.co_flags & 0x80:
            return async_wrapper

        return sync_wrapper

    return decorator

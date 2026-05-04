"""
Async structured-output LLM client.

Uses OpenAI's JSON-schema response_format so every reply is
guaranteed to parse into the requested Pydantic model.
Includes exponential backoff retries and circuit-breaker protection.
"""

import asyncio
import logging
import time
from typing import List, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config.settings import settings
from app.services.impl.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from app.core.observability.metrics.prometheus_metrics import record_llm_call

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Module-level circuit breakers (shared across instances per process)
_llm_breaker = CircuitBreaker(
    name="llm",
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout=settings.circuit_breaker_recovery_timeout,
    window=settings.circuit_breaker_window,
)
_embedding_breaker = CircuitBreaker(
    name="embedding",
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout=settings.circuit_breaker_recovery_timeout,
    window=settings.circuit_breaker_window,
)


def _is_transient(exc: Exception) -> bool:
    err = str(exc).lower()
    return any(kw in err for kw in [
        "rate_limit", "429", "500", "502", "503",
        "timeout", "connection", "overloaded",
    ])


# ── Async Embedding Client ───────────────────────────────────
class AsyncEmbeddingClient:
    def __init__(self, model: str = settings.embedding_model_name):
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key, timeout=settings.llm_timeout
        )
        self._model = model

    async def embed(self, text: str) -> List[float]:
        last_exc: Optional[Exception] = None
        for attempt in range(settings.max_retries):
            try:
                async with _embedding_breaker:
                    t0 = time.perf_counter()
                    resp = await self._client.embeddings.create(
                        model=self._model, input=text
                    )
                    record_llm_call(self._model, "embedding", time.perf_counter() - t0)
                    return resp.data[0].embedding
            except CircuitBreakerOpen:
                raise
            except Exception as exc:
                last_exc = exc
                if not _is_transient(exc) or attempt == settings.max_retries - 1:
                    raise
                delay = settings.retry_base_delay * (2 ** attempt)
                logger.warning(
                    "Embedding transient error (attempt %d/%d), retry in %.1fs: %s",
                    attempt + 1, settings.max_retries, delay, exc,
                )
                await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]


# ── Async Structured LLM Client ──────────────────────────────
class AsyncStructuredLLM:
    """
    Calls OpenAI chat completions with structured JSON output.

    Usage:
        result = await llm.generate(
            prompt="...",
            response_model=ServiceCodeSelection,
            system="You are a medical coding assistant.",
        )
    """

    def __init__(self, model: str = settings.llm_model_name):
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key, timeout=settings.llm_timeout
        )
        self._model = model

    async def generate(
        self,
        prompt: str,
        response_model: Type[T],
        system: str = "You are a medical coding assistant.",
    ) -> T:
        """Call the LLM and parse the result into *response_model*."""
        last_exc: Optional[Exception] = None
        for attempt in range(settings.max_retries):
            try:
                async with _llm_breaker:
                    t0 = time.perf_counter()
                    resp = await self._client.beta.chat.completions.parse(
                        model=self._model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        response_format=response_model,
                        temperature=0,
                    )
                    record_llm_call(self._model, "structured", time.perf_counter() - t0)
                    parsed = resp.choices[0].message.parsed
                    if parsed is None:
                        raise ValueError("LLM returned None parsed output")
                    return parsed
            except CircuitBreakerOpen:
                raise
            except Exception as exc:
                last_exc = exc
                if not _is_transient(exc) or attempt == settings.max_retries - 1:
                    raise
                delay = settings.retry_base_delay * (2 ** attempt)
                logger.warning(
                    "LLM transient error (attempt %d/%d), retry in %.1fs: %s",
                    attempt + 1, settings.max_retries, delay, exc,
                )
                await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    async def generate_text(
        self,
        prompt: str,
        system: str = "You are a medical coding assistant.",
    ) -> str:
        """Plain text completion (no structured output)."""
        last_exc: Optional[Exception] = None
        for attempt in range(settings.max_retries):
            try:
                async with _llm_breaker:
                    t0 = time.perf_counter()
                    resp = await self._client.chat.completions.create(
                        model=self._model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0,
                    )
                    record_llm_call(self._model, "text", time.perf_counter() - t0)
                    return resp.choices[0].message.content.strip()
            except CircuitBreakerOpen:
                raise
            except Exception as exc:
                last_exc = exc
                if not _is_transient(exc) or attempt == settings.max_retries - 1:
                    raise
                delay = settings.retry_base_delay * (2 ** attempt)
                logger.warning(
                    "LLM text transient error (attempt %d/%d), retry in %.1fs: %s",
                    attempt + 1, settings.max_retries, delay, exc,
                )
                await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]


# ── Backward-compatible sync wrappers (for guardrail init) ───
class OpenAIEmbeddingClient:
    """Synchronous embedding client — used during startup / preload."""

    def __init__(self, model: str = settings.embedding_model_name):
        from openai import OpenAI
        self._client = OpenAI(
            api_key=settings.openai_api_key, timeout=settings.llm_timeout
        )
        self._model = model

    def embed(self, text: str) -> List[float]:
        resp = self._client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding

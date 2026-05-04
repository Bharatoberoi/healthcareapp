"""
Async Query Guardrail — 5-layer safety filter with TTL cache.

Layers execute in order with early exit:
  1. Regex pattern matching          (~0.001 s)
  2. OpenAI Moderation API           (~0.15  s)
  3. Semantic similarity vs. known   (~0.15  s)
  4. Lightweight intent rules        (~0     s)
  5. LLM structured fallback         (~0.3   s)  — rare (<5 % of queries)

Identical queries are cached (TTL 5 min) so repeats skip all layers.
"""

# --- Standard library ---
import hashlib  # stable fingerprint for cache keys (SHA-256 of normalized query)
import logging  # structured logs for each layer and failures
import re  # compile and run regex patterns (Layer 1, Layer 5)
import time  # monotonic clock for TTL expiry (not wall-clock, safer for intervals)
from typing import Dict, List, Tuple  # type hints for cache entries and return pairs

# --- Third party ---
import numpy as np  # float vectors for cosine-style similarity in Layer 3
from openai import AsyncOpenAI  # async client for Moderation API (Layer 2)

# --- App ---
from app.config.settings import settings  # API key, timeouts for OpenAI calls
from app.schemas.workflow_models import SafetyClassification  # Pydantic model for Layer 5 LLM output
from app.services.impl.structured_llm import (
    AsyncEmbeddingClient,  # embed user query asynchronously (Layer 3)
    AsyncStructuredLLM,  # structured JSON/class output from LLM (Layer 5)
    OpenAIEmbeddingClient,  # sync embed at startup for known harmful templates
)
from app.services.impl.circuit_breaker import CircuitBreakerOpen  # skip or fail-open when embed/LLM circuit is open

logger = logging.getLogger(__name__)  # logger named after this module for log filtering

_CACHE_TTL = 300  # seconds — how long a guardrail decision stays in RAM before rechecking (300 = 5 minutes)


class OptimizedQueryGuardrail:
    """Async multi-layer query safety guardrail."""

    # ── Layer 1: regex patterns ───────────────────────────────
    CRITICAL_HARM_PATTERNS = [
        r"(?i)(lethal\s+dose|lethal\s+amount|how\s+to.*kill|how\s+to.*die)",  # suicide / lethal dosing language
        r"(?i)(end\s+my\s+life|end\s+things|suicide\s+method|overdose.*method)",  # explicit self-harm methods
        r"(?i)(painless\s+way|fastest\s+way|easiest\s+way).*(overdose|die|suicide|harm)",  # “easy way to die” style
        r"(?i)(helium|nitrogen|carbon\s+monoxide).*(tank|method|end.*life)",  # means often discussed for self-harm
        r"(?i)(barbiturate|nembutal).*(suicide|lethal|fatal)",  # high-risk substances + harm intent
        r"(?i)(drug\s+someone|slip.*drug|without.*knowledge|unaware|undetectable)",  # drugging others / covert dosing
        r"(?i)(rohypnol|flunitrazepam|date\s+rape|sexual.*assault)",  # assault / date-rape drug context
        r"(?i)(dissolve.*drink|dissolve.*beverage|no\s+taste|colorless|odorless).*(?:drug|sedative|benzodiazepine)",  # spiking drinks
        r"(?i)(amnesia|unconscious|incapacitate).*(?:drug|medication|alcohol)",  # incapacitation intent
        r"(?i)(forge.*prescription|fake.*prescription|doctor\s+shopping)",  # prescription fraud
        r"(?i)(obtain.*prescription.*without|prescription.*mill|pill\s+mill)",  # illegal prescribing / mills
        r"(?i)(testosterone.*without.*ask|without.*question.*testosterone)",  # bypassing clinical safeguards
    ]

    HARM_KEYWORDS = {
        "self_harm": ["lethal", "die", "suicide", "overdose", "fatal", "end my life", "painless"],  # category: self-harm lexicon
        "drug_others": ["drug", "drink", "unaware", "undetectable", "dissolve", "without knowledge", "rohypnol"],  # category: harm to others
        "fraud": ["forge", "fake", "prescription", "doctor shopping", "pill mill"],  # category: fraud lexicon
    }

    KNOWN_HARMFUL_QUERIES = [
        "lethal dose of medication",  # canonical bad query for embedding comparison (Layer 3)
        "how to overdose painlessly",  # template for semantic “near harmful” detection
        "methods to commit suicide",  # template
        "drug someone without knowledge",  # template
        "date rape drugs",  # template
        "fake prescription",  # template
        "how to harm myself",  # template
    ]

    def __init__(self):
        sync_embed = OpenAIEmbeddingClient()  # blocking embed client used only during __init__
        self._async_embed = AsyncEmbeddingClient()  # reused for Layer 3 on each request
        self._llm = AsyncStructuredLLM()  # reused for Layer 5 when reached
        self._compiled_patterns = [re.compile(p) for p in self.CRITICAL_HARM_PATTERNS]  # compile once for fast Layer 1 scans
        self._async_openai = AsyncOpenAI(
            api_key=settings.openai_api_key, timeout=settings.llm_timeout  # credentials + per-call timeout cap
        )

        # Pre-compute embeddings for known harmful queries (sync, at init)
        self._known_harmful_embeddings: List[Dict] = []  # list of {query, embedding} for Layer 3
        try:
            logger.info("Initializing guardrail embeddings cache...")  # startup breadcrumb
            for q in self.KNOWN_HARMFUL_QUERIES:  # one embedding per template string
                emb = sync_embed.embed(q)  # OpenAI embedding vector for this template
                self._known_harmful_embeddings.append({
                    "query": q,  # keep human-readable label for debugging (optional use)
                    "embedding": np.array(emb, dtype=np.float32),  # fixed-size vector for cosine similarity
                })
            logger.info("Embeddings initialized for %d queries", len(self._known_harmful_embeddings))  # confirm count
        except Exception as e:
            logger.error("Failed to initialize guardrail embeddings: %s", e)  # Layer 3 may become no-op if empty

        # TTL cache: hash → (is_blocked, details, expiry)
        self._cache: Dict[str, Tuple[bool, Dict, float]] = {}  # in-process only; not shared across machines

    # ── Cache helpers ─────────────────────────────────────────
    @staticmethod
    def _hash(query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()  # same text → same key (case/space normalized)

    def _cache_get(self, key: str):
        entry = self._cache.get(key)  # look up prior decision by hash key
        if entry and entry[2] > time.monotonic():  # entry[2] is expiry time; monotonic avoids clock skew issues
            return entry[0], entry[1]  # return (blocked: bool, detail dict) if still fresh
        return None  # miss or expired → caller must run layers again

    def _cache_set(self, key: str, blocked: bool, details: Dict):
        self._cache[key] = (blocked, details, time.monotonic() + _CACHE_TTL)  # store verdict + wall-less expiry instant
        # Evict old entries periodically
        if len(self._cache) > 10_000:  # cap memory if traffic is huge / many unique queries
            now = time.monotonic()  # current time for comparison
            self._cache = {k: v for k, v in self._cache.items() if v[2] > now}  # keep only non-expired rows

    # ── Layer 1: pattern matching ─────────────────────────────
    def _check_patterns(self, query: str) -> Tuple[bool, Dict]:
        query_lower = query.lower()  # case-insensitive keyword scan below
        for pattern in self._compiled_patterns:  # try each critical regex in order
            if pattern.search(query):  # match anywhere in original string (regex may use (?i))
                return True, {"type": "pattern_match", "confidence": 0.95}  # blocked + reason metadata

        for category, keywords in self.HARM_KEYWORDS.items():  # secondary: count keyword hits per category
            if sum(1 for kw in keywords if kw in query_lower) >= 3:  # ≥3 hits from same list → suspicious density
                return True, {"type": "keyword_frequency", "category": category, "confidence": 0.90}  # blocked with category tag

        return False, {}  # Layer 1 passed — empty detail dict

    # ── Layer 2: OpenAI Moderation (async) ────────────────────
    async def _check_moderation(self, query: str) -> Tuple[bool, Dict]:
        help_keywords = [
            "help", "therapist", "doctor", "provider", "treatment", "counselor",  # help-seeking signals
            "specialist", "support", "recovery", "addiction", "find", "mental health",  # more help-seeking
            "overdose reversal", "naloxone", "narcan", "therapy", "counseling",  # harm reduction / care context
        ]
        query_lower = query.lower()  # normalize for substring checks
        if any(kw in query_lower for kw in help_keywords):  # looks like someone asking for help, not harm
            if "overdose" in query_lower:  # sensitive word — need finer check
                safe_terms = ["counter", "reversal", "antidote", "naloxone", "narcan", "prevent"]  # reversal / safety framing
                if any(t in query_lower for t in safe_terms):  # e.g. “overdose reversal” → do not call moderation
                    return False, {}  # treat as safe; skip moderation call
            else:  # help keywords but no “overdose” substring
                return False, {}  # skip moderation to avoid false positives on benign help queries
        try:
            resp = await self._async_openai.moderations.create(input=query)  # OpenAI moderation scores/categories
            if resp.results[0].flagged:  # first result: overall flagged or not
                return True, {"type": "openai_moderation", "confidence": 0.88}  # blocked by vendor moderation
        except Exception as e:
            logger.debug("Moderation API unavailable: %s", e)  # network/outage — fail open below
        return False, {}  # not blocked (either safe or moderation skipped/unavailable)

    # ── Layer 3: semantic similarity (async) ──────────────────
    async def _check_semantic(self, query: str, threshold: float = 0.70) -> Tuple[bool, Dict]:
        if not self._known_harmful_embeddings:  # startup embed failed — cannot compare
            return False, {}  # skip layer (fail open for this layer only)
        try:
            emb = np.array(await self._async_embed.embed(query), dtype=np.float32)  # live query embedding
            max_sim, _ = 0.0, None  # track strongest similarity to any template (second value unused, style leftover)
            for h in self._known_harmful_embeddings:  # compare to each precomputed harmful template
                sim = float(np.dot(emb, h["embedding"]) / (  # cosine similarity core: dot product divided by norms
                    np.linalg.norm(emb) * np.linalg.norm(h["embedding"]) + 1e-8  # +eps avoids divide-by-zero
                ))
                if sim > max_sim:  # keep the maximum across templates
                    max_sim = sim  # update best match strength
            if max_sim > threshold:  # “close enough” to a known harmful paraphrase
                return True, {"type": "semantic_similarity", "similarity": round(max_sim, 3), "confidence": min(0.92, max_sim)}  # block with debug score
        except CircuitBreakerOpen:
            logger.warning("[GUARDRAIL:L3] Embedding circuit breaker open — skipping semantic check")  # too many failures upstream
        except Exception as e:
            logger.debug("Semantic check failed: %s", e)  # transient embed errors
        return False, {}  # not blocked by similarity

    # ── Layer 4: intent rules ─────────────────────────────────
    def _check_intent(self, query: str) -> Tuple[bool, Dict]:
        ql = query.lower()  # shorthand for repeated checks

        # Life-saving requests are SAFE
        if any(kw in ql for kw in ["overdose reversal", "naloxone", "narcan"]):  # explicit harm-reduction vocabulary
            if "overdose" in ql and any(w in ql for w in ["get", "find", "obtain"]):  # “get naloxone” style
                return False, {"type": "intent_safe", "confidence": 0.98}  # explicitly allow

        help_kw = ["provider", "doctor", "therapist", "counselor", "specialist", "find"]  # navigation to care
        safe_kw = ["help", "treatment", "therapy", "counsel", "naloxone", "narcan"]  # therapeutic / rescue framing
        if any(h in ql for h in help_kw) and any(s in ql for s in safe_kw):  # both help-finding and benign intent
            return False, {"type": "intent_help_seeking", "confidence": 0.92}  # allow

        seeking = ["where to get", "how to obtain", "prescription for", "how do i get"]  # acquisition phrasing
        substances = ["opioid", "barbiturate", "benzodiazepine", "rohypnol", "flunitrazepam", "helium"]  # dangerous acquisition targets
        methods = ["lethal", "overdose", "suicide", "end things", "painless way"]  # self-harm method words

        if any(s in ql for s in seeking):  # user is asking how to obtain something
            if any(sub in ql for sub in substances):  # …and names dangerous substances
                return True, {"type": "intent_substance_seeking", "confidence": 0.93}  # block
            if any(m in ql for m in methods):  # …or pairs seeking with self-harm methods
                return True, {"type": "intent_self_harm", "confidence": 0.91}  # block

        if any(kw in ql for kw in ["drink", "beverage", "tasteless", "colorless", "unaware", "undetectable"]):  # covert administration cues
            if any(kw in ql for kw in ["drug", "sedative", "benzodiazepine", "rohypnol", "amnesia"]):  # …plus drug/incapacitation
                return True, {"type": "intent_drugging", "confidence": 0.94}  # block

        return False, {}  # Layer 4 passed

    # ── Layer 5: LLM fallback (structured) ────────────────────
    async def _check_llm_fallback(self, query: str) -> Tuple[bool, Dict]:
        ql = query.lower()  # normalized text for regex + keyword heuristics below
        help_patterns = [
            r"what\s+(?:should\s+)?i\s+(?:do|can)",  # “what should I do” style (often crisis/help)
            r"what\s+to\s+do",  # short variant
            r"how\s+can\s+i\s+help\s+(?:myself|my)",  # helping self/family phrasing
        ]
        explicit_harm = ["lethal", "how to kill", "how to die", "overdose method", "drug someone", "poison"]  # if present, do not short-circuit
        for pat in help_patterns:  # try each help-shaped regex
            if re.search(pat, ql) and not any(kw in ql for kw in explicit_harm):  # help language without explicit harm list
                return False, {"type": "llm_help_seeking", "confidence": 0.95}  # skip expensive LLM — treat as safe

        prompt = (
            'Determine if this medical-service query seeks to harm self/others, '  # instruction line 1
            'obtain substances illegally, or commit fraud.\n'  # instruction line 2
            'HELP-SEEKING is SAFE. HARM-SEEKING is UNSAFE.\n\n'  # disambiguation rule for the model
            f'Query: "{query}"'  # user text injected for classification
        )
        try:
            result = await self._llm.generate(
                prompt=prompt,  # user-visible task description
                response_model=SafetyClassification,  # parsed fields: is_harmful, confidence, category, etc.
                system="You are a safety classifier for a medical cost estimation app.",  # system role string
            )
            is_harmful = result.is_harmful and result.confidence > 0.65  # require both flag and minimum confidence
            return is_harmful, {"type": "llm_fallback", "confidence": result.confidence, "category": result.category}  # block or pass with metadata
        except CircuitBreakerOpen:
            logger.warning("[GUARDRAIL:L5] Circuit breaker open — fail-open (pass)")  # do not block traffic on outage
            return False, {"type": "circuit_breaker_open", "confidence": 0.0}  # pass
        except Exception as e:
            logger.error("LLM guardrail fallback failed: %s", e)  # log full error server-side
            return False, {}  # pass on LLM failure (fail open)

    # ── Main entry point ──────────────────────────────────────
    async def check_query(self, query: str) -> Tuple[bool, Dict]:
        cache_key = self._hash(query)  # fingerprint for lookup/store
        cached = self._cache_get(cache_key)  # try RAM shortcut first
        if cached is not None:  # hit fresh cache
            return cached  # same tuple shape as full run: (blocked, details)

        # Layer 1
        blocked, detail = self._check_patterns(query)  # fast regex / keyword density
        if blocked:  # early exit on hard pattern
            logger.warning("[GUARDRAIL:L1] Blocked: %s", detail.get("type"))  # audit which rule fired
            self._cache_set(cache_key, True, detail)  # remember block for TTL window
            return True, detail  # (True, …) means caller should block pipeline

        # Layer 2
        blocked, detail = await self._check_moderation(query)  # async OpenAI moderation
        if blocked:
            logger.warning("[GUARDRAIL:L2] Blocked by moderation")
            self._cache_set(cache_key, True, detail)
            return True, detail

        # Layer 3
        blocked, detail = await self._check_semantic(query)  # async embed + cosine vs templates
        if blocked:
            logger.warning("[GUARDRAIL:L3] Blocked by similarity %.3f", detail.get("similarity", 0))
            self._cache_set(cache_key, True, detail)
            return True, detail

        # Layer 4
        blocked, detail = self._check_intent(query)  # pure Python rules
        if blocked:
            logger.warning("[GUARDRAIL:L4] Blocked: %s", detail.get("type"))
            self._cache_set(cache_key, True, detail)
            return True, detail

        # Layer 5
        blocked, detail = await self._check_llm_fallback(query)  # async LLM only if still unclear
        if blocked:
            logger.warning("[GUARDRAIL:L5] Blocked by LLM")
            self._cache_set(cache_key, True, detail)
            return True, detail

        safe_detail = {"blocked": False, "message": "Passed all safety checks"}  # positive record for cache/debug
        self._cache_set(cache_key, False, safe_detail)  # remember “allowed” for TTL (speed on repeat)
        return False, safe_detail  # (False, …) means pipeline may continue

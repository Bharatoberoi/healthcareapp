# Implementation Plan 2: Production Readiness (This Week)

## Objective
Deploy the Medical Cost Estimation API to production with reduced operational and safety risk.

## Must Do Before Production

1. Replace mock dependencies with real services.
- `app/mcp/provider_lookup_server.py` and `app/mcp/cost_estimator_server.py` are demo stubs.
- If real integrations aren’t ready, explicitly ship as “beta estimates” with hard limits and clear user messaging.

2. Lock down API security.
- Add auth (OAuth2/JWT or API keys) on all business endpoints in `app/api/router.py`.
- Restrict CORS in `app/main.py` (`allow_origins=["*"]` is not production-safe).
- Add request rate limiting and payload size limits at gateway/ingress.

3. Harden reliability around external calls.
- Add strict timeouts, retries with backoff, and circuit breakers for OpenAI/MCP calls.
- Fail gracefully with typed error codes, not generic 500s.

4. Unify guardrail behavior.
- Workflow guardrail in `app/workflows/medical_cost_workflow.py` is keyword-based, while stronger logic exists in `app/services/impl/optimized_query_guardrail.py`.
- Use one guardrail path in production to avoid inconsistent safety behavior.

5. Secrets and config hygiene.
- Move all secrets to a secret manager (not env files in CI logs).
- Add config validation at startup (required env vars, model names, index paths).

6. Observability and on-call readiness.
- Ensure request IDs, structured logs, latency/error metrics, and alerting thresholds are active.
- Validate `/metrics`, dashboards, and alerts in `k8s/monitoring/` with a real load test.

7. Production tests gate deployment.
- Add CI gates for: smoke tests, integration tests, and one load test scenario (`load-test/k6-script.js`).
- Block release if p95 latency/error budget thresholds fail.

8. Kubernetes hardening.
- Set resource requests/limits, PDB, readiness/liveness tuning, and HPA sanity bounds in `k8s/`.
- Use rolling/canary deployment with fast rollback.

9. Compliance/privacy controls.
- For medical domain: minimize PHI in logs, encrypt in transit/at rest, define retention/deletion.
- Confirm legal/compliance requirements before launch.

10. Release strategy this week.
- Do staged rollout: internal -> 5% traffic -> 25% -> 100%.
- Keep feature flags to disable Step 3/4 quickly if external dependencies fail.

## Best 7-Day Execution Order
1. Security + secrets + CORS/auth
2. Guardrail unification + timeout/retry/circuit breaker
3. Real provider/cost integrations (or explicit beta fallback)
4. Observability + alerts + SLO dashboard validation
5. CI release gates + canary + rollback drill

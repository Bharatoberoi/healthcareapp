"""
Full API test suite - tests all endpoints with multiple scenarios.

Prerequisites for a full pass:
  - API running (e.g. uvicorn app.main:app --host 127.0.0.1 --port 8000)
  - app/.env with OPENAI_API_KEY; FAISS index + metadata at default paths (or env overrides)

Env:
  API_BASE_URL  (default: http://127.0.0.1:8000)
"""
import os
import requests
import json
import time

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PASS = "[PASS]"
FAIL = "[FAIL]"
SEP  = "=" * 65

def print_result(label, status_code, body, expected_success=True):
    ok = (status_code == 200)
    tag = PASS if ok else FAIL
    print(f"\n{tag} {label}")
    print(f"     Status : {status_code}")
    if isinstance(body, dict):
        for k, v in body.items():
            val = str(v)[:120]
            print(f"     {k:25s}: {val}")
    else:
        print(f"     Body   : {str(body)[:200]}")

# ------------------------------------------------------------------ #
print(SEP)
print("  MEDICAL COST ESTIMATION API - FULL TEST SUITE")
print(SEP)

# ── TEST 1: Health ────────────────────────────────────────────────── #
print("\n--- INFRA TESTS ---")
r = requests.get(f"{BASE}/health", timeout=5)
print_result("GET /health", r.status_code, r.json())

# ── TEST 2: Readiness (FAISS load can be slow on first request / cold instance) ── #
r = requests.get(f"{BASE}/ready", timeout=90)
print_result("GET /ready", r.status_code, r.json())

# ── TEST 3: Service Code - Chiropractor ──────────────────────────── #
print("\n--- SERVICE CODE RESOLUTION (Step 2 only) ---")
r = requests.get(f"{BASE}/resolve-service-codes",
                 params={"query": "chiropractor visit for back pain"}, timeout=60)
print_result("GET /resolve-service-codes  [chiropractor]", r.status_code, r.json())

# ── TEST 4: Service Code - Annual Physical ────────────────────────── #
r = requests.get(f"{BASE}/resolve-service-codes",
                 params={"query": "annual physical exam"}, timeout=60)
print_result("GET /resolve-service-codes  [annual physical]", r.status_code, r.json())

# ── TEST 5: Service Code - Direct Code Input ──────────────────────── #
r = requests.get(f"{BASE}/resolve-service-codes",
                 params={"query": "99213"}, timeout=60)
print_result("GET /resolve-service-codes  [direct code 99213]", r.status_code, r.json())

# ── TEST 6: Out-of-scope query ────────────────────────────────────── #
r = requests.get(f"{BASE}/resolve-service-codes",
                 params={"query": "what is the weather today"}, timeout=60)
print_result("GET /resolve-service-codes  [out-of-scope]", r.status_code, r.json())

# ── TEST 7: Complete Workflow - Chiropractor ──────────────────────── #
print("\n--- COMPLETE WORKFLOW (All 4 Steps) ---")
payload = {
    "query": "I need a chiropractor visit for back pain",
    "user_location": "90210",
    "insurance_network": "Aetna",
    "insurance_details": {
        "deductible_total": 1000.0,
        "deductible_met": 0.0,
        "copay": 0.0,
        "coinsurance": 20.0,
        "out_of_pocket_max": 5000.0,
        "out_of_pocket_met": 0.0
    }
}
print("\n  Running complete workflow (30-60s)...")
start = time.time()
r = requests.post(f"{BASE}/resolve-service-codes/complete-workflow",
                  json=payload, timeout=120)
elapsed = round(time.time() - start, 1)
body = r.json()
print_result(f"POST /complete-workflow  [chiropractor]  ({elapsed}s)", r.status_code, body)

# ── TEST 8: Complete Workflow - MRI ──────────────────────────────── #
payload2 = {
    "query": "MRI scan for knee injury",
    "user_location": "10001",
    "insurance_network": "UnitedHealth",
    "insurance_details": {
        "deductible_total": 2000.0,
        "deductible_met": 1500.0,
        "copay": 0.0,
        "coinsurance": 20.0,
        "out_of_pocket_max": 6000.0,
        "out_of_pocket_met": 1500.0
    }
}
print("\n  Running complete workflow (30-60s)...")
start = time.time()
r = requests.post(f"{BASE}/resolve-service-codes/complete-workflow",
                  json=payload2, timeout=120)
elapsed = round(time.time() - start, 1)
body = r.json()
print_result(f"POST /complete-workflow  [MRI knee]  ({elapsed}s)", r.status_code, body)

# ── TEST 9: Harmful query guardrail block ────────────────────────── #
payload3 = {
    "query": "how to forge a prescription",
    "user_location": "12345",
    "insurance_network": "Aetna"
}
print("\n  Testing guardrail (harmful query)...")
start = time.time()
r = requests.post(f"{BASE}/resolve-service-codes/complete-workflow",
                  json=payload3, timeout=120)
elapsed = round(time.time() - start, 1)
body = r.json()
print_result(f"POST /complete-workflow  [harmful - guardrail]  ({elapsed}s)", r.status_code, body)

# ── SUMMARY ──────────────────────────────────────────────────────── #
print(f"\n{SEP}")
print("  ALL TESTS COMPLETE")
print(SEP)

"""End-to-end test: run workflow in-process and print full result."""
import json
import os
import sys
import logging

# Suppress INFO logs for cleaner output (optional: set to logging.INFO to see steps)
logging.getLogger().setLevel(logging.WARNING)
for _ in ("httpx", "openai", "app", "service_code_resolution_service"):
    logging.getLogger(_).setLevel(logging.WARNING)

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.workflows.medical_cost_workflow import MedicalCostWorkflow

query = "I need a chiropractor visit for back pain"
payload = {
    "user_query": query,
    "user_location": "90210",
    "insurance_network": "Aetna",
    "insurance_details": {
        "deductible_total": 1000.0,
        "deductible_met": 0.0,
        "copay": 0.0,
        "coinsurance": 20.0,
        "out_of_pocket_max": 5000.0,
        "out_of_pocket_met": 0.0,
    },
}

print("=" * 70)
print("END-TO-END TEST: Complete Medical Cost Workflow")
print("=" * 70)
print(f'\nQuery: "{query}"')
print("Location: 90210 | Network: Aetna")
print("\nRunning workflow (Step 1 -> 2 -> 3 -> 4)...")
print("This may take 30-90 seconds (LLM + FAISS).\n")

try:
    workflow = MedicalCostWorkflow()
    result = workflow.run(
        user_query=payload["user_query"],
        user_location=payload["user_location"],
        insurance_network=payload["insurance_network"],
        insurance_details=payload["insurance_details"],
    )
    print("Status: 200 (OK)")
    print("\n--- FULL RESPONSE ---\n")
    print(json.dumps(result, indent=2))
    print("\n--- END ---")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

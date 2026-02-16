"""
Simple API test script - Test the complete workflow endpoint
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("API TEST - Complete Medical Cost Workflow")
print("=" * 70)

# Test query
query = "I need a chiropractor visit for back pain"

payload = {
    "query": query,
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

print(f"\nQuery: \"{query}\"")
print(f"Location: 90210 | Network: Aetna")
print("\nCalling API (may take 30-60 seconds)...\n")

try:
    response = requests.post(
        f"{BASE_URL}/resolve-service-codes/complete-workflow",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=120
    )
    
    print(f"Status Code: {response.status_code}\n")
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
except requests.exceptions.Timeout:
    print("Request timed out. The workflow is taking longer than expected.")
except requests.exceptions.ConnectionError:
    print("Connection error. Make sure the server is running:")
    print("   python run_app.py")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 70)
print("Tip: Visit http://localhost:8000/docs for interactive API documentation")
print("=" * 70)

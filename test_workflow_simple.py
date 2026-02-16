"""
Simple test for the complete workflow
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Test the complete workflow
payload = {
    "query": "I need a chiropractor visit for back pain",
    "user_location": "12345",
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

print("Testing complete workflow endpoint...")
print(f"Request: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(
        f"{BASE_URL}/resolve-service-codes/complete-workflow",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {str(e)}")

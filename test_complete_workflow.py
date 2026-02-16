"""
Test script for the complete medical cost estimation workflow
"""

import requests
import json

# Base URL - adjust if running on different host/port
BASE_URL = "http://localhost:8000"

def test_complete_workflow():
    """Test the complete workflow endpoint"""
    
    # Test case 1: Valid medical query
    print("=" * 80)
    print("Test 1: Complete workflow with chiropractor query")
    print("=" * 80)
    
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
    
    try:
        response = requests.post(
            f"{BASE_URL}/resolve-service-codes/complete-workflow",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Make sure the server is running: uvicorn app.main:app --reload")
    
    print("\n")
    
    # Test case 2: Out of scope query
    print("=" * 80)
    print("Test 2: Out of scope query (should fail at guardrail)")
    print("=" * 80)
    
    payload = {
        "query": "What's the weather today?",
        "user_location": "12345",
        "insurance_network": "Aetna"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/resolve-service-codes/complete-workflow",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n")
    
    # Test case 3: Service code resolution only (original endpoint)
    print("=" * 80)
    print("Test 3: Service code resolution only (original endpoint)")
    print("=" * 80)
    
    try:
        response = requests.get(
            f"{BASE_URL}/resolve-service-codes",
            params={"query": "chiropractor visit"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    test_complete_workflow()

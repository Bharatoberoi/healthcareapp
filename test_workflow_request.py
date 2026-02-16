#!/usr/bin/env python3
"""
Test script for the updated medical cost estimation workflow
"""

import requests
import json
import time

# Base URL - adjust if running on different host/port
BASE_URL = "http://localhost:8000"

def test_complete_workflow():
    """Test the complete workflow endpoint"""
    
    print("\n" + "=" * 80)
    print("Testing Complete Medical Cost Estimation Workflow")
    print("=" * 80 + "\n")
    
    # Wait a moment for server to be ready
    time.sleep(2)
    
    # Test case 1: Valid medical query
    print("TEST: Complete workflow with chiropractor query")
    print("-" * 80)
    
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
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"\nResponse:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("\n✓ Workflow completed successfully!")
                print("\nWorkflow Steps:")
                for step, status in result.get("workflow_steps", {}).items():
                    print(f"  {step}: {status}")
            else:
                print(f"\n✗ Workflow failed: {result.get('error')}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to server. Make sure it's running on port 8000")
    except Exception as e:
        print(f"ERROR: {str(e)}")
    
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    test_complete_workflow()

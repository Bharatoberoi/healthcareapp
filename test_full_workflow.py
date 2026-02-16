#!/usr/bin/env python3
"""
Test the COMPLETE 4-STEP workflow according to workflow_graph.txt
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_complete_workflow():
    """Test the complete 4-step workflow"""
    
    print("\n")
    print("=" * 100)
    print("COMPLETE MEDICAL COST ESTIMATION WORKFLOW - ALL 4 STEPS")
    print("=" * 100)
    print("\nUser Query: 'I need a chiropractor visit for back pain'")
    print("\nWorkflow Steps:")
    print("  STEP 1: Query Guardrail → Validate medical query")
    print("  STEP 2: Service Code Resolution → Resolve to service code (98940)")
    print("  STEP 3: Provider Lookup → Find providers")
    print("  STEP 4: Cost Estimation → Calculate patient cost")
    print("\n" + "=" * 100 + "\n")
    
    time.sleep(1)
    
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
        print("Sending POST request to /resolve-service-codes/complete-workflow...")
        print(f"Payload: {json.dumps(payload, indent=2)}\n")
        
        response = requests.post(
            f"{BASE_URL}/resolve-service-codes/complete-workflow",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        print(f"Response Status: {response.status_code}\n")
        
        result = response.json()
        
        print("=" * 100)
        print("WORKFLOW RESPONSE (According to workflow_graph.txt)")
        print("=" * 100)
        print(json.dumps(result, indent=2))
        print("\n" + "=" * 100)
        
        if response.status_code == 200 and result.get("success"):
            print("\n✓ COMPLETE WORKFLOW SUCCESS!\n")
            
            # Extract key information
            steps = result.get("workflow_steps", {})
            service_info = result.get("service_code_info", {})
            provider = result.get("provider_info", {})
            cost = result.get("cost_breakdown", {})
            message = result.get("user_message", "")
            
            print("STEP SUMMARY:")
            for step_name, step_status in steps.items():
                icon = "✓" if step_status == "passed" else "✗"
                print(f"  {icon} {step_name}: {step_status}")
            
            print("\nSERVICE CODE INFO:")
            print(f"  Primary Code: {service_info.get('primary_code')}")
            print(f"  Service Type: {service_info.get('service_type')}")
            print(f"  Title: {service_info.get('title')}")
            print(f"  Description: {service_info.get('description')[:100]}...")
            print(f"  Alternatives: {service_info.get('alternatives')}")
            print(f"  Confidence: {service_info.get('confidence')}")
            
            print("\nPROVIDER INFO:")
            print(f"  Name: {provider.get('name')}")
            print(f"  NPI: {provider.get('npi')}")
            print(f"  Distance: {provider.get('distance')}")
            print(f"  Rating: {provider.get('rating')}★")
            print(f"  Network Status: {provider.get('network_status')}")
            print(f"  Specialty: {provider.get('specialty')}")
            print(f"  Contracted Rate: {provider.get('contracted_rate')}")
            
            print("\nCOST BREAKDOWN:")
            print(f"  Total Cost: {cost.get('total_cost')}")
            print(f"  Patient Responsibility: {cost.get('patient_responsibility')}")
            print(f"  Insurance Pays: {cost.get('insurance_pays')}")
            print(f"  Deductible Remaining: {cost.get('deductible_remaining')}")
            print(f"  Explanation: {cost.get('explanation')}")
            print(f"  Confidence: {cost.get('confidence')}")
            
            print("\nFINAL USER MESSAGE:")
            print(message)
            
        else:
            print(f"\n✗ Workflow failed")
            print(f"Error: {result.get('error')}")
            print(f"Step failed: {result.get('step_failed')}")
        
        print("\n" + "=" * 100 + "\n")
        
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out (request took too long)")
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to server on port 8000")
        print("Make sure the server is running: cd 'c:\\Users\\HP\\OneDrive\\Desktop\\Bhargav\\code_3 - Copy' ; .venv\\Scripts\\python.exe run_app.py")
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    test_complete_workflow()


from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_complete_workflow():
    print("Testing complete workflow for: 'chiropractor'")
    payload = {
        "query": "I need a chiropractor visit for back pain",
        "user_location": "10001",
        "insurance_plan": "Aetna",
        "member_id": "12345"
    }
    
    # Note: The endpoint path might need adjustment based on main.py
    # Looking at main.py, it includes service_service_router.
    # Let's check router.py for the exact path.
    response = client.post("/resolve-service-codes/complete-workflow", json=payload)
    
    if response.status_code != 200:
        print(f"Failed: {response.status_code}")
        print(response.text)
    else:
        print("Success!")
        print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    test_complete_workflow()

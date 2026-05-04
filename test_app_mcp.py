from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_query():
    print("Testing query: 'chiropractor'")
    response = client.get("/resolve-service-codes?query=chiropractor")
    if response.status_code != 200:
        print(f"Failed: {response.status_code}")
        print(response.text)
    else:
        print("Success!")
        print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    test_query()

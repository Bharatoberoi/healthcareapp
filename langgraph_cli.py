import sys
import json
from typing import Any, Dict

def load_payload() -> Dict[str, Any]:
    try:
        raw = sys.stdin.read()
        if raw and raw.strip():
            return json.loads(raw)
    except Exception:
        pass
    # fallback to args
    if len(sys.argv) > 1:
        return {"query": " ".join(sys.argv[1:])}
    return {"query": "I need a chiropractor visit for back pain"}

def main():
    payload = load_payload()
    # Import locally to avoid heavy startup when not used
    try:
        from app.workflows.medical_cost_workflow import get_workflow
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Import error: {e}"}))
        sys.exit(1)

    workflow = get_workflow()
    result = workflow.run(
        user_query=payload.get("query", ""),
        user_location=payload.get("user_location"),
        insurance_network=payload.get("insurance_network"),
        insurance_details=payload.get("insurance_details"),
    )
    # Print only machine-readable JSON
    sys.stdout.write(json.dumps(result))

if __name__ == "__main__":
    main()


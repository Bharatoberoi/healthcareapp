"""
LangGraph End-to-End Medical Cost Estimation Application

Pure LangGraph application - no API server. Runs as:
    python langgraph_app.py "I need a chiropractor visit for back pain"

Flow:
    User Input -> [Guardrail] -> [Service Code Resolution] -> [Provider Lookup] -> [Cost Estimation] -> Output
"""

import sys
import os
import json
import logging

# Ensure app modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from app.services.impl.retrieval_service_impl import RetrievalServiceImpl
from app.mcp.provider_lookup_server import ProviderLookupServer
from app.mcp.cost_estimator_server import CostEstimatorServer

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("langgraph_app")
logger.setLevel(logging.WARNING)

# Suppress noisy loggers
for name in ("httpx", "openai", "app", "service_code_resolution_service",
             "app.services.impl.optimized_query_guardrail"):
    logging.getLogger(name).setLevel(logging.WARNING)

BLUE   = "\033[94m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

# ────────────────────────────────────────────────────────────────
# STATE
# ────────────────────────────────────────────────────────────────
class WorkflowState(TypedDict):
    user_query: str
    user_location: str
    insurance_network: str
    insurance_details: Dict[str, Any]
    guardrail_passed: bool
    service_code_response: Dict[str, Any]
    primary_code: str
    service_description: str
    provider_response: Dict[str, Any]
    selected_provider: Dict[str, Any]
    cost_estimate: Dict[str, Any]
    final_response: Dict[str, Any]
    error: str


# ────────────────────────────────────────────────────────────────
# NODE FUNCTIONS
# ────────────────────────────────────────────────────────────────
retrieval_service = None
provider_lookup   = None
cost_estimator    = None


def init_services():
    global retrieval_service, provider_lookup, cost_estimator
    if retrieval_service is None:
        retrieval_service = RetrievalServiceImpl()
        provider_lookup   = ProviderLookupServer()
        cost_estimator    = CostEstimatorServer()


def query_guardrail(state: WorkflowState) -> dict:
    """STEP 1: Query Guardrail - validates user query"""
    print(f"\n{CYAN}{'='*70}")
    print(f"  STEP 1: QUERY GUARDRAIL")
    print(f"{'='*70}{RESET}")
    print(f"  Input: \"{state['user_query']}\"")

    query_lower = state["user_query"].lower()
    medical_kw = [
        "doctor", "hospital", "clinic", "medical", "health", "visit", "pain",
        "injury", "surgery", "therapy", "treatment", "exam", "test", "mri",
        "prescription", "medication", "chiropractor", "dentist", "eye",
        "emergency", "urgent", "care", "physical", "xray", "scan", "lab",
    ]
    has_medical = any(k in query_lower for k in medical_kw)
    has_code    = any(c.isdigit() for c in state["user_query"])

    if has_medical or has_code:
        print(f"  {GREEN}[PASS] Query is medical-related{RESET}")
        return {"guardrail_passed": True}
    else:
        print(f"  {RED}[FAIL] Query is NOT medical-related{RESET}")
        return {"guardrail_passed": False, "error": "Query is not medical-related"}


def service_code_resolution(state: WorkflowState) -> dict:
    """STEP 2: Service Code Resolution via RAG + FAISS + LLM"""
    print(f"\n{CYAN}{'='*70}")
    print(f"  STEP 2: SERVICE CODE RESOLUTION (RAG + FAISS + LLM)")
    print(f"{'='*70}{RESET}")
    print(f"  A. Query Enhancement (RAG)")
    print(f"     - OpenAI Embeddings (text-embedding-3-small)")
    print(f"     - FAISS Vector Search (top-k=10)")
    print(f"  B. Code Selection (LLM)")
    print(f"     - Semantic similarity scoring (80%)")
    print(f"     - Claim volume weighting (20%)")
    print(f"     - LLM selects best match")
    print(f"  {DIM}Processing...{RESET}", end="", flush=True)

    init_services()
    result = retrieval_service.resolve_service_code(state["user_query"])

    if result.get("service_code") in ("Out of Scope", "Blocked - Harmful Query", None, ""):
        reason = result.get("assumptions", "Failed")
        print(f"\r  {RED}[FAIL] {reason}{RESET}")
        return {"error": reason}

    code = result["service_code"]
    desc = result.get("description", "")
    alts = list(result.get("alternative_services", {}).keys())

    print(f"\r  {GREEN}[PASS]{RESET}                          ")
    print(f"  {BOLD}Primary Code : {code}{RESET}")
    print(f"  Type        : {result.get('service_code_type', '')}")
    print(f"  Description : {desc[:80]}")
    print(f"  Alternatives: {alts}")

    return {
        "service_code_response": result,
        "primary_code": code,
        "service_description": desc,
    }


def provider_lookup_node(state: WorkflowState) -> dict:
    """STEP 3: Provider Lookup (MCP Tool)"""
    print(f"\n{CYAN}{'='*70}")
    print(f"  STEP 3: PROVIDER LOOKUP (MCP)")
    print(f"{'='*70}{RESET}")
    print(f"  Input: service_code={state['primary_code']}, location={state.get('user_location','N/A')}, network={state.get('insurance_network','N/A')}")

    init_services()
    result = provider_lookup.lookup_providers(
        service_code=state["primary_code"],
        user_location=state.get("user_location"),
        insurance_network=state.get("insurance_network"),
    )

    providers = result.get("providers", [])
    if not providers:
        print(f"  {RED}[FAIL] No providers found{RESET}")
        return {"error": "No providers found"}

    top = providers[0]
    print(f"  {GREEN}[PASS]{RESET} Found {len(providers)} provider(s)")
    print(f"  {BOLD}Selected : {top['name']}{RESET}")
    print(f"  NPI      : {top['npi']}")
    print(f"  Distance : {top['distance']}")
    print(f"  Rating   : {top['rating']} stars")
    print(f"  Network  : {top['network_status']}")
    print(f"  Rate     : ${top['contracted_rate']:.2f}")

    return {"provider_response": result, "selected_provider": top}


def cost_estimation_node(state: WorkflowState) -> dict:
    """STEP 4: Cost Estimation (MCP Tool)"""
    print(f"\n{CYAN}{'='*70}")
    print(f"  STEP 4: COST ESTIMATION (MCP)")
    print(f"{'='*70}{RESET}")

    if state.get("error"):
        return {}

    init_services()
    provider  = state["selected_provider"]
    insurance = state.get("insurance_details", {
        "deductible_total": 1000.0, "deductible_met": 0.0,
        "copay": 0.0, "coinsurance": 20.0,
        "out_of_pocket_max": 5000.0, "out_of_pocket_met": 0.0,
    })

    ded_rem = insurance.get("deductible_total", 0) - insurance.get("deductible_met", 0)
    print(f"  Base rate       : ${provider.get('contracted_rate',0):.2f} (contracted)")
    print(f"  Deductible left : ${ded_rem:.2f}")
    print(f"  Coinsurance     : {insurance.get('coinsurance',0)}%")
    print(f"  Copay           : ${insurance.get('copay',0):.2f}")

    estimate = cost_estimator.estimate_cost(
        service_code=state["primary_code"],
        service_description=state["service_description"],
        provider_info=provider,
        user_insurance=insurance,
    )

    print(f"\n  {GREEN}[PASS]{RESET}")
    print(f"  {BOLD}Patient Pays  : {estimate['patient_responsibility']}{RESET}")
    print(f"  Insurance Pays: {estimate['insurance_pays']}")
    print(f"  Deductible Left: {estimate['deductible_remaining']}")
    print(f"  Explanation   : {estimate['explanation']}")

    return {"cost_estimate": estimate}


def format_response(state: WorkflowState) -> dict:
    """Final formatting node"""
    if state.get("error"):
        return {"final_response": {"success": False, "error": state["error"]}}

    provider = state.get("selected_provider", {})
    cost     = state.get("cost_estimate", {})

    return {"final_response": {
        "success": True,
        "service_code": state["primary_code"],
        "service_description": state["service_description"],
        "provider": provider.get("name", ""),
        "patient_pays": cost.get("patient_responsibility", ""),
        "insurance_pays": cost.get("insurance_pays", ""),
        "deductible_remaining": cost.get("deductible_remaining", ""),
        "explanation": cost.get("explanation", ""),
    }}


def check_guardrail(state: WorkflowState) -> str:
    return "passed" if state.get("guardrail_passed") else "failed"


# ────────────────────────────────────────────────────────────────
# BUILD LANGGRAPH
# ────────────────────────────────────────────────────────────────
def build_graph():
    g = StateGraph(WorkflowState)

    g.add_node("query_guardrail",        query_guardrail)
    g.add_node("service_code_resolution", service_code_resolution)
    g.add_node("provider_lookup",         provider_lookup_node)
    g.add_node("cost_estimation",         cost_estimation_node)
    g.add_node("format_response",         format_response)

    g.set_entry_point("query_guardrail")

    g.add_conditional_edges("query_guardrail", check_guardrail, {
        "passed": "service_code_resolution",
        "failed": "format_response",
    })
    g.add_edge("service_code_resolution", "provider_lookup")
    g.add_edge("provider_lookup",         "cost_estimation")
    g.add_edge("cost_estimation",         "format_response")
    g.add_edge("format_response",         END)

    return g.compile()


# ────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────
def run(query: str,
        location: str = "90210",
        network: str = "Aetna",
        insurance: Dict[str, Any] = None):

    graph = build_graph()

    initial: WorkflowState = {
        "user_query": query,
        "user_location": location,
        "insurance_network": network,
        "insurance_details": insurance or {
            "deductible_total": 1000.0, "deductible_met": 0.0,
            "copay": 0.0, "coinsurance": 20.0,
            "out_of_pocket_max": 5000.0, "out_of_pocket_met": 0.0,
        },
        "guardrail_passed": False,
        "service_code_response": {},
        "primary_code": "",
        "service_description": "",
        "provider_response": {},
        "selected_provider": {},
        "cost_estimate": {},
        "final_response": {},
        "error": "",
    }

    result = graph.invoke(initial)
    return result["final_response"]


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "I need a chiropractor visit for back pain"

    print(f"\n{BOLD}{BLUE}{'='*70}")
    print(f"  LANGGRAPH MEDICAL COST ESTIMATION APPLICATION")
    print(f"{'='*70}{RESET}")
    print(f"  Query    : {query}")
    print(f"  Location : 90210")
    print(f"  Network  : Aetna")
    print(f"  Insurance: $1000 deductible, 20% coinsurance")

    result = run(query)

    print(f"\n{BOLD}{YELLOW}{'='*70}")
    print(f"  FINAL OUTPUT TO USER")
    print(f"{'='*70}{RESET}")

    if result.get("success"):
        print(f"  {GREEN}Your estimated cost for {result.get('service_description','this service')[:60]}")
        print(f"  is {BOLD}{result['patient_pays']}{RESET}")
        print(f"  {result.get('explanation','')}")
        print(f"  Provider: {BOLD}{result['provider']}{RESET}")
        print(f"  Insurance pays: {result['insurance_pays']}")
        print(f"  Deductible remaining: {result['deductible_remaining']}")
    else:
        print(f"  {RED}Error: {result.get('error','Unknown error')}{RESET}")

    print(f"\n{DIM}Full result:{RESET}")
    print(json.dumps(result, indent=2))

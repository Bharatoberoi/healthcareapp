# api/router.py

from fastapi import APIRouter, Query, Body
from app.services.impl.retrieval_service_impl import RetrievalServiceImpl
from app.workflows.medical_cost_workflow import get_workflow
from app.schemas.request import QueryRequest, CompleteWorkflowRequest

router = APIRouter(prefix="/resolve-service-codes", tags=["Service Code Resolution"])

# Instantiate service once (singleton-style)
retrieval_service = RetrievalServiceImpl()
workflow = get_workflow()


@router.get("")
def resolve_service_codes(
    query: str = Query(..., description="Natural language query or service code (e.g. 99213)")
):
    """
    **STEP 2: SERVICE CODE RESOLUTION API**
    
    Resolves medical service codes from natural language queries.
    
    **Supported inputs:**
    - Natural language queries (e.g. 'chiropractor visit')
    - Direct service codes (e.g. '99213')

    **Processed through:**
    - Query Enhancement (RAG with OpenAI Embeddings + FAISS Vector Search)
    - Code Selection (LLM with semantic similarity scoring 70% + claim volume weighting 30%)

    **Behavior:**
    - Valid service code → primary + alternatives
    - Invalid service code → Out-of-Scope response
    - Non-medical query → Out-of-Scope response
    
    **Response includes:**
    - Primary service code
    - Service type and description
    - Alternative service codes
    - Confidence score
    """
    return retrieval_service.resolve_service_code(query=query)


@router.post("/complete-workflow")
def complete_workflow(request: CompleteWorkflowRequest = Body(...)):
    """
    **COMPLETE WORKFLOW: All 4 Steps Combined**
    
    Orchestrates the complete medical cost estimation workflow:
    
    **STEP 1: Query Guardrail**
    - Pattern Matching (harmful content detection)
    - OpenAI Moderation API
    - Semantic Similarity Check
    - Intent Classification
    - **Decision:** Valid Medical Query or Out-of-Scope/Harmful
    
    **STEP 2: Service Code Resolution**
    - Query Enhancement (RAG with embeddings + FAISS search)
    - Code Selection (LLM with semantic scoring 70% + claim volume 30%)
    - **Output:** Primary code + alternatives + confidence score
    
    **STEP 3: Provider Lookup**
    - Search in-network providers by service code
    - Filter by distance and rating
    - Check availability and network status
    - **Output:** Provider list with contracted rates and ratings
    
    **STEP 4: Cost Estimation**
    - Calculate patient responsibility
    - Applied to deductible or coinsurance
    - Insurance breakdown and explanation
    - **Output:** Cost estimate with insurance breakdown
    
    **Request parameters:**
    - `query` (required): User's natural language query (e.g., "I need a chiropractor visit for back pain")
    - `user_location` (optional): User's zipcode or coordinates
    - `insurance_network` (optional): Insurance network name (e.g., "Aetna", "UHC")
    - `insurance_details` (optional): Insurance plan details
      - deductible_total: Total deductible amount
      - deductible_met: Amount already met
      - copay: Copay amount per visit
      - coinsurance: Coinsurance percentage (e.g., 20 for 20%)
      - out_of_pocket_max: Maximum out-of-pocket
      - out_of_pocket_met: Amount already met
    
    **Response includes:**
    - Complete workflow status for all 4 steps
    - Service code information
    - Provider details
    - Cost breakdown (patient vs insurance responsibility)
    - User-friendly message with recommendations
    """
    return workflow.run(
        user_query=request.query,
        user_location=request.user_location,
        insurance_network=request.insurance_network,
        insurance_details=request.insurance_details
    )

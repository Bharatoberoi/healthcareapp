"""
LangGraph Workflow for Complete Medical Cost Estimation
Orchestrates all 4 steps: Query Guardrail → Service Code Resolution → Provider Lookup → Cost Estimation
Uses MCP (Model Context Protocol) servers for Steps 3 & 4
"""

from typing import Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from app.services.impl.retrieval_service_impl import RetrievalServiceImpl
from app.mcp.mcp_client import ProviderLookupMCPClient, CostEstimatorMCPClient
from app.core.logger import logger


class WorkflowState(TypedDict):
    """State object for the workflow"""
    user_query: str
    user_location: str
    insurance_network: str
    insurance_details: Dict[str, Any]
    
    # Step 1: Query Guardrail
    guardrail_passed: bool
    guardrail_response: Dict[str, Any]
    
    # Step 2: Service Code Resolution
    service_code_response: Dict[str, Any]
    primary_code: str
    service_description: str
    
    # Step 3: Provider Lookup
    provider_response: Dict[str, Any]
    selected_provider: Dict[str, Any]
    
    # Step 4: Cost Estimation
    cost_estimate: Dict[str, Any]
    
    # Final output
    final_response: Dict[str, Any]
    error: str


class MedicalCostWorkflow:
    """LangGraph workflow for medical cost estimation"""
    
    def __init__(self):
        self.retrieval_service = RetrievalServiceImpl()
        logger.info("[Workflow] Initializing MCP clients...")
        self.provider_lookup = ProviderLookupMCPClient()
        self.cost_estimator = CostEstimatorMCPClient()
        logger.info("[Workflow] MCP clients initialized")
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("query_guardrail", self._query_guardrail_node)
        workflow.add_node("service_code_resolution", self._service_code_resolution_node)
        workflow.add_node("provider_lookup", self._provider_lookup_node)
        workflow.add_node("cost_estimation", self._cost_estimation_node)
        workflow.add_node("format_response", self._format_response_node)
        
        # Set entry point
        workflow.set_entry_point("query_guardrail")
        
        # Add edges
        workflow.add_conditional_edges(
            "query_guardrail",
            self._check_guardrail,
            {
                "passed": "service_code_resolution",
                "failed": "format_response"  # Format error response even if guardrail fails
            }
        )
        
        workflow.add_edge("service_code_resolution", "provider_lookup")
        workflow.add_edge("provider_lookup", "cost_estimation")
        workflow.add_edge("cost_estimation", "format_response")
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def _query_guardrail_node(self, state: WorkflowState) -> WorkflowState:
        """Step 1: Query Guardrail"""
        logger.info("=" * 80)
        logger.info("STEP 1: QUERY GUARDRAIL")
        logger.info(f"Input Query: {state['user_query']}")
        logger.info("Validating query against guardrail layers...")
        
        try:
            # Quick validation: just check if the query could be medical-related
            # without expensive LLM calls - we'll cache proper result in service_code_response
            query_lower = state['user_query'].lower()
            medical_keywords = ['doctor', 'hospital', 'clinic', 'medical', 'health', 'visit', 'pain', 
                               'injury', 'surgery', 'therapy', 'treatment', 'exam', 'test', 
                               'prescription', 'medication', 'disease', 'condition', 'chiropractor',
                               'dentist', 'eye', 'emergency', 'urgent', 'care']
            
            has_medical_keyword = any(keyword in query_lower for keyword in medical_keywords)
            
            if has_medical_keyword or any(char.isdigit() for char in state['user_query']):
                state["guardrail_passed"] = True
                state["guardrail_response"] = {"status": "passed"}
                logger.info("✓ GUARDRAIL PASSED: Query appears to be medical-related")
            else:
                state["guardrail_passed"] = False
                state["error"] = "Query failed guardrail check - not medical related"
                logger.warning(f"✗ GUARDRAIL FAILED: Query is not medical related")
        except Exception as e:
            logger.error(f"✗ GUARDRAIL ERROR: {str(e)}")
            state["guardrail_passed"] = False
            state["error"] = f"Guardrail check error: {str(e)}"
        
        logger.info("=" * 80)
        return state
    
    def _service_code_resolution_node(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Service Code Resolution"""
        logger.info("=" * 80)
        logger.info("STEP 2: SERVICE CODE RESOLUTION")
        logger.info("A. Query Enhancement (RAG)")
        logger.info("   • Using OpenAI Embeddings")
        logger.info("   • Searching FAISS Vector Database")
        logger.info("   • Retrieving top-k similar service codes")
        
        try:
            result = self.retrieval_service.resolve_service_code(state["user_query"])
            
            # Check if out of scope
            if result.get("service_code") == "Out of Scope":
                state["error"] = result.get("assumptions", "Service code resolution failed - out of scope")
                logger.warning(f"✗ SERVICE CODE RESOLUTION FAILED: {state['error']}")
                return state
            
            if result.get("service_code") is None or not result.get("service_code"):
                state["error"] = "Service code resolution failed - no code returned"
                logger.warning("✗ SERVICE CODE RESOLUTION FAILED: No code returned")
                return state
            
            state["service_code_response"] = result
            state["primary_code"] = result.get("service_code", "")
            state["service_description"] = result.get("description", "")
            
            logger.info("B. Code Selection (LLM)")
            logger.info("   • Semantic similarity scoring (70%)")
            logger.info("   • Claim volume weighting (30%)")
            logger.info("   • LLM selects best match")
            logger.info("\n   OUTPUT:")
            logger.info(f"   Primary Code: {state['primary_code']}")
            logger.info(f"   Service Type: {result.get('service_code_type', '')}")
            logger.info(f"   Description: {state['service_description']}")
            logger.info(f"   Alternatives: {list(result.get('alternative_services', {}).keys())}")
            logger.info(f"   Confidence: {result.get('confidence', 'N/A')}")
            logger.info("✓ SERVICE CODE RESOLUTION PASSED")
        except Exception as e:
            logger.error(f"✗ SERVICE CODE RESOLUTION ERROR: {str(e)}")
            state["error"] = f"Service code resolution error: {str(e)}"
        
        logger.info("=" * 80)
        return state
    
    def _provider_lookup_node(self, state: WorkflowState) -> WorkflowState:
        """Step 3: Provider Lookup (via MCP)"""
        logger.info("=" * 80)
        logger.info("STEP 3: PROVIDER LOOKUP (MCP)")
        logger.info(f"Input: service_code={state['primary_code']}, user_location={state.get('user_location', 'N/A')}, insurance_network={state.get('insurance_network', 'N/A')}")
        logger.info("[MCP] Connecting to Provider Lookup MCP Server...")
        logger.info("\nSearching for in-network providers...")
        
        try:
            result = self.provider_lookup.lookup_providers(
                service_code=state["primary_code"],
                user_location=state.get("user_location"),
                insurance_network=state.get("insurance_network")
            )
            
            state["provider_response"] = result
            
            # Select the first provider (highest rated)
            providers = result.get("providers", [])
            if providers:
                state["selected_provider"] = providers[0]
                provider = state['selected_provider']
                logger.info("\n   OUTPUT:")
                logger.info(f"   Provider Name: {provider.get('name', '')}")
                logger.info(f"   NPI: {provider.get('npi', '')}")
                logger.info(f"   Distance: {provider.get('distance', '')}")
                logger.info(f"   Network Status: {provider.get('network_status', '')}")
                logger.info(f"   Rating: {provider.get('rating', '')}★")
                logger.info(f"   Contracted Rate: ${provider.get('contracted_rate', '')} ")
                logger.info("✓ PROVIDER LOOKUP PASSED")
            else:
                state["error"] = "No providers found for the service code"
                logger.warning("✗ PROVIDER LOOKUP FAILED: No providers found")
        except Exception as e:
            logger.error(f"✗ PROVIDER LOOKUP ERROR: {str(e)}")
            state["error"] = f"Provider lookup error: {str(e)}"
        
        logger.info("=" * 80)
        return state
    
    def _cost_estimation_node(self, state: WorkflowState) -> WorkflowState:
        """Step 4: Cost Estimation (via MCP)"""
        logger.info("=" * 80)
        logger.info("STEP 4: COST ESTIMATOR (MCP)")
        logger.info(f"Input: service_code={state['primary_code']}")
        logger.info(f"       provider_info (contracted_rate={state.get('selected_provider', {}).get('contracted_rate', 'N/A')}, network_status={state.get('selected_provider', {}).get('network_status', 'N/A')})")
        logger.info("       user_insurance (plan, deductible, copay, coinsurance)")
        logger.info("[MCP] Connecting to Cost Estimator MCP Server...")
        
        try:
            if state.get("error"):
                logger.info("=" * 80)
                return state
            
            logger.info("\nCalculation Logic:")
            provider = state.get("selected_provider", {})
            logger.info(f"  • Base rate: ${provider.get('contracted_rate', 0):.2f} (contracted)")
            
            insurance = state.get("insurance_details", {
                "deductible_total": 1000.0,
                "deductible_met": 0.0,
                "copay": 0.0,
                "coinsurance": 20.0,
                "out_of_pocket_max": 5000.0,
                "out_of_pocket_met": 0.0
            })
            
            deductible_remaining = insurance.get("deductible_total", 0) - insurance.get("deductible_met", 0)
            logger.info(f"  • Deductible met? → {insurance.get('deductible_met', 0)}/{insurance.get('deductible_total', 0)}")
            logger.info(f"  • Coinsurance: {insurance.get('coinsurance', 0)}% after deductible")
            logger.info(f"  • Copay: ${insurance.get('copay', 0):.2f}")
            
            cost_estimate = self.cost_estimator.estimate_cost(
                service_code=state["primary_code"],
                service_description=state["service_description"],
                provider_info=provider,
                user_insurance=insurance
            )
            
            state["cost_estimate"] = cost_estimate
            
            logger.info("\n   OUTPUT:")
            logger.info(f"   Service Code: {state['primary_code']}")
            logger.info(f"   Service Description: {state['service_description']}")
            logger.info(f"   Provider: {provider.get('name', 'N/A')}")
            logger.info(f"   Total Cost: {cost_estimate.get('total_cost', 'N/A')}")
            logger.info(f"   Patient Responsibility: {cost_estimate.get('patient_responsibility', 'N/A')}")
            logger.info(f"   Insurance Pays: {cost_estimate.get('insurance_pays', 'N/A')}")
            logger.info(f"   Deductible Remaining: {cost_estimate.get('deductible_remaining', 'N/A')}")
            logger.info(f"   Explanation: {cost_estimate.get('explanation', 'N/A')}")
            logger.info(f"   Confidence: {cost_estimate.get('confidence', 'N/A')}")
            logger.info("✓ COST ESTIMATION PASSED")
        except Exception as e:
            logger.error(f"✗ COST ESTIMATION ERROR: {str(e)}")
            state["error"] = f"Cost estimation error: {str(e)}"
        
        logger.info("=" * 80)
        return state
    
    def _format_response_node(self, state: WorkflowState) -> WorkflowState:
        """Format final response"""
        logger.info("Formatting final response")
        
        if "error" in state and state["error"]:
            state["final_response"] = {
                "success": False,
                "error": state["error"],
                "step_failed": self._identify_failed_step(state),
                "workflow_steps": {
                    "step_1_query_guardrail": "failed" if not state.get("guardrail_passed") else "passed",
                    "step_2_service_code_resolution": "not_reached",
                    "step_3_provider_lookup": "not_reached",
                    "step_4_cost_estimation": "not_reached"
                }
            }
        else:
            cost_estimate = state.get("cost_estimate", {})
            provider = state.get("selected_provider", {})
            service_response = state.get("service_code_response", {})
            
            state["final_response"] = {
                "success": True,
                "workflow_steps": {
                    "step_1_query_guardrail": "passed",
                    "step_2_service_code_resolution": "passed",
                    "step_3_provider_lookup": "passed",
                    "step_4_cost_estimation": "passed"
                },
                "user_query": state["user_query"],
                "service_code_info": {
                    "primary_code": state["primary_code"],
                    "service_type": service_response.get("service_code_type", ""),
                    "title": state["service_description"],
                    "description": service_response.get("description", ""),
                    "alternatives": list(service_response.get("alternative_services", {}).keys()) if service_response.get("alternative_services") else [],
                    "confidence": service_response.get("confidence", 0)
                },
                "provider_info": {
                    "name": provider.get("name", ""),
                    "npi": provider.get("npi", ""),
                    "distance": provider.get("distance", ""),
                    "rating": provider.get("rating", 0),
                    "network_status": provider.get("network_status", ""),
                    "specialty": provider.get("specialty", ""),
                    "address": provider.get("address", ""),
                    "contracted_rate": f"${provider.get('contracted_rate', 0):.2f}"
                },
                "cost_breakdown": {
                    "total_cost": cost_estimate.get("total_cost", ""),
                    "patient_responsibility": cost_estimate.get("patient_responsibility", ""),
                    "insurance_pays": cost_estimate.get("insurance_pays", ""),
                    "deductible_remaining": cost_estimate.get("deductible_remaining", ""),
                    "explanation": cost_estimate.get("explanation", ""),
                    "confidence": cost_estimate.get("confidence", "")
                },
                "user_message": self._generate_user_message(state)
            }
        
        return state
    
    def _check_guardrail(self, state: WorkflowState) -> str:
        """Check if guardrail passed"""
        return "passed" if state.get("guardrail_passed", False) else "failed"
    
    def _identify_failed_step(self, state: WorkflowState) -> str:
        """Identify which step failed"""
        if not state.get("guardrail_passed"):
            return "query_guardrail"
        if not state.get("service_code_response"):
            return "service_code_resolution"
        if not state.get("provider_response"):
            return "provider_lookup"
        if not state.get("cost_estimate"):
            return "cost_estimation"
        return "unknown"
    
    def _generate_user_message(self, state: WorkflowState) -> str:
        """Generate user-friendly message"""
        cost_estimate = state.get("cost_estimate", {})
        provider = state.get("selected_provider", {})
        
        message_lines = [
            "=" * 80,
            "FINAL OUTPUT TO USER",
            "=" * 80,
            f"Your estimated cost for {state.get('service_description', 'this service')} is {cost_estimate.get('patient_responsibility', 'N/A')}",
            f"{cost_estimate.get('explanation', '')}",
            f"Provider: {provider.get('name', 'N/A')} ({provider.get('distance', 'N/A')} away, {provider.get('rating', 0)}★)",
            "=" * 80
        ]
        
        return "\n".join(message_lines)
    
    def run(self, user_query: str, user_location: str = None, 
            insurance_network: str = None, insurance_details: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run the complete workflow
        
        Args:
            user_query: User's natural language query
            user_location: User's location (optional)
            insurance_network: Insurance network name (optional)
            insurance_details: Insurance details dictionary (optional)
            
        Returns:
            Final response dictionary
        """
        initial_state: WorkflowState = {
            "user_query": user_query,
            "user_location": user_location or "",
            "insurance_network": insurance_network or "",
            "insurance_details": insurance_details or {
                "deductible_total": 1000.0,
                "deductible_met": 0.0,
                "copay": 0.0,
                "coinsurance": 20.0,
                "out_of_pocket_max": 5000.0,
                "out_of_pocket_met": 0.0
            },
            "guardrail_passed": False,
            "guardrail_response": {},
            "service_code_response": {},
            "primary_code": "",
            "service_description": "",
            "provider_response": {},
            "selected_provider": {},
            "cost_estimate": {},
            "final_response": {},
            "error": ""
        }
        
        try:
            result = self.graph.invoke(initial_state)
            return result.get("final_response", {"success": False, "error": "Unknown error"})
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            return {
                "success": False,
                "error": f"Workflow execution error: {str(e)}"
            }
    
    def cleanup(self):
        """Clean up MCP client connections"""
        try:
            logger.info("[Workflow] Cleaning up MCP clients...")
            if self.provider_lookup:
                self.provider_lookup.close()
            if self.cost_estimator:
                self.cost_estimator.close()
            logger.info("[Workflow] MCP clients closed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Singleton instance
_workflow_instance = None

def get_workflow() -> MedicalCostWorkflow:
    """Get singleton instance of MedicalCostWorkflow"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = MedicalCostWorkflow()
    return _workflow_instance

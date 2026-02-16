#!/usr/bin/env python3
"""
MCP Server for Cost Estimator (Step 4)
Uses Model Context Protocol to provide cost estimation services
"""

import json
import sys
import logging
from typing import Dict, Any

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


class CostEstimatorMCPServer:
    """MCP Server for cost estimation operations"""
    
    def estimate_cost(
        self,
        service_code: str,
        service_description: str,
        provider_info: Dict[str, Any],
        user_insurance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Estimate the cost for a medical service"""
        
        logger.info(f"[MCP] Cost Estimator Server: Calculating cost for code {service_code}")
        
        # Extract values with defaults
        contracted_rate = provider_info.get("contracted_rate", 0.0)
        network_status = provider_info.get("network_status", "out-of-network")
        provider_name = provider_info.get("name", "Unknown Provider")
        
        # Insurance details
        deductible_total = user_insurance.get("deductible_total", 1000.0)
        deductible_met = user_insurance.get("deductible_met", 0.0)
        deductible_remaining = deductible_total - deductible_met
        
        copay = user_insurance.get("copay", 0.0)
        coinsurance = user_insurance.get("coinsurance", 0.0)
        out_of_pocket_max = user_insurance.get("out_of_pocket_max", 5000.0)
        oop_met = user_insurance.get("out_of_pocket_met", 0.0)
        
        # Calculate patient responsibility
        patient_responsibility = 0.0
        insurance_pays = 0.0
        explanation_parts = []
        
        # Check if out-of-network
        if network_status == "out-of-network":
            patient_responsibility = contracted_rate
            insurance_pays = 0.0
            explanation_parts.append("Out-of-network provider - full cost applies")
        else:
            # In-network logic
            if copay > 0:
                patient_responsibility = copay
                insurance_pays = contracted_rate - copay
                explanation_parts.append(f"Copay of ${copay:.2f} applies")
            else:
                # Check deductible
                if deductible_remaining > 0:
                    amount_to_deductible = min(contracted_rate, deductible_remaining)
                    patient_responsibility = amount_to_deductible
                    insurance_pays = contracted_rate - amount_to_deductible
                    
                    if amount_to_deductible == contracted_rate:
                        explanation_parts.append("Applied to deductible")
                    else:
                        explanation_parts.append(f"${amount_to_deductible:.2f} applied to deductible")
                    
                    deductible_remaining = deductible_remaining - amount_to_deductible
                    
                    if deductible_remaining <= 0 and coinsurance > 0:
                        remaining_amount = contracted_rate - amount_to_deductible
                        patient_portion = remaining_amount * (coinsurance / 100)
                        insurance_portion = remaining_amount - patient_portion
                        patient_responsibility += patient_portion
                        insurance_pays += insurance_portion
                        explanation_parts.append(f"Coinsurance ({coinsurance}%) applies to remaining amount")
                else:
                    if coinsurance > 0:
                        patient_portion = contracted_rate * (coinsurance / 100)
                        insurance_portion = contracted_rate - patient_portion
                        patient_responsibility = patient_portion
                        insurance_pays = insurance_portion
                        explanation_parts.append(f"Coinsurance ({coinsurance}%) applies")
                    else:
                        insurance_pays = contracted_rate
                        patient_responsibility = 0.0
                        explanation_parts.append("Insurance covers full cost")
        
        # Check out-of-pocket maximum
        if oop_met + patient_responsibility > out_of_pocket_max:
            excess = (oop_met + patient_responsibility) - out_of_pocket_max
            patient_responsibility -= excess
            insurance_pays += excess
            explanation_parts.append(f"Out-of-pocket maximum reached - excess covered by insurance")
        
        explanation = ". ".join(explanation_parts) if explanation_parts else "Cost calculation completed"
        
        logger.info(f"[MCP] Cost Estimator: Patient ${patient_responsibility:.2f}, Insurance ${insurance_pays:.2f}")
        
        return {
            "service_code": service_code,
            "service_description": service_description,
            "provider": provider_name,
            "total_cost": f"${contracted_rate:.2f}",
            "patient_responsibility": f"${patient_responsibility:.2f}",
            "insurance_pays": f"${insurance_pays:.2f}",
            "deductible_remaining": f"${max(0, deductible_remaining):.2f}",
            "explanation": explanation,
            "confidence": "High",
            "network_status": network_status
        }


def main():
    """Main entry point for MCP server"""
    server = CostEstimatorMCPServer()
    logger.info("[MCP] Cost Estimator Server started on stdio")
    
    # Read from stdin and process MCP requests
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            data = json.loads(line)
            method = data.get("method")
            params = data.get("params", {})
            request_id = data.get("id")
            
            response = None
            
            if method == "estimate_cost":
                response = server.estimate_cost(
                    service_code=params.get("service_code"),
                    service_description=params.get("service_description"),
                    provider_info=params.get("provider_info", {}),
                    user_insurance=params.get("user_insurance", {})
                )
            else:
                response = {"error": f"Unknown method: {method}"}
            
            result = {
                "id": request_id,
                "result": response
            }
            
            print(json.dumps(result))
            sys.stdout.flush()
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Error processing request: {e}")


if __name__ == "__main__":
    main()

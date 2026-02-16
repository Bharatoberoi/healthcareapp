"""
MCP Server for Cost Estimator API (Step 4)
Calculates cost estimates based on service code, provider info, and insurance details
"""

from typing import Dict, Any, Optional


class CostEstimatorServer:
    """MCP Server that handles cost estimation requests"""
    
    def estimate_cost(
        self,
        service_code: str,
        service_description: str,
        provider_info: Dict[str, Any],
        user_insurance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Estimate the cost for a medical service
        
        Args:
            service_code: The service code (e.g., "98940")
            service_description: Description of the service
            provider_info: Provider information including contracted_rate, network_status
            user_insurance: Insurance details including plan, deductible, copay, coinsurance
            
        Returns:
            Dictionary with cost breakdown
        """
        # Extract values with defaults
        contracted_rate = provider_info.get("contracted_rate", 0.0)
        network_status = provider_info.get("network_status", "out-of-network")
        provider_name = provider_info.get("name", "Unknown Provider")
        
        # Insurance details
        deductible_total = user_insurance.get("deductible_total", 1000.0)
        deductible_met = user_insurance.get("deductible_met", 0.0)
        deductible_remaining = deductible_total - deductible_met
        
        copay = user_insurance.get("copay", 0.0)
        coinsurance = user_insurance.get("coinsurance", 0.0)  # Percentage (e.g., 20 for 20%)
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
            # Step 1: Check if copay applies
            if copay > 0:
                patient_responsibility = copay
                insurance_pays = contracted_rate - copay
                explanation_parts.append(f"Copay of ${copay:.2f} applies")
            else:
                # Step 2: Check deductible
                if deductible_remaining > 0:
                    # Apply to deductible
                    amount_to_deductible = min(contracted_rate, deductible_remaining)
                    patient_responsibility = amount_to_deductible
                    insurance_pays = contracted_rate - amount_to_deductible
                    
                    if amount_to_deductible == contracted_rate:
                        explanation_parts.append("Applied to deductible")
                    else:
                        explanation_parts.append(f"${amount_to_deductible:.2f} applied to deductible")
                    
                    # Update deductible remaining
                    deductible_remaining = deductible_remaining - amount_to_deductible
                    
                    # If deductible is met, apply coinsurance to remaining
                    if deductible_remaining <= 0 and coinsurance > 0:
                        remaining_amount = contracted_rate - amount_to_deductible
                        patient_portion = remaining_amount * (coinsurance / 100)
                        insurance_portion = remaining_amount - patient_portion
                        patient_responsibility += patient_portion
                        insurance_pays += insurance_portion
                        explanation_parts.append(f"Coinsurance ({coinsurance}%) applies to remaining amount")
                else:
                    # Deductible met, apply coinsurance
                    if coinsurance > 0:
                        patient_portion = contracted_rate * (coinsurance / 100)
                        insurance_portion = contracted_rate - patient_portion
                        patient_responsibility = patient_portion
                        insurance_pays = insurance_portion
                        explanation_parts.append(f"Coinsurance ({coinsurance}%) applies")
                    else:
                        # No coinsurance, insurance pays all
                        insurance_pays = contracted_rate
                        patient_responsibility = 0.0
                        explanation_parts.append("Insurance covers full cost")
        
        # Check out-of-pocket maximum
        if oop_met + patient_responsibility > out_of_pocket_max:
            excess = (oop_met + patient_responsibility) - out_of_pocket_max
            patient_responsibility -= excess
            insurance_pays += excess
            explanation_parts.append(f"Out-of-pocket maximum reached - excess covered by insurance")
        
        # Format explanation
        explanation = ". ".join(explanation_parts) if explanation_parts else "Cost calculation completed"
        
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


# Singleton instance
_cost_estimator_server = None

def get_cost_estimator_server() -> CostEstimatorServer:
    """Get singleton instance of CostEstimatorServer"""
    global _cost_estimator_server
    if _cost_estimator_server is None:
        _cost_estimator_server = CostEstimatorServer()
    return _cost_estimator_server

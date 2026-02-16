"""
MCP Server for Provider Lookup API (Step 3)
Simulates provider search based on service code, location, and insurance network
"""

from typing import Dict, Any, List
import random


class ProviderLookupServer:
    """MCP Server that handles provider lookup requests"""
    
    def __init__(self):
        # Mock provider database
        self.providers_db = {
            "98940": [
                {
                    "name": "Dr. John Smith DC",
                    "npi": "1234567890",
                    "distance": "2.3 miles",
                    "network_status": "in-network",
                    "rating": 4.8,
                    "contracted_rate": 45.00,
                    "specialty": "Chiropractic",
                    "address": "123 Main St, City, State 12345"
                },
                {
                    "name": "Dr. Sarah Johnson DC",
                    "npi": "2345678901",
                    "distance": "5.1 miles",
                    "network_status": "in-network",
                    "rating": 4.6,
                    "contracted_rate": 50.00,
                    "specialty": "Chiropractic",
                    "address": "456 Oak Ave, City, State 12345"
                }
            ],
            "99213": [
                {
                    "name": "Dr. Michael Brown MD",
                    "npi": "3456789012",
                    "distance": "1.2 miles",
                    "network_status": "in-network",
                    "rating": 4.9,
                    "contracted_rate": 120.00,
                    "specialty": "Family Medicine",
                    "address": "789 Pine St, City, State 12345"
                }
            ],
            "99214": [
                {
                    "name": "Dr. Emily Chen MD",
                    "npi": "4567890123",
                    "distance": "2.0 miles",
                    "network_status": "in-network",
                    "rating": 4.7,
                    "contracted_rate": 150.00,
                    "specialty": "Internal Medicine",
                    "address": "321 Oak Blvd, City, State 12345"
                }
            ]
        }
    
    def lookup_providers(
        self,
        service_code: str,
        user_location: str = None,
        insurance_network: str = None,
        max_distance: float = 10.0
    ) -> Dict[str, Any]:
        """
        Lookup providers for a given service code
        
        Args:
            service_code: The service code (e.g., "98940")
            user_location: User's location (zipcode or lat-long)
            insurance_network: Insurance network name
            max_distance: Maximum distance in miles
            
        Returns:
            Dictionary with provider information
        """
        # Get providers for this service code (try exact match, then strip leading zeros)
        providers = self.providers_db.get(service_code, [])
        if not providers and service_code:
            # Try without leading zeros (e.g. "098940" -> "98940")
            code_clean = service_code.lstrip("0") or service_code
            providers = self.providers_db.get(code_clean, [])
        # Fallback: use default provider so workflow always returns a result for demo
        if not providers:
            providers = [
                {
                    "name": "Dr. Jane Doe",
                    "npi": "0000000001",
                    "distance": "3.0 miles",
                    "network_status": "in-network",
                    "rating": 4.5,
                    "contracted_rate": 75.00,
                    "specialty": "General",
                    "address": "100 Demo St, City, State 12345"
                }
            ]
        
        # Filter by network status if provided (keep all if filter would empty list)
        if insurance_network:
            in_network = [p for p in providers if p["network_status"] == "in-network"]
            if in_network:
                providers = in_network
        
        # Filter by distance (mock implementation) - don't over-filter
        if user_location and providers:
            try:
                providers = [
                    p for p in providers 
                    if float(p["distance"].split()[0]) <= max_distance
                ]
            except (ValueError, IndexError):
                pass
            if not providers:
                providers = self.providers_db.get("98940", []) or list(self.providers_db.values())[0]
        
        # Sort by rating (highest first)
        providers = sorted(providers, key=lambda x: x["rating"], reverse=True)
        
        # Limit to top 5
        providers = providers[:5]
        
        return {
            "service_code": service_code,
            "providers": providers,
            "total_found": len(providers)
        }
    
    def get_provider_details(self, npi: str) -> Dict[str, Any]:
        """Get detailed information about a specific provider"""
        for code, providers in self.providers_db.items():
            for provider in providers:
                if provider["npi"] == npi:
                    return provider
        return None


# Singleton instance
_provider_lookup_server = None

def get_provider_lookup_server() -> ProviderLookupServer:
    """Get singleton instance of ProviderLookupServer"""
    global _provider_lookup_server
    if _provider_lookup_server is None:
        _provider_lookup_server = ProviderLookupServer()
    return _provider_lookup_server

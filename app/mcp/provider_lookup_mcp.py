#!/usr/bin/env python3
"""
MCP Server for Provider Lookup (Step 3)
Uses Model Context Protocol to provide provider lookup services
"""

import json
import sys
import logging
from typing import Dict, Any, List

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


class ProviderLookupMCPServer:
    """MCP Server for provider lookup operations"""
    
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
            "98941": [
                {
                    "name": "Dr. John Smith DC",
                    "npi": "1234567890",
                    "distance": "2.3 miles",
                    "network_status": "in-network",
                    "rating": 4.8,
                    "contracted_rate": 50.00,
                    "specialty": "Chiropractic",
                    "address": "123 Main St, City, State 12345"
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
        """Lookup providers for a given service code"""
        
        logger.info(f"[MCP] Provider Lookup Server: Looking up providers for code {service_code}")
        
        # Get providers for this service code
        providers = self.providers_db.get(service_code, [])
        if not providers and service_code:
            code_clean = service_code.lstrip("0") or service_code
            providers = self.providers_db.get(code_clean, [])
        
        # Fallback: use default provider
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
        
        # Filter by network status
        if insurance_network:
            in_network = [p for p in providers if p["network_status"] == "in-network"]
            if in_network:
                providers = in_network
        
        # Filter by distance
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
        
        # Sort by rating
        providers = sorted(providers, key=lambda x: x["rating"], reverse=True)
        providers = providers[:5]
        
        logger.info(f"[MCP] Provider Lookup: Found {len(providers)} providers")
        
        return {
            "service_code": service_code,
            "providers": providers,
            "total_found": len(providers)
        }


def main():
    """Main entry point for MCP server"""
    server = ProviderLookupMCPServer()
    logger.info("[MCP] Provider Lookup Server started on stdio")
    
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
            
            if method == "lookup_providers":
                response = server.lookup_providers(
                    service_code=params.get("service_code"),
                    user_location=params.get("user_location"),
                    insurance_network=params.get("insurance_network"),
                    max_distance=params.get("max_distance", 10.0)
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

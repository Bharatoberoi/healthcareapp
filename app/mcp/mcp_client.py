#!/usr/bin/env python3
"""
MCP Client for communicating with MCP servers
"""

import json
import subprocess
import sys
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with MCP servers via stdin/stdout"""
    
    def __init__(self, server_script: str):
        """
        Initialize MCP client
        
        Args:
            server_script: Path to the MCP server script to run
        """
        self.server_script = server_script
        self.process: Optional[subprocess.Popen] = None
        self.request_counter = 0
        self._start_server()
    
    def _start_server(self):
        """Start the MCP server process"""
        try:
            logger.info(f"[MCP Client] Starting server: {self.server_script}")
            self.process = subprocess.Popen(
                [sys.executable, self.server_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            logger.info(f"[MCP Client] Server started with PID {self.process.pid}")
        except Exception as e:
            logger.error(f"[MCP Client] Failed to start server: {e}")
            raise
    
    def call(self, method: str, **kwargs) -> Dict[str, Any]:
        """
        Call a method on the MCP server
        
        Args:
            method: The method name to call
            **kwargs: Parameters to pass to the method
            
        Returns:
            The result from the server
        """
        if not self.process or self.process.poll() is not None:
            logger.warning("[MCP Client] Server process not running, restarting...")
            self._start_server()
        
        self.request_counter += 1
        request_id = self.request_counter
        
        request = {
            "id": request_id,
            "method": method,
            "params": kwargs
        }
        
        try:
            logger.info(f"[MCP Client] Calling {method} with params: {list(kwargs.keys())}")
            
            # Send request to server
            request_json = json.dumps(request)
            self.process.stdin.write(request_json + "\n")
            self.process.stdin.flush()
            
            # Read response from server
            response_line = self.process.stdout.readline()
            if not response_line:
                raise Exception("No response from server")
            
            response = json.loads(response_line)
            
            if "error" in response:
                logger.error(f"[MCP Client] Server error: {response['error']}")
                raise Exception(response["error"])
            
            logger.info(f"[MCP Client] Got response for {method}")
            return response.get("result", {})
            
        except Exception as e:
            logger.error(f"[MCP Client] Error calling {method}: {e}")
            raise
    
    def close(self):
        """Close the server process"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info("[MCP Client] Server closed")
            except:
                self.process.kill()
                logger.warning("[MCP Client] Server killed")


class ProviderLookupMCPClient:
    """MCP Client for Provider Lookup Server"""
    
    def __init__(self, server_script: str = None):
        if server_script is None:
            # Use default path
            import os
            base_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(base_dir, "provider_lookup_mcp.py")
        
        self.client = MCPClient(server_script)
    
    def lookup_providers(
        self,
        service_code: str,
        user_location: str = None,
        insurance_network: str = None,
        max_distance: float = 10.0
    ) -> Dict[str, Any]:
        """Lookup providers"""
        return self.client.call(
            "lookup_providers",
            service_code=service_code,
            user_location=user_location,
            insurance_network=insurance_network,
            max_distance=max_distance
        )
    
    def close(self):
        """Close the client"""
        self.client.close()


class CostEstimatorMCPClient:
    """MCP Client for Cost Estimator Server"""
    
    def __init__(self, server_script: str = None):
        if server_script is None:
            # Use default path
            import os
            base_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(base_dir, "cost_estimator_mcp.py")
        
        self.client = MCPClient(server_script)
    
    def estimate_cost(
        self,
        service_code: str,
        service_description: str,
        provider_info: Dict[str, Any],
        user_insurance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Estimate cost"""
        return self.client.call(
            "estimate_cost",
            service_code=service_code,
            service_description=service_description,
            provider_info=provider_info,
            user_insurance=user_insurance
        )
    
    def close(self):
        """Close the client"""
        self.client.close()

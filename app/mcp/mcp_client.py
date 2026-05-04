#!/usr/bin/env python3
"""
MCP Client for communicating with MCP servers
"""

import json
import subprocess
import sys
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MCP_READ_TIMEOUT = 60.0  # seconds — max time to wait for a server response


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
            logger.info("[MCP Client] Starting server: %s", self.server_script)
            self.process = subprocess.Popen(
                [sys.executable, self.server_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            logger.info("[MCP Client] Server started with PID %s", self.process.pid)
        except Exception as e:
            logger.error("[MCP Client] Failed to start server: %s", e)
            raise

    def _read_line_with_timeout(self, timeout: float) -> str:
        """Read a line from stdout with a timeout to prevent blocking forever."""
        result = [None]
        exc_holder = [None]

        def _reader():
            try:
                result[0] = self.process.stdout.readline()
            except Exception as e:
                exc_holder[0] = e

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # Timed out — kill the stuck server and raise
            logger.error("[MCP Client] Read timed out after %.1fs, killing server", timeout)
            self.process.kill()
            raise TimeoutError(
                f"MCP server did not respond within {timeout}s"
            )

        if exc_holder[0]:
            raise exc_holder[0]

        return result[0]

    def call(self, method: str, _retry: bool = True, **kwargs) -> Dict[str, Any]:
        """
        Call a method on the MCP server

        Args:
            method: The method name to call
            _retry: Whether to retry on server restart (internal)
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
            "params": kwargs,
        }

        try:
            logger.info("[MCP Client] Calling %s with params: %s", method, list(kwargs.keys()))

            # Send request to server
            request_json = json.dumps(request)
            self.process.stdin.write(request_json + "\n")
            self.process.stdin.flush()

            # Read response with timeout
            response_line = self._read_line_with_timeout(MCP_READ_TIMEOUT)
            if not response_line:
                raise Exception("No response from server (empty read)")

            response = json.loads(response_line)

            if "error" in response:
                logger.error("[MCP Client] Server error: %s", response["error"])
                raise Exception(response["error"])

            logger.info("[MCP Client] Got response for %s", method)
            return response.get("result", {})

        except (TimeoutError, BrokenPipeError, OSError) as e:
            # Server died or timed out — restart and retry once
            logger.error("[MCP Client] Error calling %s: %s", method, e)
            if _retry:
                logger.info("[MCP Client] Restarting server and retrying...")
                self._start_server()
                return self.call(method, _retry=False, **kwargs)
            raise
        except Exception as e:
            logger.error("[MCP Client] Error calling %s: %s", method, e)
            raise

    def close(self):
        """Close the server process"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info("[MCP Client] Server closed")
            except Exception:
                self.process.kill()
                logger.warning("[MCP Client] Server killed")


class ProviderLookupMCPClient:
    """MCP Client for Provider Lookup Server"""

    def __init__(self, server_script: str = None):
        if server_script is None:
            import os
            base_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(base_dir, "provider_lookup_mcp.py")

        self.client = MCPClient(server_script)

    def lookup_providers(
        self,
        service_code: str,
        user_location: str = None,
        insurance_network: str = None,
        max_distance: float = 10.0,
    ) -> Dict[str, Any]:
        """Lookup providers"""
        return self.client.call(
            "lookup_providers",
            service_code=service_code,
            user_location=user_location,
            insurance_network=insurance_network,
            max_distance=max_distance,
        )

    def close(self):
        """Close the client"""
        self.client.close()


class CostEstimatorMCPClient:
    """MCP Client for Cost Estimator Server"""

    def __init__(self, server_script: str = None):
        if server_script is None:
            import os
            base_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(base_dir, "cost_estimator_mcp.py")

        self.client = MCPClient(server_script)

    def estimate_cost(
        self,
        service_code: str,
        service_description: str,
        provider_info: Dict[str, Any],
        user_insurance: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Estimate cost"""
        return self.client.call(
            "estimate_cost",
            service_code=service_code,
            service_description=service_description,
            provider_info=provider_info,
            user_insurance=user_insurance,
        )

    def close(self):
        """Close the client"""
        self.client.close()

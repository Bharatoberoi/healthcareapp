#!/usr/bin/env python3
"""
Start Provider Lookup MCP Server
Run this before running the main API
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mcp.provider_lookup_mcp import main

if __name__ == "__main__":
    print("Starting Provider Lookup MCP Server...")
    main()

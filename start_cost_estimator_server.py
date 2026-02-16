#!/usr/bin/env python3
"""
Start Cost Estimator MCP Server
Run this before running the main API
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mcp.cost_estimator_mcp import main

if __name__ == "__main__":
    print("Starting Cost Estimator MCP Server...")
    main()

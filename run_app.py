"""
Script to run the Medical Cost Estimation API
"""

import uvicorn
import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("Starting Medical Cost Estimation API...")
    print("API will be available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("\nEndpoints:")
    print("  GET  /resolve-service-codes?query=<query> - Service code resolution only")
    print("  POST /resolve-service-codes/complete-workflow - Complete workflow (all 4 steps)")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

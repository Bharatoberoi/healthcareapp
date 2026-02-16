# Complete Medical Cost Estimation Workflow Implementation

## Overview

This application now implements the complete 4-step workflow as described in `workflow_graph.txt`:

1. **Query Guardrail** - Validates user queries for safety and medical relevance
2. **Service Code Resolution** - Resolves natural language queries to medical service codes (existing implementation)
3. **Provider Lookup** - Finds in-network providers using MCP server
4. **Cost Estimation** - Calculates patient costs using MCP server

## Architecture

### Components

1. **MCP Servers** (`app/mcp/`):
   - `provider_lookup_server.py` - Provider lookup service (Step 3)
   - `cost_estimator_server.py` - Cost calculation service (Step 4)

2. **LangGraph Workflow** (`app/workflows/`):
   - `medical_cost_workflow.py` - Orchestrates all 4 steps using LangGraph

3. **API Endpoints** (`app/api/router.py`):
   - `GET /resolve-service-codes` - Original service code resolution only
   - `POST /resolve-service-codes/complete-workflow` - Complete workflow endpoint

## Usage

### Running the Application

```bash
python run_app.py
```

The server will start on `http://localhost:8000`

### API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

### Complete Workflow Endpoint

**Endpoint:** `POST /resolve-service-codes/complete-workflow`

**Request Body:**
```json
{
  "query": "I need a chiropractor visit for back pain",
  "user_location": "12345",
  "insurance_network": "Aetna",
  "insurance_details": {
    "deductible_total": 1000.0,
    "deductible_met": 0.0,
    "copay": 0.0,
    "coinsurance": 20.0,
    "out_of_pocket_max": 5000.0,
    "out_of_pocket_met": 0.0
  }
}
```

**Response:**
```json
{
  "success": true,
  "user_query": "I need a chiropractor visit for back pain",
  "service_code": "98940",
  "service_description": "Chiropractic Manipulative Treatment",
  "provider": {
    "name": "Dr. John Smith DC",
    "distance": "2.3 miles",
    "rating": 4.8,
    "network_status": "in-network"
  },
  "cost_breakdown": {
    "total_cost": "$45.00",
    "patient_responsibility": "$45.00",
    "insurance_pays": "$0.00",
    "deductible_remaining": "$955.00",
    "explanation": "Applied to deductible"
  },
  "message": "Your estimated cost for Chiropractic Manipulative Treatment is $45.00. Applied to deductible. Provider: Dr. John Smith DC (2.3 miles away, 4.8★)"
}
```

### Testing

Run the test script:
```bash
python test_complete_workflow.py
```

Or use the simple test:
```bash
python test_workflow_simple.py
```

## Workflow Flow

```
User Query
    ↓
[Step 1: Query Guardrail] → Validates query safety
    ↓ (if passed)
[Step 2: Service Code Resolution] → Resolves to service code (e.g., "98940")
    ↓
[Step 3: Provider Lookup (MCP)] → Finds providers for service code
    ↓
[Step 4: Cost Estimation (MCP)] → Calculates patient cost
    ↓
[Format Response] → Returns complete cost estimate
```

## Dependencies

New dependencies added:
- `langgraph>=1.0.8` - Workflow orchestration
- `langchain>=0.3.0` - LangChain integration
- `langchain-openai>=0.2.0` - OpenAI integration
- `langgraph-checkpoint>=4.0.0` - State checkpointing
- `typing-extensions>=4.7.0` - Type hints support

## Notes

- The workflow may take 10-30 seconds to complete due to multiple LLM API calls
- Provider lookup and cost estimation use mock data (MCP servers can be replaced with real APIs)
- All emoji characters have been removed to prevent Windows encoding issues
- The original service code resolution endpoint remains available for backward compatibility

## Next Steps

To integrate with real provider and cost estimation APIs:
1. Replace mock data in `provider_lookup_server.py` with actual API calls
2. Replace mock calculations in `cost_estimator_server.py` with real insurance API integration
3. Add authentication/authorization if needed for external APIs

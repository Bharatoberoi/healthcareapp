# Medical Cost Estimation API with MCP

## Architecture

This application uses **Model Context Protocol (MCP)** servers for Steps 3 & 4:

### Workflow Steps:

1. **Query Guardrail** ✓ (Local)
   - Validates medical intent

2. **Service Code Resolution** ✓ (Local)
   - RAG with OpenAI Embeddings + FAISS
   - LLM-based code selection

3. **Provider Lookup** 📡 (MCP Server)
   - Connects to `provider_lookup_mcp.py` server
   - Returns in-network providers

4. **Cost Estimation** 📡 (MCP Server)
   - Connects to `cost_estimator_mcp.py` server
   - Calculates patient responsibility

---

## Quick Start

### Terminal 1: Start Provider Lookup MCP Server

```bash
cd "c:\Users\HP\OneDrive\Desktop\Bhargav\code_3 - Copy"
.\.venv\Scripts\python.exe start_provider_lookup_server.py
```

Output:
```
[MCP] Provider Lookup Server started on stdio
```

### Terminal 2: Start Cost Estimator MCP Server

```bash
cd "c:\Users\HP\OneDrive\Desktop\Bhargav\code_3 - Copy"
.\.venv\Scripts\python.exe start_cost_estimator_server.py
```

Output:
```
[MCP] Cost Estimator Server started on stdio
```

### Terminal 3: Start Main API

```bash
cd "c:\Users\HP\OneDrive\Desktop\Bhargav\code_3 - Copy"
.\.venv\Scripts\python.exe run_app.py
```

Output:
```
Starting Medical Cost Estimation API...
API will be available at: http://localhost:8000
API Documentation: http://localhost:8000/docs
...
Application startup complete.
Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## Test the Complete Workflow

```bash
cd "c:\Users\HP\OneDrive\Desktop\Bhargav\code_3 - Copy"
.\.venv\Scripts\python.exe run_workflow.py
```

---

## API Endpoints

### Test Service Code Resolution (Direct)

```bash
curl -X GET "http://localhost:8000/resolve-service-codes?query=chiropractor"
```

### Test Complete Workflow (with MCP)

```bash
curl -X POST "http://localhost:8000/resolve-service-codes/complete-workflow" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

---

## MCP Communication Flow

```
User Request
    ↓
FastAPI Main App (http://localhost:8000)
    ↓
Step 1: Query Guardrail (Local)
    ↓
Step 2: Service Code Resolution (Local)
    ↓
Step 3: Provider Lookup
    ├→ MCP Client spawns process
    ├→ Calls provider_lookup_mcp.py
    └→ Communicates via stdin/stdout (JSON)
    ↓
Step 4: Cost Estimator  
    ├→ MCP Client spawns process
    ├→ Calls cost_estimator_mcp.py
    └→ Communicates via stdin/stdout (JSON)
    ↓
Response to User
```

---

## File Structure

### MCP Servers
- `app/mcp/provider_lookup_mcp.py` - Provider Lookup MCP Server (executable)
- `app/mcp/cost_estimator_mcp.py` - Cost Estimator MCP Server (executable)
- `app/mcp/mcp_client.py` - MCP Client library

### Startup Scripts
- `start_provider_lookup_server.py` - Start Provider Lookup server
- `start_cost_estimator_server.py` - Start Cost Estimator server
- `run_app.py` - Start main API

### Updated Files
- `app/workflows/medical_cost_workflow.py` - Now uses MCP clients
- `app/main.py` - Shows MCP architecture in logs

---

## Monitoring MCP Communication

The servers log all requests and responses to stderr:

```
[MCP] Provider Lookup Server started on stdio
[MCP] Provider Lookup Server: Looking up providers for code 98941
[MCP] Provider Lookup: Found 1 providers
```

The clients log all calls to the workflow logger:

```
[MCP Client] Starting server: .../provider_lookup_mcp.py
[MCP Client] Calling lookup_providers with params: ['service_code', 'user_location', ...]
[MCP Client] Got response for lookup_providers
```

---

## Benefits of MCP Architecture

1. **Modularity** - Each service is independent
2. **Scalability** - MCP servers can run on different machines
3. **Isolation** - Failures in one server don't crash the API
4. **Standardization** - Uses MCP protocol (industry standard)
5. **Testability** - Test servers independently

---

## Troubleshooting

### "No response from server"
- Make sure all 3 terminals are running
- Check server startup messages
- Verify no port conflicts

### "Connection refused"
- Make sure MCP servers started first
- Check file paths are correct
- Allow a few seconds for servers to initialize

### Server crashes
- Check stderr logs for error messages
- Verify Python environment has all packages
- Restart all servers

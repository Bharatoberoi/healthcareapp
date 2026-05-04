Local Next.js frontend for LangGraph app

Quick start:

1. Install dependencies:
   cd frontend
   npm install

2. Run in dev mode:
   npm run dev

3. Open http://localhost:3000

The frontend calls the Python CLI `langgraph_cli.py` via the Next API route `/api/run-workflow`.
Ensure you can run `python langgraph_cli.py` from the repo root.


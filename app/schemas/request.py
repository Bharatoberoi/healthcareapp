from pydantic import BaseModel
from typing import Optional, Dict, Any

class QueryRequest(BaseModel):
    query: str

class CompleteWorkflowRequest(BaseModel):
    query: str
    user_location: Optional[str] = None
    insurance_network: Optional[str] = None
    insurance_details: Optional[Dict[str, Any]] = None

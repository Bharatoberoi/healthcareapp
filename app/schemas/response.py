from typing import Dict
from pydantic import BaseModel

class AlternativeService(BaseModel):
    description: str
    weighted_score: float
    claim_volume_rank: int

class ServiceCodeResponse(BaseModel):
    service_code: str
    service_code_type: str
    description: str
    alternative_services: Dict[str, AlternativeService]
    assumptions: str

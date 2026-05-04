from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────
class StepStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_REACHED = "not_reached"


class StreamEventType(str, Enum):
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_ERROR = "workflow_error"
    CLARIFICATION_NEEDED = "clarification_needed"


# ── Sub-models ────────────────────────────────────────────────
class AlternativeService(BaseModel):
    code: str
    description: str
    weighted_score: Optional[float] = None


class ServiceCodeInfo(BaseModel):
    primary_code: str
    service_type: str = ""
    description: str = ""
    alternatives: List[AlternativeService] = []
    confidence: float = 0.0
    assumptions: str = ""


class ProviderInfo(BaseModel):
    name: str = ""
    npi: str = ""
    distance: str = ""
    rating: float = 0.0
    network_status: str = ""
    specialty: str = ""
    address: str = ""
    contracted_rate: str = ""


class CostBreakdown(BaseModel):
    total_cost: str = ""
    patient_responsibility: str = ""
    insurance_pays: str = ""
    deductible_remaining: str = ""
    explanation: str = ""
    confidence: str = ""


class WorkflowSteps(BaseModel):
    step_1_query_guardrail: StepStatus = StepStatus.NOT_REACHED
    step_2_service_code_resolution: StepStatus = StepStatus.NOT_REACHED
    step_3_provider_lookup: StepStatus = StepStatus.NOT_REACHED
    step_4_cost_estimation: StepStatus = StepStatus.NOT_REACHED


class ClarificationCandidate(BaseModel):
    code: str
    description: str
    score: float


# ── Top-level responses ──────────────────────────────────────
class WorkflowResponse(BaseModel):
    success: bool
    request_id: str = ""
    workflow_steps: WorkflowSteps = WorkflowSteps()
    user_query: str = ""
    service_code_info: Optional[ServiceCodeInfo] = None
    provider_info: Optional[ProviderInfo] = None
    cost_breakdown: Optional[CostBreakdown] = None
    user_message: str = ""
    error: Optional[str] = None
    needs_clarification: bool = False
    clarification_candidates: List[ClarificationCandidate] = []


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    error_code: str = "INTERNAL_ERROR"
    request_id: str = ""
    detail: Optional[str] = None


class StreamEvent(BaseModel):
    event: StreamEventType
    data: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str = ""
    version: str = "2.0.0"

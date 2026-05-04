from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any


class InsuranceDetails(BaseModel):
    """Validated insurance plan details."""

    deductible_total: float = Field(default=1000.0, ge=0, alias="deductible")
    deductible_met: float = Field(default=0.0, ge=0)
    copay: float = Field(default=0.0, ge=0)
    coinsurance: float = Field(default=20.0, ge=0, le=100)
    out_of_pocket_max: float = Field(default=5000.0, ge=0)
    out_of_pocket_met: float = Field(default=0.0, ge=0)

    class Config:
        populate_by_name = True

    @field_validator("deductible_met")
    @classmethod
    def _deductible_met_lte_total(cls, v: float, info) -> float:
        total = info.data.get("deductible_total", 1000.0)
        if v > total:
            raise ValueError("deductible_met cannot exceed deductible_total")
        return v

    @field_validator("out_of_pocket_met")
    @classmethod
    def _oop_met_lte_max(cls, v: float, info) -> float:
        oop_max = info.data.get("out_of_pocket_max", 5000.0)
        if v > oop_max:
            raise ValueError("out_of_pocket_met cannot exceed out_of_pocket_max")
        return v


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


class CompleteWorkflowRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    user_location: Optional[str] = None
    insurance_network: Optional[str] = None
    insurance_details: Optional[InsuranceDetails] = None

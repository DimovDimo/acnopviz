from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    status: Literal["new", "accepted", "dismissed"]
    note: str = Field(default="", max_length=1000)


class ScenarioRequest(BaseModel):
    financing_rate: float = Field(default=0.08, ge=0, le=0.5)
    horizon: int = Field(default=6, ge=1, le=12)
    recovery_uplift: float = Field(default=0.0, ge=0, le=0.5)
    expense_reduction: float = Field(default=0.0, ge=0, le=0.3)

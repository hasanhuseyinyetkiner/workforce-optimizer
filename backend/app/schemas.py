"""Request bodies. Response payloads are plain dicts documented by the handlers."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class EmployeeIn(BaseModel):
    display_alias: str = Field(min_length=1, max_length=120)
    weekly_hour_cap: int = Field(ge=1, le=80)
    cost_per_hour: int = Field(ge=0, le=10000)
    night_preference: Literal["avoid", "neutral", "prefer"] = "neutral"
    weekend_preference: Literal["avoid", "neutral", "prefer"] = "neutral"
    skill_names: list[str] = Field(default_factory=list)


class EmployeePatch(BaseModel):
    display_alias: str | None = Field(default=None, min_length=1, max_length=120)
    weekly_hour_cap: int | None = Field(default=None, ge=1, le=80)
    cost_per_hour: int | None = Field(default=None, ge=0, le=10000)
    night_preference: Literal["avoid", "neutral", "prefer"] | None = None
    weekend_preference: Literal["avoid", "neutral", "prefer"] | None = None
    skill_names: list[str] | None = None


class TimeOffIn(BaseModel):
    start_local: str
    end_local: str
    reason: str = Field(default="PTO", max_length=200)


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    start_local: str
    end_local: str


class SkillRequirementIn(BaseModel):
    skill_names: list[str] = Field(min_length=1)
    min_count: int = Field(ge=1, le=50)


class ShiftIn(BaseModel):
    local_date: date
    start_local: str
    end_local: str
    required_count: int = Field(ge=0, le=50)
    label: str = Field(min_length=1, max_length=80)
    template_id: int | None = None
    skill_requirements: list[SkillRequirementIn] = Field(default_factory=list)


class WeightsIn(BaseModel):
    cost: int = Field(ge=0, le=100000)
    preference: int = Field(ge=0, le=100000)
    fairness: int = Field(ge=0, le=100000)
    overtime: int = Field(ge=0, le=100000)
    night_imbalance: int = Field(ge=0, le=100000)
    weekend_imbalance: int = Field(ge=0, le=100000)
    understaff: int = Field(ge=0, le=100000)


class RulesIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    min_rest_hours: float = Field(ge=0, le=48)
    max_shift_hours: int = Field(ge=1, le=24)
    max_consecutive_days: int | None = Field(default=6, ge=1, le=14)
    overtime_threshold_hours: int = Field(ge=1, le=80)
    relaxed_understaffing: bool = False
    weights: WeightsIn


class RunIn(BaseModel):
    mode: Literal["reproducible", "fast"] = "reproducible"
    random_seed: int = Field(default=1, ge=0, le=2_147_483_647)
    label: str = Field(default="current", max_length=80)


class DemoIn(BaseModel):
    scenario: Literal["optimal", "feasible", "infeasible"]

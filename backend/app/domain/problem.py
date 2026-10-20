"""Pure scheduling inputs. No database and no solver imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SkillRequirement:
    """Employees qualify if they hold any listed skill. Rows are ANDed."""

    any_of_ids: tuple[int, ...]
    label: str
    min_count: int


@dataclass(frozen=True)
class Shift:
    id: int
    label: str
    start: datetime
    end: datetime
    local_start_date: str
    start_local: str
    end_local: str
    overnight: bool
    required_count: int
    skill_requirements: tuple[SkillRequirement, ...]
    is_night: bool
    is_weekend: bool

    @property
    def duration_hours(self) -> int:
        seconds = (self.end - self.start).total_seconds()
        return int(seconds // 3600)


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime
    local_start_date: str
    hours: int


@dataclass(frozen=True)
class Employee:
    id: int
    display_alias: str
    skill_ids: frozenset[int]
    weekly_hour_cap: int
    cost_per_hour: int
    night_preference: str
    weekend_preference: str
    available: tuple[tuple[datetime, datetime], ...]
    time_off: tuple[tuple[datetime, datetime], ...]
    prior_shifts: tuple[BusyInterval, ...] = ()


@dataclass(frozen=True)
class Weights:
    cost: int = 1
    preference: int = 8
    fairness: int = 4
    overtime: int = 15
    night_imbalance: int = 3
    weekend_imbalance: int = 3
    understaff: int = 500

    def as_dict(self) -> dict[str, int]:
        return {
            "cost": self.cost,
            "preference": self.preference,
            "fairness": self.fairness,
            "overtime": self.overtime,
            "night_imbalance": self.night_imbalance,
            "weekend_imbalance": self.weekend_imbalance,
            "understaff": self.understaff,
        }


@dataclass(frozen=True)
class Rules:
    min_rest_hours: float
    max_shift_hours: int
    max_consecutive_days: int | None
    overtime_threshold_hours: int
    weights: Weights
    relaxed_understaffing: bool = False
    name: str = "rules"


@dataclass(frozen=True)
class Problem:
    planning_timezone: str
    employees: tuple[Employee, ...]
    shifts: tuple[Shift, ...]
    rules: Rules
    organization_name: str = "Synthetic organization"

"""Tiny problem builders for solver and validator tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.problem import Employee, Problem, Rules, Shift, Weights

SPAN = (
    datetime(2026, 11, 1, tzinfo=UTC),
    datetime(2026, 11, 20, tzinfo=UTC),
)


def employee(employee_id: int, **overrides) -> Employee:
    data = {
        "id": employee_id,
        "display_alias": f"Person {employee_id}",
        "skill_ids": frozenset(),
        "weekly_hour_cap": 40,
        "cost_per_hour": 10,
        "night_preference": "neutral",
        "weekend_preference": "neutral",
        "available": (SPAN,),
        "time_off": (),
    }
    data.update(overrides)
    return Employee(**data)


def shift(shift_id: int, start: datetime, hours: int = 8, **overrides) -> Shift:
    end = start + timedelta(hours=hours)
    data = {
        "id": shift_id,
        "label": "Shift",
        "start": start,
        "end": end,
        "local_start_date": start.date().isoformat(),
        "start_local": start.strftime("%H:%M"),
        "end_local": end.strftime("%H:%M"),
        "overnight": end.date() != start.date(),
        "required_count": 1,
        "skill_requirements": (),
        "is_night": start.hour >= 20 or start.hour < 6,
        "is_weekend": start.weekday() >= 5,
    }
    data.update(overrides)
    return Shift(**data)


def rules(**overrides) -> Rules:
    weights = overrides.pop(
        "weights",
        Weights(
            cost=0,
            preference=0,
            fairness=0,
            overtime=0,
            night_imbalance=0,
            weekend_imbalance=0,
            understaff=0,
        ),
    )
    data = {
        "min_rest_hours": 8,
        "max_shift_hours": 12,
        "max_consecutive_days": None,
        "overtime_threshold_hours": 100,
        "weights": weights,
        "relaxed_understaffing": False,
        "name": "test",
    }
    data.update(overrides)
    return Rules(**data)


def problem(employees: list[Employee], shifts: list[Shift], ruleset: Rules | None = None) -> Problem:
    return Problem(
        planning_timezone="UTC",
        organization_name="Test ward (synthetic)",
        employees=tuple(employees),
        shifts=tuple(shifts),
        rules=ruleset or rules(),
    )

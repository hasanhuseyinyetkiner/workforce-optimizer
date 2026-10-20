"""Build a pure Problem from the current database rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.problem import Employee as DomainEmployee
from app.domain.problem import Problem, Rules, Shift, SkillRequirement, Weights
from app.models import Employee, Organization, Ruleset, ShiftInstance, Skill


def default_rules() -> Rules:
    return Rules(
        name="Default rules",
        min_rest_hours=8,
        max_shift_hours=12,
        max_consecutive_days=6,
        overtime_threshold_hours=40,
        relaxed_understaffing=False,
        weights=Weights(),
    )


def rules_from_row(row: Ruleset) -> Rules:
    raw = row.weights or {}
    return Rules(
        name=row.name,
        min_rest_hours=float(row.min_rest_hours),
        max_shift_hours=int(row.max_shift_hours),
        max_consecutive_days=row.max_consecutive_days,
        overtime_threshold_hours=int(row.overtime_threshold_hours),
        relaxed_understaffing=bool(row.relaxed_understaffing),
        weights=Weights(
            cost=int(raw["cost"]),
            preference=int(raw["preference"]),
            fairness=int(raw["fairness"]),
            overtime=int(raw["overtime"]),
            night_imbalance=int(raw["night_imbalance"]),
            weekend_imbalance=int(raw["weekend_imbalance"]),
            understaff=int(raw["understaff"]),
        ),
    )


def active_ruleset(session: Session) -> Ruleset | None:
    return session.scalar(select(Ruleset).where(Ruleset.is_active.is_(True)).order_by(Ruleset.id.desc()))


def build_problem(session: Session) -> Problem:
    org = session.scalar(select(Organization).order_by(Organization.id).limit(1))
    timezone_name = org.planning_timezone if org is not None else "America/New_York"
    organization_name = org.name if org is not None else "Synthetic organization"
    ids_by_name = {skill.name: skill.id for skill in session.scalars(select(Skill)).all()}
    employees: list[DomainEmployee] = []
    for row in session.scalars(select(Employee).order_by(Employee.id)).all():
        employees.append(
            DomainEmployee(
                id=row.id,
                display_alias=row.display_alias,
                skill_ids=frozenset(skill.id for skill in row.skills),
                weekly_hour_cap=row.weekly_hour_cap,
                cost_per_hour=row.cost_per_hour,
                night_preference=row.night_preference,
                weekend_preference=row.weekend_preference,
                available=tuple((window.start_utc, window.end_utc) for window in row.availability),
                time_off=tuple((item.start_utc, item.end_utc) for item in row.time_off),
            )
        )
    shifts: list[Shift] = []
    for row in session.scalars(select(ShiftInstance).order_by(ShiftInstance.start_utc, ShiftInstance.id)).all():
        requirements = tuple(
            SkillRequirement(
                any_of_ids=tuple(ids_by_name[name] for name in requirement.skill_names),
                label=" or ".join(requirement.skill_names),
                min_count=requirement.min_count,
            )
            for requirement in row.requirements
        )
        shifts.append(
            Shift(
                id=row.id,
                label=row.label,
                start=row.start_utc,
                end=row.end_utc,
                local_start_date=row.local_date,
                start_local=row.start_local,
                end_local=row.end_local,
                overnight=row.overnight,
                required_count=row.required_count,
                skill_requirements=requirements,
                is_night=row.is_night,
                is_weekend=row.is_weekend,
            )
        )
    rules_row = active_ruleset(session)
    rules = rules_from_row(rules_row) if rules_row is not None else default_rules()
    return Problem(
        planning_timezone=timezone_name,
        organization_name=organization_name,
        employees=tuple(employees),
        shifts=tuple(shifts),
        rules=rules,
    )

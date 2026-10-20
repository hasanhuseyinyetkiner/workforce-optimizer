"""Employee, shift, template, and rules edits."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.errors import DomainError
from app.domain.timeutil import duration_hours, local_wall_to_utc, parse_hhmm, parse_local_datetime
from app.models import (
    AvailabilityWindow,
    Employee,
    EmployeeSkill,
    Organization,
    Ruleset,
    ShiftInstance,
    ShiftSkillRequirement,
    ShiftTemplate,
    Skill,
    TimeOff,
)
from app.services.problem_builder import active_ruleset

PREFERENCES = {"avoid", "neutral", "prefer"}


def get_organization(session: Session) -> Organization:
    org = session.scalar(select(Organization).order_by(Organization.id).limit(1))
    if org is not None:
        return org
    org = Organization(name="Northwind Ward (synthetic)", planning_timezone="America/New_York")
    session.add(org)
    session.flush()
    return org


def _skills(session: Session, names: list[str]) -> list[Skill]:
    found: list[Skill] = []
    for name in names:
        cleaned = name.strip()
        if not cleaned:
            continue
        skill = session.scalar(select(Skill).where(Skill.name == cleaned))
        if skill is None:
            skill = Skill(name=cleaned)
            session.add(skill)
            session.flush()
        found.append(skill)
    return found


def _default_availability(session: Session, timezone_name: str) -> tuple[datetime, datetime]:
    shifts = session.scalars(select(ShiftInstance)).all()
    if shifts:
        start = min(shift.start_utc for shift in shifts) - timedelta(days=1)
        end = max(shift.end_utc for shift in shifts) + timedelta(days=1)
        return start, end
    start = local_wall_to_utc(datetime(2026, 1, 1, 0, 0), timezone_name)
    end = local_wall_to_utc(datetime(2027, 1, 1, 0, 0), timezone_name)
    return start, end


def create_employee(session: Session, payload: dict) -> Employee:
    alias = payload["display_alias"].strip()
    if session.scalar(select(Employee.id).where(Employee.display_alias == alias)):
        raise DomainError("duplicate_employee", f"{alias} already exists.")
    night = payload.get("night_preference", "neutral")
    weekend = payload.get("weekend_preference", "neutral")
    if night not in PREFERENCES or weekend not in PREFERENCES:
        raise DomainError("invalid_preference", "Preference must be avoid, neutral, or prefer.")
    org = get_organization(session)
    row = Employee(
        display_alias=alias,
        weekly_hour_cap=payload["weekly_hour_cap"],
        cost_per_hour=payload["cost_per_hour"],
        night_preference=night,
        weekend_preference=weekend,
    )
    session.add(row)
    session.flush()
    for skill in _skills(session, payload.get("skill_names", [])):
        session.add(EmployeeSkill(employee_id=row.id, skill_id=skill.id))
    start, end = _default_availability(session, org.planning_timezone)
    session.add(AvailabilityWindow(employee_id=row.id, start_utc=start, end_utc=end))
    session.commit()
    session.refresh(row)
    return row


def update_employee(session: Session, employee_id: int, payload: dict) -> Employee:
    row = session.get(Employee, employee_id)
    if row is None:
        raise DomainError("not_found", "Employee not found.")
    if "display_alias" in payload and payload["display_alias"] is not None:
        row.display_alias = payload["display_alias"].strip()
    for field in ("weekly_hour_cap", "cost_per_hour", "night_preference", "weekend_preference"):
        if payload.get(field) is not None:
            setattr(row, field, payload[field])
    if payload.get("night_preference") not in (None, *PREFERENCES) or payload.get(
        "weekend_preference"
    ) not in (None, *PREFERENCES):
        raise DomainError("invalid_preference", "Preference must be avoid, neutral, or prefer.")
    if payload.get("skill_names") is not None:
        session.execute(delete(EmployeeSkill).where(EmployeeSkill.employee_id == row.id))
        session.flush()
        for skill in _skills(session, payload["skill_names"]):
            session.add(EmployeeSkill(employee_id=row.id, skill_id=skill.id))
    session.commit()
    session.refresh(row)
    return row


def delete_employee(session: Session, employee_id: int) -> None:
    row = session.get(Employee, employee_id)
    if row is None:
        raise DomainError("not_found", "Employee not found.")
    session.delete(row)
    session.commit()


def add_time_off(session: Session, employee_id: int, payload: dict) -> TimeOff:
    row = session.get(Employee, employee_id)
    if row is None:
        raise DomainError("not_found", "Employee not found.")
    org = get_organization(session)
    start = parse_local_datetime(payload["start_local"], org.planning_timezone)
    end = parse_local_datetime(payload["end_local"], org.planning_timezone)
    if end <= start:
        raise DomainError("invalid_time_off", "Time off end must be after its start.")
    item = TimeOff(
        employee_id=row.id,
        start_utc=start,
        end_utc=end,
        reason=(payload.get("reason") or "PTO").strip() or "PTO",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def create_template(session: Session, payload: dict) -> ShiftTemplate:
    parse_hhmm(payload["start_local"])
    parse_hhmm(payload["end_local"])
    row = ShiftTemplate(
        name=payload["name"].strip(),
        start_local=payload["start_local"].strip(),
        end_local=payload["end_local"].strip(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def create_shift(session: Session, payload: dict) -> ShiftInstance:
    org = get_organization(session)
    row = _shift_row(session, org.planning_timezone, payload, template_id=payload.get("template_id"))
    session.add(row)
    session.flush()
    _replace_requirements(session, row, payload.get("skill_requirements", []))
    session.commit()
    session.refresh(row)
    return row


def delete_shift(session: Session, shift_id: int) -> None:
    row = session.get(ShiftInstance, shift_id)
    if row is None:
        raise DomainError("not_found", "Shift not found.")
    session.delete(row)
    session.commit()


def save_rules(session: Session, payload: dict) -> Ruleset:
    current = active_ruleset(session)
    if current is None:
        current = Ruleset(name=payload["name"], is_active=True, weights={})
        session.add(current)
    current.name = payload["name"].strip()
    current.min_rest_hours = payload["min_rest_hours"]
    current.max_shift_hours = payload["max_shift_hours"]
    current.max_consecutive_days = payload.get("max_consecutive_days")
    current.overtime_threshold_hours = payload["overtime_threshold_hours"]
    current.relaxed_understaffing = payload["relaxed_understaffing"]
    current.weights = payload["weights"]
    current.is_active = True
    session.commit()
    session.refresh(current)
    return current


def _shift_row(session: Session, timezone_name: str, payload: dict, template_id: int | None) -> ShiftInstance:
    local_date = payload["local_date"]
    start_hour, start_minute = parse_hhmm(payload["start_local"])
    end_hour, end_minute = parse_hhmm(payload["end_local"])
    start_local = datetime(local_date.year, local_date.month, local_date.day, start_hour, start_minute)
    end_local = datetime(local_date.year, local_date.month, local_date.day, end_hour, end_minute)
    overnight = end_local <= start_local
    if overnight:
        end_local = end_local + timedelta(days=1)
    start_utc = local_wall_to_utc(start_local, timezone_name)
    end_utc = local_wall_to_utc(end_local, timezone_name)
    duration_hours(start_utc, end_utc)
    return ShiftInstance(
        template_id=template_id,
        label=payload["label"].strip(),
        local_date=local_date.isoformat(),
        start_local=f"{start_hour:02d}:{start_minute:02d}",
        end_local=f"{end_hour:02d}:{end_minute:02d}",
        start_utc=start_utc,
        end_utc=end_utc,
        overnight=overnight,
        required_count=payload["required_count"],
        is_night=start_hour >= 20 or start_hour < 6,
        is_weekend=local_date.weekday() >= 5,
    )


def _replace_requirements(session: Session, shift: ShiftInstance, requirements: list[dict]) -> None:
    for requirement in requirements:
        names = [name.strip() for name in requirement["skill_names"] if name.strip()]
        if not names:
            raise DomainError("invalid_skill_spec", "A skill requirement needs at least one skill name.")
        _skills(session, names)
        session.add(
            ShiftSkillRequirement(
                shift_id=shift.id,
                min_count=requirement["min_count"],
                skill_names=names,
            )
        )

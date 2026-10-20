"""Replace the database with a packaged synthetic scenario."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.domain.scenario import load_scenario
from app.models import (
    Assignment,
    AvailabilityWindow,
    Employee,
    EmployeeSkill,
    OptimizationRun,
    Organization,
    Ruleset,
    ScheduleVersion,
    ShiftInstance,
    ShiftSkillRequirement,
    ShiftTemplate,
    Skill,
    TimeOff,
)


def wipe_domain(session: Session) -> None:
    for model in (
        Assignment,
        ScheduleVersion,
        OptimizationRun,
        ShiftSkillRequirement,
        ShiftInstance,
        ShiftTemplate,
        TimeOff,
        AvailabilityWindow,
        EmployeeSkill,
        Employee,
        Skill,
        Ruleset,
        Organization,
    ):
        session.execute(delete(model))
    session.flush()


def load_scenario_into_db(session: Session, scenario: str) -> dict[str, int]:
    bundle = load_scenario(scenario)
    wipe_domain(session)
    session.add(
        Organization(name=bundle.organization_name, planning_timezone=bundle.planning_timezone)
    )
    for name in sorted(bundle.skill_names.values()):
        session.add(Skill(name=name))
    session.flush()
    skills = {skill.name: skill for skill in session.scalars(select(Skill)).all()}
    for employee in bundle.problem.employees:
        row = Employee(
            display_alias=employee.display_alias,
            weekly_hour_cap=employee.weekly_hour_cap,
            cost_per_hour=employee.cost_per_hour,
            night_preference=employee.night_preference,
            weekend_preference=employee.weekend_preference,
        )
        session.add(row)
        session.flush()
        for skill_id in sorted(employee.skill_ids):
            session.add(EmployeeSkill(employee_id=row.id, skill_id=skills[bundle.skill_names[skill_id]].id))
        for start, end in employee.available:
            session.add(AvailabilityWindow(employee_id=row.id, start_utc=start, end_utc=end))
        for start, end in employee.time_off:
            session.add(
                TimeOff(employee_id=row.id, start_utc=start, end_utc=end, reason="PTO")
            )
    for template in bundle.templates:
        session.add(
            ShiftTemplate(
                name=template["name"],
                start_local=template["start_local"],
                end_local=template["end_local"],
            )
        )
    session.flush()
    templates = {item.name: item for item in session.scalars(select(ShiftTemplate)).all()}
    for shift in bundle.problem.shifts:
        template = templates.get(shift.label)
        row = ShiftInstance(
            template_id=template.id if template is not None else None,
            label=shift.label,
            local_date=shift.local_start_date,
            start_local=shift.start_local,
            end_local=shift.end_local,
            start_utc=shift.start,
            end_utc=shift.end,
            overnight=shift.overnight,
            required_count=shift.required_count,
            is_night=shift.is_night,
            is_weekend=shift.is_weekend,
        )
        session.add(row)
        session.flush()
        for requirement in shift.skill_requirements:
            names = [bundle.skill_names[skill_id] for skill_id in requirement.any_of_ids]
            session.add(
                ShiftSkillRequirement(shift_id=row.id, min_count=requirement.min_count, skill_names=names)
            )
    rules = bundle.problem.rules
    session.add(
        Ruleset(
            name=rules.name,
            min_rest_hours=rules.min_rest_hours,
            max_shift_hours=rules.max_shift_hours,
            max_consecutive_days=rules.max_consecutive_days,
            overtime_threshold_hours=rules.overtime_threshold_hours,
            relaxed_understaffing=rules.relaxed_understaffing,
            weights=rules.weights.as_dict(),
            is_active=True,
        )
    )
    session.commit()
    return {
        "employees": session.scalar(select(func.count()).select_from(Employee)) or 0,
        "shifts": session.scalar(select(func.count()).select_from(ShiftInstance)) or 0,
        "skills": session.scalar(select(func.count()).select_from(Skill)) or 0,
    }


def seed_if_empty(session: Session) -> bool:
    count = session.scalar(select(func.count()).select_from(Employee)) or 0
    if count:
        return False
    load_scenario_into_db(session, "feasible")
    return True

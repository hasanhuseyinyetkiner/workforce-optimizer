"""JSON-ready views. Every figure the UI shows is computed here."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.scoring import schedule_kpis, score_schedule
from app.domain.solver import mode_label
from app.domain.timeutil import format_local
from app.domain.validator import validate_schedule
from app.models import (
    Employee,
    OptimizationRun,
    ScheduleVersion,
    ShiftInstance,
    ShiftTemplate,
    Skill,
    TimeOff,
)
from app.services.problem_builder import build_problem


def employee_dict(row: Employee, timezone_name: str) -> dict:
    return {
        "id": row.id,
        "display_alias": row.display_alias,
        "weekly_hour_cap": row.weekly_hour_cap,
        "cost_per_hour": row.cost_per_hour,
        "night_preference": row.night_preference,
        "weekend_preference": row.weekend_preference,
        "skills": sorted(skill.name for skill in row.skills),
        "availability": [
            {
                "id": window.id,
                "start_utc": window.start_utc,
                "end_utc": window.end_utc,
                "start_local": format_local(window.start_utc, timezone_name),
                "end_local": format_local(window.end_utc, timezone_name),
            }
            for window in row.availability
        ],
        "time_off": [
            {
                "id": item.id,
                "start_utc": item.start_utc,
                "end_utc": item.end_utc,
                "start_local": format_local(item.start_utc, timezone_name),
                "end_local": format_local(item.end_utc, timezone_name),
                "reason": item.reason,
            }
            for item in row.time_off
        ],
    }


def shift_dict(row: ShiftInstance) -> dict:
    return {
        "id": row.id,
        "template_id": row.template_id,
        "label": row.label,
        "local_date": row.local_date,
        "start_local": row.start_local,
        "end_local": row.end_local,
        "start_utc": row.start_utc,
        "end_utc": row.end_utc,
        "overnight": row.overnight,
        "required_count": row.required_count,
        "is_night": row.is_night,
        "is_weekend": row.is_weekend,
        "duration_hours": int((row.end_utc - row.start_utc).total_seconds() // 3600),
        "skill_requirements": [
            {
                "skill_names": list(requirement.skill_names),
                "label": " or ".join(requirement.skill_names),
                "min_count": requirement.min_count,
            }
            for requirement in row.requirements
        ],
    }


def template_dict(row: ShiftTemplate) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "start_local": row.start_local,
        "end_local": row.end_local,
    }


def rules_dict(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "min_rest_hours": row.min_rest_hours,
        "max_shift_hours": row.max_shift_hours,
        "max_consecutive_days": row.max_consecutive_days,
        "overtime_threshold_hours": row.overtime_threshold_hours,
        "relaxed_understaffing": row.relaxed_understaffing,
        "weights": row.weights,
        "is_active": row.is_active,
    }


def run_dict(session: Session, run: OptimizationRun) -> dict:
    schedule_id = session.scalar(
        select(ScheduleVersion.id).where(ScheduleVersion.optimization_run_id == run.id)
    )
    parameters = run.parameters or {}
    return {
        "id": run.id,
        "status": run.status,
        "solver_status": run.solver_status,
        "objective": run.objective,
        "best_bound": run.best_bound,
        "runtime_seconds": run.runtime_seconds,
        "mode": run.mode,
        "reproducible": run.mode == "reproducible",
        "mode_label": parameters.get("mode_label") or mode_label(run.mode),
        "random_seed": run.random_seed,
        "parameters": parameters,
        "label": run.label,
        "error_message": run.error_message,
        "diagnostics": run.diagnostics,
        "objective_breakdown": run.objective_breakdown,
        "schedule_id": schedule_id,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "heartbeat_at": run.heartbeat_at,
    }


def schedule_dict(session: Session, schedule: ScheduleVersion) -> dict:
    problem = build_problem(session)
    pairs = [(row.employee_id, row.shift_instance_id) for row in schedule.assignments]
    validation = validate_schedule(problem, pairs)
    breakdown = score_schedule(problem, pairs)
    run = session.get(OptimizationRun, schedule.optimization_run_id)
    solver_status = run.solver_status if run is not None and run.solver_status else "UNKNOWN"
    kpis = schedule_kpis(problem, pairs, breakdown, solver_status)
    employees = {employee.id: employee for employee in problem.employees}
    shifts = {shift.id: shift for shift in problem.shifts}
    assignment_rows = []
    for employee_id, shift_id in sorted(pairs):
        employee = employees.get(employee_id)
        shift = shifts.get(shift_id)
        if employee is None or shift is None:
            continue
        assignment_rows.append(
            {
                "employee_id": employee.id,
                "display_alias": employee.display_alias,
                "shift_id": shift.id,
                "label": shift.label,
                "local_date": shift.local_start_date,
                "start_local": shift.start_local,
                "end_local": shift.end_local,
                "start_utc": shift.start,
                "end_utc": shift.end,
                "overnight": shift.overnight,
                "is_night": shift.is_night,
                "is_weekend": shift.is_weekend,
                "hours": shift.duration_hours,
            }
        )
    parameters = run.parameters if run is not None else {}
    return {
        "id": schedule.id,
        "run_id": schedule.optimization_run_id,
        "solver_status": solver_status,
        "objective": breakdown.total,
        "best_bound": run.best_bound if run is not None else None,
        "runtime_seconds": run.runtime_seconds if run is not None else None,
        "mode": run.mode if run is not None else None,
        "reproducible": bool(run and run.mode == "reproducible"),
        "mode_label": (parameters or {}).get("mode_label") or (mode_label(run.mode) if run else None),
        "parameters": parameters or {},
        "objective_breakdown": breakdown.as_dict(),
        "employee_hours": kpis["employee_hours"],
        "assignments": assignment_rows,
        "shifts": [
            {
                "id": shift.id,
                "label": shift.label,
                "local_date": shift.local_start_date,
                "start_local": shift.start_local,
                "end_local": shift.end_local,
                "start_utc": shift.start,
                "end_utc": shift.end,
                "overnight": shift.overnight,
                "required_count": shift.required_count,
                "is_night": shift.is_night,
                "is_weekend": shift.is_weekend,
                "duration_hours": shift.duration_hours,
                "skill_requirements": [
                    {
                        "label": requirement.label,
                        "min_count": requirement.min_count,
                    }
                    for requirement in shift.skill_requirements
                ],
            }
            for shift in problem.shifts
        ],
        "employees": [
            {
                "id": employee.id,
                "display_alias": employee.display_alias,
                "skills": sorted(
                    skill.name
                    for skill in session.get(Employee, employee.id).skills  # type: ignore[union-attr]
                )
                if session.get(Employee, employee.id) is not None
                else [],
                "weekly_hour_cap": employee.weekly_hour_cap,
                "hours": next(
                    item["hours"]
                    for item in kpis["employee_hours"]
                    if item["employee_id"] == employee.id
                ),
            }
            for employee in problem.employees
        ],
        "validation": validation.as_dict(),
        "kpis": kpis,
        "planning_timezone": problem.planning_timezone,
        "organization_name": problem.organization_name,
        "days": sorted({shift.local_start_date for shift in problem.shifts}),
        "rules": {
            "name": problem.rules.name,
            "min_rest_hours": problem.rules.min_rest_hours,
            "max_shift_hours": problem.rules.max_shift_hours,
            "max_consecutive_days": problem.rules.max_consecutive_days,
            "overtime_threshold_hours": problem.rules.overtime_threshold_hours,
            "relaxed_understaffing": problem.rules.relaxed_understaffing,
            "weights": problem.rules.weights.as_dict(),
        },
        "created_at": schedule.created_at,
    }


def overview_dict(session: Session, *, demo: bool) -> dict:
    from app.models import Organization

    org = session.scalar(select(Organization).order_by(Organization.id).limit(1))
    latest = session.scalar(select(OptimizationRun).order_by(OptimizationRun.id.desc()).limit(1))
    recent = session.scalars(select(OptimizationRun).order_by(OptimizationRun.id.desc()).limit(8)).all()
    schedule_payload = None
    if latest is not None:
        schedule_id = session.scalar(
            select(ScheduleVersion.id).where(ScheduleVersion.optimization_run_id == latest.id)
        )
        if schedule_id is not None:
            schedule = session.get(ScheduleVersion, schedule_id)
            if schedule is not None:
                full = schedule_dict(session, schedule)
                schedule_payload = {
                    "id": full["id"],
                    "solver_status": full["solver_status"],
                    "objective_breakdown": full["objective_breakdown"],
                    "kpis": full["kpis"],
                    "validation": full["validation"],
                    "mode_label": full["mode_label"],
                }
    return {
        "demo": demo,
        "synthetic_data": True,
        "organization_name": org.name if org is not None else None,
        "planning_timezone": org.planning_timezone if org is not None else None,
        "counts": {
            "employees": _count(session, Employee),
            "shifts": _count(session, ShiftInstance),
            "skills": _count(session, Skill),
        },
        "latest_run": run_dict(session, latest) if latest is not None else None,
        "recent_runs": [run_dict(session, run) for run in recent],
        "schedule": schedule_payload,
    }


def _count(session: Session, model) -> int:
    from sqlalchemy import func

    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def schedule_csv(session: Session, schedule: ScheduleVersion) -> str:
    payload = schedule_dict(session, schedule)
    lines = [
        "employee_alias,employee_id,shift_id,shift_label,local_date,start_local,end_local,start_utc,end_utc,hours,overnight"
    ]
    for row in payload["assignments"]:
        lines.append(
            ",".join(
                [
                    _csv(row["display_alias"]),
                    str(row["employee_id"]),
                    str(row["shift_id"]),
                    _csv(row["label"]),
                    row["local_date"],
                    row["start_local"],
                    row["end_local"],
                    _as_utc(row["start_utc"]),
                    _as_utc(row["end_utc"]),
                    str(row["hours"]),
                    "true" if row["overnight"] else "false",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def schedule_ics(session: Session, schedule: ScheduleVersion) -> str:
    payload = schedule_dict(session, schedule)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Workforce Optimizer//Synthetic Demo//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics(payload['organization_name'])}",
        "X-WR-TIMEZONE:UTC",
    ]
    for index, row in enumerate(payload["assignments"], start=1):
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:schedule-{payload['id']}-shift-{row['shift_id']}-employee-{row['employee_id']}@workforce-optimizer.local",
                f"DTSTAMP:{_ics_time(payload['created_at'])}",
                f"DTSTART:{_ics_time(row['start_utc'])}",
                f"DTEND:{_ics_time(row['end_utc'])}",
                f"SUMMARY:{_ics(row['display_alias'])} · {_ics(row['label'])}",
                f"DESCRIPTION:Synthetic assignment {index}. Hours={row['hours']}. Not a legal work record.",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _csv(value: str) -> str:
    if any(char in value for char in ",\"\n"):
        return '"' + value.replace('"', '""') + '"'
    return value


def _ics(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", " ")


def _ics_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _as_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def time_off_dict(item: TimeOff, timezone_name: str) -> dict:
    return {
        "id": item.id,
        "employee_id": item.employee_id,
        "start_utc": item.start_utc,
        "end_utc": item.end_utc,
        "start_local": format_local(item.start_utc, timezone_name),
        "end_local": format_local(item.end_utc, timezone_name),
        "reason": item.reason,
    }


def schedule_summary(session: Session, schedule: ScheduleVersion) -> dict:
    run = session.get(OptimizationRun, schedule.optimization_run_id)
    parameters = run.parameters if run is not None else {}
    return {
        "id": schedule.id,
        "run_id": schedule.optimization_run_id,
        "label": run.label if run is not None else "",
        "solver_status": run.solver_status if run is not None else "UNKNOWN",
        "objective": run.objective if run is not None else None,
        "mode": run.mode if run is not None else None,
        "mode_label": (parameters or {}).get("mode_label") or (mode_label(run.mode) if run else None),
        "created_at": schedule.created_at,
        "assignment_count": len(schedule.assignments),
    }


def _rules_for_run(session: Session, run: OptimizationRun | None) -> dict:
    from app.models import Ruleset

    if run is None or run.ruleset_id is None:
        return {}
    row = session.get(Ruleset, run.ruleset_id)
    if row is None:
        return {}
    return rules_dict(row)


def compare_schedules(session: Session, left: ScheduleVersion, right: ScheduleVersion) -> dict:
    """Diff two stored schedules on persisted objectives, rulesets, and assignment pairs."""
    left_payload = schedule_dict(session, left)
    right_payload = schedule_dict(session, right)
    left_run = session.get(OptimizationRun, left.optimization_run_id)
    right_run = session.get(OptimizationRun, right.optimization_run_id)
    left_pairs = {(row["employee_id"], row["shift_id"]) for row in left_payload["assignments"]}
    right_pairs = {(row["employee_id"], row["shift_id"]) for row in right_payload["assignments"]}
    only_left = sorted(left_pairs - right_pairs)
    only_right = sorted(right_pairs - left_pairs)
    shared = sorted(left_pairs & right_pairs)

    left_breakdown = (left_run.objective_breakdown if left_run and left_run.objective_breakdown else None) or left_payload[
        "objective_breakdown"
    ]
    right_breakdown = (
        right_run.objective_breakdown if right_run and right_run.objective_breakdown else None
    ) or right_payload["objective_breakdown"]
    delta = {
        key: int(right_breakdown.get(key, 0)) - int(left_breakdown.get(key, 0))
        for key in sorted(set(left_breakdown) | set(right_breakdown))
    }

    left_rules = _rules_for_run(session, left_run) or left_payload["rules"]
    right_rules = _rules_for_run(session, right_run) or right_payload["rules"]
    left_weights = left_rules.get("weights") or {}
    right_weights = right_rules.get("weights") or {}
    weight_keys = sorted(set(left_weights) | set(right_weights))
    weight_deltas = {
        key: int(right_weights.get(key, 0)) - int(left_weights.get(key, 0)) for key in weight_keys
    }
    rules_match = left_rules == right_rules
    left_objective = left_run.objective if left_run and left_run.objective is not None else left_payload["objective"]
    right_objective = (
        right_run.objective if right_run and right_run.objective is not None else right_payload["objective"]
    )

    return {
        "left": {
            "id": left.id,
            "run_id": left.optimization_run_id,
            "label": schedule_summary(session, left)["label"],
            "solver_status": left_payload["solver_status"],
            "objective": left_objective,
            "objective_breakdown": left_breakdown,
            "mode_label": left_payload["mode_label"],
            "validation": left_payload["validation"],
            "rules": left_rules,
        },
        "right": {
            "id": right.id,
            "run_id": right.optimization_run_id,
            "label": schedule_summary(session, right)["label"],
            "solver_status": right_payload["solver_status"],
            "objective": right_objective,
            "objective_breakdown": right_breakdown,
            "mode_label": right_payload["mode_label"],
            "validation": right_payload["validation"],
            "rules": right_rules,
        },
        "objective_delta": delta,
        "rules_match": rules_match,
        "weight_deltas": weight_deltas,
        "assignment_diff": {
            "shared_count": len(shared),
            "only_left": [{"employee_id": e, "shift_id": s} for e, s in only_left],
            "only_right": [{"employee_id": e, "shift_id": s} for e, s in only_right],
            "only_left_count": len(only_left),
            "only_right_count": len(only_right),
        },
    }

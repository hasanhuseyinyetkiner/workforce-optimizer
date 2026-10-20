"""Independent hard-constraint checker. This module must not import OR-Tools."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.domain.eligibility import (
    employee_block_reason,
    gap_too_short,
    horizon_dates,
    overlaps,
    rest_threshold,
    week_key,
)
from app.domain.problem import Employee, Problem, Shift


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    shift_id: int | None = None
    employee_id: int | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "shift_id": self.shift_id,
            "employee_id": self.employee_id,
        }


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    violations: tuple[Violation, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "violations": [item.as_dict() for item in self.violations],
        }


def validate_schedule(problem: Problem, assignments: list[tuple[int, int]]) -> ValidationResult:
    violations: list[Violation] = []
    employees = {employee.id: employee for employee in problem.employees}
    shifts = {shift.id: shift for shift in problem.shifts}
    seen: set[tuple[int, int]] = set()

    for employee_id, shift_id in assignments:
        employee = employees.get(employee_id)
        shift = shifts.get(shift_id)
        if employee is None:
            violations.append(
                Violation(
                    "unknown_employee",
                    f"Assignment references unknown employee {employee_id}.",
                    shift_id=shift_id,
                    employee_id=employee_id,
                )
            )
            continue
        if shift is None:
            violations.append(
                Violation(
                    "unknown_shift",
                    f"Assignment references unknown shift {shift_id}.",
                    shift_id=shift_id,
                    employee_id=employee_id,
                )
            )
            continue
        if (employee_id, shift_id) in seen:
            violations.append(
                Violation(
                    "duplicate_assignment",
                    f"{employee.display_alias} is assigned twice to {shift.label} on {shift.local_start_date}.",
                    shift_id=shift_id,
                    employee_id=employee_id,
                )
            )
            continue
        seen.add((employee_id, shift_id))
        reason = employee_block_reason(employee, shift, problem)
        if reason is not None:
            violations.append(
                Violation(
                    reason,
                    _block_message(reason, employee, shift, problem),
                    shift_id=shift_id,
                    employee_id=employee_id,
                )
            )

    by_employee: dict[int, list[Shift]] = defaultdict(list)
    for employee_id, shift_id in seen:
        by_employee[employee_id].append(shifts[shift_id])

    minimum = rest_threshold(problem.rules.min_rest_hours)
    for employee in problem.employees:
        taken = sorted(by_employee.get(employee.id, []), key=lambda item: (item.start, item.id))
        for index, left in enumerate(taken):
            for right in taken[index + 1 :]:
                if not gap_too_short(left.start, left.end, right.start, right.end, minimum):
                    continue
                code = (
                    "overlap"
                    if overlaps(left.start, left.end, right.start, right.end)
                    else "rest"
                )
                if code == "overlap":
                    message = (
                        f"{employee.display_alias} has overlapping shifts "
                        f"{left.label} ({left.local_start_date}) and {right.label} ({right.local_start_date})."
                    )
                else:
                    message = (
                        f"{employee.display_alias} has less than {problem.rules.min_rest_hours:g}h rest "
                        f"between {left.label} ({left.local_start_date}) and {right.label} ({right.local_start_date})."
                    )
                violations.append(
                    Violation(code, message, shift_id=right.id, employee_id=employee.id)
                )

        new_hours: dict[tuple[int, int], int] = defaultdict(int)
        prior_hours: dict[tuple[int, int], int] = defaultdict(int)
        for shift in taken:
            new_hours[week_key(shift.local_start_date)] += shift.duration_hours
        for prior in employee.prior_shifts:
            prior_hours[week_key(prior.local_start_date)] += prior.hours
        for key in set(new_hours) | set(prior_hours):
            total_hours = new_hours[key] + prior_hours[key]
            if new_hours[key] > 0 and total_hours > employee.weekly_hour_cap:
                year, week = key
                violations.append(
                    Violation(
                        "weekly_cap",
                        (
                            f"{employee.display_alias} is scheduled for {total_hours}h in ISO week "
                            f"{year}-W{week:02d}, above the {employee.weekly_hour_cap}h cap."
                        ),
                        employee_id=employee.id,
                    )
                )

        if problem.rules.max_consecutive_days is not None:
            worked = {date.fromisoformat(shift.local_start_date) for shift in taken}
            worked.update(date.fromisoformat(prior.local_start_date) for prior in employee.prior_shifts)
            window = problem.rules.max_consecutive_days + 1
            dates = horizon_dates(problem)
            if len(dates) >= window:
                for start_index in range(len(dates) - window + 1):
                    chunk = dates[start_index : start_index + window]
                    if sum(day in worked for day in chunk) > problem.rules.max_consecutive_days:
                        violations.append(
                            Violation(
                                "consecutive_days",
                                (
                                    f"{employee.display_alias} works more than "
                                    f"{problem.rules.max_consecutive_days} consecutive days "
                                    f"in {chunk[0].isoformat()} to {chunk[-1].isoformat()}."
                                ),
                                employee_id=employee.id,
                            )
                        )
                        break

    if not problem.rules.relaxed_understaffing:
        assigned_ids: dict[int, list[int]] = defaultdict(list)
        for employee_id, shift_id in seen:
            assigned_ids[shift_id].append(employee_id)
        for shift in problem.shifts:
            assigned = assigned_ids.get(shift.id, [])
            if len(assigned) < shift.required_count:
                violations.append(
                    Violation(
                        "coverage",
                        (
                            f"{shift.label} on {shift.local_start_date} needs {shift.required_count} "
                            f"people and has {len(assigned)}."
                        ),
                        shift_id=shift.id,
                    )
                )
            for requirement in shift.skill_requirements:
                qualified = [
                    employee_id
                    for employee_id in assigned
                    if any(
                        skill_id in employees[employee_id].skill_ids
                        for skill_id in requirement.any_of_ids
                    )
                ]
                if len(qualified) < requirement.min_count:
                    violations.append(
                        Violation(
                            "skill",
                            (
                                f"{shift.label} on {shift.local_start_date} needs {requirement.min_count} "
                                f"{requirement.label} and has {len(qualified)}."
                            ),
                            shift_id=shift.id,
                        )
                    )

    return ValidationResult(valid=not violations, violations=tuple(violations))


def _block_message(reason: str, employee: Employee, shift: Shift, problem: Problem) -> str:
    when = f"{shift.label} on {shift.local_start_date}"
    if reason == "max_shift_hours":
        return (
            f"{when} is {shift.duration_hours}h, above the {problem.rules.max_shift_hours}h maximum, "
            f"so {employee.display_alias} cannot take it."
        )
    if reason == "unavailable":
        return f"{employee.display_alias} is not available for {when}."
    if reason == "time_off":
        return f"{employee.display_alias} is on leave during {when}."
    if reason == "prior_conflict":
        return f"{employee.display_alias} has a prior commitment that blocks {when}."
    return f"{employee.display_alias} cannot take {when} ({reason})."

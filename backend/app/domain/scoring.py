"""Objective scoring for a finished assignment. No OR-Tools imports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.domain.problem import Employee, Problem, Shift, Weights


@dataclass(frozen=True)
class Breakdown:
    cost: int
    preference: int
    fairness: int
    overtime: int
    night_imbalance: int
    weekend_imbalance: int
    understaff: int

    @property
    def total(self) -> int:
        return (
            self.cost
            + self.preference
            + self.fairness
            + self.overtime
            + self.night_imbalance
            + self.weekend_imbalance
            + self.understaff
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "cost": self.cost,
            "preference": self.preference,
            "fairness": self.fairness,
            "overtime": self.overtime,
            "night_imbalance": self.night_imbalance,
            "weekend_imbalance": self.weekend_imbalance,
            "understaff": self.understaff,
            "total": self.total,
        }


def preference_points(employee: Employee, shift: Shift) -> int:
    points = 0
    if employee.night_preference == "avoid" and shift.is_night:
        points += 1
    elif employee.night_preference == "prefer" and not shift.is_night:
        points += 1
    if employee.weekend_preference == "avoid" and shift.is_weekend:
        points += 1
    elif employee.weekend_preference == "prefer" and not shift.is_weekend:
        points += 1
    return points


def _spread(values: list[int]) -> int:
    if not values:
        return 0
    total = sum(values)
    count = len(values)
    return sum(abs(count * value - total) for value in values)


def hours_by_employee(problem: Problem, assignments: list[tuple[int, int]]) -> dict[int, int]:
    totals = {employee.id: 0 for employee in problem.employees}
    shifts = {shift.id: shift for shift in problem.shifts}
    for employee_id, shift_id in assignments:
        totals[employee_id] = totals.get(employee_id, 0) + shifts[shift_id].duration_hours
    return totals


def score_schedule(problem: Problem, assignments: list[tuple[int, int]]) -> Breakdown:
    weights: Weights = problem.rules.weights
    shifts = {shift.id: shift for shift in problem.shifts}
    employees = {employee.id: employee for employee in problem.employees}
    hours = hours_by_employee(problem, assignments)
    ordered_hours = [hours[employee.id] for employee in problem.employees]

    cost = 0
    preference = 0
    night_counts = {employee.id: 0 for employee in problem.employees}
    weekend_counts = {employee.id: 0 for employee in problem.employees}
    for employee_id, shift_id in assignments:
        employee = employees[employee_id]
        shift = shifts[shift_id]
        cost += employee.cost_per_hour * shift.duration_hours
        preference += preference_points(employee, shift)
        if shift.is_night:
            night_counts[employee_id] += 1
        if shift.is_weekend:
            weekend_counts[employee_id] += 1

    overtime = sum(
        max(0, hours[employee.id] - problem.rules.overtime_threshold_hours)
        for employee in problem.employees
    )

    assigned_by_shift: dict[int, list[int]] = {shift.id: [] for shift in problem.shifts}
    for employee_id, shift_id in assignments:
        assigned_by_shift[shift_id].append(employee_id)

    understaff_units = 0
    for shift in problem.shifts:
        assigned = assigned_by_shift[shift.id]
        understaff_units += max(0, shift.required_count - len(assigned))
        for requirement in shift.skill_requirements:
            qualified = sum(
                1
                for employee_id in assigned
                if any(skill_id in employees[employee_id].skill_ids for skill_id in requirement.any_of_ids)
            )
            understaff_units += max(0, requirement.min_count - qualified)

    understaff_component = understaff_units if problem.rules.relaxed_understaffing else 0
    return Breakdown(
        cost=weights.cost * cost,
        preference=weights.preference * preference,
        fairness=weights.fairness * _spread(ordered_hours),
        overtime=weights.overtime * overtime,
        night_imbalance=weights.night_imbalance
        * _spread([night_counts[employee.id] for employee in problem.employees]),
        weekend_imbalance=weights.weekend_imbalance
        * _spread([weekend_counts[employee.id] for employee in problem.employees]),
        understaff=weights.understaff * understaff_component,
    )


def assignment_hash(assignments: list[tuple[int, int]]) -> str:
    canonical = sorted((int(employee_id), int(shift_id)) for employee_id, shift_id in assignments)
    payload = json.dumps(canonical, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def schedule_kpis(
    problem: Problem,
    assignments: list[tuple[int, int]],
    breakdown: Breakdown,
    solver_status: str,
) -> dict[str, object]:
    hours = hours_by_employee(problem, assignments)
    employees = {employee.id: employee for employee in problem.employees}
    demand_hours = sum(shift.required_count * shift.duration_hours for shift in problem.shifts)
    scheduled_hours = sum(hours.values())
    spread = (max(hours.values()) - min(hours.values())) if hours else 0
    covered = 0
    assigned_by_shift: dict[int, list[int]] = {shift.id: [] for shift in problem.shifts}
    for employee_id, shift_id in assignments:
        assigned_by_shift[shift_id].append(employee_id)
    for shift in problem.shifts:
        assigned = assigned_by_shift[shift.id]
        skills_ok = True
        for requirement in shift.skill_requirements:
            qualified = sum(
                1
                for employee_id in assigned
                if any(skill_id in employees[employee_id].skill_ids for skill_id in requirement.any_of_ids)
            )
            if qualified < requirement.min_count:
                skills_ok = False
        if len(assigned) >= shift.required_count and skills_ok:
            covered += 1
    coverage_pct = None
    if problem.shifts:
        coverage_pct = round(100.0 * covered / len(problem.shifts), 1)
    return {
        "coverage_pct": coverage_pct,
        "covered_shifts": covered,
        "shift_count": len(problem.shifts),
        "demand_hours": demand_hours,
        "scheduled_hours": scheduled_hours,
        "objective": breakdown.total,
        "solver_status": solver_status,
        "fairness_spread_hours": spread,
        "employee_hours": [
            {
                "employee_id": employee.id,
                "display_alias": employee.display_alias,
                "hours": hours[employee.id],
            }
            for employee in problem.employees
        ],
    }

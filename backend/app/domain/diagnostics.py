"""Best-effort infeasibility notes.

Capability (honest):
- Structural pre-checks (coverage/skills/rest heuristics) without OR-Tools.
- Progressive relaxation probes (named mutants).
- When OR-Tools CP-SAT assumptions are available: a *group-level* sufficient
  assumption set for hard constraint families (coverage, skills, rest, weekly
  caps, consecutive days). That is not a minimal IIS over every individual
  constraint, and we do not invent one if the API is unavailable.
"""

from __future__ import annotations

from app.domain.eligibility import employee_block_reason, rest_conflict
from app.domain.problem import Problem

DIAGNOSTIC_NOTE = (
    "Best-effort conflict diagnostics: structural findings, progressive "
    "relaxation probes, and (when available) CP-SAT sufficient assumptions over "
    "hard constraint *groups*. Not a proven minimal unsatisfiable core (IIS) "
    "over every individual constraint."
)

GROUP_LABELS = {
    "coverage": "Shift coverage (required headcount)",
    "skill_requirements": "Skill requirements",
    "rest": "Rest / no-overlap between shifts",
    "weekly_cap": "Weekly hour caps (incl. prior hours)",
    "consecutive_days": "Max consecutive working days",
}


def structural_findings(problem: Problem) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    eligible: dict[int, list] = {}
    for shift in problem.shifts:
        allowed = [
            employee
            for employee in problem.employees
            if employee_block_reason(employee, shift, problem) is None
        ]
        eligible[shift.id] = allowed
        if shift.duration_hours > problem.rules.max_shift_hours and shift.required_count > 0:
            findings.append(
                {
                    "code": "shift_exceeds_max_hours",
                    "shift_id": shift.id,
                    "message": (
                        f"{shift.label} on {shift.local_start_date} is {shift.duration_hours}h, "
                        f"above the maximum of {problem.rules.max_shift_hours}h."
                    ),
                }
            )
        if len(allowed) < shift.required_count:
            findings.append(
                {
                    "code": "insufficient_staff",
                    "shift_id": shift.id,
                    "message": (
                        f"{shift.label} on {shift.local_start_date} needs {shift.required_count} "
                        f"eligible employees; {len(allowed)} are available and not on leave."
                    ),
                }
            )
        for requirement in shift.skill_requirements:
            qualified = [
                employee
                for employee in allowed
                if any(skill_id in employee.skill_ids for skill_id in requirement.any_of_ids)
            ]
            if len(qualified) < requirement.min_count:
                code = "no_qualified_employee" if len(qualified) == 0 else "insufficient_skill"
                findings.append(
                    {
                        "code": code,
                        "shift_id": shift.id,
                        "skill": requirement.label,
                        "message": (
                            f"{shift.label} on {shift.local_start_date} needs {requirement.min_count} "
                            f"{requirement.label}; {len(qualified)} eligible employees have that skill."
                        ),
                    }
                )

    shifts = list(problem.shifts)
    for index, left in enumerate(shifts):
        for right in shifts[index + 1 :]:
            if not rest_conflict(left, right, problem.rules.min_rest_hours):
                continue
            left_ids = {employee.id for employee in eligible[left.id]}
            right_ids = {employee.id for employee in eligible[right.id]}
            if len(left_ids) == 1 and left_ids == right_ids:
                only = eligible[left.id][0]
                findings.append(
                    {
                        "code": "rest_conflict",
                        "shift_id": left.id,
                        "employee_id": only.id,
                        "message": (
                            f"Only {only.display_alias} can work both {left.label} on {left.local_start_date} "
                            f"and {right.label} on {right.local_start_date}, and rest or overlap forbids it."
                        ),
                    }
                )
    return findings


def explain(
    problem: Problem,
    relaxations: list[dict[str, object]],
    *,
    assumption_groups: list[str] | None = None,
    assumptions_available: bool = True,
) -> dict[str, object]:
    groups = list(assumption_groups or [])
    conflict_groups = [
        {
            "group": name,
            "label": GROUP_LABELS.get(name, name),
        }
        for name in groups
    ]
    return {
        "note": DIAGNOSTIC_NOTE,
        "findings": structural_findings(problem),
        "relaxations": relaxations,
        "assumptions_available": assumptions_available,
        "assumption_method": (
            "CpSolver.sufficient_assumptions_for_infeasibility"
            if assumptions_available
            else None
        ),
        "conflict_groups": conflict_groups,
        "unsat_core_kind": (
            "constraint_group_assumptions" if groups else ("unavailable" if not assumptions_available else "empty")
        ),
    }

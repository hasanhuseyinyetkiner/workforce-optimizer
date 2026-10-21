"""OR-Tools CP-SAT model. Validated against ortools 9.15.6755.

Reproducible mode sets SatParameters that the installed package documents as
deterministic when interleave_search is true: interleave_search, num_workers,
random_seed, and max_deterministic_time. share_linear2_bounds is explicitly
false because that field's docstring says enabling it is non-deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta

import ortools
from ortools.sat.python import cp_model

from app.domain.diagnostics import explain
from app.domain.eligibility import (
    employee_block_reason,
    horizon_dates,
    rest_conflict,
    week_key,
)
from app.domain.problem import Problem, Shift
from app.domain.scoring import preference_points

WORKER_CAP = 4
SOLVER_STATUSES = ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN")


@dataclass(frozen=True)
class SolverConfig:
    mode: str
    num_workers: int
    random_seed: int
    interleave_search: bool
    max_deterministic_time: float | None
    max_time_in_seconds: float | None
    share_linear2_bounds: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "ortools_version": ortools.__version__,
            "mode": self.mode,
            "mode_label": mode_label(self.mode),
            "interleave_search": self.interleave_search,
            "num_workers": self.num_workers,
            "random_seed": self.random_seed,
            "max_deterministic_time": self.max_deterministic_time,
            "max_time_in_seconds": self.max_time_in_seconds,
            "share_linear2_bounds": self.share_linear2_bounds,
            "worker_cap": WORKER_CAP,
            "log_search_progress": False,
            "log_to_stdout": False,
        }


@dataclass(frozen=True)
class SolveResult:
    solver_status: str
    objective: int | None
    best_bound: int | None
    runtime_seconds: float
    assignments: tuple[tuple[int, int], ...]
    parameters: dict[str, object]
    error: str | None = None
    conflict_groups: tuple[str, ...] = ()
    assumptions_available: bool = True


def mode_label(mode: str) -> str:
    if mode == "reproducible":
        return "Reproducible"
    return "Fast · not reproducible"


def cap_workers(requested: int) -> int:
    return max(1, min(int(requested), WORKER_CAP))


def make_config(
    mode: str,
    *,
    random_seed: int,
    num_workers: int,
    deterministic_seconds: float,
    fast_seconds: float,
) -> SolverConfig:
    workers = cap_workers(num_workers)
    if mode == "reproducible":
        return SolverConfig(
            mode="reproducible",
            num_workers=workers,
            random_seed=random_seed,
            interleave_search=True,
            max_deterministic_time=float(deterministic_seconds),
            max_time_in_seconds=None,
            share_linear2_bounds=False,
        )
    if mode != "fast":
        raise ValueError(f"Unknown solver mode: {mode}")
    return SolverConfig(
        mode="fast",
        num_workers=workers,
        random_seed=random_seed,
        interleave_search=False,
        max_deterministic_time=None,
        max_time_in_seconds=float(fast_seconds),
        share_linear2_bounds=False,
    )


def _require_parameters(solver: cp_model.CpSolver) -> None:
    required = (
        "interleave_search",
        "num_workers",
        "random_seed",
        "max_deterministic_time",
        "max_time_in_seconds",
        "share_linear2_bounds",
        "log_search_progress",
        "log_to_stdout",
    )
    missing = [name for name in required if not hasattr(solver.parameters, name)]
    if missing:
        raise RuntimeError(
            f"Installed OR-Tools {ortools.__version__} is missing SatParameters: {missing}"
        )


def apply_parameters(solver: cp_model.CpSolver, config: SolverConfig) -> None:
    _require_parameters(solver)
    params = solver.parameters
    params.interleave_search = config.interleave_search
    params.num_workers = config.num_workers
    params.random_seed = config.random_seed
    params.share_linear2_bounds = config.share_linear2_bounds
    params.log_search_progress = False
    params.log_to_stdout = False
    if config.mode == "reproducible":
        if config.max_deterministic_time is None:
            raise RuntimeError("Reproducible mode requires max_deterministic_time.")
        params.max_deterministic_time = float(config.max_deterministic_time)
    else:
        if config.max_time_in_seconds is None:
            raise RuntimeError("Fast mode requires max_time_in_seconds.")
        params.max_time_in_seconds = float(config.max_time_in_seconds)


def _as_integral(value: float, label: str) -> int:
    rounded = round(value)
    if abs(value - rounded) > 1e-6:
        raise RuntimeError(f"Solver {label} is not integral: {value}")
    return int(rounded)


def _lin_sum(terms: list[object]) -> object:
    if not terms:
        return 0
    total = terms[0]
    for term in terms[1:]:
        total = total + term  # type: ignore[operator]
    return total


def _assumptions_api_available() -> bool:
    return hasattr(cp_model.CpModel, "add_assumption") and hasattr(
        cp_model.CpSolver, "sufficient_assumptions_for_infeasibility"
    )


def _extract_conflict_groups(
    solver: cp_model.CpSolver,
    assumption_index: dict[int, str],
) -> tuple[str, ...]:
    if not assumption_index:
        return ()
    try:
        core = solver.sufficient_assumptions_for_infeasibility()
    except Exception:
        return ()
    groups = {
        assumption_index[literal]
        for literal in core
        if literal in assumption_index
    }
    return tuple(sorted(groups))


def _refine_conflict_groups(
    problem: Problem,
    config: SolverConfig,
    groups: tuple[str, ...],
) -> tuple[str, ...]:
    """Deletion filter over assumption groups. Still not a proven minimal IIS."""
    if len(groups) <= 1:
        return groups
    essential = list(groups)
    changed = True
    while changed and len(essential) > 1:
        changed = False
        for group in list(essential):
            trial = tuple(g for g in essential if g != group)
            if _groups_still_infeasible(problem, config, trial):
                essential = list(trial)
                changed = True
                break
    return tuple(sorted(essential))


def _groups_still_infeasible(
    problem: Problem,
    config: SolverConfig,
    active_groups: tuple[str, ...],
) -> bool:
    employees = tuple(sorted(problem.employees, key=lambda employee: employee.id))
    shifts = tuple(sorted(problem.shifts, key=lambda shift: (shift.start, shift.id)))
    ordered = replace(problem, employees=employees, shifts=shifts)
    model = cp_model.CpModel()
    model.name = "workforce-optimizer-core-refine"
    _allowed, pieces, _ = _build_model(
        model,
        ordered,
        use_assumptions=True,
        active_groups=set(active_groups),
    )
    if pieces:
        objective = pieces[0]
        for piece in pieces[1:]:
            objective = objective + piece  # type: ignore[operator]
        model.minimize(objective)
    else:
        model.minimize(0)
    solver = cp_model.CpSolver()
    apply_parameters(solver, config)
    status = solver.solve(model)
    return solver.status_name(status) == "INFEASIBLE"


def solve_problem(problem: Problem, config: SolverConfig) -> SolveResult:
    employees = tuple(sorted(problem.employees, key=lambda employee: employee.id))
    shifts = tuple(sorted(problem.shifts, key=lambda shift: (shift.start, shift.id)))
    ordered = replace(problem, employees=employees, shifts=shifts)
    model = cp_model.CpModel()
    model.name = "workforce-optimizer"
    use_assumptions = _assumptions_api_available()
    allowed, pieces, assumption_index = _build_model(model, ordered, use_assumptions=use_assumptions)
    if pieces:
        objective = pieces[0]
        for piece in pieces[1:]:
            objective = objective + piece  # type: ignore[operator]
        model.minimize(objective)
    else:
        model.minimize(0)

    solver = cp_model.CpSolver()
    apply_parameters(solver, config)
    status = solver.solve(model)
    name = solver.status_name(status)
    parameters = config.as_dict()
    runtime = float(solver.wall_time)
    if name == "MODEL_INVALID":
        return SolveResult(
            solver_status="UNKNOWN",
            objective=None,
            best_bound=None,
            runtime_seconds=runtime,
            assignments=(),
            parameters=parameters,
            error=f"CP-SAT rejected the model. {solver.response_stats()}",
            assumptions_available=use_assumptions,
        )
    if name not in SOLVER_STATUSES:
        return SolveResult(
            solver_status="UNKNOWN",
            objective=None,
            best_bound=None,
            runtime_seconds=runtime,
            assignments=(),
            parameters=parameters,
            error=f"Unexpected solver status {name}.",
            assumptions_available=use_assumptions,
        )
    if name not in {"OPTIMAL", "FEASIBLE"}:
        conflict_groups: tuple[str, ...] = ()
        if name == "INFEASIBLE" and use_assumptions:
            raw = _extract_conflict_groups(solver, assumption_index)
            conflict_groups = _refine_conflict_groups(ordered, config, raw)
        return SolveResult(
            solver_status=name,
            objective=None,
            best_bound=None,
            runtime_seconds=runtime,
            assignments=(),
            parameters=parameters,
            conflict_groups=conflict_groups,
            assumptions_available=use_assumptions,
        )
    assignments = tuple(
        sorted(
            (employee_id, shift_id)
            for (employee_id, shift_id), variable in allowed.items()
            if solver.value(variable) == 1
        )
    )
    return SolveResult(
        solver_status=name,
        objective=_as_integral(solver.objective_value, "objective"),
        best_bound=_as_integral(solver.best_objective_bound, "best bound"),
        runtime_seconds=runtime,
        assignments=assignments,
        parameters=parameters,
        assumptions_available=use_assumptions,
    )


def _group_literal(
    model: cp_model.CpModel,
    assumption_index: dict[int, str],
    group: str,
    *,
    use_assumptions: bool,
    active_groups: set[str] | None,
) -> tuple[cp_model.IntVar | None, bool]:
    """Return (assumption_literal, group_enabled).

    group_enabled False → skip this hard-constraint family (refinement).
    literal None + enabled True → unconditional hard constraint (no assumptions API).
    """
    if active_groups is not None and group not in active_groups:
        return None, False
    if not use_assumptions:
        return None, True
    literal = model.new_bool_var(f"assume_{group}")
    assumption_index[literal.Index()] = group
    model.add_assumption(literal)
    return literal, True


def _add_hard(
    model: cp_model.CpModel,
    constraint: object,
    literal: cp_model.IntVar | None,
    *,
    enabled: bool,
) -> None:
    if not enabled:
        return
    if literal is None:
        return
    constraint.only_enforce_if(literal)  # type: ignore[attr-defined]


def _build_model(
    model: cp_model.CpModel,
    problem: Problem,
    *,
    use_assumptions: bool = True,
    active_groups: set[str] | None = None,
) -> tuple[dict[tuple[int, int], cp_model.IntVar], list[object], dict[int, str]]:
    rules = problem.rules
    weights = rules.weights
    employees = problem.employees
    shifts = problem.shifts
    assumption_index: dict[int, str] = {}
    lit_kwargs = {"use_assumptions": use_assumptions, "active_groups": active_groups}
    assume_coverage, en_coverage = _group_literal(
        model, assumption_index, "coverage", **lit_kwargs
    )
    assume_skills, en_skills = _group_literal(
        model, assumption_index, "skill_requirements", **lit_kwargs
    )
    assume_rest, en_rest = _group_literal(model, assumption_index, "rest", **lit_kwargs)
    assume_weekly, en_weekly = _group_literal(
        model, assumption_index, "weekly_cap", **lit_kwargs
    )
    assume_consecutive, en_consecutive = _group_literal(
        model, assumption_index, "consecutive_days", **lit_kwargs
    )

    allowed: dict[tuple[int, int], cp_model.IntVar] = {}
    for employee in employees:
        for shift in shifts:
            if employee_block_reason(employee, shift, problem) is not None:
                continue
            allowed[employee.id, shift.id] = model.new_bool_var(f"x_{employee.id}_{shift.id}")

    shortfalls: list[object] = []
    for shift in shifts:
        present = [allowed[employee.id, shift.id] for employee in employees if (employee.id, shift.id) in allowed]
        headcount = _lin_sum(present)
        if rules.relaxed_understaffing:
            short = model.new_int_var(0, shift.required_count, f"short_{shift.id}")
            model.add(headcount + short >= shift.required_count)
            shortfalls.append(short)
        elif en_coverage:
            constraint = model.add(headcount >= shift.required_count)
            _add_hard(model, constraint, assume_coverage, enabled=True)
        for requirement_index, requirement in enumerate(shift.skill_requirements):
            qualified = [
                allowed[employee.id, shift.id]
                for employee in employees
                if (employee.id, shift.id) in allowed
                and any(skill_id in employee.skill_ids for skill_id in requirement.any_of_ids)
            ]
            qualified_sum = _lin_sum(qualified)
            if rules.relaxed_understaffing:
                skill_short = model.new_int_var(
                    0,
                    requirement.min_count,
                    f"skill_short_{shift.id}_{requirement_index}",
                )
                model.add(qualified_sum + skill_short >= requirement.min_count)
                shortfalls.append(skill_short)
            elif en_skills:
                constraint = model.add(qualified_sum >= requirement.min_count)
                _add_hard(model, constraint, assume_skills, enabled=True)

    for employee in employees:
        owned = [shift for shift in shifts if (employee.id, shift.id) in allowed]
        for index, left in enumerate(owned):
            for right in owned[index + 1 :]:
                if rest_conflict(left, right, rules.min_rest_hours) and en_rest:
                    constraint = model.add(
                        allowed[employee.id, left.id] + allowed[employee.id, right.id] <= 1
                    )
                    _add_hard(model, constraint, assume_rest, enabled=True)

    hour_hi = sum(shift.duration_hours for shift in shifts) + 1
    for employee in employees:
        by_week: dict[tuple[int, int], list[Shift]] = {}
        for shift in shifts:
            if (employee.id, shift.id) not in allowed:
                continue
            by_week.setdefault(week_key(shift.local_start_date), []).append(shift)
        prior_by_week: dict[tuple[int, int], int] = {}
        for prior in employee.prior_shifts:
            key = week_key(prior.local_start_date)
            prior_by_week[key] = prior_by_week.get(key, 0) + prior.hours
        for key in set(by_week) | set(prior_by_week):
            if not en_weekly:
                continue
            terms = [
                allowed[employee.id, shift.id] * shift.duration_hours for shift in by_week.get(key, [])
            ]
            prior_hours = prior_by_week.get(key, 0)
            if prior_hours > employee.weekly_hour_cap:
                for shift in by_week.get(key, []):
                    constraint = model.add(allowed[employee.id, shift.id] == 0)
                    _add_hard(model, constraint, assume_weekly, enabled=True)
                continue
            constraint = model.add(_lin_sum(terms) + prior_hours <= employee.weekly_hour_cap)
            _add_hard(model, constraint, assume_weekly, enabled=True)

    if rules.max_consecutive_days is not None and en_consecutive:
        dates = horizon_dates(problem)
        window = rules.max_consecutive_days + 1
        if len(dates) >= window:
            for employee in employees:
                prior_dates = {prior.local_start_date for prior in employee.prior_shifts}
                worked: dict = {}
                for day in dates:
                    iso = day.isoformat()
                    day_shifts = [
                        shift
                        for shift in shifts
                        if shift.local_start_date == iso and (employee.id, shift.id) in allowed
                    ]
                    if iso in prior_dates:
                        worked[day] = 1
                    elif not day_shifts:
                        worked[day] = 0
                    elif len(day_shifts) == 1:
                        worked[day] = allowed[employee.id, day_shifts[0].id]
                    else:
                        flag = model.new_bool_var(f"day_{employee.id}_{iso}")
                        model.add_max_equality(
                            flag,
                            *[allowed[employee.id, shift.id] for shift in day_shifts],
                        )
                        worked[day] = flag
                for start_index in range(len(dates) - window + 1):
                    chunk = dates[start_index : start_index + window]
                    constraint = model.add(
                        _lin_sum([worked[day] for day in chunk]) <= rules.max_consecutive_days
                    )
                    _add_hard(model, constraint, assume_consecutive, enabled=True)

    loads = []
    night_loads = []
    weekend_loads = []
    overtime_vars = []
    cost_terms = []
    preference_terms = []
    for employee in employees:
        hour_terms = [
            allowed[employee.id, shift.id] * shift.duration_hours
            for shift in shifts
            if (employee.id, shift.id) in allowed
        ]
        night_terms = [
            allowed[employee.id, shift.id]
            for shift in shifts
            if shift.is_night and (employee.id, shift.id) in allowed
        ]
        weekend_terms = [
            allowed[employee.id, shift.id]
            for shift in shifts
            if shift.is_weekend and (employee.id, shift.id) in allowed
        ]
        load = _lin_sum(hour_terms)
        loads.append(load)
        night_loads.append(_lin_sum(night_terms))
        weekend_loads.append(_lin_sum(weekend_terms))
        overtime = model.new_int_var(0, hour_hi, f"ot_{employee.id}")
        model.add(overtime >= load - rules.overtime_threshold_hours)
        model.add(overtime >= 0)
        overtime_vars.append(overtime)
        for shift in shifts:
            variable = allowed.get((employee.id, shift.id))
            if variable is None:
                continue
            cost_terms.append(variable * (employee.cost_per_hour * shift.duration_hours))
            points = preference_points(employee, shift)
            if points:
                preference_terms.append(variable * points)

    pieces: list[object] = []
    _add_weighted(pieces, weights.cost, cost_terms)
    _add_weighted(pieces, weights.preference, preference_terms)
    _add_weighted(pieces, weights.overtime, overtime_vars)
    _add_weighted(pieces, weights.understaff, shortfalls if rules.relaxed_understaffing else [])
    if employees:
        count = len(employees)
        dev_hi = count * hour_hi + 1
        _add_weighted(
            pieces,
            weights.fairness,
            _absolute_deviations(model, loads, count, dev_hi, "fair"),
        )
        _add_weighted(
            pieces,
            weights.night_imbalance,
            _absolute_deviations(model, night_loads, count, count * (len(shifts) + 1), "night"),
        )
        _add_weighted(
            pieces,
            weights.weekend_imbalance,
            _absolute_deviations(
                model,
                weekend_loads,
                count,
                count * (len(shifts) + 1),
                "weekend",
            ),
        )
    return allowed, pieces, assumption_index


def _add_weighted(pieces: list[object], weight: int, terms: list[object]) -> None:
    if weight == 0 or not terms:
        return
    pieces.append(weight * _lin_sum(terms))


def _absolute_deviations(
    model: cp_model.CpModel,
    loads: list[object],
    count: int,
    dev_hi: int,
    prefix: str,
) -> list[object]:
    total = _lin_sum(loads)
    deviations = []
    for index, load in enumerate(loads):
        deviation = model.new_int_var(0, max(dev_hi, 1), f"{prefix}_{index}")
        model.add(deviation >= count * load - total)
        model.add(deviation >= total - count * load)
        deviations.append(deviation)
    return deviations


def probe_relaxations(problem: Problem, config: SolverConfig) -> list[dict[str, object]]:
    if len(problem.employees) * max(len(problem.shifts), 1) > 4000:
        return [
            {
                "relaxed": ["skipped"],
                "solver_status": "UNKNOWN",
                "detail": "Problem is too large for interactive relaxation probes.",
            }
        ]
    variants: list[tuple[str, Problem]] = [
        ("skill_requirements", _clear_skills(problem)),
        ("coverage_and_skills", _clear_coverage(problem)),
        ("rest", _with_rules(problem, min_rest_hours=0)),
        ("availability_and_time_off", _clear_availability(problem)),
        ("weekly_cap_and_max_shift", _clear_caps(problem)),
        ("consecutive_days", _with_rules(problem, max_consecutive_days=None)),
    ]
    results = []
    for name, mutated in variants:
        outcome = solve_problem(mutated, config)
        results.append(
            {
                "relaxed": [name],
                "solver_status": outcome.solver_status,
                "error": outcome.error,
            }
        )
    return results


def diagnose(
    problem: Problem,
    config: SolverConfig,
    *,
    conflict_groups: tuple[str, ...] | list[str] | None = None,
    assumptions_available: bool | None = None,
) -> dict[str, object]:
    available = _assumptions_api_available() if assumptions_available is None else assumptions_available
    groups = list(conflict_groups) if conflict_groups is not None else []
    if conflict_groups is None and available:
        probe = solve_problem(problem, config)
        groups = list(probe.conflict_groups)
        available = probe.assumptions_available
    return explain(
        problem,
        probe_relaxations(problem, config),
        assumption_groups=groups,
        assumptions_available=available,
    )


def _with_rules(problem: Problem, **changes: object) -> Problem:
    return replace(problem, rules=replace(problem.rules, **changes))


def _clear_skills(problem: Problem) -> Problem:
    shifts = tuple(replace(shift, skill_requirements=()) for shift in problem.shifts)
    return replace(problem, shifts=shifts)


def _clear_coverage(problem: Problem) -> Problem:
    shifts = tuple(
        replace(shift, required_count=0, skill_requirements=()) for shift in problem.shifts
    )
    return replace(problem, shifts=shifts)


def _clear_caps(problem: Problem) -> Problem:
    employees = tuple(replace(employee, weekly_hour_cap=1000) for employee in problem.employees)
    return replace(
        problem,
        employees=employees,
        rules=replace(problem.rules, max_shift_hours=24),
    )


def _clear_availability(problem: Problem) -> Problem:
    if not problem.shifts:
        return problem
    start = min(shift.start for shift in problem.shifts) - timedelta(days=1)
    end = max(shift.end for shift in problem.shifts) + timedelta(days=1)
    employees = tuple(
        replace(employee, available=((start, end),), time_off=()) for employee in problem.employees
    )
    return replace(problem, employees=employees)

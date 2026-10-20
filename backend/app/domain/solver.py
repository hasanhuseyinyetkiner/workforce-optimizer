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


def solve_problem(problem: Problem, config: SolverConfig) -> SolveResult:
    employees = tuple(sorted(problem.employees, key=lambda employee: employee.id))
    shifts = tuple(sorted(problem.shifts, key=lambda shift: (shift.start, shift.id)))
    ordered = replace(problem, employees=employees, shifts=shifts)
    model = cp_model.CpModel()
    model.name = "workforce-optimizer"
    allowed, pieces = _build_model(model, ordered)
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
        )
    if name not in {"OPTIMAL", "FEASIBLE"}:
        return SolveResult(
            solver_status=name,
            objective=None,
            best_bound=None,
            runtime_seconds=runtime,
            assignments=(),
            parameters=parameters,
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
    )


def _build_model(
    model: cp_model.CpModel,
    problem: Problem,
) -> tuple[dict[tuple[int, int], cp_model.IntVar], list[object]]:
    rules = problem.rules
    weights = rules.weights
    employees = problem.employees
    shifts = problem.shifts
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
        else:
            model.add(headcount >= shift.required_count)
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
            else:
                model.add(qualified_sum >= requirement.min_count)

    for employee in employees:
        owned = [shift for shift in shifts if (employee.id, shift.id) in allowed]
        for index, left in enumerate(owned):
            for right in owned[index + 1 :]:
                if rest_conflict(left, right, rules.min_rest_hours):
                    model.add(
                        allowed[employee.id, left.id] + allowed[employee.id, right.id] <= 1
                    )

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
            terms = [
                allowed[employee.id, shift.id] * shift.duration_hours for shift in by_week.get(key, [])
            ]
            prior_hours = prior_by_week.get(key, 0)
            if prior_hours > employee.weekly_hour_cap:
                for shift in by_week.get(key, []):
                    model.add(allowed[employee.id, shift.id] == 0)
                continue
            model.add(_lin_sum(terms) + prior_hours <= employee.weekly_hour_cap)

    if rules.max_consecutive_days is not None:
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
                    model.add(_lin_sum([worked[day] for day in chunk]) <= rules.max_consecutive_days)

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
    return allowed, pieces


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


def diagnose(problem: Problem, config: SolverConfig) -> dict[str, object]:
    return explain(problem, probe_relaxations(problem, config))


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

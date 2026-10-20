"""Reproducible CP-SAT micro-benchmark for portfolio docs.

Size ladder (synthetic) plus shipped Northwind demo scenarios.
Prints hardware, params, candidate counts, status, objective/bound, wall time, validator.

Usage (from backend/):
  uv run python scripts/micro_benchmark.py
"""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import ortools

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.domain.eligibility import employee_block_reason  # noqa: E402
from app.domain.problem import Employee, Problem, Rules, Shift, Weights  # noqa: E402
from app.domain.scenario import load_scenario  # noqa: E402
from app.domain.solver import make_config, solve_problem  # noqa: E402
from app.domain.validator import validate_schedule  # noqa: E402

SEED = 1
WORKERS = 4
DET_SECONDS = 8.0


def _count_candidates(problem: Problem) -> int:
    return sum(
        1
        for employee in problem.employees
        for shift in problem.shifts
        if employee_block_reason(employee, shift, problem) is None
    )


def _weights_demo() -> Weights:
    return Weights(
        cost=1,
        preference=8,
        fairness=4,
        overtime=15,
        night_imbalance=3,
        weekend_imbalance=3,
        understaff=500,
    )


def _rules_demo() -> Rules:
    return Rules(
        name="micro-benchmark rules",
        min_rest_hours=8,
        max_shift_hours=12,
        max_consecutive_days=6,
        overtime_threshold_hours=40,
        relaxed_understaffing=False,
        weights=_weights_demo(),
    )


def _span(days: int = 21) -> tuple[tuple[datetime, datetime], ...]:
    start = datetime(2026, 11, 1, tzinfo=UTC)
    return ((start, start + timedelta(days=days)),)


def _employee(employee_id: int, *, cost: int | None = None) -> Employee:
    return Employee(
        id=employee_id,
        display_alias=f"Synth Emp {employee_id}",
        skill_ids=frozenset(),
        weekly_hour_cap=48,
        cost_per_hour=cost if cost is not None else 28 + (employee_id % 5) * 2,
        night_preference="prefer" if employee_id % 3 == 0 else "neutral",
        weekend_preference="avoid" if employee_id % 4 == 0 else "neutral",
        available=_span(),
        time_off=(),
    )


def _day_shifts(count: int, *, required: int = 1, hours: int = 8) -> tuple[Shift, ...]:
    """Non-overlapping day shifts starting 2026-11-02 12:00 UTC (≈ 07:00 ET)."""
    base = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    shifts: list[Shift] = []
    for index in range(1, count + 1):
        start = base + timedelta(days=index - 1)
        end = start + timedelta(hours=hours)
        local_date = start.date().isoformat()
        shifts.append(
            Shift(
                id=index,
                label=f"Day-{index}",
                start=start,
                end=end,
                local_start_date=local_date,
                start_local="07:00",
                end_local="15:00",
                overnight=False,
                required_count=required,
                skill_requirements=(),
                is_night=False,
                is_weekend=start.weekday() >= 5,
            )
        )
    return tuple(shifts)


def build_sized(name: str, n_employees: int, n_shifts: int, *, required: int = 1) -> Problem:
    return Problem(
        planning_timezone="UTC",
        organization_name=f"Micro-bench {name} (synthetic)",
        employees=tuple(_employee(i) for i in range(1, n_employees + 1)),
        shifts=_day_shifts(n_shifts, required=required),
        rules=_rules_demo(),
    )


def run_one(label: str, problem: Problem, *, seed: int = SEED) -> dict[str, object]:
    config = make_config(
        "reproducible",
        random_seed=seed,
        num_workers=WORKERS,
        deterministic_seconds=DET_SECONDS,
        fast_seconds=DET_SECONDS,
    )
    candidates = _count_candidates(problem)
    result = solve_problem(problem, config)
    validator = "n/a"
    if result.solver_status in {"OPTIMAL", "FEASIBLE"}:
        check = validate_schedule(problem, result.assignments)
        validator = "valid" if check.valid else f"invalid({len(check.violations)})"
    return {
        "label": label,
        "employees": len(problem.employees),
        "shifts": len(problem.shifts),
        "candidates": candidates,
        "seed": seed,
        "status": result.solver_status,
        "objective": result.objective,
        "bound": result.best_bound,
        "runtime_s": round(result.runtime_seconds, 4),
        "assignments": len(result.assignments),
        "validator": validator,
        "error": result.error,
        "assignment_tuple": result.assignments,
    }


def _print_row(row: dict[str, object]) -> None:
    obj = row["objective"] if row["objective"] is not None else "—"
    bound = row["bound"] if row["bound"] is not None else "—"
    print(
        f"{row['label']:<18} "
        f"{row['employees']:>3}×{row['shifts']:<3} "
        f"{row['candidates']:>6} "
        f"{row['seed']:>5} "
        f"{row['status']:<11} "
        f"{str(obj):>8} "
        f"{str(bound):>8} "
        f"{row['runtime_s']:>8} "
        f"{row['assignments']:>4} "
        f"{row['validator']}"
    )
    if row["error"]:
        print(f"  error: {row['error']}")


def main() -> None:
    print("=== Workforce Optimizer micro-benchmark ===")
    print(f"python: {sys.version.split()[0]}")
    print(f"ortools: {ortools.__version__}")
    print(f"platform: {platform.platform()}")
    print(f"processor: {platform.processor()}")
    print(f"mode: reproducible  num_workers={WORKERS}  max_deterministic_time={DET_SECONDS}")
    print()

    rows: list[dict[str, object]] = [
        run_one("tiny", build_sized("tiny", 3, 5, required=1)),
        run_one("small", build_sized("small", 5, 14, required=1)),
        run_one("demo-feasible", load_scenario("feasible").problem, seed=1),
        run_one("medium", build_sized("medium", 8, 14, required=2)),
        run_one("demo-infeasible", load_scenario("infeasible").problem),
        run_one("larger", build_sized("larger", 10, 20, required=2)),
    ]

    header = (
        f"{'instance':<18} {'E×S':>7} {'cand':>6} {'seed':>5} "
        f"{'status':<11} {'obj':>8} {'bound':>8} {'wall_s':>8} {'asg':>4} {'validator'}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        _print_row(row)

    demo = load_scenario("feasible").problem
    a = run_one("demo-repro-a", demo, seed=1)
    b = run_one("demo-repro-b", demo, seed=1)
    equal = a["assignment_tuple"] == b["assignment_tuple"] and a["objective"] == b["objective"]
    print()
    print(
        f"demo-feasible seed=1 consecutive equality "
        f"(assignments+objective): {equal}  objs={a['objective']},{b['objective']}"
    )


if __name__ == "__main__":
    main()

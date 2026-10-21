"""Correctness tests for time, the validator, and CP-SAT."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.domain.diagnostics import DIAGNOSTIC_NOTE, structural_findings
from app.domain.problem import BusyInterval, SkillRequirement, Weights
from app.domain.scenario import load_scenario
from app.domain.scoring import assignment_hash, score_schedule
from app.domain.solver import diagnose, make_config, solve_problem
from app.domain.timeutil import local_wall_to_utc
from app.domain.validator import validate_schedule
from tests.factories import employee, problem, rules, shift

ROOT = Path(__file__).resolve().parents[1]
CONFIG = make_config("reproducible", random_seed=1, num_workers=4, deterministic_seconds=8, fast_seconds=8)


def _solve(instance):
    return solve_problem(instance, CONFIG)


def _enumerate_best(instance):
    pairs = [(person.id, item.id) for person in instance.employees for item in instance.shifts]
    assert len(pairs) <= 12
    best_score = None
    best = None
    for mask in range(1 << len(pairs)):
        chosen = [pairs[index] for index in range(len(pairs)) if mask >> index & 1]
        if not validate_schedule(instance, chosen).valid:
            continue
        total = score_schedule(instance, chosen).total
        if best_score is None or total < best_score:
            best_score = total
            best = chosen
    return best_score, best


def test_ortools_parameters_match_installed_api():
    from ortools.sat.python import cp_model

    params = cp_model.CpSolver().parameters
    for name in (
        "interleave_search",
        "num_workers",
        "random_seed",
        "max_deterministic_time",
        "max_time_in_seconds",
    ):
        assert hasattr(params, name), name
    config = make_config("reproducible", random_seed=7, num_workers=4, deterministic_seconds=3, fast_seconds=9)
    assert config.interleave_search is True
    assert config.num_workers == 4
    assert config.random_seed == 7
    assert config.max_deterministic_time == 3
    assert config.max_time_in_seconds is None
    fast = make_config("fast", random_seed=7, num_workers=99, deterministic_seconds=3, fast_seconds=9)
    assert fast.interleave_search is False
    assert fast.num_workers == 4
    assert fast.max_time_in_seconds == 9
    assert fast.as_dict()["mode_label"] == "Fast · not reproducible"


def test_validator_module_does_not_import_ortools():
    for relative in (
        "app/domain/validator.py",
        "app/domain/scoring.py",
        "app/domain/eligibility.py",
        "app/domain/diagnostics.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "ortools" not in source


def test_dst_gap_and_overlap_are_rejected():
    with pytest.raises(Exception) as gap:
        local_wall_to_utc(datetime(2026, 3, 8, 2, 30), "America/New_York")
    assert gap.value.code == "nonexistent_local_time"
    with pytest.raises(Exception) as overlap:
        local_wall_to_utc(datetime(2026, 11, 1, 1, 30), "America/New_York")
    assert overlap.value.code == "ambiguous_local_time"
    utc = local_wall_to_utc(datetime(2026, 11, 2, 7, 0), "America/New_York")
    assert utc == datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def test_naive_datetime_rejected_by_type_decorator(tmp_path):
    from app.database import Base, UtcDateTime, make_engine
    from app.models import Organization
    from sqlalchemy.orm import Session

    engine = make_engine("sqlite:///" + (tmp_path / "clocks.db").as_posix())
    Base.metadata.create_all(engine)
    decorator = UtcDateTime()
    with pytest.raises(ValueError):
        decorator.process_bind_param(datetime(2026, 11, 2, 12, 0), engine.dialect)
    with Session(engine) as session:
        session.add(Organization(name="Synthetic", planning_timezone="UTC"))
        session.commit()
    from app.models import OptimizationRun

    with Session(engine) as session:
        row = OptimizationRun(
            status="QUEUED",
            mode="reproducible",
            random_seed=1,
            parameters={"mode": "reproducible"},
            label="clock",
            created_at=datetime(2026, 11, 2, 16, 0, tzinfo=UTC),
            heartbeat_at=datetime(2026, 11, 2, 12, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/New_York")),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.created_at == datetime(2026, 11, 2, 16, 0, tzinfo=UTC)
        assert row.heartbeat_at == datetime(2026, 11, 2, 17, 0, tzinfo=UTC)
        assert row.created_at.tzinfo is not None


def test_known_optimum_cheapest_employee():
    start = datetime(2026, 11, 2, 8, tzinfo=UTC)
    instance = problem(
        [employee(1, cost_per_hour=10), employee(2, cost_per_hour=50)],
        [shift(1, start)],
        rules(weights=Weights(cost=1, preference=0, fairness=0, overtime=0, night_imbalance=0, weekend_imbalance=0, understaff=0)),
    )
    expected, _ = _enumerate_best(instance)
    result = _solve(instance)
    assert result.solver_status == "OPTIMAL"
    assert result.objective == expected == 80
    assert result.assignments == ((1, 1),)
    assert validate_schedule(instance, list(result.assignments)).valid
    assert score_schedule(instance, list(result.assignments)).total == result.objective


def test_known_optimum_fairness_split():
    start = datetime(2026, 11, 2, 8, tzinfo=UTC)
    instance = problem(
        [employee(1, cost_per_hour=1), employee(2, cost_per_hour=1)],
        [shift(1, start, hours=4), shift(2, start + timedelta(hours=6), hours=4)],
        rules(
            min_rest_hours=1,
            weights=Weights(
                fairness=1,
                cost=1,
                preference=0,
                overtime=0,
                night_imbalance=0,
                weekend_imbalance=0,
                understaff=0,
            ),
        ),
    )
    expected, _ = _enumerate_best(instance)
    result = _solve(instance)
    assert result.solver_status == "OPTIMAL"
    assert result.objective == expected == 8
    assert validate_schedule(instance, list(result.assignments)).valid
    assert sorted(employee_id for employee_id, _shift_id in result.assignments) == [1, 2]


def test_known_optimum_required_skill():
    start = datetime(2026, 11, 2, 8, tzinfo=UTC)
    skilled = shift(
        1,
        start,
        skill_requirements=(SkillRequirement(any_of_ids=(7,), label="RN", min_count=1),),
    )
    instance = problem(
        [employee(1, cost_per_hour=20, skill_ids=frozenset({7})), employee(2, cost_per_hour=1)],
        [skilled],
        rules(weights=Weights(cost=1, preference=0, fairness=0, overtime=0, night_imbalance=0, weekend_imbalance=0, understaff=0)),
    )
    expected, _ = _enumerate_best(instance)
    result = _solve(instance)
    assert result.solver_status == "OPTIMAL"
    assert result.assignments == ((1, 1),)
    assert result.objective == expected == 160


def test_known_optimum_overnight_rest_and_preference():
    night = shift(
        1,
        datetime(2026, 11, 2, 23, tzinfo=UTC),
        label="Night",
        is_night=True,
    )
    day = shift(2, datetime(2026, 11, 3, 7, tzinfo=UTC), label="Day", is_night=False)
    instance = problem(
        [
            employee(1, cost_per_hour=1, night_preference="avoid"),
            employee(2, cost_per_hour=100),
        ],
        [night, day],
        rules(
            min_rest_hours=8,
            weights=Weights(cost=1, preference=100, fairness=0, overtime=0, night_imbalance=0, weekend_imbalance=0, understaff=0),
        ),
    )
    expected, _ = _enumerate_best(instance)
    result = _solve(instance)
    assert result.solver_status == "OPTIMAL"
    assert result.objective == expected == 808
    assert result.assignments == ((1, 2), (2, 1))
    blocked = problem(
        [employee(1, cost_per_hour=1)],
        [night, day],
        rules(min_rest_hours=8),
    )
    infeasible = _solve(blocked)
    assert infeasible.solver_status == "INFEASIBLE"
    assert infeasible.assignments == ()


def test_pto_blocks_only_the_employee_on_leave():
    start = datetime(2026, 11, 4, 8, tzinfo=UTC)
    item = shift(1, start)
    on_leave = employee(
        1,
        time_off=((start - timedelta(hours=1), start + timedelta(hours=10)),),
    )
    other = employee(2, cost_per_hour=5)
    instance = problem([on_leave, other], [item], rules(weights=Weights(cost=1)))
    result = _solve(instance)
    assert result.solver_status == "OPTIMAL"
    assert result.assignments == ((2, 1),)
    rejected = validate_schedule(instance, [(1, 1)])
    assert not rejected.valid
    assert rejected.violations[0].code == "time_off"
    only = problem([on_leave], [item])
    assert _solve(only).solver_status == "INFEASIBLE"


def test_no_qualified_employee_and_insufficient_staff():
    start = datetime(2026, 11, 3, 8, tzinfo=UTC)
    missing = shift(
        1,
        start,
        hours=4,
        label="Procedure",
        skill_requirements=(SkillRequirement(any_of_ids=(99,), label="CRNA", min_count=1),),
    )
    unqualified = problem([employee(1), employee(2)], [missing])
    result = _solve(unqualified)
    assert result.solver_status == "INFEASIBLE"
    assert result.assignments == ()
    codes = {item["code"] for item in structural_findings(unqualified)}
    assert "no_qualified_employee" in codes
    short = problem([employee(1), employee(2)], [shift(1, start, required_count=3)])
    assert _solve(short).solver_status == "INFEASIBLE"
    assert "insufficient_staff" in {item["code"] for item in structural_findings(short)}


def test_rest_violation_and_relaxation_note():
    start = datetime(2026, 11, 2, 8, tzinfo=UTC)
    instance = problem(
        [employee(1)],
        [shift(1, start, label="Day"), shift(2, start + timedelta(hours=8), label="Evening")],
        rules(min_rest_hours=11),
    )
    result = _solve(instance)
    assert result.solver_status == "INFEASIBLE"
    report = diagnose(instance, CONFIG)
    assert report["note"] == DIAGNOSTIC_NOTE
    assert "minimal unsatisfiable core" in report["note"]
    assert any(item["code"] == "rest_conflict" for item in report["findings"])
    rest = next(item for item in report["relaxations"] if item["relaxed"] == ["rest"])
    assert rest["solver_status"] in {"OPTIMAL", "FEASIBLE"}


def test_empty_input_is_optimal_and_demand_without_staff_is_infeasible():
    empty = problem([], [])
    result = _solve(empty)
    assert result.solver_status == "OPTIMAL"
    assert result.objective == 0
    assert result.assignments == ()
    assert validate_schedule(empty, []).valid
    demand = problem([], [shift(1, datetime(2026, 11, 2, 8, tzinfo=UTC))])
    assert _solve(demand).solver_status == "INFEASIBLE"


def test_relaxed_understaffing_is_labeled_and_optimal():
    start = datetime(2026, 11, 2, 8, tzinfo=UTC)
    instance = problem(
        [employee(1, cost_per_hour=0)],
        [shift(1, start, required_count=2)],
        rules(
            relaxed_understaffing=True,
            weights=Weights(understaff=10, cost=0, preference=0, fairness=0, overtime=0, night_imbalance=0, weekend_imbalance=0),
        ),
    )
    expected, _ = _enumerate_best(instance)
    result = _solve(instance)
    assert result.solver_status == "OPTIMAL"
    assert result.assignments == ((1, 1),)
    assert result.objective == expected == 10
    assert validate_schedule(instance, list(result.assignments)).valid


def test_demo_reproducible_ten_times_and_validator_accepts():
    instance = load_scenario("feasible").problem
    hashes = []
    objective = None
    for _ in range(10):
        result = _solve(instance)
        assert result.solver_status in {"OPTIMAL", "FEASIBLE"}
        assert result.assignments
        assert validate_schedule(instance, list(result.assignments)).valid
        assert score_schedule(instance, list(result.assignments)).total == result.objective
        hashes.append(assignment_hash(list(result.assignments)))
        objective = result.objective
    assert len(set(hashes)) == 1
    assert objective is not None
    stored = result.parameters
    assert stored["interleave_search"] is True
    assert stored["num_workers"] == 4
    assert stored["random_seed"] == 1
    assert stored["max_deterministic_time"] == 8
    assert stored["max_time_in_seconds"] is None
    assert stored["mode_label"] == "Reproducible"


def test_infeasible_demo_has_diagnostics_and_no_assignments():
    instance = load_scenario("infeasible").problem
    result = _solve(instance)
    assert result.solver_status == "INFEASIBLE"
    assert result.assignments == ()
    assert result.assumptions_available is True
    assert "skill_requirements" in result.conflict_groups
    report = diagnose(
        instance,
        CONFIG,
        conflict_groups=result.conflict_groups,
        assumptions_available=result.assumptions_available,
    )
    assert report["note"] == DIAGNOSTIC_NOTE
    assert report["assumptions_available"] is True
    assert report["unsat_core_kind"] == "constraint_group_assumptions"
    assert any(item["group"] == "skill_requirements" for item in report["conflict_groups"])
    assert any(item["code"] == "no_qualified_employee" and item["skill"] == "CRNA" for item in report["findings"])
    relaxed = next(item for item in report["relaxations"] if item["relaxed"] == ["skill_requirements"])
    assert relaxed["solver_status"] in {"OPTIMAL", "FEASIBLE"}


def test_optimal_scenario_is_optimal():
    instance = load_scenario("optimal").problem
    result = _solve(instance)
    assert result.solver_status == "OPTIMAL"
    assert result.objective is not None
    assert result.best_bound == result.objective
    assert result.assignments


def test_objective_breakdown_components_match_scorer_golden():
    """Each soft component from score_schedule must sum to the solver objective."""
    start = datetime(2026, 11, 2, 8, tzinfo=UTC)
    night = shift(1, datetime(2026, 11, 2, 22, tzinfo=UTC), label="Night", is_night=True, is_weekend=False)
    day = shift(2, start + timedelta(days=1), label="Day", is_night=False, is_weekend=False)
    weekend = shift(
        3,
        datetime(2026, 11, 7, 8, tzinfo=UTC),  # Saturday
        label="Weekend",
        is_night=False,
        is_weekend=True,
    )
    instance = problem(
        [
            employee(1, cost_per_hour=10, night_preference="avoid", weekend_preference="avoid"),
            employee(2, cost_per_hour=12, night_preference="prefer", weekend_preference="prefer"),
        ],
        [night, day, weekend],
        rules(
            min_rest_hours=1,
            overtime_threshold_hours=8,
            weights=Weights(
                cost=1,
                preference=5,
                fairness=2,
                overtime=3,
                night_imbalance=4,
                weekend_imbalance=4,
                understaff=0,
            ),
        ),
    )
    expected_total, best = _enumerate_best(instance)
    result = _solve(instance)
    assert result.solver_status == "OPTIMAL"
    assert result.objective == expected_total
    breakdown = score_schedule(instance, list(result.assignments))
    assert breakdown.as_dict() == {
        "cost": breakdown.cost,
        "preference": breakdown.preference,
        "fairness": breakdown.fairness,
        "overtime": breakdown.overtime,
        "night_imbalance": breakdown.night_imbalance,
        "weekend_imbalance": breakdown.weekend_imbalance,
        "understaff": breakdown.understaff,
        "total": breakdown.total,
    }
    assert breakdown.total == result.objective
    assert sum(
        [
            breakdown.cost,
            breakdown.preference,
            breakdown.fairness,
            breakdown.overtime,
            breakdown.night_imbalance,
            breakdown.weekend_imbalance,
            breakdown.understaff,
        ]
    ) == result.objective
    # Golden component map for the known optimum (enumerate-checked).
    golden = score_schedule(instance, best)
    assert breakdown.as_dict() == golden.as_dict()
    assert breakdown.cost > 0
    assert breakdown.preference >= 0


def test_demo_feasible_breakdown_matches_solver_objective():
    instance = load_scenario("feasible").problem
    result = _solve(instance)
    assert result.solver_status in {"OPTIMAL", "FEASIBLE"}
    breakdown = score_schedule(instance, list(result.assignments))
    assert breakdown.total == result.objective
    assert breakdown.as_dict()["total"] == result.objective
    for key in ("cost", "preference", "fairness", "overtime", "night_imbalance", "weekend_imbalance", "understaff"):
        assert key in breakdown.as_dict()
        assert isinstance(breakdown.as_dict()[key], int)


def test_time_limit_can_return_unknown_without_assignments():
    """Fast mode with a tiny wall budget must not invent a successful roster on UNKNOWN."""
    instance = load_scenario("feasible").problem
    tight = make_config(
        "fast",
        random_seed=1,
        num_workers=1,
        deterministic_seconds=8,
        fast_seconds=1e-9,
    )
    result = solve_problem(instance, tight)
    # Tiny budgets usually yield UNKNOWN; if the solver still proves FEASIBLE/OPTIMAL
    # instantly, that is also honest — but then assignments must validate.
    assert result.solver_status in {"UNKNOWN", "FEASIBLE", "OPTIMAL", "INFEASIBLE"}
    if result.solver_status == "UNKNOWN":
        assert result.assignments == ()
        assert result.objective is None
    elif result.solver_status in {"OPTIMAL", "FEASIBLE"}:
        assert validate_schedule(instance, list(result.assignments)).valid
        assert score_schedule(instance, list(result.assignments)).total == result.objective
    else:
        assert result.assignments == ()


def test_prior_shifts_lock_weekly_cap_explains_infeasibility():
    """Prior (locked) hours in the same ISO week fill the weekly cap → INFEASIBLE."""
    monday = datetime(2026, 11, 2, 8, tzinfo=UTC)
    # Rest interval is last week (no prior_conflict); hours roll into Monday's ISO week.
    prior = BusyInterval(
        start=monday - timedelta(days=7),
        end=monday - timedelta(days=7) + timedelta(hours=8),
        local_start_date=monday.date().isoformat(),
        hours=40,
    )
    instance = problem(
        [employee(1, weekly_hour_cap=40, prior_shifts=(prior,))],
        [shift(1, monday + timedelta(days=1), hours=8)],
        rules(min_rest_hours=1, weights=Weights(cost=1)),
    )
    result = _solve(instance)
    assert result.solver_status == "INFEASIBLE"
    assert result.assignments == ()
    report = diagnose(
        instance,
        CONFIG,
        conflict_groups=result.conflict_groups,
        assumptions_available=result.assumptions_available,
    )
    assert report["note"] == DIAGNOSTIC_NOTE
    assert "Not a proven minimal unsatisfiable core" in report["note"]
    groups = {item["group"] for item in report["conflict_groups"]}
    assert "weekly_cap" in groups or any(
        item["relaxed"] == ["weekly_cap_and_max_shift"] and item["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        for item in report["relaxations"]
    )


def test_hard_constraint_violation_never_returned_as_success():
    """Validator rejects fabricated illegal assignments; solver never publishes them."""
    start = datetime(2026, 11, 2, 8, tzinfo=UTC)
    instance = problem(
        [employee(1)],
        [shift(1, start), shift(2, start + timedelta(hours=8))],
        rules(min_rest_hours=11),
    )
    result = _solve(instance)
    assert result.solver_status == "INFEASIBLE"
    assert result.assignments == ()
    forged = validate_schedule(instance, [(1, 1), (1, 2)])
    assert not forged.valid
    assert forged.violations  # any hard-code rejection is enough; must not be Valid

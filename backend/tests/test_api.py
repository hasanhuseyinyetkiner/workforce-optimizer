"""API, persistence, and solve-orchestration tests."""

from __future__ import annotations

import os
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from app.domain.solver import SolveResult
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def database_url(tmp_path_factory):
    env = os.environ.get("POSTGRES_TEST_URL")
    if env:
        url = env
    else:
        url = "sqlite:///" + (tmp_path_factory.mktemp("db") / "test.db").as_posix()
    os.environ["DATABASE_URL"] = url
    os.environ["APP_ENV"] = "test"
    os.environ["HOST"] = "127.0.0.1"
    from app.config import get_settings
    from app.database import reset_engine, run_migrations

    get_settings.cache_clear()
    reset_engine()
    run_migrations(url)
    return url


def _await_idle_solves(timeout_seconds: float = 90.0) -> None:
    from app.database import get_sessionmaker
    from app.models import OptimizationRun
    from sqlalchemy import select

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        session = get_sessionmaker()()
        try:
            active = session.scalars(
                select(OptimizationRun.id).where(OptimizationRun.status.in_(("QUEUED", "RUNNING")))
            ).all()
            if not active:
                return
        finally:
            session.close()
        time.sleep(0.1)


@pytest.fixture
def client(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("ALLOW_NETWORK_BIND", "false")
    monkeypatch.setenv("SOLVER_DETERMINISTIC_TIME_SECONDS", "8")
    from app.config import get_settings
    from app.database import get_sessionmaker, reset_engine
    from app.main import create_app
    from app.services.seed import wipe_domain

    get_settings.cache_clear()
    reset_engine()
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
        _await_idle_solves()
        session = get_sessionmaker()()
        try:
            wipe_domain(session)
            session.commit()
        finally:
            session.close()
    reset_engine()
    get_settings.cache_clear()


def _wait_run(client: TestClient, run_id: int, *, timeout_seconds: float = 90.0) -> dict:
    body = {}
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        body = client.get(f"/api/optimization-runs/{run_id}").json()
        if body["status"] in {"SUCCEEDED", "FAILED"}:
            return body
        time.sleep(0.1)
    return body


def test_bind_policy_refuses_public_host():
    from app.config import Settings, enforce_bind_policy

    with pytest.raises(RuntimeError):
        enforce_bind_policy(Settings(host="0.0.0.0", allow_network_bind=False))
    enforce_bind_policy(Settings(host="0.0.0.0", allow_network_bind=True))
    enforce_bind_policy(Settings(host="127.0.0.1", allow_network_bind=False))


def test_health_ready_and_dst_rejection(client: TestClient):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] == "ready"
    created = client.post(
        "/api/shifts",
        json={
            "local_date": "2026-11-02",
            "start_local": "07:00",
            "end_local": "15:00",
            "required_count": 1,
            "label": "Day",
            "skill_requirements": [],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["start_utc"].startswith("2026-11-02T12:00:00")
    gap = client.post(
        "/api/shifts",
        json={
            "local_date": "2026-03-08",
            "start_local": "02:30",
            "end_local": "06:30",
            "required_count": 1,
            "label": "Gap",
        },
    )
    assert gap.status_code == 422
    assert gap.json()["detail"]["code"] == "nonexistent_local_time"
    ambiguous = client.post(
        "/api/shifts",
        json={
            "local_date": "2026-11-01",
            "start_local": "01:30",
            "end_local": "05:30",
            "required_count": 1,
            "label": "Fold",
        },
    )
    assert ambiguous.status_code == 422
    assert ambiguous.json()["detail"]["code"] == "ambiguous_local_time"


def test_demo_solve_validate_and_export(client: TestClient):
    loaded = client.post("/api/demo/load", json={"scenario": "feasible"})
    assert loaded.status_code == 200
    assert loaded.json()["employees"] == 5
    assert loaded.json()["shifts"] == 21
    created = client.post(
        "/api/optimization-runs",
        json={"mode": "reproducible", "random_seed": 1, "label": "demo"},
    )
    assert created.status_code == 201
    first = _wait_run(client, created.json()["id"])
    assert first["status"] == "SUCCEEDED", first
    assert first["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    assert first["schedule_id"]
    assert first["parameters"]["interleave_search"] is True
    assert first["parameters"]["num_workers"] == 4
    assert first["parameters"]["max_time_in_seconds"] is None
    assert first["mode_label"] == "Reproducible"
    schedule = client.get(f"/api/schedules/{first['schedule_id']}")
    assert schedule.status_code == 200
    body = schedule.json()
    assert body["validation"]["valid"] is True
    assert body["kpis"]["scheduled_hours"] > 0
    assert body["objective_breakdown"]["total"] == body["objective"]
    assert any(row["display_alias"] == "Avery Quinn" for row in body["employee_hours"])
    checked = client.post(f"/api/schedules/{first['schedule_id']}/validate")
    assert checked.json()["valid"] is True
    csv_body = client.get(f"/api/schedules/{first['schedule_id']}/export.csv").text
    assert "employee_alias" in csv_body
    assert "Avery Quinn" in csv_body
    ics = client.get(f"/api/schedules/{first['schedule_id']}/export.ics").text
    assert "BEGIN:VCALENDAR" in ics
    assert "DTSTART:" in ics
    again = client.post("/api/optimization-runs", json={"mode": "reproducible", "random_seed": 1})
    second = _wait_run(client, again.json()["id"])
    second_schedule = client.get(f"/api/schedules/{second['schedule_id']}").json()
    assert sorted(
        (row["employee_id"], row["shift_id"]) for row in body["assignments"]
    ) == sorted((row["employee_id"], row["shift_id"]) for row in second_schedule["assignments"])


def test_schedule_compare_diffs_objectives_and_assignments(client: TestClient):
    client.post("/api/demo/load", json={"scenario": "feasible"})
    first = _wait_run(
        client,
        client.post(
            "/api/optimization-runs",
            json={"mode": "reproducible", "random_seed": 1, "label": "baseline"},
        ).json()["id"],
    )
    assert first["schedule_id"]
    rules = client.get("/api/rulesets/active").json()
    weights = dict(rules["weights"])
    weights["preference"] = int(weights.get("preference", 1)) + 50
    saved = client.post(
        "/api/rulesets",
        json={
            "name": "Preference heavy",
            "min_rest_hours": rules["min_rest_hours"],
            "max_shift_hours": rules["max_shift_hours"],
            "max_consecutive_days": rules["max_consecutive_days"],
            "overtime_threshold_hours": rules["overtime_threshold_hours"],
            "relaxed_understaffing": rules["relaxed_understaffing"],
            "weights": weights,
        },
    )
    assert saved.status_code == 201
    second = _wait_run(
        client,
        client.post(
            "/api/optimization-runs",
            json={"mode": "reproducible", "random_seed": 1, "label": "pref-heavy"},
        ).json()["id"],
    )
    assert second["schedule_id"]
    listed = client.get("/api/schedules")
    assert listed.status_code == 200
    assert len(listed.json()) >= 2
    compared = client.get(
        f"/api/schedules/compare?left_id={first['schedule_id']}&right_id={second['schedule_id']}"
    )
    assert compared.status_code == 200, compared.text
    body = compared.json()
    assert body["left"]["id"] == first["schedule_id"]
    assert body["right"]["id"] == second["schedule_id"]
    assert "total" in body["objective_delta"]
    assert body["rules_match"] is False
    assert "shared_count" in body["assignment_diff"]


def test_infeasible_demo_stores_no_schedule(client: TestClient):
    client.post("/api/demo/load", json={"scenario": "infeasible"})
    created = client.post("/api/optimization-runs", json={"mode": "reproducible", "random_seed": 1})
    body = _wait_run(client, created.json()["id"])
    assert body["status"] == "SUCCEEDED"
    assert body["solver_status"] == "INFEASIBLE"
    assert body["schedule_id"] is None
    assert "proven minimal unsatisfiable core" in body["diagnostics"]["note"].lower()
    assert body["diagnostics"]["assumptions_available"] is True
    assert any(item["group"] == "skill_requirements" for item in body["diagnostics"]["conflict_groups"])
    assert any(item["code"] == "no_qualified_employee" for item in body["diagnostics"]["findings"])
    missing = client.get("/api/schedules/latest")
    assert missing.status_code == 404


def test_health_while_solve_is_running(client: TestClient, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def slow_solve(problem, config):
        entered.set()
        assert release.wait(5)
        return SolveResult(
            solver_status="OPTIMAL",
            objective=0,
            best_bound=0,
            runtime_seconds=0.01,
            assignments=(),
            parameters=config.as_dict(),
        )

    monkeypatch.setattr("app.services.runs.solve_problem", slow_solve)
    created = client.post("/api/optimization-runs", json={"mode": "reproducible", "random_seed": 1})
    assert created.status_code == 201
    assert entered.wait(3)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    conflict = client.post("/api/optimization-runs", json={"mode": "fast", "random_seed": 2})
    assert conflict.status_code == 409
    release.set()
    finished = _wait_run(client, created.json()["id"])
    assert finished["status"] == "SUCCEEDED"
    assert finished["solver_status"] == "OPTIMAL"


def test_stale_running_run_is_reaped(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "test")
    from app.config import get_settings
    from app.database import get_sessionmaker, reset_engine
    from app.models import OptimizationRun
    from app.services.runs import reap_stale_runs
    from app.services.seed import wipe_domain
    from sqlalchemy import select

    get_settings.cache_clear()
    reset_engine()
    session = get_sessionmaker()()
    try:
        wipe_domain(session)
        old = datetime.now(UTC) - timedelta(minutes=10)
        session.add(
            OptimizationRun(
                status="RUNNING",
                mode="reproducible",
                random_seed=1,
                parameters={"mode": "reproducible"},
                label="stale",
                created_at=old,
                started_at=old,
                heartbeat_at=old,
            )
        )
        session.commit()
        assert reap_stale_runs(session, timedelta(seconds=30)) == 1
        session.commit()
        row = session.scalars(select(OptimizationRun)).one()
        assert row.status == "FAILED"
        assert "Stale run reaped" in (row.error_message or "")
    finally:
        wipe_domain(session)
        session.commit()
        session.close()
        reset_engine()
        get_settings.cache_clear()


def test_employee_shift_and_rules_crud(client: TestClient):
    created = client.post(
        "/api/employees",
        json={
            "display_alias": "River Hale",
            "weekly_hour_cap": 36,
            "cost_per_hour": 30,
            "night_preference": "avoid",
            "skill_names": ["RN"],
        },
    )
    assert created.status_code == 201
    employee_id = created.json()["id"]
    assert created.json()["skills"] == ["RN"]
    listed = client.get("/api/employees")
    assert any(row["display_alias"] == "River Hale" for row in listed.json())
    rules = client.post(
        "/api/rulesets",
        json={
            "name": "Edited rules",
            "min_rest_hours": 10,
            "max_shift_hours": 12,
            "max_consecutive_days": 5,
            "overtime_threshold_hours": 36,
            "relaxed_understaffing": False,
            "weights": {
                "cost": 1,
                "preference": 2,
                "fairness": 3,
                "overtime": 4,
                "night_imbalance": 0,
                "weekend_imbalance": 0,
                "understaff": 9,
            },
        },
    )
    assert rules.status_code == 201
    assert client.get("/api/rulesets/active").json()["min_rest_hours"] == 10
    template = client.post(
        "/api/shift-templates",
        json={"name": "Day", "start_local": "07:00", "end_local": "15:00"},
    )
    assert template.status_code == 201
    client.delete(f"/api/employees/{employee_id}")
    assert client.get("/api/employees").json() == []


@pytest.mark.postgres
def test_utc_roundtrip_postgres():
    url = os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_URL not set")
    from app.database import make_engine, run_migrations
    from app.models import OptimizationRun
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    run_migrations(url)
    engine = make_engine(url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM optimization_runs"))
    with Session(engine) as session:
        row = OptimizationRun(
            status="QUEUED",
            mode="reproducible",
            random_seed=1,
            parameters={"mode": "reproducible"},
            label="pg",
            created_at=datetime(2026, 11, 2, 15, 30, tzinfo=UTC),
            heartbeat_at=datetime(2026, 11, 2, 11, 30, tzinfo=__import__("zoneinfo").ZoneInfo("America/New_York")),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.created_at == datetime(2026, 11, 2, 15, 30, tzinfo=UTC)
        assert row.heartbeat_at.tzinfo is not None
        assert row.heartbeat_at == datetime(2026, 11, 2, 16, 30, tzinfo=UTC)
        session.delete(row)
        session.commit()
    engine.dispose()

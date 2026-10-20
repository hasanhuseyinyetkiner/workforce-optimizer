"""Run CP-SAT off the request thread and persist status, heartbeat, and results."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_sessionmaker
from app.domain.diagnostics import DIAGNOSTIC_NOTE
from app.domain.scoring import score_schedule
from app.domain.solver import diagnose, make_config, solve_problem
from app.domain.validator import validate_schedule
from app.models import Assignment, OptimizationRun, ScheduleVersion
from app.services.problem_builder import active_ruleset, build_problem

logger = logging.getLogger(__name__)


class ConflictError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def reap_stale_runs(session: Session, stale_after: timedelta) -> int:
    cutoff = datetime.now(UTC) - stale_after
    rows = session.scalars(
        select(OptimizationRun).where(
            OptimizationRun.status == "RUNNING",
            or_(OptimizationRun.heartbeat_at.is_(None), OptimizationRun.heartbeat_at < cutoff),
        )
    ).all()
    now = datetime.now(UTC)
    for run in rows:
        run.status = "FAILED"
        run.solver_status = None
        run.error_message = "Stale run reaped: no heartbeat before the deadline."
        run.finished_at = now
    return len(rows)


def launch_run(session: Session, *, mode: str, random_seed: int, label: str) -> OptimizationRun:
    active = session.scalar(
        select(OptimizationRun.id).where(OptimizationRun.status.in_(("QUEUED", "RUNNING")))
    )
    if active is not None:
        raise ConflictError("A solve is already running.")
    settings = get_settings()
    config = make_config(
        mode,
        random_seed=random_seed,
        num_workers=settings.solver_num_workers,
        deterministic_seconds=settings.solver_deterministic_time_seconds,
        fast_seconds=settings.solver_fast_time_seconds,
    )
    now = datetime.now(UTC)
    rules = active_ruleset(session)
    run = OptimizationRun(
        status="QUEUED",
        solver_status=None,
        mode=mode,
        random_seed=random_seed,
        parameters=config.as_dict(),
        label=label,
        created_at=now,
        heartbeat_at=now,
        ruleset_id=rules.id if rules is not None else None,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def start_solve_thread(run_id: int) -> None:
    thread = threading.Thread(target=execute_run, args=(run_id,), name=f"solve-{run_id}", daemon=True)
    thread.start()


def execute_run(run_id: int) -> None:
    session_factory = get_sessionmaker()
    session = session_factory()
    try:
        run = session.get(OptimizationRun, run_id)
        if run is None:
            return
        now = datetime.now(UTC)
        run.status = "RUNNING"
        run.started_at = now
        run.heartbeat_at = now
        session.commit()
        config = make_config(
            run.mode,
            random_seed=run.random_seed,
            num_workers=int(run.parameters.get("num_workers", 1)),
            deterministic_seconds=float(run.parameters.get("max_deterministic_time") or 10),
            fast_seconds=float(run.parameters.get("max_time_in_seconds") or 10),
        )
        problem = build_problem(session)
        session.close()
        session = None

        stop = threading.Event()

        def beat() -> None:
            while not stop.wait(2):
                heartbeat = session_factory()
                try:
                    row = heartbeat.get(OptimizationRun, run_id)
                    if row is None or row.status != "RUNNING":
                        return
                    row.heartbeat_at = datetime.now(UTC)
                    heartbeat.commit()
                except Exception:
                    logger.exception("heartbeat failed for run %s", run_id)
                finally:
                    heartbeat.close()

        beater = threading.Thread(target=beat, name=f"heartbeat-{run_id}", daemon=True)
        beater.start()
        try:
            outcome = solve_problem(problem, config)
            validation = None
            breakdown = None
            report = None
            publish = False
            error = outcome.error
            if outcome.solver_status == "INFEASIBLE":
                report = diagnose(problem, config)
            elif outcome.solver_status in {"OPTIMAL", "FEASIBLE"}:
                validation = validate_schedule(problem, list(outcome.assignments))
                breakdown = score_schedule(problem, list(outcome.assignments))
                if not validation.valid:
                    error = "Independent validator rejected the solver assignment. No schedule was stored."
                elif breakdown.total != outcome.objective:
                    error = (
                        "Solver objective "
                        f"{outcome.objective} did not match the independent scorer {breakdown.total}. "
                        "No schedule was stored."
                    )
                else:
                    publish = True
            elif outcome.solver_status == "UNKNOWN" and error is None:
                report = {
                    "note": DIAGNOSTIC_NOTE,
                    "findings": [
                        {
                            "code": "unknown",
                            "message": (
                                "The solver stopped without a proven feasible schedule. "
                                "No assignments were stored."
                            ),
                        }
                    ],
                    "relaxations": [],
                }
        finally:
            stop.set()
            beater.join(timeout=2)

        session = session_factory()
        run = session.get(OptimizationRun, run_id)
        if run is None:
            return
        finished = datetime.now(UTC)
        run.parameters = outcome.parameters
        run.runtime_seconds = outcome.runtime_seconds
        run.finished_at = finished
        run.heartbeat_at = finished
        run.solver_status = outcome.solver_status
        if error:
            run.status = "FAILED"
            run.error_message = error
            run.objective = outcome.objective
            run.best_bound = outcome.best_bound
            if validation is not None:
                run.diagnostics = {
                    "note": "The independent validator rejected the solver output.",
                    "findings": [item.as_dict() for item in validation.violations],
                    "relaxations": [],
                }
        else:
            run.status = "SUCCEEDED"
            run.error_message = None
            run.objective = outcome.objective
            run.best_bound = outcome.best_bound
            run.diagnostics = report
            if breakdown is not None:
                run.objective_breakdown = breakdown.as_dict()
            if publish and validation is not None and breakdown is not None:
                schedule = ScheduleVersion(
                    optimization_run_id=run.id,
                    created_at=finished,
                    validation=validation.as_dict(),
                )
                session.add(schedule)
                session.flush()
                for employee_id, shift_id in outcome.assignments:
                    session.add(
                        Assignment(
                            schedule_version_id=schedule.id,
                            employee_id=employee_id,
                            shift_instance_id=shift_id,
                        )
                    )
        session.commit()
    except Exception as exc:
        logger.exception("solve failed for run %s", run_id)
        if session is None:
            session = session_factory()
        run = session.get(OptimizationRun, run_id)
        if run is not None and run.status != "SUCCEEDED":
            run.status = "FAILED"
            run.error_message = str(exc)
            run.finished_at = datetime.now(UTC)
            run.heartbeat_at = run.finished_at
            session.commit()
    finally:
        if session is not None:
            session.close()

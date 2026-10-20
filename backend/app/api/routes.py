"""HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Employee, OptimizationRun, ScheduleVersion, ShiftInstance, ShiftTemplate, Skill
from app.schemas import DemoIn, EmployeeIn, EmployeePatch, RulesIn, RunIn, ShiftIn, TemplateIn, TimeOffIn
from app.services.catalog import (
    add_time_off,
    create_employee,
    create_shift,
    create_template,
    delete_employee,
    delete_shift,
    get_organization,
    save_rules,
    update_employee,
)
from app.services.problem_builder import active_ruleset
from app.services.runs import ConflictError, launch_run, start_solve_thread
from app.services.seed import load_scenario_into_db
from app.services.serialize import (
    employee_dict,
    overview_dict,
    rules_dict,
    run_dict,
    schedule_csv,
    schedule_dict,
    schedule_ics,
    shift_dict,
    template_dict,
    time_off_dict,
)

router = APIRouter()


def get_db():
    from app.database import get_sessionmaker

    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def _timezone(session: Session) -> str:
    return get_organization(session).planning_timezone


@router.get("/health")
def health() -> dict:
    from app.config import get_settings

    settings = get_settings()
    return {
        "status": "ok",
        "demo": settings.app_env == "demo",
        "synthetic_data": settings.app_env == "demo",
    }


@router.get("/ready")
def ready(session: Session = Depends(get_db)) -> dict:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/api/overview")
def overview(session: Session = Depends(get_db)) -> dict:
    from app.config import get_settings

    return overview_dict(session, demo=get_settings().app_env == "demo")


@router.get("/api/employees")
def list_employees(session: Session = Depends(get_db)) -> list[dict]:
    timezone_name = _timezone(session)
    rows = session.scalars(select(Employee).order_by(Employee.display_alias)).all()
    return [employee_dict(row, timezone_name) for row in rows]


@router.post("/api/employees", status_code=201)
def post_employee(payload: EmployeeIn, session: Session = Depends(get_db)) -> dict:
    row = create_employee(session, payload.model_dump())
    return employee_dict(row, _timezone(session))


@router.patch("/api/employees/{employee_id}")
def patch_employee(employee_id: int, payload: EmployeePatch, session: Session = Depends(get_db)) -> dict:
    row = update_employee(session, employee_id, payload.model_dump(exclude_unset=True))
    return employee_dict(row, _timezone(session))


@router.delete("/api/employees/{employee_id}", status_code=204)
def remove_employee(employee_id: int, session: Session = Depends(get_db)) -> None:
    delete_employee(session, employee_id)


@router.post("/api/employees/{employee_id}/time-off", status_code=201)
def post_time_off(employee_id: int, payload: TimeOffIn, session: Session = Depends(get_db)) -> dict:
    item = add_time_off(session, employee_id, payload.model_dump())
    return time_off_dict(item, _timezone(session))


@router.get("/api/skills")
def list_skills(session: Session = Depends(get_db)) -> list[dict]:
    rows = session.scalars(select(Skill).order_by(Skill.name)).all()
    return [{"id": row.id, "name": row.name} for row in rows]


@router.get("/api/shift-templates")
def list_templates(session: Session = Depends(get_db)) -> list[dict]:
    rows = session.scalars(select(ShiftTemplate).order_by(ShiftTemplate.name)).all()
    return [template_dict(row) for row in rows]


@router.post("/api/shift-templates", status_code=201)
def post_template(payload: TemplateIn, session: Session = Depends(get_db)) -> dict:
    return template_dict(create_template(session, payload.model_dump()))


@router.get("/api/shifts")
def list_shifts(session: Session = Depends(get_db)) -> list[dict]:
    rows = session.scalars(select(ShiftInstance).order_by(ShiftInstance.start_utc, ShiftInstance.id)).all()
    return [shift_dict(row) for row in rows]


@router.post("/api/shifts", status_code=201)
def post_shift(payload: ShiftIn, session: Session = Depends(get_db)) -> dict:
    return shift_dict(create_shift(session, payload.model_dump()))


@router.delete("/api/shifts/{shift_id}", status_code=204)
def remove_shift(shift_id: int, session: Session = Depends(get_db)) -> None:
    delete_shift(session, shift_id)


@router.get("/api/rulesets/active")
def get_rules(session: Session = Depends(get_db)) -> dict:
    row = active_ruleset(session)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "No active ruleset."})
    return rules_dict(row)


@router.post("/api/rulesets", status_code=201)
def post_rules(payload: RulesIn, session: Session = Depends(get_db)) -> dict:
    data = payload.model_dump()
    data["weights"] = payload.weights.model_dump()
    return rules_dict(save_rules(session, data))


@router.post("/api/demo/load")
def load_demo(payload: DemoIn, session: Session = Depends(get_db)) -> dict:
    counts = load_scenario_into_db(session, payload.scenario)
    return {"scenario": payload.scenario, "synthetic": True, **counts}


@router.post("/api/optimization-runs", status_code=201)
def post_run(payload: RunIn, session: Session = Depends(get_db)) -> dict:
    try:
        run = launch_run(
            session,
            mode=payload.mode,
            random_seed=payload.random_seed,
            label=payload.label,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": "solve_in_progress", "message": exc.message}) from exc
    body = run_dict(session, run)
    run_id = run.id
    session.close()
    start_solve_thread(run_id)
    return body


@router.get("/api/optimization-runs/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_db)) -> dict:
    run = session.get(OptimizationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Run not found."})
    return run_dict(session, run)


@router.get("/api/schedules/latest")
def latest_schedule(session: Session = Depends(get_db)) -> dict:
    schedule = session.scalar(select(ScheduleVersion).order_by(ScheduleVersion.id.desc()).limit(1))
    if schedule is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "No schedule has been stored."},
        )
    return schedule_dict(session, schedule)


@router.get("/api/schedules/{schedule_id}")
def get_schedule(schedule_id: int, session: Session = Depends(get_db)) -> dict:
    schedule = session.get(ScheduleVersion, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Schedule not found."})
    return schedule_dict(session, schedule)


@router.post("/api/schedules/{schedule_id}/validate")
def validate(schedule_id: int, session: Session = Depends(get_db)) -> dict:
    schedule = session.get(ScheduleVersion, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Schedule not found."})
    payload = schedule_dict(session, schedule)
    schedule.validation = payload["validation"]
    session.commit()
    return payload["validation"]


@router.get("/api/schedules/{schedule_id}/export.csv")
def export_csv(schedule_id: int, session: Session = Depends(get_db)) -> Response:
    schedule = session.get(ScheduleVersion, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Schedule not found."})
    body = schedule_csv(session, schedule)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="schedule-{schedule_id}.csv"'},
    )


@router.get("/api/schedules/{schedule_id}/export.ics")
def export_ics(schedule_id: int, session: Session = Depends(get_db)) -> Response:
    schedule = session.get(ScheduleVersion, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Schedule not found."})
    body = schedule_ics(session, schedule)
    return Response(
        content=body,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="schedule-{schedule_id}.ics"'},
    )

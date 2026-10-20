"""FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import enforce_bind_policy, get_settings
from app.database import get_sessionmaker, reset_engine, run_migrations
from app.domain.errors import DomainError
from app.services.runs import reap_stale_runs
from app.services.seed import load_scenario_into_db, seed_if_empty

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    enforce_bind_policy(settings)
    run_migrations(settings.resolved_database_url)
    reset_engine()
    session = get_sessionmaker()()
    try:
        reap_stale_runs(session, timedelta(seconds=settings.stale_run_seconds))
        if settings.app_env == "demo":
            if settings.reset_demo:
                load_scenario_into_db(session, "feasible")
            else:
                seed_if_empty(session)
        session.commit()
    finally:
        session.close()
    yield
    reset_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    enforce_bind_policy(settings)
    app = FastAPI(title="Workforce Optimizer", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": {"code": exc.code, "message": exc.message}})

    @app.get("/")
    def root() -> dict:
        return {
            "service": "workforce-optimizer",
            "health": "/health",
            "ready": "/ready",
            "docs": "/docs",
        }

    app.include_router(router)
    return app


app = create_app()

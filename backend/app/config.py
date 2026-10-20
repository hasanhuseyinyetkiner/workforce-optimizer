"""Runtime settings. Defaults keep the API on loopback with a local SQLite file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def default_database_url() -> str:
    path = (BACKEND_ROOT / "data" / "workforce.db").as_posix()
    return f"sqlite:///{path}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "demo"
    host: str = "127.0.0.1"
    port: int = 8103
    allow_network_bind: bool = False
    reset_demo: bool = False
    database_url: str = ""
    solver_num_workers: int = 4
    solver_deterministic_time_seconds: float = 10
    solver_fast_time_seconds: float = 10
    stale_run_seconds: int = 120
    cors_origins: str = "http://127.0.0.1:5103,http://localhost:5103"

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or default_database_url()

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def enforce_bind_policy(settings: Settings) -> None:
    host = settings.host.strip().lower()
    if host in {"127.0.0.1", "::1", "localhost"}:
        return
    if settings.allow_network_bind:
        return
    raise RuntimeError(
        "Refusing to start on a non-loopback host. "
        "Set ALLOW_NETWORK_BIND=true only when a local reverse proxy or Compose "
        "port mapping restricts exposure to 127.0.0.1."
    )

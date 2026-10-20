"""Loopback-checked API entrypoint."""

from __future__ import annotations

import uvicorn

from app.config import enforce_bind_policy, get_settings


def main() -> None:
    settings = get_settings()
    enforce_bind_policy(settings)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        factory=False,
    )


if __name__ == "__main__":
    main()

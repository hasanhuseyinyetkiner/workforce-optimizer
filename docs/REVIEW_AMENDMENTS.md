# Design review amendments (binding)

These amendments come from the pre-implementation design review (2026-10-20). They **override** any conflicting text in `docs/PRODUCT_SPEC.md`. IDs refer to review findings.

## Environment and delivery (all products)

- **[C-1] No Docker, no local PostgreSQL.** The dev machine is Windows 11 with `uv` (use Python 3.12: `uv python pin 3.12`), Node 24 and pnpm. Provide a **native dev path that is verified locally** (`uv run ...` backend, `pnpm dev` frontend). Local tests may use SQLite through the same SQLAlchemy models; PostgreSQL-only behavior gets a SQLite-safe fallback or a `@pytest.mark.postgres` marker that runs in CI. Write `compose.yaml` and Dockerfiles, but they are verified **only in CI** by a `compose-smoke` job; the README must say so until that job passes.
- **CI** (GitHub Actions, `ubuntu-latest`): backend Ruff + pytest against a PostgreSQL service container; frontend ESLint + `tsc` + Vitest + build; `compose-smoke` (`docker compose up --build -d`, wait for `/ready`, then `docker compose down -v`).
- **[C-6] Ports:** API `8103`, web `5103`, PostgreSQL host port `5403`.
- **[C-2] Loopback by default.** Uvicorn binds `127.0.0.1`; Compose port mappings use `127.0.0.1:` prefixes. No auth in the MVP, so startup refuses a non-loopback host unless `ALLOW_NETWORK_BIND=true` is set explicitly. `APP_ENV=demo` shows a persistent "Local demo · synthetic data" banner.
- **[C-3] No CPU-heavy work on the event loop.** Solves run in a worker thread/process, never inside an `async def` handler. `OptimizationRun` rows carry `status` and `heartbeat_at`; a startup reaper marks stale `RUNNING` runs `FAILED` with a reason. Cap CP-SAT `num_workers` so the API stays responsive; add a test proving `/health` responds while a solve runs.
- **[C-4] Licensing and git.** Do **not** add a `LICENSE` file; the README states "License: pending owner decision". Do not create remotes or push. Commit locally in small conventional commits (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, `ci:`).
- **Brand:** accent color `#D97706` (amber). Light and dark themes.

## Product-specific

- **[WFO-1] Reproducibility is a mode, not a default.** `reproducible` mode (used by the demo and all tests): `interleave_search=True`, fixed `num_workers`, stored `random_seed`, and a `max_deterministic_time` limit instead of wall-clock time. `fast` mode uses a wall-clock limit and is labeled non-reproducible in the UI. Persist every solver parameter on `OptimizationRun`. Verify parameter names and semantics against the installed `ortools` version before relying on them. Test: solve the demo instance 10 times in reproducible mode and assert identical assignment hashes.
- **[WFO-2] MIT-only calendar.** Use only FullCalendar standard (MIT) plugins or a custom roster grid. The employee-by-time "resource timeline" view is FullCalendar Premium and must not be used. A CI step asserts no `@fullcalendar/resource*` or `fullcalendar-scheduler` dependency exists.
- **[WFO-3] Time model.** All persisted datetimes go through a UTC-enforcing SQLAlchemy `TypeDecorator` (aware in, aware out) so SQLite and PostgreSQL behave identically. Planning-time-zone conversion happens in the domain layer with `zoneinfo`. Shift times that are nonexistent or ambiguous because of DST are rejected with a validation error unless explicitly handled. Round-trip test on SQLite locally and PostgreSQL in CI.

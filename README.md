# Workforce Optimizer

Constraint-based scheduling that explains every shift assignment.

OR-Tools CP-SAT solver, independent Python validator, reproducible solve mode. Synthetic employees and shift demand only.

## Verified local run (Windows)

```powershell
# Terminal 1 — API (127.0.0.1:8103)
cd backend
uv sync
uv run python -m app.cli

# Terminal 2 — Web (127.0.0.1:5103)
cd frontend
pnpm install
pnpm dev
```

| Service | URL |
| --- | --- |
| Web | http://127.0.0.1:5103 |
| API docs | http://127.0.0.1:8103/docs |

Demo scenario loads on startup. Use Solve → reproducible mode; validator runs after each schedule.

```powershell
cd backend
uv run pytest -q
```

## Status

Backend + frontend MVP runnable. No FullCalendar Premium plugins. License pending owner decision.

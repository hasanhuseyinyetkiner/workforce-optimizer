<a id="readme-top"></a>

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-dark.svg">
  <img alt="Workforce Optimizer — constraint-based scheduling that explains every shift" src="docs/assets/banner-light.svg" width="100%">
</picture>

**OR-Tools CP-SAT scheduling with an independent validator.** Load a synthetic roster scenario, solve in reproducible mode, inspect FEASIBLE / OPTIMAL / INFEASIBLE honestly, and export CSV/ICS.

[Quick start](#quick-start) · [How it works](#how-it-works) · [Limitations](#security-privacy-and-limitations)

</div>

## Quick start

```powershell
# Backend (API http://127.0.0.1:8103)
cd backend
uv sync
uv run python -m app.cli

# Frontend (http://127.0.0.1:5103) — new terminal
cd frontend
pnpm install
pnpm dev
```

| Service | URL |
| --- | --- |
| Web | http://127.0.0.1:5103 |
| API docs | http://127.0.0.1:8103/docs |

Demo employees/shifts seed on startup. Open **Solve** → run reproducible mode → open **Schedule**.

## How it works

```mermaid
flowchart LR
  D[Demand + employees + rules] --> M[CP-SAT model]
  M --> S[Solver status]
  S --> V[Independent Python validator]
  V --> UI[Roster UI + exports]
```

Reproducible mode uses `interleave_search`, fixed workers, seed and deterministic time. Calendar UI uses custom/MIT-only components (no FullCalendar Premium).

## Testing

```powershell
cd backend; uv run pytest -q
cd frontend; pnpm test; pnpm build
```

## Security, privacy and limitations

> [!IMPORTANT]
> Not labor-law compliance. Synthetic aliases only. Loopback by default.

License: pending owner decision.

<p align="right"><a href="#readme-top">↑ back to top</a></p>

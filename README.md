<a id="readme-top"></a>

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-dark.svg">
  <img alt="Workforce Optimizer — constraint-based scheduling that explains every shift" src="docs/assets/banner-light.svg" width="100%">
</picture>

**Constraint-based scheduling that explains every shift assignment.**

OR-Tools CP-SAT with an independent pure-Python validator. Load a synthetic roster, solve in reproducible mode, inspect OPTIMAL / FEASIBLE / INFEASIBLE honestly, compare scenarios, and export CSV/ICS.

[Quick start](#quick-start) · [How it works](#how-it-works) · [Docs](#docs) · [Limitations](#security-privacy-and-limitations)

</div>

## Quick start

Native path (verified on Windows 11 with `uv` + pnpm). Docker Compose is provided for CI only until `compose-smoke` is green on GitHub Actions.

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

Demo employees/shifts seed on startup. Open **Solve** → run reproducible mode → open **Schedule**. Compare stored schedules under **Scenarios**.

## How it works

```mermaid
flowchart LR
  D[Demand + employees + rules] --> M[CP-SAT model]
  M --> S[Solver status]
  S --> V[Independent Python validator]
  V --> UI[Custom roster UI + exports]
```

- Reproducible mode: `interleave_search`, capped workers (≤4), seed, `max_deterministic_time`.
- Fast mode: wall-clock limit, labeled non-reproducible in the UI.
- Roster UI is a custom employee×day grid (MIT-safe; no FullCalendar Premium).

## Testing

Measured locally on 2026-10-20:

| Check | Result |
| --- | --- |
| `cd backend && uv run ruff check app tests` | pass |
| `cd backend && uv run pytest -q` | **23 passed**, 1 skipped |
| `cd frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm build` | pass |
| `cd frontend && pnpm assert:no-fc-premium` | pass |
| `cd frontend && pnpm test:e2e` | **1 passed** (demo→solve→validate→export) |

```powershell
cd backend; uv run ruff check app tests; uv run pytest -q
cd frontend; pnpm lint; pnpm typecheck; pnpm test; pnpm build; pnpm assert:no-fc-premium; pnpm test:e2e
```

## Docs

- [ALGORITHM.md](docs/ALGORITHM.md) — hard/soft constraints, modes, validator
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — services and runtime
- [GITHUB_METADATA.md](docs/GITHUB_METADATA.md) — description and topics
- [REVIEW_AMENDMENTS.md](docs/REVIEW_AMENDMENTS.md) — binding design amendments

## Security, privacy and limitations

> [!IMPORTANT]
> Not labor-law compliance. Synthetic aliases only. Loopback by default (`127.0.0.1`). Solves run off the event loop with CP-SAT worker cap 4.

License: pending owner decision.

<p align="right"><a href="#readme-top">↑ back to top</a></p>

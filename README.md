# Workforce Optimizer

Local CP-SAT roster demo: assign staff to shifts under hard coverage / skill / rest / hour rules, return honest solver status, and re-check assignments with an OR-Tools-free validator.

Accent: **`#D97706`**. Ports: API **8103**, web **5103**. License: [MIT](LICENSE).

[![CI](https://github.com/hasanhuseyinyetkiner/workforce-optimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/hasanhuseyinyetkiner/workforce-optimizer/actions/workflows/ci.yml)

<p align="center">
  <img alt="Overview after a reproducible solve" src="docs/screenshots/overview.png" width="92%">
</p>

## Why it exists

Ward managers need a roster that respects configured constraints — and a clear `INFEASIBLE` when nothing works. This app never fabricates assignments on conflict. Status is a model result, not a labor-law verdict.

## Capabilities

| Shipped | Notes |
| --- | --- |
| OR-Tools CP-SAT model | Hard vs soft terms; reproducible / fast modes |
| Independent validator | Pure Python; used on validate + export |
| Scenarios | Toggle **OPTIMAL / FEASIBLE / INFEASIBLE** with live wall-ms telemetry |
| Conflict diagnostics | Structural findings + assumption-group core + relaxation probes |
| Dense roster grid | Employee×day CSS grid, violation badges, CSV/ICS export |
| Solver telemetry | Wall ms, objective, best bound, gap |

Synthetic Northwind Ward data only. Local demo / MVP — not multi-tenant SaaS.

## Architecture

```mermaid
flowchart LR
  UI[React UI :5103] --> API[FastAPI :8103]
  API --> DB[(SQLite local / PostgreSQL CI)]
  API --> Worker[Solve thread]
  Worker --> CPSAT[OR-Tools CP-SAT]
  Worker --> Val[Pure-Python validator]
```

Model: [docs/ALGORITHM.md](docs/ALGORITHM.md) · measured runs: [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Quick start

```powershell
# Backend — http://127.0.0.1:8103
cd backend
uv sync
uv run python -m app.cli

# Frontend — http://127.0.0.1:5103 (new terminal)
cd frontend
pnpm install
pnpm dev
```

Env: [`.env.example`](.env.example). Non-loopback bind needs `ALLOW_NETWORK_BIND=true`.

### 60-second path

1. Open http://127.0.0.1:5103
2. **Scenarios** → **OPTIMAL** (or **FEASIBLE**) — load + solve, watch wall ms
3. **Schedule** → dense grid + validator summary
4. **INFEASIBLE** toggle → Solve shows conflict groups (e.g. skill requirements), no roster

### API sketch

```powershell
curl -X POST http://127.0.0.1:8103/api/demo/load -H "Content-Type: application/json" -d "{\"scenario\":\"optimal\"}"
curl -X POST http://127.0.0.1:8103/api/optimization-runs -H "Content-Type: application/json" -d "{\"mode\":\"reproducible\",\"random_seed\":1}"
```

Scenarios: `optimal` | `feasible` | `infeasible`.

## Status semantics

| Status | Meaning |
| --- | --- |
| `OPTIMAL` | Proven optimum within the search budget |
| `FEASIBLE` | Feasible assignment; not proven optimal (gap may be &gt; 0) |
| `INFEASIBLE` | No assignment under configured hard rules — **no schedule row** |
| `UNKNOWN` | Timeout / unexpected / model invalid |

## Diagnostics (honest)

On `INFEASIBLE`: structural findings, CP-SAT **constraint-group** assumptions (`sufficient_assumptions_for_infeasibility` + deletion filter), and progressive relaxations. This is **not** a proven minimal IIS over every individual constraint. See [ALGORITHM.md](docs/ALGORITHM.md#diagnostics-best-effort).

## Tests & benchmark

```powershell
cd backend
uv run ruff check app tests
uv run pytest -q
uv run python scripts/micro_benchmark.py

cd ../frontend
pnpm lint && pnpm typecheck && pnpm test && pnpm build
pnpm test:e2e
```

Measured micro-benchmark: [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Docs

| Doc | Contents |
| --- | --- |
| [ALGORITHM.md](docs/ALGORITHM.md) | Variables, hard/soft, diagnostics, status |
| [BENCHMARK.md](docs/BENCHMARK.md) | Measured size ladder |
| [frontend/README.md](frontend/README.md) | SPA notes |

## Limitations

- Not labor-law compliance. `INFEASIBLE` ≠ “legally prohibited.”
- Demo auth: none. Loopback by default. CP-SAT workers capped at 4.
- Assumption-group cores are best-effort, not full IIS.

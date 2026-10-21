# Frontend — Workforce Optimizer

React + Vite + TypeScript SPA for the local Workforce Optimizer demo.

## Stack

| Piece | Choice |
| --- | --- |
| UI | React 19, React Router, TanStack Query |
| Styling | Tailwind CSS 4, amber accent `#D97706` |
| Charts | Recharts (Overview / Solve breakdown) |
| Roster | Dense custom employee×day grid + violation badges (`SchedulePage.tsx`) |
| Scenarios | OPTIMAL / FEASIBLE / INFEASIBLE toggle with live wall-ms telemetry |
| Tests | Vitest smoke + Playwright e2e |
| Package manager | pnpm 12.14.0 |

There is **no** third-party calendar library in `dependencies`. The Schedule page is a CSS grid of employees × local dates. `pnpm assert:no-fc-premium` is defensive lockfile hygiene from historical WFO-2 (banned premium calendar package name patterns) — not a claim that any calendar widget is shipped.

## Dev

```powershell
# API must be on http://127.0.0.1:8103 (see repo root README)
pnpm install
pnpm dev
```

App: http://127.0.0.1:5103 — Vite proxies `/api` to the backend when configured (see `vite.config.ts`).

Env template: [`.env.example`](.env.example).

## Scripts

| Command | Purpose |
| --- | --- |
| `pnpm dev` | Vite on `127.0.0.1:5103` |
| `pnpm lint` | ESLint |
| `pnpm typecheck` | `tsc --noEmit` |
| `pnpm test` | Vitest |
| `pnpm build` | Production build |
| `pnpm assert:no-fc-premium` | Lockfile hygiene |
| `pnpm test:e2e` | Playwright (starts/uses local stack per `playwright.config.ts`) |

## Pages

| Route | Page |
| --- | --- |
| `/` | Overview — counts, latest run, objective chart, validator card |
| `/employees` | Employee list |
| `/shifts` | Shift demand |
| `/rules` | Active ruleset (hard/soft labels) |
| `/solve` | Reproducible solve launcher + status |
| `/schedule` | Custom roster grid, re-validate, CSV/ICS |
| `/scenarios` | Load feasible/infeasible demos; compare schedules |

## Screenshots

Authentic captures used in the root README live in [`../docs/screenshots/`](../docs/screenshots/). Regenerate with Playwright when the UI changes:

```powershell
# Backend running on :8103
pnpm exec playwright test e2e/screenshots.spec.ts
```

## Accessibility notes

- Demo banner announces synthetic / local-demo data.
- Solver status uses text badges (`OPTIMAL` / `FEASIBLE` / `INFEASIBLE` / `UNKNOWN`), not color alone.
- Roster grid exposes an accessible name via `aria-label` on the grid container.
- Export actions are ordinary links with visible labels.

## Related docs

- [Root README](../README.md)
- [Architecture](../docs/ARCHITECTURE.md)
- [Engineering decisions](../docs/ENGINEERING_DECISIONS.md)

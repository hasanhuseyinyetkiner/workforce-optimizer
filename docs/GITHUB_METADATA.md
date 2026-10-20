# GitHub repository metadata

Use these values when editing the GitHub repository settings. Do not invent stars, download counts, or unrun benchmarks.

## Description

```
Open-source workforce scheduling with OR-Tools CP-SAT, explainable constraints and independent validation.
```

## Topics

```
operations-research
or-tools
optimization
scheduling
fastapi
react
python
workforce-management
```

## Homepage

Leave blank unless a public demo URL is published.

## Measured verification (local, 2026-10-20)

| Check | Command | Result |
| --- | --- | --- |
| Backend lint | `cd backend && uv run ruff check app tests` | pass |
| Backend tests | `cd backend && uv run pytest -q` | 23 passed, 1 skipped |
| Frontend | `cd frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm build` | pass |
| FullCalendar guard | `cd frontend && pnpm assert:no-fc-premium` | pass (custom roster; no Premium deps) |
| Playwright smoke | `cd frontend && pnpm test:e2e` | 1 passed |

## About box checklist

- [ ] Description pasted
- [ ] Topics added
- [ ] License left unset (README: pending owner decision)
- [ ] README screenshot / banner present

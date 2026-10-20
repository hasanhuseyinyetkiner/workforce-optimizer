# GitHub repository metadata

Use these values when editing the GitHub repository settings. Do not invent stars, download counts, or unrun benchmarks.

## Description

```
Workforce scheduling demo with OR-Tools CP-SAT, explainable constraints, and independent validation.
```

Do **not** use wording that claims “open-source” / OSS until the owner adds a `LICENSE` file. README status: **License: pending owner decision.**

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

## About box checklist

- [ ] Description pasted (non-OSS wording above)
- [ ] Topics added
- [ ] License left unset until owner decides (do not imply MIT/Apache without a file)
- [x] README screenshots / banner present (`docs/assets/banner-*.svg`, `docs/screenshots/{overview,solve,schedule,validate,scenarios}.png` from live `:5103`)
- [x] Accent documented as amber `#D97706` (UI + screenshots; emerald deferred)
- [x] `PRODUCT_SPEC.md` marked historical; checklist in `RELEASE_READINESS.md`

## Measured verification (local, 2026-10-20 — this polish session)

| Check | Command / method | Result |
| --- | --- | --- |
| Backend lint | `cd backend && uv run ruff check app tests` | All checks passed |
| Backend tests | `cd backend && uv run pytest -q` | **23 passed**, 1 skipped, 1 warning |
| Frontend lint / typecheck / test / build | `pnpm lint && pnpm typecheck && pnpm test && pnpm build` | pass (standalone `tsc` after one OOM under memory pressure) / Vitest **1 passed** / build OK |
| Calendar lockfile guard | `pnpm assert:no-fc-premium` | pass (hygiene; custom roster grid is the Schedule UI) |
| Playwright smoke | `pnpm test:e2e -- e2e/demo-solve.spec.ts` | **1 passed** (demo→solve→validate→export) |
| Screenshots on disk | visual check of `docs/screenshots/*.png` | match current UI (custom roster grid; FEASIBLE / Valid) |
| Micro-benchmark | `uv run python scripts/micro_benchmark.py` | see [BENCHMARK.md](BENCHMARK.md) — statuses/objectives stable; wall times vary |
| Local md link check | relative-link scan over docs + README + frontend/README | all resolve |
| CI compose-smoke | GitHub Actions | not re-verified in this local session |

## Suggested pin rationale

Constraint-programming case study with an independent validator, honest `INFEASIBLE` handling (configured hard rules — not a legal ban), and a reproducible solver mode — useful when interviewers ask how you model hard vs soft staffing rules without inventing schedules.

## Related

- [RELEASE_READINESS.md](RELEASE_READINESS.md) — pre-publish checklist
- [PRODUCT_SPEC.md](PRODUCT_SPEC.md) — historical prompt only
- [BENCHMARK.md](BENCHMARK.md) — measured solver micro-benchmark

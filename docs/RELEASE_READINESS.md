# Release readiness (local portfolio)

Checklist for a truthful local demo release. **Do not** invent CI greens, coverage %, or benchmarks. License remains pending owner decision — do not add a `LICENSE` file without explicit approval. Do not push or change repository visibility without owner authorization.

## Product claims gate

| Claim area | Ready when | Evidence |
| --- | --- | --- |
| Solver honesty | Status semantics documented; `INFEASIBLE` stores no roster | [ALGORITHM.md](ALGORITHM.md), API/UI |
| No labor-law compliance marketing | README / limitations say demo operational rules only | Root README |
| Roster UI | Described as custom employee×day grid | [frontend/README.md](../frontend/README.md) |
| Benchmarks | Only measured tables from `scripts/micro_benchmark.py` | [BENCHMARK.md](BENCHMARK.md) |
| Screenshots | Captured from live `:5103` with current UI | `docs/screenshots/*.png` |
| Spec docs | `PRODUCT_SPEC.md` marked historical | Banner at top of that file |

## Local verification commands

```powershell
# Backend
cd backend
uv run ruff check app tests
uv run pytest -q
uv run python scripts/micro_benchmark.py

# Frontend
cd ../frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm assert:no-fc-premium
pnpm exec playwright install chromium   # once
pnpm test:e2e
```

Optional screenshot refresh (API on `:8103`):

```powershell
cd frontend
pnpm exec playwright test e2e/screenshots.spec.ts
```

## GitHub metadata

Apply About box values from [GITHUB_METADATA.md](GITHUB_METADATA.md) manually. Leave Homepage blank unless a public demo URL exists. Leave license unset until the owner decides.

## Compose / CI

- Native Windows path is the documented demo path.
- `compose-smoke` in GitHub Actions exercises Docker; do not claim local Docker verification unless you ran it.
- Push to `origin` only with owner permission.

## Blockers that stop “ready”

- Failing pytest / Vitest / Playwright / ruff / eslint / tsc / build
- README claiming OPTIMAL when measured status is FEASIBLE
- Current-facing docs implying a third-party calendar widget is the Schedule UI
- Any invented runtime, accuracy, or compliance percentage

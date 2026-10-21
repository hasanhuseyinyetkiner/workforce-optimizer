# Engineering decisions

Staff-level product and modeling choices for Workforce Optimizer.

## Engineering case study

### Hard vs soft

| Class | Role | Examples |
| --- | --- | --- |
| **Hard** | Must hold for any accepted roster | Coverage, skills, no overlap, min rest, availability/PTO, weekly caps, max consecutive days |
| **Soft** | Weighted penalties in the minimize objective | Cost, preference mismatches, fairness deviations, overtime, night/weekend imbalance, understaff (only if relaxed) |

Hard violations → `INFEASIBLE` (or eligibility pruning before variables exist). Soft terms never authorize a hard breach. Soft weights are demo defaults in `backend/app/data/feasible/rules.json` — tunable per ruleset, not universal “best” values.

### Weights and trade-offs

Demo weights: cost 1, preference 8, fairness 4, overtime 15, night/weekend imbalance 3/3, understaff 500 (active only with `relaxed_understaffing`). Raising a weight increases pressure to shrink that term, often at the expense of another (e.g. more fairness can raise cost). The UI objective breakdown uses the same formulas as `scoring.score_schedule`.

### Reproducibility limits

`reproducible` mode fixes SatParameters that OR-Tools documents as deterministic under `interleave_search`. Limits:

1. Assignment hashes match across runs with the same seed/version/params (demo ×10 test + micro-bench).
2. Wall-clock runtime is **not** deterministic.
3. A deterministic time budget can end at `FEASIBLE` with a bound gap — honest, not “almost optimal.”
4. Cross-version OR-Tools results are not guaranteed.

### Independent validation

CP-SAT produces candidates; `validator.py` rechecks hard rules without importing OR-Tools (enforced by test). Validate and export paths go through this checker. Tiny instances are also compared to exhaustive enumeration for score agreement.

### Infeasibility diagnostics

On `INFEASIBLE`, diagnostics combine: (1) structural findings, (2) CP-SAT **constraint-group assumptions** + deletion filter (`sufficient_assumptions_for_infeasibility`), (3) progressive relaxation probes. Best-effort only — **not** a proven irreducible inconsistent subset (IIS) over individual constraints. If the assumption API is unavailable, that layer is omitted and labeled honestly.

**Infeasible ≠ legally prohibited.** Status means the configured constraint model has no satisfying assignment, not that a schedule violates labor law.

### Resource limits

| Limit | Value |
| --- | --- |
| CP-SAT `num_workers` | ≤ 4 |
| Solve thread | Off the FastAPI event loop |
| Reproducible budget (demo/tests) | `max_deterministic_time=8s` |
| Bind | Loopback unless `ALLOW_NETWORK_BIND=true` |
| Auth | None in MVP — local synthetic demo only |

---

## WFO-1 — Reproducibility is a mode, not a default

**Context.** OR-Tools CP-SAT search can be non-deterministic under wall-clock limits and certain parameter combinations. Portfolio demos and tests need identical assignment hashes across runs.

**Options.** Always force deterministic parameters; always use wall-clock “fast” search; or expose both with explicit labeling.

**Decision.** Two modes:

| Mode | Behavior |
| --- | --- |
| `reproducible` | `interleave_search=True`, fixed `random_seed`, capped `num_workers`, `max_deterministic_time`, `share_linear2_bounds=False` |
| `fast` | Wall-clock `max_time_in_seconds`; UI label **Fast · not reproducible** |

Demo UI and automated tests use `reproducible`. Every SatParameter used is checked against the installed `ortools` version at apply time. Parameters are persisted on `OptimizationRun`.

**Trade-offs.** Deterministic budgets can stop at `FEASIBLE` with a gap to the best bound (measured on the demo: objective 8788 vs bound ~8597–8647 under an 8s deterministic limit). That honesty is preferred over pretending OPTIMAL.

**Validation.** `test_demo_reproducible_ten_times_and_validator_accepts`; `scripts/micro_benchmark.py` same-seed equality (2026-10-20).

## WFO-2 — Custom roster grid (historical licensing context)

> **Historical decision.** Early product notes considered FullCalendar; Premium resource-timeline packages were ruled out. **Current product truth:** the Schedule page is a **custom employee×day CSS grid** in `SchedulePage.tsx`. No FullCalendar packages ship in `frontend/package.json`.

**Context (historical).** FullCalendar’s resource-timeline / scheduler packages are Premium-licensed and unsuitable for an unlicensed portfolio MVP.

**Decision.** Ship a custom employee×day roster grid. CI script `frontend/scripts/assert-no-fc-premium.mjs` fails if banned Premium package strings appear in the lockfile (defensive hygiene, not an indication that FullCalendar is in use).

**Trade-offs.** No drag-edit timeline in MVP; export and validator remain first-class instead.

## WFO-3 — UTC clocks end-to-end

**Context.** SQLite and PostgreSQL differ on naive datetime handling; DST gaps/overlaps break overnight roster math if local walls are stored naively.

**Decision.** Persist via `UtcDateTime` (aware in, aware out). Planning-timezone conversion lives in the domain layer (`zoneinfo`). Nonexistent and ambiguous local times are rejected at ingest unless explicitly handled.

**Validation.** Round-trip tests on SQLite locally; PostgreSQL in CI; DST fixture tests in `test_solver.py`.

## Brand accent — amber `#D97706`

**Context.** The shipped UI, SVG banners, Recharts fills, and screenshots use amber `#D97706`.

**Decision.** Keep amber as the product accent. Document it in the README.

## Independent validator over solver trust

**Context.** CP-SAT is the optimizer; exports and human review need a second opinion that cannot silently share solver bugs or import costs.

**Decision.** `validator.py` / `scoring.py` / `eligibility.py` / `diagnostics.py` must not import OR-Tools. API validate and export use the validator.

**Trade-offs.** Two implementations of hard rules must stay aligned — covered by shared eligibility helpers and tests that compare solver outputs to validator acceptance.

## Worker cap and off-loop solves

**Context.** CP-SAT can saturate cores; async FastAPI handlers must stay healthy.

**Decision.** Cap `num_workers` at 4; run solves in a worker thread; reap stale `RUNNING` rows; keep `/health` responsive (covered by tests).

## Related files

| File | Role |
| --- | --- |
| [`ALGORITHM.md`](ALGORITHM.md) | Formal model + status semantics |
| [`BENCHMARK.md`](BENCHMARK.md) | Measured micro-benchmark |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Runtime topology |

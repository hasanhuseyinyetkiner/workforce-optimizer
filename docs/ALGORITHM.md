# Algorithm

Workforce Optimizer builds a Google OR-Tools **CP-SAT** model over employee×shift assignment booleans, then rechecks every hard constraint with a pure-Python validator that never imports OR-Tools.

Implementation: `backend/app/domain/solver.py`, `validator.py`, `eligibility.py`, `scoring.py`. Verified against **ortools 9.15.6755**.

## Inputs

- Employees with skills, weekly hour caps, preferences, availability windows, and time off
- Shift instances with required headcount, skill requirements, and UTC start/end (planning TZ conversion via `zoneinfo`)
- An active ruleset: hard limits plus soft objective weights

## Decision variables

| Symbol | Type | When created |
| --- | --- | --- |
| \(x_{e,s}\) | BoolVar `x_{employee}_{shift}` | Only if `employee_block_reason(...)` is `None` |
| `short_s` / `skill_short_*` | IntVar | Only if `rules.relaxed_understaffing` |
| `ot_e` | IntVar | Always when building soft terms |
| `fair_*` / `night_*` / `weekend_*` | IntVar | Absolute deviations from mean load |

Eligibility blocks (no variable) cover: `max_shift_hours`, `unavailable`, `time_off`, `prior_conflict`. Candidate count = number of created \(x_{e,s}\) variables after pruning.

## Hard constraints

Always enforced in the main solve unless a **named relaxation probe** temporarily mutates the problem (diagnostics only):

1. **Coverage** — \(\sum_e x_{e,s} \ge r_s\) (or \(+\) shortfall when relaxed)
2. **Skills** — for each requirement row, qualified assignees \(\ge\) `min_count` (`any_of` skill ids)
3. **No overlap / rest** — for each employee, any pair of shifts with overlap or gap \(<\) `min_rest_hours` cannot both be 1 (overnight handled via UTC endpoints)
4. **Availability / PTO** — blocked employees never receive an assignment variable
5. **Weekly caps** — ISO-week hours including prior boundary shifts \(\le\) weekly cap
6. **Max shift hours** — shifts longer than `max_shift_hours` are ineligible
7. **Max consecutive days** — sliding window over planning horizon local start-dates when configured

If the model is infeasible, the API stores `INFEASIBLE` with diagnostics. It **never fabricates** a roster.

Hard constraints here are **model rules** configured for the demo ward. They are **not** a claim of labor-law compliance, collective-bargaining compliance, or that an assignment is legally permitted or prohibited in any jurisdiction.

## Soft objective

Minimize a weighted sum (demo weights from `backend/app/data/feasible/rules.json`):

| Term | Demo weight | Meaning |
| --- | --- | --- |
| cost | 1 | \(\sum x_{e,s} \cdot \mathrm{cost}_e \cdot \mathrm{hours}_s\) |
| preference | 8 | penalties for night/weekend preference mismatches (`preference_points`) |
| fairness | 4 | absolute deviations of hours from the mean (scaled by \(n\)) |
| overtime | 15 | hours above `overtime_threshold_hours` |
| night / weekend imbalance | 3 / 3 | absolute deviations of night/weekend shift counts |
| understaff | 500 | shortfall variables **only** when `relaxed_understaffing` is true |

Post-solve breakdown for the UI uses the same formulas in `scoring.score_schedule` (no OR-Tools import).

Higher weight → stronger pressure to reduce that term. Changing weights changes trade-offs (e.g. raising `fairness` can increase `cost`). Soft terms never override hard feasibility.

## Solver modes (WFO-1)

| Mode | Parameters | Label |
| --- | --- | --- |
| `reproducible` | `interleave_search=True`, capped `num_workers`, fixed `random_seed`, `max_deterministic_time`, `share_linear2_bounds=False` | Reproducible |
| `fast` | wall-clock `max_time_in_seconds`, non-deterministic search | Fast · not reproducible |

`num_workers` is capped at **4** (`WORKER_CAP`) so the API stays responsive. Every parameter dict is persisted on `OptimizationRun` (including `ortools_version`).

`share_linear2_bounds` is forced **false** because the installed OR-Tools docstring marks enabling it as non-deterministic.

### Reproducibility limits

- Same seed + `reproducible` mode → identical assignment hashes on the demo (verified ×10 in tests; consecutive micro-bench runs equal).
- Wall-clock times still vary (OS scheduling, thermal state). Do not treat runtime as a reproducibility invariant.
- Deterministic time budget can stop at `FEASIBLE` with a gap to the best bound; that is expected, not a bug.
- OR-Tools version and parameter set must match; results are not guaranteed across major solver upgrades.

## Independent validator

`app/domain/validator.py` re-validates coverage, skills, overlap, rest, availability, PTO, weekly caps, and consecutive days from the stored assignment list. API validate and export paths use this checker. Unit tests assert the module source does not contain `ortools`.

The validator answers: “does this assignment list violate any hard rule?” It does **not** re-prove optimality.

## Status semantics

CP-SAT returns a native status. This app maps and persists:

| Persisted status | Meaning in this app |
| --- | --- |
| `OPTIMAL` | Proven optimum within the search budget |
| `FEASIBLE` | Feasible assignment found; **not** proven optimal |
| `INFEASIBLE` | No assignment satisfies the configured hard constraints — **no schedule row** |
| `UNKNOWN` | Search stopped without a usable proof/assignment, **or** the model was rejected |

**`MODEL_INVALID`** (CP-SAT rejects the model) is mapped to **`UNKNOWN`** with an `error` string containing solver response stats. It is not shown as a separate UI badge.

### Important distinctions

| Do not confuse | Correct reading |
| --- | --- |
| `INFEASIBLE` vs “illegal / prohibited” | Infeasible means the **configured model** has no satisfying assignment. It is **not** a labor-law verdict and does not mean “this roster is legally prohibited.” |
| `FEASIBLE` vs `OPTIMAL` | Feasible may still have a positive gap (objective vs best bound). |
| `UNKNOWN` vs “good enough” | Timeout or model rejection is not an optimality claim. |
| Validator `Valid` vs optimum | Valid means hard rules pass; soft score may still be suboptimal. |

Timeouts are not optimality proofs. `FEASIBLE` with a positive optimality gap is expected when `max_deterministic_time` expires before a proof.

## Diagnostics (best effort)

On `INFEASIBLE`, the app attaches structured conflict diagnostics:

1. **Structural findings** — eligibility / coverage / skill pre-checks (`diagnostics.structural_findings`), no OR-Tools.
2. **CP-SAT assumption groups** — hard constraint families (`coverage`, `skill_requirements`, `rest`, `weekly_cap`, `consecutive_days`) are wrapped with `AddAssumption` literals. After infeasibility, `CpSolver.sufficient_assumptions_for_infeasibility` plus a **deletion filter** yields a refined group set. This is a *group-level* sufficient set, **not** a proven minimal IIS over every individual constraint. If the assumption API were missing on the installed OR-Tools build, the app would skip this layer and say so (`assumptions_available=false`) rather than invent an IIS.
3. **Progressive relaxations** — `probe_relaxations` re-solves named mutants (clear skills, clear coverage, zero rest, clear availability, raise caps, clear consecutive days). Large problems skip probes (`employees × shifts > 4000`).

Honest capability label is stored on every diagnostic payload (`note`, `unsat_core_kind`).

## Micro-benchmark

**This-session measured baseline:** [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md) (2026-10-21).  
**Historical ladder only:** [BENCHMARK.md](BENCHMARK.md) (2026-10-20) — do not cite as this-session evidence.

Re-run:

```powershell
cd backend
uv run python scripts/micro_benchmark.py
```

Portfolio micro-benchmark only — not a production OR performance claim.

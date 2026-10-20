# Algorithm

Workforce Optimizer builds a Google OR-Tools **CP-SAT** model over employee×shift assignment booleans, then rechecks every hard constraint with a pure-Python validator that never imports OR-Tools.

## Inputs

- Employees with skills, weekly hour caps, preferences, availability windows, and time off
- Shift instances with required headcount, skill requirements, and UTC start/end (planning TZ conversion via `zoneinfo`)
- An active ruleset: hard limits plus soft objective weights

## Hard constraints (always enforced unless a named relaxation is active)

1. **Coverage** — assigned headcount ≥ required count
2. **Skills** — each skill requirement’s `min_count` is met by qualified assignees
3. **No overlap / rest** — overlapping shifts forbidden; gaps shorter than `min_rest_hours` forbidden (overnight handled via UTC endpoints)
4. **Availability / PTO** — blocked employees never receive an assignment variable
5. **Weekly caps** — ISO-week hours including prior boundary shifts ≤ weekly cap
6. **Max shift hours** — shifts longer than `max_shift_hours` are ineligible
7. **Max consecutive days** — sliding window over the planning horizon when configured

If the model is infeasible, the API stores `INFEASIBLE` with diagnostics. It never fabricates a roster.

## Soft objective

Minimize a weighted sum of:

| Term | Meaning |
| --- | --- |
| cost | Σ cost_per_hour × hours |
| preference | penalties for night/weekend preference mismatches |
| fairness | absolute deviations of hours from the mean |
| overtime | hours above the overtime threshold |
| night / weekend imbalance | absolute deviations of night/weekend shift counts |
| understaff | shortfall variables **only** when `relaxed_understaffing` is true |

## Solver modes (WFO-1)

| Mode | Parameters | Label |
| --- | --- | --- |
| `reproducible` | `interleave_search=True`, capped `num_workers`, fixed `random_seed`, `max_deterministic_time`, `share_linear2_bounds=False` | Reproducible |
| `fast` | wall-clock `max_time_in_seconds`, non-deterministic search | Fast · not reproducible |

`num_workers` is capped at **4** so the API stays responsive. Every parameter dict is persisted on `OptimizationRun`.

## Independent validator

`app/domain/validator.py` re-validates coverage, skills, overlap, rest, availability, PTO, weekly caps, and consecutive days from the stored assignment list. API validate and export paths use this checker.

## Status semantics

| Status | Meaning |
| --- | --- |
| OPTIMAL | proven optimum within the search budget |
| FEASIBLE | feasible but not proven optimal |
| INFEASIBLE | no assignment satisfies hard constraints |
| UNKNOWN | timeout / unexpected / model invalid |

Timeouts are not optimality proofs.

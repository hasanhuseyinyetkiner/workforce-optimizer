# Solver micro-benchmark (historical)

> **Historical only (2026-10-20).** For the latest measured session, see [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md).

Measured portfolio runs on synthetic instances. **Numbers below are from an actual local execution** of `backend/scripts/micro_benchmark.py` on 2026-10-20. This is not a large-scale OR performance claim and must not be cited as a production speedup.

## How to reproduce

```powershell
cd backend
uv run python scripts/micro_benchmark.py
```

If your numbers differ slightly in wall time, that is expected. Assignment hashes for `demo-feasible` seed 1 should match across consecutive runs on the same OR-Tools version and parameters.

## Environment (measured)

| Item | Value |
| --- | --- |
| Host | hasanyetkiner |
| Machine | HP Victus by HP Laptop 16-e0xxx |
| CPU | AMD Ryzen 5 5600H with Radeon Graphics (6 cores / 12 threads) |
| RAM | ~15 GB |
| OS | Windows-11-10.0.26300-SP0 |
| Python | 3.12.10 |
| OR-Tools | 9.15.6755 |
| Mode | `reproducible` |
| Seed | 1 (unless noted) |
| `num_workers` | 4 (capped) |
| `max_deterministic_time` | 8.0 s |
| Date measured | 2026-10-20 |

Solver parameters also persist on each `OptimizationRun` in the app (`ortools_version`, mode, seed, worker count, time limits).

## Results (measured 2026-10-20)

| Instance | Emp | Shifts | Candidates | Seed | Status | Objective | Bound | Runtime (s) | Validator | Assignments |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- | ---: |
| tiny | 3 | 5 | 15 | 1 | OPTIMAL | 1400 | 1400 | 0.136 | valid | 5 |
| small | 5 | 14 | 70 | 1 | OPTIMAL | 3856 | 3856 | 8.478 | valid | 14 |
| demo-feasible | 5 | 21 | 101 | 1 | FEASIBLE | 8788 | 8597 | 10.866 | valid | 28 |
| medium | 8 | 14 | 112 | 1 | FEASIBLE | 8200 | 7766 | 13.572 | valid | 28 |
| demo-infeasible | 5 | 22 | 106 | 1 | INFEASIBLE | — | — | 0.001 | n/a | 0 |
| larger | 10 | 20 | 200 | 1 | OPTIMAL | 10352 | 10352 | 3.708 | valid | 40 |

**Candidates** = eligible employee×shift pairs after hard eligibility pruning (availability, PTO, max shift hours, prior rest) — i.e. Boolean variables that can exist in the model.

### Notes on these rows

- `demo-feasible` / `demo-infeasible` are the shipped Northwind Ward CSV scenarios under `backend/app/data/`.
- `tiny` / `small` / `medium` / `larger` are generated in the script (UTC, full availability, no skill rows, demo soft weights) for size scaling only. `medium`/`larger` use `required_count=2`.
- Wall time can exceed `max_deterministic_time`; the deterministic budget is a CP-SAT search parameter, not a hard process kill.
- `FEASIBLE` with objective ≠ bound means a feasible roster was found but optimality was **not** proven within the budget (`demo-feasible`, `medium`).
- `INFEASIBLE` means no assignment satisfies the configured hard constraints. It is **not** a labor-law or “legally prohibited” judgment — see [ALGORITHM.md](ALGORITHM.md#status-semantics).

## Reproducibility check (same session)

`demo-feasible`, seed 1, two consecutive solves:

| Check | Result |
| --- | --- |
| Equal assignment tuples | True |
| Objectives | 8788, 8788 |
| Statuses | FEASIBLE, FEASIBLE |

## Earlier demo seed-42 row (same machine, same day)

Documented during README evidence capture (same hardware/env; seed **42**):

| Instance | Emp × shifts | Seed | Status | Objective | Bound | Runtime (s) | Validator |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| demo-feasible | 5 × 21 | 42 | FEASIBLE | 8788 | 8647 | ~4.57 | valid |

## What this does **not** claim

- Production ward scale, multi-site throughput, or cloud SLAs
- Labor-law compliance or certified staffing legality
- That `FEASIBLE` equals proven `OPTIMAL`
- Cross-machine runtime equality (hardware and OS differ)
- Bit-identical wall clocks across consecutive runs (assignments are the reproducibility invariant)

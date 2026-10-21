# Performance baseline (this session)

Measured wall times from a real local run of `backend/scripts/micro_benchmark.py` on **2026-10-21**.  
`docs/BENCHMARK.md` remains a historical snapshot (2026-10-20) and is **not** this-session evidence.

## Command

```powershell
cd backend
uv run python scripts/micro_benchmark.py
```

## Environment (measured)

| Item | Value |
| --- | --- |
| Host | hasanyetkiner |
| Machine | HP Victus by HP Laptop 16-e0xxx |
| CPU | AMD Ryzen 5 5600H with Radeon Graphics (6 cores / 12 threads) |
| RAM | ~15.7 GB |
| OS | Windows 11 Enterprise · 10.0.26300 |
| Python | 3.12.10 |
| OR-Tools | 9.15.6755 |
| Mode | `reproducible` |
| Seed | 1 |
| `num_workers` | 4 (capped) |
| `max_deterministic_time` | 8.0 s |
| Reps | 1 ladder pass + 2 consecutive `demo-feasible` solves for equality |
| Date measured | 2026-10-21 |

## Results (measured 2026-10-21)

| Instance | Emp | Shifts | Candidates | Seed | Status | Objective | Bound | Runtime (s) | Validator | Assignments |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- | ---: |
| tiny | 3 | 5 | 15 | 1 | OPTIMAL | 1400 | 1400 | 0.050 | valid | 5 |
| small | 5 | 14 | 70 | 1 | OPTIMAL | 3856 | 3856 | 5.615 | valid | 14 |
| demo-feasible | 5 | 21 | 101 | 1 | FEASIBLE | 8788 | 8613 | 14.331 | valid | 28 |
| medium | 8 | 14 | 112 | 1 | OPTIMAL | 8200 | 8200 | 11.684 | valid | 28 |
| demo-infeasible | 5 | 22 | 106 | 1 | INFEASIBLE | — | — | 0.001 | n/a | 0 |
| larger | 10 | 20 | 200 | 1 | OPTIMAL | 10352 | 10352 | 0.973 | valid | 40 |

## Reproducibility check (same session)

`demo-feasible`, seed 1, two consecutive solves:

| Check | Result |
| --- | --- |
| Equal assignment tuples + objective | True |
| Objectives | 8788, 8788 |
| Statuses | FEASIBLE, FEASIBLE |

## What this does **not** claim

- Production ward scale, multi-site throughput, or cloud SLAs
- Labor-law compliance
- That wall clocks are bit-identical across machines or consecutive days (they vary; assignment equality is the reproducibility invariant)
- Docker compose performance (Docker remains blocked in this workspace)

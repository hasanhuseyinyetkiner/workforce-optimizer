# Security boundaries

Workforce Optimizer is a **local CP-SAT roster demo**, not a multi-tenant SaaS or production HR system.

## Assumptions

- Default API bind is loopback (`127.0.0.1:8103`). Non-loopback hosts require `ALLOW_NETWORK_BIND=true` (see `.env.example` and `backend/app/config.py`).
- Demo auth: **none**. Treat the API as trusted-local only.
- Intended data is **synthetic** (Northwind Ward). Do not load real employee PII, medical details, or production rosters.
- CORS defaults to the paired demo UI origins (`127.0.0.1:5103` / `localhost:5103`). CORS is not authentication.
- CP-SAT worker count is capped (`SOLVER_NUM_WORKERS`, default 4) so a local solve cannot monopolize the machine by default.
- Independent validator paths re-check hard constraints in pure Python; they do not grant network or filesystem privileges beyond the app process.

## What this is not

- Not a labor-law compliance engine. Solver `INFEASIBLE` means “no assignment under configured hard rules,” not “legally prohibited.”
- Not a production security posture (no authn/z, tenancy, audit log retention, or secrets management).
- Not a claim that dependencies, containers, or the demo DB are vulnerability-free.

## Reporting

This repository is a portfolio demo. If you find a security issue in the published code, open a private report with the repository owner rather than filing a public issue with exploit detail.

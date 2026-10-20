# CURSOR AGENT PROMPT — WORKFORCE OPTIMIZER

Act as a senior operations-research engineer, constraint-programming expert, Python engineer and React product developer. Build **Workforce Optimizer**, a fully functional and visually polished open-source employee scheduling app. Implement executable code and verify outputs with an **independent schedule validator**. Read `.cursor/rules/*.mdc` where present. Use small complete implementation slices, not unfinished mockups.

## Product concept

Operations managers configure employees, skills, demand by shift, availability, PTO and staffing preferences. The app constructs a feasible shift plan, optimizes costs/fairness where possible, explains the result and exports an audit-ready roster. **Do not market mathematical optimization as generative AI.** The project demonstrates actual computational engineering.

## Stack

- Python 3.12+, Google OR-Tools CP-SAT (verified supported API), FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, pytest, Ruff.
- React + Vite + TypeScript, Tailwind, FullCalendar (check suitable current license), Recharts, TanStack Query, React Router, Lucide.
- Docker Compose, GitHub Actions, Vitest, Playwright.
- For an MVP, keep solve jobs bounded to a documented small planning horizon and employee count; add async queue only if justified by measured blocking.

## Domain model

Employee(id, name/display alias, skills, weekly hour cap, preferences), Skill, ShiftTemplate(duration/start/end), ShiftInstance(date/start/end/required_count/required_skills), Availability, TimeOff, Ruleset(hard_constraints, soft_weights, active dates), Assignment, OptimizationRun(status, solver_status, objective, bound, runtime, seed), ScheduleVersion.

Use timezone-aware timestamps. Define a planning time zone per organization. Hours crossing midnight must be assigned correctly. Add demonstration employees and skills without real PII.

## Hard constraints (all independently testable)

1. Shift staffing coverage at or above a defined minimum and required skill coverage. Do not quietly treat unmet minimums as valid.
2. One employee cannot work overlapping shifts.
3. Employee must be available and not on leave.
4. Rest-period constraints and configurable max shift hours or weekly caps; previous scheduling boundary and overnight shifts accounted for.
5. Required skills must be present on assigned employees; distinguish skill coverage per shift from required headcount.
6. Optional constraints: max consecutive work days, local rule configuration, individual restrictions.
7. If infeasible, report **INFEASIBLE** with useful diagnostics, never fabricate a compliant schedule. For diagnosing conflicts, use progressive relaxations/explanation as a best effort, clearly labeled not a minimal unsatisfiable core unless proven.

## Soft objectives

Minimize configurable weighted penalties for unequal shift distribution, preference violations, overtime, understaffing **only in a clearly named relaxed scenario**, unbalanced nights/weekends and cost. Explain weighting and trade-offs; publish objective breakdown in UI. First get valid feasible plans, then optimization.

## Product UI

- Overview KPI tiles (coverage, hours, objective score, solve status, fairness distribution).
- Employees + skills + availability editor.
- Rules wizard with hard/soft labels and validation hints.
- Shift demand calendar; sample template selection.
- Solve screen with progress/status and solved/feasible/infeasible/unknown distinctions.
- Drag-free schedule/calendar viewer initially (manual editing only in later stage, always revalidate); per-employee hours and rule explanations.
- Scenario comparison: baseline vs changed staffing or preferences; differences and objective scores with matched rules.
- Export CSV and ICS (correct timezone), plus validator summary.

## API

Suggested endpoints: `POST/GET /api/employees`, `POST/GET /api/shift-templates`, `POST/GET /api/shifts`, `POST /api/rulesets`, `POST /api/optimization-runs`, `GET /api/optimization-runs/{id}`, `GET /api/schedules/{id}`, `POST /api/schedules/{id}/validate`, `GET /api/schedules/{id}/export.csv`, `GET /health`. Use typed payload schemas and clear error responses.

## Solver accuracy / tests

- Solver statuses must be displayed accurately: OPTIMAL vs FEASIBLE vs INFEASIBLE vs UNKNOWN, with objective and best bound where available.
- Build a **separate pure-Python validator** that rechecks every hard constraint without calling the solver.
- Test 2–4 tiny known-optimum instances against manual/exhaustive enumeration; test overnight shift, PTO, no qualified employee, insufficient staff, adjacent rest violations and empty input.
- Use explicit reproducible solver settings; allow reasonable time limit. Solve timeouts are not optimality proofs.
- Test shifts crossing DST transitions or explicitly document limitations and reject unsafe timezones if necessary.
- At least one Playwright smoke test: import demo -> adjust a constraint -> generate plan -> inspect validator -> export.

## Security and honest scope

No guarantee of labor-law compliance. Legal and collective-bargaining constraints vary by locale and must be configured and externally validated. Employee schedules may be personal data; protect exports and logs. MVP can be local demo, but public multi-user hosting requires auth/authorization. Never auto-publish workforce data.

## README / GitHub product polish

English headline: "Constraint-based scheduling that explains every shift assignment." Actual calendar/dashboard screenshot near top; capability highlights; an accurate diagram of input -> constraint model -> CP-SAT -> validator -> schedule; full reproducible Quick Start; small sample scenario and measured result; example of an infeasible case; description of hard vs soft constraints, objective and solver status; tests and benchmark protocol; truthful limitations; docs/API/CSV examples; license/contribution guide. Add an informative `docs/ARCHITECTURE.md` and `docs/ALGORITHM.md`. `docs/GITHUB_METADATA.md` description `Open-source workforce scheduling with OR-Tools CP-SAT, explainable constraints and independent validation.` Topics: `operations-research`, `or-tools`, `optimization`, `scheduling`, `fastapi`, `react`, `python`, `workforce-management`.

## Deliverables & phases

Phase 1: PostgreSQL schema + CSV/demo seed, employee/shift/rules CRUD, real frontend views, Docker boot.
Phase 2: CP-SAT model, independent validator, bounded solve API, tiny-case correctness tests.
Phase 3: interactive schedule/calendar, outcomes, export, scenario comparison, E2E tests and accessibility.
Phase 4: clean CI/build, actual screenshots, benchmark with measured instances, truthful polished README, reproducible Docker start.

**Acceptance:** Running the sample instance generates a schedule the validator independently accepts; a deliberately infeasible instance is clearly flagged; an actual browser UI lets people inspect the results; no fake claims or unrun tests. Implement, test and report exact results. Do not deploy/push without permission.

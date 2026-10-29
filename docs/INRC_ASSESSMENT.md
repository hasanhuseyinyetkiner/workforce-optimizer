# INRC-I benchmark assessment

Checked 2026-10-29. There is no INRC result for this project: the shipped inputs are synthetic, and the solver does not implement the competition formulation.

## Source and permission

The [organizers' INRC2010 page](https://watt.cs.kuleuven.be/node/820) links the official [instance archive](https://patat.cs.kuleuven.be/sites/patat.cs.kuleuven.be/files/inrc1/instances.zip), input and solution schemas, and an evaluator. It describes sprint, medium and long tracks and publishes finalist rankings. The [competition specification](https://patat.cs.kuleuven.be/sites/patat.cs.kuleuven.be/files/inrc1/nrpcompetition_description.pdf) defines the problem, file formats and evaluation procedure.

The archive downloaded on 2026-10-29 had SHA-256 `e4e8d922c4e4a65eb50186a607a25be72e0a9100bcb786058146c1b431e6a4c2`. The organizer page and specification did not state a data license in the material reviewed, and a filename search of the outer archive and its nested ZIPs found no license, copyright, terms or README files. This is not proof that permission does not exist. Redistribution and reuse terms remain unverified; neither the instances nor the evaluator are bundled here. The project's MIT license does not establish a license for third-party data.

## Why the scores are not comparable

| Dimension | INRC-I | This project |
| --- | --- | --- |
| Feasibility | Required shifts are assigned and at most one shift per nurse per day; contract constraints are scored as soft violations. | Coverage, availability, rest, weekly hour caps and configured consecutive-day limits are hard rules; optional understaffing changes coverage. |
| Objective | Weighted violations of the instance's contract and request constraints, evaluated in the competition format. | Weighted cost, preference, overtime and workload/balance terms, optionally including understaffing. |
| Input/output | Competition instances and solution formats, with an organizer-provided evaluator. | Application-specific employees, shifts, rules and assignment records; no INRC parser or solution exporter. |
| Run conditions | Track-specific, machine-benchmarked CPU limits; historical rules specify a single processor. | The synthetic micro-benchmark uses CP-SAT deterministic time and up to four workers. |

The project validator independently checks this application's rules, not INRC feasibility or scoring. Translating only coverage and employees while dropping contracts or requests would define a different problem. Even if the resulting schedule happened to pass the official evaluator, the application's objective and solver bound would not be comparable to INRC scores or rankings.

## What a defensible benchmark would require

1. Establish the rights to use and, if needed, redistribute specific instances and evaluator; record source, version, checksum and any permission. Public download availability alone does not establish a license. INRC describes realistic problem constraints, but this does not establish that a particular instance contains actual employee records.
2. Implement and test an instance importer and solution exporter against the official schemas, preserving all relevant contracts, requests, weights and calendar semantics. Reject unsupported features explicitly rather than silently dropping them.
3. Implement the same hard constraints and weighted soft objective as the specification. Cross-check feasible and deliberately invalid solutions, including penalty breakdowns, with the official evaluator.
4. Record exact instances, solver and evaluator versions, parameters, seed, hardware, limits, status and raw outputs. Use comparable run conditions when comparing results; report feasibility and score only after official evaluation.

Until these steps are completed, the [synthetic performance baseline](PERFORMANCE_BASELINE.md) is useful only for observing this project's own behavior, not as evidence of performance on real rosters or against competition entries.

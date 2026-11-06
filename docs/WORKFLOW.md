# Team workflow

Two people, two roles, one `main` that always runs.

| Role | Default owner | Focus |
|---|---|---|
| A: Engine | AleksPolishcuk | detector, physics residuals, sensor-vs-machine arbiter, diagnosis, alert policy, scorer, test-pump CSV |
| B: Cockpit | devExponent | repo hygiene, API, operator interface, integrations (Gemini, n8n, ElevenLabs), demo video, technical note, submission |

Owners can be swapped. If you swap, move the issue assignees too.

## Branches

- `main`: always runs. The demo and the submission come from here. No force-push.
- `a/engine`: long-lived branch of the Engine owner.
- `b/cockpit`: long-lived branch of the Cockpit owner.
- Optional short topic branches: `a/<topic>`, `b/<topic>`.

Merge into `main` through a pull request at least every 3 hours. Merge `main` into your branch first. The other person reviews quickly. If they are asleep, self-merge once the relevant check passes. Tag milestones on `main`: `v0.1-baseline-reproduced`, `v0.5-safe-submission`, `v1.0-submission`.

## Who touches which paths

| Owner | Paths |
|---|---|
| A: Engine | `src/watchkeeper/ingest`, `features`, `detect`, `diagnose`, `alerts`, `sandbox`; `eval/`; `tests/`; `submission/predictions_test.csv` |
| B: Cockpit | `web/`; `src/watchkeeper/api`, `explain`; `automation/`; `docs/` (except the contract); `submission/` (except the CSV); `README.md` |
| Both | `pyproject.toml`, `Makefile`, `CLAUDE.md`, the alert contract |

Do not edit the other person's paths without telling them first. This keeps merges clean.

## Contract

The alert format is in `docs/PLAN.md`, section 6. Issue "Agree alert contract and mock alerts" turns it into `docs/alert.schema.json` and `docs/mock_alerts.json`. Changing it needs both people. The engine writes alerts to `artifacts/alerts/<asset_id>.json`, and the API reads them from there. Until the engine is ready, the API serves `docs/mock_alerts.json`.

## Issues, labels and milestones

Labels: `engine`, `cockpit`, `shared`, `p0` (critical path), `stretch` (only after the core works).

Milestones (Turku time, EET):

| Milestone | Due | Meaning |
|---|---|---|
| M1 Walking skeleton | Sat 7 Nov 01:30 | replay, detector, alerts, API and screen work end to end, even with baseline logic |
| M2 Safe submission | Sat 7 Nov 20:00 | a complete, valid, weaker submission exists |
| M3 Final submission | Sun 8 Nov 09:30 | submitted on sinceai.app. The hard deadline is 10:00 |

Rules that apply to every task are in `CLAUDE.md`. In short: advice only, no write path, causal alerts, never tune on the test pumps, keys only in `.env`.

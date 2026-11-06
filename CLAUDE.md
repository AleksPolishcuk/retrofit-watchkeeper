# Project rules for AI agents

Watchkeeper is a read-only operator-assist layer for existing cooling-water pumps (challenge RETROFIT AI, Since AI Hackathon 2026). These rules are hard constraints. Do not relax them to make a metric look better.

## Safety
- Advice only. No code path may write to a pump, drive, valve, PLC, safety system or ship system. Adapters publish or read, never subscribe to command topics.
- The sandbox (`retrofit_sim what_if`) is for simulated comparison only.
- No claims of certification, class approval, guaranteed fault identification or proven savings.

## Causality
- An alert at time t may use only telemetry with timestamps <= t, plus static information (`assets.csv`). Batch processing is fine as long as every alert respects this.
- `make test` includes a truncation test: cut telemetry at random points, re-run, and the alerts before the cut must be identical.

## Test data
- PUMP-10, PUMP-11 and PUMP-12 are the test pumps. Never hand-label them, never tune thresholds or models while looking at them.
- Fit on train (PUMP-01..07). Select models on validation (PUMP-08, 09), and compare methods with leave-one-asset-out over PUMP-01..09. The validation split has only 9 scored events, so differences of a few points are noise.
- Evaluation code must not read test telemetry. `make predict` runs from a tagged commit and records that commit next to the CSV.

## Alert policy (matches the scorer in `retrofit_sim/scoring.py`)
- `event_class` must be `MACHINE` or `SENSOR`, otherwise the file is rejected.
- Alerts less than 5 minutes apart on one asset merge into one burst. A burst naming several fault types earns no type credit, and one naming both classes earns no class credit. Raise one alert per problem.
- False alerts and excess repeats are penalised. One reminder episode per 12 hours is free.
- `UNKNOWN` earns detection credit but no fault-type credit. Use it only when the cause is genuinely unclear.

## Secrets
- Keys live in `.env` only, on the backend only. Never commit them, print them or paste them into chat. `.env.example` lists the names.
- Every integration (Gemini, ElevenLabs, n8n, FIWARE) is optional and needs a fallback. The core pipeline must not depend on any of them.
- An LLM may only word explanations from structured evidence that the pipeline already computed. It never decides whether to alert.

## Data
- The organizers' data pack is not in this repo. `data/` is a symlink created by `scripts/link_data.sh`.
- Keep attribution in README and NOTICE: "RETROFIT AI 2026 synthetic pump benchmark, Since AI Hackathon 2026".

## Working agreement
- Two people, two branches: `a/...` for the engine, `b/...` for the cockpit. `main` always runs.
- Agree the alert JSON contract first (see `docs/PLAN.md`, section 6). The UI works on mock alerts until the engine is ready.
- Record the AI tools used in `submission/SUBMISSION.md`.

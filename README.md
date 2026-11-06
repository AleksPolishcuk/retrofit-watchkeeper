# Watchkeeper

Read-only operator-assist layer for existing cooling-water pumps.

Built by team **Nordic Forge** at the Since AI Hackathon 2026 (Turku, 6-8 November 2026) for the challenge **RETROFIT AI: Make Existing Machines Intelligent** (challenge owner Business Turku, technical sparring partner Elomatic).

> **Advice only. No write path.** Watchkeeper reads telemetry and recommends actions for a human to approve. It never sends commands to a pump, drive, valve, PLC or safety system.

## What it will do

1. Ingest or replay pump telemetry (read-only, MQTT-style messages).
2. Detect developing machine and instrument problems early, taking the operating regime into account.
3. Tell a sensor fault from a machine fault.
4. Show the evidence behind every alert and say how certain it is.
5. Recommend an inspection or maintenance action for a human to review.
6. Optionally compare an intervention in the provided digital sandbox (simulation only).

## Status

Scaffold only. Nothing is measured yet. Results, baseline comparison and limitations will be added here as they exist.

## Layout

```
src/watchkeeper/   ingest, features, detect, diagnose, alerts, explain, sandbox, api
web/               operator interface
eval/              evaluation scripts and result tables
automation/n8n/    exported human-approval workflow
docs/              team plan, technical note, architecture, business case
submission/        test-pump alert CSV and submission notes
scripts/           data linking and demo helpers
```

## Run

The organizers' data pack (`RETROFIT_AI_PARTICIPANTS_2026`) is not stored in this repository. Point to your local copy:

```bash
make setup
make setup-pack PACK=/path/to/RETROFIT_AI_PARTICIPANTS_2026
make data PACK=/path/to/RETROFIT_AI_PARTICIPANTS_2026
```

`make eval`, `make predict`, `make api`, `make web`, `make demo` and `make test` are placeholders until the matching parts exist.

## Data and attribution

All data are synthetic. See [NOTICE](NOTICE). Data: "RETROFIT AI 2026 synthetic pump benchmark, Since AI Hackathon 2026" (CC BY 4.0). Simulator, scorer and baselines from the data pack are MIT-licensed.

## AI tools used

To be completed before submission.

## Limitations (preliminary)

- The data are synthetic and come from a reduced-order simulator. Fault growth is compressed into a 7-day window.
- Seal leakage and electrical rotor or stator faults are not part of the benchmark.
- Results on this benchmark are not evidence of field performance, and nothing here is certified for operational use.

## License

MIT, see [LICENSE](LICENSE).

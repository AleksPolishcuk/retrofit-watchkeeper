# Watchkeeper

Read-only operator-assist layer for existing cooling-water pumps.

Built by team **Nordic Forge** at the Since AI Hackathon 2026 (Turku, 6-8 November 2026) for the challenge **RETROFIT AI: Make Existing Machines Intelligent** (challenge owner Business Turku, technical sparring partner Elomatic).

> **Advice only. No write path.** Watchkeeper reads telemetry and recommends actions for a human to approve. It never sends commands to a pump, drive, valve, PLC or safety system. The API has GET routes only, and a test fails if that changes.

## What it does

1. Replays or ingests pump telemetry: the recorded one-minute averages, or the organizers' raw replay stream (one message per second), which a read-only adapter turns into the same one-minute readings (`make live-demo`, see below).
2. Learns each pump's own normal at each operating point, using only data from before the moment being judged (causal; a truncation test enforces it).
3. Raises an alert when a deviation persists, says whether it looks like a **machine** problem or an **instrument** problem, and names the most likely fault type.
4. Shows the evidence behind every alert, what limits our certainty (missing channels, instrumentation level), what it may mean and what to check first.
5. Uses graded words (Watch, Possible, Likely, Very likely) backed by back-test counts, never percentages that pretend to be calibrated.
6. Recommends an inspection or maintenance action for a human to approve, and can compare an intervention in the organizers' simulation sandbox (simulation only).
7. Says so when its own data are the problem: a silent gateway, a lost channel or speed signal, rows without measurements, a pump still learning its normal, quality flags, unit mix-ups (the **Data check** in the case view). Silence from the detector is never read as a healthy pump.
8. Keeps a review log of what people decided, in the browser only: Open, On inspection, Result recorded, Recovery check, Closed. An inspection ends as no fault found, needs further inspection, or fault confirmed with the actual fault recorded next to what the model suggested. A new case of a kind already seen on the same pump is flagged as a possible return. The log has a summary (confirmed share, time to first decision) and a CSV and JSON export. The API never writes. `make archive` keeps an immutable snapshot of the alerts per model version, so a re-run does not erase what was shown before.

## Live replay (raw messages in, alerts out)

`make live-demo` replays the public validation pump PUMP-08 as raw messages (`python -m retrofit_sim replay`, one per second), turns them into one-minute readings, re-runs the detector and writes `artifacts/live/PUMP-08/state.json`. The Monitor tab shows it as a **Live replay** strip (as-of time, data check, alerts as they appear). The adapter (`src/watchkeeper/ingest/`) only reads: no publish, no subscribe, no command topic. A test fails if a write or subscribe path appears.

- Minutes built from raw messages equal the organizers' `features_1min` (largest difference 3e-5, float32 rounding) on a retrofit, a fully instrumented and a legacy pump.
- The live run gives exactly the alerts of one batch run over the same minutes (PUMP-08, three alerts, same time, type and confidence).
- Duplicates, out-of-order and late messages, unparsable lines and non-telemetry topics are counted and handled, never fatal.
- Cost: the adapter handles about 21,000 messages per second; the detector re-run takes 1 to 3 seconds for up to a week of history on one core and grows with the history. An incremental scorer would remove that growth; it is not built.

Numbers and method: `eval/results/live_replay.md`. The prototype has been run on a replay of recorded data, not on a live plant feed.

## Measured results

Everything below is on **synthetic** data, scored by the organizers' own scorer (`retrofit_sim.scoring`). It shows how the method behaves on this benchmark. It is not evidence of performance in a plant.

The numbers in this table come from a model fitted only on fleets generated with the organizers' simulator (`models/wk.joblib`), never on the public pumps or on the fleets being scored. Hold fleets were opened once, after the method was frozen. The model that wrote the test-pump predictions (`models/wk_final.joblib`) is the same method refitted on the simulator fleets plus the labelled public pumps, so its own numbers on those pumps are not shown.

| Set | Watchkeeper | Organizers' mode-aware baseline B1 | Random alerts |
|---|---|---|---|
| **Untouched hold fleets** (24 pumps, 82 events) | **62.8** (95% interval 55 to 70) | 52.1 (44 to 60) | 36.0 |
| Tuning fleets (16 pumps, 48 events) | 59.9 (50 to 70) | 42.9 (35 to 51) | 37.5 |
| 9 public development pumps (35 events) | 67.1 (58 to 73) | 63.4 | 43.6 |
| Organizers' own split: 7 train pumps / 2 validation pumps | 63.0 / 79.5 | 58.2 / 78.0 | |
| Masked-clogging trap (3 pumps, 6 events) | 48.1 | 52.1 | 40.9 |

- An alert-free detector scores 10. The plant's existing alarms score 23 on the organizers' validation split.
- The 2-pump validation split has 9 events, so differences of a few points there are noise.
- Intervals resample pumps (1000 draws). Full table, tier and fault-type breakdown: [eval/results/final/report.md](eval/results/final/report.md).
- **False alerts:** on 294 pump-days of healthy simulated pumps, 1.3 false episodes per pump-month (upper 95% bound 2.3). That is still more than an operator would accept; see limitations.
- **Sensors missing:** [eval/results/missing_sensor.md](eval/results/missing_sensor.md) removes whole channels from the hold fleets.
- **Likelihood words:** counts per level from held-out back-tests are in `models/stages.json` and in the Proof tab.

### What did not work

- Fusing weak shifts across channels along each fault's signature, plus a slow cumulative-sum detector, was built and tested. It found more events, but added false alerts and no earlier warning. It stays in the code, switched off: [eval/results/signature.md](eval/results/signature.md).
- Three data-quality options were gated before use (`eval/results/data_quality_gate.md`): handling of a lost speed signal passed and is on; a stricter frozen-sensor rule loses real events and stays off; reporting a six-to-twelve hour sustained deviation that the model calls normal closes a real gap but adds false alerts, so it stays off (cautious pilot setting: 12 hours).
- Using the operating context (cooling demand, supply water and ambient temperature) was tested in four ways: as part of the operating-point key, as a fluid temperature relative to the supply water, as classifier features, and combinations. None met the adoption rule that was fixed before the runs (healthy false alerts 1.3 per pump-month stayed or rose; scores moved within noise), so the submitted method does not use it: [eval/results/context.md](eval/results/context.md). A better model of normal operation would need each loop's physics, not more bins.

## Test-pump predictions

`submission/predictions_test.csv` has 33 alerts for PUMP-10, 11 and 12, produced once from git tag `freeze-v1` by `make predict`. `predictions_test.meta.json` records the commit, the tag, a clean-tree flag and the model file's SHA-256. Test pumps were never used for fitting, selection or threshold choice.

## Run it

The organizers' data pack (`RETROFIT_AI_PARTICIPANTS_2026`) is not stored in this repository. Point to your local copy:

```bash
make setup
make setup-pack PACK=/path/to/RETROFIT_AI_PARTICIPANTS_2026
make data PACK=/path/to/RETROFIT_AI_PARTICIPANTS_2026
make test                      # unit tests, truncation (causality) tests, review log logic (needs Node 22.18 or newer, skipped otherwise)
make api                       # read-only API on http://127.0.0.1:8000
make web                       # interface on http://localhost:5173
make alerts                    # optional: rewrite artifacts/alerts (committed; needs models/wk.joblib from `make model`)
make live-demo                 # optional: replay PUMP-08 as raw messages through the read-only ingest (a few minutes); shows in Monitor
make archive                   # optional: immutable snapshots of artifacts/alerts per model version
```

If the interface says "These are demo alerts" or the priority filter shows nothing, the alert files are missing or old: `artifacts/alerts/*.json` is committed, so `git pull`, restart `make api` and reload. After training the models yourself, `make alerts` rewrites them (byte-identical for the same model). `models/*.joblib` and `bank/` are not committed.

To regenerate the models and numbers (about 25 minutes on 8 cores):

```bash
make bank                      # simulated fleets from the organizers' simulator, into bank/ (not committed)
make model                     # models/wk.joblib (bank only) and models/wk_final.joblib (bank + public pumps)
make report                    # eval/results/final/report.md, tuning and tune/dev/trap/healthy sets
make levels                    # models/stages.json
make predict                   # needs a clean working tree
```

`make report` leaves the hold fleets alone; `eval/run_report.py --hold` opens them and should be run once, at freeze.

## Layout

```
src/watchkeeper/   features (causal baselines, NPSH, input hygiene), detect (alert timing, cavitation, data health, range check), diagnose (model, knowledge),
                   ingest (raw replay messages to minutes, live runner), incidents, stage words, alerts (contract v2, archive), what-if, api
web/               four tabs: Monitor (data, what looks wrong, how sure, what to do), Value, Proof, Retrofit (React, TypeScript, Vite; Inter and IBM Plex Mono bundled, no external font requests)
eval/              experiments, probes, results tables
scripts/           bank generation, data linking
docs/              plan, audit, alert contract (JSON schema), business case, edge and transfer, technical note, demo script
submission/        test-pump alerts and submission notes
```

## Data and attribution

All data are synthetic. See [NOTICE](NOTICE). Data: "RETROFIT AI 2026 synthetic pump benchmark, Since AI Hackathon 2026" (CC BY 4.0). Simulator, scorer and baselines from the data pack are MIT-licensed.

## AI tools used

- **Claude** (Anthropic), through Claude Code, was used to analyse the challenge material, write and review code, run experiments and draft documentation. A human reviewed and directed the work.
- **No language model runs in the product.** Alerts, evidence, stage words and wording come from the pipeline and fixed templates. Optional integrations are not required and are not enabled.

## Limitations

- The data are synthetic and come from a reduced-order simulator. Fault growth is compressed into a 7-day window. Seal leakage and electrical rotor or stator faults are not part of the benchmark.
- The fault **type** is right for only about two in five faults, and machine faults are often named as instrument drift. The machine-or-instrument **class** is right more often (about three in five), and every alert says which instrument to check first.
- Masked suction clogging on the trap fleets is a weak spot: below the baseline, and the type is never named.
- False alerts on healthy simulated pumps are about 1.3 per pump-month, mostly at operating points not seen in the first 24 hours. A pilot would tune this with operators.
- Bad data: of the 18 controlled situations of the organizers' enterprise reference, 11 are handled, 5 partly, and 2 are known gaps (a large deviation of 20 minutes that the classifier calls normal, and a value constant inside each minute that is called frozen). The Proof tab lists all 18; options that did not pass our own gate are off (`eval/results/data_quality_gate.md`).
- The live replay re-runs the detector on all minutes received, so one run takes 1 to 3 seconds for up to a week of history and grows with it. It was run on replayed recorded data, not on a plant feed.
- The review log lives in one browser. There are no roles, owners, escalation, work orders or maintenance-system integration.
- No time-to-failure estimate is given ("not estimated"); stage words come from back-test counts on this simulator only.
- Not certified, not class-approved and not a safety system. Existing alarms and trips remain authoritative.

## License

MIT, see [LICENSE](LICENSE).

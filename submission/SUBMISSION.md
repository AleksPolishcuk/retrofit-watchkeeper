# Submission: Watchkeeper (team Nordic Forge)

Challenge: RETROFIT AI, Make Existing Machines Intelligent (Business Turku, with Elomatic). Since AI Hackathon 2026, Turku.

## Deliverables

| Asked for | Where |
|---|---|
| Working prototype: ingest or replay, detect, evidence and uncertainty, recommended action | `make api` and `make web`; the Alerts page replays the data up to the alert; `make live-demo` streams raw replay messages through the read-only ingest and the detector (`src/watchkeeper/ingest/`, `eval/results/live_replay.md`); code in `src/watchkeeper/` and `web/` |
| Alerts for the 3 test pumps in the template format | `submission/predictions_test.csv` (33 alerts) with `predictions_test.meta.json` (commit, tag `freeze-v1`, model SHA-256) |
| Code and run instructions | `README.md` (Run it), `Makefile` |
| Comparison with the provided baselines | `README.md` (Measured results), `eval/results/final/report.md` |
| Honest limitations | `README.md` (Limitations), Proof tab of the interface, `docs/TECHNICAL_NOTE.md` |
| Short demo | `docs/DEMO_SCRIPT.md` (storyboard for a 3 minute recording: Overview, Alerts, Proof, Value, Retrofit) |
| Optional: what-if in the sandbox | Alerts page, step 4, "Try it in the simulator" for strainer, bearing and alignment alerts (simulation only) |
| Optional: edge design and transfer plan | `docs/EDGE_AND_TRANSFER.md`, Retrofit tab |
| Optional: business case | `docs/business_case.md` (assumptions labelled, measured inputs from untouched fleets) |

## How this answers the five jury criteria

| Criterion (weight) | What we offer | Where to see it |
|---|---|---|
| Operational value (25%) | Early, explained, actionable alerts: 6 of 15 faults that reached the plant's alarm limit were flagged before it (0.3 to 77 h); machine-or-instrument class right on 59% of faults (baseline 50%); every alert says what to check first, and a person's decisions are kept in a browser-local review log (inspection result with the actual fault, recovery check, returns, export); false alerts 1.3 per pump-month on healthy pumps; business case with every money figure labelled as an assumption and the unfavourable cases shown | interface tab **Value**, `docs/business_case.md` |
| Technical quality (25%) | Causal per-pump baseline by operating point with regime learning, learned fault typing, physical cavitation check; 62.8 on 82 events from untouched fleets against 52.1 for the organizers' baseline and 36 for random alerts; bootstrap intervals; negative results published | tab **Proof**, `docs/TECHNICAL_NOTE.pdf`, `eval/results/` |
| Reliability and safety (20%) | Read-only by construction and by test; causality enforced by a truncation test; human approves every action; uncertainty stated (four level words with back-test counts, missing channels, instrumentation level, time to act "not estimated"); sensor-versus-machine call; missing-sensor test; behaviour under bad data tested on the 18 controlled situations of the enterprise reference (11 handled, 5 partly, 2 known gaps, all listed); test pumps never used | tab **Proof** (sections 2 and 3), `tests/` |
| Low-cost retrofit and transfer (20%) | Works on the data a pump already has; tested with legacy, retrofit and full instrumentation and with channels removed; edge footprint measured (6.6 MB, 1.3 s per pump-week, one core); read-only integration, pilot path and what does and does not transfer | tab **Retrofit**, `docs/EDGE_AND_TRANSFER.md` |
| Working demo and clarity (10%) | One four-step flow per case: the data (replayed as it arrived), what looks wrong, how sure we are, what to do; plain wording; runs offline with `make demo` | page **Alerts**, `docs/DEMO_SCRIPT.md`; accessibility (axe clean, contrast test, keyboard, 320 px): `docs/ACCESSIBILITY.md` |

## How the test-pump file was made

1. The method was frozen at git tag `freeze-v1`, with a clean working tree.
2. `make predict` loaded `models/wk_final.joblib` and wrote the CSV once. Nothing is trained at predict time. The meta file records the commit, the tag, `dirty: false` and the model's SHA-256.
3. The test pumps (PUMP-10, 11, 12) were never used to fit, select or tune anything. The evaluation code does not read their telemetry, and the API does not serve it.
4. After later code changes (interface, operating-context options that are switched off) the frozen model was run again into a scratch folder and produced the same 33 alerts with the same confidence values.
5. Every alert is causal: it uses only data up to its own timestamp. `tests/test_evalkit.py` cuts telemetry at several points and checks that earlier alerts do not change; the organizers' own baseline B1 fails that test, ours passes.

## History note

On 7 Nov 2026 the repository history was rewritten once to remove an assistant instruction file from every commit. Code, models and results are unchanged; all commit hashes changed.
The freeze commit that wrote the test-pump predictions is now `6dc3c93` (tag `freeze-v1`; it was `7d78408` before the rewrite). `submission/predictions_test.meta.json` records the new hash and, in `commit_before_history_rewrite`, the old one. The model hash and the CSV are untouched.

## Evidence discipline

- Fitted on fleets generated with the organizers' simulator (rules allow the simulator), not on the public pumps.
- Thresholds chosen on separate tuning fleets. Hold fleets (24 pumps, 82 events) opened once at freeze: Watchkeeper 62.8 (95% interval 55 to 70), organizers' baseline 52.1, random alerts 36.0.
- Healthy fleets (294 pump-days) measure false alerts: 1.3 episodes per pump-month.
- Negative results kept: signature fusion and slow cumulative-sum detection did not help (`eval/results/signature.md`); masked clogging is a weak spot (48.1 against 52.1 for the baseline).

## AI tools used

- Claude (Anthropic) through Claude Code: analysis of the challenge material, code, experiments, documentation. A human directed and reviewed the work.
- No language model runs in the product. Alert wording and evidence come from the pipeline and fixed templates.

## Licences and attribution

All data are synthetic: "RETROFIT AI 2026 synthetic pump benchmark, Since AI Hackathon 2026" (CC BY 4.0). The organizers' simulator, scorer and baselines are MIT. Our code is MIT (`LICENSE`).

## Safety statement

Advice only. No code path writes to a machine. Not certified, not class-approved, not a safety system; existing alarms and trips remain authoritative.

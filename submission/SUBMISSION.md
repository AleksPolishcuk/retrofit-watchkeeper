# Submission: Watchkeeper (team Nordic Forge)

Challenge: RETROFIT AI, Make Existing Machines Intelligent (Business Turku, with Elomatic). Since AI Hackathon 2026, Turku.

## Deliverables

| Asked for | Where |
|---|---|
| Working prototype: ingest or replay, detect, evidence and uncertainty, recommended action | `make api` and `make web`; pump view has a causal replay; code in `src/watchkeeper/` and `web/` |
| Alerts for the 3 test pumps in the template format | `submission/predictions_test.csv` (33 alerts) with `predictions_test.meta.json` (commit, tag `freeze-v1`, model SHA-256) |
| Code and run instructions | `README.md` (Run it), `Makefile` |
| Comparison with the provided baselines | `README.md` (Measured results), `eval/results/final/report.md` |
| Honest limitations | `README.md` (Limitations), Results page of the interface, `docs/TECHNICAL_NOTE.md` |
| Short demo | `docs/DEMO_SCRIPT.md` (storyboard for a 3 to 4 minute recording) |
| Optional: what-if in the sandbox | pump view, "Simulate" on strainer, bearing and alignment alerts (simulation only) |
| Optional: edge design and transfer plan | `docs/EDGE_AND_TRANSFER.md`, Retrofit page |
| Optional: business case | `docs/business_case.md` (assumptions labelled, measured inputs from untouched fleets) |

## How the test-pump file was made

1. The method was frozen at git tag `freeze-v1`, with a clean working tree.
2. `make predict` loaded `models/wk_final.joblib` and wrote the CSV once. Nothing is trained at predict time. The meta file records the commit, the tag, `dirty: false` and the model's SHA-256.
3. The test pumps (PUMP-10, 11, 12) were never used to fit, select or tune anything. The evaluation code does not read their telemetry, and the API does not serve it.
4. Every alert is causal: it uses only data up to its own timestamp. `tests/test_evalkit.py` cuts telemetry at several points and checks that earlier alerts do not change; the organizers' own baseline B1 fails that test, ours passes.

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

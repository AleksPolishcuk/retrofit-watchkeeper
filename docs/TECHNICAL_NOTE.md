# Watchkeeper: technical note

Team Nordic Forge. RETROFIT AI, Since AI Hackathon 2026. All data are synthetic; nothing here is evidence of field performance.

## 1. Problem and approach

Existing cooling-water pumps already carry a few sensors. The aim is to notice a developing machine or instrument problem early, say how sure we are and why, and recommend an inspection for a human to approve, without touching the control system. Watchkeeper is a read-only layer: it reads one-minute averages, learns each pump's own normal, alerts on persistent departures, tells instrument problems from machine problems, and shows its evidence.

## 2. Data and splits

The organizers' pack has 12 simulated pumps: 7 training and 2 validation pumps with labelled events, and 3 test pumps without labels. Pumps have three instrumentation levels (legacy, retrofit with a wireless vibration sensor reporting every 5 minutes, full). Because 35 labelled events cannot support model selection, we generated extra fleets with the organizers' own simulator (the rules allow it):

| Set | Fleets | Use |
|---|---|---|
| train | 5 fleets x 8 pumps | fit the fault-type model |
| healthy_train | 6 fleets, no faults | examples of normal operation (class NONE) |
| tune | 2 fleets | choose thresholds |
| healthy | 6 fleets, no faults | measure false alerts per pump-month |
| trap | 3 pumps | suction clogging with a partly hidden suction signal |
| hold | 3 fleets (24 pumps, 82 events) | opened once, after freezing |

The 9 public pumps are used for a second, independent comparison. The three test pumps are never loaded by any evaluation code.

## 3. Method

1. **Causal normal.** Each minute is compared with the pump's own median and robust spread at the same operating point (speed bin), from steady running only. The baseline grows over the first 24 hours, then freezes. A speed first seen after that is learned for two hours before it is judged (the organizers' version compares it with all baseline speeds, which gives z of about 20 for days on healthy variable-speed pumps).
2. **Trigger.** A robust z above 5 that persists 12 minutes. Gateway gaps and frozen values have their own counters and rules, so an outage during a long deviation still alerts. Sparse wireless channels are held for 6 minutes; thermal channels are ignored for 60 minutes after a restart.
3. **Diagnosis.** A random forest (60 trees, under 7 MB) on backward-looking features (z, 15-minute mean, 30-minute change, channel presence) gives the fault type or "normal". A rule decides when one instrument moved while the channels coupled to it did not (instrument fault). A physical check from the estimated NPSH margin confirms cavitation.
4. **Live ingest.** A read-only adapter turns raw replay messages (one per second) into the same one-minute readings as the organizers' file (largest difference 3e-5 on three pumps), tolerating duplicates, out-of-order and late messages, and counting what it drops. Re-running the detector on the minutes received gives the same alerts as a batch run (PUMP-08, three alerts). One re-run takes 1 to 3 seconds on one core for up to a week of history, so it grows with the history; an incremental scorer is not built.
5. **Data check.** Before any judgement the pipeline reads the state of its own data: repeated minutes are removed, and gateway silence, missing or stale channels, a lost speed signal, rows without measurements, the learning phase and quality flags are reported in plain words. A lost speed signal suspends operating-point checks instead of creating a new regime (it used to cause false alerts for days).
6. **Alerts.** One alert per problem per 12 hours; related alerts form an incident. Likelihood is a stage word (Watch, Possible, Likely, Very likely) with the back-test count behind it. Time to act is "not estimated".

Causality is enforced by test: telemetry is cut at several points and the earlier alerts must not change. The organizers' baseline fails this test (its baseline uses the first 24 hours of the whole window); ours passes.

## 4. Results (organizers' scorer)

| Set | Watchkeeper | Organizers' baseline B1 | Random alerts |
|---|---|---|---|
| Hold fleets (24 pumps, 82 events) | **62.8** (95% interval 55 to 70) | 52.1 (44 to 60) | 36.0 |
| Tuning fleets (48 events) | 59.9 (50 to 70) | 42.9 | 37.5 |
| Public pumps (35 events) | 67.1 (58 to 73) | 63.4 | 43.6 |
| Organizers' split: train / validation | 63.0 / 79.5 | 58.2 / 78.0 | |
| Masked-clogging trap (6 events) | 48.1 | 52.1 | 40.9 |

On the hold fleets: F1 0.71, recall 0.67, precision 0.76, fault-type recall 0.41, class recall 0.59. Healthy fleets: 1.33 false episodes per pump-month (upper 95% bound 2.27). Removing whole channels lowers the hold score gradually, from 62.8 to between 55.5 (no vibration) and 62.3 (no bearing and winding temperature): `eval/results/missing_sensor.md`.

## 5. What did not work

- **Fusing channels along fault signatures, plus a cumulative-sum detector on the fused score.** Built, unit-tested and measured. It finds more events (tune recall 0.62 to 0.69-0.73) but adds false alerts (healthy 6.8 to 9-14 per pump-month) and does not shorten the delay. Raising its thresholds does not remove the false alerts, because healthy pumps carry persistent offsets from the baseline. Switched off (`eval/results/signature.md`).
- **Earlier warning by this route.** We measured delay after the moment an effect first exceeds 3 sigma; the median is about 1 to 3 hours on the tuning and public sets for the trigger as built, and slow faults take longer.
- **Data-quality options.** A stricter frozen-sensor rule and an alert for a six-to-twelve hour sustained deviation that the classifier calls normal were gated (`eval/results/data_quality_gate.md`) and not adopted: the first loses real events, the second adds 2 to 7 false alerts per 294 pump-days for a gain within noise.
- **Operating context.** Cooling demand and temperatures from the operating-context table were tried as part of the operating-point key, as a fluid temperature relative to the supply water, and as classifier features. With an adoption rule fixed in advance, none helped: demand bins raised healthy false alerts from 1.3 to 4.4 per pump-month, and the other variants moved scores within noise (`eval/results/context.md`). The options stay in the code, switched off.

## 6. Limitations

- Synthetic, reduced-order simulator; fault growth compressed to 7 days; no seal leaks or electrical rotor and stator faults.
- Fault type is right for about two in five faults; the class (machine or instrument) for about three in five. Many machine faults are called instrument drift. The alert therefore states which instrument to check first.
- Masked suction clogging is below the baseline, and its type is never named.
- False alerts on healthy simulated pumps remain (1.3 per pump-month); the operating context did not remove them.
- No time-to-failure estimate. Stage words reflect this simulator only.
- Not certified and not a safety system; existing alarms and trips remain authoritative.

## 7. Reproducing

`make setup`, `make setup-pack`, `make data`, `make test`, `make bank`, `make model`, `make report`, `make levels`, `make predict`. Test-pump alerts: `submission/predictions_test.csv`, produced once from tag `freeze-v1`, with the model's SHA-256 in `predictions_test.meta.json`.

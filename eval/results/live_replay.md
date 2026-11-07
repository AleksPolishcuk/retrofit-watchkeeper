# Live replay: equivalence with the batch path and cost

Public pumps only. Replay messages come from `retrofit_sim.replay.messages` (the same stream `python -m retrofit_sim replay` prints). Reproduce with `.venv/bin/python eval/probes/live_equivalence.py`.

## 1. Minutes from raw messages equal the organizers' `features_1min`

First six hours of each pump's window, one message per second.

| Pump | Tier | Messages | Minutes | Same minutes | Largest absolute difference | Missing-value pattern differences |
|---|---|---|---|---|---|---|
| PUMP-08 | T1_RETROFIT | 21600 | 360 | yes | 1.5e-05 | 0 |
| PUMP-04 | T2_FULL | 21600 | 360 | yes | 3.1e-05 | 0 |
| PUMP-03 | T0_LEGACY | 21600 | 360 | yes | 3.1e-05 | 0 |

The differences are float32 rounding. Every channel, count, operating mode, running fraction, quality-flag mask and row count agrees.

## 2. The live pipeline gives the batch alerts

PUMP-08 (a validation pump that `models/wk.joblib` was not fitted on), 2025-09-08T00:00 to 2025-09-11T14:00: 5160 finished minutes. The detector was re-run every 30 minutes, and every minute during the hour around the first alert.

- Live alerts: 3. One batch run over the same minutes: 3. **Identical (time, type, confidence): yes.**
  - 2025-09-10T09:33:00Z SUCTION_STRAINER_CLOGGING (0.23)
  - 2025-09-10T23:58:00Z BEARING_WEAR (0.25)
  - 2025-09-11T12:35:00Z BEARING_WEAR (0.34)

## 3. Cost and delay (one core, CPU only)

- Ingest: 21,365 messages per second including the replay generator, so one pump at one message per second uses about 0.005 % of a core.
- Detector re-run, history of 3421 to 3480 minutes: median 1199 ms, 95th percentile 1844 ms, worst 2526 ms.
- First alert: published 0.0 data-minutes after its alert time when the detector runs every minute. At real-time replay the delay from the end of the minute is the 5 s lateness window plus one detector run.
- Whole run: 332.7 s wall, 305.5 s CPU, peak memory 570 MB.
- Re-running every minute at this history length costs about 2.0 % of one core per pump.

Limit, stated plainly: the detector is re-run on all minutes received so far, so one run takes 1 to 3 seconds for history of two days to a week (a full-week batch run of PUMP-08 takes 1.6 s) and the cost grows with the history. Peak memory includes the model and the public data table. An incremental scorer would remove the growth; it is not built.

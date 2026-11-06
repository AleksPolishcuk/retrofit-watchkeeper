# Where organizer baseline B1 loses points

Method: B1 (mode-aware robust z), parameters tuned on the other pumps in each fold (leave-one-asset-out over the 9 dev pumps, PUMP-01..09). 35 scored events. Source table: `B1_mode_aware_z/per_event_loo.csv`.

| Measure | Value |
|---|---|
| Composite, leave-one-asset-out | **57.2** (validation split alone shows 78.0 because it has only 2 pumps and 9 events) |
| Events detected | 23 of 35 |
| Class correct (machine vs sensor) | 19 of 35 |
| Fault type correct | 10 of 35 (type recall 0.29, weight 25 percent) |

## By fault type

| Fault type | Events | Detected | Type correct | Mean timeliness |
|---|---|---|---|---|
| AIR_ENTRAINMENT | 2 | 2 | 0 | 1.00 |
| BEARING_WEAR | 4 | 4 | 1 | 0.72 |
| CAVITATION | 4 | **0** | 0 | 0.00 |
| COMMUNICATION_LOSS | 2 | 2 | 2 | 1.00 |
| DISCHARGE_RESTRICTION | 3 | 2 | 2 | 0.66 |
| IMBALANCE | 1 | 1 | 0 | 1.00 |
| IMPELLER_WEAR | 2 | **0** | 0 | 0.00 |
| MISALIGNMENT | 3 | 2 | 0 | 0.48 |
| SENSOR_CALIBRATION_SHIFT | 2 | 2 | 1 | 1.00 |
| SENSOR_DRIFT | 3 | 2 | 0 | 0.59 |
| SENSOR_NOISE_SPIKES | 2 | **0** | 0 | 0.00 |
| SENSOR_STUCK | 3 | 2 | 2 | 0.67 |
| SUCTION_STRAINER_CLOGGING | 4 | 4 | 2 | 0.87 |

## Three biggest losses

1. **Diagnosis.** 13 of the 23 detected events get the wrong type. The rule table confuses drift with calibration shift (2 of 3 drifts), and sends bearing wear to discharge restriction, calibration shift and UNKNOWN. Detected-but-wrong is the largest single pool of lost points (type recall counts 25 percent).
2. **Whole families never found.**
   - Cavitation: 0 of 4 (all four episodes are on PUMP-06, the hot process pump). They are short and episodic.
   - Impeller wear: 0 of 2 (PUMP-03 and PUMP-05). Both are present from the first minute of the window, so a baseline taken from the first 24 hours treats the worn pump as normal. Only an absolute reference such as the pump curve can see them.
   - Noise spikes: 0 of 2.
3. **Not causal.** B1 takes its commissioning baseline from the first 24 hours, so an alert raised in that period uses statistics from later data. Truncating telemetry changes early alerts:

| Pump | Cut after | Alerts up to the cut, full run | Same, truncated run | Identical |
|---|---|---|---|---|
| PUMP-04 | 6 h | 1 | 0 | no |
| PUMP-04 | 20 h | 1 | 1 (different) | no |
| PUMP-06 | 20 h | 0 | 1 | no |

All other cuts tested (PUMP-02, PUMP-08, and later cuts) were identical. The organizers may run exactly this check on finalists, so our method has to use a baseline that only looks backwards.

## What this means for the engine

1. Causal baseline (expanding window until 24 h, frozen after).
2. An absolute reference from the pump curve and design point, to see conditions that exist from the start (impeller wear).
3. A diagnosis that learns from labelled events instead of fixed rules (largest pool of points).
4. A short-window suction-side detector for cavitation episodes.

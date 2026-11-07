# Results

Model: `wk.joblib`. Composite is the organizers' scorer. Intervals resample pumps (1000 draws).

| Set | Method | Composite (95% interval) | F1 | Recall | Precision | False + repeat per pump-day | Type recall | Class recall | Events |
|---|---|---|---|---|---|---|---|---|---|
| 9 public dev pumps | **WK** | 67.1 (58 to 73) | 0.75 | 0.71 | 0.78 | 0.11 | 0.49 | 0.60 | 35 |
| 9 public dev pumps | B1 organizer | 63.4 | 0.76 | 0.74 | 0.79 | 0.11 | 0.31 | 0.63 | 35 |
| 9 public dev pumps | B1 causal | 64.0 | 0.76 | 0.74 | 0.79 | 0.11 | 0.31 | 0.66 | 35 |
| tune fleets (16 pumps) | **WK** | 59.9 (50 to 70) | 0.70 | 0.65 | 0.76 | 0.09 | 0.35 | 0.54 | 48 |
| tune fleets (16 pumps) | B1 organizer | 42.9 | 0.51 | 0.48 | 0.53 | 0.18 | 0.17 | 0.38 | 48 |
| tune fleets (16 pumps) | B1 causal | 41.9 | 0.48 | 0.48 | 0.49 | 0.21 | 0.15 | 0.38 | 48 |
| masked-clogging trap (3 pumps) | **WK** | 48.1 | 0.62 | 0.67 | 0.57 | 0.14 | 0.00 | 0.67 | 6 |
| masked-clogging trap (3 pumps) | B1 organizer | 52.1 | 0.62 | 0.83 | 0.50 | 0.24 | 0.00 | 0.83 | 6 |
| masked-clogging trap (3 pumps) | B1 causal | 50.6 | 0.59 | 0.83 | 0.45 | 0.29 | 0.00 | 0.83 | 6 |
| hold fleets (24 pumps) | **WK** | 62.8 (55 to 70) | 0.71 | 0.67 | 0.76 | 0.10 | 0.41 | 0.59 | 82 |
| hold fleets (24 pumps) | B1 organizer | 52.1 | 0.63 | 0.57 | 0.70 | 0.12 | 0.23 | 0.50 | 82 |
| hold fleets (24 pumps) | B1 causal | 51.3 | 0.60 | 0.59 | 0.62 | 0.18 | 0.23 | 0.51 | 82 |

Null detector (same number of alerts per pump, random times, same type mix): 9 public dev pumps 43.6, tune fleets (16 pumps) 37.5, masked-clogging trap (3 pumps) 40.9, hold fleets (24 pumps) 36.0. An alert-free detector scores 10.

## Healthy fleets (no faults, every alert is false)

294 pump-days, 13 alerts, 13 false episodes. Rate **0.044 per pump-day, 1.33 per pump-month** (upper 95% bound 2.27). Design budget: at most 1 per pump per quarter (0.33 per pump-month).

## 9 public dev pumps: by instrumentation tier

| Tier | Events | Detected | Right type |
|---|---|---|---|
| T0_LEGACY | 5 | 3 | 2 |
| T1_RETROFIT | 15 | 11 | 9 |
| T2_FULL | 15 | 11 | 6 |

## 9 public dev pumps: by fault type

| Type | Events | Detected | Right type |
|---|---|---|---|
| AIR_ENTRAINMENT | 2 | 2 | 1 |
| BEARING_WEAR | 4 | 3 | 2 |
| CAVITATION | 4 | 3 | 3 |
| COMMUNICATION_LOSS | 2 | 2 | 2 |
| DISCHARGE_RESTRICTION | 3 | 2 | 1 |
| IMBALANCE | 1 | 1 | 1 |
| IMPELLER_WEAR | 2 | 0 | 0 |
| MISALIGNMENT | 3 | 3 | 1 |
| SENSOR_CALIBRATION_SHIFT | 2 | 2 | 0 |
| SENSOR_DRIFT | 3 | 1 | 1 |
| SENSOR_NOISE_SPIKES | 2 | 0 | 0 |
| SENSOR_STUCK | 3 | 2 | 2 |
| SUCTION_STRAINER_CLOGGING | 4 | 4 | 3 |

## tune fleets (16 pumps): by instrumentation tier

| Tier | Events | Detected | Right type |
|---|---|---|---|
| T0_LEGACY | 19 | 11 | 7 |
| T1_RETROFIT | 17 | 8 | 5 |
| T2_FULL | 12 | 12 | 5 |

## tune fleets (16 pumps): by fault type

| Type | Events | Detected | Right type |
|---|---|---|---|
| AIR_ENTRAINMENT | 5 | 3 | 2 |
| BEARING_WEAR | 1 | 1 | 1 |
| COMMUNICATION_LOSS | 4 | 4 | 4 |
| DISCHARGE_RESTRICTION | 12 | 5 | 2 |
| IMPELLER_WEAR | 6 | 4 | 1 |
| MISALIGNMENT | 2 | 2 | 1 |
| SENSOR_CALIBRATION_SHIFT | 3 | 3 | 2 |
| SENSOR_DRIFT | 6 | 4 | 3 |
| SENSOR_NOISE_SPIKES | 6 | 2 | 0 |
| SENSOR_STUCK | 2 | 2 | 1 |
| SUCTION_STRAINER_CLOGGING | 1 | 1 | 0 |

## masked-clogging trap (3 pumps): by instrumentation tier

| Tier | Events | Detected | Right type |
|---|---|---|---|
| T1_RETROFIT | 4 | 2 | 0 |
| T2_FULL | 2 | 2 | 0 |

## masked-clogging trap (3 pumps): by fault type

| Type | Events | Detected | Right type |
|---|---|---|---|
| SENSOR_DRIFT | 3 | 3 | 0 |
| SUCTION_STRAINER_CLOGGING | 3 | 1 | 0 |

## hold fleets (24 pumps): by instrumentation tier

| Tier | Events | Detected | Right type |
|---|---|---|---|
| T0_LEGACY | 25 | 15 | 7 |
| T1_RETROFIT | 38 | 30 | 20 |
| T2_FULL | 19 | 10 | 7 |

## hold fleets (24 pumps): by fault type

| Type | Events | Detected | Right type |
|---|---|---|---|
| AIR_ENTRAINMENT | 8 | 2 | 2 |
| BEARING_WEAR | 4 | 4 | 4 |
| CAVITATION | 6 | 5 | 5 |
| COMMUNICATION_LOSS | 6 | 6 | 6 |
| DISCHARGE_RESTRICTION | 10 | 5 | 3 |
| IMBALANCE | 2 | 1 | 0 |
| IMPELLER_WEAR | 10 | 7 | 0 |
| MISALIGNMENT | 7 | 6 | 5 |
| SENSOR_CALIBRATION_SHIFT | 8 | 5 | 2 |
| SENSOR_DRIFT | 5 | 3 | 2 |
| SENSOR_NOISE_SPIKES | 4 | 4 | 0 |
| SENSOR_STUCK | 6 | 5 | 4 |
| SUCTION_STRAINER_CLOGGING | 6 | 2 | 1 |


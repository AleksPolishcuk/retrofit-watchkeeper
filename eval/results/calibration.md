# Confidence calibration

Leave-one-asset-out alerts of the `wk` method on the 9 dev pumps: 68 alerts, 35 with the right fault type (51%), 64 inside a labelled event.

Target: the probability that the fault type named in the alert matches a labelled event active at that time.

| Score | Brier (lower is better) | Expected calibration error |
|---|---|---|
| **raw score used as a probability (shipped)** | 0.195 | 0.071 |
| constant base rate (0.51) | 0.250 | 0.000 |
| learned calibrator, C=0.3, each pump held out | 0.247 | 0.037 |
| learned calibrator, C=1.0, each pump held out | 0.225 | 0.154 |
| learned calibrator, C=5.0, each pump held out | 0.193 | 0.090 |

## Reliability of the raw score

| Predicted | Alerts | Mean predicted | Observed correct |
|---|---|---|---|
| 0.0-0.2 | 3 | 0.17 | 0.00 |
| 0.2-0.4 | 30 | 0.30 | 0.30 |
| 0.4-0.6 | 11 | 0.48 | 0.82 |
| 0.6-0.8 | 20 | 0.65 | 0.65 |
| 0.8-1.0 | 4 | 0.88 | 1.00 |

## By source of the alert

| Source | Alerts | Mean raw score | Observed correct |
|---|---|---|---|
| cavitation | 4 | 0.71 | 0.75 |
| model | 49 | 0.37 | 0.49 |
| rule_arbiter | 11 | 0.60 | 0.36 |
| rule_gap | 2 | 0.90 | 1.00 |
| rule_stuck | 2 | 0.85 | 1.00 |

## Decision

No learned calibrator beats the raw score by 0.01 Brier (best 0.193 against 0.195). With about 68 alerts a logistic calibrator only adds noise, so the raw score is shipped as the confidence. Rule-based instrument alerts are the weakest (see the table by source), and the cockpit shows the alternatives next to the main diagnosis.

Caveat: this is a small sample, and the test pumps are a new vessel and a new plant, so calibration may shift there.

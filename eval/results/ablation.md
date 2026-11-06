# What each step adds (leave-one-asset-out over the 9 dev pumps, 35 scored events)

Every row is fitted without the pump it is scored on. The validation column is the organizers' fixed split (2 pumps, 9 events) and is noisy. The train column of any learned method is in-sample and is not shown here.

| Step | LOO composite | Validation | Recall | Precision | Type recall | Sensor recall | Notes |
|---|---|---|---|---|---|---|---|
| Organizer B1 (rules, 24 h baseline) | 57.2 | 78.0 | 0.66 | 0.70 | 0.29 | 0.67 | not causal: early alerts change when telemetry is cut |
| + causal expanding baseline (`b1c`) | 58.7 | 75.6 | 0.69 | 0.71 | 0.29 | 0.67 | passes the truncation test |
| + learned diagnosis, no rules (RF, 300 trees) | 60.0 | 67.4 | 0.63 | 0.79 | 0.37 | 0.33 | machine types much better, instrument events lost |
| + rules for gaps and frozen channels (`wk`, RF 100 trees) | 60.0 | 78.6 | 0.63 | 0.73 | 0.40 | 0.50 | passes the truncation test |
| + cavitation from the estimated NPSH margin (physics, no training) | **66.7** | 78.6 | 0.71 | 0.76 | 0.49 | 0.50 | cavitation 3 of 4 found, all with the right type; healthy pumps never go below margin 3.3 |
| + hours since last maintenance lockout as a feature (`wk-no-arbiter`) | 68.8 | 75.8 | 0.74 | 0.74 | 0.51 | 0.58 | misalignment and calibration offsets follow maintenance |
| + single-channel arbiter incl. drift (`wk`) | **70.3** | 76.9 | 0.83 | 0.71 | 0.49 | 0.75 | recall and instrument events up, false alerts 0.14 to 0.19 per asset-day |
| + arbiter limited to process instruments (pressures, flow, current, power, bearing temperature) | **70.9** | 75.8 | 0.80 | 0.76 | 0.51 | 0.75 | 13 of 24 arbiter alerts came from winding temperature and vibration, where lone deviations were machine effects (9 of them had no instrument fault); false alerts 0.19 to 0.14 per asset-day |

## Reading

- Making the baseline causal cost nothing (57.2 to 58.7), so there is no reason to keep the non-causal one.
- Learned diagnosis helps machine faults a lot: bearing wear 4 of 4 with the right type (rules: 1 of 4), strainer clogging 4 of 4, impeller wear 2 of 2. It hurts instrument faults when used alone, because there are too few examples. Deterministic rules for a gateway gap and a frozen channel repair most of that.
- The composite barely moves (58.7 to 60.0) because gains in type recall are offset by lost recall and more false alerts. Two of the three impeller-wear hits come from the two similar pumps teaching each other (PUMP-03 and PUMP-05); on the unseen test vessel and plant this is unlikely to repeat, so do not count on it.

## What is still missing (from the per-event table)

Biggest remaining losses in fault-type points: misalignment (3 detected, 0 right type, mistaken for bearing wear), sensor drift (1 of 3 detected, 0 right type; organizer rules never output drift), sensor noise spikes (0 of 2), discharge restriction, air entrainment. The pump-curve reference (absolute, not self-baselined) is untested.

## Experiments that did not help (kept out of the pipeline)

Run offline on the leave-one-asset-out predictions of `wk` (composite 70.3, 71 alerts, 4 false-alert episodes, 8 excess repeats).

| Change | Composite | Why it loses |
|---|---|---|
| Drop alerts with confidence below 0.25 / 0.35 / 0.5 | 68.1 / 61.1 / 56.1 | removes more true detections than false ones |
| Hold other alerts on the same pump for 12 h (any class) | 66.6 | precision rises to 0.93 and excess repeats fall to 0, but recall falls from 0.83 to 0.71: a "repeat" is often the first detection of a second event |
| Hold 6 h / 24 h, same class or any class | 64.5 to 67.1 | same trade-off |

| Spread-based noise rule (one channel with very high spread, coupled channels quiet) | 69.9 vs 70.3 | finds 1 of 2 noise events but names it a calibration shift, and adds 2 false alerts (spread z is unstable where the baseline spread is tiny) |

The composite rewards detection more than quiet, so the current policy (one alert per fault type per 12 h while the deviation lasts) stays. The jury also weighs false alarms under reliability, so the false-alert rate is reported next to the composite.

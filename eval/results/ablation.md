# What each step adds (leave-one-asset-out over the 9 dev pumps, 35 scored events)

Every row is fitted without the pump it is scored on. The validation column is the organizers' fixed split (2 pumps, 9 events) and is noisy. The train column of any learned method is in-sample and is not shown here.

| Step | LOO composite | Validation | Recall | Precision | Type recall | Sensor recall | Notes |
|---|---|---|---|---|---|---|---|
| Organizer B1 (rules, 24 h baseline) | 57.2 | 78.0 | 0.66 | 0.70 | 0.29 | 0.67 | not causal: early alerts change when telemetry is cut |
| + causal expanding baseline (`b1c`) | 58.7 | 75.6 | 0.69 | 0.71 | 0.29 | 0.67 | passes the truncation test |
| + learned diagnosis, no rules (RF, 300 trees) | 60.0 | 67.4 | 0.63 | 0.79 | 0.37 | 0.33 | machine types much better, instrument events lost |
| + rules for gaps and frozen channels (`wk`, RF 100 trees) | 60.0 | 78.6 | 0.63 | 0.73 | 0.40 | 0.50 | passes the truncation test |

## Reading

- Making the baseline causal cost nothing (57.2 to 58.7), so there is no reason to keep the non-causal one.
- Learned diagnosis helps machine faults a lot: bearing wear 4 of 4 with the right type (rules: 1 of 4), strainer clogging 4 of 4, impeller wear 2 of 2. It hurts instrument faults when used alone, because there are too few examples. Deterministic rules for a gateway gap and a frozen channel repair most of that.
- The composite barely moves (58.7 to 60.0) because gains in type recall are offset by lost recall and more false alerts. Two of the three impeller-wear hits come from the two similar pumps teaching each other (PUMP-03 and PUMP-05); on the unseen test vessel and plant this is unlikely to repeat, so do not count on it.

## What is still missing (from the per-event table)

Not detected by any method here: cavitation 0 of 4 (short episodes on PUMP-06), sensor noise spikes 0 of 2, sensor drift 1 of 3. These need their own detectors (short-window suction-side detector, a spread-based noise detector, a ramp detector). The pump-curve reference (absolute, not self-baselined) is untested.

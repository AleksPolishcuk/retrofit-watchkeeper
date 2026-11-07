# Edge design and transfer plan

This covers the "low-cost retrofit feasibility and transfer" criterion. Measured numbers come from `eval/results/`. Prices and the pilot sequence are from the organizers' `RETROFIT_FEASIBILITY.md` (LIST prices of 30 Oct 2026 and stated assumptions); they are not recommendations of any vendor.

## 1. What runs where

```
 [ Safety system / SIS ]        untouched, authoritative trips and interlocks
 [ PLC / drive / MCC ] ──read only──┐
 [ Existing and retrofit sensors ] ─┤
                                    ▼
                          [ Edge box, own network zone ]
                           Watchkeeper (Python, one CPU core)
                           local buffer, works offline
                                    │ one-way conduit (DMZ or unidirectional gateway)
                                    ▼
                          [ Historian / operator screen ]   advice and evidence for a person
```

- **No write path.** The code has no function that sends anything to a pump, drive, valve, PLC or safety system. The HTTP interface has GET routes only, and a test fails if another method appears (`tests/test_api.py::test_every_route_is_read_only`). The sandbox is a simulation (`retrofit_sim what_if`); it never touches a real machine.
- **Offline first.** Scoring needs the model file and the pump's own recent data. No network, no cloud call and no language model is needed at runtime.
- **Existing alarms stay authoritative.** Watchkeeper is an additional advisory layer; it does not replace or silence any trip or alarm.

## 2. Measured footprint

From `eval/footprint.py` on a laptop (Python 3.10, one core):

| | |
|---|---|
| Model file | 6.6 MB |
| Scoring one pump for a week (9,980 one-minute rows) | 1.3 s, 0.13 ms per pump-minute |
| Peak memory of the measuring process | 331 MB, including loading the whole public data table |
| GPU, network | not needed |

Reading: one small edge computer (EUR 0.5-0.6 k class in the organizers' bill of materials) can score a whole fleet many times over in real time. The figure is for scoring a recorded week in one batch. Every score uses only earlier data, so the same pipeline runs on a stream: `make live-demo` feeds the organizers' raw replay (one message per second) through the read-only adapter and the detector, and the alerts equal those of a batch run (`eval/results/live_replay.md`). Re-running the detector every minute on a day or two of history costs about 2 % of one core per pump; the cost grows with the history because the detector is re-run on all minutes received, and an incremental scorer is not built. The prototype has been run on replayed recorded data, not on a live plant feed.

## 3. What a pump needs to be onboarded

1. An asset record: instrumentation level and channel list, rated motor speed and power, suction static head (used by the physical cavitation check).
2. One-minute averages of the channels the pump already has. Missing channels are allowed and are stated on each alert.
3. About 24 hours of normal running to learn what normal looks like at each speed (operating point). A speed not seen in that period is learned for two further hours before it is judged, so a healthy demand change does not raise an alert.
4. Shadow mode first: alerts are logged and compared with operator decisions before anyone is asked to act (organizers' pilot path, steps 1-2).

## 4. If a sensor is missing

`eval/results/missing_sensor.md` removes whole channels from the untouched hold fleets. The composite falls gradually from 62.8:

| Missing | Composite |
|---|---|
| bearing and winding temperature | 62.3 |
| flow and power | 61.2 |
| suction pressure | 58.8 |
| discharge pressure | 55.9 |
| vibration sensor | 55.5 |

The vibration sensor and discharge pressure matter most. That supports the organizers' advice to start from what the drive and the motor starter already know and add one vibration and temperature point per critical bearing.

## 5. Moving to other machines

What transfers without change: the per-pump causal baseline by operating point, the rules for data gaps and frozen values, the physical cavitation check (from NPSH margin), incident grouping, the stage words with back-test counts, and the human-approval flow.

What needs local work and has **not** been tested: the fault-type model was trained on simulated cooling-water pumps. Other pump types, fluids, drives or machine classes need their own labelled examples. Until they exist, the sensible mode is detection plus the "machine or instrument" call without naming a fault type.

Suggested sequence for a new site, from the organizers' pilot path: read-only data for 4-8 weeks, shadow mode, add one retrofit point where shadow mode shows a blind spot, advisory pilot with a named role and a feedback button, then a review based on measured value and an independent engineering and regulatory check before any operational use.

## 6. Honest limits

- All measurements are on synthetic data.
- False alerts on healthy simulated pumps are about 1.3 per pump-month; a plant would tune this with its operators. Adding the operating context (demand, temperatures) did not lower it on this benchmark.
- The fault type is right for about two in five faults; the machine-or-instrument class is right more often. Alerts say which instrument to check first for this reason.
- Class approval for condition-based maintenance needs an approved maintenance scheme; a prototype earns none.

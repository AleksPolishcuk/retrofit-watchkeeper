# Scenario probe: how Watchkeeper behaves in the enterprise verification scenarios

Real minute features of quiet healthy simulated pumps are perturbed as each scenario describes and run through the frozen model. No public or test pump is used.

| Scenario | What was done | Result | Note |
|---|---|---|---|
| A01 | stable, correct data | no alert |  |
| A02a | gateway silent for 4 minutes | no alert | our gap rule needs 8 minutes |
| A02b | gateway silent for 12 minutes | 1 alert(s): COMMUNICATION_LOSS 14 Dec 07:08 |  |
| A03 | suction pressure channel stops, gateway alive | no alert | no dynamic channel-loss notice |
| A04 | speed signal of the drive disappears | 5 alert(s): IMPELLER_WEAR 15 Dec 06:14; SENSOR_CALIBRATION_SHIFT 15 Dec 18:14; SUCTION_STRAINER_CLOGGING 16 Dec 18:14; IMPELLER_WEAR 19 Dec 06:12; SENSOR_CALIBRAT |  |
| A05 | flow and pressure deviation for 8 minutes | no alert |  |
| A06 | flow and pressure deviation for 20 minutes | no alert | the trigger fires (z up to 31) but the classifier says NONE, 70 to 74 percent, so the alert is suppressed |
| A11 | same deviation, readings flagged OUT_OF_RANGE | no alert | quality flags are not used |
| A12 | pressure constant inside minutes, changing between minutes | 1 alert(s): SENSOR_STUCK 14 Dec 07:12 | stuck rule looks at spread inside a minute only |
| A14 | a row with the same minute arrives twice | CRASH ValueError: cannot reindex on an axis with duplicate labels |  |
| A15 | continuous deviation for 14 hours | no alert | same cause as A06: 90 trigger minutes in the first window, classifier answers NONE; the incident grouping is covered by tests/test_incidents.py |
| A18 | rows arrive but every physical measurement is missing (2 h) | no alert | nothing tells the user that evaluation is impossible |
| A10 | T1: 28 abnormal wireless vibration samples, 5 minutes apart | 1 alert(s): MISALIGNMENT 12 Jun 18:14 |  |

Checked afterwards (`/tmp` diagnosis, same pump): with flow x0.8, pressure x1.12, current x0.9 the largest robust deviations are 8.8, 15.4 and 9.1; with flow x0.6 they are 16.8, 31.7 and 17.0. In both cases the trigger is on for every minute of the window and the mean probability of NONE is 0.74 and 0.70, so the alert is suppressed (suppress threshold 0.6).

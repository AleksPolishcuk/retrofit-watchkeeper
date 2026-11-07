# Scenario probe: how Watchkeeper behaves in the enterprise verification scenarios

Real minute features of quiet healthy simulated pumps are perturbed as each scenario describes and run through the frozen model. No public or test pump is used.

Three runs per scenario. **Without options** is the behaviour of the submitted model (freeze-v1). **Current default** adds `speedloss`, which passed the data-quality gate and is on by default in the code. **All options** adds `flatstrict` and `longdev12` as well; both failed the gate and are off (see `data_quality_gate.md`).

| Scenario | What was done | Without options (freeze-v1) | Current default | All options | Note |
|---|---|---|---|---|---|
| A01 | stable, correct data | no alert | no alert | no alert |  |
| A02a | gateway silent for 4 minutes | no alert | no alert | no alert | our gap rule needs 8 minutes |
| A02b | gateway silent for 12 minutes | 1 alert(s): COMMUNICATION_LOSS 14 Dec 07:08 | 1 alert(s): COMMUNICATION_LOSS 14 Dec 07:08 | 1 alert(s): COMMUNICATION_LOSS 14 Dec 07:08 |  |
| A03 | suction pressure channel stops, gateway alive | no alert | no alert | no alert | no alert is raised, but the Data check in the case view and `/api/data-health` name the silent channel |
| A04 | speed signal of the drive disappears | 5 alert(s): IMPELLER_WEAR 15 Dec 06:14; SENSOR_CALIBRATION_SHIFT 15 Dec 18:14; SUCTION_STRAINER_CLOGGING 16 Dec 18:14; IMPELLER_WEAR 19 Dec 06:12; SENSOR_CALIBRAT | no alert | no alert | without the option the missing speed makes a new operating regime and gives false alerts for days; `speedloss` fixes it |
| A05 | flow and pressure deviation for 8 minutes | no alert | no alert | no alert |  |
| A06 | flow and pressure deviation for 20 minutes | no alert | no alert | no alert | the trigger fires (z up to 31) but the classifier says NONE, 70 to 74 percent, so the alert is suppressed |
| A11 | same deviation, readings flagged OUT_OF_RANGE | no alert | no alert | no alert | the detector ignores quality flags; the Data check counts them |
| A12 | pressure constant inside minutes, changing between minutes | 1 alert(s): SENSOR_STUCK 14 Dec 07:12 | 1 alert(s): SENSOR_STUCK 14 Dec 07:12 | no alert | the default rule looks at spread inside a minute only; `flatstrict` also requires no change between minutes but loses real events on the tuning fleets |
| A14 | a row with the same minute arrives twice | no alert | no alert | no alert | crashed the first version of the probe; input hygiene now keeps the last row and counts the duplicate |
| A15 | continuous deviation for 14 hours | no alert | no alert | 1 alert(s): UNKNOWN 14 Dec 19:00 | only `longdev12` reports it (one UNKNOWN alert); contract v2 groups later reminders into one incident |
| A18 | rows arrive but every physical measurement is missing (2 h) | no alert | no alert | no alert | no alert is raised, but the Data check says every measurement is missing and nothing can be evaluated |
| A10 | T1: 28 abnormal wireless vibration samples, 5 minutes apart | 1 alert(s): MISALIGNMENT 12 Jun 18:14 | 1 alert(s): MISALIGNMENT 12 Jun 18:14 | 1 alert(s): MISALIGNMENT 12 Jun 18:14 |  |

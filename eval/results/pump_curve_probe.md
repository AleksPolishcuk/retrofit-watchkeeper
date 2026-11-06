# Probe: pump curve as an absolute reference (not shipped)

Question: can a pump-curve and design-point model predict the discharge pressure well enough to see conditions that exist from the first minute of the window (impeller wear), which a self-baselining method treats as normal?

Method (`eval/probes/pump_curve_probe.py`): speed ratio from the drive (1 for fixed speed), system curve through the design point (`design_head`, `design_flow`, `static_head` from assets.csv), operating point from `retrofit_sim.physics`, discharge pressure = rho g H + measured suction pressure. Ratio = measured / expected over steady running minutes.

| Pump | Tier | Control | Impeller wear in labels | Suction pressure measured | Ratio (median) |
|---|---|---|---|---|---|
| PUMP-01 | T1 | VFD temperature | no | yes | 1.012 |
| PUMP-02 | T2 | VFD temperature | no | yes | 0.956 |
| PUMP-04 | T2 | VFD pressure | no | yes | 0.983 |
| PUMP-06 | T1 | flow valve | no | yes | 1.041 |
| PUMP-07 | T2 | VFD temperature | no | yes | 1.010 |
| PUMP-08 | T1 | VFD temperature | no | yes | 0.995 |
| PUMP-09 | T2 | fixed speed | no | yes | 0.988 |
| **PUMP-03** | T0 | fixed speed | **yes** | **no** | 1.506 |
| **PUMP-05** | T0 | fixed speed | **yes** | **no** | 0.984 |

## Result

- On healthy pumps that have a suction pressure transmitter the model is accurate: ratios 0.96 to 1.04, mostly within 1 to 2 percent.
- Both impeller-wear events in the dev data are on legacy (T0) pumps with no suction pressure. Without it the expected pressure is off by an unknown offset (PUMP-03 is a pressurised closed loop: ratio 1.51; PUMP-05 looks healthy at 0.98 although the label says moderate wear).
- So the reference works where wear is not present in the data, and fails where it is. It cannot be validated here, and shipping an unvalidated detector is worse than not having one.

## What would make it usable

A suction pressure estimate for T0 pumps (known suction static head and loop pressure per site), or a labelled impeller-wear example on a T1/T2 pump to validate against. On the test set, PUMP-10 (T1) and PUMP-12 (T2) have suction pressure, so the idea may still be worth a bounded try if validation data appears.

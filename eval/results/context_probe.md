# Probe: expected motor speed from the operating context (A10, not integrated)

`src/watchkeeper/features/context.py` computes the speed a temperature-controlled drive should run at for the current cooling demand and water
temperature, from the documented control law, the pump data sheet and the public context table. Measured minus expected speed is a residual that
rises when the pump needs more speed for the same duty (strainer clogging, restriction, impeller wear), and it does not use the suction transmitter.

| Pump | Healthy residual (speed ratio) | During strainer clogging |
|---|---|---|
| PUMP-01 (T1, August) | median +0.009, 5th to 95th percentile +0.002 to +0.036 | +0.019 and +0.016 in its two events |
| PUMP-02, PUMP-07 (T2) | +0.006, a constant offset, spread under 0.001 | no clogging event |
| PUMP-08 (T1, September) | +0.006, spread under 0.001 | **+0.006, no change** |

Reading: the residual is very stable on healthy pumps, and it shows clogging when the sea is warm enough for the drive to run above its minimum
speed. In cold water the pump sits at minimum speed, so on PUMP-08 the clogging cannot appear in speed at all. The feature therefore helps part of the
year only, and only on the seawater loops with this control. Wiring it in needs a context table in the data object, one more feature channel,
retraining and the three-set evaluation; that was not done in the time available. If it is done, expect the benefit on the masked-clogging trap
and on seawater pumps in the warm season, and none on fixed-speed or pressure-controlled pumps.

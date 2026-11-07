# Data-quality options: gate result

Three options that change which alerts are raised were tested before switching any of them on. Compact model (60 trees) trained on the bank training fleets plus the healthy_train fleets, evaluated on the tune fleets, the 9 public pumps, the masked-clogging trap and 6 healthy fleets (294 pump-days). Script: `eval/experiment_signature.py --learn --train-healthy --ctx=<option>`.

Gate, written down before the last two runs: adopt an option if it does not lose score on tune or the public pumps and does not raise healthy false episodes; an option that adds recall may cost at most about two healthy alerts per 294 pump-days.

| Option | What it does | Tune | Public pumps | Trap | Healthy false episodes per pump-month (count) | Decision |
|---|---|---|---|---|---|---|
| none (current method) | | 59.9 | 67.1 | 48.1 | 1.33 (13) | |
| `speedloss` | minutes after a lost speed signal are not steady (A04) | 59.9 | 67.1 | 48.1 | 1.33 (13) | **on by default**: identical on every set, and identical on the 33 test-pump alerts (0 minutes affected) |
| `flatstrict` | a value that changes between minutes is not frozen (A12) | 57.7 | 66.9 | 47.8 | 1.22 (12) | **off**: loses 3 real stuck-sensor events on tune; the benchmark counts a signal that is constant inside each minute as stuck |
| `longdev` (6 h) | six hours of departure that the model keeps calling normal become an `UNKNOWN` alert (A06, A15) | 61.4 | 69.4 | 48.1 | 2.04 (20) | off: best score, most false alerts |
| `longdev8` (8 h) | same, 8 hours | 61.3 | 68.1 | 48.1 | 1.73 (17) | off: just misses the gate on false alerts |
| `longdev12` (12 h) | same, 12 hours | 60.8 | 67.6 | 48.1 | 1.53 (15) | off: gain below the gate (+0.9 on tune) |

Reading:

- `speedloss` removes a real failure (five false alerts in four days after the speed signal disappeared) at no cost anywhere we can measure, so it is the only option that is on.
- `flatstrict` is a genuine trade-off. In a plant a pressure that moves between minutes while having no spread inside a minute is more likely a coarse instrument than a frozen one. On this benchmark such a pattern is labelled stuck, and the stricter rule loses events. Left off; it is the right switch for a site with low-resolution transmitters.
- `longdev` closes a hole that a plant would notice: a large sustained change from the pump's own normal (up to 31 sigma for 14 hours in the scenario probe) raises no alert, because the classifier answers "normal". The score gain is 0.9 to 1.5 on tune and 0.5 to 2.3 on the public pumps, all within noise, and it costs 2 to 7 more false alerts over 294 pump-days. None of the three lengths passes the gate, so none is on. 12 hours is the cautious choice for a pilot.
- The submitted predictions (`freeze-v1`) are unchanged: the 33 alerts for PUMP-10, 11 and 12 reproduce identically with the current code and with `speedloss` on.

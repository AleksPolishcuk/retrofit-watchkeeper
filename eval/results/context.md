# Operating context (plan item A14): measured, not adopted

Question: does using the operating context (cooling demand, supply water temperature, ambient temperature, joined per minute to the telemetry) lower false alerts or raise the score?

Method: `src/watchkeeper/features/ctxjoin.py` joins the context table to the features (it exists for every pump, test pumps included, and holds no labels). Four ways of using it were tried with `eval/experiment_signature.py`. The compact model (60 trees) is trained on the bank training fleets plus the healthy_train fleets, and evaluated on the tune fleets, the 9 public pumps, the masked-clogging trap and 6 healthy fleets (294 pump-days, no faults).

The decision rule was fixed before the runs: adopt a variant only if healthy false episodes fall by at least 25%, or the tune score rises by at least 2 with no loss on the public pumps and no rise in healthy false episodes.

| Variant | Tune | Public pumps | Trap | Healthy false episodes per pump-month (count) |
|---|---|---|---|---|
| Current method (regime learning, healthy fleets as normal examples) | 59.9 | 67.1 | 48.1 | **1.33 (13)** |
| Cooling demand added to the operating-point key (15 percent bins) | 60.9 | 66.4 | 52.6 | 4.39 (43) |
| Fluid temperature relative to the supply water temperature | 60.2 | 68.4 | 42.6 | 1.73 (17) |
| Both of the above | 61.6 | 67.7 | 49.7 | 2.76 (27) |
| Context as classifier features (demand, 30 minute change, largest change in 3 h, water and ambient temperature) | 61.7 | 66.7 | 55.7 | 1.53 (15) |
| Features and relative fluid temperature | 61.3 | 65.9 | 43.4 | 1.84 (18) |

Reading:

- No variant meets the rule. The best tune score (61.7) is 1.8 above the current method, below the threshold, and the healthy count does not fall in any variant.
- Splitting baselines by demand is clearly worse on healthy pumps: thinner cells mean shorter and noisier baselines, so more false alerts (43 against 13). The other differences are within noise: the composite has a 95% interval of about plus or minus 10, and a count of 13 healthy alerts has a Poisson spread of about 3.6.
- The remaining false alerts of the current method are therefore not simple demand or temperature effects that a bin or a feature can remove. A better model of normal operation would need the physics of each loop (system curve and control law), which `eval/results/context_probe.md` started for variable-speed seawater pumps.

Decision: the options stay in the code, switched off (`ctx=()` in `WKMethod`), with tests. The submitted model (tag `freeze-v1`) is unchanged. The second untouched set `hold2` (seeds 211 to 213) was generated and never opened.

# Signature fusion and slow-change detector: measured, not adopted

Question: do weak shifts on several channels that agree with a fault's physical signature allow an earlier alert than the single-channel trigger, without more false alerts?

Method (`src/watchkeeper/detect/signature.py`, `eval/experiment_signature.py`): per fault type, a trimmed fused score (the largest single contributor is left out, so one wild channel cannot raise a machine-fault score alone), computed on a 15-minute causal window; plus a one-sided CUSUM on its hourly mean for slow faults. Both are backward-looking and have unit tests, including a truncation test. One compact model (60 trees) trained on the bank training fleets, evaluated on the tune fleets, the 9 development pumps, the masked-clogging trap, and 6 healthy fleets (42 pumps x 7 days, no faults, so every episode there is false).

| Setting | Tune composite | Tune recall | Tune type recall | Dev9 composite | Healthy episodes per pump-month | Median delay after detectable, tune (h) |
|---|---|---|---|---|---|---|
| Off (current) | 58.7 | 0.62 | 0.33 | 68.5 | 6.84 | 3.9 |
| Fused, h = 5 | 57.0 | 0.71 | 0.46 | 63.7 | 13.67 | 3.4 |
| Fused, h = 6 | 59.0 | 0.73 | 0.44 | 64.1 | 12.14 | 3.7 |
| Slow, h = 8 | 58.1 | 0.69 | 0.40 | 62.7 | 8.98 | 3.9 |
| Slow, h = 12 | 58.3 | 0.69 | 0.40 | 62.3 | 8.78 | 4.7 |
| Slow, h = 16 | 58.8 | 0.69 | 0.40 | 63.0 | 8.88 | 4.7 |

Reading:

- The detectors find more events (tune recall 0.62 to 0.69-0.73, type recall 0.33 to 0.40-0.46), but the median delay does not improve, and on the development pumps the composite drops by 4 to 6 points.
- Raising the threshold does **not** remove the false alerts: the slow detector still fires on 21 healthy pump-weeks at h = 16, and the fused flag still fires 68 times at h = 6. White-noise tests would predict almost none. The healthy simulated pumps carry persistent offsets from the regime baseline (VFD pumps against demand, seasonal temperature), and a detector that integrates evidence integrates that bias too.
- So the limit is the quality of the normal-operation baseline, not the way the channels are combined. Fusing helps only after the baseline is better (context normalisation, plan item A14).

Decision: both detectors stay in the code, off by default (`sig_h=None, slow_h=None`), with their tests. They are not part of the submitted model. This is reported as a negative result.

# Organizer baselines, reproduced

Run on 6 Nov 2026 from `RETROFIT_AI_PARTICIPANTS_2026/baselines/run_baselines.py` (full data, Python 3.10, pandas 2.3.3, numpy 2.2.6, scikit-learn 1.7.2). Parameters are tuned on the training split only.

| Baseline | Split | Composite here | Composite in organizer docs |
|---|---|---|---|
| B1 mode-aware z | train | 58.2 | 58.2 |
| B1 mode-aware z | validation | 78.0 | 78.0 |
| B2 CUSUM | train / validation | 53.3 / 50.9 | 53.3 / 50.9 |
| B3 Isolation Forest | train | 39.8 | 39.4 |
| B3 Isolation Forest | validation | 69.2 | 69.2 |

B3 differs by 0.4 on train, most likely because of library versions (the forest is random-state seeded but sklearn changed between releases). Everything else matches exactly.

Full table: `organizer_baselines/baseline_metrics.md`.

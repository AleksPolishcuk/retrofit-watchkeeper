# WK_causal_learned

Fixed split: fitted on the train pumps. The train row is in-sample; read validation and leave-one-asset-out.

Leave-one-asset-out: 9 folds, each fitted on the other eight pumps.

| Run | Composite | F1 | Recall | Precision | FA / asset-day | Timeliness | Type recall | Class recall | Machine recall | Sensor recall | Events |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fit on train / train | 82.7 | 0.85 | 0.85 | 0.85 | 0.08 | 0.76 | 0.81 | 0.81 | 0.83 | 0.88 | 26 |
| fit on train / validation | 75.8 | 0.89 | 0.89 | 0.89 | 0.07 | 0.86 | 0.44 | 0.67 | 1.00 | 0.75 | 9 |
| leave-one-asset-out / all 9 | 70.9 | 0.78 | 0.80 | 0.76 | 0.14 | 0.72 | 0.51 | 0.71 | 0.83 | 0.75 | 35 |

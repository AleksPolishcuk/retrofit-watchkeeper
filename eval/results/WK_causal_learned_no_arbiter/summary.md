# WK_causal_learned

Fixed split: fitted on the train pumps. The train row is in-sample; read validation and leave-one-asset-out.

Leave-one-asset-out: 9 folds, each fitted on the other eight pumps.

| Run | Composite | F1 | Recall | Precision | FA / asset-day | Timeliness | Type recall | Class recall | Machine recall | Sensor recall | Events |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fit on train / train | 85.9 | 0.88 | 0.85 | 0.92 | 0.04 | 0.79 | 0.85 | 0.85 | 0.83 | 0.88 | 26 |
| fit on train / validation | 75.8 | 0.89 | 0.89 | 0.89 | 0.07 | 0.86 | 0.44 | 0.67 | 1.00 | 0.75 | 9 |
| leave-one-asset-out / all 9 | 68.8 | 0.74 | 0.74 | 0.74 | 0.14 | 0.69 | 0.51 | 0.69 | 0.83 | 0.58 | 35 |

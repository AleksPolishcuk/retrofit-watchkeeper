# WK_causal_learned

Fixed split: fitted on the train pumps. The train row is in-sample; read validation and leave-one-asset-out.

Leave-one-asset-out: 9 folds, each fitted on the other eight pumps.

| Run | Composite | F1 | Recall | Precision | FA / asset-day | Timeliness | Type recall | Class recall | Machine recall | Sensor recall | Events |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fit on train / train | 85.5 | 0.88 | 0.85 | 0.92 | 0.04 | 0.76 | 0.85 | 0.85 | 0.83 | 0.88 | 26 |
| fit on train / validation | 78.6 | 0.89 | 0.89 | 0.89 | 0.07 | 0.86 | 0.56 | 0.67 | 1.00 | 0.75 | 9 |
| leave-one-asset-out / all 9 | 66.7 | 0.74 | 0.71 | 0.76 | 0.13 | 0.66 | 0.49 | 0.63 | 0.83 | 0.50 | 35 |

# WK_causal_learned

Fixed split: fitted on the train pumps. The train row is in-sample; read validation and leave-one-asset-out.

Leave-one-asset-out: 9 folds, each fitted on the other eight pumps.

| Run | Composite | F1 | Recall | Precision | FA / asset-day | Timeliness | Type recall | Class recall | Machine recall | Sensor recall | Events |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fit on train / train | 79.6 | 0.83 | 0.77 | 0.91 | 0.04 | 0.69 | 0.77 | 0.77 | 0.72 | 0.88 | 26 |
| fit on train / validation | 78.6 | 0.89 | 0.89 | 0.89 | 0.07 | 0.86 | 0.56 | 0.67 | 1.00 | 0.75 | 9 |
| leave-one-asset-out / all 9 | 60.0 | 0.68 | 0.63 | 0.73 | 0.13 | 0.58 | 0.40 | 0.54 | 0.70 | 0.50 | 35 |

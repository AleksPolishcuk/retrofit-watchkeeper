# WK_causal_learned

Fixed split: fitted on the train pumps. The train row is in-sample; read validation and leave-one-asset-out.

Leave-one-asset-out: 9 folds, each fitted on the other eight pumps.

| Run | Composite | F1 | Recall | Precision | FA / asset-day | Timeliness | Type recall | Class recall | Machine recall | Sensor recall | Events |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fit on train / train | 76.8 | 0.79 | 0.85 | 0.73 | 0.16 | 0.76 | 0.69 | 0.77 | 0.83 | 0.88 | 26 |
| fit on train / validation | 76.9 | 0.89 | 0.89 | 0.89 | 0.07 | 0.86 | 0.44 | 0.78 | 1.00 | 0.75 | 9 |
| leave-one-asset-out / all 9 | 70.3 | 0.76 | 0.83 | 0.71 | 0.19 | 0.75 | 0.49 | 0.74 | 0.87 | 0.75 | 35 |

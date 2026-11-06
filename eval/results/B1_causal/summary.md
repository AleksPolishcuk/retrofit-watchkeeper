# B1_causal

Fixed split params (fit on train): `(6, 30)`

Leave-one-asset-out params per held-out pump: `{"PUMP-01": [6, 5], "PUMP-02": [6, 5], "PUMP-03": [6, 30], "PUMP-04": [6, 30], "PUMP-05": [6, 30], "PUMP-06": [6, 15], "PUMP-07": [6, 5], "PUMP-08": [6, 5], "PUMP-09": [6, 30]}`

| Run | Composite | F1 | Recall | Precision | FA / asset-day | Timeliness | Type recall | Class recall | Machine recall | Sensor recall | Events |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fit on train / train | 60.2 | 0.72 | 0.65 | 0.81 | 0.08 | 0.57 | 0.31 | 0.62 | 0.67 | 0.62 | 26 |
| fit on train / validation | 75.6 | 0.89 | 0.89 | 0.89 | 0.07 | 0.80 | 0.44 | 0.78 | 1.00 | 0.75 | 9 |
| leave-one-asset-out / all 9 | 58.7 | 0.70 | 0.69 | 0.71 | 0.16 | 0.62 | 0.29 | 0.57 | 0.70 | 0.67 | 35 |

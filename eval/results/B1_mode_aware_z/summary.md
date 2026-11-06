# B1_mode_aware_z

Fixed split params (fit on train): `(6, 15)`

Leave-one-asset-out params per held-out pump: `{"PUMP-01": [6, 5], "PUMP-02": [8, 5], "PUMP-03": [6, 30], "PUMP-04": [6, 30], "PUMP-05": [6, 15], "PUMP-06": [6, 15], "PUMP-07": [6, 5], "PUMP-08": [6, 15], "PUMP-09": [6, 15]}`

| Run | Composite | F1 | Recall | Precision | FA / asset-day | Timeliness | Type recall | Class recall | Machine recall | Sensor recall | Events |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fit on train / train | 58.2 | 0.72 | 0.69 | 0.75 | 0.12 | 0.58 | 0.27 | 0.54 | 0.67 | 0.75 | 26 |
| fit on train / validation | 78.0 | 0.89 | 0.89 | 0.89 | 0.07 | 0.86 | 0.44 | 0.89 | 1.00 | 0.75 | 9 |
| leave-one-asset-out / all 9 | 57.2 | 0.68 | 0.66 | 0.70 | 0.16 | 0.59 | 0.29 | 0.54 | 0.65 | 0.67 | 35 |

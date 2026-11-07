# Missing sensors: untouched hold fleets (24 pumps, 82 events), frozen model

Whole channels are removed from the data before anything is computed. The model was trained on a mix of full, retrofit and legacy pumps, so it has seen missing channels, but not these removals on top of each tier.

| Scenario | Composite | Recall | Precision | Type recall | Class recall | False + repeat per pump-day |
|---|---|---|---|---|---|---|
| all channels | 62.8 | 0.67 | 0.76 | 0.41 | 0.59 | 0.1 |
| no suction pressure | 58.8 | 0.59 | 0.87 | 0.35 | 0.54 | 0.04 |
| no flow and no power | 61.2 | 0.65 | 0.78 | 0.39 | 0.57 | 0.09 |
| no vibration sensor | 55.5 | 0.59 | 0.75 | 0.3 | 0.45 | 0.1 |
| no bearing and winding temperature | 62.3 | 0.65 | 0.78 | 0.41 | 0.59 | 0.09 |
| no discharge pressure | 55.9 | 0.57 | 0.77 | 0.33 | 0.45 | 0.08 |

#!/usr/bin/env python3
"""The test-set trap the organizers describe: a drifting suction transmitter that masks a clogging strainer. Three pumps (two T1, one T2)."""
import copy
import subprocess
import sys
from pathlib import Path

import retrofit_sim
import yaml

PACK = Path(retrofit_sim.__file__).resolve().parents[2]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "bank")
pub = yaml.safe_load((PACK / "configs" / "fleet_public.yaml").read_text())
by = {a["asset_id"]: a for a in pub["assets"]}
cfg = copy.deepcopy(pub)
cfg["assets"] = []
for i, (src, tier, rate) in enumerate((("PUMP-01", "T1_RETROFIT", 0.055), ("PUMP-02", "T2_FULL", 0.055), ("PUMP-01", "T1_RETROFIT", 0.04)), start=1):
    a = copy.deepcopy(by[src])
    a.update(asset_id=f"TRAP-{i:02d}", split="train", instrumentation_tier=tier, start_utc="2025-08-11T00:00:00")
    a["scenario"] = [{"type": "SUCTION_STRAINER_CLOGGING", "onset_h": 40, "params": {"rate_per_h": rate, "c_max": 3.0, "shape": "linear"}},
                     {"type": "SENSOR_DRIFT", "sensor_tag": "suction_pressure_kpa", "onset_h": 38, "params": {"drift_per_h": 0.35}}]
    cfg["assets"].append(a)
(OUT / "cfg").mkdir(parents=True, exist_ok=True)
(OUT / "cfg" / "trap.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
sys.exit(subprocess.run([sys.executable, str(PACK / "make_dataset.py"), "--tier", "full", "--fleet-config", str(OUT / "cfg" / "trap.yaml"),
                         "--no-snapshots", "--output", str(OUT / "trap")]).returncode)

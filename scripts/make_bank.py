#!/usr/bin/env python3
"""Generate the bank of simulated pump fleets used to train, tune and check the detector. Uses the organizers' own simulator.

  .venv/bin/python scripts/make_bank.py --out bank            # everything below, about 10 to 15 minutes on 8 cores
  .venv/bin/python scripts/make_bank.py --out bank --only hold

Sets (seeds are fixed so the bank is reproducible):
  train    201-205  five fleets of 8 pumps with random faults, extended with impeller wear and air entrainment
  tune     206-207  used only to choose thresholds
  hold     208-210  untouched until a method is frozen; the number to quote
  healthy  301-306  fleets with no faults, to measure false alerts per pump-month. The generator needs at least one event per fleet, so pump -01
                    gets a 30 minute gateway outage and is left out of the count: 6 fleets x 7 pumps x 7 days = 294 pump-days
Every fleet is 8 pumps x 7 days at 1 Hz, written by `make_dataset.py --tier full` with all labels visible.
The bank is data: it is not committed (see .gitignore). It stays inside the rules, which allow the simulator source and your own data.
"""
import argparse
import copy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
import retrofit_sim

PACK = Path(retrofit_sim.__file__).resolve().parents[2]            # the organizers' pack that `make setup-pack` installed
SETS = {"train": [201, 202, 203, 204, 205], "tune": [206, 207], "hold": [208, 209, 210], "healthy": [301, 302, 303, 304, 305, 306]}


def plain(x):
    """numpy scalars and arrays to plain Python so that the config can be written as YAML."""
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    return x


def build_assets(public_cfg: dict, seed: int, healthy: bool, n_assets: int = 8, days: float = 7.0) -> list:
    from retrofit_sim.stress import sample_fleet
    fleet = sample_fleet(public_cfg, seed, n_assets=n_assets, days=days, missing_prob=0.25)
    rng = np.random.default_rng([seed, 4242])
    horizon = days * 24
    for k, a in enumerate(fleet):
        a["asset_id"] = f"B{seed}-{k + 1:02d}"
        a["split"] = "train"                                  # so that the writer exports every label to events_train.csv
        a["site"] = f"Bank fleet {seed} (fictional)"
        if healthy:
            a["scenario"] = [{"type": "COMMUNICATION_LOSS", "sensor_tag": "GATEWAY", "onset_h": 60, "end_h": 60.5, "jitter_h": 2}] if k == 0 else []
            continue
        types = {s["type"] for s in a["scenario"]}
        if rng.random() < 0.35 and "IMPELLER_WEAR" not in types:        # pre-existing wear, as in the public train pumps
            iw0 = float(rng.uniform(0.02, 0.08))
            a["scenario"].append({"type": "IMPELLER_WEAR", "onset_h": -float(rng.uniform(100, 600)), "jitter_h": 0,
                                  "params": {"rate_per_h": float(rng.uniform(3e-5, 8e-5)), "iw0": iw0, "iw_max": iw0 + float(rng.uniform(0.03, 0.07))}})
        if rng.random() < 0.3 and "AIR_ENTRAINMENT" not in types:
            on = float(rng.uniform(0.2, 0.8) * horizon)
            a["scenario"].append({"type": "AIR_ENTRAINMENT", "onset_h": round(on, 1), "end_h": round(min(horizon - 1, on + rng.uniform(3, 9)), 1),
                                  "jitter_h": 1, "params": {"alpha_max": float(rng.uniform(0.015, 0.04))}})
    return fleet


def make_fleet(name: str, seed: int, healthy: bool, out: Path) -> str:
    cfg_dir = out / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    pub = yaml.safe_load((PACK / "configs" / "fleet_public.yaml").read_text(encoding="utf-8"))
    cfg = copy.deepcopy(pub)
    cfg["assets"] = plain(build_assets(pub, seed, healthy))
    cfg_path = cfg_dir / f"{name}_{seed}.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    dest = out / name / f"s{seed}"
    if (dest / "public" / "features_1min.parquet").exists():
        return f"{name} {seed}: exists"
    cmd = [sys.executable, str(PACK / "make_dataset.py"), "--tier", "full", "--seed", str(seed), "--fleet-config", str(cfg_path),
           "--no-snapshots", "--output", str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    (dest.parent / f"log_{seed}.txt").parent.mkdir(parents=True, exist_ok=True)
    (dest.parent / f"log_{seed}.txt").write_text((r.stdout or "")[-2000:] + (r.stderr or "")[-2000:])
    return f"{name} {seed}: {'ok' if r.returncode == 0 else 'FAILED'}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "bank"))
    ap.add_argument("--only", choices=sorted(SETS), default=None)
    ap.add_argument("--jobs", type=int, default=7)
    a = ap.parse_args()
    out = Path(a.out)
    jobs = [(n, s) for n, seeds in SETS.items() if a.only in (None, n) for s in seeds]
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for msg in ex.map(lambda j: make_fleet(j[0], j[1], j[0] == "healthy", out), jobs):
            print(msg, flush=True)
    (out / "DONE").write_text("ok\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

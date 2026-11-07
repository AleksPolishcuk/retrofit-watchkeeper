"""Commissioning check: do the values look like the units and tags that the asset record says they are?

Scenario P05: a transmitter with other units, or the tags of two pumps swapped, produces plausible-looking but wrong numbers. Comparing the median of each channel
while the pump runs with the rated and design values of the asset record catches most such mix-ups (a factor of ten, a thousand, 6.9 for psi against kPa, 1.8 for Fahrenheit).
It reports; it never changes a value.
"""
from __future__ import annotations

import pandas as pd

# channel, asset column holding the reference, lowest and highest plausible ratio of the running median to the reference, label
RATIOS = [
    ("motor_current_a", "motor_rated_current_a", 0.25, 1.35, "Motor current"),
    ("motor_power_kw", "motor_rated_kw", 0.15, 1.25, "Motor power"),
    ("motor_speed_rpm", "motor_rated_rpm", 0.30, 1.15, "Speed"),
    ("flow_m3_h", "design_flow_m3_h", 0.15, 1.7, "Flow"),
]
G = 9.81                          # kPa per metre of water column
TEMPERATURES = ("fluid_temp_c", "bearing_temp_c", "motor_winding_temp_c")


def check_ranges(feat: pd.DataFrame, asset) -> list[dict]:
    f = feat
    if "operating_mode" in f:
        f = f[f["operating_mode"] == "RUNNING"]
    issues: list[dict] = []
    if len(f) < 30:
        return issues

    def med(ch):
        c = f.get(f"{ch}__mean")
        return None if c is None or c.notna().sum() < 30 else float(c.median())

    for ch, ref_col, lo, hi, label in RATIOS:
        v, ref = med(ch), asset.get(ref_col)
        if v is None or ref is None or pd.isna(ref) or float(ref) <= 0:
            continue
        r = v / float(ref)
        if not lo <= r <= hi:
            issues.append({"channel": ch, "ratio": round(r, 2), "message": f"{label} is {r:.2f} times its rated or design value while the pump runs: check units and tag mapping."})
    v, head = med("discharge_pressure_kpa"), asset.get("design_head_m")
    if v is not None and head is not None and not pd.isna(head) and float(head) > 0:
        r = v / (float(head) * G)
        if not 0.2 <= r <= 3.0:
            issues.append({"channel": "discharge_pressure_kpa", "ratio": round(r, 2), "message": f"Discharge pressure is {r:.2f} times what the design head implies: check units (kPa, bar, psi) and tag mapping."})
    for ch in TEMPERATURES:
        v = med(ch)
        if v is not None and not -30 <= v <= 160:
            issues.append({"channel": ch, "ratio": None, "message": f"{ch.replace('_', ' ')} median is {v:.0f}: check units (Celsius expected)."})
    return issues

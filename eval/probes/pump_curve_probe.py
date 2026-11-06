"""Exploration only: how well does a pump-curve + design-point model predict discharge pressure on healthy vs impeller-wear pumps?"""
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from retrofit_sim import physics as ph
from watchkeeper.evalkit import load_dev

d = load_dev()
A = d.assets.set_index("asset_id")
wear = set(d.events[d.events.fault_type == "IMPELLER_WEAR"].asset_id)
rows = []
for a in d.ids:
    r_ = A.loc[a]
    f = d.feat[d.feat.asset_id == a].copy()
    f["t"] = pd.to_datetime(f["window_start_utc"], utc=True)
    f = f.set_index("t").sort_index()
    f = f[(f.running_fraction >= 0.99)]
    pdm = f["discharge_pressure_kpa__mean"]
    sal = 6.0 if "seawater" in str(r_.fluid).lower() else 0.0
    rho = ph.water_density(f["fluid_temp_c__mean"], sal)
    n = f.get("motor_speed_rpm__mean")
    r = (n / r_.motor_rated_rpm).clip(0.3, 1.1) if n is not None and n.notna().any() else pd.Series(1.0, index=f.index)
    h0 = r_.pump_shutoff_head_m / r_.pump_rated_head_m
    K = (r_.design_head_m - r_.static_head_m) / r_.design_flow_m3_h ** 2
    Hexp = []
    for ri in r.values:
        Q = float(ph.solve_operating_point(ri, r_.pump_rated_head_m, r_.pump_rated_flow_m3_h, h0, r_.static_head_m, K)) if np.isfinite(ri) else np.nan
        Hexp.append(float(ph.pump_head(Q, ri, r_.pump_rated_head_m, r_.pump_rated_flow_m3_h, h0)) if np.isfinite(Q) else np.nan)
    Hexp = pd.Series(Hexp, index=f.index)
    ps = f.get("suction_pressure_kpa__mean")
    ps_known = ps is not None and ps.notna().any()
    pexp = rho * ph.G * Hexp / 1000.0 + (ps if ps_known else 0.0)
    ratio = pdm / pexp
    rows.append({"asset": a, "tier": r_.instrumentation_tier[:2], "control": r_.control[:9], "impeller_wear": a in wear, "ps_known": ps_known,
                 "median pd meas": pdm.median(), "median pd model": pexp.median(), "ratio med": ratio.median(), "ratio p10": ratio.quantile(.1), "ratio p90": ratio.quantile(.9)})
pd.set_option("display.width", 250, "display.max_columns", 30)
print(pd.DataFrame(rows).round(3).to_string(index=False))

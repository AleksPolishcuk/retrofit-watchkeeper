"""Exploration only (not part of the repo): estimate the NPSH margin from measured channels on dev pumps."""
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from retrofit_sim import physics as ph
from watchkeeper.evalkit import load_dev

d = load_dev()
A = d.assets.set_index("asset_id")
rows = []
for a in d.ids:
    r_ = A.loc[a]
    f = d.feat[d.feat.asset_id == a].copy()
    f["t"] = pd.to_datetime(f["window_start_utc"], utc=True)
    f = f.set_index("t").sort_index()
    if "suction_pressure_kpa__mean" not in f or f["suction_pressure_kpa__mean"].notna().sum() == 0:
        continue
    sal = 6.0 if "Seawater" in str(r_.fluid) else 0.0
    T = f["fluid_temp_c__mean"]
    rho = ph.water_density(T, sal)
    n = f.get("motor_speed_rpm__mean")
    ratio = (n / r_.motor_rated_rpm) if (n is not None and n.notna().any()) else pd.Series(1.0, index=f.index)
    ratio = ratio.clip(lower=0.3)
    q = (r_.design_flow_m3_h / (ratio * r_.pump_rated_flow_m3_h)).clip(0.3, 1.3)
    v = 2.5 * q * ratio                                   # inlet velocity at the estimated flow (m/s), approx
    p_tot = f["suction_pressure_kpa__mean"] * 1000 + ph.P_ATM + 0.5 * rho * v ** 2
    npsha = (p_tot - ph.vapour_pressure_pa(T)) / (rho * ph.G)
    npshr = ph.npsh_required(q * ratio * r_.pump_rated_flow_m3_h, ratio, r_.pump_rated_flow_m3_h, r_.npsh3_at_bep_m)
    sigma = (npsha / npshr).where(f["running_fraction"] >= 0.99)
    f["sigma"] = sigma
    ev = d.events[(d.events.asset_id == a) & (d.events.fault_type == "CAVITATION")]
    inev = pd.Series(False, index=f.index)
    for e in ev.itertuples():
        end = pd.to_datetime(e.end_utc, utc=True) + pd.Timedelta(minutes=30)
        inev |= (f.index >= pd.to_datetime(e.onset_utc, utc=True)) & (f.index <= end)
    rows.append({"asset": a, "tier": r_.instrumentation_tier[:2], "fluid": str(r_.fluid)[:14], "npshr_bep": r_.npsh3_at_bep_m,
                 "sigma_p01": sigma.quantile(0.01), "sigma_p50": sigma.median(), "sigma_min": sigma.min(),
                 "frac<1.15": (sigma < 1.15).mean(), "n_cav_events": len(ev),
                 "sigma_in_cav": sigma[inev].median() if inev.any() else np.nan, "frac<1.15_in_cav": (sigma[inev] < 1.15).mean() if inev.any() else np.nan,
                 "frac<1.15_outside": (sigma[~inev] < 1.15).mean()})
    if a == "PUMP-06":
        pass
pd.set_option("display.width", 250, "display.max_columns", 30)
print(pd.DataFrame(rows).round(3).to_string(index=False))

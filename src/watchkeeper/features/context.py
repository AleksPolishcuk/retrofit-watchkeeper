"""Expected motor speed from the operating context, for pumps whose speed follows a temperature set-point.

On a ship seawater loop with `VFD_TEMPERATURE` control the drive raises speed with cooling demand and lowers it when the sea is cold
(TECHNICAL_MODEL.md section 4): required flow = demand x (36 - 25) / (36 - supply water temperature), clipped to 40-115 percent of design flow,
and speed is the one that delivers that flow on the clean system curve through the design point. Every input is public: the pump data sheet
(assets.csv), the context table (duty demand and water temperature) and those documented constants.

Measured speed above the expected speed means the pump needs more speed than it should for the same duty: strainer clogging, restriction
or impeller wear. It does not depend on the suction transmitter, so it keeps working when that instrument drifts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from retrofit_sim import physics as ph

T_SET_C, T_DESIGN_C, MIN_FLOW_FRAC, MAX_FLOW_FRAC = 36.0, 25.0, 0.40, 1.15


def applies(asset: pd.Series) -> bool:
    return str(asset.get("control")) == "VFD_TEMPERATURE"


def expected_speed_ratio(asset: pd.Series, demand_pct: np.ndarray, supply_temp_c: np.ndarray) -> np.ndarray:
    need = (np.asarray(demand_pct, float) / 100.0) * (T_SET_C - T_DESIGN_C) / np.maximum(T_SET_C - np.asarray(supply_temp_c, float), 3.0)
    q_req = np.clip(need, MIN_FLOW_FRAC, MAX_FLOW_FRAC) * float(asset["design_flow_m3_h"])
    h_static = float(asset["static_head_m"])
    k = (float(asset["design_head_m"]) - h_static) / float(asset["design_flow_m3_h"]) ** 2
    h0 = float(asset["pump_shutoff_head_m"]) / float(asset["pump_rated_head_m"])
    r = ph.speed_for_flow(q_req, float(asset["pump_rated_head_m"]), float(asset["pump_rated_flow_m3_h"]), h0, h_static, k)
    r_min = float(asset["min_speed_ratio"]) if pd.notna(asset.get("min_speed_ratio")) else 0.5
    return np.clip(r, r_min, 1.0)


def speed_residual(g: pd.DataFrame, asset: pd.Series, ctx: pd.DataFrame) -> pd.Series:
    """Measured minus expected speed ratio per minute of `g`; NaN when the pump is not running or the context is missing."""
    nan = pd.Series(np.nan, index=g.index)
    if ctx is None or ctx.empty or not applies(asset) or "motor_speed_rpm__mean" not in g:
        return nan
    c = ctx.assign(t=pd.to_datetime(ctx["timestamp_utc"], utc=True)).drop_duplicates("t").set_index("t").sort_index()[["duty_demand_pct", "supply_water_temp_c"]]
    m = c.reindex(pd.to_datetime(g["window_start_utc"], utc=True), method="nearest", tolerance=pd.Timedelta("90s"))
    r_exp = expected_speed_ratio(asset, m["duty_demand_pct"].to_numpy(), m["supply_water_temp_c"].to_numpy())
    r_meas = (g["motor_speed_rpm__mean"] / float(asset["motor_rated_rpm"])).to_numpy()
    res = pd.Series(r_meas - r_exp, index=g.index)
    running = (g["running_fraction"].fillna(0.0) >= 0.99).to_numpy() if "running_fraction" in g else np.ones(len(g), bool)
    return res.where(running)

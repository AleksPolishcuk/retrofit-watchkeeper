"""Estimated NPSH margin from measured suction pressure and fluid temperature (physics-informed, no training).

margin = NPSHa / NPSHr. NPSHa is the total head at the pump inlet above the vapour pressure; the suction gauge reads static
pressure, so the dynamic head of the inlet velocity is added back. NPSHr follows the pump family in `retrofit_sim.physics`
and the pump data sheet in assets.csv. Cavitation starts when the margin falls to about 1.15 (organizer label definition).

Flow is usually not measured on retrofit pumps, so the operating point is assumed at the design flow for the current speed.
Only static asset information and the current minute are used, so the estimate is causal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from retrofit_sim import physics as ph

SEAWATER_PSU = 6.0                    # brackish Baltic water used by the benchmark
INLET_VELOCITY_BEP = 2.5              # m/s at BEP flow (suction line sizing used by the simulator)
CAVITATION_MARGIN = 1.15


def npsh_margin(g: pd.DataFrame, asset: pd.Series) -> pd.Series:
    """Per-minute margin for one pump, NaN when it cannot be estimated (no suction pressure, not running)."""
    nan = pd.Series(np.nan, index=g.index)
    if "suction_pressure_kpa__mean" not in g or "fluid_temp_c__mean" not in g:
        return nan
    ps, temp = g["suction_pressure_kpa__mean"], g["fluid_temp_c__mean"]
    if ps.notna().sum() == 0 or temp.notna().sum() == 0:
        return nan
    salinity = SEAWATER_PSU if "seawater" in str(asset["fluid"]).lower() else 0.0
    rho = ph.water_density(temp, salinity)
    if "motor_speed_rpm__mean" in g and g["motor_speed_rpm__mean"].notna().any():
        r = (g["motor_speed_rpm__mean"] / asset["motor_rated_rpm"]).clip(lower=0.3, upper=1.1)
    else:
        r = pd.Series(1.0, index=g.index)
    q = (asset["design_flow_m3_h"] / (r * asset["pump_rated_flow_m3_h"])).clip(0.3, 1.3)       # flow ratio at the current speed
    v = INLET_VELOCITY_BEP * q * r                                                              # inlet velocity, m/s
    p_total = ps * 1000.0 + ph.P_ATM + 0.5 * rho * v ** 2
    npsha = (p_total - ph.vapour_pressure_pa(temp)) / (rho * ph.G)
    npshr = ph.npsh_required(q * r * asset["pump_rated_flow_m3_h"], r, asset["pump_rated_flow_m3_h"], asset["npsh3_at_bep_m"])
    margin = pd.Series(np.asarray(npsha / npshr), index=g.index)
    running = g["running_fraction"].fillna(0.0) >= 0.99 if "running_fraction" in g else pd.Series(True, index=g.index)
    return margin.where(running)

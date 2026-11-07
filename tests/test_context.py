import numpy as np
import pandas as pd

from watchkeeper.features.context import applies, expected_speed_ratio

A = pd.Series({"control": "VFD_TEMPERATURE", "design_flow_m3_h": 500.0, "design_head_m": 25.5, "static_head_m": 3.0, "pump_shutoff_head_m": 31.7,
               "pump_rated_head_m": 26.0, "pump_rated_flow_m3_h": 520.0, "min_speed_ratio": 0.5})


def test_expected_speed_rises_with_demand_and_with_warmer_water_and_stays_inside_the_drive_limits():
    low, high = expected_speed_ratio(A, np.array([40.0, 100.0]), np.array([10.0, 10.0]))
    assert low <= high
    cold, warm = expected_speed_ratio(A, np.array([90.0, 90.0]), np.array([5.0, 25.0]))
    assert cold <= warm
    r = expected_speed_ratio(A, np.linspace(0, 120, 25), np.linspace(0, 30, 25))
    assert (r >= 0.5).all() and (r <= 1.0).all()


def test_the_control_law_only_applies_to_temperature_controlled_drives():
    assert applies(A) and not applies(A.copy().rename({"control": "x"})) and not applies(pd.Series({"control": "FIXED_SPEED"}))

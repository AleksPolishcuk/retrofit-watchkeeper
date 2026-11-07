"""Detection: when to raise an alert."""
from .alerting import alerts_from_flag, alerts_from_flags, b1_flag, split_flags

__all__ = ["alerts_from_flag", "alerts_from_flags", "b1_flag", "split_flags"]

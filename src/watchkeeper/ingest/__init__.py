"""Read-only ingest: telemetry messages (replay or a broker you run yourself) to the one-minute features the detector uses."""
from .aggregate import MinuteAggregator, rows_to_frame

__all__ = ["MinuteAggregator", "rows_to_frame"]

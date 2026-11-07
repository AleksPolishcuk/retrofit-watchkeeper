"""Raw telemetry messages -> finished one-minute feature rows, in the same shape as the organizers' `features_1min`.

Input is what `python -m retrofit_sim replay` prints: one JSON object per line, `{"topic": "retrofit/<site>/<asset>/telemetry", "payload": {...}}`,
one message per second per pump. Nothing here publishes, subscribes or writes to a device. Only telemetry topics are read; any other topic
(a command topic, for example) is counted and ignored without looking at its payload.

A minute is finished when a message arrives that is `lateness_s` seconds past its end. The aggregator is tolerant on purpose:

- the same timestamp twice is kept once (the last copy wins) and counted;
- messages that arrive out of order inside the lateness window are placed correctly;
- a message for a minute that was already finished is dropped and counted (a finished minute is never revised, so alerts stay causal);
- unparsable lines, wrong shapes and non-numeric channel values are counted and skipped, never fatal.

Per channel and minute: mean, std (sample std, as pandas), min, max and count of values that arrived. Also the dominant operating mode, the running
fraction, the OR of the quality flag bits, and the number of rows, as in the organizers' file.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

META_KEYS = frozenset({"timestamp_utc", "operating_mode", "quality_flags", "sensor_source", "sample_interval_s"})
STATS = ("mean", "std", "min", "max", "count")
QUALITY_BITS = (1, 2, 4, 8, 16)


def epoch_seconds(ts: str) -> float:
    """ISO-8601 timestamp (`Z` or an offset; no zone means UTC) to epoch seconds."""
    s = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class MinuteAggregator:
    """Collects messages per pump and hands back finished minutes as dict rows (see `rows_to_frame`)."""

    def __init__(self, lateness_s: float = 5.0, channels: dict[str, list[str]] | None = None):
        self.lateness = float(lateness_s)
        self.known: dict[str, list[str]] = {a: list(c) for a, c in (channels or {}).items()}
        self._open: dict[str, dict[int, dict[float, dict]]] = defaultdict(dict)
        self._watermark: dict[str, float] = {}
        self._closed: dict[str, int] = {}
        self.stats: Counter = Counter()

    # -- input ---------------------------------------------------------------------------------------------------------------------------
    def feed_line(self, line: str) -> list[dict]:
        line = line.strip()
        if not line:
            return []
        try:
            msg = json.loads(line)
        except ValueError:
            self.stats["messages"] += 1
            self.stats["malformed"] += 1
            return []
        return self.feed(msg)

    def feed(self, msg) -> list[dict]:
        self.stats["messages"] += 1
        topic = msg.get("topic") if isinstance(msg, dict) else None
        if not isinstance(topic, str):
            self.stats["malformed"] += 1
            return []
        parts = topic.split("/")
        if len(parts) < 2 or parts[-1] != "telemetry":                      # decided on the topic alone: the payload of another topic is never looked at
            self.stats["ignored_topic"] += 1
            return []
        payload = msg.get("payload")
        if not isinstance(payload, dict):
            self.stats["malformed"] += 1
            return []
        asset = parts[-2]
        try:
            ts = epoch_seconds(payload["timestamp_utc"])
        except (KeyError, ValueError, TypeError, AttributeError):
            self.stats["malformed"] += 1
            return []
        if not math.isfinite(ts):
            self.stats["malformed"] += 1
            return []
        minute = int(ts // 60) * 60
        if minute <= self._closed.get(asset, -1 << 60):
            self.stats["late_dropped"] += 1
            return []
        wm = self._watermark.get(asset)
        if wm is not None and ts < wm:
            self.stats["out_of_order"] += 1
        self._watermark[asset] = ts if wm is None else max(wm, ts)
        known = self.known.setdefault(asset, [])
        for k, v in payload.items():
            if k not in META_KEYS and _is_number(v) and k not in known:
                known.append(k)
        bucket = self._open[asset].setdefault(minute, {})
        if ts in bucket:
            self.stats["duplicates" if bucket[ts] == payload else "conflicts"] += 1
        bucket[ts] = payload
        return self._finish_ready(asset)

    def flush(self, asset: str | None = None) -> list[dict]:
        """End of stream: finish every minute that is still open."""
        out = []
        for a in ([asset] if asset else sorted(self._open)):
            for m in sorted(self._open[a]):
                out.append(self._finish(a, m))
            self._open[a].clear()
        return out

    # -- internals -----------------------------------------------------------------------------------------------------------------------
    def _finish_ready(self, asset: str) -> list[dict]:
        out, wm = [], self._watermark[asset]
        pending = self._open[asset]
        for m in sorted(pending):
            if wm < m + 60 + self.lateness:
                break
            out.append(self._finish(asset, m))
            del pending[m]
        return out

    def _finish(self, asset: str, minute: int) -> dict:
        self._closed[asset] = max(self._closed.get(asset, minute), minute)
        self.stats["minutes"] += 1
        bucket = self._open[asset][minute]
        payloads = [bucket[t] for t in sorted(bucket)]
        row: dict = {"asset_id": asset, "window_start_utc": pd.Timestamp(minute, unit="s", tz="UTC")}
        for c in self.known.get(asset, []):
            vals = []
            for p in payloads:
                v = p.get(c)
                if v is None:
                    continue
                if not _is_number(v):
                    self.stats["bad_values"] += 1
                    continue
                if not math.isfinite(v):
                    continue
                vals.append(v)
            n = len(vals)
            a = np.asarray(vals, dtype="float64")
            row[f"{c}__mean"] = float(a.mean()) if n else math.nan
            row[f"{c}__std"] = float(a.std(ddof=1)) if n > 1 else math.nan
            row[f"{c}__min"] = float(a.min()) if n else math.nan
            row[f"{c}__max"] = float(a.max()) if n else math.nan
            row[f"{c}__count"] = n
        modes = Counter(str(p.get("operating_mode", "UNKNOWN")) for p in payloads)
        top = max(modes.values())
        row["operating_mode"] = min(m for m, c in modes.items() if c == top)          # a tie goes to the first name alphabetically, as in the organizers' file
        row["running_fraction"] = modes.get("RUNNING", 0) / len(payloads)
        flags = [int(p["quality_flags"]) if _is_number(p.get("quality_flags")) else 0 for p in payloads]
        acc = 0
        for bit in QUALITY_BITS:
            if any(f & bit for f in flags):
                acc |= bit
        row["quality_any"] = acc
        row["rows"] = len(payloads)
        return row


def rows_to_frame(rows: list[dict]) -> pd.DataFrame:
    """Finished-minute rows to a feature frame. Channels that never arrived for a pump stay NaN; floats are float32 like the organizers' file."""
    if not rows:
        return pd.DataFrame(columns=["asset_id", "window_start_utc"])
    df = pd.DataFrame(rows)
    df["window_start_utc"] = pd.to_datetime(df["window_start_utc"], utc=True).astype("datetime64[ms, UTC]")
    for c in df.columns:
        if df[c].dtype == "float64":
            df[c] = df[c].astype("float32")
    df["quality_any"] = df["quality_any"].astype("int16")
    df["rows"] = df["rows"].astype("int16")
    return df

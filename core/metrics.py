"""Rolling aim metrics with optional CSV logging."""

from __future__ import annotations

import csv
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, Optional

logger = logging.getLogger(__name__)

_LOG_DIR = Path("logs")
_CSV_PATH = _LOG_DIR / "metrics.csv"


@dataclass
class MetricsCollector:
    """Collects reaction, snap, and settle time samples."""

    reaction_samples: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    snap_samples: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    settle_samples: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    _lock_time: float = 0.0
    _snap_time: float = 0.0
    _settled: bool = False
    _log_csv: bool = True

    def lock(self) -> None:
        """Record the moment a target is first locked."""
        self._lock_time = time.monotonic()
        self._snap_time = 0.0
        self._settled = False

    def snap(self) -> None:
        """Record that the aim first reached the target vicinity."""
        if self._snap_time == 0.0 and self._lock_time > 0.0:
            self._snap_time = time.monotonic()
            elapsed = (self._snap_time - self._lock_time) * 1000.0
            self.snap_samples.append(elapsed)

    def settle(self) -> None:
        """Record that the aim has settled on target."""
        if not self._settled and self._snap_time > 0.0:
            self._settled = True
            elapsed = (time.monotonic() - self._snap_time) * 1000.0
            self.settle_samples.append(elapsed)

    def reaction(self, ms: float) -> None:
        """Record a reaction time sample in milliseconds."""
        self.reaction_samples.append(ms)

    def summary(self) -> Dict[str, Optional[float]]:
        """Return summary statistics of collected metrics."""
        def _avg(d: Deque[float]) -> Optional[float]:
            return sum(d) / len(d) if d else None

        def _p95(d: Deque[float]) -> Optional[float]:
            if not d:
                return None
            s = sorted(d)
            idx = int(len(s) * 0.95)
            return s[min(idx, len(s) - 1)]

        return {
            "reaction_avg_ms": _avg(self.reaction_samples),
            "snap_avg_ms": _avg(self.snap_samples),
            "settle_avg_ms": _avg(self.settle_samples),
            "snap_p95_ms": _p95(self.snap_samples),
            "settle_p95_ms": _p95(self.settle_samples),
            "reaction_count": float(len(self.reaction_samples)),
            "snap_count": float(len(self.snap_samples)),
            "settle_count": float(len(self.settle_samples)),
        }

    def csv_append(self) -> None:
        """Append current summary to logs/metrics.csv."""
        if not self._log_csv:
            return
        try:
            _LOG_DIR.mkdir(exist_ok=True)
            s = self.summary()
            exists = _CSV_PATH.exists()
            with open(_CSV_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp"] + list(s.keys()))
                if not exists:
                    writer.writeheader()
                row = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
                row.update({k: (f"{v:.1f}" if v is not None else "") for k, v in s.items()})
                writer.writerow(row)
        except OSError:
            logger.warning("Failed to write metrics CSV", exc_info=True)

"""
predictor.py
Estimates fill rate from historical readings and predicts when a bin
will reach 100% capacity.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import statistics
import logging

logger = logging.getLogger(__name__)


class BinStatus(str, Enum):
    NORMAL = "Normal"       # < 60 %
    WARNING = "Warning"     # 60–85 %
    CRITICAL = "Critical"   # > 85 %


@dataclass
class PredictionResult:
    bin_id: str
    current_fill: float             # 0.0 – 1.0
    fill_rate_per_hour: float       # Δfill per hour (can be negative if bin was emptied)
    minutes_until_full: Optional[int]   # None if fill rate ≤ 0 or already full
    predicted_full_at: Optional[str]    # ISO datetime string
    status: BinStatus
    confidence: float               # 0.0 – 1.0


class Predictor:
    """
    Predicts time-to-full for a single bin given its fill-level history.

    Algorithm:
    1. Take last N readings (configurable, default 10).
    2. Compute per-interval fill rates (Δfill / Δtime_hours).
    3. Use median rate (robust against sensor spikes).
    4. Extrapolate: minutes_until_full = (1 - current_fill) / rate * 60.
    5. Confidence = f(number of readings, rate variance).
    """

    # Thresholds for status assignment
    WARNING_THRESHOLD = 0.60
    CRITICAL_THRESHOLD = 0.85

    def __init__(self, window_size: int = 10, min_readings: int = 2):
        self.window_size = window_size
        self.min_readings = min_readings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, bin_id: str, history: list[dict], current_fill: float) -> PredictionResult:
        """
        history: list of {"timestamp": ISO str, "fill_level": float}, sorted ascending.
        current_fill: latest fill level (0–1).
        """
        status = self._classify(current_fill)
        window = history[-self.window_size:] if len(history) >= self.window_size else history

        if len(window) < self.min_readings:
            # Not enough data — return status only
            return PredictionResult(
                bin_id=bin_id,
                current_fill=current_fill,
                fill_rate_per_hour=0.0,
                minutes_until_full=None,
                predicted_full_at=None,
                status=status,
                confidence=0.0,
            )

        rates = self._compute_rates(window)

        if not rates:
            return PredictionResult(
                bin_id=bin_id,
                current_fill=current_fill,
                fill_rate_per_hour=0.0,
                minutes_until_full=None,
                predicted_full_at=None,
                status=status,
                confidence=0.0,
            )

        median_rate = statistics.median(rates)   # fill fraction per hour
        confidence = self._confidence(rates)

        minutes_until_full = None
        predicted_full_at = None

        if median_rate > 0 and current_fill < 1.0:
            remaining = 1.0 - current_fill
            hours_left = remaining / median_rate
            minutes_until_full = int(hours_left * 60)
            predicted_full_at = (datetime.utcnow() + timedelta(minutes=minutes_until_full)).isoformat()

        return PredictionResult(
            bin_id=bin_id,
            current_fill=current_fill,
            fill_rate_per_hour=round(median_rate, 5),
            minutes_until_full=minutes_until_full,
            predicted_full_at=predicted_full_at,
            status=status,
            confidence=round(confidence, 2),
        )

    def predict_many(self, bins: list[dict]) -> list[PredictionResult]:
        """
        Convenience wrapper for multiple bins.
        Each bin dict: {bin_id, current_fill, history: [{timestamp, fill_level}]}.
        """
        results = []
        for b in bins:
            try:
                result = self.predict(
                    bin_id=b["bin_id"],
                    history=b.get("history", []),
                    current_fill=b["current_fill"],
                )
                results.append(result)
            except Exception as e:
                logger.error("Prediction failed for bin %s: %s", b.get("bin_id"), e)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_rates(self, window: list[dict]) -> list[float]:
        """Returns list of fill rates (Δfill/hour) between consecutive readings."""
        rates = []
        for i in range(1, len(window)):
            try:
                t0 = datetime.fromisoformat(window[i - 1]["timestamp"])
                t1 = datetime.fromisoformat(window[i]["timestamp"])
                f0 = window[i - 1]["fill_level"]
                f1 = window[i]["fill_level"]

                delta_hours = (t1 - t0).total_seconds() / 3600
                if delta_hours <= 0:
                    continue

                rate = (f1 - f0) / delta_hours

                # Ignore negative rates (bin was emptied between readings)
                if rate < 0:
                    continue

                rates.append(rate)
            except (KeyError, ValueError) as e:
                logger.warning("Skipping bad history entry: %s", e)
        return rates

    def _classify(self, fill_level: float) -> BinStatus:
        if fill_level >= self.CRITICAL_THRESHOLD:
            return BinStatus.CRITICAL
        if fill_level >= self.WARNING_THRESHOLD:
            return BinStatus.WARNING
        return BinStatus.NORMAL

    def _confidence(self, rates: list[float]) -> float:
        """
        Confidence is higher when:
        - More readings are available (up to window_size).
        - Variance in rates is low (consistent fill pattern).
        """
        if len(rates) == 0:
            return 0.0

        count_score = min(len(rates) / self.window_size, 1.0)

        if len(rates) < 2:
            variance_score = 0.5
        else:
            mean = statistics.mean(rates)
            stdev = statistics.stdev(rates)
            cv = stdev / mean if mean > 0 else 1.0   # coefficient of variation
            variance_score = max(0.0, 1.0 - min(cv, 1.0))

        return (count_score + variance_score) / 2

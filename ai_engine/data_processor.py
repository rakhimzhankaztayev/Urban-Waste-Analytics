"""
data_processor.py
Handles raw sensor data: validation, anomaly detection, normalization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SensorReading:
    bin_id: str
    timestamp: datetime
    fill_level: float          # 0.0 – 1.0
    latitude: float
    longitude: float
    district: str = ""
    raw_value: Optional[float] = None  # raw cm/voltage from sensor

    def __post_init__(self):
        self.fill_level = max(0.0, min(1.0, self.fill_level))


@dataclass
class ProcessedBin:
    bin_id: str
    latitude: float
    longitude: float
    district: str
    fill_level: float
    history: list[dict] = field(default_factory=list)   # [{timestamp, fill_level}, ...]
    anomaly_detected: bool = False
    anomaly_reason: str = ""


class DataProcessor:
    """
    Cleans and validates raw sensor readings before feeding them
    to the Predictor or Optimizer.
    """

    # If fill level drops by more than this in one interval → bin was emptied
    EMPTIED_DROP_THRESHOLD = 0.35

    # Readings outside [0, 1] after normalization → discard
    VALID_RANGE = (0.0, 1.0)

    def __init__(self, sensor_max_cm: float = 100.0):
        """
        sensor_max_cm: physical depth of the bin in cm.
        Raw sensor value is distance from lid to trash surface.
        fill_level = 1 - (raw_cm / sensor_max_cm)
        """
        self.sensor_max_cm = sensor_max_cm

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize_raw(self, raw_cm: float) -> float:
        """Convert raw distance (cm) to fill level 0–1."""
        level = 1.0 - (raw_cm / self.sensor_max_cm)
        return round(max(0.0, min(1.0, level)), 4)

    def validate_reading(self, reading: SensorReading) -> tuple[bool, str]:
        """Returns (is_valid, reason)."""
        if not (self.VALID_RANGE[0] <= reading.fill_level <= self.VALID_RANGE[1]):
            return False, f"fill_level {reading.fill_level} out of range"
        if reading.timestamp > datetime.utcnow():
            return False, "timestamp is in the future"
        return True, ""

    def detect_anomaly(self, history: list[dict]) -> tuple[bool, str]:
        """
        Scans history for anomalies:
        - Sudden drop  → bin was emptied (not an error, just a state reset)
        - Sudden spike → sensor glitch
        Returns (anomaly_detected, reason).
        """
        if len(history) < 2:
            return False, ""

        for i in range(1, len(history)):
            prev = history[i - 1]["fill_level"]
            curr = history[i]["fill_level"]
            delta = curr - prev

            if delta < -self.EMPTIED_DROP_THRESHOLD:
                return True, f"bin_emptied: drop of {abs(delta):.2f} detected"

            if delta > 0.5:
                return True, f"sensor_spike: jump of {delta:.2f} detected"

        return False, ""

    def process_readings(self, raw_readings: list[dict]) -> list[ProcessedBin]:
        """
        Main entry point.
        raw_readings: list of dicts from DB / MQTT / mock generator.
        Returns a list of ProcessedBin objects grouped by bin_id.
        """
        # Group by bin_id
        bins: dict[str, ProcessedBin] = {}

        for r in raw_readings:
            try:
                reading = SensorReading(
                    bin_id=r["bin_id"],
                    timestamp=datetime.fromisoformat(r["timestamp"])
                    if isinstance(r["timestamp"], str)
                    else r["timestamp"],
                    fill_level=float(r.get("fill_level", 0)),
                    latitude=float(r["latitude"]),
                    longitude=float(r["longitude"]),
                    district=r.get("district", ""),
                    raw_value=r.get("raw_value"),
                )

                # Normalize from raw sensor if provided
                if reading.raw_value is not None:
                    reading.fill_level = self.normalize_raw(reading.raw_value)

                valid, reason = self.validate_reading(reading)
                if not valid:
                    logger.warning("Skipping invalid reading bin=%s: %s", reading.bin_id, reason)
                    continue

                if reading.bin_id not in bins:
                    bins[reading.bin_id] = ProcessedBin(
                        bin_id=reading.bin_id,
                        latitude=reading.latitude,
                        longitude=reading.longitude,
                        district=reading.district,
                        fill_level=reading.fill_level,
                    )

                bins[reading.bin_id].fill_level = reading.fill_level
                bins[reading.bin_id].history.append(
                    {
                        "timestamp": reading.timestamp.isoformat(),
                        "fill_level": reading.fill_level,
                    }
                )

            except (KeyError, ValueError) as e:
                logger.error("Malformed reading skipped: %s | %s", r, e)

        # Anomaly detection pass
        for b in bins.values():
            anomaly, reason = self.detect_anomaly(b.history)
            b.anomaly_detected = anomaly
            b.anomaly_reason = reason
            if anomaly and "bin_emptied" in reason:
                # Reset fill level to last value after the drop
                b.fill_level = b.history[-1]["fill_level"]
                logger.info("Bin %s was emptied, resetting state.", b.bin_id)

        return list(bins.values())

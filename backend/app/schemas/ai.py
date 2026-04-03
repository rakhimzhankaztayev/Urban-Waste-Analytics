from datetime import datetime

from pydantic import BaseModel, Field


class ReadingInput(BaseModel):
    bin_id: str
    latitude: float
    longitude: float
    fill_level: float = Field(..., description="Fill level in percent (0-100) or normalized value (0-1).")
    timestamp: datetime | None = None
    district: str = "Central"


class StartPoint(BaseModel):
    latitude: float = 43.2389
    longitude: float = 76.9455


class AIReportRequest(BaseModel):
    raw_readings: list[ReadingInput] = Field(default_factory=list)
    start_point: StartPoint = Field(default_factory=StartPoint)


class PredictionOutput(BaseModel):
    bin_id: str
    latitude: float
    longitude: float
    current_fill: float
    status: str
    fill_rate_per_hour: float
    minutes_until_full: int | None
    predicted_full_at: str | None
    confidence: float


class RouteStopOutput(BaseModel):
    order: int
    bin_id: str
    latitude: float
    longitude: float
    district: str
    distance_from_prev_km: float


class RouteOutput(BaseModel):
    stops: list[RouteStopOutput]
    total_distance_km: float
    estimated_duration_min: int
    bins_count: int
    truck_id: str


class ReportOutput(BaseModel):
    what_is_happening: str
    how_critical: str
    recommended_actions: str


class StatisticsOutput(BaseModel):
    total_bins_analysed: int
    critical_bins: int
    warning_bins: int
    normal_bins: int
    average_fill_level: float
    anomalies_detected: int
    anomaly_reasons: list[str]


class AIReportResponse(BaseModel):
    predictions: list[PredictionOutput]
    route: RouteOutput
    report: ReportOutput
    statistics: StatisticsOutput
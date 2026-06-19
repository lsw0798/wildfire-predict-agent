from pydantic import BaseModel


class MonitoringWatchpoint(BaseModel):
    id: str
    province: str
    city: str
    lat: float
    lon: float
    incident_count: int
    latest_year: int | None
    top_cause: str | None
    priority_score: int
    priority_label: str


class MonitoringSummaryResponse(BaseModel):
    generated_at: str
    total_records: int
    watchpoints: list[MonitoringWatchpoint]


class ForestHeatmapPoint(BaseModel):
    id: str
    province: str
    city: str
    lat: float
    lon: float
    risk_score: float
    risk_level: str
    confidence: float
    confidence_margin: float
    review_required: bool
    incident_count: int
    latest_year: int | None
    top_cause: str | None
    circle_radius_m: int
    key_factors: list[str]


class ForestHeatmapResponse(BaseModel):
    generated_at: str
    metric: str
    resolution: float
    total_records: int
    forest_records: int
    filtered_records: int
    points: list[ForestHeatmapPoint]

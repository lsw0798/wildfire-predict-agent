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

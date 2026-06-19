from pydantic import BaseModel, Field

from app.services.spatial_radius import DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM


class AnalyzeRequest(BaseModel):
    lat: float = Field(..., description="위도")
    lon: float = Field(..., description="경도")
    user_type: str = Field(..., description="사용자 유형")
    radius_km: float | None = Field(
        default=None,
        gt=0,
        description=(
            "과거 산불 이력 조회 반경(km). 생략 시 "
            f"{DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM}km 기본값을 사용합니다."
        ),
    )


class AnalyzeResponse(BaseModel):
    risk_level: str
    risk_score: float
    false_positive_risk: str
    confidence: float
    confidence_breakdown: dict[str, float | str | list[str]] = Field(default_factory=dict)
    confidence_reasons: list[str] = Field(default_factory=list)
    confidence_margin: float
    reroute_applied: bool = False
    reroute_reason: str = ""
    model_score: float | None = None
    model_confidence: float = 0.0
    model_version: str = ""
    model_feature_coverage: float = 0.0
    model_decision_mode: str = "rule_only_fallback"
    model_reason: str = ""
    analysis_radius_km: float
    radius_points: dict[str, dict[str, float]]
    key_factors: list[str]
    recommended_actions: list[str]
    risk_summary_text: str
    false_positive_summary_text: str
    xai_reasons: list[str]
    reviewed_signals: list[str]
    data_quality_summary: str
    uncertainty_notes: list[str]
    selected_tools: list[str]
    selection_reason: str
    selection_mode: str

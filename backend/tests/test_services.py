from app.services.false_positive_review import review_false_positive
from app.services.risk_engine import score_risk


def test_score_risk_high_when_dry_and_windy():
    result = score_risk({
        "humidity_percent": 18,
        "wind_speed": 8.5,
        "drought_duration_days": 28,
        "slope": 18,
        "fuel_moisture": 10,
        "vulnerable": 2000,
    })
    assert result["risk_level"] in {"high", "critical"}


def test_false_positive_review_medium_or_higher_when_fog_like():
    result = review_false_positive({
        "visibility": 400,
        "humidity_percent": 92,
        "wind_speed": 0.4,
        "surface_temperature": 8,
        "fire_intensity": "약함",
    })
    assert result["false_positive_risk"] in {"medium", "high"}

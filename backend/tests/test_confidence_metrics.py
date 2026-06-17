import pytest

from app.services.confidence_metrics import build_confidence_metrics


def test_build_confidence_metrics_returns_tighter_margin_for_live_sources_and_richer_history():
    result = build_confidence_metrics(
        confidence=0.84,
        nearby_incident_count=9,
        estimated_fields=[],
        historical_source="live",
        realtime_source="live",
    )

    assert result["confidence_margin"] == pytest.approx(0.06)
    assert result["confidence_lower_bound"] == pytest.approx(0.78)
    assert result["confidence_upper_bound"] == pytest.approx(0.9)
    assert result["source_quality_score"] == pytest.approx(0.95)
    assert "안정적" in result["source_quality_summary"]


def test_build_confidence_metrics_widens_margin_when_sources_fallback_and_fields_estimated():
    result = build_confidence_metrics(
        confidence=0.58,
        nearby_incident_count=1,
        estimated_fields=["humidity_percent", "wind_speed", "visibility", "surface_temperature"],
        historical_source="estimated",
        realtime_source="fallback",
    )

    assert result["confidence_margin"] == pytest.approx(0.17)
    assert result["confidence_lower_bound"] == pytest.approx(0.41)
    assert result["confidence_upper_bound"] == pytest.approx(0.75)
    assert result["source_quality_score"] == pytest.approx(0.37)
    assert "추정" in result["source_quality_summary"] or "보강" in result["source_quality_summary"]
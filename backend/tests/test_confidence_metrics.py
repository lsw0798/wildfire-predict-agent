import pytest

from app.services.confidence_metrics import build_confidence_metrics, diagnose_confidence_path


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


def test_diagnose_confidence_path_returns_stable_when_sources_are_live_and_complete():
    result = diagnose_confidence_path(
        estimated_fields=[],
        historical_source="live",
        realtime_source="live",
        nearby_incident_count=6,
    )

    assert result["route"] == "stable"
    assert result["severity"] == "low"
    assert "유지" in str(result["summary"])


def test_diagnose_confidence_path_requests_realtime_augmentation_when_realtime_was_skipped():
    result = diagnose_confidence_path(
        estimated_fields=["humidity_percent", "wind_speed", "visibility"],
        historical_source="estimated",
        realtime_source="skipped",
        nearby_incident_count=1,
    )

    assert result["route"] in {"augment_realtime", "augment_both"}
    assert "realtime_source_skipped" in result["reasons"]
    assert result["severity"] in {"medium", "high"}


def test_diagnose_confidence_path_requests_historical_augmentation_when_historical_was_skipped():
    result = diagnose_confidence_path(
        estimated_fields=["surface_temperature", "fire_intensity"],
        historical_source="skipped",
        realtime_source="fallback",
        nearby_incident_count=0,
    )

    assert result["route"] in {"augment_historical", "augment_both"}
    assert "historical_source_skipped" in result["reasons"]


def test_diagnose_confidence_path_requests_conservative_route_when_model_and_rule_disagree():
    result = diagnose_confidence_path(
        estimated_fields=[],
        historical_source="live",
        realtime_source="live",
        nearby_incident_count=6,
        model_feature_coverage=1.0,
        model_decision_mode="ml_model",
        model_score=0.82,
        rule_score=0.34,
        model_confidence=0.88,
    )

    assert result["route"] == "augment_both"
    assert result["severity"] == "high"
    assert "model_rule_disagreement" in result["reasons"]
    assert "모델" in str(result["summary"])


def test_diagnose_confidence_path_requests_conservative_route_when_model_coverage_is_low():
    result = diagnose_confidence_path(
        estimated_fields=["humidity_percent"],
        historical_source="live",
        realtime_source="live",
        nearby_incident_count=4,
        model_feature_coverage=0.33,
        model_decision_mode="ml_model",
        model_score=0.61,
        rule_score=0.58,
        model_confidence=0.52,
    )

    assert result["route"] == "augment_both"
    assert result["severity"] == "high"
    assert "model_feature_coverage_low" in result["reasons"]
    assert "coverage" in str(result["summary"]).lower() or "모델" in str(result["summary"])

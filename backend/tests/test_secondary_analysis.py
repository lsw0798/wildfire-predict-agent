import pytest

from app.services.secondary_analysis import run_secondary_analysis


def test_run_secondary_analysis_boosts_risk_for_augment_realtime_with_strong_live_signals():
    result = run_secondary_analysis(
        route="augment_realtime",
        initial_risk={"risk_level": "medium", "risk_score": 0.35, "key_factors": ["낮은 습도"]},
        initial_false_positive={"false_positive_risk": "medium", "uncertainty_notes": ["기존 노트"]},
        historical_context={"incident_count": 0, "source": "skipped"},
        realtime_context={
            "source": "live",
            "status": {
                "humidity_percent": 22.0,
                "wind_speed": 6.4,
                "fire_intensity": "높음",
            },
        },
        derived_features={"estimated_fields": ["humidity_percent"]},
    )

    assert result["analysis_mode"] == "realtime-heavy"
    assert result["final_risk"]["risk_score"] == pytest.approx(0.43)
    assert result["final_risk"]["risk_level"] == "medium"
    assert "실시간 관측 재평가" in result["final_risk"]["key_factors"]
    assert result["final_false_positive"]["false_positive_risk"] == "low"
    assert any("realtime" in note for note in result["adjustments"])


def test_run_secondary_analysis_applies_conservative_penalty_for_augment_both_with_many_estimates():
    result = run_secondary_analysis(
        route="augment_both",
        initial_risk={"risk_level": "high", "risk_score": 0.55, "key_factors": ["강한 풍속"]},
        initial_false_positive={"false_positive_risk": "low", "uncertainty_notes": ["기존 노트"]},
        historical_context={"incident_count": 0, "source": "fallback"},
        realtime_context={"source": "fallback", "status": {}},
        derived_features={
            "estimated_fields": [
                "humidity_percent",
                "wind_speed",
                "surface_temperature",
                "fire_intensity",
            ]
        },
    )

    assert result["analysis_mode"] == "conservative"
    assert result["final_risk"]["risk_score"] == pytest.approx(0.48)
    assert result["final_risk"]["risk_level"] == "medium"
    assert result["final_false_positive"]["false_positive_risk"] == "medium"
    assert any("conservative" in note for note in result["adjustments"])


def test_run_secondary_analysis_applies_conservative_penalty_for_model_disagreement():
    result = run_secondary_analysis(
        route="augment_both",
        initial_risk={"risk_level": "high", "risk_score": 0.62, "key_factors": ["강한 풍속"]},
        initial_false_positive={"false_positive_risk": "low", "uncertainty_notes": ["기존 노트"]},
        historical_context={"incident_count": 4, "source": "live"},
        realtime_context={"source": "live", "status": {}},
        derived_features={"estimated_fields": []},
        model_scoring={
            "decision_mode": "ml_model",
            "ml_score": 0.21,
            "ml_confidence": 0.89,
            "feature_coverage": 1.0,
        },
    )

    assert result["analysis_mode"] == "conservative"
    assert result["final_risk"]["risk_score"] == pytest.approx(0.55)
    assert result["final_false_positive"]["false_positive_risk"] == "medium"
    assert any("model disagreement" in note for note in result["adjustments"])


def test_run_secondary_analysis_applies_conservative_penalty_for_low_model_coverage():
    result = run_secondary_analysis(
        route="augment_both",
        initial_risk={"risk_level": "medium", "risk_score": 0.42, "key_factors": ["낮은 습도"]},
        initial_false_positive={"false_positive_risk": "medium", "uncertainty_notes": ["기존 노트"]},
        historical_context={"incident_count": 3, "source": "live"},
        realtime_context={"source": "live", "status": {}},
        derived_features={"estimated_fields": []},
        model_scoring={
            "decision_mode": "ml_model",
            "ml_score": 0.44,
            "ml_confidence": 0.51,
            "feature_coverage": 0.33,
        },
    )

    assert result["analysis_mode"] == "conservative"
    assert result["final_risk"]["risk_score"] == pytest.approx(0.35)
    assert result["final_false_positive"]["false_positive_risk"] == "high"
    assert any("low model coverage" in note for note in result["adjustments"])

import pytest

from app.agents import wildfire_graph
from app.services.model_scoring import build_model_scoring, get_model_scorer


REQUIRED_MODEL_FEATURES = {
    "humidity_percent",
    "wind_speed",
    "drought_duration_days",
    "slope",
    "fuel_moisture",
    "vulnerable",
}


def test_build_model_scoring_returns_rule_only_fallback_when_no_model_scorer():
    features = {
        "humidity_percent": 24.0,
        "wind_speed": 6.2,
        "drought_duration_days": 180,
    }

    result = build_model_scoring(features=features)

    assert result["ml_score"] is None
    assert result["ml_confidence"] == 0.0
    assert result["model_version"] == "unavailable"
    assert result["decision_mode"] == "rule_only_fallback"
    assert result["reason"] == "no_model_scorer_configured"
    assert result["required_features"] == sorted(REQUIRED_MODEL_FEATURES)
    assert result["available_features"] == [
        "drought_duration_days",
        "humidity_percent",
        "wind_speed",
    ]
    assert result["feature_coverage"] == pytest.approx(0.5)


def test_build_model_scoring_uses_injected_model_scorer_when_available():
    features = {
        "humidity_percent": 24.0,
        "wind_speed": 6.2,
        "drought_duration_days": 180,
        "slope": 16.0,
        "fuel_moisture": 10.0,
        "vulnerable": 1200.0,
    }

    def stub_model_scorer(*, features: dict):
        assert features["humidity_percent"] == 24.0
        return {
            "ml_score": "0.67",
            "ml_confidence": "0.84",
            "model_version": "baseline-v1",
            "reason": "stub_model_loaded",
        }

    result = build_model_scoring(features=features, model_scorer=stub_model_scorer)

    assert result["ml_score"] == pytest.approx(0.67)
    assert result["ml_confidence"] == pytest.approx(0.84)
    assert result["model_version"] == "baseline-v1"
    assert result["decision_mode"] == "ml_model"
    assert result["reason"] == "stub_model_loaded"
    assert result["feature_coverage"] == pytest.approx(1.0)


def test_get_model_scorer_returns_none_without_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WILDFIRE_BASELINE_MODEL_MODE", raising=False)
    monkeypatch.delenv("WILDFIRE_BASELINE_MODEL_VERSION", raising=False)

    scorer = get_model_scorer()

    assert scorer is None


def test_get_model_scorer_returns_stub_callable_when_env_requests_stub(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WILDFIRE_BASELINE_MODEL_MODE", "stub")
    monkeypatch.setenv("WILDFIRE_BASELINE_MODEL_VERSION", "baseline-env-v1")

    scorer = get_model_scorer()

    assert callable(scorer)
    result = scorer(
        features={
            "humidity_percent": 22.0,
            "wind_speed": 6.4,
            "drought_duration_days": 180,
            "vulnerable": 1300.0,
        }
    )
    assert result["model_version"] == "baseline-env-v1"
    assert result["reason"] == "env_stub_model"
    assert result["ml_score"] == pytest.approx(0.72)
    assert result["ml_confidence"] == pytest.approx(0.76)


def test_generate_report_exposes_model_adapter_fields_even_without_real_model():
    report = wildfire_graph.generate_report(
        lat=37.5665,
        lon=126.9780,
        user_type="시민",
        historical_context={
            "source": "live",
            "incident_count": 2,
            "latest_year": 2024,
            "top_causes": [{"cause": "입산자실화", "count": 1}],
        },
        realtime_context={
            "source": "live",
            "status": {
                "humidity_percent": 24.0,
                "wind_speed": 6.2,
                "visibility": 1800.0,
                "surface_temperature": 30.0,
                "fire_intensity": "높음",
            },
        },
        derived_features={
            "lat": 37.5665,
            "lon": 126.9780,
            "drought_duration_days": 180,
            "vulnerable": 1200.0,
            "humidity_percent": 24.0,
            "wind_speed": 6.2,
            "visibility": 1800.0,
            "surface_temperature": 30.0,
            "fire_intensity": "높음",
        },
    )

    assert report["model_score"] is None
    assert report["model_confidence"] == 0.0
    assert report["model_version"] == "unavailable"
    assert report["model_feature_coverage"] == pytest.approx(0.67)
    assert report["model_decision_mode"] == "rule_only_fallback"
    assert report["model_reason"] == "no_model_scorer_configured"
    assert any("model_scoring decision_mode=rule_only_fallback" in note for note in report["uncertainty_notes"])


def test_run_analysis_graph_uses_injected_model_scorer_when_available():
    class StubHistoricalService:
        def load_processed_summary_preview(self):
            return {
                "row_count": 3857,
                "trend_preview_path": "/tmp/wildfire.csv",
                "preview_rows": [{"OCCRR_YR": 2024}],
            }

        def load_trend_records(self, path=None):
            assert path in {"/tmp/wildfire.csv", "/private/tmp/wildfire.csv"}
            return [
                {
                    "OCCRR_YR": 2024,
                    "FRFR_OCCRR_CAUS_NM": "입산자실화",
                    "FRFR_OCCRR_LCTN_YCRD": 37.5666,
                    "FRFR_OCCRR_LCTN_XCRD": 126.9781,
                    "HMDT": 29.0,
                    "WDSP": 6.2,
                    "TPRT": 31.5,
                    "FRFR_DMG_AREA": 0.8,
                    "FRFR_POTFR_TM": "2:30",
                    "HASLV": 1800,
                }
            ]

        def find_nearby_incidents(self, records, *, latitude, longitude, radius_km=50.0, limit=None):
            assert latitude == pytest.approx(37.5665)
            assert longitude == pytest.approx(126.978)
            return records

        def summarize_historical_context(self, records, *, top_n=3):
            return {
                "incident_count": len(records),
                "latest_year": 2024,
                "top_causes": [{"cause": "입산자실화", "count": 1}],
            }

    def stub_realtime_provider(*, latitude: float, longitude: float):
        assert latitude == pytest.approx(37.5665)
        assert longitude == pytest.approx(126.978)
        return {
            "available": True,
            "source": "live",
            "items": [
                {
                    "humidity_percent": 24,
                    "wind_speed": 6.5,
                    "visibility": 620,
                    "surface_temperature": 33.4,
                    "fire_intensity": "높음",
                }
            ],
        }

    def selection_decider(*, lat: float, lon: float, user_type: str):
        return {
            "use_historical": True,
            "use_realtime": True,
            "selected_tools": ["historical", "realtime"],
            "reason": "baseline scoring test",
            "mode": "llm",
        }

    def stub_model_scorer(*, features: dict):
        assert features["humidity_percent"] == pytest.approx(24.0)
        assert features["wind_speed"] == pytest.approx(6.5)
        return {
            "ml_score": 0.73,
            "ml_confidence": 0.88,
            "model_version": "baseline-v1",
            "reason": "stubbed_model_prediction",
        }

    from app.schemas.report import AnalyzeRequest

    response = wildfire_graph.run_analysis_graph(
        payload=AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="시민"),
        historical_service=StubHistoricalService(),
        realtime_status_provider=stub_realtime_provider,
        selection_decider=selection_decider,
        model_scorer=stub_model_scorer,
    )

    assert response["model_score"] == pytest.approx(0.73)
    assert response["model_confidence"] == pytest.approx(0.88)
    assert response["model_version"] == "baseline-v1"
    assert response["model_feature_coverage"] == pytest.approx(0.67)
    assert response["model_decision_mode"] == "ml_model"
    assert response["model_reason"] == "stubbed_model_prediction"
    assert any("model-scoring mode=ml_model" in note for note in response["uncertainty_notes"])

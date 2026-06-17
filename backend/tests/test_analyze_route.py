import pytest
from pydantic import ValidationError

from app.api.routes import analyze as analyze_route
from app.agents import wildfire_graph
from app.schemas.group_e import ToolSelectionDecision
from app.schemas.report import AnalyzeRequest, AnalyzeResponse
from app.services.spatial_radius import DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM


def test_analyze_route_delegates_to_injected_orchestrator():
    captured = {}

    def stub_orchestrator(*, payload, historical_service, realtime_status_provider, selection_decider) -> dict:
        captured["payload"] = payload
        captured["historical_service"] = historical_service
        captured["realtime_status_provider"] = realtime_status_provider
        captured["selection_decider"] = selection_decider
        return {
            "risk_level": "medium",
            "risk_score": 0.52,
            "false_positive_risk": "low",
            "confidence": 0.81,
            "confidence_margin": 0.08,
            "analysis_radius_km": DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM,
            "radius_points": {
                "north": {"lat": 38.0162, "lon": 126.9780},
                "south": {"lat": 37.1168, "lon": 126.9780},
                "east": {"lat": 37.5665, "lon": 127.5460},
                "west": {"lat": 37.5665, "lon": 126.4100},
            },
            "key_factors": ["건조 주의"],
            "recommended_actions": ["공식 안내 확인"],
            "risk_summary_text": "현재 위치는 중간 수준의 산불 위험으로 평가됩니다.",
            "false_positive_summary_text": "오탐 가능성은 낮지만 단일 신호만으로 확정하지 않습니다.",
            "xai_reasons": ["건조 신호가 일부 확인되었습니다."],
            "reviewed_signals": ["인접 산불 이력 3건", "실시간 습도 관측값"],
            "data_quality_summary": "실시간과 과거 데이터를 함께 참고해 신뢰도를 계산했습니다.",
            "uncertainty_notes": ["graph completed"],
            "selected_tools": ["historical", "realtime"],
            "selection_reason": "기본 검증을 위해 두 소스를 모두 조회합니다.",
            "selection_mode": "llm",
        }

    response = analyze_route.analyze(
        AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="시민"),
        orchestrator=stub_orchestrator,
    )

    assert isinstance(response, AnalyzeResponse)
    assert response.uncertainty_notes == ["graph completed"]
    assert response.confidence_margin == 0.08
    assert response.analysis_radius_km == DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
    assert response.radius_points["north"]["lat"] == pytest.approx(38.0162)
    assert response.risk_summary_text.startswith("현재 위치는")
    assert response.false_positive_summary_text.startswith("오탐 가능성은")
    assert response.reviewed_signals == ["인접 산불 이력 3건", "실시간 습도 관측값"]
    assert captured["payload"].lat == 37.5665
    assert captured["payload"].lon == 126.978
    assert captured["payload"].user_type == "시민"
    assert hasattr(captured["historical_service"], "load_processed_summary_preview")
    assert callable(captured["realtime_status_provider"])
    assert callable(captured["selection_decider"])


def test_analyze_request_accepts_optional_radius_km_and_preserves_backward_compatibility():
    without_radius = AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="시민")
    with_radius = AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="시민", radius_km=18.0)

    assert without_radius.radius_km is None
    assert with_radius.radius_km == 18.0


@pytest.mark.parametrize("invalid_radius", [0, -1, -5.2])
def test_analyze_request_rejects_non_positive_radius_km(invalid_radius: float):
    with pytest.raises(ValidationError):
        AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="시민", radius_km=invalid_radius)


def test_generate_report_uses_provided_contexts_and_features():
    report = wildfire_graph.generate_report(
        lat=35.1796,
        lon=129.0756,
        user_type="공무원",
        historical_context={"drought_duration_days": 21, "vulnerable": 1400},
        realtime_context={
            "humidity_percent": 32,
            "wind_speed": 4.1,
            "visibility": 800,
            "surface_temperature": 24,
            "fire_intensity": "약함",
        },
        derived_features={"slope": 14, "fuel_moisture": 11},
    )

    assert report["risk_level"] in {"medium", "high", "critical"}
    assert report["recommended_actions"][0] == "취약계층 우선 대피 동선 점검"
    assert any("historical_context" in note for note in report["uncertainty_notes"])
    assert any("realtime_context" in note for note in report["uncertainty_notes"])
    assert any("derived_features" in note for note in report["uncertainty_notes"])


def test_route_dependency_provider_exposes_langgraph_orchestrator_callable():
    orchestrator = analyze_route.get_report_orchestrator()

    assert orchestrator is wildfire_graph.run_analysis_graph
    assert callable(orchestrator)


def test_analyze_route_resolves_default_orchestrator_for_direct_function_calls():
    class StubHistoricalService:
        def load_processed_summary_preview(self):
            return {
                "row_count": 1,
                "preview_rows": [{"OCCRR_YR": 2024, "FRFR_OCCRR_CAUS_NM": "입산자실화"}],
            }

        def summarize_historical_context(self, records, *, top_n=3):
            return {
                "incident_count": len(records),
                "latest_year": 2024,
                "top_causes": [{"cause": "입산자실화", "count": 1}],
            }

    def stub_realtime_provider(*, latitude: float, longitude: float):
        return {
            "available": False,
            "source": "fallback",
            "reason": "missing_api_key",
            "items": [],
        }

    response = analyze_route.analyze(
        AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="시민"),
        historical_service=StubHistoricalService(),
        realtime_status_provider=stub_realtime_provider,
    )

    assert isinstance(response, AnalyzeResponse)
    assert response.risk_level in {"low", "medium", "high", "critical"}
    assert any("historical source=" in note for note in response.uncertainty_notes)
    assert any("langgraph node=select_sources" in note for note in response.uncertainty_notes)


def test_run_analysis_graph_builds_non_empty_group_b_contexts_via_injected_services():
    class StubHistoricalService:
        def load_processed_summary_preview(self):
            return {
                "row_count": 3857,
                "trend_preview_path": "/tmp/wildfire.csv",
                "preview_rows": [{"OCCRR_YR": 2024}],
            }

        def load_trend_records(self, path=None):
            assert path == "/tmp/wildfire.csv"
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
                },
                {
                    "OCCRR_YR": 2023,
                    "FRFR_OCCRR_CAUS_NM": "담뱃불실화",
                    "FRFR_OCCRR_LCTN_YCRD": 37.5670,
                    "FRFR_OCCRR_LCTN_XCRD": 126.9775,
                    "HMDT": 35.0,
                    "WDSP": 4.8,
                    "TPRT": 28.0,
                    "FRFR_DMG_AREA": 0.2,
                    "FRFR_POTFR_TM": "1:10",
                    "HASLV": 1200,
                },
            ]

        def find_nearby_incidents(self, records, *, latitude, longitude, radius_km=50.0, limit=None):
            assert latitude == pytest.approx(37.5665)
            assert longitude == pytest.approx(126.978)
            assert radius_km == DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
            return records

        def summarize_historical_context(self, records, *, top_n=3):
            assert len(records) == 2
            return {
                "incident_count": 2,
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
                    "humidity_percent": 27,
                    "wind_speed": 7.1,
                    "visibility": 620,
                    "surface_temperature": 33.4,
                    "fire_intensity": "높음",
                }
            ],
        }

    def selection_decider(*, lat: float, lon: float, user_type: str) -> ToolSelectionDecision:
        assert lat == pytest.approx(37.5665)
        assert lon == pytest.approx(126.978)
        assert user_type == "시민"
        return ToolSelectionDecision(
            use_historical=True,
            use_realtime=True,
            selected_tools=["historical", "realtime"],
            reason="초기 판단에는 과거와 실시간이 모두 필요합니다.",
            mode="llm",
        )

    response = wildfire_graph.run_analysis_graph(
        payload=AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="시민"),
        historical_service=StubHistoricalService(),
        realtime_status_provider=stub_realtime_provider,
        selection_decider=selection_decider,
    )

    assert response["selected_tools"] == ["historical", "realtime"]
    assert response["selection_mode"] == "llm"
    assert response["analysis_radius_km"] == DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
    assert set(response["radius_points"].keys()) == {"north", "south", "east", "west"}
    assert response["risk_summary_text"].startswith("현재 위치는")
    assert response["false_positive_summary_text"].startswith("오탐")
    assert isinstance(response["xai_reasons"], list) and response["xai_reasons"]
    assert isinstance(response["reviewed_signals"], list) and response["reviewed_signals"]
    assert "신뢰도" in response["data_quality_summary"] or "데이터" in response["data_quality_summary"]
    assert response["risk_level"] in {"low", "medium", "high", "critical"}
    assert any("historical source=live" in note for note in response["uncertainty_notes"])
    assert any("realtime source=live" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=fetch_historical source=live" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=fetch_realtime source=live" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=primary_assessment" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=verification_gate" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=compose_report" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=build_response" in note for note in response["uncertainty_notes"])


def test_run_analysis_graph_skips_unselected_realtime_lookup_and_returns_selection_metadata():
    class StubHistoricalService:
        def load_processed_summary_preview(self):
            return {
                "row_count": 1,
                "trend_preview_path": "/tmp/wildfire.csv",
                "preview_rows": [
                    {
                        "OCCRR_YR": 2024,
                        "FRFR_OCCRR_CAUS_NM": "쓰레기소각",
                    }
                ],
            }

        def load_trend_records(self, path=None):
            return [
                {
                    "OCCRR_YR": 2024,
                    "FRFR_OCCRR_CAUS_NM": "쓰레기소각",
                    "FRFR_OCCRR_LCTN_YCRD": 37.54022,
                    "FRFR_OCCRR_LCTN_XCRD": 127.42677,
                    "HMDT": 31.0,
                    "WDSP": 3.4,
                    "TPRT": 25.0,
                    "HASLV": 140.0,
                }
            ]

        def find_nearby_incidents(self, records, *, latitude, longitude, radius_km=50.0, limit=None):
            assert radius_km == DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
            return records

        def summarize_historical_context(self, records, *, top_n=3):
            return {
                "incident_count": len(records),
                "latest_year": 2024,
                "top_causes": [{"cause": "쓰레기소각", "count": 1}],
            }

    def failing_realtime_provider(*, latitude: float, longitude: float):
        raise AssertionError("realtime provider should not be called when Group E deselects realtime")

    def selection_decider(*, lat: float, lon: float, user_type: str) -> ToolSelectionDecision:
        assert lat == pytest.approx(37.5402197416608)
        assert lon == pytest.approx(127.426770370139)
        assert user_type == "공무원"
        return ToolSelectionDecision(
            use_historical=True,
            use_realtime=False,
            selected_tools=["historical"],
            reason="과거 인접 산불 이력만으로 1차 판단이 가능해 실시간 조회를 생략합니다.",
            mode="rule_fallback",
        )

    response = wildfire_graph.run_analysis_graph(
        payload=AnalyzeRequest(lat=37.5402197416608, lon=127.426770370139, user_type="공무원"),
        historical_service=StubHistoricalService(),
        realtime_status_provider=failing_realtime_provider,
        selection_decider=selection_decider,
    )

    assert response["selected_tools"] == ["historical"]
    assert response["selection_reason"] == "과거 인접 산불 이력만으로 1차 판단이 가능해 실시간 조회를 생략합니다."
    assert response["selection_mode"] == "rule_fallback"
    assert response["analysis_radius_km"] == DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
    assert response["reviewed_signals"]
    assert response["false_positive_summary_text"]
    assert any("realtime source=skipped" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=fetch_realtime source=skipped" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=compose_report" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=build_response" in note for note in response["uncertainty_notes"])


def test_run_analysis_graph_records_review_nodes_when_verification_is_triggered():
    class StubHistoricalService:
        def load_processed_summary_preview(self):
            return {
                "row_count": 1,
                "trend_preview_path": "/tmp/wildfire.csv",
                "preview_rows": [{"OCCRR_YR": 2024}],
            }

        def load_trend_records(self, path=None):
            return [
                {
                    "OCCRR_YR": 2024,
                    "FRFR_OCCRR_CAUS_NM": "입산자실화",
                    "FRFR_OCCRR_LCTN_YCRD": 37.5665,
                    "FRFR_OCCRR_LCTN_XCRD": 126.9780,
                    "HMDT": 91.0,
                    "WDSP": 0.3,
                    "TPRT": 6.0,
                    "HASLV": 1800.0,
                }
            ]

        def find_nearby_incidents(self, records, *, latitude, longitude, radius_km=50.0, limit=None):
            assert radius_km == DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
            return records

        def summarize_historical_context(self, records, *, top_n=3):
            return {
                "incident_count": len(records),
                "latest_year": 2024,
                "top_causes": [{"cause": "입산자실화", "count": 1}],
            }

    def fallback_realtime_provider(*, latitude: float, longitude: float):
        return {
            "available": False,
            "source": "fallback",
            "reason": "missing_api_key",
            "items": [],
        }

    def selection_decider(*, lat: float, lon: float, user_type: str) -> ToolSelectionDecision:
        return ToolSelectionDecision(
            use_historical=True,
            use_realtime=True,
            selected_tools=["historical", "realtime"],
            reason="오탐 보정을 위해 과거와 실시간 소스를 모두 확인합니다.",
            mode="llm",
        )

    response = wildfire_graph.run_analysis_graph(
        payload=AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="공무원"),
        historical_service=StubHistoricalService(),
        realtime_status_provider=fallback_realtime_provider,
        selection_decider=selection_decider,
    )

    assert any("langgraph node=false_positive_review" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=data_quality_review" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=source_review" in note for note in response["uncertainty_notes"])
    assert any("langgraph node=decision_adjustment" in note for note in response["uncertainty_notes"])
    assert any("agent loop step=verification triggered=" in note for note in response["uncertainty_notes"])


def test_generate_report_mentions_live_fallback_and_estimated_uncertainty_sources():
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
            "source": "fallback",
            "reason": "missing_api_key",
            "status": {},
        },
        derived_features={
            "lat": 37.5665,
            "lon": 126.978,
            "drought_duration_days": 731,
            "vulnerable": 1800.0,
            "humidity_percent": 45.0,
            "wind_speed": 1.0,
            "visibility": 5000.0,
            "surface_temperature": 24.0,
            "fire_intensity": "추정",
            "estimated_fields": [
                "humidity_percent",
                "wind_speed",
                "visibility",
                "surface_temperature",
                "fire_intensity",
            ],
        },
    )

    assert any("historical source=live" in note for note in report["uncertainty_notes"])
    assert any("realtime source=fallback" in note for note in report["uncertainty_notes"])
    assert any("estimated_fields" in note for note in report["uncertainty_notes"])
    assert any("agent loop step=verification" in note for note in report["uncertainty_notes"])


def test_generate_report_agent_loop_downgrades_risk_when_false_positive_and_estimates_stack_up():
    report = wildfire_graph.generate_report(
        lat=37.5665,
        lon=126.9780,
        user_type="공무원",
        historical_context={
            "source": "estimated",
            "incident_count": 1,
            "latest_year": 2024,
            "top_causes": [{"cause": "입산자실화", "count": 1}],
        },
        realtime_context={
            "source": "fallback",
            "reason": "missing_api_key",
            "status": {},
        },
        derived_features={
            "lat": 37.5665,
            "lon": 126.978,
            "drought_duration_days": 730,
            "vulnerable": 1800.0,
            "humidity_percent": 91.0,
            "wind_speed": 0.3,
            "visibility": 280.0,
            "surface_temperature": 6.0,
            "fire_intensity": "약함",
            "slope": 17.0,
            "fuel_moisture": 9.0,
            "estimated_fields": [
                "humidity_percent",
                "wind_speed",
                "visibility",
                "surface_temperature",
                "fire_intensity",
            ],
        },
    )

    assert report["false_positive_risk"] == "high"
    assert report["risk_level"] == "medium"
    assert report["risk_score"] == 0.29
    assert report["confidence"] < 0.62
    assert "오탐 교정 루프 반영" in report["key_factors"]
    assert any("교차 검증" in action for action in report["recommended_actions"])
    assert any("agent loop step=decision-adjustment" in note for note in report["uncertainty_notes"])


def test_run_analysis_graph_passes_radius_override_to_historical_context_builder():
    class StubHistoricalService:
        def load_processed_summary_preview(self):
            return {
                "row_count": 1,
                "trend_preview_path": "/tmp/wildfire.csv",
                "preview_rows": [{"OCCRR_YR": 2024}],
            }

        def load_trend_records(self, path=None):
            return [
                {
                    "OCCRR_YR": 2024,
                    "FRFR_OCCRR_CAUS_NM": "입산자실화",
                    "FRFR_OCCRR_LCTN_YCRD": 37.5665,
                    "FRFR_OCCRR_LCTN_XCRD": 126.9780,
                    "HMDT": 29.0,
                    "WDSP": 6.2,
                    "TPRT": 31.5,
                    "HASLV": 1800,
                }
            ]

        def find_nearby_incidents(self, records, *, latitude, longitude, radius_km=50.0, limit=None):
            assert radius_km == 12.5
            return records

        def summarize_historical_context(self, records, *, top_n=3):
            return {
                "incident_count": len(records),
                "latest_year": 2024,
                "top_causes": [{"cause": "입산자실화", "count": 1}],
            }

    def stub_realtime_provider(*, latitude: float, longitude: float):
        return {
            "available": False,
            "source": "fallback",
            "reason": "missing_api_key",
            "items": [],
        }

    def selection_decider(*, lat: float, lon: float, user_type: str) -> ToolSelectionDecision:
        return ToolSelectionDecision(
            use_historical=True,
            use_realtime=True,
            selected_tools=["historical", "realtime"],
            reason="반경 사용자 설정을 반영합니다.",
            mode="llm",
        )

    response = wildfire_graph.run_analysis_graph(
        payload=AnalyzeRequest(lat=37.5665, lon=126.9780, user_type="시민", radius_km=12.5),
        historical_service=StubHistoricalService(),
        realtime_status_provider=stub_realtime_provider,
        selection_decider=selection_decider,
    )

    assert response["risk_level"] in {"low", "medium", "high", "critical"}
    assert response["analysis_radius_km"] == 12.5
    assert response["radius_points"]["north"]["lat"] > 37.5665

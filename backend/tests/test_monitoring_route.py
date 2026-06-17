from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.monitoring import MonitoringSummaryResponse
from app.api.routes import monitoring as monitoring_route


class StubMonitoringSummaryService:
    def build_summary(self, *, limit: int = 30) -> dict:
        assert limit == 30
        return {
            "generated_at": "2026-06-15T00:00:00Z",
            "total_records": 2,
            "watchpoints": [
                {
                    "id": "강원특별자치도|원주시",
                    "province": "강원특별자치도",
                    "city": "원주시",
                    "lat": 37.3,
                    "lon": 127.9,
                    "incident_count": 2,
                    "latest_year": 2024,
                    "top_cause": "입산자실화",
                    "priority_score": 28,
                    "priority_label": "medium",
                }
            ],
        }


def test_monitoring_summary_route_delegates_to_service():
    response = monitoring_route.get_monitoring_summary(service=StubMonitoringSummaryService())

    assert isinstance(response, MonitoringSummaryResponse)
    assert response.total_records == 2
    assert response.watchpoints[0].id == "강원특별자치도|원주시"
    assert response.watchpoints[0].priority_label == "medium"


def test_monitoring_summary_endpoint_is_available_under_api():
    app = create_app()
    app.dependency_overrides[monitoring_route.get_monitoring_summary_service] = lambda: StubMonitoringSummaryService()
    client = TestClient(app)

    payload = client.get("/api/monitoring/summary")

    assert payload.status_code == 200
    assert payload.json() == {
        "generated_at": "2026-06-15T00:00:00Z",
        "total_records": 2,
        "watchpoints": [
            {
                "id": "강원특별자치도|원주시",
                "province": "강원특별자치도",
                "city": "원주시",
                "lat": 37.3,
                "lon": 127.9,
                "incident_count": 2,
                "latest_year": 2024,
                "top_cause": "입산자실화",
                "priority_score": 28,
                "priority_label": "medium",
            }
        ],
    }

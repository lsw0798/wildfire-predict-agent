from fastapi.testclient import TestClient

from app.main import create_app
from app.api.routes import monitoring as monitoring_route
from app.schemas.monitoring import ForestHeatmapResponse
from app.services.forest_heatmap import ForestHeatmapService


class StubHistoricalService:
    def __init__(self, records):
        self.records = records
        self.trend_csv_path = "/tmp/trend.csv"
        self.requested_paths = []

    def load_trend_records(self, path=None):
        self.requested_paths.append(path)
        return list(self.records)


RECORDS = [
    {
        "FRFR_OCCRR_CTPRV_NM": "강원특별자치도",
        "FRFR_OCCRR_SGNG_NM": "홍천군",
        "FRFR_OCCRR_LCTN_YCRD": 37.6972,
        "FRFR_OCCRR_LCTN_XCRD": 127.8889,
        "OCCRR_YR": 2024,
        "FRFR_OCCRR_CAUS_NM": "입산자실화",
        "FRFR_DMG_AREA": 1.2,
        "TPRT": 31.0,
        "HMDT": 24.0,
        "WDSP": 5.6,
        "PRCPT_QNTT": 0.0,
        "STORUNST_CD": 1,
        "FRTP_CD": 1,
        "DNST_CD": "C",
        "FRTP_TRE_HGHT": 18,
        "HASLV": 820,
        "FRSTTN_DSTNC": 12.5,
        "PTMNT_DSTNC": 300,
    },
    {
        "FRFR_OCCRR_CTPRV_NM": "강원특별자치도",
        "FRFR_OCCRR_SGNG_NM": "홍천군",
        "FRFR_OCCRR_LCTN_YCRD": 37.6992,
        "FRFR_OCCRR_LCTN_XCRD": 127.8899,
        "OCCRR_YR": 2023,
        "FRFR_OCCRR_CAUS_NM": "입산자실화",
        "FRFR_DMG_AREA": 0.4,
        "TPRT": 29.0,
        "HMDT": 28.0,
        "WDSP": 4.8,
        "PRCPT_QNTT": 0.0,
        "STORUNST_CD": 1,
        "FRTP_CD": 1,
        "DNST_CD": "B",
        "FRTP_TRE_HGHT": 16,
        "HASLV": 760,
        "FRSTTN_DSTNC": 11.2,
        "PTMNT_DSTNC": 500,
    },
    {
        "FRFR_OCCRR_CTPRV_NM": "서울특별시",
        "FRFR_OCCRR_SGNG_NM": "중구",
        "FRFR_OCCRR_LCTN_YCRD": 37.56,
        "FRFR_OCCRR_LCTN_XCRD": 126.98,
        "OCCRR_YR": 2024,
        "FRFR_OCCRR_CAUS_NM": "기타",
        "STORUNST_CD": 0,
        "FRTP_CD": 0,
    },
]


def test_forest_heatmap_service_filters_non_forest_records_and_scores_cells():
    service = ForestHeatmapService(historical_service=StubHistoricalService(RECORDS))

    heatmap = service.build_heatmap(limit=20, resolution=0.1)

    assert heatmap["total_records"] == 3
    assert heatmap["forest_records"] == 2
    assert heatmap["filtered_records"] == 1
    assert len(heatmap["points"]) == 1

    point = heatmap["points"][0]
    assert point["province"] == "강원특별자치도"
    assert point["city"] == "홍천군"
    assert point["incident_count"] == 2
    assert point["latest_year"] == 2024
    assert point["top_cause"] == "입산자실화"
    assert 0.0 <= point["risk_score"] <= 1.0
    assert point["risk_level"] in {"low", "medium", "high", "critical"}
    assert 0.0 <= point["confidence"] <= 1.0
    assert point["review_required"] is False
    assert point["circle_radius_m"] >= 3500


def test_forest_heatmap_route_wraps_service_output_in_response_model():
    class StubForestHeatmapService:
        def build_heatmap(self, *, limit=250, resolution=0.1):
            assert limit == 250
            assert resolution == 0.1
            return {
                "generated_at": "2026-06-19T00:00:00Z",
                "metric": "risk",
                "resolution": 0.1,
                "total_records": 3,
                "forest_records": 2,
                "filtered_records": 1,
                "points": [
                    {
                        "id": "37.7|127.9",
                        "province": "강원특별자치도",
                        "city": "홍천군",
                        "lat": 37.7,
                        "lon": 127.9,
                        "risk_score": 0.72,
                        "risk_level": "high",
                        "confidence": 0.78,
                        "confidence_margin": 0.22,
                        "review_required": False,
                        "incident_count": 2,
                        "latest_year": 2024,
                        "top_cause": "입산자실화",
                        "circle_radius_m": 5200,
                        "key_factors": ["산림 지점 과거 발생 이력", "낮은 습도"],
                    }
                ],
            }

    response = monitoring_route.get_forest_heatmap(service=StubForestHeatmapService())

    assert isinstance(response, ForestHeatmapResponse)
    assert response.forest_records == 2
    assert response.points[0].city == "홍천군"


def test_forest_heatmap_endpoint_is_available_under_api():
    class StubForestHeatmapService:
        def build_heatmap(self, *, limit=250, resolution=0.1):
            return {
                "generated_at": "2026-06-19T00:00:00Z",
                "metric": "risk",
                "resolution": resolution,
                "total_records": 1,
                "forest_records": 1,
                "filtered_records": 0,
                "points": [],
            }

    app = create_app()
    app.dependency_overrides[monitoring_route.get_forest_heatmap_service] = lambda: StubForestHeatmapService()
    client = TestClient(app)

    response = client.get("/api/monitoring/forest-heatmap")

    assert response.status_code == 200
    assert response.json()["forest_records"] == 1
    assert response.json()["points"] == []

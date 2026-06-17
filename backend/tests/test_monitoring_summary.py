from app.api.routes import monitoring as monitoring_route
from app.schemas.monitoring import MonitoringSummaryResponse
from app.services.historical_wildfire import HistoricalWildfireService
from app.services.monitoring_summary import MonitoringSummaryService


class StubHistoricalService:
    def __init__(self, records, *, trend_csv_path=None, preview_bundle=None):
        self.records = records
        self.trend_csv_path = trend_csv_path
        self._preview_bundle = preview_bundle or {}
        self.requested_paths = []

    def load_trend_records(self, path=None):
        self.requested_paths.append(path)
        return list(self.records)

    def load_processed_preview_bundle(self):
        return self._preview_bundle


RECORDS = [
    {
        "FRFR_OCCRR_CTPRV_NM": "강원특별자치도",
        "FRFR_OCCRR_SGNG_NM": "홍천군",
        "FRFR_OCCRR_LCTN_YCRD": 37.6972,
        "FRFR_OCCRR_LCTN_XCRD": 127.8889,
        "OCCRR_YR": 2024,
        "FRFR_OCCRR_CAUS_NM": "입산자실화",
    },
    {
        "FRFR_OCCRR_CTPRV_NM": "강원특별자치도",
        "FRFR_OCCRR_SGNG_NM": "홍천군",
        "FRFR_OCCRR_LCTN_YCRD": 37.6992,
        "FRFR_OCCRR_LCTN_XCRD": 127.8899,
        "OCCRR_YR": 2023,
        "FRFR_OCCRR_CAUS_NM": "입산자실화",
    },
    {
        "FRFR_OCCRR_CTPRV_NM": "경기도",
        "FRFR_OCCRR_SGNG_NM": "양평군",
        "FRFR_OCCRR_LCTN_YCRD": 37.4915,
        "FRFR_OCCRR_LCTN_XCRD": 127.4876,
        "OCCRR_YR": 2024,
        "FRFR_OCCRR_CAUS_NM": "논·밭두렁소각",
    },
]


def test_monitoring_summary_service_groups_watchpoints_and_sorts_by_priority_score():
    historical_service = StubHistoricalService(RECORDS, trend_csv_path="/tmp/trend.csv")
    service = MonitoringSummaryService(historical_service=historical_service)

    summary = service.build_summary(limit=10)

    assert summary["total_records"] == 3
    assert len(summary["watchpoints"]) == 2
    assert historical_service.requested_paths == ["/tmp/trend.csv"]

    top_watchpoint = summary["watchpoints"][0]
    assert top_watchpoint["id"] == "강원특별자치도|홍천군"
    assert top_watchpoint["incident_count"] == 2
    assert top_watchpoint["latest_year"] == 2024
    assert top_watchpoint["top_cause"] == "입산자실화"
    assert top_watchpoint["priority_score"] > summary["watchpoints"][1]["priority_score"]
    assert top_watchpoint["priority_label"] == "medium"
    assert top_watchpoint["lat"] == 37.6982
    assert top_watchpoint["lon"] == 127.8894


def test_monitoring_summary_service_resolves_trend_path_from_preview_bundle_when_missing_on_service():
    historical_service = StubHistoricalService(
        RECORDS,
        preview_bundle={
            "trend_preview": {"path": "/tmp/preview-trend.csv"},
            "processed_summary": {"trend_preview_path": "/tmp/ignored.csv"},
        },
    )
    service = MonitoringSummaryService(historical_service=historical_service)

    service.build_summary(limit=5)

    assert historical_service.requested_paths == ["/tmp/preview-trend.csv"]


def test_monitoring_route_wraps_service_output_in_response_model():
    class StubMonitoringSummaryService:
        def build_summary(self, *, limit=30):
            assert limit == 30
            return {
                "generated_at": "2026-06-15T00:00:00Z",
                "total_records": 3,
                "watchpoints": [
                    {
                        "id": "강원특별자치도|홍천군",
                        "province": "강원특별자치도",
                        "city": "홍천군",
                        "lat": 37.6982,
                        "lon": 127.8894,
                        "incident_count": 2,
                        "latest_year": 2024,
                        "top_cause": "입산자실화",
                        "priority_score": 28,
                        "priority_label": "medium",
                    }
                ],
            }

    response = monitoring_route.get_monitoring_summary(service=StubMonitoringSummaryService())

    assert isinstance(response, MonitoringSummaryResponse)
    assert response.total_records == 3
    assert response.watchpoints[0].city == "홍천군"
    assert response.watchpoints[0].priority_label == "medium"


def test_historical_wildfire_service_load_trend_records_normalizes_csv_rows(tmp_path):
    csv_path = tmp_path / "trend.csv"
    csv_path.write_text(
        "FRFR_OCCRR_CTPRV_NM,FRFR_OCCRR_SGNG_NM,FRFR_OCCRR_LCTN_YCRD,FRFR_OCCRR_LCTN_XCRD,OCCRR_YR\n"
        "강원특별자치도,홍천군,37.6972,127.8889,2024\n",
        encoding="utf-8",
    )

    service = HistoricalWildfireService(trend_csv_path=csv_path)
    records = service.load_trend_records()

    assert records == [
        {
            "FRFR_OCCRR_CTPRV_NM": "강원특별자치도",
            "FRFR_OCCRR_SGNG_NM": "홍천군",
            "FRFR_OCCRR_LCTN_YCRD": 37.6972,
            "FRFR_OCCRR_LCTN_XCRD": 127.8889,
            "OCCRR_YR": 2024,
        }
    ]

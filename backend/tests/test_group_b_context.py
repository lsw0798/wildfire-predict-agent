from pathlib import Path

from app.services.group_b_context import build_historical_context, get_historical_wildfire_service
from app.services.spatial_radius import DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM


def test_get_historical_wildfire_service_uses_backend_processed_preview_path():
    service = get_historical_wildfire_service()

    assert str(service.summary_preview_path).endswith('/project/backend/data/processed/wildfire_public_data_preview.json')


def test_build_historical_context_uses_shared_default_radius_when_not_overridden():
    class StubHistoricalService:
        def load_processed_preview_bundle(self):
            return {
                "processed_summary": {
                    "row_count": 2,
                    "trend_preview_path": "/tmp/trend.csv",
                    "preview_rows": [],
                }
            }

        def load_trend_records(self, path=None):
            assert path in {"/tmp/trend.csv", "/private/tmp/trend.csv"}
            return [{"OCCRR_YR": 2024}]

        def find_nearby_incidents(self, records, *, latitude, longitude, radius_km=50.0, limit=None):
            assert latitude == 37.5
            assert longitude == 127.0
            assert radius_km == DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
            assert limit == 20
            return records

        def summarize_historical_context(self, records, *, top_n=3):
            return {"incident_count": len(records), "latest_year": 2024, "top_causes": []}

    context = build_historical_context(
        StubHistoricalService(),
        latitude=37.5,
        longitude=127.0,
    )

    assert context["radius_km"] == DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM


def test_build_historical_context_allows_radius_override():
    class StubHistoricalService:
        def load_processed_preview_bundle(self):
            return {
                "processed_summary": {
                    "row_count": 1,
                    "trend_preview_path": "/tmp/trend.csv",
                    "preview_rows": [],
                }
            }

        def load_trend_records(self, path=None):
            return [{"OCCRR_YR": 2023}]

        def find_nearby_incidents(self, records, *, latitude, longitude, radius_km=50.0, limit=None):
            assert radius_km == 12.5
            return records

        def summarize_historical_context(self, records, *, top_n=3):
            return {"incident_count": len(records), "latest_year": 2023, "top_causes": []}

    context = build_historical_context(
        StubHistoricalService(),
        latitude=37.5,
        longitude=127.0,
        radius_km=12.5,
    )

    assert context["radius_km"] == 12.5

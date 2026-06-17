from __future__ import annotations

import json
from pathlib import Path

from app.services.historical_wildfire import HistoricalWildfireService


def test_load_processed_summary_preview_reads_nested_preview_payload(tmp_path: Path):
    preview_path = tmp_path / "wildfire_public_data_preview.json"
    preview_path.write_text(
        json.dumps(
            {
                "trend_preview": {"row_count": 2},
                "processed_summary": {
                    "row_count": 12,
                    "columns": ["OCCRR_YR", "FRFR_OCCRR_CAUS_NM"],
                    "numeric_columns": ["OCCRR_YR"],
                    "preview_rows": [{"OCCRR_YR": 2024, "FRFR_OCCRR_CAUS_NM": "입산자실화"}],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = HistoricalWildfireService(summary_preview_path=preview_path)

    assert service.load_processed_summary_preview()["row_count"] == 12
    assert service.load_processed_summary_preview()["preview_rows"][0]["FRFR_OCCRR_CAUS_NM"] == "입산자실화"


def test_load_trend_records_parses_csv_rows_and_normalizes_numbers(tmp_path: Path):
    csv_path = tmp_path / "trend.csv"
    csv_path.write_text(
        "OCCRR_YR,FRFR_OCCRR_CAUS_NM,FRFR_OCCRR_LCTN_YCRD,FRFR_OCCRR_LCTN_XCRD,FRFR_DMG_AREA\n"
        "2024,입산자실화,37.5,127.0,0.15\n"
        "2023,담뱃불실화,37.6,127.1,\n",
        encoding="utf-8",
    )

    service = HistoricalWildfireService(trend_csv_path=csv_path)
    records = service.load_trend_records()

    assert records == [
        {
            "OCCRR_YR": 2024,
            "FRFR_OCCRR_CAUS_NM": "입산자실화",
            "FRFR_OCCRR_LCTN_YCRD": 37.5,
            "FRFR_OCCRR_LCTN_XCRD": 127.0,
            "FRFR_DMG_AREA": 0.15,
        },
        {
            "OCCRR_YR": 2023,
            "FRFR_OCCRR_CAUS_NM": "담뱃불실화",
            "FRFR_OCCRR_LCTN_YCRD": 37.6,
            "FRFR_OCCRR_LCTN_XCRD": 127.1,
            "FRFR_DMG_AREA": None,
        },
    ]


def test_find_nearby_incidents_filters_by_radius_and_sorts_by_distance():
    service = HistoricalWildfireService()
    records = [
        {
            "incident_id": "near-1",
            "OCCRR_YR": 2024,
            "FRFR_OCCRR_LCTN_YCRD": 37.5005,
            "FRFR_OCCRR_LCTN_XCRD": 127.0005,
        },
        {
            "incident_id": "near-2",
            "OCCRR_YR": 2023,
            "FRFR_OCCRR_LCTN_YCRD": 37.51,
            "FRFR_OCCRR_LCTN_XCRD": 127.01,
        },
        {
            "incident_id": "far",
            "OCCRR_YR": 2022,
            "FRFR_OCCRR_LCTN_YCRD": 35.0,
            "FRFR_OCCRR_LCTN_XCRD": 129.0,
        },
    ]

    nearby = service.find_nearby_incidents(records, latitude=37.5, longitude=127.0, radius_km=2.0)

    assert [item["incident_id"] for item in nearby] == ["near-1", "near-2"]
    assert nearby[0]["distance_km"] < nearby[1]["distance_km"]
    assert all(item["distance_km"] <= 2.0 for item in nearby)


def test_summarize_historical_context_counts_causes_and_latest_year():
    service = HistoricalWildfireService()
    records = [
        {"OCCRR_YR": 2022, "FRFR_OCCRR_CAUS_NM": "입산자실화"},
        {"OCCRR_YR": "2024", "FRFR_OCCRR_CAUS_NM": "입산자실화"},
        {"OCCRR_YR": 2023, "FRFR_OCCRR_CAUS_NM": "담뱃불실화"},
        {"OCCRR_YR": None, "FRFR_OCCRR_CAUS_NM": ""},
    ]

    summary = service.summarize_historical_context(records, top_n=2)

    assert summary == {
        "incident_count": 4,
        "latest_year": 2024,
        "top_causes": [
            {"cause": "입산자실화", "count": 2},
            {"cause": "담뱃불실화", "count": 1},
        ],
    }

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from app.services.spatial_radius import DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM


class HistoricalWildfireService:
    def __init__(
        self,
        *,
        summary_preview_path: str | Path | None = None,
        trend_csv_path: str | Path | None = None,
    ) -> None:
        self.summary_preview_path = Path(summary_preview_path) if summary_preview_path else None
        self.trend_csv_path = Path(trend_csv_path) if trend_csv_path else None

    def load_processed_preview_bundle(self, path: str | Path | None = None) -> dict[str, Any]:
        target_path = Path(path) if path else self.summary_preview_path
        if target_path is None:
            raise ValueError("summary preview path is required")

        payload = json.loads(target_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
        raise ValueError("summary preview payload must be a JSON object")

    def load_processed_summary_preview(self, path: str | Path | None = None) -> dict[str, Any]:
        payload = self.load_processed_preview_bundle(path)
        if isinstance(payload, dict) and "processed_summary" in payload:
            summary = payload["processed_summary"]
            if isinstance(summary, dict):
                return summary
        if isinstance(payload, dict):
            return payload
        raise ValueError("summary preview payload must be a JSON object")

    def load_trend_records(self, path: str | Path | None = None) -> list[dict[str, Any]]:
        target_path = Path(path) if path else self.trend_csv_path
        if target_path is None:
            raise ValueError("trend csv path is required")

        with target_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            return [self._normalize_row(row) for row in reader]

    def find_nearby_incidents(
        self,
        records: list[dict[str, Any]],
        *,
        latitude: float,
        longitude: float,
        radius_km: float = DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        nearby: list[dict[str, Any]] = []
        for record in records:
            incident_lat = self._coerce_float(record.get("FRFR_OCCRR_LCTN_YCRD") or record.get("lat"))
            incident_lon = self._coerce_float(record.get("FRFR_OCCRR_LCTN_XCRD") or record.get("lon"))
            if incident_lat is None or incident_lon is None:
                continue

            distance_km = self._haversine_km(latitude, longitude, incident_lat, incident_lon)
            if distance_km <= radius_km:
                enriched = dict(record)
                enriched["distance_km"] = round(distance_km, 3)
                nearby.append(enriched)

        nearby.sort(key=lambda item: item["distance_km"])
        if limit is not None:
            return nearby[:limit]
        return nearby

    def summarize_historical_context(
        self,
        records: list[dict[str, Any]],
        *,
        top_n: int = 3,
    ) -> dict[str, Any]:
        causes = Counter()
        years: list[int] = []

        for record in records:
            cause = str(record.get("FRFR_OCCRR_CAUS_NM") or record.get("cause") or "").strip()
            if cause:
                causes[cause] += 1

            year = self._coerce_int(record.get("OCCRR_YR") or record.get("year"))
            if year is not None:
                years.append(year)

        return {
            "incident_count": len(records),
            "latest_year": max(years) if years else None,
            "top_causes": [
                {"cause": cause, "count": count}
                for cause, count in causes.most_common(top_n)
            ],
        }

    def _normalize_row(self, row: dict[str, str | None]) -> dict[str, Any]:
        return {key: self._normalize_value(value) for key, value in row.items()}

    @staticmethod
    def _normalize_value(value: str | None) -> Any:
        if value is None:
            return None

        text = value.strip()
        if text == "":
            return None

        int_value = HistoricalWildfireService._coerce_int(text)
        if int_value is not None and text == str(int_value):
            return int_value

        float_value = HistoricalWildfireService._coerce_float(text)
        if float_value is not None:
            return float_value

        return text

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        try:
            text = str(value).strip()
            if text == "":
                return None
            if "." in text:
                number = float(text)
                if number.is_integer():
                    return int(number)
                return None
            return int(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        try:
            text = str(value).strip()
            if text == "":
                return None
            return float(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius_km = 6371.0
        lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(
            math.radians,
            (lat1, lon1, lat2, lon2),
        )
        delta_lat = lat2_rad - lat1_rad
        delta_lon = lon2_rad - lon1_rad
        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return earth_radius_km * c

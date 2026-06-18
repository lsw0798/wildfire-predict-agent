from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import _resolve_project_path
from app.services.group_b_context import get_historical_wildfire_service
from app.services.historical_wildfire import HistoricalWildfireService


class MonitoringSummaryService:
    def __init__(self, *, historical_service: HistoricalWildfireService) -> None:
        self.historical_service = historical_service

    def build_summary(self, *, limit: int = 30) -> dict[str, Any]:
        records = self.historical_service.load_trend_records(path=self._resolve_trend_csv_path())
        max_year = max(
            (self._coerce_int(record.get("OCCRR_YR")) for record in records),
            default=None,
        )

        grouped: dict[str, dict[str, Any]] = {}
        for record in records:
            province = str(record.get("FRFR_OCCRR_CTPRV_NM") or "미상").strip() or "미상"
            city = str(record.get("FRFR_OCCRR_SGNG_NM") or "미상").strip() or "미상"
            watchpoint_id = f"{province}|{city}"
            latitude = self._coerce_float(record.get("FRFR_OCCRR_LCTN_YCRD"))
            longitude = self._coerce_float(record.get("FRFR_OCCRR_LCTN_XCRD"))
            year = self._coerce_int(record.get("OCCRR_YR"))
            cause = str(record.get("FRFR_OCCRR_CAUS_NM") or "미상").strip() or "미상"

            bucket = grouped.setdefault(
                watchpoint_id,
                {
                    "id": watchpoint_id,
                    "province": province,
                    "city": city,
                    "incident_count": 0,
                    "latest_year": None,
                    "cause_counter": Counter(),
                    "lat_sum": 0.0,
                    "lon_sum": 0.0,
                    "coordinate_count": 0,
                },
            )
            bucket["incident_count"] += 1
            bucket["cause_counter"][cause] += 1
            if year is not None and (bucket["latest_year"] is None or year > bucket["latest_year"]):
                bucket["latest_year"] = year
            if latitude is not None and longitude is not None:
                bucket["lat_sum"] += latitude
                bucket["lon_sum"] += longitude
                bucket["coordinate_count"] += 1

        watchpoints = [
            self._build_watchpoint(bucket=bucket, max_year=max_year)
            for bucket in grouped.values()
        ]
        watchpoints.sort(
            key=lambda item: (
                -item["priority_score"],
                -item["incident_count"],
                -(item["latest_year"] or 0),
                item["id"],
            )
        )

        return {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "total_records": len(records),
            "watchpoints": watchpoints[:limit],
        }

    def _resolve_trend_csv_path(self) -> str | Path | None:
        if self.historical_service.trend_csv_path is not None:
            return self.historical_service.trend_csv_path

        preview_bundle = self.historical_service.load_processed_preview_bundle()
        trend_preview = preview_bundle.get("trend_preview") if isinstance(preview_bundle, dict) else None
        if isinstance(trend_preview, dict) and trend_preview.get("path"):
            return str(_resolve_project_path(trend_preview["path"]))

        summary = preview_bundle.get("processed_summary") if isinstance(preview_bundle, dict) else None
        if isinstance(summary, dict) and summary.get("trend_preview_path"):
            return str(_resolve_project_path(summary["trend_preview_path"]))
        return None

    def _build_watchpoint(self, *, bucket: dict[str, Any], max_year: int | None) -> dict[str, Any]:
        coordinate_count = bucket["coordinate_count"]
        lat = round(bucket["lat_sum"] / coordinate_count, 4) if coordinate_count else 0.0
        lon = round(bucket["lon_sum"] / coordinate_count, 4) if coordinate_count else 0.0
        top_cause = self._select_top_cause(bucket["cause_counter"])
        priority_score = self._priority_score(
            incident_count=bucket["incident_count"],
            latest_year=bucket["latest_year"],
            max_year=max_year,
            top_cause=top_cause,
        )
        return {
            "id": bucket["id"],
            "province": bucket["province"],
            "city": bucket["city"],
            "lat": lat,
            "lon": lon,
            "incident_count": bucket["incident_count"],
            "latest_year": bucket["latest_year"],
            "top_cause": top_cause,
            "priority_score": priority_score,
            "priority_label": self._priority_label(priority_score),
        }

    @staticmethod
    def _select_top_cause(cause_counter: Counter[str]) -> str | None:
        if not cause_counter:
            return None
        return sorted(cause_counter.items(), key=lambda item: (-item[1], item[0]))[0][0]

    @staticmethod
    def _priority_score(*, incident_count: int, latest_year: int | None, max_year: int | None, top_cause: str | None) -> int:
        score = incident_count * 10
        if latest_year is not None and max_year is not None:
            if latest_year >= max_year:
                score += 5
            elif latest_year >= max_year - 1:
                score += 3
            else:
                score += 1

        cause_text = top_cause or ""
        if "실화" in cause_text:
            score += 3
        elif "소각" in cause_text or "화재" in cause_text:
            score += 2
        elif cause_text:
            score += 1
        return score

    @staticmethod
    def _priority_label(priority_score: int) -> str:
        if priority_score >= 35:
            return "high"
        if priority_score >= 20:
            return "medium"
        return "low"

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        return HistoricalWildfireService._coerce_float(value)

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        return HistoricalWildfireService._coerce_int(value)


def get_monitoring_summary_service() -> MonitoringSummaryService:
    return MonitoringSummaryService(historical_service=get_historical_wildfire_service())

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import _resolve_project_path
from app.services.group_b_context import get_historical_wildfire_service
from app.services.historical_wildfire import HistoricalWildfireService

DEFAULT_HEATMAP_LIMIT = 250
DEFAULT_HEATMAP_RESOLUTION = 0.1


class ForestHeatmapService:
    def __init__(self, *, historical_service: HistoricalWildfireService) -> None:
        self.historical_service = historical_service

    def build_heatmap(
        self,
        *,
        limit: int = DEFAULT_HEATMAP_LIMIT,
        resolution: float = DEFAULT_HEATMAP_RESOLUTION,
    ) -> dict[str, Any]:
        safe_resolution = _safe_resolution(resolution)
        safe_limit = max(1, min(int(limit), 1000))
        records = self.historical_service.load_trend_records(path=self._resolve_trend_csv_path())
        max_year = max((_coerce_int(record.get("OCCRR_YR")) for record in records), default=None)

        grouped: dict[str, dict[str, Any]] = {}
        forest_records = 0
        filtered_records = 0

        for record in records:
            lat = _coerce_float(record.get("FRFR_OCCRR_LCTN_YCRD"))
            lon = _coerce_float(record.get("FRFR_OCCRR_LCTN_XCRD"))
            if lat is None or lon is None or not _looks_like_korea(lat, lon):
                filtered_records += 1
                continue
            if not _is_forest_record(record):
                filtered_records += 1
                continue

            forest_records += 1
            grid_lat = round(round(lat / safe_resolution) * safe_resolution, 4)
            grid_lon = round(round(lon / safe_resolution) * safe_resolution, 4)
            bucket_id = f"{grid_lat:.4f}|{grid_lon:.4f}"
            bucket = grouped.setdefault(
                bucket_id,
                {
                    "id": bucket_id,
                    "records": [],
                    "lat_sum": 0.0,
                    "lon_sum": 0.0,
                    "province_counter": Counter(),
                    "city_counter": Counter(),
                    "cause_counter": Counter(),
                    "years": [],
                },
            )
            bucket["records"].append(record)
            bucket["lat_sum"] += lat
            bucket["lon_sum"] += lon

            province = str(record.get("FRFR_OCCRR_CTPRV_NM") or "미상").strip() or "미상"
            city = str(record.get("FRFR_OCCRR_SGNG_NM") or "미상").strip() or "미상"
            cause = str(record.get("FRFR_OCCRR_CAUS_NM") or "미상").strip() or "미상"
            bucket["province_counter"][province] += 1
            bucket["city_counter"][city] += 1
            bucket["cause_counter"][cause] += 1
            year = _coerce_int(record.get("OCCRR_YR"))
            if year is not None:
                bucket["years"].append(year)

        points = [
            self._build_point(bucket=bucket, max_year=max_year)
            for bucket in grouped.values()
        ]
        points.sort(
            key=lambda point: (
                -point["risk_score"],
                -point["confidence"],
                -point["incident_count"],
                point["id"],
            )
        )

        return {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "metric": "risk",
            "resolution": safe_resolution,
            "total_records": len(records),
            "forest_records": forest_records,
            "filtered_records": filtered_records,
            "points": points[:safe_limit],
        }

    def _resolve_trend_csv_path(self) -> str | Path | None:
        if getattr(self.historical_service, "trend_csv_path", None) is not None:
            return self.historical_service.trend_csv_path

        preview_bundle = self.historical_service.load_processed_preview_bundle()
        trend_preview = preview_bundle.get("trend_preview") if isinstance(preview_bundle, dict) else None
        if isinstance(trend_preview, dict) and trend_preview.get("path"):
            return str(_resolve_project_path(trend_preview["path"]))

        summary = preview_bundle.get("processed_summary") if isinstance(preview_bundle, dict) else None
        if isinstance(summary, dict) and summary.get("trend_preview_path"):
            return str(_resolve_project_path(summary["trend_preview_path"]))
        return None

    def _build_point(self, *, bucket: dict[str, Any], max_year: int | None) -> dict[str, Any]:
        records: list[dict[str, Any]] = bucket["records"]
        incident_count = len(records)
        latest_year = max(bucket["years"], default=None)
        top_cause = _select_top(bucket["cause_counter"])
        province = _select_top(bucket["province_counter"]) or "미상"
        city = _select_top(bucket["city_counter"]) or "미상"
        risk_score, key_factors = _score_risk(records, incident_count, latest_year, max_year, top_cause)
        confidence = _score_confidence(records, incident_count, latest_year, max_year)
        confidence_margin = round(max(0.0, 1.0 - confidence), 2)
        review_required = (risk_score >= 0.65 and confidence < 0.55) or confidence_margin >= 0.5

        return {
            "id": bucket["id"],
            "province": province,
            "city": city,
            "lat": round(bucket["lat_sum"] / incident_count, 5),
            "lon": round(bucket["lon_sum"] / incident_count, 5),
            "risk_score": risk_score,
            "risk_level": _risk_level(risk_score),
            "confidence": confidence,
            "confidence_margin": confidence_margin,
            "review_required": review_required,
            "incident_count": incident_count,
            "latest_year": latest_year,
            "top_cause": top_cause,
            "circle_radius_m": _circle_radius_m(incident_count, risk_score),
            "key_factors": key_factors,
        }


def get_forest_heatmap_service() -> ForestHeatmapService:
    return ForestHeatmapService(historical_service=get_historical_wildfire_service())


def _score_risk(
    records: list[dict[str, Any]],
    incident_count: int,
    latest_year: int | None,
    max_year: int | None,
    top_cause: str | None,
) -> tuple[float, list[str]]:
    factors: list[str] = ["산림 지점 과거 발생 이력"]
    density_score = min(incident_count / 8.0, 1.0)

    recency_score = 0.2
    if latest_year is not None and max_year is not None:
        year_gap = max(max_year - latest_year, 0)
        recency_score = max(0.2, 1.0 - min(year_gap, 5) / 5.0)
        if year_gap <= 1:
            factors.append("최근 발생 이력")

    cause_text = top_cause or ""
    if "실화" in cause_text:
        cause_score = 0.9
        factors.append("실화 계열 대표 원인")
    elif "소각" in cause_text or "화재" in cause_text:
        cause_score = 0.7
        factors.append("소각/화재 계열 대표 원인")
    elif cause_text:
        cause_score = 0.4
    else:
        cause_score = 0.2

    avg_humidity = _average(records, "HMDT")
    avg_wind = _average(records, "WDSP")
    avg_temp = _average(records, "TPRT")
    avg_precip = _average(records, "PRCPT_QNTT")
    weather_score = 0.25
    if avg_humidity is not None and avg_humidity < 30:
        weather_score += 0.3
        factors.append("낮은 습도 이력")
    if avg_wind is not None and avg_wind >= 5:
        weather_score += 0.25
        factors.append("강한 풍속 이력")
    if avg_temp is not None and avg_temp >= 30:
        weather_score += 0.15
        factors.append("높은 기온 이력")
    if avg_precip is not None and avg_precip <= 0:
        weather_score += 0.1
        factors.append("무강수 이력")
    weather_score = min(weather_score, 1.0)

    fuel_score = _fuel_score(records)
    terrain_score = min((_max(records, "HASLV") or 0.0) / 1000.0, 1.0)
    damage_score = min((_max(records, "FRFR_DMG_AREA") or 0.0) / 1.0, 1.0)
    response_score = min((_average(records, "FRSTTN_DSTNC") or 0.0) / 20.0, 1.0)

    score = (
        density_score * 0.28
        + recency_score * 0.15
        + weather_score * 0.20
        + cause_score * 0.10
        + fuel_score * 0.10
        + terrain_score * 0.07
        + damage_score * 0.07
        + response_score * 0.03
    )
    return round(min(max(score, 0.0), 0.99), 2), factors[:5]


def _score_confidence(
    records: list[dict[str, Any]],
    incident_count: int,
    latest_year: int | None,
    max_year: int | None,
) -> float:
    volume_score = min(incident_count / 5.0, 1.0)
    recency_score = 0.3
    if latest_year is not None and max_year is not None:
        recency_score = max(0.3, 1.0 - min(max_year - latest_year, 5) / 5.0)
    completeness_keys = [
        "FRFR_OCCRR_LCTN_YCRD",
        "FRFR_OCCRR_LCTN_XCRD",
        "OCCRR_YR",
        "FRFR_OCCRR_CAUS_NM",
        "HMDT",
        "WDSP",
        "TPRT",
        "FRFR_DMG_AREA",
        "STORUNST_CD",
        "FRTP_CD",
        "HASLV",
    ]
    present = 0
    total = max(len(records) * len(completeness_keys), 1)
    for record in records:
        present += sum(1 for key in completeness_keys if record.get(key) not in (None, ""))
    completeness_score = present / total
    forest_quality = 1.0 if all(_is_forest_record(record) for record in records) else 0.5
    confidence = volume_score * 0.35 + recency_score * 0.20 + completeness_score * 0.35 + forest_quality * 0.10
    return round(min(max(confidence, 0.0), 0.99), 2)


def _is_forest_record(record: dict[str, Any]) -> bool:
    standing = _coerce_float(record.get("STORUNST_CD"))
    forest_type = _coerce_float(record.get("FRTP_CD"))
    if standing == 1:
        return True
    if forest_type is not None and forest_type > 0:
        return True
    return False


def _fuel_score(records: list[dict[str, Any]]) -> float:
    scores: list[float] = []
    for record in records:
        score = 0.35 if _is_forest_record(record) else 0.0
        density = str(record.get("DNST_CD") or "").strip().upper()
        if density == "C":
            score += 0.35
        elif density == "B":
            score += 0.2
        height = _coerce_float(record.get("FRTP_TRE_HGHT"))
        if height is not None:
            score += min(height / 30.0, 0.3)
        scores.append(min(score, 1.0))
    return round(sum(scores) / len(scores), 3) if scores else 0.0


def _circle_radius_m(incident_count: int, risk_score: float) -> int:
    return int(min(18000, max(3500, 3000 + incident_count * 850 + risk_score * 2500)))


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.55:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def _average(records: list[dict[str, Any]], key: str) -> float | None:
    values = [_coerce_float(record.get(key)) for record in records]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _max(records: list[dict[str, Any]], key: str) -> float | None:
    values = [_coerce_float(record.get(key)) for record in records]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return None
    return max(numeric_values)


def _select_top(counter: Counter[str]) -> str | None:
    if not counter:
        return None
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _safe_resolution(value: float) -> float:
    try:
        resolution = float(value)
    except (TypeError, ValueError):
        return DEFAULT_HEATMAP_RESOLUTION
    if resolution <= 0:
        return DEFAULT_HEATMAP_RESOLUTION
    return min(max(resolution, 0.02), 0.5)


def _looks_like_korea(lat: float, lon: float) -> bool:
    return 32.0 <= lat <= 39.5 and 124.0 <= lon <= 132.0


def _coerce_int(value: Any) -> int | None:
    return HistoricalWildfireService._coerce_int(value)


def _coerce_float(value: Any) -> float | None:
    return HistoricalWildfireService._coerce_float(value)

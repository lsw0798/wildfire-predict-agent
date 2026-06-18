from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable

from app.core.config import _resolve_project_path, get_settings
from app.services.historical_wildfire import HistoricalWildfireService
from app.services.realtime_wildfire import get_realtime_wildfire_status
from app.services.spatial_radius import DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM

DEFAULT_VISIBILITY = 5000.0
DEFAULT_SURFACE_TEMPERATURE = 24.0
DEFAULT_HUMIDITY_PERCENT = 45.0
DEFAULT_WIND_SPEED = 1.0
RealtimeStatusProvider = Callable[..., dict[str, Any]]


def get_historical_wildfire_service() -> HistoricalWildfireService:
    settings = get_settings()
    processed_dir = settings.wildfire_processed_data_path.parent
    preview_path = processed_dir / "wildfire_public_data_preview.json"
    return HistoricalWildfireService(summary_preview_path=preview_path)


def get_realtime_status_provider() -> RealtimeStatusProvider:
    def provider(*, latitude: float, longitude: float) -> dict[str, Any]:
        _ = (latitude, longitude)
        return get_realtime_wildfire_status()

    return provider


def build_historical_context(
    historical_service: HistoricalWildfireService,
    *,
    latitude: float,
    longitude: float,
    radius_km: float | None = None,
) -> dict[str, Any]:
    effective_radius_km = (
        float(radius_km)
        if radius_km is not None
        else DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
    )
    preview_bundle = _load_preview_bundle(historical_service)
    summary = preview_bundle.get("processed_summary", {}) if isinstance(preview_bundle, dict) else {}
    trend_csv_path = _resolve_trend_csv_path(historical_service, preview_bundle, summary)

    if trend_csv_path is not None:
        try:
            records = historical_service.load_trend_records(path=trend_csv_path)
            nearby = historical_service.find_nearby_incidents(
                records,
                latitude=latitude,
                longitude=longitude,
                radius_km=effective_radius_km,
                limit=20,
            )
            context = historical_service.summarize_historical_context(nearby)
            context.update(
                {
                    "source": "live",
                    "radius_km": effective_radius_km,
                    "row_count": summary.get("row_count"),
                    "trend_csv_path": str(trend_csv_path),
                    "nearby_incidents": nearby,
                }
            )
            return context
        except (FileNotFoundError, OSError, ValueError):
            pass

    preview_rows = summary.get("preview_rows") or []
    context = historical_service.summarize_historical_context(preview_rows)
    context.update(
        {
            "source": "estimated" if preview_rows else "fallback",
            "radius_km": effective_radius_km,
            "row_count": summary.get("row_count"),
            "trend_csv_path": None,
            "nearby_incidents": preview_rows,
        }
    )
    if not preview_rows:
        context["reason"] = "historical_data_unavailable"
    return context


def build_realtime_context(
    realtime_status_provider: RealtimeStatusProvider,
    *,
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    payload = realtime_status_provider(latitude=latitude, longitude=longitude) or {}
    item = _select_realtime_item(payload)
    status = {
        "humidity_percent": _coerce_float(item.get("humidity_percent") or item.get("HMDT")),
        "wind_speed": _coerce_float(item.get("wind_speed") or item.get("WDSP")),
        "visibility": _coerce_float(item.get("visibility")),
        "surface_temperature": _coerce_float(
            item.get("surface_temperature")
            or item.get("temperature")
            or item.get("TPRT")
        ),
        "fire_intensity": _coerce_text(item.get("fire_intensity") or item.get("status")),
    }
    return {
        "source": payload.get("source", "fallback"),
        "available": bool(payload.get("available")),
        "reason": payload.get("reason"),
        "status": status,
        "raw_items": payload.get("items", []),
    }


def derive_group_b_features(
    *,
    latitude: float,
    longitude: float,
    historical_context: dict[str, Any],
    realtime_context: dict[str, Any],
) -> dict[str, Any]:
    nearby_incidents = historical_context.get("nearby_incidents") or []
    realtime_status = realtime_context.get("status") or {}
    estimated_fields: list[str] = []

    drought_duration_days = _derive_drought_duration_days(historical_context)
    vulnerable = _derive_vulnerable(nearby_incidents)

    humidity_percent = _prefer_live_or_estimate(
        realtime_status.get("humidity_percent"),
        _average_numeric(nearby_incidents, "HMDT"),
        DEFAULT_HUMIDITY_PERCENT,
        "humidity_percent",
        estimated_fields,
    )
    wind_speed = _prefer_live_or_estimate(
        realtime_status.get("wind_speed"),
        _average_numeric(nearby_incidents, "WDSP"),
        DEFAULT_WIND_SPEED,
        "wind_speed",
        estimated_fields,
    )
    visibility = _prefer_live_or_estimate(
        realtime_status.get("visibility"),
        None,
        DEFAULT_VISIBILITY,
        "visibility",
        estimated_fields,
    )
    surface_temperature = _prefer_live_or_estimate(
        realtime_status.get("surface_temperature"),
        _average_numeric(nearby_incidents, "TPRT"),
        DEFAULT_SURFACE_TEMPERATURE,
        "surface_temperature",
        estimated_fields,
    )

    fire_intensity = realtime_status.get("fire_intensity")
    if not fire_intensity:
        fire_intensity = _estimate_fire_intensity(nearby_incidents, humidity_percent, wind_speed)
        estimated_fields.append("fire_intensity")

    features: dict[str, Any] = {
        "lat": latitude,
        "lon": longitude,
        "drought_duration_days": drought_duration_days,
        "vulnerable": vulnerable,
        "humidity_percent": humidity_percent,
        "wind_speed": wind_speed,
        "visibility": visibility,
        "surface_temperature": surface_temperature,
        "fire_intensity": fire_intensity,
    }
    if estimated_fields:
        features["estimated_fields"] = estimated_fields
    return features


def _load_preview_bundle(historical_service: HistoricalWildfireService) -> dict[str, Any]:
    if hasattr(historical_service, "load_processed_preview_bundle"):
        try:
            bundle = historical_service.load_processed_preview_bundle()
            if isinstance(bundle, dict):
                return bundle
        except (FileNotFoundError, OSError, ValueError):
            return {}

    try:
        summary = historical_service.load_processed_summary_preview()
    except (FileNotFoundError, OSError, ValueError):
        return {}

    if isinstance(summary, dict):
        return {"processed_summary": summary}
    return {}


def _resolve_trend_csv_path(
    historical_service: HistoricalWildfireService,
    preview_bundle: dict[str, Any],
    summary: dict[str, Any],
) -> Path | str | None:
    candidates = [
        ((preview_bundle.get("trend_preview") or {}).get("path") if isinstance(preview_bundle.get("trend_preview"), dict) else None),
        summary.get("trend_preview_path") if isinstance(summary, dict) else None,
        getattr(historical_service, "trend_csv_path", None),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        candidate_path = _resolve_project_path(candidate)
        return str(candidate_path)
    return None


def _select_realtime_item(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items") or []
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            return first
    return {}


def _derive_drought_duration_days(historical_context: dict[str, Any]) -> int:
    latest_year = historical_context.get("latest_year")
    try:
        latest_year_int = int(latest_year)
    except (TypeError, ValueError):
        return 0
    current_year_start = date(date.today().year, 1, 1)
    latest_year_start = date(latest_year_int, 1, 1)
    return max((current_year_start - latest_year_start).days, 0)


def _derive_vulnerable(nearby_incidents: list[dict[str, Any]]) -> float:
    values = [_coerce_float(item.get("HASLV")) for item in nearby_incidents]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return 0.0
    return float(max(numeric_values))


def _average_numeric(records: list[dict[str, Any]], key: str) -> float | None:
    values = [_coerce_float(record.get(key)) for record in records]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return None
    return round(sum(numeric_values) / len(numeric_values), 3)


def _prefer_live_or_estimate(
    preferred: float | None,
    estimated: float | None,
    default: float,
    field_name: str,
    estimated_fields: list[str],
) -> float:
    if preferred is not None:
        return float(preferred)
    if estimated is not None:
        estimated_fields.append(field_name)
        return float(estimated)
    estimated_fields.append(field_name)
    return float(default)


def _estimate_fire_intensity(
    nearby_incidents: list[dict[str, Any]],
    humidity_percent: float,
    wind_speed: float,
) -> str:
    max_damage = max((_coerce_float(item.get("FRFR_DMG_AREA")) or 0.0 for item in nearby_incidents), default=0.0)
    if max_damage >= 1.0 or humidity_percent < 30 or wind_speed >= 5:
        return "높음"
    if max_damage >= 0.3:
        return "보통"
    return "추정"


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


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

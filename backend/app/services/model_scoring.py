from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

ModelScorer = Callable[..., dict[str, Any] | None]

REQUIRED_MODEL_FEATURES = [
    "humidity_percent",
    "wind_speed",
    "drought_duration_days",
    "slope",
    "fuel_moisture",
    "vulnerable",
]


def get_model_scorer() -> ModelScorer | None:
    mode = os.getenv("WILDFIRE_BASELINE_MODEL_MODE", "").strip().lower()
    if mode != "stub":
        return None

    model_version = os.getenv("WILDFIRE_BASELINE_MODEL_VERSION", "baseline-env-stub")

    def stub_model_scorer(*, features: dict[str, Any]) -> dict[str, Any]:
        humidity = _coerce_optional_float(features.get("humidity_percent")) or 50.0
        wind_speed = _coerce_optional_float(features.get("wind_speed")) or 1.0
        drought_days = _coerce_optional_float(features.get("drought_duration_days")) or 0.0
        vulnerable = _coerce_optional_float(features.get("vulnerable")) or 0.0

        raw_score = 0.28
        raw_score += 0.18 if humidity < 30 else 0.0
        raw_score += 0.14 if wind_speed >= 5 else 0.0
        raw_score += 0.08 if drought_days >= 30 else 0.0
        raw_score += 0.04 if vulnerable >= 1000 else 0.0
        ml_score = round(min(raw_score, 0.99), 2)

        confidence = 0.62
        confidence += 0.06 if humidity < 30 else 0.0
        confidence += 0.04 if wind_speed >= 5 else 0.0
        confidence += 0.02 if drought_days >= 30 else 0.0
        confidence += 0.02 if vulnerable >= 1000 else 0.0
        ml_confidence = round(min(confidence, 0.95), 2)

        return {
            "ml_score": ml_score,
            "ml_confidence": ml_confidence,
            "model_version": model_version,
            "reason": "env_stub_model",
        }

    return stub_model_scorer


def build_model_scoring(
    *,
    features: dict[str, Any],
    model_scorer: ModelScorer | None = None,
) -> dict[str, Any]:
    available_features = sorted(
        feature_name
        for feature_name in REQUIRED_MODEL_FEATURES
        if _has_usable_value(features.get(feature_name))
    )
    feature_coverage = round(len(available_features) / len(REQUIRED_MODEL_FEATURES), 2)

    if model_scorer is None:
        return {
            "ml_score": None,
            "ml_confidence": 0.0,
            "model_version": "unavailable",
            "feature_coverage": feature_coverage,
            "decision_mode": "rule_only_fallback",
            "reason": "no_model_scorer_configured",
            "required_features": sorted(REQUIRED_MODEL_FEATURES),
            "available_features": available_features,
        }

    raw_result = model_scorer(features=features) or {}
    ml_score = _coerce_optional_float(raw_result.get("ml_score"))
    ml_confidence = _coerce_optional_float(raw_result.get("ml_confidence"))

    return {
        "ml_score": ml_score,
        "ml_confidence": round(ml_confidence if ml_confidence is not None else 0.0, 2),
        "model_version": str(raw_result.get("model_version") or "custom"),
        "feature_coverage": feature_coverage,
        "decision_mode": "ml_model" if ml_score is not None else "rule_only_fallback",
        "reason": str(raw_result.get("reason") or "model_scorer_returned_no_score"),
        "required_features": sorted(REQUIRED_MODEL_FEATURES),
        "available_features": available_features,
    }



def _has_usable_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True



def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return float(value)
    try:
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None

from __future__ import annotations

from typing import Any


RISK_LEVEL_ORDER = ["low", "medium", "high", "critical"]
FALSE_POSITIVE_LEVEL_ORDER = ["low", "medium", "high"]


def run_secondary_analysis(
    *,
    route: str,
    initial_risk: dict[str, Any],
    initial_false_positive: dict[str, Any],
    historical_context: dict[str, Any],
    realtime_context: dict[str, Any],
    derived_features: dict[str, Any],
    model_scoring: dict[str, Any] | None = None,
) -> dict[str, Any]:
    final_risk = dict(initial_risk)
    final_false_positive = dict(initial_false_positive)
    adjustments: list[str] = []
    analysis_mode = "stable"
    estimated_fields = list(derived_features.get("estimated_fields") or [])
    realtime_status = realtime_context.get("status") or {}

    if route == "augment_historical":
        analysis_mode = "historical-heavy"
        incident_count = int(historical_context.get("incident_count", 0) or 0)
        vulnerable = float(derived_features.get("vulnerable", 0) or 0)
        drought_days = float(derived_features.get("drought_duration_days", 0) or 0)
        if str(historical_context.get("source", "unknown")) == "live" and (
            incident_count >= 2 or vulnerable >= 1000 or drought_days >= 20
        ):
            final_risk = _adjust_risk(final_risk, delta=0.05, extra_factor="과거 산불 맥락 재평가")
            final_false_positive = _adjust_false_positive(final_false_positive, delta=-1)
            adjustments.append("secondary-analysis historical-heavy reranked using live historical context")

    elif route == "augment_realtime":
        analysis_mode = "realtime-heavy"
        humidity = float(realtime_status.get("humidity_percent") or derived_features.get("humidity_percent") or 50)
        wind_speed = float(realtime_status.get("wind_speed") or derived_features.get("wind_speed") or 1)
        fire_intensity = str(realtime_status.get("fire_intensity") or derived_features.get("fire_intensity") or "")
        strong_signals = 0
        strong_signals += int(humidity < 30)
        strong_signals += int(wind_speed >= 5)
        strong_signals += int(fire_intensity in {"높음", "강함"})
        if str(realtime_context.get("source", "unknown")) == "live" and strong_signals >= 2:
            final_risk = _adjust_risk(final_risk, delta=0.08, extra_factor="실시간 관측 재평가")
            final_false_positive = _adjust_false_positive(final_false_positive, delta=-1)
            adjustments.append("secondary-analysis realtime-heavy boosted by strong live signals")

    elif route == "augment_both":
        analysis_mode = "conservative"
        historical_source = str(historical_context.get("source", "unknown"))
        realtime_source = str(realtime_context.get("source", "unknown"))
        if len(estimated_fields) >= 3 or historical_source != "live" or realtime_source != "live":
            final_risk = _adjust_risk(final_risk, delta=-0.07, extra_factor="보수적 재평가")
            final_false_positive = _adjust_false_positive(final_false_positive, delta=1)
            adjustments.append("secondary-analysis conservative path applied for weak multi-source evidence")

        decision_mode = str((model_scoring or {}).get("decision_mode", ""))
        model_score = _coerce_float((model_scoring or {}).get("ml_score"))
        model_confidence = _coerce_float((model_scoring or {}).get("ml_confidence"))
        feature_coverage = _coerce_float((model_scoring or {}).get("feature_coverage"))
        rule_score = _coerce_float(initial_risk.get("risk_score")) or 0.0

        if decision_mode == "ml_model" and model_score is not None:
            if abs(model_score - rule_score) >= 0.25:
                final_risk = _adjust_risk(final_risk, delta=-0.07, extra_factor="모델 불일치 보수 재평가")
                final_false_positive = _adjust_false_positive(final_false_positive, delta=1)
                adjustments.append("secondary-analysis conservative path applied for model disagreement")
            if feature_coverage is not None and feature_coverage < 0.5:
                final_risk = _adjust_risk(final_risk, delta=-0.07, extra_factor="낮은 모델 coverage 보수 재평가")
                final_false_positive = _adjust_false_positive(final_false_positive, delta=1)
                adjustments.append("secondary-analysis conservative path applied for low model coverage")
            elif model_confidence is not None and model_confidence < 0.6:
                final_risk = _adjust_risk(final_risk, delta=-0.05, extra_factor="낮은 모델 신뢰도 보수 재평가")
                final_false_positive = _adjust_false_positive(final_false_positive, delta=1)
                adjustments.append("secondary-analysis conservative path applied for low model confidence")

    return {
        "analysis_mode": analysis_mode,
        "final_risk": final_risk,
        "final_false_positive": final_false_positive,
        "adjustments": adjustments,
    }


def _adjust_risk(risk: dict[str, Any], *, delta: float, extra_factor: str) -> dict[str, Any]:
    new_score = round(min(max(float(risk.get("risk_score", 0.0)) + delta, 0.0), 0.99), 2)
    key_factors = list(risk.get("key_factors") or [])
    if extra_factor not in key_factors:
        key_factors.append(extra_factor)
    return {
        **risk,
        "risk_score": new_score,
        "risk_level": _risk_level_from_score(new_score),
        "key_factors": key_factors,
    }


def _adjust_false_positive(result: dict[str, Any], *, delta: int) -> dict[str, Any]:
    current = str(result.get("false_positive_risk", "medium"))
    try:
        index = FALSE_POSITIVE_LEVEL_ORDER.index(current)
    except ValueError:
        index = 1
    next_index = min(max(index + delta, 0), len(FALSE_POSITIVE_LEVEL_ORDER) - 1)
    return {
        **result,
        "false_positive_risk": FALSE_POSITIVE_LEVEL_ORDER[next_index],
    }


def _coerce_float(value: Any) -> float | None:
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


def _risk_level_from_score(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.25:
        return "medium"
    return "low"

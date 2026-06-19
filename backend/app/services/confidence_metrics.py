from __future__ import annotations


def build_confidence_metrics(
    *,
    confidence: float,
    nearby_incident_count: int,
    estimated_fields: list[str],
    historical_source: str,
    realtime_source: str,
) -> dict[str, float | str]:
    margin = 0.11

    if historical_source == "live":
        margin -= 0.02
    elif historical_source == "estimated":
        margin += 0.02
    elif historical_source == "fallback":
        margin += 0.03

    if realtime_source == "live":
        margin -= 0.02
    elif realtime_source == "fallback":
        margin += 0.02
    elif realtime_source == "skipped":
        margin += 0.01

    if nearby_incident_count >= 8:
        margin -= 0.01
    elif nearby_incident_count <= 1:
        margin += 0.01

    if len(estimated_fields) >= 3:
        margin += 0.01

    margin = round(min(max(margin, 0.05), 0.2), 2)
    lower_bound = round(max(confidence - margin, 0.0), 2)
    upper_bound = round(min(confidence + margin, 0.99), 2)

    source_quality_score = 0.7
    source_quality_score += {
        "live": 0.15,
        "estimated": -0.12,
        "fallback": -0.18,
        "skipped": -0.1,
    }.get(historical_source, -0.08)
    source_quality_score += {
        "live": 0.1,
        "fallback": -0.15,
        "skipped": -0.08,
    }.get(realtime_source, -0.05)

    if nearby_incident_count >= 8:
        source_quality_score += 0.05
    elif nearby_incident_count <= 1:
        source_quality_score -= 0.03

    if len(estimated_fields) >= 4:
        source_quality_score -= 0.03
    elif estimated_fields:
        source_quality_score -= 0.01

    source_quality_score = round(min(max(source_quality_score, 0.2), 0.95), 2)

    if source_quality_score >= 0.8:
        source_quality_summary = "과거 이력과 실시간 출처가 비교적 안정적이라 신뢰 구간이 좁습니다."
    elif source_quality_score >= 0.55:
        source_quality_summary = "핵심 출처는 확보됐지만 일부 신호는 추가 확인이 필요합니다."
    else:
        source_quality_summary = "추정값 또는 대체 출처 비중이 커서 현장·공공 데이터 보강이 필요합니다."

    return {
        "confidence_margin": margin,
        "confidence_lower_bound": lower_bound,
        "confidence_upper_bound": upper_bound,
        "source_quality_score": source_quality_score,
        "source_quality_summary": source_quality_summary,
    }



def diagnose_confidence_path(
    *,
    estimated_fields: list[str],
    historical_source: str,
    realtime_source: str,
    nearby_incident_count: int,
    model_feature_coverage: float | None = None,
    model_decision_mode: str | None = None,
    model_score: float | None = None,
    rule_score: float | None = None,
    model_confidence: float | None = None,
) -> dict[str, str | list[str]]:
    reasons: list[str] = []
    need_historical = False
    need_realtime = False
    need_conservative = False

    if realtime_source == "skipped":
        reasons.append("realtime_source_skipped")
        if historical_source != "live" or len(estimated_fields) >= 2:
            need_realtime = True

    if historical_source == "skipped":
        reasons.append("historical_source_skipped")
        if realtime_source != "live" or len(estimated_fields) >= 2 or nearby_incident_count <= 1:
            need_historical = True

    if realtime_source == "fallback":
        reasons.append("realtime_source_not_live")
        if historical_source in {"skipped", "fallback", "estimated"}:
            need_historical = True

    if historical_source in {"estimated", "fallback"}:
        reasons.append("historical_source_not_live")
        if realtime_source in {"skipped", "fallback"}:
            need_realtime = True

    if len(estimated_fields) >= 3:
        reasons.append("estimated_fields_ge_3")
        if historical_source == "skipped":
            need_historical = True
        if realtime_source == "skipped":
            need_realtime = True

    if nearby_incident_count <= 1:
        reasons.append("limited_historical_evidence")

    if (model_decision_mode or "") == "ml_model":
        if model_feature_coverage is not None and model_feature_coverage < 0.5:
            reasons.append("model_feature_coverage_low")
            need_conservative = True
        if model_confidence is not None and model_confidence < 0.6:
            reasons.append("model_confidence_low")
            need_conservative = True
        if model_score is not None and rule_score is not None and abs(model_score - rule_score) >= 0.25:
            reasons.append("model_rule_disagreement")
            need_conservative = True

    route = "stable"
    if need_conservative:
        route = "augment_both"
    elif need_historical and need_realtime:
        route = "augment_both"
    elif need_historical:
        route = "augment_historical"
    elif need_realtime:
        route = "augment_realtime"

    if need_conservative or route == "augment_both" or len(estimated_fields) >= 4:
        severity = "high"
    elif route != "stable" or len(estimated_fields) >= 2:
        severity = "medium"
    else:
        severity = "low"

    if need_conservative:
        summary = "모델 신호와 규칙 기반 판단 또는 모델 coverage가 불안정해 보수적 재검토 경로를 적용합니다."
    elif route == "stable":
        summary = "현재 데이터 조합만으로 1차 분석을 유지합니다."
    elif route == "augment_historical":
        summary = "과거 맥락 근거가 약해 historical 소스를 보강 조회합니다."
    elif route == "augment_realtime":
        summary = "실시간 관측 근거가 약해 realtime 소스를 보강 조회합니다."
    else:
        summary = "핵심 출처가 함께 약해 historical·realtime 소스를 모두 재검토합니다."

    return {
        "route": route,
        "severity": severity,
        "reasons": reasons,
        "summary": summary,
    }

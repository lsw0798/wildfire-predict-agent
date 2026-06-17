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

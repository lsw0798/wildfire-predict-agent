from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.schemas.group_e import ToolSelectionDecision
from app.schemas.report import AnalyzeRequest
from app.services.confidence_metrics import build_confidence_metrics, diagnose_confidence_path
from app.services.false_positive_review import review_false_positive
from app.services.group_b_context import (
    RealtimeStatusProvider,
    build_historical_context,
    build_realtime_context,
    derive_group_b_features,
)
from app.services.group_e_selector import SelectionDecider
from app.services.historical_wildfire import HistoricalWildfireService
from app.services.model_scoring import ModelScorer, build_model_scoring
from app.services.risk_engine import score_risk
from app.services.secondary_analysis import run_secondary_analysis
from app.services.spatial_radius import DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM, cardinal_point

ReportOrchestrator = Callable[..., dict]


class AnalysisGraphState(TypedDict, total=False):
    payload: AnalyzeRequest
    historical_service: HistoricalWildfireService
    realtime_status_provider: RealtimeStatusProvider
    selection_decider: SelectionDecider
    model_scorer: ModelScorer | None
    selection: ToolSelectionDecision
    historical_context: dict[str, Any]
    realtime_context: dict[str, Any]
    derived_features: dict[str, Any]
    model_scoring: dict[str, Any]
    initial_risk: dict[str, Any]
    initial_false_positive: dict[str, Any]
    final_risk: dict[str, Any]
    final_false_positive: dict[str, Any]
    verification_reasons: list[str]
    score_penalty: float
    agent_trace: list[str]
    report: dict[str, Any]
    response: dict[str, Any]
    workflow_trace: list[str]
    confidence_diagnostics: dict[str, Any]
    route_decision: str
    secondary_fetch_applied: list[str]
    secondary_analysis_result: dict[str, Any]


BASE_ACTIONS = {
    "default": [
        "취약계층 우선 대피 동선 점검",
        "초기 진입로 및 소방 접근 경로 확인",
        "현장 영상 또는 센서 신호와 교차 검증",
    ],
    "시민": [
        "인근 통제 구역 접근 자제",
        "공식 재난 안내 확인",
        "연기 또는 화염 식별 시 즉시 신고",
    ],
}


@lru_cache
def _get_analysis_graph():
    graph = StateGraph(AnalysisGraphState)
    graph.add_node("select_sources", _select_sources_node)
    graph.add_node("fetch_historical", _fetch_historical_node)
    graph.add_node("fetch_realtime", _fetch_realtime_node)
    graph.add_node("derive_features", _derive_features_node)
    graph.add_node("diagnose_path", _diagnose_path_node)
    graph.add_node("augment_sources", _augment_sources_node)
    graph.add_node("primary_assessment", _primary_assessment_node)
    graph.add_node("secondary_analysis", _secondary_analysis_node)
    graph.add_node("verification_gate", _verification_gate_node)
    graph.add_node("false_positive_review", _false_positive_review_node)
    graph.add_node("data_quality_review", _data_quality_review_node)
    graph.add_node("source_review", _source_review_node)
    graph.add_node("decision_adjustment", _decision_adjustment_node)
    graph.add_node("compose_report", _compose_report_node)
    graph.add_node("build_response", _build_response_node)

    graph.add_edge(START, "select_sources")
    graph.add_edge("select_sources", "fetch_historical")
    graph.add_edge("fetch_historical", "fetch_realtime")
    graph.add_edge("fetch_realtime", "derive_features")
    graph.add_edge("derive_features", "primary_assessment")
    graph.add_edge("primary_assessment", "diagnose_path")
    graph.add_conditional_edges(
        "diagnose_path",
        _diagnose_route,
        {
            "augment_sources": "augment_sources",
            "secondary_analysis": "secondary_analysis",
        },
    )
    graph.add_edge("augment_sources", "primary_assessment")
    graph.add_edge("secondary_analysis", "verification_gate")
    graph.add_conditional_edges(
        "verification_gate",
        _verification_route,
        {
            "run_reviews": "false_positive_review",
            "compose_report": "compose_report",
        },
    )
    graph.add_edge("false_positive_review", "data_quality_review")
    graph.add_edge("data_quality_review", "source_review")
    graph.add_edge("source_review", "decision_adjustment")
    graph.add_edge("decision_adjustment", "compose_report")
    graph.add_edge("compose_report", "build_response")
    graph.add_edge("build_response", END)
    return graph.compile()



def get_report_orchestrator() -> ReportOrchestrator:
    return run_analysis_graph



def run_analysis_graph(
    *,
    payload: AnalyzeRequest,
    historical_service: HistoricalWildfireService,
    realtime_status_provider: RealtimeStatusProvider,
    selection_decider: SelectionDecider,
    model_scorer: ModelScorer | None = None,
) -> dict:
    final_state = _get_analysis_graph().invoke(
        {
            "payload": payload,
            "historical_service": historical_service,
            "realtime_status_provider": realtime_status_provider,
            "selection_decider": selection_decider,
            "model_scorer": model_scorer,
            "workflow_trace": [],
            "agent_trace": [],
            "score_penalty": 0.0,
        }
    )
    response = final_state.get("response")
    if not isinstance(response, dict):
        raise TypeError("analysis graph did not produce a response payload")
    return response



def generate_report(
    *,
    lat: float,
    lon: float,
    user_type: str,
    historical_context: dict | None = None,
    realtime_context: dict | None = None,
    derived_features: dict | None = None,
    model_scorer: ModelScorer | None = None,
) -> dict:
    historical_context = historical_context or {}
    realtime_context = realtime_context or {}
    derived_features = derived_features or {}

    features = {
        **historical_context,
        **realtime_context,
        **derived_features,
    }

    model_scoring = build_model_scoring(features=features, model_scorer=model_scorer)
    initial_risk = score_risk(features)
    initial_false_positive = review_false_positive(features)
    final_risk, final_false_positive, agent_trace = _run_agent_loop(
        initial_risk=initial_risk,
        initial_false_positive=initial_false_positive,
        historical_context=historical_context,
        realtime_context=realtime_context,
        derived_features=derived_features,
    )
    return _assemble_report(
        lat=lat,
        lon=lon,
        user_type=user_type,
        historical_context=historical_context,
        realtime_context=realtime_context,
        derived_features=derived_features,
        initial_risk=initial_risk,
        model_scoring=model_scoring,
        final_risk=final_risk,
        final_false_positive=final_false_positive,
        agent_trace=agent_trace,
    )



def _select_sources_node(state: AnalysisGraphState) -> AnalysisGraphState:
    payload = state["payload"]
    selection = _coerce_selection_decision(
        state["selection_decider"](
            lat=payload.lat,
            lon=payload.lon,
            user_type=payload.user_type,
        )
    )
    return {
        "selection": selection,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            f"langgraph node=select_sources selected={selection.selected_tools} mode={selection.mode}",
        ],
    }



def _fetch_historical_node(state: AnalysisGraphState) -> AnalysisGraphState:
    payload = state["payload"]
    selection = state["selection"]
    if selection.use_historical:
        historical_context = build_historical_context(
            state["historical_service"],
            latitude=payload.lat,
            longitude=payload.lon,
            radius_km=payload.radius_km,
        )
    else:
        historical_context = _build_skipped_context(tool_name="historical")
    return {
        "historical_context": historical_context,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            f"langgraph node=fetch_historical source={historical_context.get('source', 'unknown')}",
        ],
    }



def _fetch_realtime_node(state: AnalysisGraphState) -> AnalysisGraphState:
    payload = state["payload"]
    selection = state["selection"]
    if selection.use_realtime:
        realtime_context = build_realtime_context(
            state["realtime_status_provider"],
            latitude=payload.lat,
            longitude=payload.lon,
        )
    else:
        realtime_context = _build_skipped_context(tool_name="realtime")
    return {
        "realtime_context": realtime_context,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            f"langgraph node=fetch_realtime source={realtime_context.get('source', 'unknown')}",
        ],
    }



def _derive_features_node(state: AnalysisGraphState) -> AnalysisGraphState:
    payload = state["payload"]
    derived_features = derive_group_b_features(
        latitude=payload.lat,
        longitude=payload.lon,
        historical_context=state["historical_context"],
        realtime_context=state["realtime_context"],
    )
    return {
        "derived_features": derived_features,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            "langgraph node=derive_features",
        ],
    }



def _diagnose_path_node(state: AnalysisGraphState) -> AnalysisGraphState:
    historical_context = state.get("historical_context", {})
    realtime_context = state.get("realtime_context", {})
    derived_features = state.get("derived_features", {})
    model_scoring = state.get("model_scoring") or {}
    initial_risk = state.get("initial_risk") or {}
    diagnostics = diagnose_confidence_path(
        estimated_fields=derived_features.get("estimated_fields") or [],
        historical_source=str(historical_context.get("source", "unknown")),
        realtime_source=str(realtime_context.get("source", "unknown")),
        nearby_incident_count=int(historical_context.get("incident_count", 0) or 0),
        model_feature_coverage=float(model_scoring.get("feature_coverage") or 0.0),
        model_decision_mode=str(model_scoring.get("decision_mode", "rule_only_fallback")),
        model_score=(float(model_scoring["ml_score"]) if model_scoring.get("ml_score") is not None else None),
        rule_score=(float(initial_risk["risk_score"]) if initial_risk.get("risk_score") is not None else None),
        model_confidence=float(model_scoring.get("ml_confidence") or 0.0),
    )
    previous_diagnostics = state.get("confidence_diagnostics") or {}
    if state.get("secondary_fetch_applied") and diagnostics.get("route") == "stable":
        previous_route = str(previous_diagnostics.get("route", "stable"))
        if previous_route != "stable":
            diagnostics = {
                **diagnostics,
                "route": previous_route,
                "severity": previous_diagnostics.get("severity", diagnostics.get("severity", "low")),
                "reasons": previous_diagnostics.get("reasons", diagnostics.get("reasons", [])),
                "summary": previous_diagnostics.get("summary", diagnostics.get("summary", "")),
            }
    route = str(diagnostics.get("route", "stable"))
    summary = str(diagnostics.get("summary", ""))
    return {
        "confidence_diagnostics": diagnostics,
        "route_decision": route,
        "agent_trace": [
            *state.get("agent_trace", []),
            f"agent loop step=diagnose-path route={route} summary={summary}",
        ],
        "workflow_trace": [
            *state.get("workflow_trace", []),
            f"langgraph node=diagnose_path route={route}",
        ],
    }



def _diagnose_route(state: AnalysisGraphState) -> Literal["augment_sources", "secondary_analysis"]:
    route = str(state.get("route_decision", "stable"))
    if state.get("secondary_fetch_applied"):
        return "secondary_analysis"
    if route == "stable":
        return "secondary_analysis"
    return "augment_sources"



def _augment_sources_node(state: AnalysisGraphState) -> AnalysisGraphState:
    payload = state["payload"]
    route = str(state.get("route_decision", "stable"))
    historical_context = dict(state.get("historical_context", {}))
    realtime_context = dict(state.get("realtime_context", {}))
    applied: list[str] = []

    if route in {"augment_historical", "augment_both"}:
        historical_context = build_historical_context(
            state["historical_service"],
            latitude=payload.lat,
            longitude=payload.lon,
            radius_km=payload.radius_km,
        )
        applied.append("historical")

    if route in {"augment_realtime", "augment_both"}:
        realtime_context = build_realtime_context(
            state["realtime_status_provider"],
            latitude=payload.lat,
            longitude=payload.lon,
        )
        applied.append("realtime")

    derived_features = derive_group_b_features(
        latitude=payload.lat,
        longitude=payload.lon,
        historical_context=historical_context,
        realtime_context=realtime_context,
    )
    applied_text = ",".join(applied) if applied else "none"
    return {
        "historical_context": historical_context,
        "realtime_context": realtime_context,
        "derived_features": derived_features,
        "secondary_fetch_applied": applied,
        "agent_trace": [
            *state.get("agent_trace", []),
            f"agent loop step=augment-sources applied={applied_text}",
        ],
        "workflow_trace": [
            *state.get("workflow_trace", []),
            f"langgraph node=augment_sources applied={applied_text}",
        ],
    }



def _primary_assessment_node(state: AnalysisGraphState) -> AnalysisGraphState:
    features = {
        **state.get("historical_context", {}),
        **state.get("realtime_context", {}),
        **state.get("derived_features", {}),
    }
    model_scoring = build_model_scoring(
        features=features,
        model_scorer=state.get("model_scorer"),
    )
    initial_risk = score_risk(features)
    initial_false_positive = review_false_positive(features)
    trace_line = (
        "agent loop step=primary-assessment "
        f"risk={initial_risk['risk_level']} score={initial_risk['risk_score']} "
        f"false_positive={initial_false_positive['false_positive_risk']}"
    )
    return {
        "initial_risk": initial_risk,
        "initial_false_positive": initial_false_positive,
        "model_scoring": model_scoring,
        "final_risk": dict(initial_risk),
        "final_false_positive": dict(initial_false_positive),
        "agent_trace": [
            *state.get("agent_trace", []),
            trace_line,
            (
                "agent loop step=model-scoring "
                f"mode={model_scoring.get('decision_mode', 'rule_only_fallback')} "
                f"coverage={model_scoring.get('feature_coverage', 0.0)}"
            ),
        ],
        "workflow_trace": [
            *state.get("workflow_trace", []),
            "langgraph node=primary_assessment",
        ],
    }



def _secondary_analysis_node(state: AnalysisGraphState) -> AnalysisGraphState:
    route = str(state.get("route_decision", "stable"))
    result = run_secondary_analysis(
        route=route,
        initial_risk=state["initial_risk"],
        initial_false_positive=state["initial_false_positive"],
        historical_context=state.get("historical_context", {}),
        realtime_context=state.get("realtime_context", {}),
        derived_features=state.get("derived_features", {}),
        model_scoring=state.get("model_scoring"),
    )
    adjustments = list(result.get("adjustments") or [])
    analysis_mode = str(result.get("analysis_mode", "stable"))
    if adjustments:
        trace_line = (
            "agent loop step=secondary-analysis "
            f"mode={analysis_mode} adjustments={' | '.join(adjustments)}"
        )
    else:
        trace_line = f"agent loop step=secondary-analysis mode={analysis_mode} action=none"
    return {
        "final_risk": dict(result.get("final_risk") or state.get("final_risk", {})),
        "final_false_positive": dict(
            result.get("final_false_positive") or state.get("final_false_positive", {})
        ),
        "secondary_analysis_result": result,
        "agent_trace": [*state.get("agent_trace", []), trace_line],
        "workflow_trace": [
            *state.get("workflow_trace", []),
            f"langgraph node=secondary_analysis mode={analysis_mode}",
        ],
    }



def _verification_gate_node(state: AnalysisGraphState) -> AnalysisGraphState:
    verification_reasons = _collect_verification_reasons(
        historical_context=state.get("historical_context", {}),
        realtime_context=state.get("realtime_context", {}),
        derived_features=state.get("derived_features", {}),
        false_positive_risk=state["initial_false_positive"]["false_positive_risk"],
    )
    if verification_reasons:
        trace_line = "agent loop step=verification triggered=" + ", ".join(verification_reasons)
    else:
        trace_line = "agent loop step=verification skipped reason=signals_stable"
    return {
        "verification_reasons": verification_reasons,
        "agent_trace": [*state.get("agent_trace", []), trace_line],
        "workflow_trace": [
            *state.get("workflow_trace", []),
            "langgraph node=verification_gate",
        ],
    }



def _verification_route(state: AnalysisGraphState) -> Literal["run_reviews", "compose_report"]:
    if state.get("verification_reasons"):
        return "run_reviews"
    return "compose_report"



def _false_positive_review_node(state: AnalysisGraphState) -> AnalysisGraphState:
    false_positive_risk = state["initial_false_positive"]["false_positive_risk"]
    score_penalty = float(state.get("score_penalty", 0.0))
    agent_trace = list(state.get("agent_trace", []))

    if false_positive_risk == "high":
        score_penalty += 0.12
        agent_trace.append("agent loop step=false-positive-review action=apply_high_penalty")
    elif false_positive_risk == "medium":
        score_penalty += 0.05
        agent_trace.append("agent loop step=false-positive-review action=apply_medium_penalty")
    else:
        agent_trace.append("agent loop step=false-positive-review action=none")

    return {
        "score_penalty": score_penalty,
        "agent_trace": agent_trace,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            "langgraph node=false_positive_review",
        ],
    }



def _data_quality_review_node(state: AnalysisGraphState) -> AnalysisGraphState:
    estimated_fields = state.get("derived_features", {}).get("estimated_fields") or []
    score_penalty = float(state.get("score_penalty", 0.0))
    agent_trace = list(state.get("agent_trace", []))

    if len(estimated_fields) >= 3:
        score_penalty += 0.06
        agent_trace.append(
            "agent loop step=data-quality-review action=penalize_estimated_fields "
            f"count={len(estimated_fields)}"
        )
    elif estimated_fields:
        score_penalty += 0.03
        agent_trace.append(
            "agent loop step=data-quality-review action=minor_penalty_estimated_fields "
            f"count={len(estimated_fields)}"
        )
    else:
        agent_trace.append("agent loop step=data-quality-review action=none")

    return {
        "score_penalty": score_penalty,
        "agent_trace": agent_trace,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            "langgraph node=data_quality_review",
        ],
    }



def _source_review_node(state: AnalysisGraphState) -> AnalysisGraphState:
    historical_context = state.get("historical_context", {})
    realtime_context = state.get("realtime_context", {})
    score_penalty = float(state.get("score_penalty", 0.0))
    agent_trace = list(state.get("agent_trace", []))

    realtime_source = str(realtime_context.get("source", "unknown"))
    historical_source = str(historical_context.get("source", "unknown"))

    if realtime_source != "live":
        score_penalty += 0.03
        agent_trace.append(
            "agent loop step=source-review action=penalize_realtime_source "
            f"source={realtime_source}"
        )
    else:
        agent_trace.append("agent loop step=source-review realtime_action=none")

    if historical_source == "fallback":
        score_penalty += 0.02
        agent_trace.append(
            "agent loop step=source-review action=penalize_historical_source "
            f"source={historical_source}"
        )
    else:
        agent_trace.append(
            "agent loop step=source-review historical_action=none "
            f"source={historical_source}"
        )

    return {
        "score_penalty": score_penalty,
        "agent_trace": agent_trace,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            "langgraph node=source_review",
        ],
    }



def _decision_adjustment_node(state: AnalysisGraphState) -> AnalysisGraphState:
    score_penalty = float(state.get("score_penalty", 0.0))
    initial_risk = state["initial_risk"]
    final_risk = dict(state.get("final_risk", initial_risk))
    agent_trace = list(state.get("agent_trace", []))

    if score_penalty > 0:
        adjusted_score = round(max(float(initial_risk["risk_score"]) - score_penalty, 0.0), 2)
        adjusted_level = _risk_level_from_score(adjusted_score)
        final_risk = {
            **final_risk,
            "risk_score": adjusted_score,
            "risk_level": adjusted_level,
        }
        agent_trace.append(
            "agent loop step=decision-adjustment "
            f"score_penalty={score_penalty:.2f} result={adjusted_level}:{adjusted_score}"
        )
    else:
        agent_trace.append("agent loop step=decision-adjustment action=none")

    return {
        "final_risk": final_risk,
        "agent_trace": agent_trace,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            "langgraph node=decision_adjustment",
        ],
    }



def _compose_report_node(state: AnalysisGraphState) -> AnalysisGraphState:
    payload = state["payload"]
    report = _assemble_report(
        lat=payload.lat,
        lon=payload.lon,
        user_type=payload.user_type,
        historical_context=state.get("historical_context", {}),
        realtime_context=state.get("realtime_context", {}),
        derived_features=state.get("derived_features", {}),
        initial_risk=state["initial_risk"],
        model_scoring=state.get("model_scoring"),
        final_risk=state.get("final_risk", state["initial_risk"]),
        final_false_positive=state.get("final_false_positive", state["initial_false_positive"]),
        agent_trace=state.get("agent_trace", []),
        confidence_diagnostics=state.get("confidence_diagnostics"),
        secondary_fetch_applied=state.get("secondary_fetch_applied"),
    )
    return {
        "report": report,
        "workflow_trace": [
            *state.get("workflow_trace", []),
            "langgraph node=compose_report",
        ],
    }



def _build_response_node(state: AnalysisGraphState) -> AnalysisGraphState:
    selection = state["selection"]
    report = state["report"]
    workflow_trace = [
        *state.get("workflow_trace", []),
        "langgraph node=build_response",
    ]
    uncertainty_notes = [*report.get("uncertainty_notes", []), *workflow_trace]
    response = {
        **report,
        "uncertainty_notes": uncertainty_notes,
        "selected_tools": selection.selected_tools,
        "selection_reason": selection.reason,
        "selection_mode": selection.mode,
    }
    return {
        "response": response,
        "workflow_trace": workflow_trace,
    }



def _assemble_report(
    *,
    lat: float,
    lon: float,
    user_type: str,
    historical_context: dict,
    realtime_context: dict,
    derived_features: dict,
    initial_risk: dict,
    model_scoring: dict | None,
    final_risk: dict,
    final_false_positive: dict,
    agent_trace: list[str],
    confidence_diagnostics: dict | None = None,
    secondary_fetch_applied: list[str] | None = None,
) -> dict:
    if model_scoring is None:
        model_scoring_payload: dict[str, Any] = build_model_scoring(
            features={
                **historical_context,
                **realtime_context,
                **derived_features,
            }
        )
    else:
        model_scoring_payload = model_scoring
    estimated_fields = derived_features.get("estimated_fields") or []
    confidence = _calculate_confidence(
        false_positive_risk=final_false_positive["false_positive_risk"],
        historical_context=historical_context,
        realtime_context=realtime_context,
        estimated_fields=estimated_fields,
        risk_changed=(
            final_risk["risk_level"] != initial_risk["risk_level"]
            or final_risk["risk_score"] != initial_risk["risk_score"]
        ),
    )
    analysis_radius_km = float(
        historical_context.get("radius_km") or DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM
    )
    confidence_metrics = build_confidence_metrics(
        confidence=confidence,
        nearby_incident_count=int(historical_context.get("incident_count", 0) or 0),
        estimated_fields=estimated_fields,
        historical_source=str(historical_context.get("source", "unknown")),
        realtime_source=str(realtime_context.get("source", "unknown")),
    )
    actions = _build_actions(
        user_type=user_type,
        risk_level=final_risk["risk_level"],
        false_positive_risk=final_false_positive["false_positive_risk"],
        realtime_context=realtime_context,
        estimated_fields=estimated_fields,
    )
    key_factors = _build_key_factors(
        initial_factors=initial_risk.get("key_factors") or [],
        final_risk=final_risk,
        initial_risk=initial_risk,
        false_positive_risk=final_false_positive["false_positive_risk"],
        estimated_fields=estimated_fields,
        realtime_context=realtime_context,
    )
    reviewed_signals = _build_reviewed_signals(
        historical_context=historical_context,
        realtime_context=realtime_context,
        derived_features=derived_features,
        analysis_radius_km=analysis_radius_km,
    )
    xai_reasons = _build_xai_reasons(
        final_risk=final_risk,
        false_positive_risk=final_false_positive["false_positive_risk"],
        initial_factors=initial_risk.get("key_factors") or [],
        estimated_fields=estimated_fields,
        historical_context=historical_context,
        realtime_context=realtime_context,
    )
    risk_summary_text = _build_risk_summary_text(
        risk_level=final_risk["risk_level"],
        risk_score=float(final_risk["risk_score"]),
        incident_count=int(historical_context.get("incident_count", 0) or 0),
        radius_km=analysis_radius_km,
    )
    false_positive_summary_text = _build_false_positive_summary_text(
        false_positive_risk=final_false_positive["false_positive_risk"],
        confidence_margin=float(confidence_metrics["confidence_margin"]),
    )
    data_quality_summary = _build_data_quality_summary(
        confidence=confidence,
        confidence_metrics=confidence_metrics,
        estimated_fields=estimated_fields,
        confidence_diagnostics=confidence_diagnostics,
        secondary_fetch_applied=secondary_fetch_applied or [],
    )
    uncertainty_notes = _build_uncertainty_notes(
        base_false_positive_notes=final_false_positive["uncertainty_notes"],
        historical_context=historical_context,
        realtime_context=realtime_context,
        derived_features=derived_features,
        estimated_fields=estimated_fields,
        agent_trace=agent_trace,
        lat=lat,
        lon=lon,
        confidence_diagnostics=confidence_diagnostics,
        model_scoring=model_scoring_payload,
        secondary_fetch_applied=secondary_fetch_applied or [],
    )
    return {
        **final_risk,
        "false_positive_risk": final_false_positive["false_positive_risk"],
        "confidence": confidence,
        "confidence_breakdown": {
            "route": str((confidence_diagnostics or {}).get("route", "stable")),
            "severity": str((confidence_diagnostics or {}).get("severity", "low")),
            "source_quality_score": float(confidence_metrics["source_quality_score"]),
            "confidence_lower_bound": float(confidence_metrics["confidence_lower_bound"]),
            "confidence_upper_bound": float(confidence_metrics["confidence_upper_bound"]),
            "estimated_field_count": str(len(estimated_fields)),
            "historical_source": str(historical_context.get("source", "unknown")),
            "realtime_source": str(realtime_context.get("source", "unknown")),
        },
        "confidence_reasons": list((confidence_diagnostics or {}).get("reasons") or []),
        "confidence_margin": confidence_metrics["confidence_margin"],
        "reroute_applied": bool(secondary_fetch_applied),
        "reroute_reason": str(
            (confidence_diagnostics or {}).get("summary")
            or ("현재 데이터 조합만으로 1차 분석을 유지합니다." if not secondary_fetch_applied else "")
        ),
        "model_score": model_scoring_payload.get("ml_score"),
        "model_confidence": float(model_scoring_payload.get("ml_confidence") or 0.0),
        "model_version": str(model_scoring_payload.get("model_version") or ""),
        "model_feature_coverage": float(model_scoring_payload.get("feature_coverage") or 0.0),
        "model_decision_mode": str(model_scoring_payload.get("decision_mode") or "rule_only_fallback"),
        "model_reason": str(model_scoring_payload.get("reason") or ""),
        "analysis_radius_km": analysis_radius_km,
        "radius_points": _build_radius_points(lat=lat, lon=lon, radius_km=analysis_radius_km),
        "key_factors": key_factors,
        "recommended_actions": actions,
        "risk_summary_text": risk_summary_text,
        "false_positive_summary_text": false_positive_summary_text,
        "xai_reasons": xai_reasons,
        "reviewed_signals": reviewed_signals,
        "data_quality_summary": data_quality_summary,
        "uncertainty_notes": uncertainty_notes,
    }



def _build_radius_points(*, lat: float, lon: float, radius_km: float) -> dict[str, dict[str, float]]:
    radius_points: dict[str, dict[str, float]] = {}
    for direction in ("north", "south", "east", "west"):
        point = cardinal_point(
            latitude=lat,
            longitude=lon,
            radius_km=radius_km,
            direction=direction,
        )
        radius_points[direction] = {
            "lat": round(point.latitude, 6),
            "lon": round(point.longitude, 6),
        }
    return radius_points



def _build_risk_summary_text(*, risk_level: str, risk_score: float, incident_count: int, radius_km: float) -> str:
    level_text = {
        "low": "낮은 편",
        "medium": "중간 수준",
        "high": "높은 상태",
        "critical": "매우 높은 상태",
    }.get(risk_level, "확인 필요 상태")
    return (
        f"현재 위치는 반경 {radius_km:.1f}km 기준으로 산불 위험이 {level_text}입니다 "
        f"(위험 점수 {risk_score:.2f}, 인접 이력 {incident_count}건 참고)."
    )



def _build_false_positive_summary_text(*, false_positive_risk: str, confidence_margin: float) -> str:
    level_text = {
        "low": "오탐 가능성은 낮은 편입니다",
        "medium": "오탐 가능성을 함께 염두에 둬야 합니다",
        "high": "오탐 가능성이 높아 추가 확인이 필요합니다",
    }.get(false_positive_risk, "오탐 가능성을 함께 검토했습니다")
    return f"{level_text}. 현재 신뢰도 변동 폭은 ±{confidence_margin:.2f} 수준으로 해석합니다."



def _build_reviewed_signals(
    *,
    historical_context: dict,
    realtime_context: dict,
    derived_features: dict,
    analysis_radius_km: float,
) -> list[str]:
    reviewed_signals = [
        f"반경 {analysis_radius_km:.1f}km 인접 산불 이력 {int(historical_context.get('incident_count', 0) or 0)}건",
        f"과거 데이터 출처: {historical_context.get('source', 'unknown')}",
        f"실시간 데이터 출처: {realtime_context.get('source', 'unknown')}",
    ]

    status = realtime_context.get("status") or {}
    if status.get("humidity_percent") is not None:
        reviewed_signals.append(f"실시간 습도 {float(status['humidity_percent']):.1f}%")
    if status.get("wind_speed") is not None:
        reviewed_signals.append(f"실시간 풍속 {float(status['wind_speed']):.1f}m/s")

    estimated_fields = derived_features.get("estimated_fields") or []
    if estimated_fields:
        reviewed_signals.append(f"추정값 포함 항목 {len(estimated_fields)}개")

    return _dedupe_preserve_order(reviewed_signals)



def _build_xai_reasons(
    *,
    final_risk: dict,
    false_positive_risk: str,
    initial_factors: list[str],
    estimated_fields: list[str],
    historical_context: dict,
    realtime_context: dict,
) -> list[str]:
    xai_reasons = [
        *[f"위험 판단 근거: {factor}" for factor in initial_factors],
        f"최종 위험 단계는 {final_risk['risk_level']}이며 점수는 {float(final_risk['risk_score']):.2f}입니다.",
        f"오탐 위험 평가는 {false_positive_risk} 단계입니다.",
    ]
    if historical_context.get("incident_count") is not None:
        xai_reasons.append(
            f"주변 과거 산불 이력 {int(historical_context.get('incident_count', 0) or 0)}건을 함께 검토했습니다."
        )
    if realtime_context.get("source") != "live":
        xai_reasons.append("실시간 데이터가 완전한 실측값이 아니어서 보수적으로 해석했습니다.")
    if estimated_fields:
        joined = ", ".join(estimated_fields)
        xai_reasons.append(f"다음 항목은 추정치가 포함되었습니다: {joined}.")
    return _dedupe_preserve_order(xai_reasons)



def _build_data_quality_summary(
    *,
    confidence: float,
    confidence_metrics: dict[str, float | str],
    estimated_fields: list[str],
    confidence_diagnostics: dict | None = None,
    secondary_fetch_applied: list[str] | None = None,
) -> str:
    lower_bound = float(confidence_metrics["confidence_lower_bound"])
    upper_bound = float(confidence_metrics["confidence_upper_bound"])
    summary = (
        f"현재 신뢰도는 {confidence:.2f}이며 해석 범위는 대략 {lower_bound:.2f}~{upper_bound:.2f}입니다. "
        f"{confidence_metrics['source_quality_summary']}"
    )
    if estimated_fields:
        summary += f" 추정값이 포함된 항목은 {len(estimated_fields)}개입니다."
    if confidence_diagnostics:
        summary += f" 경로 진단: {confidence_diagnostics.get('summary', '')}"
    if secondary_fetch_applied:
        summary += f" 보강 조회 소스: {', '.join(secondary_fetch_applied)}."
    return summary



def _coerce_selection_decision(value: ToolSelectionDecision | dict) -> ToolSelectionDecision:
    if isinstance(value, ToolSelectionDecision):
        return value
    if isinstance(value, dict):
        return ToolSelectionDecision(**value)
    raise TypeError("selection_decider must return ToolSelectionDecision or dict")



def _build_skipped_context(*, tool_name: str) -> dict[str, object]:
    return {
        "source": "skipped",
        "reason": f"group_e_deselected_{tool_name}",
        "status": {},
        "nearby_incidents": [],
    }



def _run_agent_loop(
    *,
    initial_risk: dict,
    initial_false_positive: dict,
    historical_context: dict,
    realtime_context: dict,
    derived_features: dict,
) -> tuple[dict, dict, list[str]]:
    trace = [
        (
            "agent loop step=primary-assessment "
            f"risk={initial_risk['risk_level']} score={initial_risk['risk_score']} "
            f"false_positive={initial_false_positive['false_positive_risk']}"
        )
    ]

    final_risk = dict(initial_risk)
    final_false_positive = dict(initial_false_positive)
    verification_reasons = _collect_verification_reasons(
        historical_context=historical_context,
        realtime_context=realtime_context,
        derived_features=derived_features,
        false_positive_risk=initial_false_positive["false_positive_risk"],
    )
    if not verification_reasons:
        trace.append("agent loop step=verification skipped reason=signals_stable")
        return final_risk, final_false_positive, trace

    trace.append(
        "agent loop step=verification triggered=" + ", ".join(verification_reasons)
    )

    score_penalty = 0.0
    if initial_false_positive["false_positive_risk"] == "high":
        score_penalty += 0.12
        trace.append("agent loop step=false-positive-review action=apply_high_penalty")
    elif initial_false_positive["false_positive_risk"] == "medium":
        score_penalty += 0.05
        trace.append("agent loop step=false-positive-review action=apply_medium_penalty")
    else:
        trace.append("agent loop step=false-positive-review action=none")

    estimated_fields = derived_features.get("estimated_fields") or []
    if len(estimated_fields) >= 3:
        score_penalty += 0.06
        trace.append(
            "agent loop step=data-quality-review action=penalize_estimated_fields "
            f"count={len(estimated_fields)}"
        )
    elif estimated_fields:
        score_penalty += 0.03
        trace.append(
            "agent loop step=data-quality-review action=minor_penalty_estimated_fields "
            f"count={len(estimated_fields)}"
        )
    else:
        trace.append("agent loop step=data-quality-review action=none")

    realtime_source = str(realtime_context.get("source", "unknown"))
    historical_source = str(historical_context.get("source", "unknown"))
    if realtime_source != "live":
        score_penalty += 0.03
        trace.append(
            "agent loop step=source-review action=penalize_realtime_source "
            f"source={realtime_source}"
        )
    else:
        trace.append("agent loop step=source-review realtime_action=none")
    if historical_source == "fallback":
        score_penalty += 0.02
        trace.append(
            "agent loop step=source-review action=penalize_historical_source "
            f"source={historical_source}"
        )
    else:
        trace.append(
            "agent loop step=source-review historical_action=none "
            f"source={historical_source}"
        )

    if score_penalty > 0:
        adjusted_score = round(max(float(initial_risk["risk_score"]) - score_penalty, 0.0), 2)
        adjusted_level = _risk_level_from_score(adjusted_score)
        final_risk = {
            **final_risk,
            "risk_score": adjusted_score,
            "risk_level": adjusted_level,
        }
        trace.append(
            "agent loop step=decision-adjustment "
            f"score_penalty={score_penalty:.2f} result={adjusted_level}:{adjusted_score}"
        )
    else:
        trace.append("agent loop step=decision-adjustment action=none")

    return final_risk, final_false_positive, trace



def _collect_verification_reasons(
    *,
    historical_context: dict,
    realtime_context: dict,
    derived_features: dict,
    false_positive_risk: str,
) -> list[str]:
    reasons: list[str] = []
    estimated_fields = derived_features.get("estimated_fields") or []

    if false_positive_risk in {"medium", "high"}:
        reasons.append(f"false_positive={false_positive_risk}")
    if estimated_fields:
        reasons.append(f"estimated_fields={len(estimated_fields)}")
    if historical_context.get("source") != "live":
        reasons.append(f"historical_source={historical_context.get('source', 'unknown')}")
    if realtime_context.get("source") != "live":
        reasons.append(f"realtime_source={realtime_context.get('source', 'unknown')}")

    return reasons



def _calculate_confidence(
    *,
    false_positive_risk: str,
    historical_context: dict,
    realtime_context: dict,
    estimated_fields: list[str],
    risk_changed: bool,
) -> float:
    baseline_by_fp = {
        "low": 0.84,
        "medium": 0.74,
        "high": 0.62,
    }
    confidence = baseline_by_fp.get(false_positive_risk, 0.7)

    if historical_context.get("source") == "estimated":
        confidence -= 0.05
    elif historical_context.get("source") == "fallback":
        confidence -= 0.08

    if realtime_context.get("source") != "live":
        confidence -= 0.07
    if estimated_fields:
        confidence -= min(0.02 * len(estimated_fields), 0.1)
    if risk_changed:
        confidence -= 0.04
    if historical_context.get("source") == "live" and realtime_context.get("source") == "live" and not estimated_fields:
        confidence += 0.03

    return round(min(max(confidence, 0.35), 0.93), 2)



def _build_actions(
    *,
    user_type: str,
    risk_level: str,
    false_positive_risk: str,
    realtime_context: dict,
    estimated_fields: list[str],
) -> list[str]:
    base_actions = list(BASE_ACTIONS.get(user_type, BASE_ACTIONS["default"]))
    extra_actions: list[str] = []

    if risk_level in {"high", "critical"}:
        extra_actions.append("산림·소방 합동상황실 기준으로 경보 단계를 재확인")
    if false_positive_risk in {"medium", "high"}:
        extra_actions.append("안개·구름·연무 가능성을 위성/영상 정보와 교차 검증")
    if realtime_context.get("source") != "live":
        extra_actions.append("실시간 공공데이터 부재로 현장 관측 또는 인근 관측소 값을 추가 확인")
    if estimated_fields:
        extra_actions.append("추정치가 포함된 항목은 현장 센서·관측값으로 재검증")

    return _dedupe_preserve_order([*base_actions, *extra_actions])



def _build_key_factors(
    *,
    initial_factors: list[str],
    final_risk: dict,
    initial_risk: dict,
    false_positive_risk: str,
    estimated_fields: list[str],
    realtime_context: dict,
) -> list[str]:
    factors = list(initial_factors)
    if final_risk["risk_level"] != initial_risk["risk_level"]:
        factors.append("오탐 교정 루프 반영")
    if false_positive_risk in {"medium", "high"}:
        factors.append("오탐 가능성 재검토 필요")
    if estimated_fields:
        factors.append(f"추정 기반 항목 {len(estimated_fields)}개 포함")
    if realtime_context.get("source") != "live":
        factors.append("실시간 데이터 신뢰도 제한")
    if not factors:
        factors.append("위험 신호 제한적")
    return _dedupe_preserve_order(factors)



def _build_uncertainty_notes(
    *,
    base_false_positive_notes: list[str],
    historical_context: dict,
    realtime_context: dict,
    derived_features: dict,
    estimated_fields: list[str],
    agent_trace: list[str],
    lat: float,
    lon: float,
    confidence_diagnostics: dict | None = None,
    model_scoring: dict | None = None,
    secondary_fetch_applied: list[str] | None = None,
) -> list[str]:
    diagnostics_reasons = []
    diagnostics_summary = "none"
    if confidence_diagnostics:
        diagnostics_reasons = confidence_diagnostics.get("reasons") or []
        diagnostics_summary = str(confidence_diagnostics.get("summary", "none"))

    return [
        *base_false_positive_notes,
        *agent_trace,
        f"confidence_diagnostics summary={diagnostics_summary}",
        f"confidence_diagnostics reasons={diagnostics_reasons or ['none']}",
        (
            "model_scoring decision_mode="
            f"{(model_scoring or {}).get('decision_mode', 'rule_only_fallback')} "
            f"version={(model_scoring or {}).get('model_version', 'unknown')} "
            f"coverage={(model_scoring or {}).get('feature_coverage', 0.0)}"
        ),
        f"secondary_fetch_applied={secondary_fetch_applied or ['none']}",
        f"historical source={historical_context.get('source', 'unknown')} incident_count={historical_context.get('incident_count', 0)}",
        f"historical_context keys={sorted(historical_context.keys()) or ['none']}",
        f"realtime source={realtime_context.get('source', 'unknown')} reason={realtime_context.get('reason', 'none')}",
        f"realtime_context keys={sorted(realtime_context.keys()) or ['none']}",
        f"derived_features keys={sorted(derived_features.keys()) or ['none']}",
        f"estimated_fields={estimated_fields or ['none']}",
        f"입력 좌표(lat={lat}, lon={lon}) 기준으로 분석했습니다.",
    ]



def _risk_level_from_score(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.25:
        return "medium"
    return "low"



def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered

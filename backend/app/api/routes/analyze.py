from fastapi import APIRouter, Depends

from app.agents.wildfire_graph import ReportOrchestrator, get_report_orchestrator
from app.schemas.report import AnalyzeRequest, AnalyzeResponse
from app.services.group_b_context import (
    RealtimeStatusProvider,
    get_historical_wildfire_service,
    get_realtime_status_provider,
)
from app.services.group_e_selector import SelectionDecider, get_selection_decider
from app.services.historical_wildfire import HistoricalWildfireService
from app.services.model_scoring import ModelScorer, get_model_scorer

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    payload: AnalyzeRequest,
    orchestrator: ReportOrchestrator = Depends(get_report_orchestrator),
    historical_service: HistoricalWildfireService = Depends(get_historical_wildfire_service),
    realtime_status_provider: RealtimeStatusProvider = Depends(get_realtime_status_provider),
    selection_decider: SelectionDecider = Depends(get_selection_decider),
    model_scorer: ModelScorer | None = Depends(get_model_scorer),
) -> AnalyzeResponse:
    if not callable(orchestrator) or hasattr(orchestrator, "dependency"):
        orchestrator = get_report_orchestrator()
    if not hasattr(historical_service, "load_processed_summary_preview") or hasattr(historical_service, "dependency"):
        historical_service = get_historical_wildfire_service()
    if not callable(realtime_status_provider) or hasattr(realtime_status_provider, "dependency"):
        realtime_status_provider = get_realtime_status_provider()
    if not callable(selection_decider) or hasattr(selection_decider, "dependency"):
        selection_decider = get_selection_decider()
    if model_scorer is not None and not callable(model_scorer):
        model_scorer = get_model_scorer()

    report = orchestrator(
        payload=payload,
        historical_service=historical_service,
        realtime_status_provider=realtime_status_provider,
        selection_decider=selection_decider,
        model_scorer=model_scorer,
    )
    return AnalyzeResponse(**report)

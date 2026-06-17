from fastapi import APIRouter, Depends

from app.schemas.monitoring import MonitoringSummaryResponse
from app.services.monitoring_summary import MonitoringSummaryService, get_monitoring_summary_service

router = APIRouter()


@router.get("/monitoring/summary", response_model=MonitoringSummaryResponse)
def get_monitoring_summary(
    service: MonitoringSummaryService = Depends(get_monitoring_summary_service),
) -> MonitoringSummaryResponse:
    if not hasattr(service, "build_summary") or hasattr(service, "dependency"):
        service = get_monitoring_summary_service()
    return MonitoringSummaryResponse(**service.build_summary(limit=30))

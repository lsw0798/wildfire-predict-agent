from fastapi import APIRouter, Depends

from app.schemas.monitoring import ForestHeatmapResponse, MonitoringSummaryResponse
from app.services.forest_heatmap import ForestHeatmapService, get_forest_heatmap_service
from app.services.monitoring_summary import MonitoringSummaryService, get_monitoring_summary_service

router = APIRouter()


@router.get("/monitoring/summary", response_model=MonitoringSummaryResponse)
def get_monitoring_summary(
    service: MonitoringSummaryService = Depends(get_monitoring_summary_service),
) -> MonitoringSummaryResponse:
    if not hasattr(service, "build_summary") or hasattr(service, "dependency"):
        service = get_monitoring_summary_service()
    return MonitoringSummaryResponse(**service.build_summary(limit=30))


@router.get("/monitoring/forest-heatmap", response_model=ForestHeatmapResponse)
def get_forest_heatmap(
    limit: int = 250,
    resolution: float = 0.1,
    service: ForestHeatmapService = Depends(get_forest_heatmap_service),
) -> ForestHeatmapResponse:
    if not hasattr(service, "build_heatmap") or hasattr(service, "dependency"):
        service = get_forest_heatmap_service()
    return ForestHeatmapResponse(**service.build_heatmap(limit=limit, resolution=resolution))

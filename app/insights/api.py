"""FastAPI router for CORTIA Insights Explainable AI Centre."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from .service import InsightsService

router = APIRouter(prefix="/api/insights", tags=["insights"])


def get_insights_service(request: Request) -> InsightsService:
    model_dir = getattr(request.app.state, "model_dir", None)
    if not model_dir:
        import os
        model_dir = os.getenv("BHM_MODEL_DIR", "model")
    eeg_service = getattr(request.app.state, "eeg", None)
    eeg_store = eeg_service.store if eeg_service else None
    return InsightsService(model_dir=model_dir, eeg_store=eeg_store)


@router.get("/overview")
def get_insights_overview(service: InsightsService = Depends(get_insights_service)):
    evals = service.get_model_evaluations()
    history = service.get_unified_history(limit=5)
    latest_mri = service.get_latest_mri_scan()
    latest_eeg = service.get_latest_eeg_session()
    evs_ready = evals["mri"]["available"]
    return {
        "workspace": "CORTIA Insights — Explainable AI Centre",
        "mri_status": {
            "model_ready": evs_ready,
            "model_name": evals["mri"]["model_name"],
            "test_accuracy": evals["mri"].get("accuracy"),
            "latest_scan_id": latest_mri["scan_id"] if latest_mri else None,
        },
        "eeg_status": {
            "model_installed": False,
            "signal_pipeline_active": True,
            "active_channels": 1,
            "hardware_scope": "Maker UNO + BioAmp EXG Pill (Uncalibrated ADC counts)",
            "latest_session_id": latest_eeg["session_id"] if latest_eeg else None,
        },
        "recent_activity": history,
        "disclaimer": "Research and explainability workspace only. Not evaluated for diagnostic or therapeutic decision-making.",
    }


@router.get("/mri/latest")
def get_latest_mri(service: InsightsService = Depends(get_insights_service)):
    scan = service.get_latest_mri_scan()
    if not scan:
        raise HTTPException(status_code=404, detail="No MRI scan records found in database.")
    return scan


@router.get("/mri/{scan_id}")
def get_mri_explanation(scan_id: int, service: InsightsService = Depends(get_insights_service)):
    scan = service.get_mri_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"MRI scan record {scan_id} not found.")
    return scan


@router.get("/eeg/latest")
def get_latest_eeg(service: InsightsService = Depends(get_insights_service)):
    sess = service.get_latest_eeg_session()
    if not sess:
        raise HTTPException(status_code=404, detail="No EEG session records found in database.")
    return sess


@router.get("/eeg/{session_id}")
def get_eeg_feature_record(session_id: str, service: InsightsService = Depends(get_insights_service)):
    sess = service.get_eeg_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"EEG session {session_id} not found.")
    return sess


@router.get("/performance")
def get_performance_records(service: InsightsService = Depends(get_insights_service)):
    return service.get_model_evaluations()


@router.get("/history")
def get_history(
    limit: int = Query(50, ge=1, le=200),
    type: Optional[str] = Query(None, pattern="^(all|mri|eeg)$"),
    service: InsightsService = Depends(get_insights_service),
):
    return service.get_unified_history(limit=limit, filter_type=type)


@router.get("/compare/eeg")
def compare_eeg(
    session_a: str = Query(..., description="First EEG session ID"),
    session_b: str = Query(..., description="Second EEG session ID"),
    service: InsightsService = Depends(get_insights_service),
):
    try:
        return service.compare_eeg_sessions(session_a, session_b)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

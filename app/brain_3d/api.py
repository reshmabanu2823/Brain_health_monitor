"""FastAPI router for 3D Brain Imaging."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from .service import get_brain_3d_service

router = APIRouter(prefix="/api/brain", tags=["brain-3d"])


@router.get("/studies")
def list_studies() -> Dict[str, Any]:
    svc = get_brain_3d_service()
    return {"studies": svc.list_studies()}


@router.get("/studies/{study_id}")
def get_study_details(study_id: str) -> Dict[str, Any]:
    svc = get_brain_3d_service()
    study = svc.get_study(study_id)
    if not study:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")
    return study


@router.get("/studies/{study_id}/mesh")
def get_study_mesh(study_id: str, layer: str = Query("brain", regex="^(brain|lesion)$")) -> Dict[str, Any]:
    svc = get_brain_3d_service()
    try:
        return svc.get_mesh(study_id, layer=layer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate 3D mesh: {str(exc)}")


@router.get("/studies/{study_id}/slice")
def get_study_slice(
    study_id: str,
    axis: str = Query("axial", regex="^(axial|coronal|sagittal)$"),
    index: int = Query(64, ge=0),
    mask: int = Query(1, ge=0, le=1)
):
    svc = get_brain_3d_service()
    try:
        png_bytes = svc.get_slice_image(study_id, axis=axis, index=index, show_mask=bool(mask))
        return Response(content=png_bytes, media_type="image/png")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate slice: {str(exc)}")

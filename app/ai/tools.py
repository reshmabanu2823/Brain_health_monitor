"""Read-only, authorized project state retrieval tools for CORTIA AI."""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from ..logger import connection as scan_db_conn
    from ..artifacts import load_contract
except ImportError:
    from logger import connection as scan_db_conn
    from artifacts import load_contract

log = logging.getLogger(__name__)


def get_eeg_hardware_status(eeg_service) -> Dict[str, Any]:
    """Retrieve EEG connection state and hardware status without fabricating live activity."""
    if not eeg_service:
        return {"connected": False, "source": None, "state": "unavailable", "note": "EEG service not initialized."}
    snap = eeg_service.snapshot()
    source = snap.get("source")
    state = snap.get("state")
    return {
        "connected": state in ("streaming", "recording"),
        "state": state,
        "source": source,
        "is_simulated": source == "simulated",
        "measured_rate_hz": snap.get("measured_rate_hz"),
        "quality_state": snap.get("quality_state"),
        "quality_reasons": snap.get("quality_reasons", []),
        "disclaimer": "Simulated waveform data is active when source is 'simulated'. Physical hardware is only used when connected via serial port.",
    }


def get_latest_eeg_summary(eeg_service) -> Optional[Dict[str, Any]]:
    """Retrieve latest stored EEG session summary from real database."""
    if not eeg_service or not eeg_service.store:
        return None
    sessions = eeg_service.store.list(limit=1)
    if not sessions:
        return None
    return get_eeg_session_summary(eeg_service, sessions[0]["id"])


def get_eeg_session_summary(eeg_service, session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve verified summary for a specific EEG session."""
    if not eeg_service or not eeg_service.store:
        return None
    try:
        summary = eeg_service.store.get_summary(session_id)
        return summary
    except KeyError:
        return None
    except Exception as exc:
        log.exception("Failed to retrieve EEG session %s: %s", session_id, exc)
        return None


def get_model_registry(eeg_service) -> Dict[str, Any]:
    """Retrieve model registry showing availability and clinical feasibility boundaries."""
    from ..eeg.api import model_registry
    class DummyService:
        def __init__(self, model):
            self.model = model
    return model_registry(DummyService(eeg_service.model if eeg_service else None))


def get_latest_mri_scan() -> Optional[Dict[str, Any]]:
    """Retrieve the most recent real MRI analysis record."""
    with scan_db_conn() as conn:
        row = conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    return _format_scan_row(row)


def get_mri_scan_by_id(scan_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve an MRI analysis record by ID."""
    with scan_db_conn() as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if not row:
        return None
    return _format_scan_row(row)


def _format_scan_row(row) -> Dict[str, Any]:
    record = dict(row)
    probs = json.loads(record.pop("probabilities_json") or "{}")
    return {
        "scan_id": record["id"],
        "filename": record["filename"],
        "timestamp": record["timestamp"],
        "result": record["result"],
        "confidence": float(record["confidence"]),
        "is_tumor": bool(record["is_tumor"]),
        "probabilities": probs,
        "tumor_area_pct": float(record.get("tumor_area_pct") or 0.0),
        "peak_saliency": float(record.get("peak_saliency") or 0.0),
        "notes": record.get("notes") or "",
        "patient_id": record.get("patient_id") or "ANON",
        "explanation": {
            "method": "Grad-CAM",
            "available": bool(record.get("peak_saliency", 0) > 0),
            "measurement": "saliency coverage, not lesion segmentation",
        }
    }


def get_verified_model_evaluations(model_dir: str) -> Dict[str, Any]:
    """Retrieve real evaluation records for MRI and EEG without fabricating data."""
    directory = Path(model_dir)
    eval_file = directory / "evaluation.json"
    mri_data = None
    if eval_file.exists():
        try:
            mri_data = json.loads(eval_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "mri_evaluation": mri_data,
        "eeg_evaluation": {
            "available": False,
            "reason": "No trained EEG classifier model installed.",
            "hardware_limitation": "Single-channel BioAmp EXG is constrained to bipolar biopotential telemetry and cannot perform sleep staging or psychiatric diagnostic screening."
        }
    }


def get_system_health(app_state) -> Dict[str, Any]:
    """Retrieve actual system runtime health."""
    model_loaded = getattr(app_state, "model", None) is not None
    eeg_active = getattr(app_state, "eeg", None) is not None
    return {
        "status": "healthy" if model_loaded else "degraded",
        "system_name": "CORTIA Neural Observation Platform v3.0",
        "mri_inference_ready": model_loaded,
        "eeg_service_ready": eeg_active,
        "disclaimer": "Research and observation platform only. Not approved for diagnostic use.",
    }

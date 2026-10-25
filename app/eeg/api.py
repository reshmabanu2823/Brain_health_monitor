"""EEG routes in the existing FastAPI process, separate from MRI routes."""
import json
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from serial.tools import list_ports
import database as cortia_db

router = APIRouter()


def service(request: Request):
    s = getattr(request.app.state, 'eeg', None)
    if s is None:
        raise HTTPException(503, 'EEG service unavailable')
    return s


def local_control(request: Request):
    origin = request.headers.get('origin')
    if origin and urlsplit(origin).netloc != request.headers.get('host'):
        raise HTTPException(403, 'Device controls require same-origin requests')


class ConnectRequest(BaseModel):
    source: Literal['serial', 'simulated']
    port: str | None = Field(default=None, max_length=256)


class StartRecordingRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class UpdateNotesRequest(BaseModel):
    notes: str = Field(..., max_length=4000)


@router.get('/api/device/ports')
def ports():
    return [{'device': p.device, 'description': p.description} for p in list_ports.comports()]


@router.get('/api/device/status')
def status(s=Depends(service)):
    return {k: v for k, v in s.snapshot().items() if k not in ('samples', 'analysis', 'prediction')}


@router.post('/api/device/connect', dependencies=[Depends(local_control)])
def connect(body: ConnectRequest, s=Depends(service)):
    if body.source == 'serial' and body.port not in {p.device for p in list_ports.comports()}:
        raise HTTPException(422, 'Choose an available serial port from /api/device/ports')
    try:
        s.connect(body.source, body.port)
        return {'state': 'starting', 'source': body.source}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/api/device/disconnect', dependencies=[Depends(local_control)])
def disconnect(s=Depends(service)):
    try:
        s.disconnect()
        return {'state': 'disconnected'}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get('/api/eeg/live')
def live(s=Depends(service)):
    return s.snapshot()


@router.get('/api/eeg/model/info')
def model_info(s=Depends(service)):
    if s.model is None:
        return {'available': False, 'reason': 'No EEG model installed; labeled dataset required'}
    # No training subject identifiers or source-file paths in the public response.
    return {k: v for k, v in s.model.info.items() if k in ('available', 'reason', 'name', 'version', 'task', 'labels', 'feature_names', 'preprocessing', 'units', 'limitation')}


@router.get('/api/eeg/models/registry')
def model_registry(s=Depends(service)):
    """Model registry documenting planned experimental modules, input formats, and clinical feasibility constraints."""
    active_model = None
    if s.model and getattr(s.model, 'estimator', None) is not None:
        active_model = {
            'name': s.model.info.get('name'),
            'version': s.model.info.get('version'),
            'task': s.model.info.get('task'),
            'labels': s.model.info.get('labels')
        }

    return {
        'registry_version': '2.0',
        'active_model': active_model,
        'hardware_scope': 'Maker UNO + BioAmp EXG Pill (1 bipolar biopotential channel, uncalibrated 10-bit ADC counts)',
        'modules': [
            {
                'module_id': 'stress_state_index',
                'name': 'Stress-Related State Estimation',
                'version': None,
                'intended_task': 'Research tracking of sympathetic autonomic arousal via frontal beta/alpha power ratios.',
                'required_input_format': 'Single-channel uncalibrated 10-bit ADC counts (250 Hz, 4s window + 1s guards, 1–40 Hz bandpass).',
                'availability': False,
                'reason': 'No trained subject-disjoint baseline artifact installed; labeled experimental dataset required.',
                'limitations': 'Uncalibrated single-channel biopotentials cannot differentiate psychological stress from ocular tension or ambient interference.'
            },
            {
                'module_id': 'relaxation_alpha_reactivity',
                'name': 'Relaxation / Alpha-Theta Reactivity',
                'version': None,
                'intended_task': 'Quantification of occipital/frontal alpha synchronization during eyes-closed relaxation vs. eyes-open baseline.',
                'required_input_format': 'Single-channel uncalibrated 10-bit ADC counts (250 Hz, 4s window + 1s guards, 1–40 Hz bandpass).',
                'availability': False,
                'reason': 'Experimental protocol defined in docs/EEG_ML.md; requires empirical multi-subject dataset collection.',
                'limitations': 'Forehead placement captures prominent ocular blink artifacts and frontal electromyographic noise that overlap alpha band frequencies.'
            },
            {
                'module_id': 'cognitive_attention_engagement',
                'name': 'Attention & Cognitive Engagement Baseline',
                'version': None,
                'intended_task': 'Relative theta-to-beta ratio (TBR) tracking during sustained attention tasks for research observation.',
                'required_input_format': 'Single-channel uncalibrated 10-bit ADC counts (250 Hz, 4s window + 1s guards, 1–40 Hz bandpass).',
                'availability': False,
                'reason': 'No calibrated classifier loaded; baseline awaiting verified controlled-task participant manifest.',
                'limitations': 'Single-channel TBR lacks multi-site central/parietal (Cz/Pz) spatial reference required for standardized attention metrics.'
            },
            {
                'module_id': 'sleep_polysomnography_staging',
                'name': 'Sleep Architecture & Staging',
                'version': None,
                'intended_task': 'Multi-stage NREM/REM sleep scoring (W, N1, N2, N3, REM).',
                'required_input_format': 'Multi-channel montage: minimum 2 EEG channels (C3/C4, O1/O2), dual EOG, and submental chin EMG.',
                'availability': False,
                'reason': 'NOT FEASIBLE on single-channel BioAmp hardware. Clinical polysomnography mandates multi-channel spatial electrooculography and electromyography.',
                'limitations': 'Single-channel uncalibrated forehead electrode cannot resolve sleep spindles (12–14 Hz sigma), K-complexes, slow-wave delta thresholds, or REM atonia.'
            },
            {
                'module_id': 'anxiety_disorder_assessment',
                'name': 'Anxiety State Evaluation',
                'version': None,
                'intended_task': 'Diagnostic classification of generalized or acute anxiety states.',
                'required_input_format': 'Standard 10-20 multi-channel clinical montage with impedance checking and normative database referencing.',
                'availability': False,
                'reason': 'NOT FEASIBLE on single-channel Maker UNO biopotential kit. Neuropsychiatric diagnoses require standardized clinical evaluation and multi-site spatial coherence.',
                'limitations': 'High-frequency beta/gamma rhythms in single-channel frontal leads are heavily contaminated by temporal muscle tension and cannot provide clinical specificity.'
            },
            {
                'module_id': 'depression_screening_module',
                'name': 'Depression Screening & Affective Asymmetry',
                'version': None,
                'intended_task': 'Frontal Alpha Asymmetry (FAA) depression vulnerability index.',
                'required_input_format': 'Bilateral homologous electrode pair (F3 and F4) with linked-ear or common average reference.',
                'availability': False,
                'reason': 'NOT FEASIBLE on 1-channel BioAmp hardware. FAA calculation mathematically requires simultaneous bilateral differential recording (ln[F4] - ln[F3]).',
                'limitations': 'A single physical channel cannot acquire differential hemispheric asymmetry.'
            }
        ]
    }


@router.post('/api/eeg/recordings', dependencies=[Depends(local_control)])
def start_recording(body: StartRecordingRequest | None = None, s=Depends(service)):
    try:
        notes = body.notes if body else None
        rec_id = s.start_recording(notes=notes)
        try:
            cortia_db.start_eeg_session(source="SIMULATED" if getattr(s, 'source', None) != 'serial' else 'HARDWARE', notes=notes or '')
        except Exception:
            pass
        return {'id': rec_id}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/api/eeg/recordings/stop', dependencies=[Depends(local_control)])
def stop_recording(s=Depends(service)):
    try:
        rec_id = s.stop_recording()
        try:
            rec = s.store.get(rec_id) if hasattr(s, 'store') and hasattr(s.store, 'get') else {}
            if rec:
                cortia_db.end_eeg_session(
                    session_id=rec_id,
                    duration_seconds=rec.get('duration_seconds', 0),
                    total_samples=rec.get('sample_count', 0),
                    signal_quality=rec.get('signal_quality', 'Acceptable'),
                    features_json=json.dumps(rec.get('features', {})),
                )
        except Exception:
            pass
        return {'id': rec_id}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/api/eeg/session/start")
def eeg_start(source: str = "SIMULATED", notes: str = ""):
    session_id = cortia_db.start_eeg_session(source=source, notes=notes)
    return {"session_id": session_id}


@router.post("/api/eeg/session/{session_id}/end")
def eeg_end(session_id: str, body: dict):
    cortia_db.end_eeg_session(
        session_id=session_id,
        duration_seconds=body.get("duration_seconds", 0),
        total_samples=body.get("total_samples", 0),
        signal_quality=body.get("signal_quality", "Unknown"),
        features_json=json.dumps(body.get("features", {})),
    )
    return {"status": "completed"}


@router.get("/api/eeg/sessions")
def list_eeg_sessions(limit: int = 50):
    return cortia_db.get_eeg_sessions(limit=limit)


@router.get('/api/eeg/recordings')
def recordings(limit: int = Query(100, ge=1, le=100), s=Depends(service)):
    return s.store.list(limit)


@router.get('/api/eeg/recordings/{rid}/summary')
def recording_summary(rid: str, s=Depends(service)):
    try:
        return s.store.get_summary(rid)
    except KeyError as exc:
        raise HTTPException(404, 'Recording not found') from exc


@router.post('/api/eeg/recordings/{rid}/notes', dependencies=[Depends(local_control)])
def update_recording_notes(rid: str, body: UpdateNotesRequest, s=Depends(service)):
    try:
        s.store.get(rid)
    except KeyError as exc:
        raise HTTPException(404, 'Recording not found') from exc
    s.store.update_notes(rid, body.notes)
    return {'status': 'updated', 'id': rid, 'notes': body.notes}


@router.get('/api/eeg/recordings/{rid}/export')
def export(rid: str, s=Depends(service)):
    try:
        session = s.store.get(rid)
    except KeyError as exc:
        raise HTTPException(404, 'Recording not found') from exc
    if session['status'] == 'recording':
        raise HTTPException(409, 'Stop recording before exporting a stable snapshot')
    return StreamingResponse(
        s.store.export(rid),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="eeg-{session["id"]}.csv"'}
    )

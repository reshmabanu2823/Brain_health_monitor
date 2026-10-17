"""FastAPI workstation API with bounded, validated model inference."""
import asyncio
import base64
import binascii
import io
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Optional
import numpy as np
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from app.eeg.api import router as eeg_router
from app.eeg.model import EEGModel
from app.eeg.service import EEGService
from app.eeg.signal import SignalConfig
from app.eeg.storage import RecordingStore

BASE_DIR = str(Path(__file__).resolve().parent)
APP_DIR = os.path.join(BASE_DIR, 'app')
MODEL_DIR = os.getenv('BHM_MODEL_DIR', os.path.join(BASE_DIR, 'model'))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOADS_DIR = os.getenv('BHM_UPLOAD_DIR', os.path.join(BASE_DIR, 'uploads'))
MAX_UPLOAD_BYTES = int(os.getenv('BHM_MAX_UPLOAD_BYTES', 10 * 1024 * 1024))
MAX_CONCURRENT_ANALYSES = int(os.getenv('BHM_MAX_CONCURRENT_ANALYSES', 2))
if MAX_UPLOAD_BYTES <= 0 or MAX_CONCURRENT_ANALYSES <= 0:
    raise ValueError('Upload limit and concurrency must be positive')
sys.path.append(APP_DIR)
from inference import BrainTumorModel, CLASS_LABELS, read_mri_file
from gradcam import generate_gradcam_heatmap, preload_gradcam_model
from logger import init_db, log_result, get_scan_history, get_scan_stats, clear_scan_history
from report_generator import generate_pdf_report

log = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.dcm', '.dicom'}
PROBABILITY_NAMES = ['Glioma', 'Meningioma', 'No Tumor', 'Pituitary']


@asynccontextmanager
async def lifespan(application):
    init_db()
    Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
    application.state.model = None
    application.state.analysis_slots = threading.BoundedSemaphore(MAX_CONCURRENT_ANALYSES)
    try:
        application.state.model = await asyncio.to_thread(BrainTumorModel, MODEL_DIR)
    except Exception:
        log.exception('Inference model unavailable at startup')
    eeg_config = SignalConfig(
        sample_rate=int(os.getenv('BHM_EEG_SAMPLE_RATE', '250')),
        window_seconds=float(os.getenv('BHM_EEG_WINDOW_SECONDS', '4')),
        guard_seconds=float(os.getenv('BHM_EEG_GUARD_SECONDS', '1')),
        low_hz=float(os.getenv('BHM_EEG_LOW_HZ', '1')),
        high_hz=float(os.getenv('BHM_EEG_HIGH_HZ', '40')),
        notch_hz=None if os.getenv('BHM_EEG_NOTCH_HZ', '50').lower() in ('none','off') else float(os.getenv('BHM_EEG_NOTCH_HZ', '50')),
    )
    eeg_db = os.getenv('BHM_EEG_DB', str(Path(os.getenv('BHM_LOG_DIR', 'logs')) / 'eeg.db'))
    application.state.eeg = EEGService(RecordingStore(eeg_db), eeg_config,
        EEGModel(os.getenv('BHM_EEG_MODEL_DIR', 'eeg_model')))
    # Acquisition starts only via explicit device controls, never automatically.
    # Keep the warm-up task tracked and drain it during shutdown.
    warmup = asyncio.create_task(asyncio.to_thread(preload_gradcam_model, MODEL_DIR))
    try:
        yield
    finally:
        await asyncio.to_thread(application.state.eeg.disconnect)
        await warmup


app = FastAPI(title='Brain Health Monitor API', description='Single-channel EEG and separate MRI research workstation', version='3.0.0', lifespan=lifespan)
app.include_router(eeg_router)
origins = [value.strip() for value in os.getenv('BHM_CORS_ORIGINS', '').split(',') if value.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


def safe_filename(value):
    name = Path(str(value).replace('\\', '/')).name
    return re.sub(r'[^A-Za-z0-9._ -]', '_', name)[:120] or 'scan.png'


def to_base64_url(image_data):
    if image_data is None:
        return None
    image = Image.fromarray(np.asarray(image_data, dtype=np.uint8)) if isinstance(image_data, np.ndarray) else image_data.copy()
    image = image.convert('RGB')
    image.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=92)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


def base64_to_pil(value):
    try:
        raw = base64.b64decode(value.split(',', 1)[-1], validate=True)
        if not raw or len(raw) > MAX_UPLOAD_BYTES:
            raise ValueError('Invalid report image size')
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError('Report image exceeds 16 megapixels')
            return image.convert('RGB')
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Invalid report image') from exc


class PDFReportRequest(BaseModel):
    patient_id: Optional[str] = Field(default='ANON', max_length=128)
    patient_name: Optional[str] = Field(default='De-identified', max_length=256)
    filename: str = Field(min_length=1, max_length=256)
    label: str
    confidence: float = Field(ge=0, le=100, allow_inf_nan=False)
    probabilities: dict[str, float]
    tumor_metrics: Optional[dict] = None
    original_b64: str = Field(max_length=14_000_000)
    heatmap_b64: Optional[str] = Field(default=None, max_length=14_000_000)
    notes: Optional[str] = Field(default='', max_length=4000)

    @field_validator('label')
    @classmethod
    def validate_label(cls, value):
        if value not in CLASS_LABELS.values():
            raise ValueError('Unknown classification label')
        return value

    @field_validator('probabilities')
    @classmethod
    def validate_probabilities(cls, values):
        if set(values) != set(PROBABILITY_NAMES) or any(not np.isfinite(v) or not 0 <= v <= 100 for v in values.values()) or abs(sum(values.values()) - 100) > .1:
            raise ValueError('Expected four percentages summing to 100')
        return values

    @field_validator('tumor_metrics')
    @classmethod
    def validate_metrics(cls, values):
        if not values:
            return {}
        for key, maximum in [('tumor_area_pct', 100), ('peak_saliency', 1)]:
            value = values.get(key, 0)
            if not isinstance(value, (int, float)) or not np.isfinite(value) or not 0 <= value <= maximum:
                raise ValueError('Invalid saliency metric')
        for name, keys in [('bbox', ('x', 'y', 'w', 'h')), ('center', ('x', 'y'))]:
            data = values.get(name)
            if data is not None and (not isinstance(data, dict) or any(type(data.get(key)) is not int or not 0 <= data[key] <= 224 for key in keys)):
                raise ValueError('Invalid saliency coordinates')
        return values


async def run_analysis(worker, gate):
    if not gate.acquire(blocking=False):
        raise HTTPException(503, 'Analysis capacity reached; retry shortly')
    def guarded():
        try:
            return worker()
        finally:
            gate.release()
    task = asyncio.create_task(asyncio.to_thread(guarded))
    # Shield keeps the worker alive on client cancellation; its finally owns cleanup.
    task.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None)
    return await asyncio.shield(task)


@app.get('/api/health')
def health_check():
    loaded = getattr(app.state, 'model', None) is not None
    return {'status': 'healthy' if loaded else 'degraded', 'system': 'Brain Health Monitor v3.0', 'model_loaded': loaded}


@app.get('/api/ready')
def readiness():
    if getattr(app.state, 'model', None) is None:
        return JSONResponse({'status': 'not_ready'}, status_code=503)
    return {'status': 'ready'}


@app.get('/api/stats')
def fetch_stats():
    return get_scan_stats(MODEL_DIR)


@app.get('/api/scans')
def fetch_scan_history(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return [{**row, 'patient_id': 'ANON', 'patient_name': 'De-identified'} for row in get_scan_history(limit, offset)]


@app.post('/api/scans/clear')
def clear_history():
    return {'success': clear_scan_history()}


def _process_upload(path, filename, model):
    try:
        image, metadata = read_mri_file(path)
        label, confidence, probabilities, _, _ = model.predict(image)
        labels = getattr(model, 'labels', list(CLASS_LABELS.values()))
        class_index = labels.index(label)
        overlay, metrics = generate_gradcam_heatmap(image, MODEL_DIR, return_metrics=True, class_index=class_index)
        names = getattr(model, 'probability_labels', PROBABILITY_NAMES)
        distribution = {name: round(float(probabilities[i]) * 100, 2) for i, name in enumerate(names)}
        metadata = {**metadata, 'patient_id': 'ANON', 'patient_name': 'De-identified'}
        patient_id = 'ANON'
        if patient_id == 'ANON':
            patient_id = 'SCAN-' + uuid.uuid4().hex[:12]
        patient_name = metadata.get('patient_name') or 'De-identified'
        scan_id = log_result(filename, label, confidence, distribution, patient_id=patient_id, patient_name=patient_name, tumor_area_pct=metrics.get('tumor_area_pct', 0), peak_saliency=metrics.get('peak_saliency', 0))
        return {'success': True, 'scan_id': scan_id, 'filename': filename, 'patient_id': patient_id, 'patient_name': patient_name, 'label': label, 'confidence': round(confidence, 1), 'is_tumor': label != 'No Tumor', 'probabilities': distribution, 'tumor_metrics': metrics, 'dicom_metadata': metadata, 'original_b64': to_base64_url(image), 'heatmap_b64': to_base64_url(overlay), 'explanation': {'available': overlay is not None, 'method': 'gradcam' if overlay is not None else None, 'class_index': class_index, 'measurement': 'saliency coverage, not lesion segmentation', 'reason': None if overlay is not None else 'Grad-CAM is unavailable for this prediction'}}
    finally:
        Path(path).unlink(missing_ok=True)


@app.post('/api/predict')
async def predict_mri(file: UploadFile = File(...)):
    model = getattr(app.state, 'model', None)
    if model is None:
        await file.close()
        raise HTTPException(503, 'Inference model is unavailable')
    filename = safe_filename(file.filename or 'scan.png')
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        await file.close()
        raise HTTPException(415, 'Unsupported image format')
    path = None
    transferred = False
    try:
        with tempfile.NamedTemporaryFile(dir=UPLOADS_DIR, suffix=suffix, delete=False) as output:
            path = output.name
            size = 0
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, 'Upload exceeds configured size limit')
                output.write(chunk)
        if size == 0:
            raise HTTPException(422, 'Empty image upload')
        transferred = True
        try:
            return await run_analysis(lambda: _process_upload(path, filename, model), app.state.analysis_slots)
        except HTTPException:
            # Capacity rejected the request before the worker took ownership.
            transferred = False
            raise
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(422, 'Invalid image or incompatible model output') from exc
    except Exception as exc:
        log.exception('Prediction failed')
        raise HTTPException(500, 'Prediction failed') from exc
    finally:
        await file.close()
        if path is not None and not transferred:
            Path(path).unlink(missing_ok=True)


def _render_pdf(request):
    original = base64_to_pil(request.original_b64)
    heatmap = base64_to_pil(request.heatmap_b64) if request.heatmap_b64 else None
    return generate_pdf_report(patient_id=request.patient_id or 'ANON', patient_name=request.patient_name or 'De-identified', filename=safe_filename(request.filename), label=request.label, confidence=request.confidence, probabilities=request.probabilities, tumor_metrics=request.tumor_metrics or {}, original_pil=original, heatmap_pil=heatmap, notes=request.notes or '')


@app.post('/api/report/pdf')
async def generate_pdf(request: PDFReportRequest):
    try:
        pdf = await run_analysis(lambda: _render_pdf(request), app.state.analysis_slots)
        filename = 'Model_Report_' + Path(safe_filename(request.filename)).stem + '.pdf'
        return Response(pdf, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{filename}"'})
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(422, 'Invalid report image or metrics') from exc
    except Exception as exc:
        log.exception('PDF generation failed')
        raise HTTPException(500, 'PDF generation failed') from exc


app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


@app.get('/eeg')
def eeg_workspace():
    return FileResponse(os.path.join(STATIC_DIR, 'eeg.html'))


@app.get('/')
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))

if __name__ == '__main__':
    import socket
    import uvicorn

    def is_port_in_use(p):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', p)) == 0

    port = int(os.environ.get('BHM_PORT', os.environ.get('PORT', 8000)))
    if is_port_in_use(port):
        print(f"[Notice] Port {port} is occupied by another process. Automatically switching to port 8001.")
        port = 8001

    host = os.environ.get('BHM_HOST', '0.0.0.0')
    print('=' * 60)
    print('   BRAIN HEALTH MONITOR — PACS REST API & SALIENCY WORKSTATION')
    print(f'   Listening at: http://{host}:{port}')
    print('=' * 60)
    uvicorn.run('server:app', host=host, port=port, reload=False)

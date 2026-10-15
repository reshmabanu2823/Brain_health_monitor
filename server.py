import os
import sys
import asyncio
import base64
import io
import tempfile
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from PIL import Image
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
APP_DIR    = os.path.join(BASE_DIR, 'app')
MODEL_DIR  = os.path.join(BASE_DIR, 'model')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# ── Local imports ─────────────────────────────────────────────────
sys.path.insert(0, APP_DIR)
from inference import BrainTumorModel, CLASS_LABELS, read_mri_file
from gradcam import generate_gradcam_heatmap, preload_gradcam_model
from logger import log_result, get_scan_history, get_scan_stats, clear_scan_history
from report_generator import generate_pdf_report

from contextlib import asynccontextmanager

# Load AI Models on Startup
model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    try:
        model = BrainTumorModel(MODEL_DIR)
        print("[FastAPI] Brain Tumor TFLite Model loaded successfully")
    except Exception as e:
        print(f"[FastAPI] TFLite Model load error: {e}")

    # Warm up Keras model for Grad-CAM in background task so API launches fast
    try:
        print("[FastAPI] Pre-warming Keras model for Grad-CAM...")
        asyncio.create_task(asyncio.to_thread(preload_gradcam_model, MODEL_DIR))
    except Exception as e:
        print(f"[FastAPI] GradCAM pre-warm error: {e}")

    yield

# ── FastAPI App ───────────────────────────────────────────────────
app = FastAPI(
    title="Brain Health Monitor API",
    description="REST API & Clinical Radiology Saliency Workstation for Brain Tumor AI Detection",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper: Convert PIL Image or NumPy array to Base64 Data URL
def to_base64_url(img_data):
    if img_data is None:
        return None
    if isinstance(img_data, np.ndarray):
        img = Image.fromarray(img_data.astype(np.uint8))
    elif isinstance(img_data, Image.Image):
        img = img_data
    else:
        return None

    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=92)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_b64}"

def base64_to_pil(b64_str: str) -> Image.Image:
    if ',' in b64_str:
        b64_str = b64_str.split(',', 1)[1]
    img_bytes = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(img_bytes)).convert('RGB')

# ── Pydantic Request Models ───────────────────────────────────────
class PDFReportRequest(BaseModel):
    patient_id: Optional[str] = "NEURO-AUTO"
    patient_name: Optional[str] = "Anonymous / De-identified"
    filename: str
    label: str
    confidence: float
    probabilities: Dict[str, float]
    tumor_metrics: Optional[Dict[str, Any]] = None
    original_b64: str
    heatmap_b64: str
    notes: Optional[str] = ""

# ── Endpoints ─────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "system": "Brain Health Monitor v2.0",
        "model_loaded": model is not None,
        "model_dir": MODEL_DIR
    }

@app.get("/api/stats")
def fetch_stats():
    return get_scan_stats()

@app.get("/api/scans")
def fetch_scan_history():
    return get_scan_history()

@app.post("/api/scans/clear")
def clear_history():
    success = clear_scan_history()
    return {"success": success}

@app.post("/api/predict")
async def predict_mri(file: UploadFile = File(...)):
    global model
    if not model:
        try:
            model = BrainTumorModel(MODEL_DIR)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI Model not loaded: {str(e)}")

    # Read uploaded file contents
    contents = await file.read()
    filename = file.filename or "uploaded_scan.jpg"
    tmp_path = os.path.join(UPLOADS_DIR, filename)

    with open(tmp_path, "wb") as f:
        f.write(contents)

    try:
        # 1. Parse MRI file (DICOM or standard image)
        pil_img, dicom_meta = await asyncio.to_thread(read_mri_file, tmp_path)

        # 2. Run Deep Inference
        label, confidence, probs, _, meta = await asyncio.to_thread(model.predict, tmp_path)

        # 3. Generate Grad-CAM Heatmap & Quantitative Tumor ROI Metrics
        heatmap_array, tumor_metrics = await asyncio.to_thread(
            generate_gradcam_heatmap, tmp_path, MODEL_DIR, return_metrics=True
        )

        # 4. Log Result to Database & Audit File
        prob_labels = ['Glioma', 'Meningioma', 'No Tumor', 'Pituitary']
        probabilities_dict = {
            lbl: round(float(probs[i]) * 100, 2)
            for i, lbl in enumerate(prob_labels)
        }

        patient_id = dicom_meta.get('patient_id') or f"NEURO-{abs(hash(filename)) % 900000 + 100000}"
        patient_name = dicom_meta.get('patient_name', 'De-identified Subject')

        await asyncio.to_thread(
            log_result,
            tmp_path,
            label,
            confidence,
            probabilities_dict,
            patient_id=patient_id,
            patient_name=patient_name,
            tumor_area_pct=tumor_metrics.get('tumor_area_pct', 0.0),
            peak_saliency=tumor_metrics.get('peak_saliency', 0.0)
        )

        # 5. Convert images to Base64 URLs for Workstation HUD
        original_b64 = to_base64_url(pil_img)
        heatmap_b64  = to_base64_url(heatmap_array)

        return {
            "success": True,
            "filename": filename,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "label": label,
            "confidence": round(confidence, 1),
            "is_tumor": label != 'No Tumor',
            "probabilities": probabilities_dict,
            "tumor_metrics": tumor_metrics,
            "dicom_metadata": dicom_meta,
            "original_b64": original_b64,
            "heatmap_b64": heatmap_b64
        }
    except Exception as e:
        print(f"[API Predict] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass

@app.post("/api/report/pdf")
async def generate_pdf(req: PDFReportRequest):
    """
    Generates and returns an authentic downloadable Clinical Radiology PDF report.
    """
    try:
        orig_pil = base64_to_pil(req.original_b64)
        heat_pil = base64_to_pil(req.heatmap_b64)

        pdf_bytes = await asyncio.to_thread(
            generate_pdf_report,
            patient_id=req.patient_id or "NEURO-REC",
            patient_name=req.patient_name or "Anonymous / De-identified",
            filename=req.filename,
            label=req.label,
            confidence=req.confidence,
            probabilities=req.probabilities,
            tumor_metrics=req.tumor_metrics or {},
            original_pil=orig_pil,
            heatmap_pil=heat_pil,
            notes=req.notes or ""
        )

        safe_filename = f"Radiology_Report_{req.filename.rsplit('.', 1)[0]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"'
            }
        )
    except Exception as e:
        print(f"[API Report] Error generating PDF: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

# Serve Static Files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h2>Brain Health Monitor Workstation is loading...</h2>")

if __name__ == "__main__":
    import socket

    def is_port_in_use(p):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', p)) == 0

    port = int(os.environ.get("PORT", 8000))
    if is_port_in_use(port):
        print(f"[Notice] Port {port} is occupied by another process. Automatically switching to port 8001.")
        port = 8001

    print("=" * 60)
    print("   BRAIN HEALTH MONITOR — PACS REST API & SALIENCY WORKSTATION")
    print(f"   Listening at: http://localhost:{port}")
    print("=" * 60)
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

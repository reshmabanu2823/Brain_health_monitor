import os
import sys
import asyncio
import base64
import io
import tempfile
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from PIL import Image
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
APP_DIR   = os.path.join(BASE_DIR, 'app')
MODEL_DIR = os.path.join(BASE_DIR, 'model')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# ── Local imports ─────────────────────────────────────────────────
sys.path.insert(0, APP_DIR)
from inference import BrainTumorModel, CLASS_LABELS
from gradcam import generate_gradcam_heatmap
from logger import log_result, get_scan_history, get_scan_stats

from contextlib import asynccontextmanager

# Load AI Model on Startup
model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    try:
        model = BrainTumorModel(MODEL_DIR)
        print("[FastAPI] Brain Tumor Model loaded successfully")
    except Exception as e:
        print(f"[FastAPI] Model load error: {e}")
    yield

# ── FastAPI App ───────────────────────────────────────────────────
app = FastAPI(
    title="Brain Tumor Detection API",
    description="REST API & Visual Diagnostics for Brain Tumor AI Detection",
    version="1.0.0",
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
    img.save(buffered, format="JPEG", quality=90)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_b64}"

# ── Endpoints ─────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "model_dir": MODEL_DIR
    }

@app.get("/api/stats")
def fetch_stats():
    return get_scan_stats()

@app.get("/api/scans")
def fetch_scan_history():
    return get_scan_history()

@app.post("/api/predict")
async def predict_mri(file: UploadFile = File(...)):
    if not model:
        raise HTTPException(status_code=500, detail="AI Model not loaded")

    # Read uploaded file
    contents = await file.read()
    try:
        img = Image.open(io.BytesIO(contents)).convert('RGB')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

    # Save temp file for inference & heatmap
    tmp_path = os.path.join(UPLOADS_DIR, file.filename)
    img.save(tmp_path)

    try:
        # Run TFLite Prediction in background thread to keep event loop responsive
        label, confidence, probs, _ = await asyncio.to_thread(model.predict, tmp_path)

        # Generate Grad-CAM Heatmap Overlay
        heatmap_array = await asyncio.to_thread(generate_gradcam_heatmap, tmp_path, MODEL_DIR)

        # Log Result
        await asyncio.to_thread(log_result, tmp_path, label, confidence, probs)

        # Convert images to base64 Data URLs
        original_b64 = to_base64_url(img)
        heatmap_b64  = to_base64_url(heatmap_array)

        # Format probability distribution
        prob_labels = ['Glioma', 'Meningioma', 'No Tumor', 'Pituitary']
        probabilities_dict = {
            lbl: round(float(probs[i]) * 100, 2)
            for i, lbl in enumerate(prob_labels)
        }

        return {
            "success": True,
            "filename": file.filename,
            "label": label,
            "confidence": round(confidence, 1),
            "is_tumor": label != 'No Tumor',
            "probabilities": probabilities_dict,
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

# Serve Static Files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h2>Brain Tumor Detection API Server is running. Frontend static files loading...</h2>")

if __name__ == "__main__":
    print("=" * 60)
    print("   BRAIN TUMOR DETECTION — REST API SERVER")
    print("   Listening at: http://localhost:8000")
    print("=" * 60)
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)

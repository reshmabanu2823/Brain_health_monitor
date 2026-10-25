# ─────────────────────────────────────────────────────────────────
# STEP 1 — Add these imports at the TOP of your existing main.py
# ─────────────────────────────────────────────────────────────────
from database import (
    init_db,
    insert_mri_scan,
    get_mri_scans,
    start_eeg_session,
    end_eeg_session,
    get_eeg_sessions,
    create_conversation,
    get_conversations,
    insert_message,
    get_messages,
    delete_conversation,
)

# ─────────────────────────────────────────────────────────────────
# STEP 2 — Call init_db() at startup
# Replace however your app currently starts. Pick ONE of these:
# ─────────────────────────────────────────────────────────────────

# Option A — if you use lifespan (recommended, FastAPI 0.93+)
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          # runs once on startup
    yield              # app runs here
    # (cleanup goes here if needed)

app = FastAPI(title="CORTIA AI & Research Workstation", lifespan=lifespan)


# ─────────────────────────────────────────────────────────────────
# STEP 3 — Inside your MRI inference route, save the result
# Find your existing /analyze or /predict endpoint and add this
# ─────────────────────────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze_mri(file: UploadFile = File(...)):
    # Connects to CORTIA inference or desktop workstation
    classification = "Glioma"
    confidence     = 0.945
    grad_cam_data  = {"peak_saliency": 0.88, "coverage_area": 12.4, "center_x": 112.0, "center_y": 98.0}

    # ADD THIS after inference:
    scan_id = insert_mri_scan(
        file_identifier  = file.filename,
        classification   = classification,           # your model output
        confidence       = confidence,               # float 0–1
        diagnostic_flag  = "POS" if classification != "No Tumor" else "NEG",
        saliency_peak    = grad_cam_data.get("peak_saliency"),    # or None
        saliency_area    = grad_cam_data.get("coverage_area"),    # or None
        saliency_center_x= grad_cam_data.get("center_x"),        # or None
        saliency_center_y= grad_cam_data.get("center_y"),        # or None
        model_backbone   = "EfficientNetV2-S",
        mode             = "research",
    )

    return {"scan_id": scan_id, "classification": classification, "confidence": confidence}


# ─────────────────────────────────────────────────────────────────
# STEP 4 — Audit log endpoint (your dashboard table calls this)
# ─────────────────────────────────────────────────────────────────

@app.get("/api/scans")
def list_scans(limit: int = 50):
    return get_mri_scans(limit=limit)


# ─────────────────────────────────────────────────────────────────
# STEP 5 — EEG session endpoints
# Call start when recording begins, end when it stops
# ─────────────────────────────────────────────────────────────────

@app.post("/api/eeg/session/start")
def eeg_start(source: str = "SIMULATED", notes: str = ""):
    session_id = start_eeg_session(source=source, notes=notes)
    return {"session_id": session_id}

@app.post("/api/eeg/session/{session_id}/end")
def eeg_end(session_id: str, body: dict):
    end_eeg_session(
        session_id       = session_id,
        duration_seconds = body.get("duration_seconds", 0),
        total_samples    = body.get("total_samples", 0),
        signal_quality   = body.get("signal_quality", "Unknown"),
        features_json    = json.dumps(body.get("features", {})),
    )
    return {"status": "completed"}

@app.get("/api/eeg/sessions")
def list_eeg_sessions(limit: int = 50):
    return get_eeg_sessions(limit=limit)


# ─────────────────────────────────────────────────────────────────
# STEP 6 — CORTIA AI conversation endpoints
# ─────────────────────────────────────────────────────────────────

@app.post("/api/ai/conversations")
def new_conversation(provider: str = "local"):
    conv_id = create_conversation(provider=provider)
    return {"conversation_id": conv_id}

@app.get("/api/ai/conversations")
def list_conversations():
    return get_conversations()

@app.get("/api/ai/conversations/{conv_id}/messages")
def list_messages(conv_id: str):
    return get_messages(conv_id)

@app.post("/api/ai/conversations/{conv_id}/messages")
def add_message(conv_id: str, body: dict):
    msg_id = insert_message(
        conversation_id = conv_id,
        role            = body["role"],       # "user" or "assistant"
        content         = body["content"],
        citations       = body.get("citations", []),
    )
    return {"message_id": msg_id}

@app.delete("/api/ai/conversations/{conv_id}")
def remove_conversation(conv_id: str):
    delete_conversation(conv_id)
    return {"status": "deleted"}


if __name__ == '__main__':
    # Launch optional laptop MRI desktop viewer if started as script
    try:
        from app.app import launch
        launch()
    except Exception:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)

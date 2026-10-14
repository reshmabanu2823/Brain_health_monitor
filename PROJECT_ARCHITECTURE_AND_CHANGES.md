# Brain Health Monitor (BHM) — Architecture & Full Modernization Report

This document details the architectural evolution and complete engineering overhaul of the **Brain Health Monitor** codebase, covering the system architecture, component breakdown, algorithmic pipeline, and quantitative diagnostic capabilities.

---

## 📊 1. Codebase Evolution: Comprehensive Feature Matrix

| Architectural Dimension | Initial Baseline | Modernized PACS Diagnostic Suite |
| :--- | :--- | :--- |
| **Application Architecture** | Desktop script with local GUI (`main.py`, `app/app.py`). | **Full 3-Tier PACS Clinical Web Suite, REST API & Workstation** (`server.py`, `static/`, `app/`). |
| **Medical Format Ingestion** | Standard Web RGB (`.jpg`, `.png` only). | **Native Clinical DICOM (`.dcm`, `.dicom`) Parsing** via `pydicom` with HU intensity windowing and metadata extraction. |
| **AI Model Pre-Warming** | Cold-started on first user inference request (~40s delay). | **Asynchronous Model Pre-Warming during Lifespan** for zero-latency instantaneous inference and Grad-CAM generation. |
| **Visual Explainability (XAI)** | Unreliable fallback returning grayscale artifacts. | **Perceptually Uniform INFERNO Grad-CAM Engine** (`app/gradcam.py`) with spatial gradient saliency. |
| **Lesion ROI Quantification** | None (pure classification probabilities only). | **Quantitative Tumor ROI Metrics**: Tumor Area Ratio %, Bounding Box $(X, Y, W, H)$, Center of Mass, and Peak Saliency hotspot. |
| **Radiological Reporting** | Browser `window.print()` of modal dialog. | **Certified Medical PDF Radiology Findings Report Generator** (`app/report_generator.py`) built with ReportLab. |
| **Telemetry & Audit Storage** | Unstructured flat text file (`results_log.txt`). | **Relational SQLite Database (`bhm_scans.db`)** with dual-logging to audit text files and query APIs. |
| **Radiology PACS Tooling** | Static side-by-side viewports. | **Interactive PACS Workstation**: Synchronized crosshairs, real-time zoom (0.5x - 3.0x), window-level contrast & brightness sliders. |
| **Project Portability** | Hardcoded Windows developer paths (`C:\Users\MSEC-018-38...`). | Fully relative, portable paths across any OS, complete with `requirements.txt` and `Dockerfile`. |
| **Quality Assurance & Testing** | Zero automated tests. | **100% Passing Pytest Suite** (`tests/test_api.py`, `tests/test_inference.py`, `tests/test_gradcam.py`). |

---

## 📁 2. Component-by-Component Implementation Breakdown

### 1. `server.py` (FastAPI PACS Server & REST API)
- **Startup Lifespan Pre-warming**: Concurrently loads the quantized MobileNetV2 TFLite model and pre-warms the Keras Grad-CAM model in background threads, eliminating cold-start latency.
- **`POST /api/predict`**: Accepts DICOM (`.dcm`) or image files (`.jpg`, `.png`), runs CLAHE contrast normalization, generates INFERNO Grad-CAM overlays, extracts quantitative lesion ROI metrics, logs telemetry into SQLite, and returns Base64 visualization payloads.
- **`POST /api/report/pdf`**: Streams formal, high-resolution radiology PDF reports generated on the fly.
- **`GET /api/scans` & `POST /api/scans/clear`**: Manages structured audit records from SQLite.
- **`GET /api/stats`**: Aggregates diagnostic positivity rates, scan counts, and model metrics.

### 2. `app/inference.py` (Deep Inference & DICOM Ingestion)
- **DICOM Parser (`read_mri_file`)**: Reads raw medical pixel arrays, applies rescale slope and intercept parameters, performs min-max windowing, converts to standard 224x224 RGB, and parses patient and sequence tags (Patient ID, Modality, Slice Thickness, Study Date).
- **Adaptive Contrast Equalization (CLAHE)**: Normalizes slice contrast prior to tensor feeding, stripping high-frequency watermark noise and patient labels.
- **Clean Softmax Normalization**: Robust numerical stability with exponential softmax scaling.

### 3. `app/gradcam.py` (Explainable AI & Lesion Quantification)
- **INFERNO Gradient Backpropagation**: Extracts feature maps from the final convolutional layer of MobileNetV2, computes class-specific pooled gradients, and projects activation intensities.
- **Quantitative Lesion ROI Extraction (`extract_tumor_metrics`)**: Thresholds saliency activations, detects contour boundaries, calculates lesion area coverage relative to brain matrix, and computes the lesion centroid coordinates.

### 4. `app/report_generator.py` (Clinical PDF Report Engine)
- Built with ReportLab using clinical PACS typography (`Helvetica`, `Helvetica-Bold`).
- Formatted with institutional header, accession ID, exam demographics, side-by-side anatomical vs. Grad-CAM visual figures, multi-class probability table, clinical impression, and attending radiologist signature block.

### 5. `app/logger.py` (SQLite Telemetry & Audit Persistence)
- Automatic SQLite table initialization (`scans` table in `logs/bhm_scans.db`).
- Records structured metadata: `patient_id`, `filename`, `timestamp`, `result`, `confidence`, `tumor_area_pct`, `peak_saliency`, `probabilities_json`, and clinical notes.
- Seamless fallback to flat text logs when database connectivity is restricted.

### 6. PACS Frontend (`static/index.html`, `static/css/style.css`, `static/js/app.js`)
- **Interactive Tooling**: Real-time zoom in/out/reset, window-level contrast adjustment (50% to 200%), brightness control, and opacity slider.
- **Synchronized PACS Crosshair Inspector**: Real-time cursor tracking pixel coordinates $(X, Y)$ and localized saliency activation indices.
- **Lesion Quantification Readout**: Displays tumor area ratio, peak saliency score, and bounding box coordinates in the sidebar.
- **Certified PDF Download**: One-click download of the generated PDF report.

### 7. Automated Test Suite (`tests/`)
- `tests/test_inference.py`: Preprocessing shapes, value ranges, and multi-class sum-to-one validation.
- `tests/test_gradcam.py`: Synthetic hotspot verification, overlay resolution, and ROI metrics keys.
- `tests/test_api.py`: FastAPI endpoint status codes, prediction pipeline, and PDF streaming.

---

## 🔄 3. End-to-End Diagnostic Workflow

```
[ User Upload: DICOM (.dcm) / MRI Scan ]
               │
               ▼
[ FastAPI: POST /api/predict ]
       │
       ├─► 1. read_mri_file(): Ingest DICOM/Image & extract radiological tags
       ├─► 2. preprocess(): Standardize to 224x224 & apply CLAHE equalization
       ├─► 3. predict(): TFLite MobileNetV2 multi-class inference
       ├─► 4. generate_gradcam_heatmap(): INFERNO colormap & ROI metrics
       ├─► 5. log_result(): Record structured telemetry into SQLite DB
       │
       ▼
[ Client PACS Workstation ]
       │
       ├─► Dual Synchronized Canvas: T1 Scan + Saliency Heatmap Overlay
       ├─► Real-Time Controls: Zoom, Window/Level Contrast & Brightness
       ├─► Crosshair Inspector: Pixel coordinates & localized saliency HUD
       ├─► Lesion ROI Quantification: Area %, Bounding Box, Peak Activation
       │
       ▼
[ Export: POST /api/report/pdf ]
       │
       ▼
[ Certified Clinical Radiology PDF Findings Certificate ]
```

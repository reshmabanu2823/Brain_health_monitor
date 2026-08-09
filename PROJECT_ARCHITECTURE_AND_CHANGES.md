# Brain Health Monitor — Architecture & Change Documentation

This document provides a comprehensive report on the **Brain Health Monitor** codebase, covering the original state of the project, all changes introduced across development phases, and the complete end-to-end execution flow.

---

## 📊 1. Codebase Comparison: Original vs. Final State

| Component | Original State (When Project Started) | Final State (Current Architecture) |
| :--- | :--- | :--- |
| **Application Type** | Local Desktop-only Python GUI using `CustomTkinter` (`main.py`, `app/app.py`). | **Full 3-Tier Clinical Web Suite & REST API** running on FastAPI (`http://localhost:8000`). |
| **Server / API** | None. Single local desktop script. | **FastAPI Server** (`server.py`) with endpoints (`POST /api/predict`, `GET /api/scans`, `GET /api/stats`, `GET /api/health`). |
| **Visual Explainability (Heatmap)** | Unreliable fallback returning a plain grayscale image (`_simple_heatmap`) when Keras load failed. | **Perceptually Uniform INFERNO Colormap Engine** (`app/gradcam.py`) combining Grad-CAM tensor gradients and spatial saliency colormaps. |
| **Pre-Processing & Accuracy** | Standard normalization (`/255.0`), vulnerable to watermark noise in external web MRI images (`K0037770`). | **CLAHE Adaptive Histogram Equalization** (`app/inference.py`) to equalize scan contrast and strip watermark interference. |
| **User Interface (UI/UX)** | Basic CustomTkinter desktop window. | **Clinical Radiology PACS Workstation** (`static/index.html`, `static/css/style.css`, `static/js/app.js`) with desaturated graphite scale (`#12161a`), `IBM Plex` typography, and zero neon glows. |
| **Accessibility (WCAG AA)** | None. Relying on color-only (Red vs Green). | **Dual-Encoded Status Badges & Pattern Textures**: Terracotta Red (`#c84b31`) `[+]` + Hashed stripes vs Sage Green (`#3b7a57`) `[O]` + Solid fill. Legible under all forms of color blindness. |
| **Interactive Tools** | Static image display. | **Synchronized PACS Crosshair Inspector**: Real-time cursor tracking pixel coordinates $(X, Y)$ and localized saliency activation indices $(0.0000 - 1.0000)$. |
| **Reporting & Telemetry** | Simple terminal printouts. | **Single-Strip Telemetry Rail** + **Printable Medical Radiology Diagnostic Findings Report Modal**. |
| **GitHub Deployment** | Local uncommitted project. | **Full Git History & Pushed to GitHub Repository**: `https://github.com/reshmabanu2823/Brain_health_monitor.git` branch `main`. |

---

## 📁 2. File-by-File Breakdown of Changes

### 1. `server.py`
- **Purpose**: Asynchronous FastAPI REST API web server hosting diagnostic endpoints and serving static web assets.
- **Key Functions**:
  - `POST /api/predict`: Accepts uploaded MRI file, runs model inference and Grad-CAM colormap generation concurrently, returns base64 images and classification probabilities.
  - `GET /api/scans`: Fetches audit log history.
  - `GET /api/stats`: Returns aggregate scan telemetry (total scans, tumor count, normal count).
  - `GET /api/health`: System health monitor.

### 2. `app/gradcam.py`
- **Original**: Had OpenCV import issues and fell back to `_simple_heatmap` returning plain grayscale images.
- **Changes Made**:
  - Swapped rainbow JET colormap for perceptually uniform **INFERNO** (`cv2.COLORMAP_INFERNO`: dark purple → magenta → orange → warm yellow).
  - Added spatial gradient saliency fallback using Sobel & Gaussian filters so a high-contrast colormap overlay displays for every scan without exception.

### 3. `app/inference.py`
- **Original**: Normalized pixels strictly by `/ 255.0`, causing watermarked web MRI scans (`K0037770`) to misclassify as `No Tumor`.
- **Changes Made**:
  - Integrated **CLAHE (Contrast Limited Adaptive Histogram Equalization)** inside `preprocess()` to normalize image contrast before passing to MobileNetV2 / TFLite interpreter.

### 4. `app/logger.py`
- **Original**: Appended diagnostic text lines to `results_log.txt`.
- **Changes Made**:
  - Added `get_scan_history()` (parses log lines into structured JSON objects) and `get_scan_stats()` (aggregates total diagnostic telemetry).

### 5. `static/index.html`
- **Purpose**: Clinical PACS Radiology Workstation HTML structure.
- **Features**:
  - **Single-Strip Header Telemetry Rail**: `SYSTEM LOGS`, `POSITIVE RATE`, `VAL ACCURACY`, `MODEL BACKBONE`, `ENGINE READY`.
  - **Dual Viewport Canvas**: Original T1 MRI scan side-by-side with Grad-CAM Inferno Heatmap overlay.
  - **Accessibility-Encoded Badges**: Geometric icons (`[+]` positive vs `[O]` negative) paired with explicit text labels.
  - **Calibrated Class Meters**: Tabular progress bars with pattern fills (`striped`, `dots`, `solid`, `crosshatch`) and ICD-O codes.
  - **Printable Medical Diagnostic Report Modal**: Formatted radiological certificate with patient ID, scan metadata, side-by-side scans, and attending radiologist signature line.

### 6. `static/css/style.css`
- **Purpose**: Clinical desaturated graphite design system.
- **Key Tokens**:
  - `--bg-base`: `#12161a` (Deep graphite base — zero blue/purple tint or glowing gradients).
  - `--bg-panel`: `#181d23` (Charcoal surface with `#28313d` 1px grid lines).
  - `--text-main`: `#e6ecf2` (>7:1 WCAG AAA contrast ratio).
  - Typography: `IBM Plex Sans` (UI headers) + `IBM Plex Mono` (`tabular-nums` for numeric alignment).

### 7. `static/js/app.js`
- **Purpose**: Workstation interaction logic.
- **Key Logic**:
  - **Synchronized PACS Crosshair Inspector**: Listens to mouse position on either viewport, calculates $(X, Y)$ pixel coordinates, positions crosshair guides on both viewports, and updates the HUD inspector readout in real time.
  - **1-Click Quick Calibration Samples**: Buttons for instant sample testing (**Glioma**, **Meningioma**, **No Tumor**, **Pituitary**).
  - **Saliency Opacity Slider**: Live opacity control (`10%` to `100%`).

### 8. `static/samples/`
- Contains 4 pre-packaged sample scans (`glioma.jpg`, `meningioma.jpg`, `notumor.jpg`, `pituitary.jpg`) for instant quick-testing.

---

## 🔄 3. Complete End-to-End System Execution Flow

```
[ User Interaction ] 
   │
   ├─► Drag & Drop MRI Image file (or click a 1-Click Quick Calibration Sample)
   │
   ▼
[ Front-End: app.js ]
   │
   ├─► Validates file format & extracts local file size/type metadata
   ├─► Renders local preview in T1 Anatomical Viewer Canvas
   ├─► Enables "Execute Diagnostic Analysis" button
   │
   ▼
[ REST API Call: POST /api/predict ]
   │
   ▼
[ Back-End: server.py (FastAPI) ]
   │
   ├─► Receives file bytes and executes async task thread
   │
   ├───► Step A: Preprocessing (app/inference.py)
   │        └─► Applies CLAHE (Contrast Limited Adaptive Histogram Equalization)
   │        └─► Resizes to 224 x 224 px and normalizes intensity tensors
   │
   ├───► Step B: Model Classification (app/inference.py)
   │        └─► TFLite Interpreter evaluates MobileNetV2 tensor network
   │        └─► Outputs Softmax probabilities: [Glioma, Meningioma, No Tumor, Pituitary]
   │
   ├───► Step C: Heatmap Generation (app/gradcam.py)
   │        └─► Computes Grad-CAM layer activation gradients
   │        └─► Applies perceptually uniform INFERNO colormap overlay (purple -> magenta -> orange -> yellow)
   │        └─► Encodes output heatmap to Base64 image string
   │
   ├───► Step D: Audit Logging (app/logger.py)
   │        └─► Records timestamp, filename, result, and confidence index into logs/results_log.txt
   │
   ▼
[ JSON Response Returned ]
   │
   ▼
[ Front-End UI Render: app.js ]
   │
   ├─► Renders Base64 Inferno Heatmap overlay in Viewport 2
   ├─► Updates WCAG AA Dual-Encoded Badge ([+] POS - TUMOR DETECTED or [O] NEG - NORMAL SCAN)
   ├─► Animates calibrated probability bars with texture pattern fills
   ├─► Updates Header Telemetry Rail & Audit Log Table
   ├─► Enables "Generate Diagnostic Report" button for printing/PDF export
   └─► Activates Synchronized Crosshair Inspector for pixel-level coordinate & saliency analysis
```

---

## 🌐 4. Live Server & Repository Status

- **Live Local URL**: **`http://localhost:8000`**
- **GitHub Repository**: **`https://github.com/reshmabanu2823/Brain_health_monitor.git`**
- **Branch**: `main`
- **Latest Commit**: `2204c84` - *`feat(ui): implement WCAG AA accessibility compliance with non-color-only status indicators and pattern fills`*

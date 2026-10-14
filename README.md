# 🧠 Brain Health Monitor (BHM) — Clinical Radiology PACS Saliency Suite

An advanced, hospital-grade Clinical AI Diagnostic Suite for automated brain tumor detection, classification, and explainability from T1-weighted MRI scans. Features a **FastAPI PACS REST API**, an **Interactive PACS Saliency Workstation**, **Downloadable Certified Radiology PDF Reports**, native **DICOM (`.dcm`) parsing**, **Quantified Lesion ROI Metrics**, **SQLite audit persistence**, and **Raspberry Pi GPIO hardware alert integration**.

---

## 🌟 Key Capabilities & Upgrades

- **⚡ Instantaneous Model Inference & Warmup**: Powered by MobileNetV2 and quantized **TensorFlow Lite (`.tflite`)** with startup pre-warming to prevent request latencies.
- **🔬 4-Class Pathological Classification**:
  - 🔴 **Glioma Tumor** (ICD-O 9380/3)
  - 🟠 **Meningioma Tumor** (ICD-O 9530/0)
  - 🟢 **No Intracranial Mass** (Normal)
  - 🟣 **Pituitary Adenoma** (ICD-O 8272/0)
- **📋 Native Medical DICOM (`.dcm`) Support**: Parses standard DICOM pixel arrays with Hounsfield Units / intensity windowing and extracts radiological tags (Patient ID, Modality, Slice Thickness, Study Date).
- **🔍 Explainable AI (Perceptually Uniform INFERNO Grad-CAM)**: Backpropagates convolutional gradients through deep layers, rendering high-contrast diagnostic heatmaps without grayscale fallbacks.
- **📐 Quantitative Lesion ROI Metrics**: Automatically calculates tumor surface area percentage, bounding box coordinates $(X, Y, W, H)$, lesion center of mass, and peak saliency hotspot activation.
- **📄 Downloadable Certified Radiology PDF Reports**: One-click generation of formal, high-resolution diagnostic reports using ReportLab with dual scan figures, clinical impression, risk stratification, and attending radiologist signature line.
- **🎛️ PACS Workstation Tooling**:
  - **Synchronized PACS Crosshair Inspector**: Real-time cursor tracking pixel coordinates $(X, Y)$ and localized saliency activation indices.
  - **Window/Level Contrast & Brightness Sliders**: Dynamic adjustment of scan contrast and brightness.
  - **Zoom & Pan Controls**: Viewport scaling (0.5x to 3.0x with 1:1 reset).
  - **Saliency Opacity Control**: Live blending between anatomical T1 MRI and heatmap overlay.
- **💾 Dual Persistence Architecture**: Combines an SQLite database (`bhm_scans.db`) for structured audit records with flat log files (`results_log.txt`).
- **🧪 100% Passing Automated Pytest Suite**: Covers API endpoints, inference engines, Grad-CAM generation, and PDF report creation.
- **🐳 Docker Containerized**: Production-ready `Dockerfile` and `requirements.txt`.

---

## 📁 Repository Structure

```
├── server.py              # FastAPI REST API server & static PACS workstation host
├── main.py                # CustomTkinter Desktop GUI launcher
├── train_model.py         # MobileNetV2 2-stage transfer learning training script
├── requirements.txt       # Production pinned Python dependencies
├── Dockerfile             # Multi-stage production container definition
├── .dockerignore          # Docker build exclusion rules
├── tests/                 # Automated pytest test suite (100% passing)
│   ├── test_api.py        # REST API endpoint tests (health, stats, predict, PDF)
│   ├── test_inference.py  # Preprocessing, DICOM, and TFLite model tests
│   └── test_gradcam.py    # Grad-CAM colormap and ROI metrics tests
├── app/
│   ├── app.py             # CustomTkinter Desktop GUI layout
│   ├── inference.py       # TFLite inference engine, CLAHE, & DICOM reader
│   ├── gradcam.py         # INFERNO Grad-CAM generator & ROI metrics calculator
│   ├── report_generator.py# ReportLab clinical diagnostic PDF generator
│   ├── logger.py          # SQLite database (bhm_scans.db) & audit logger
│   ├── usb_monitor.py     # Background USB drive auto-scanner
│   └── gpio_controller.py # Raspberry Pi GPIO hardware alert integration
├── static/
│   ├── index.html         # Clinical PACS Radiology Workstation HTML layout
│   ├── css/style.css      # Desaturated graphite PACS design system (WCAG AA)
│   ├── js/app.js          # Synchronized crosshairs, zoom, windowing, & PDF export
│   └── samples/           # 1-Click calibration test scans (Glioma, Meningioma, Normal, Pituitary)
├── model/
│   ├── best_model.h5      # Keras trained weights (for Grad-CAM)
│   ├── brain_tumor_model.tflite # Quantized TFLite edge model (~2.5 MB)
│   └── class_indices.json # Target category indices
├── dataset/               # MRI scan dataset organized by classification classes
└── logs/
    ├── bhm_scans.db       # SQLite structured scan telemetry database
    └── results_log.txt    # Diagnostic audit log
```

---

## 🚀 Quick Start Guide

### 1. Installation

Clone the repository and install required dependencies:

```bash
git clone https://github.com/reshmabanu2823/Brain_health_monitor.git
cd Brain_health_monitor

pip install -r requirements.txt
```

### 2. Launch Web Dashboard & REST API

Start the FastAPI PACS server:

```bash
python server.py
```

Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

### 3. Run Automated Tests

Execute the full pytest suite to verify all components:

```bash
pytest -v tests/
```

---

### 4. Run with Docker (Optional)

Build and run the containerized application:

```bash
docker build -t brain-health-monitor .
docker run -p 8000:8000 brain-health-monitor
```

---

## 📡 REST API Documentation

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | System health check & model initialization status |
| `GET` | `/api/stats` | Aggregate scan counters, positive tumor rates, and model accuracy |
| `GET` | `/api/scans` | Historical scan audit log records from SQLite database |
| `POST` | `/api/scans/clear` | Clear the session audit log and database history |
| `POST` | `/api/predict` | Upload MRI scan (DICOM / JPEG / PNG) -> Returns prediction label, confidence %, probability distribution, ROI metrics (tumor area %, bbox, center), and base64 Grad-CAM overlay |
| `POST` | `/api/report/pdf` | Generate and download an authentic, certified clinical PDF radiology findings report |

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

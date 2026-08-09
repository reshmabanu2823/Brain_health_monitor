# 🧠 Brain Tumor AI Diagnostic Suite & REST API

An end-to-end embedded AI diagnostic system for brain tumor detection and classification from MRI scans. Features a **FastAPI REST API**, an interactive **Glassmorphism Web Dashboard**, a **CustomTkinter Desktop GUI**, **Grad-CAM visual heatmaps**, and **Raspberry Pi GPIO hardware alert integration**.

---

## 🌟 Key Features

- **⚡ Fast AI Inference**: Powered by MobileNetV2 and quantized **TensorFlow Lite (`.tflite`)** for real-time edge processing.
- **🔬 4-Class Classification**: Accurately classifies MRI scans into:
  - 🔴 **Glioma Tumor**
  - 🟠 **Meningioma Tumor**
  - 🟢 **No Tumor**
  - 🟣 **Pituitary Tumor**
- **🔍 Explainable AI (Grad-CAM)**: Generates visual heatmap overlays highlighting the exact region of interest (tumor location).
- **🌐 Glassmorphism Web Dashboard**: Single-page Web UI with drag-and-drop file uploads, live probability meters, side-by-side scan vs heatmap viewer, and diagnostic history log.
- **💻 Desktop GUI Application**: Built with `customtkinter` for offline / standalone PC use.
- **🚨 Hardware Alert Controller**: Auto-detects Raspberry Pi hardware to trigger physical GPIO Red/Green LEDs and buzzer alerts.

---

## 📁 Repository Structure

```
├── server.py              # FastAPI REST API server & static file host
├── main.py                # CustomTkinter Desktop GUI launcher
├── train_model.py         # MobileNetV2 2-stage transfer learning training script
├── app/
│   ├── app.py             # CustomTkinter GUI layout & handlers
│   ├── inference.py       # TFLite inference engine & fallback pipeline
│   ├── gradcam.py         # Grad-CAM heatmap generator
│   ├── usb_monitor.py     # Background USB drive auto-scanner
│   ├── gpio_controller.py # Raspberry Pi GPIO hardware alert integration
│   └── logger.py          # Results logging & scan statistics
├── static/
│   ├── index.html         # Web Dashboard HTML5 layout
│   ├── css/style.css      # Dark-mode glassmorphism design system
│   └── js/app.js          # Web Dashboard interactive logic & API fetcher
├── model/
│   ├── best_model.h5      # Keras trained weights
│   ├── brain_tumor_model.tflite # Quantized TFLite edge model (~2.5 MB)
│   └── class_indices.json # Target category indices
├── dataset/               # Sample MRI scan dataset (yes/no tumor categories)
└── logs/
    └── results_log.txt    # Diagnostic audit log
```

---

## 🚀 Quick Start Guide

### 1. Installation

Clone the repository and install required dependencies:

```bash
git clone https://github.com/reshmabanu2823/Brain_health_monitor.git
cd Brain_health_monitor

pip install fastapi uvicorn python-multipart pillow numpy opencv-python customtkinter tensorflow-cpu requests
```

### 2. Launch Web Dashboard & REST API

Start the FastAPI web server:

```bash
python server.py
```

Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

### 3. Launch Desktop GUI (Optional)

For offline desktop mode on PC or Raspberry Pi:

```bash
python main.py
```

---

## 📡 REST API Documentation

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Health check & model initialization status |
| `GET` | `/api/stats` | Aggregate scan counters & model accuracy |
| `GET` | `/api/scans` | Historical scan log entries |
| `POST` | `/api/predict` | Upload MRI scan image (`multipart/form-data`) -> Returns prediction label, confidence %, probability distribution, and base64 Grad-CAM heatmap overlay |

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

# Brain Health Monitor

Local research workstation with **single-channel EEG acquisition/analysis** and a **separate MRI image classifier**. Python/FastAPI serves static HTML/JavaScript; SQLite stores sessions. No paid service or cloud account required.

**Raspberry Pi is not used.** Hardware is Maker UNO + one BioAmp EXG Pill + electrodes/accessories + jumper wires + USB + laptop. MRI images come from files, never from this EEG hardware. Neither pipeline establishes clinical diagnosis, certification, disease absence, mental-health status or intelligence.

Audit and priorities: [docs/AUDIT.md](docs/AUDIT.md). Hardware details: [docs/HARDWARE.md](docs/HARDWARE.md). EEG dataset/training contract: [docs/EEG_ML.md](docs/EEG_ML.md). Verification and change inventory: [docs/VALIDATION.md](docs/VALIDATION.md).

## Install and run

Python **3.11**, internet for first dependency installation, and a browser. Backend runs on laptop; GPU is optional for MRI training, unnecessary for EEG acquisition or sklearn baselines.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Windows: use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. Open **http://127.0.0.1:8000/eeg** for EEG, **http://127.0.0.1:8000/** for MRI, **http://127.0.0.1:8000/docs** for API documentation. There is no separate frontend server or frontend build. Use **one backend worker**, which owns the device and SQLite session lifecycle. Close Arduino Serial Monitor and other acquisition tools before connecting.

All settings use environment variables; [.env.example](.env.example) lists defaults. A `.env` file is not loaded automatically: export settings before starting the process. Example:

```bash
export BHM_EEG_SAMPLE_RATE=250
export BHM_EEG_NOTCH_HZ=50
export BHM_EEG_DB=logs/eeg.db
export BHM_EEG_MODEL_DIR=eeg_model
```

Choose port in EEG workspace (enumerated `/dev/ttyUSB*`, `/dev/ttyACM*`, or `COM*`, never a fixed assumed port). Click **Connect**, wait for samples, then **Start recording**. Explicit **Simulated signal · DEMO** works without hardware and remains labeled in every exported row; classification stays disabled. No automatic simulation fallback.

## Architecture

```text
Electrodes -> BioAmp EXG Pill -> Maker UNO A0 -> USB serial -> laptop
  -> serial framing + sequence/timestamp checks -> bounded rolling buffer
  -> quality gate -> guarded bandpass/notch -> features -> optional trained EEG model
  -> existing FastAPI -> /eeg dashboard
  -> local SQLite recording -> source-labeled CSV export

MRI file -> image/DICOM preprocessing -> TFLite MRI model -> optional Grad-CAM
  -> existing /api/predict -> MRI workspace / -> SQLite scan history + research PDF
```

Raw EEG values are **10-bit ADC counts**, not calibrated microvolts. One differential amplifier provides one signal channel, regardless of electrode/accessory count. Nominal 250 Hz firmware rate is checked against device timestamps. UI shows measured rate separately from configured rate. USB arrival time is not sample time.

## EEG processing and ML

Default analysis uses six seconds of input: four-second central window plus one-second filter guards on each edge. Windows update roughly once per second; these overlapping live views are **not independent evaluation samples**. Missing/nonfinite samples, wrong timing, clipping, flatlines and large steps suppress analysis. Filters and limits are configurable via `SignalConfig`; common rate/window/bandpass/notch settings use environment variables. Filtering detrends and applies optional 50 Hz notch and fourth-order 1–40 Hz Butterworth bandpass. Filter parameters must be below actual Nyquist frequency.

Welch PSD, relative band powers, variance, Hjorth mobility/complexity and spectral entropy share one implementation between inference and training. Bands are operational choices: delta **1–4**, theta **4–8**, alpha **8–13**, beta **13–30**, **partial gamma 30–40 Hz**. No full gamma claim. Power is ADC counts² and PSD counts²/Hz. Unsupported bands are unavailable. One-second guards reduce edge transients; they do not prove artifact removal. Contact impedance, EEG origin and muscle/eye contamination are not reliably verified by these heuristics.

**No EEG dataset or trained EEG classifier is bundled. No EEG accuracy is claimed.** Supply appropriately licensed, labeled, subject-identified recordings and the manifest described in [docs/EEG_ML.md](docs/EEG_ML.md):

```bash
.venv/bin/python train_eeg.py --manifest /absolute/path/to/manifest.json --output-dir eeg_model_candidate
export BHM_EEG_MODEL_DIR=eeg_model_candidate
# Restart backend to load the reviewed local artifact.
```

Train/validation/test assignments are explicit and subject-disjoint. Duplicate file/numeric content is rejected. Training windows do not overlap. Train-fitted scaling stays inside sklearn pipelines. Dummy prior baseline, logistic regression and small random forest use identical splits; validation balanced accuracy selects the candidate. Final held-out test reports accuracy, precision/recall/F1 by class, macro F1, balanced accuracy, confusion matrix and ROC-AUC where valid. Outputs include model, metadata, feature order, config, label mapping, manifest, metrics and confusion-matrix SVG. Artifacts use trusted local joblib files; do not load untrusted model files.

## API

Existing MRI routes remain: `GET /api/health`, `/api/ready`, `/api/stats`, `/api/scans`; `POST /api/scans/clear`, `/api/predict`, `/api/report/pdf`. MRI upload accepts supported raster images and single-frame grayscale MR DICOM; explanations can be unavailable. `/api/ready` reports MRI readiness; `/api/device/status` reports EEG separately.

| Method | EEG endpoint | Behavior |
|---|---|---|
| GET | `/api/device/ports` | Enumerated ports; no fixed COM port |
| POST | `/api/device/connect` | JSON `{"source":"serial","port":"..."}` or `{"source":"simulated"}` |
| POST | `/api/device/disconnect` | Stop acquisition; interrupt active recording |
| GET | `/api/device/status` | Connection, source, measured/configured rate and counters |
| GET | `/api/eeg/live` | Latest samples, quality analysis, prediction/unavailability |
| GET | `/api/eeg/model/info` | Compatible EEG artifact metadata or unavailable reason |
| POST | `/api/eeg/recordings` | Start session from currently connected source |
| POST | `/api/eeg/recordings/stop` | Finalize active recording |
| GET | `/api/eeg/recordings?limit=100` | Latest sessions; bounded history |
| GET | `/api/eeg/recordings/{id}/export` | Source-labeled CSV after session is finalized |

Serial failures clear current estimates, interrupt active recording and retry up to five times. Reconnecting starts a fresh buffer and requires a fresh recording. Session duration limit defaults to one hour in `EEGService`; closed sessions remain on disk until manually archived/deleted. Retention-buffer evictions, malformed lines and discontinuities are visible. Storage/processing failures stop acquisition with an error rather than pretending data was saved.

## MRI evaluation and CUDA training

MRI data are four class image folders. Existing original Testing protocol contains **314 deduplicated images**. Bundled TFLite report: **74.52% accuracy, 0.693 macro F1**; bundled training overlap is uncertain. Previous EfficientNetV2-S GPU candidate (`model_candidate_eff_full`): **78.98% accuracy, 0.777 macro F1**. Completed grouped-validation candidate (`model_candidate_eff_clustered`): **80.89% accuracy (254/314), 0.802 macro F1** on the same Testing-folder protocol. Glioma recall improves from **38.10% to 50.00%**. No-tumor recall falls from **93.83% to 85.19%**. The 90% minimum and 95% target remain unmet. Both candidates are saved separately; neither has been promoted. Completed BraTS candidate (`model_candidate_eff_brats`): **81.21% test accuracy (255/314)**, glioma recall **60.71%**, macro F1 **0.8007**. This improves overall accuracy by one image, with lower meningioma recall. No training remains running or queued; no model promoted. See [handoff](HANDOFF.md). See [latest evaluation](model_candidate_eff_clustered/evaluation.json) and [HANDOFF.md](HANDOFF.md). Validation accuracy is not final test accuracy. A 95% target is aspirational, not a reported test result. Patient IDs are absent from the original dataset; no patient-disjoint or clinical validation can be claimed. Pooled scores are optimistic and not comparable with original Testing-folder scores.

```bash
.venv/bin/python evaluate_model.py --model-dir model --output evaluation/bundled-evaluation.json --tflite-only
.venv/bin/python train_model.py --backbone mobilenetv2 --output-dir model_candidate_new
```

GPU environment is separate (`~/venvs/bhm-gpu`, TensorFlow 2.21 with CUDA):

```bash
BHM_CUDA_LIBS=$(find "$HOME/venvs/bhm-gpu/lib/python3.11/site-packages/nvidia" -type d -name lib -printf '%p:')
export LD_LIBRARY_PATH="$BHM_CUDA_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
~/venvs/bhm-gpu/bin/python train_model.py --backbone efficientnetv2s --fine-tune-layers 0 --fine-tune-lr 5e-5 --output-dir model_candidate_new
~/venvs/bhm-gpu/bin/python evaluate_model.py --model-dir model_candidate_new --output model_candidate_new/evaluation.json --tflite-only
```

Never train on the original Testing folder or tune hyperparameters against it. Review evaluation before changing `BHM_MODEL_DIR`; candidates never overwrite `model/` automatically. Shared MRI preprocessing and hash/class-order contracts remain in `app/preprocessing.py` and `app/artifacts.py`.

#External data acquired on 2026-10-15: UCSF-PDGM T1c scans and tumor masks from 495 patients (1.44 GiB). Core-guided preparation and conservative overlap screening leave 528 additional glioma slices from 148 patients. UCSF remains separate. The completed BraTS experiment added 2,224 screened training slices while preserving validation/test splits; resulting test accuracy is 81.21%. See [acquisition details](docs/DATA_ACQUISITION.md) for exclusions, patient provenance, source attribution and BraTS access requirements.

## Grouped training/validation experiment

The previous candidate reached 99.32% validation accuracy while testing at 78.98%. An audit found 482 of its 1,182 validation images had a training image within three bits of a 64-bit perceptual difference hash. This is evidence of image similarity, not proof that all pairs are duplicate scans or the same patient.

`--cluster-validation` keeps connected components of similar images (hash distance at most three) and supplied patient IDs together across training/validation, including links across class labels. It preserves the original Testing folder and training pool. Whole groups take precedence over exact validation proportions; every class must remain in both splits or training fails. The manifest records cluster IDs, grouping parameters and class counts. Perceptual hashing is heuristic and does not establish patient independence or eliminate every possible leak. The flag cannot be combined with `--pooled`.

```bash
~/venvs/bhm-gpu/bin/python train_model.py --backbone efficientnetv2s --extra-class-dir "$HOME/datasets_extra/cheng/images" --extra-no-tumor-dir dataset/brain_tumor_dataset/no --head-epochs 10 --fine-tune-epochs 30 --fine-tune-layers 0 --fine-tune-lr 5e-5 --label-smoothing 0.1 --cluster-validation --output-dir model_candidate_eff_clustered
~/venvs/bhm-gpu/bin/python evaluate_model.py --model-dir model_candidate_eff_clustered --manifest model_candidate_eff_clustered/manifest.json --output model_candidate_eff_clustered/evaluation.json --tflite-only
```

Set the CUDA library path as above. This experiment tests more credible checkpoint selection; an accuracy gain is not guaranteed. Repeated results on the same Testing folder are development benchmarks, not independent external validation.

Completed on 2026-10-15 at 16:29 IST: 10 head epochs, 21 fine-tuning epochs with early stopping, successful TFLite export and evaluation. The validation-loss-selected checkpoint has 95.38% grouped validation accuracy and **80.89% test accuracy**, a **1.91 percentage-point** test improvement. Actual-data audit confirms identical test records, unchanged training pool and zero cross-split pairs at the declared three-bit hash threshold. Verification: 79 tests passed, two optional browser tests skipped. Candidate remains separate because class tradeoffs require review before deployment.

## Tests and optional deployment

```bash
.venv/bin/python -m pytest -q
node --check static/js/app.js
node --check static/js/eeg.js
# Optional rendered browser checks, while isolated local server runs:
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
BHM_BROWSER_URL=http://127.0.0.1:8000 .venv/bin/python -m pytest tests/test_eeg_browser.py -q
```

Browser test creates a labeled simulated recording. Run against a disposable local database. Default pytest skips this opt-in test. No physical acquisition or firmware upload is implied by automated software tests.

```bash
docker build -t brain-health-monitor .
docker run --rm -p 127.0.0.1:8000:8000 brain-health-monitor
```

Container is optional; for physical acquisition prefer native laptop execution. Docker needs explicit serial-device permission/passthrough configured for host OS. No Docker build/deployment is claimed unless recorded in validation notes. Optional desktop MRI viewer: `.venv/bin/python main.py` (requires graphical desktop). It is separate from EEG browser workspace.

## Privacy and limitations

Default bind is loopback. No authentication/multiuser authorization is implemented; do not expose as a public health-data service. EEG storage contains device samples and timestamps, no identity fields. MRI API strips DICOM patient ID/name before response/persistence; this does **not** remove burned-in annotations, identifiers in filenames, or all other DICOM metadata. Upload de-identified inputs only. Existing scan databases are not retroactively scrubbed; history responses redact their identity fields. CSV exports remain local research data.

Troubleshooting: wrong rate → match firmware/host settings; no port → check data-capable USB cable/CH340 driver and OS permissions; busy port → close other serial programs; no analysis → collect six seconds and inspect timing/clipping/transient warnings; no prediction → install reviewed compatible EEG artifact and use valid real input; MRI unavailable → install matching TensorFlow 2.21 CPU runtime; Grad-CAM unavailable → inspect model compatibility without inventing a heatmap. CPU augmentation can limit GPU training utilization.

Dataset licenses/provenance must be checked independently; no license rights are inferred from image folders. Source code licensing needs owner confirmation because no LICENSE file was found in this checkout.

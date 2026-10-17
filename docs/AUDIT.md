# Repository audit — 2026-10-15

Inspected local checkout (remote origin matches supplied GitHub URL), all Python modules, static HTML/CSS/JS, tests, training/evaluation scripts, dependency/build files, documentation and dataset file inventory. Existing uncommitted work preserved. Model binaries inspected through metadata/evaluation, not reverse-engineered. Dataset images not individually relabeled; provenance/license cannot be established merely from folders.

## Before this upgrade
| Area | Existing state | Priority |
|---|---|---|
| Web | Plain HTML/CSS/JS, no Node build; MRI workstation, history, report modal | Preserve |
| API | FastAPI server.py; health/ready/stats/scans/predict/report/pdf | Preserve |
| Desktop | CustomTkinter app/app.py, USB image-drive watcher; main.py launcher | Preserve, repair package import |
| MRI | Real TFLite inference, DICOM/raster validation, Grad-CAM if compatible, ReportLab PDF | Preserve separately from EEG |
| Storage | SQLite scan history + text audit | Keep; remove automatic DICOM identity persistence |
| EEG | No acquisition, firmware, datasets, windows, features, model, dashboard | P0 implement software; hardware validation blocked |
| Hardware | Legacy GPIO platform detection/LED/buzzer; USB watcher handles image drives, not biosignal serial | P0 remove unsupported platform dependency |
| Honesty | Initial HTML hardcodes 53 scans, 73.5% positive rate, 96.4% accuracy; random fallback report ID; README claims certification and lesion quantification | P0 replace with measured/empty states |
| EEG model | No labels or subjects available; no supported prediction task established | P0 explicit unavailable, build reproducible pipeline |
| MRI data | Four image classes; 314 deduplicated Testing images, no reliable patient IDs | P1 preserve evaluation caveats |
| MRI training | GPU EfficientNet run in progress; validation differs from fixed Testing distribution | P1 do not report validation as test accuracy |
| Dependencies | Existing venv TF CPU 2.15; requirements TF >=2.16 conflicts with verified local environment | P1 align tested Python 3.11 requirements |
| Deployment | Docker FastAPI, local default bind, no EEG device passthrough; no authentication | P1 local trusted workstation only |

Existing routes reviewed: GET /, /api/health, /api/ready, /api/stats, /api/scans; POST /api/scans/clear, /api/predict, /api/report/pdf; /static assets. No EEG routes existed. Prior tests use intentionally mocked MRI predictions; they are tests, not production fallback behavior. Existing production inference rejects unavailable models rather than random predictions. Grad-CAM coverage is saliency, not lesion segmentation. No clinical validation or hardware testing is established.

## Prioritized delivery
1. Establish honest hardware/raw-count/serial contract and scientific limitations.
2. Implement tested serial acquisition, bounded buffers, timestamp-derived timing, quality gating, features and recording isolation.
3. Implement leakage-resistant training and matching inference artifacts, without inventing data.
4. Integrate same-backend API and functional research dashboard; preserve MRI.
5. Document/run automated and browser checks; record unresolved physical and dataset validation separately.

## Hardware source reconciliation
Official Basic page now advertises UNO R4 Minima and accessories, whereas user's installed kit has Maker UNO. Manufacturer Maker UNO page confirms Arduino compatibility, CH340 USB bridge and Micro USB. Manufacturer starter manual identifies ATmega328P/16 MHz/A0–A5. BioAmp documentation specifies VCC→5V, GND→GND, OUT→A0 and 115200 baud examples. Use custom timestamped raw firmware here, not vendor Chords binary protocol. No additional channel or sensor inferred from band accessory names.

Sources accessed 2026-10-15:
- https://docs.upsidedownlabs.tech/kits/diy-neuroscience/basic/index.html
- https://docs.upsidedownlabs.tech/hardware/bioamp/bioamp-exg-pill/index.html
- https://www.cytron.io/p-maker-uno-simplifying-arduino-for-education
- https://cdn.cytron.io/makeruno/Maker_UNO_Starter_Kit_Module.pdf
- https://docs.arduino.cc/language-reference/en/functions/analog-io/analogRead/

No attached ttyACM/ttyUSB device found during audit. No EEG CSV/EDF/BDF/MAT dataset found. MRI dataset provenance/license and medical labels need independent verification; a repository license would not establish dataset rights. No new dataset downloaded.

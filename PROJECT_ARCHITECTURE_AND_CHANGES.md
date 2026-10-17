# Architecture and changes

Current architecture and setup live in [README.md](README.md). This replaces obsolete claims of certified clinical reports, verified lesion segmentation and unsupported board-level alerts.

- `server.py`: existing FastAPI application, MRI endpoints preserved; EEG router and worker lifecycle added.
- `app/eeg/protocol.py`: bounded streaming CSV parser and device-clock continuity tracking.
- `app/eeg/signal.py`: validated finite windows, guarded filters, PSD, band powers/features.
- `app/eeg/service.py`: device ownership, explicit simulation, reconnects, analysis and recordings.
- `app/eeg/storage.py`: SQLite sessions/raw samples and source-labeled CSV export.
- `app/eeg/model.py`, `app/eeg/training.py`, `train_eeg.py`: matching experimental inference/training contract.
- `firmware/maker_uno_eeg/`: raw Maker UNO sketch; physical upload pending.
- `static/eeg.html`, `static/js/eeg.js`, `static/css/eeg.css`: research dashboard at `/eeg`.
- MRI remains separate at `/`, using existing image preprocessing, TFLite, optional real Grad-CAM and research PDF.
- Removed `app/gpio_controller.py`: unsupported hardware assumptions and simulated LED/buzzer messages; desktop MRI remains functional without them.

See [audit](docs/AUDIT.md), [hardware](docs/HARDWARE.md), [EEG methodology](docs/EEG_ML.md) and [validation](docs/VALIDATION.md). No clinical validation, external deployment or physical EEG acquisition is established by software changes.

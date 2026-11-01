# CORTIA

Personal EEG monitoring and separate MRI image classification. Fresh FastAPI + React/TypeScript application, built independently from the older Brain_health_monitor UI and EEG implementation. Only the requested MRI model artifacts are imported.

CORTIA is research-support software, **not a clinically validated diagnostic device**. No generated EEG, seeded baselines, demo health scores, or hardcoded dashboard readings exist in production code.

## Run this workspace

```bash
cd /home/vinay/cortia
bash scripts/start.sh
```

Open **http://127.0.0.1:8010**. Create your own account; no default credentials exist. Interactive API documentation: **http://127.0.0.1:8010/docs**. The frontend is served by FastAPI after its production build, with no CDN dependency.

## Fresh setup

Python 3.12, Node.js 22+, npm, and uv are required.

```bash
bash scripts/setup.sh
# Optional single-frame MR DICOM decoding:
uv pip install --python .venv/bin/python -r backend/requirements-mri.txt
# Import only original MRI artifacts from a local clone:
.venv/bin/python scripts/import_mri.py --source /path/to/Brain_health_monitor --output models/mri-imported
export CORTIA_MODEL_DIR="$PWD/models/mri-imported"
bash scripts/start.sh
```

The imported artifacts are present in this workspace but excluded from Git. `models/mri/manifest.json` records the source commit, architecture, normalization, class order and SHA-256 hashes. Model files stay local; the import script reproduces their provenance without copying older application code.

The importer refuses existing output directories; use a new model version path.
Source candidates require explicit metadata. [Candidate assessment](docs/mri-candidate.md)
documents the separate EfficientNetV2S export, measured class tradeoffs and missing
training files. It is experimental and is not the active local model.

## Implemented paths

- Argon2 accounts, expiring opaque HttpOnly session cookies, same-origin mutation protection, authenticated REST/WebSocket access, owner-scoped records and files.
- Chords UNO-R4 serial handshake, exclusive device ownership, packet resynchronization, duplicate/counter-gap checks, throughput mismatch detection, disconnection handling and live sample streaming.
- Recording context, append-only raw CSV, timestamps, eight-second analysis windows, stored features and quality events.
- SOS bandpass, FFT amplitude, Welch PSD, exact band integrals, relative power and three transparent spectral ratios.
- Frozen personal baseline versions using independent session means, sample SD, median and exploratory z-score comparisons.
- Separate acquisition-gap, artifact, poor-signal and baseline-deviation events with explanations.
- Actual TFLite MRI inference, validated image uploads, per-user prediction history, source provenance and conditional Grad-CAM.
- Evidence summaries and optional external AI selection of backend-approved statements. The model cannot supply free-form findings.
- Overview, live monitor, brainwaves, baselines, MRI, history/comparison, insights and methods pages. Empty/error/loading states never fill charts with invented data.
- Downloadable raw CSV, EEG JSON reports and MRI JSON reports.

## Validation boundaries

Software tests exercise parsing, analytical fixtures, persistence, access isolation, baseline statistics, WebSockets and real MRI inference. Analytical EEG fixtures exist **only in tests**; they are never inserted into the application database or shown as recordings.

**Physical EEG hardware has not been tested.** No serial device was available during development. The documented acquisition implementation is not proof of successful BioAmp/UNO-R4 operation. Use [hardware acceptance checks](docs/hardware.md) before relying on recordings.

**MRI inference and Grad-CAM are verified locally.** The original bundled Keras and TFLite artifacts disagree, so that export still withholds attribution. A separate float32 conversion of the original Keras weights passes parity and actual Grad-CAM checks on nine repository images across all four dataset classes. This workspace selects that derived bundle through `.env`; original artifacts remain intact. No training occurs, and this does not establish classification accuracy or clinical suitability. See [export provenance and reproduction](docs/mri-export.md).

**External AI service is not configured or live-tested.** Backend summaries work without it. Optional provider selection is constrained and fails closed on invalid IDs or extra text.

## Development

```bash
# Terminal 1 — one worker only
cd backend
../.venv/bin/python -m uvicorn cortia.main:create_app --factory --host 127.0.0.1 --port 8010
# Terminal 2
cd frontend
npm run dev
```

Vite proxies API/WebSocket requests to port 8010. Production UI uses the same origin as FastAPI. Keep a single backend process: serial ownership and streaming buffers intentionally reside in one local process.

## Verification

```bash
cd backend && ../.venv/bin/python -m pytest -q
cd ../frontend && npm run build
npx playwright install chromium
npm run test:e2e
# Existing Chrome fallback, if installed:
CORTIA_BROWSER=/usr/bin/google-chrome-stable npm run test:e2e
```

Browser tests launch a separate temporary data directory and remove it after shutdown. Tests using original real MRI fixtures skip if that external repository is absent. Test output explicitly identifies such skips.

## Configuration

| Variable | Meaning |
| --- | --- |
| `CORTIA_DATA_DIR` | Private SQLite/raw/image storage; default `./data` |
| `CORTIA_MODEL_DIR` | MRI artifacts; default `./models/mri` |
| `CORTIA_DATABASE_URL` | Optional SQLAlchemy database URL |
| `CORTIA_SECURE_COOKIE=1` | Secure cookies when deployed behind HTTPS |
| `CORTIA_AI_ENDPOINT` | Trusted operator-configured chat-completion JSON endpoint |
| `CORTIA_AI_KEY` | Optional provider bearer secret |
| `CORTIA_AI_MODEL` | Provider model name |

Export variables before starting, or copy `.env.example` to `.env`. Startup script loads that local file. Never commit secrets. External AI requires explicit consent for each request to transmit curated statements; raw EEG, scans and usernames are not sent.

SQLite schema version 1 is tracked explicitly. SQLAlchemy models use portable types for a future PostgreSQL deployment. PostgreSQL driver, migrations beyond v1, multi-process acquisition coordination and remote deployment have **not** been validated. Back up metadata and private files together before any migration.

Store data on an OS-encrypted volume. Local files are permission-restricted but not application-encrypted. This local research application does not claim compliance certification or clinical validation.

Read [completion report](docs/completion-report.md), [scientific methods](docs/science.md), [API and schema](docs/api.md), [hardware checks](docs/hardware.md), [validation record](docs/validation.md), and [remaining work](docs/remaining.md).

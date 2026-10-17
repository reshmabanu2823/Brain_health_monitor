# Delivery and validation — 2026-10-15

## Delivered incrementally

Existing FastAPI, static frontend, SQLite persistence, MRI inference, optional Grad-CAM and research PDF routes preserved. EEG uses the same process and a separate workspace; no second backend or additional sensor assumed. Changes remain local/uncommitted; pre-existing work was retained. No GitHub push, deployment or production-model promotion performed.

## Changed-file inventory for this upgrade

Created:
- `app/eeg/__init__.py`
- `app/eeg/protocol.py`
- `app/eeg/signal.py`
- `app/eeg/service.py`
- `app/eeg/storage.py`
- `app/eeg/model.py`
- `app/eeg/training.py`
- `train_eeg.py`
- `firmware/maker_uno_eeg/maker_uno_eeg.ino`
- `static/eeg.html`
- `static/css/eeg.css`
- `static/js/eeg.js`
- `tests/test_eeg_protocol.py`
- `tests/test_eeg_signal.py`
- `tests/test_eeg_service.py`
- `tests/test_eeg_training.py`
- `tests/test_eeg_api.py`
- `tests/test_eeg_browser.py`
- `requirements-dev.txt`
- `docs/AUDIT.md`
- `docs/HARDWARE.md`
- `docs/EEG_ML.md`
- `docs/VALIDATION.md`
- `docs/screenshots/eeg-desktop.png`, `docs/screenshots/eeg-mobile.png`
- `docs/superpowers/specs/2026-10-15-eeg-research-design.md`
- `docs/superpowers/plans/2026-10-15-eeg-research.md`

Modified during this upgrade:
- `server.py`: EEG lifecycle/router/workspace, DICOM identity redaction before persistence/response, legacy history identity-field redaction.
- `app/app.py`: remove unsupported GPIO calls; retain desktop MRI functionality.
- `app/usb_monitor.py`: remove obsolete platform comment; image-drive monitoring remains.
- `main.py`: correct package-qualified desktop launcher import.
- `static/index.html`, `static/js/app.js`: measured/empty telemetry, research wording, EEG navigation, escaped filenames/history content, report ID from actual scan record, health checks.
- `static/css/style.css`: remove external Google Fonts request, use existing fallback fonts for offline loading.
- `requirements.txt`: add EEG dependencies, align CPU TensorFlow with bundled artifact compatibility (2.21).
- `.env.example`: EEG configuration defaults.
- `tests/test_api.py`: isolated EEG DB during MRI tests; history privacy regression.
- `README.md`, `PROJECT_ARCHITECTURE_AND_CHANGES.md`, `CLAUDE.md`, `HANDOFF.md`: architecture, commands, evidence and current limitations.

Removed: `app/gpio_controller.py` (unsupported hardware dependencies and console messages pretending physical LED/buzzer alerts). Existing desktop result visualization remains; no new hardware alerts are implied.

Other modified/untracked files shown by `git status` predated this upgrade. Do not attribute the entire working-tree diff to this turn. MRI models and datasets were not overwritten by this upgrade. Test server logs and optional screenshot originals are runtime artifacts; no EEG model was promoted.

## Actual checks

| Command/check | Actual result |
|---|---|
| `.venv/bin/python -m pytest -q` | **74 passed, 2 skipped**, 16.68 s; two opt-in browser tests skipped in default run |
| `BHM_BROWSER_URL=http://127.0.0.1:8765 .venv/bin/python -m pytest tests/test_eeg_browser.py -q --basetemp=/tmp/bhm-browser-evidence-verified` | **2 passed**, 13.33 s |
| `node --check static/js/app.js` | Passed |
| `node --check static/js/eeg.js` | Passed |
| `uv pip check --python .venv/bin/python` | 82 installed packages checked; all compatible |
| `.venv/bin/python -m compileall -q app server.py train_eeg.py main.py` | Passed |
| `git diff --check` | Passed |
| Independent review of EEG modules/integration | One actionable finding: UART capacity at 500 Hz; fixed with regression test and 100–250 Hz cap |
| Physical serial acquisition/firmware upload | **Not performed**: no attached board, no Arduino toolchain available |
| Docker build/deployment | **Not performed** |
| Production EEG training | **Not performed**: no labeled EEG dataset |

Initial full-suite run exposed four failures from existing TensorFlow 2.15 vs newer TFLite/Keras artifacts. Updating project CPU venv to TensorFlow 2.21 fixed them; separate running CUDA training venv was not changed. Initial browser attempts encountered Google Fonts loading timeout and later a backend startup race. Removed external font dependency, waited for server readiness, reran successfully. Reported passing results refer to final reruns, not those failed attempts.

Warnings remain: Starlette test-client HTTPX deprecation and TensorFlow Lite interpreter deprecation. They did not fail tests; runtime migration is future maintenance. Optional browser dependency is separate in `requirements-dev.txt`.

## Test coverage and UI evidence

Automated checks cover known-frequency alpha dominance, high-frequency attenuation, invalid filter/rate configuration, missing/nonfinite samples, clipping, flatline, gaps/jitter, guarded window length, segmentation, serial fragments/malformed/overlong lines, ADC bounds, device-clock rollover/reset, reconnect failures without simulation fallback, stale input, recording source isolation and interruption, rate summaries, CSV export, API errors, foreign-origin device controls, subject/content leakage, artifact mismatch, synthetic-fixture training roundtrip, real bundled MRI loading/inference/Grad-CAM and API/PDF behavior.

Training-roundtrip test data are deterministic **test fixtures**, not a biological dataset. Their classification performance is not an EEG result and is not published as one.

Browser plugin was unavailable; used regular Playwright Chromium. Flow: disconnected EEG → missing-port error → explicit simulated source → waveform/PSD/quality → recording → source-labeled CSV link → desktop/mobile screenshots → disconnect → intentional backend-503 state. Separate MRI flow: actual sample-image upload → bundled TFLite inference → research report modal → actual PDF download → EEG navigation. No JavaScript page exceptions. Mobile viewport 390×844 had no document overflow. Deliberate backend failure is an expected test response, not a production success state. QA server used temporary SQLite directories, not user's scan database.

[Desktop screenshot](screenshots/eeg-desktop.png) · [Mobile screenshot](screenshots/eeg-mobile.png). Both show **simulated** input explicitly. Canvas is rendered from returned sample/PSD data; charts do not carry invented patient metrics.

## Implemented versus blocked/partial

| Feature | Status and limit |
|---|---|
| Serial framing, port selection, reconnects | Implemented and software-tested; physical validation pending |
| Maker UNO raw firmware | Implemented; target compilation/upload and achieved timing unverified |
| Waveform, measured rate, quality, PSD, band power | Implemented; quality is heuristic, amplitudes uncalibrated |
| Explicit simulated source | Implemented/tested, source retained in exports, classifier disabled |
| Session storage, basic duration/count/rate summaries, CSV | Implemented/tested; full longitudinal quality summaries and retention UI remain future work |
| EEG trainer and artifact contract | Implemented/tested with fixtures; no trained biological EEG classifier/data |
| Live classifier integration | Implemented and gated; unavailable until compatible reviewed artifact exists |
| EEG/MRI workspace separation | Implemented/tested |
| MRI prediction/Grad-CAM/research PDF/history | Preserved and tested; no clinical certification |
| MRI GPU candidate | Existing independent run continues; final Testing evaluation pending at this delivery snapshot |
| Subject-level uncertainty/external validation | Not implemented; needed before research generalization claims |
| Public/multiuser deployment | Not implemented; local trusted workstation only |

## Measurements and remaining limits

Saved bundled MRI TFLite evaluation: **74.52% accuracy**, **0.69289 macro F1**, 314 unique Testing images. Bundled training overlap is uncertain. Earlier EfficientNet candidate: **72.93% accuracy**, **0.70335 macro F1**. These are original MRI evaluation protocol results, not EEG results.

Separate CUDA run `bhm-train-eff-full-20261015` remains active; at latest check it entered fine-tune epoch 18/30. Best observed validation accuracy is **99.32%**; **no final test result exists yet**. A 95% target remains aspirational; validation cannot establish original-test success. Inspect `logs/train_cuda_full.result.json` after automatic export/evaluation. No automatic model promotion.

Other limits: heuristic quality cannot prove cortical EEG, reject all artifacts or measure impedance; ADC reference/gain/offset uncalibrated; one channel cannot support multichannel claims; device timestamps not UTC synchronization; interruption creates new sessions; MRI dataset subject IDs/provenance/license and label quality remain unresolved; no automatic de-identification of filenames/burned-in text; old DB records require owner-controlled retention/removal. Actual hardware gain/bandwidth and timing must be measured. EEG labels/task validation and prospective independent-subject sessions are required before reporting classifier reliability.

Next priorities: physical wiring/upload/timing validation; collect consented task-labeled recordings; review signal quality with suitable expertise; reserve unseen subjects; train/compare baselines and report subject-level confidence intervals; validate on prospective Maker UNO sessions; add longitudinal quality summaries/retention controls; migrate deprecated test/runtime APIs when verified.

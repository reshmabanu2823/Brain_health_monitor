# Validation record — 2026-11-01

## Verified in this workspace

| Check | Result |
| --- | --- |
| Backend suite: `cd backend && ../.venv/bin/python -m pytest -q` | **77 passed**, eight upstream TensorFlow interpreter deprecation warnings |
| Frontend: `cd frontend && npm run build` | TypeScript and Vite production build pass |
| Browser suite: `CORTIA_MODEL_DIR=/home/vinay/cortia/models/mri-float32 CORTIA_EXPECT_GRADCAM=1 CORTIA_BROWSER=/usr/bin/google-chrome-stable npm run test:e2e` | **6 passed** with real backend, isolated temporary database, and actual Grad-CAM checked before/after reload |
| Same browser cases with `CORTIA_MODEL_DIR=/home/vinay/cortia/models/mri-candidate-brats-float32` | **6 passed**, candidate inference and actual Grad-CAM persistence |
| Python dependencies: `uv pip check --python .venv/bin/python` | All installed packages compatible |
| Production frontend dependency audit: `npm audit --omit=dev` | Zero reported vulnerabilities at verification time |
| Shell scripts: `bash -n scripts/start.sh scripts/setup.sh scripts/e2e-server.sh` | Pass |
| Local health, built dashboard, local API docs | HTTP 200 on port 8010 |
| Source review | Independent read-only review; identified material findings fixed with regression tests |

A clean dependency audit is not a penetration test or proof of security. No clinical validation was performed.

## Backend coverage

- Fragmented binary packets, corruption recovery, invalid ADC range, duplicate counters, counter wrap and packet loss.
- Analytical alpha fixture, PSD band conservation, truncated beta, gamma absence, rejected flatline/clipping/gaps and invalid window inputs.
- No recording without live hardware; raw sample persistence and correct segment offsets from received test packets only.
- Exclusive owner snapshots and recording controls; canceled handshakes; stale disconnect operations cannot erase new ownership.
- Acquisition restart stream-ID changes reset WebSocket cursors even without an observed disconnected poll.
- Serial cleanup still runs when recording storage finalization fails.
- Authentication, logout/revocation, password input validation, blocked cross-origin mutations and anonymous WebSocket rejection.
- Different-user denial on recordings, segments, anomalies, reports, raw files, explanations, MRI images and prediction history.
- Baseline cohort independence, eligibility, context matching, statistics, zero-variance behavior and in-sample labeling.
- Request-body bounds before multipart parsing, including unknown-length/chunked input; invalid image rejection.
- Actual original MRI image through original model artifacts and fresh upload/inference/history/report API.
- Float32 re-export of original Keras weights, original artifact preservation, source-tampering rejection, existing-output protection, and refusal to publish mismatching conversion output.
- Evidence-only summaries and rejection of invented AI statements or extra model prose.
- Real loopback HTTP AI contracts: consent before sending, verified statement selection, digest/persistence, rejected inventions and safe provider failures. This does not establish live-provider operation.
- Hand-calculated benchmark metrics, dataset hash/label checks, recorded split overlap/duplicate rejection, and no-usable-Grad-CAM export cleanup.
- Explicit legacy/signed input contracts, RGB display reconstruction, actual EfficientNetV2S candidate/Keras parity, candidate import integrity/class/provenance/overwrite checks, archived experiment manifest selection, and stale evaluation removal on new exports.
- Eight optional-decoder DICOM tests: MR normalization/inversion, non-MR/multiframe/corrupt/flat rejection, actual MRI fixture upload, metadata-free stored PNG and exact source digest. This does not prove pixel-identifier removal or comprehensive deidentification.

Fixtures with analytical EEG exist only under `backend/tests`; no synthetic recordings enter the real application database. Hardware ownership/concurrency tests use controlled test doubles, not physical devices.

## Browser coverage

1. Anonymous-to-account flow; disconnected overview and disabled recording control.
2. Brainwaves, baseline, history and insight empty states; methods reference.
3. Invalid MRI upload never produces a prediction.
4. Real repository MRI image upload, actual model inference, actual Grad-CAM overlay, and prediction/overlay persistence after page reload with the verified derived bundle.
5. 390 px mobile navigation, no horizontal overflow, logout and protected endpoint denial.
6. Interactive OpenAPI documentation loads entirely from local assets.

The overview was also visually inspected from an actual browser screenshot. No health measurements were populated for that preview.

## MRI result boundary

Original fixture: `Brain_health_monitor/dataset/no/N1.JPG`.
TFLite artifact SHA-256: `c034cd57128e44e408587973d9f54da1838acade845236c9580316efbe0b036e`.
Actual output was a valid four-class distribution; winning dataset class was `no_tumor` with approximately 0.94818 model score. This single fixture confirms code execution and contracts only. It does not establish accuracy or clinical performance.

The paired Keras artifact disagrees with TFLite on this input under the preserved source preprocessing. The frontend displays attribution unavailable, with the agreement failure reason. CORTIA does not substitute another saliency method or claim the image establishes a healthy brain.

Follow-up: a separate float32 TFLite export of the unchanged original Keras weights
is now selected locally through `.env`. Nine real images covering all four dataset
classes pass winning-class agreement with Keras; maximum absolute probability
difference is **0.000004955654**. All nine produce actual Grad-CAM.
On N1.JPG, the derived `no_tumor` score is approximately **0.85304**, following
Keras rather than the original TFLite score. This model-version difference is not
a biological change or improved-accuracy claim. Original artifacts and historical
reports remain unchanged. Derived TFLite SHA-256:
`19917cd19886162798d23aaa6b184effcf4804cd4578fac210b3eb2dd75826a1`.
See [reproduction and provenance](mri-export.md).

The full 314-image repository benchmark is complete. Exported/Keras winning-class
agreement is 100%; maximum probability difference is 0.00002486234. Grad-CAM is
available for 308 images; six have no positive activation and correctly withhold
attribution. Benchmark accuracy is 75.48%, macro F1 0.70665, glioma recall 29.8%
and pituitary recall 55.6%. Original training overlap and patient independence
are unknown, so this is not independent clinical validation. Known benchmark
limitations are now included in the selected derived model's manifest.

Accelerated 60-minute test fixtures at both 250 and 500 Hz verify 2.7 million raw
samples and 900 persisted windows in temporary storage. These checks do not
validate physical acquisition or real-time, multi-hour operation.
See [full completion report and reproducible benchmark commands](completion-report.md).

A separate existing EfficientNetV2S candidate is now compatible and benchmarked on
the same 314 images: accuracy 80.89%, macro F1 0.79764, glioma recall 59.5%, no-tumor
recall 85.2%. All winning classes agree with Keras; maximum probability difference
is 0.000003472022. Actual Grad-CAM succeeds on all 314. Class tradeoffs and 5,230
missing source training/validation files prevent treating it as an automatic
replacement or independently validated model. Active selection remains the
original-weight export. See [candidate evidence and provenance](mri-candidate.md).

Default MRI runtime uses pinned TensorFlow 2.21. The current LiteRT package metadata unconditionally requires `backports.strenum`, whose Python constraint excludes this Python 3.12 environment. That dependency combination failed compatibility checks, so it was removed. TensorFlow inference passes and dependencies are compatible, but TensorFlow emits an upstream deprecation warning for its legacy Lite interpreter. A future migration requires a compatible LiteRT release and rerunning inference/attribution checks. Full installed versions are recorded in `backend/requirements-workspace.lock`.

## Remaining external validation

- **Physical Arduino UNO R4 / BioAmp setup:** absent. Handshake, actual bandwidth/gain, rate stability, electrode quality and real recording behavior need [physical acceptance checks](hardware.md).
- **External AI:** no endpoint/key configured. Constrained selection and input/output rejection are tested locally; live provider operation is not tested.
- **Grad-CAM:** verified for nine images with the derived float32 bundle; still withheld for any runtime disagreement, invalid gradients, or no positive activation. Original export still fails agreement on N1.JPG.
- **PostgreSQL/remote deployment:** ORM architecture allows later migration; driver deployment, migrations, remote access and multi-process acquisition are not validated.
- **Scale/retention:** no long-duration physical recording or storage-load benchmark. CSV remains intentionally inspectable; compression/retention is future work.
- **Medical validity:** signal descriptors and exploratory thresholds are not validated diagnostic or wellness scores. MRI performance/generalization and any clinical use require independent validation.

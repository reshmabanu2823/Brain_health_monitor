# CORTIA completion report — 2026-11-01

Local implementation and the available software checks are complete. Physical EEG
acceptance and a real AI-provider check remain blocked by missing external inputs.
MRI benchmarking also exposes substantial classifier weaknesses; no clinical
validation has been established.

## Software verification

- **77 backend tests pass**, including actual MRI inference, export parity,
  authentication/isolation, baselines, recording integrity, no-Grad-CAM export
  rejection/cleanup, and real loopback HTTP AI contracts.
- **Six browser cases pass against both active and candidate bundles**, including actual Grad-CAM display and persistence
  after reload. Production frontend build and Python dependency checks pass.
- Independent read-only review finds no blocking software defects in the export
  and validation changes.
- The application serves locally at `http://127.0.0.1:8010`.

## Actual MRI benchmark

The selected float32 export was evaluated through CORTIA's real MRIService on
**314 unique repository images**, with verified hashes and no overlap against
the recorded train/validation split hashes.

| Dataset class | Correct / actual | Recall | Precision | F1 |
| --- | ---: | ---: | ---: | ---: |
| Glioma | 25 / 84 | 29.8% | 100.0% | 45.9% |
| Meningioma | 112 / 113 | 99.1% | 68.3% | 80.9% |
| No tumor | 80 / 81 | 98.8% | 77.7% | 87.0% |
| Pituitary | 20 / 36 | 55.6% | 90.9% | 69.0% |

Overall accuracy is **75.48%**; four-class macro F1 is **0.70665**.
Low glioma and pituitary recall is a material model limitation. Of the 84
glioma-labeled images, 42 were classified as meningioma, 15 as no tumor and two
as pituitary. High model scores do not make these errors clinically acceptable.
The derived model manifest now includes these measured limitations, so new
prediction reports expose them alongside the existing scope restrictions.

All 314 exported predictions agree with original Keras on winning class; maximum
absolute probability difference is **0.00002486234**. Actual Grad-CAM succeeds on
308 images. Six correctly return attribution unavailable because no positive
Grad-CAM activation exists; no substitute heatmap is generated.

This is a reused repository benchmark. Original model training provenance is
unknown, so the images may have appeared during original training. Patient
independence is unknown. These results do **not** establish external generalization,
calibration, or clinical validity. Improving the model requires a separate training
and validation effort with suitable data and traceable splits; changing labels,
thresholds or reporting language cannot resolve the measured weaknesses.

[Full metrics, confusion matrix and per-image results](benchmarks/2026-11-01-mri.json)

Reproduce from project root, choosing a new output file:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/benchmark_mri.py \
  --model-dir models/mri-float32 \
  --dataset /home/vinay/brain_health_monitor/dataset \
  --split /home/vinay/brain_health_monitor/evaluation/bundled-evaluation-manifest.json \
  --output /tmp/cortia-mri-benchmark-new.json
```

## Recording and storage stress test

Accelerated test workloads exercise real packet decoding, acquisition storage,
filters, features and database writes. Every raw CSV sample index, device counter,
sample-clock value, ADC value and gap flag is checked. Segment boundaries, counts,
quality and stored feature aggregates are checked too.

| Fixture rate | Fixture duration | Samples verified | Valid windows | Raw CSV | Run time |
| --- | ---: | ---: | ---: | ---: | ---: |
| 250 Hz | 60 minutes | 900,000 | 450 | 42,871,993 bytes | 13.19 s |
| 500 Hz | 60 minutes | 1,800,000 | 450 | 86,661,519 bytes | 20.47 s |

All **2.7 million** generated test samples and 900 windows pass integrity checks.
Peak process RSS is approximately 149.5 MiB across both workloads. SQLite metadata
including WAL uses approximately 9.4 MiB per workload at measurement time. Values
reflect this machine and workload, not a production capacity guarantee.

Generated packets exist only in temporary test directories, which are deleted.
No fixtures are inserted into the production database or dashboard. These are
accelerated software checks, **not** two hours of physical or real-time recording.
They do not test USB timing, electrodes, firmware, source-rate stability, real
signal quality or multi-hour wall-clock behavior.

[Machine-readable storage results](benchmarks/2026-11-01-acquisition-soak.json)

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/soak_acquisition.py \
  --minutes 60 --output /tmp/cortia-acquisition-soak-new.json
```

## AI integration

Six new real loopback-HTTP tests verify authenticated provider requests, explicit
consent before transmission, curated evidence only, persistence and evidence
digests, rejection of invented statements/prose, and safe provider failure handling.
No real provider endpoint/model/key is configured; no live-provider test has run.
Backend evidence summaries remain available without external AI.

## What still needs external action

1. **Connect the UNO R4/BioAmp hardware.** Complete [physical acceptance](hardware.md),
   including firmware/rate verification, interruptions, real recordings and
   physical long-duration testing. No supported serial device is currently present.
2. **Configure a trusted AI endpoint and model**, plus a key if required, in local
   `.env`. Then test consented explanations from actual recordings. Keep keys local.
3. **Model improvement and independent validation.** Repository classifier weaknesses
   remain. Suitable data, patient-independent validation where possible, and
   appropriate independent clinical evaluation cannot be produced by software tests.

Remote deployment, PostgreSQL and distributed acquisition remain optional future
extensions of the agreed single-process local workstation design.

## Subsequent candidate assessment

An existing unpromoted EfficientNetV2S candidate is now imported with explicit
signed-input preprocessing, separately float32-exported, and benchmarked on the
identical 314-image cohort. Accuracy reaches 80.89%, macro F1 0.79764 and glioma
recall 59.5%, with actual Grad-CAM on all 314 images. However, no-tumor recall falls
to 85.2%, and tumor-labeled images predicted as no tumor increase from 23 to 25.
It is not an automatic improvement for every use and remains experimental.

The original-weight export remains active. Restoring 5,230 unavailable candidate
training/validation files and independent validation remain necessary for further
reproducible model work. [Candidate comparison and provenance](mri-candidate.md).

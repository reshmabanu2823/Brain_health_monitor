# CORTIA MRI candidate assessment

Continuation of the authorized MRI work under the existing local-workstation spec.
Hardware and live AI remain unavailable. The source project contains unpromoted
EfficientNetV2S candidates with training metadata. Assess the BraTS-extended candidate
as a separate bundle; do not treat a reused test-set gain as clinical validation.

## Design choices

Support exactly the two explicit source contracts: legacy RGB /255 and MobileNetV2
RGB /127.5 - 1. Use the same transform in inference, export verification and offline
benchmarking. Grad-CAM overlays must use visible RGB pixels, not signed model inputs.
Import model files and metadata only; never copy source application code. Record
hashes, source subdirectory, repository revision context and experimental status.
Keep current active model while assessing candidate class tradeoffs.

- [x] Add failing tests for signed preprocessing, display reconstruction and unsupported contracts.
- [x] Implement shared preprocessing and wire inference/export/benchmark/Grad-CAM to it.
- [x] Add import contract/integrity/overwrite tests and implement versioned candidate import.
- [x] Import candidate separately, export float32, verify real images and Grad-CAM.
- [x] Benchmark all 314 repository images and report per-class changes against current model.
- [x] Run backend/browser/build checks and independent review; update status/report.

Evidence: 77 backend tests; six browser cases against both active and candidate
bundles; production build pass. Independent review finds no blockers. New tests
also cover source experiment archive selection and DICOM fixture tag stripping.
Candidate four-class accuracy 80.89% vs 75.48%; no-tumor recall 85.2% vs 98.8% and more
tumor/no-tumor label errors. Candidate remains experimental. Data audit finds 5,230
training/validation files unavailable; archive hash matches recorded experiment.
Results: `docs/mri-candidate.md` and linked per-image/paired/data audit JSON reports.

Review focus: signed input values must not distort displayed MRI, unknown contracts
must fail, source hashes must match before importing, current bundles must survive,
candidate training limitations must travel to reports, and test-set comparisons must
not be described as external validation or justify an automatic clinical deployment.

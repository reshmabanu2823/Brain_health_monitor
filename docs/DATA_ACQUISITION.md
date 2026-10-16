# External MRI acquisition — 2026-10-15

## Current status

Public UCSF-PDGM Version 5 T1c volumes and matching tumor masks downloaded successfully: **495 unique source patients, 990 files, 1,543,565,298 bytes (1.44 GiB)**. Six follow-up exams were excluded. Every downloaded size matches the provider's selected-file listing; local SHA-256 checksums are recorded. No normal/no-tumor data were acquired. Conversion produced **1,516 RGB slices from 424 patients**. Another **71 patients** have no labels 1 or 4 and were excluded from this core-guided preparation; their raw scans and valid glioma diagnoses are preserved. Overlap screening completed: **528 slices from 148 patients** remain in `images_filtered/`. The conservative hash rule excludes all slices from 276 patients with potential image similarity to existing data; it does not prove these are duplicates or shared patients.

Data directory: `/home/vinay/datasets_extra/ucsf_pdgm/`.

- `raw/`: original compressed NIfTI volumes and masks.
- `UCSF-PDGM-metadata_v5.csv`, `UCSF-PDGM-metadata_glossary.csv`: provider clinical data and schema.
- `download_plan.json`, `download_manifest.json`: provider listing, selected cases, diagnoses, byte counts and checksums.
- `images/`: complete prepared class folders, `index.json` and `preparation_manifest.json`, published together after conversion succeeds.
- `images_filtered/`: completed audited derivative with whole-patient exclusions for potential overlap with existing images; `overlap_audit.json` records the heuristic matches and counts.
- `SOURCE.md`: citation, license, acquisition and conversion methods.

## Source and access

[UCSF-PDGM collection](https://www.cancerimagingarchive.net/collection/ucsf-pdgm/), [DOI](https://doi.org/10.7937/tcia.bdgf-8v37), Version 5, CC BY 4.0. Only T1c and tumor segmentation files were selected from the provider's public Aspera package. The full multimodal collection is about 142 GB and exceeds local available disk space; the selected 1.44 GiB acquisition fits while preserving at least 3 GiB free. No existing data or models were deleted.

The [BraTS 2023 data folder](https://www.synapse.org/Synapse:syn64952532) requires Synapse authentication and acceptance of its post-challenge terms. The user accepted the terms and downloaded the official training ZIP through their signed-in browser. The archive is local and verified; programmatic Synapse credentials are unnecessary for preparation. UCSF clinical metadata include BraTS mappings, so these collections must not be counted as independent without checking those mappings.

REMBRANDT image access follows its provider's controlled-access process; no REMBRANDT images were downloaded or requests submitted.

## Preparation and verification

Local acquisition runner: `logs/fetch_ucsf.py`; service `bhm-download-ucsf-t1c-20261015.service` completed with exit code 0. Native transfer client: official IBM Aspera Transfer SDK 1.1.9, downloaded using IBM's [published SDK locations](https://github.com/IBM/aspera-cli/blob/main/docs/sdk_location.yaml). Public-link authorization follows IBM's client implementation; no personal Synapse credentials were used.

Local conversion runner: `logs/prepare_ucsf.py`; service `bhm-prepare-ucsf-20261015.service`; log `logs/prepare_ucsf.log`; completion `logs/prepare_ucsf.exit`. The strict service exited 1 because of the 71 reviewed core-label exclusions. Qualified publication then completed successfully using `logs/publish_ucsf_qualified.py`; its manifest records all exclusions.

The converter verifies source checksums, 3D shape and affine alignment, finite values, known segmentation labels and diagnosis mapping. It reorients paired data to RAS and selects up to four axial planes separated by at least 5 mm, with core area at least half the patient's peak. [BraTS 2021 labels](https://www.med.upenn.edu/cbica/brats2021/) identify necrotic core as 1, edema as 2, and enhancing tumor as 4. Labels 1 and 4 support slice selection; edema-only planes are excluded. Positive-voxel 1st/99th percentile windowing generates RGB PNGs. No mask channel, contour or mask-based patch is supplied to the classifier.

Patient IDs use the namespace `ucsf_pdgm:`. Fresh sibling staging, exact file/index/manifest reconciliation, checksums, refusal to overwrite and atomic publication prevent partially indexed images entering training. Strict conversion stops publication when any case is rejected and writes `preparation_rejections.json`. All 71 rejections were exactly `No annotated tumor core`. After reviewing these exclusions, `logs/publish_ucsf_qualified.py` reconciled all 495 downloaded patients with accepted/excluded sets and atomically published the qualified subset. The exclusion does not imply absence of tumor; label-2-only cases are simply outside this slice policy. Twelve local checks pass, covering slice selection, spacing, mask-independent pixels, malformed data, registration, canonical orientation and safe publication:

```bash
PYTHONPATH=/home/vinay/datasets_extra/ucsf_pdgm/python_tools:logs .venv/bin/python -m pytest logs/ucsf_conversion_checks.py -q
```

Nibabel 5.4.2 is installed only under `/home/vinay/datasets_extra/ucsf_pdgm/python_tools`; application environments and dependencies are unchanged. For a fresh output directory, run strict preparation after a successful download. If it stops on rejected cases, review the complete report before qualified publication:

```bash
PYTHONPATH=/home/vinay/datasets_extra/ucsf_pdgm/python_tools:logs .venv/bin/python -u logs/prepare_ucsf.py
# Only after reviewing the complete rejection report:
PYTHONPATH=/home/vinay/datasets_extra/ucsf_pdgm/python_tools:logs .venv/bin/python logs/publish_ucsf_qualified.py
PYTHONPATH=.:/home/vinay/datasets_extra/ucsf_pdgm/python_tools:logs .venv/bin/python -u logs/audit_ucsf_images.py
```

The audit compares every prepared image with existing train/validation/test images from `model_candidate_eff_clustered/manifest.json`. A conservative six-bit perceptual-hash threshold excludes an entire new patient when any selected image is close to an existing image. Original raw and prepared data remain intact; filtering writes a separate patient-indexed dataset. All 6,120 existing reference images matched their saved SHA-256 checksums. Screening found 558 image-level similarity matches across 276 patients, retaining 528 images from 148 patients; no exact duplicate PNG groups occurred within the prepared data. Use the filtered subset for the next experiment. The default app suite passes with 79 passed and two optional browser tests skipped; all 12 local conversion checks also pass.

## Limits

This source adds glioma cases, not the other three classifier classes. Skull-stripped volumes and annotation-guided slice selection differ from arbitrary uploaded JPEGs. Excluding core-label-negative cases also biases this prepared subset toward tumors with annotated core. Perceptual hashing is heuristic; existing patient identifiers are incomplete. Cross-source patient independence is not established. Adding these data does not guarantee 90% test accuracy.

No new model has been trained on these data yet. Best measured candidate remains 80.89% on the fixed original 314-image Testing-folder benchmark; no model promotion occurred. Keep existing validation and test records fixed when evaluating the next training experiment.

## BraTS continuation — 2026-10-15

Official archive `/home/vinay/Downloads/ASNR-MICCAI-BraTS2023-GLI-Challenge-TrainingData.zip` (13,172,616,844 bytes, 12.27 GiB), Synapse `syn51514132`, matches provider MD5 `1abc1e06776230cc440977e4472dd5e1`. Selected extraction contains 1,251 T1c/mask pairs (2,502 files, 3.19 GiB). Other modalities remain compressed in the preserved archive. Selected members are read through ZIP CRC checks and receive local SHA-256 hashes.

[Official BraTS access discussion](https://www.synapse.org/Synapse:syn25829067/discussion/threadId=12691) confirms the BraTS 2023 enhancing-tumor label is 3, replacing 4. `logs/prepare_brats.py` validates source labels `{0,1,2,3}` and maps 3 to 4 only for the reused slice selector. Source masks are unchanged. Clinical diagnoses are inherited from the adult glioma collection; source masks select core-supported axial planes and never enter classifier pixels. No-core exclusions are explicit. Fresh staging, checksum/index reconciliation and atomic publication apply as for UCSF. Fifteen conversion checks pass; two additional audit integration checks pass. Independent review cleared conversion, overlap audit and the training wrapper.

Pipeline services: `bhm-prepare-brats-20261015.service` → `bhm-audit-brats-20261015.service` → `bhm-train-eff-brats-20261015.service`. Each successor requires predecessor exit 0. At 19:21 IST, selected extraction is complete and three CPU workers are converting slices; audit/training successors are queued. CUDA execution preflight passed on the RTX 4050. Logs: `logs/prepare_brats.log`, `logs/audit_brats_training.log`, `logs/train_cuda_brats.log`.

`logs/audit_brats_training.py` screens whole BraTS patients against all 6,120 existing train/validation/test images, using six-bit dHash proximity, and deduplicates remaining exact PNG copies. It writes a separate `images_filtered/` and `logs/brats_training_manifest.json`. Original 4,638 training records remain; screened BraTS records append only to training. Original 1,168 validation and 314 test records remain exactly equal. This heuristic does not establish patient identity or independence. UCSF remains separate pending patient-mapping verification, avoiding unverified double-counting between the two new sources.

`logs/train_fixed_brats.py` validates manifest and image checksums and passes that frozen manifest to the unchanged trainer through a process-local builder substitution. Same EfficientNetV2-S configuration as the 80.89% baseline: ImageNet initialization, 10 head epochs, up to 30 full fine-tuning epochs, learning rate 5e-5, label smoothing 0.1, batch 16, seed 42; checkpoint selection uses validation loss only. Candidate `model_candidate_eff_brats` is separate from the app model. TFLite export is evaluated once on the saved fixed benchmark after training. No accuracy gain is established until that evaluation completes.

## Completed BraTS result

Training/export/evaluation completed at 20:48:14 IST, exit 0. Fixed test accuracy: **81.21% (255/314)** versus 80.89%, a one-image gain. Glioma recall rose from 50.00% to 60.71%, while meningioma recall fell from 98.23% to 92.04%. Macro F1 fell slightly from 0.8019 to 0.8007. Neither 90% nor 95% achieved; no model promoted. Original validation/test records and exported model checksums verified. No training remains running or queued. Earlier active/queued descriptions above are historical. Evaluation: `model_candidate_eff_brats/evaluation.json`.

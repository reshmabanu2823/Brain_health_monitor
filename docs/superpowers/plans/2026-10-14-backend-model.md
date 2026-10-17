# Backend and model reliability implementation plan

> Use superpowers:executing-plans to implement tasks inline with regression tests.

**Goal:** Make inference, uploads, explanations, and training reproducible and truthful.
**Architecture:** Shared image/artifact contracts underpin the existing FastAPI and desktop clients. Independent dataset/evaluation utilities support an import-safe training CLI.
**Tech stack:** Python 3.11, FastAPI, TensorFlow 2.15, SQLite, NumPy, Pillow, pydicom.
**Spec:** ../specs/2026-10-14-backend-model-design.md

## Global constraints
Preserve bundled weights and dataset. Upload default 10 MiB; decoded images max 16 megapixels. New artifacts use [-1,1]; legacy uses [0,1]. No invented predictions, metrics, or clinical certification. No remote changes.

## Review focus
- Client cancellation holds analysis capacity until the worker finishes (task 3).
- MONOCHROME1 single-frame DICOM is inverted; multiframe rejected (task 1).
- Duplicate images with conflicting labels halt training (task 4).
- Evaluation hashes must match the serving artifact (task 2).
- Unavailable explanation clears the previous overlay and PDF remains usable (task 3).

## Tasks
1. Shared preprocessing/artifacts and inference (`app/preprocessing.py`, `app/artifacts.py`, `app/inference.py`, `tests/test_model_contract.py`). Interfaces: `preprocess_image(image, preprocessing)` returns float32 tensor/array; `load_contract(model_dir)` returns validated metadata and ordered labels; `BrainTumorModel.predict(input)` preserves five-value result. Write/run failing tests for probability preservation, preprocessing, missing runtimes, quantization, concurrency, metadata and DICOM. Implement; run tests.
2. Persistence and explanations (`app/logger.py`, `app/gradcam.py`, `tests/test_storage.py`, `tests/test_gradcam.py`). Interfaces: `get_scan_stats(model_dir)`, `get_scan_history(limit, offset)`, `log_result(...)`; `generate_gradcam_heatmap(input, model_dir, return_metrics, class_index)` returns genuine overlay or unavailable. Test isolated DB aggregates, NumPy serialization, model-bound evaluation, synthetic ROI, failed gradients, shared decoder. Implement; run tests.
3. API and clients (`server.py`, `app/report_generator.py`, `app/app.py`, `static/js/app.js`, `static/index.html`, `Dockerfile`, `tests/test_api.py`). Tests first for traversal, limits, formats, corrupt content, readiness, concurrent same-name requests, saturated/cancelled workers, PDFs and validation. Unique temp files, bounded workers, app state, sanitized report inputs, nullable explanations, client fallback. Implement; run suite and real model/PDF integration.
4. Training and evaluation (`app/dataset.py`, `app/evaluation.py`, `train_model.py`, `evaluate_model.py`, `tests/test_training.py`). Interfaces: `build_manifest(dataset_dir, seed, validation_fraction)` returns disjoint records and exclusions; `classification_metrics(y_true,y_pred,class_names)` returns JSON metrics. Test conflicting duplicates, seed reproducibility, disjoint sets, class weights and metrics. Implement deterministic augmentation, frozen BN, best checkpoint, matching exports and CLI evaluation. Run unit suite, actual dataset audit and bundled model evaluation; short candidate smoke training if resources permit.
5. Documentation and final verification (`README.md`, `requirements.txt`, `.env.example`, verification report). Document setup, API error behavior, environment settings, legacy assumptions, evaluation limitations, training/promotion commands. Run complete tests, static checks, actual server smoke. Review changes and fix material findings. Leave local branch reviewable.

## Execution record
- User explicitly requested implementation after reviewing scope/spec; proceed inline without further design gates.
- Work in requested checkout on feature branch to make changes immediately accessible; preserve existing data.

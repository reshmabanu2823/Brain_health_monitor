# Backend and model reliability design

## Intent and scope

Improve the existing FastAPI backend and MobileNetV2/TFLite model pipeline. The user approved improving upload safety, inference concurrency, readiness reporting, preprocessing consistency, dataset splitting, reproducible training, and measured evaluation. Preserve the current web workstation and desktop workflows where possible.

The intended deployment audience is unspecified. Assume a local demonstration or research prototype. Success means predictions originate from the loaded model, inputs and artifacts have explicit contracts, API failures are handled consistently, and evaluation results are reproducible. This work does not establish clinical validity or promise increased accuracy.

## Evidence from the repository

- `app/inference.py` applies softmax to an already-softmax classifier output, changing confidence values.
- Training rescales RGB images to [0, 1]; inference additionally converts to grayscale and applies CLAHE. Grad-CAM uses a third preprocessing path.
- Missing inference dependencies select a heuristic classifier with invented probabilities.
- `server.py` writes uploads to a user-supplied filename and shares one unprotected TFLite interpreter across worker threads.
- Health always reports healthy; stats return a literal 96.4% accuracy.
- Validation uses the training augmentation generator. Class weights are manually assigned and omitted during fine-tuning.
- SHA-256 inspection found 93 duplicate copies within Training, 80 within Testing, and 64 hashes shared between them. Training has 2,870 files and Testing has 394 files.
- Grad-CAM silently replaces unavailable gradients with intensity/edge saliency, then exposes thresholded saliency as tumor area.
- The desktop code unpacks four values from an inference function returning five.
- TensorFlow, FastAPI, pytest, OpenCV, and pydicom are not installed in the current Python environment.

## Selected approach and alternatives

Improve the current framework and backbone, with regression tests and an explicit model artifact contract. This directly addresses known errors and retains the current clients.

Replacing the backend framework adds migration work without addressing the model errors. Replacing MobileNetV2 before establishing trustworthy evaluation makes model comparisons unreliable. Both alternatives are deferred.

## Model contract and inference

Add a shared preprocessing module used by training, inference, and explanations. It converts decoded inputs to RGB, resizes consistently, and normalizes according to model metadata.

Existing bundled artifacts retain RGB [0, 1] preprocessing, matching the checked-in training script; remove inference-only CLAHE. Newly trained artifacts use MobileNetV2 [-1, 1] normalization and explicitly declare it in versioned metadata. Do not apply new normalization to old weights. This legacy assumption must be documented because the original training provenance is unavailable.

Metadata describes preprocessing version, image size, ordered classes, output interpretation, seed, and model hashes. Validate metadata and class mapping when loading. Missing metadata permits only the documented legacy contract; invalid metadata or incompatible tensor shapes fail loading. Resolve labels from `class_indices.json`, checking that all four known categories map to unique contiguous indices.

Preserve the current five-value `predict` result. Protect the interpreter's complete set/invoke/get operation with a lock. Respect tensor dtype and quantization scale/zero-point for integer models. Preserve valid softmax probabilities without applying softmax again; use numerically stable softmax only for explicitly declared logits. Reject non-finite or malformed outputs. Missing runtimes or artifacts must fail explicitly, never produce heuristic classifications.

## Backend behavior

Keep the existing endpoint paths and successful prediction fields. Add metadata fields only where useful.

- Stream uploads into unique temporary files with a default 10 MiB limit configurable through an environment variable. Restrict suffixes to supported raster and DICOM formats. Sanitize filenames for display and audit storage; never use them as storage paths. Remove temporary files on every exit path.
- Decode and validate inputs before inference; bound decoded image size to 16 megapixels. Return 413 for oversized uploads, 415 for unsupported formats, 422 for invalid image content, 503 when inference is unavailable, and generic 500 errors for unexpected internal failures. Log internal exceptions without exposing filesystem paths in responses.
- Initialize the model through lifespan, keep load status on application state, and avoid request-time model reload races. `/api/health` reports degraded status when inference is unavailable; add `/api/ready` returning 503 until inference is ready. Update the container health check to use readiness.
- Run blocking decode, inference, persistence, and report work outside the event loop. Bound concurrent analysis with configurable capacity and return 503 when full, avoiding an unbounded inference backlog. Ensure capacity is held until the worker finishes, including client cancellation.
- Allow CORS only for configured origins; same-origin workstation requests work by default.
- Validate PDF payload fields, probability ranges, image sizes and base64 content. Sanitize download names and escape user-provided ReportLab paragraph text. Reports describe classifier outputs and saliency rather than asserting an examination, certification, physician signature, lesion segmentation, or clinical risk from confidence alone.

## DICOM and explanations

Use the same decoder for predictions and explanations. Support single-frame grayscale MR DICOM, including rescale slope/intercept and MONOCHROME1 inversion. Reject unsupported multi-frame/color data with a clear validation error rather than silently falling back to PIL. Absent acquisition metadata remains unknown rather than receiving invented values.

Generate actual Grad-CAM for the selected classifier class using the shared preprocessing contract. Cache model construction safely. Do not substitute intensity maps when Grad-CAM fails. Prediction can succeed with `heatmap_b64: null`, empty metrics, and explicit explanation availability/method fields. Add a small client fallback so the workstation clears any previous overlay and reports unavailable explanations; reports accept an absent overlay.

Retain `tumor_metrics` and its existing keys for client compatibility, but identify their meaning as saliency coverage in model-image coordinates, not measured lesion area. Adjust report/workstation wording accordingly. Fix desktop unpacking and NumPy probability serialization as necessary to preserve the existing workflow.

## Persistence and measured statistics

Use context-managed SQLite connections with a busy timeout and parameterized queries. Keep SQLite as the source of history and aggregate statistics; calculate aggregate counts in SQL rather than reading at most 5,000 rows. Keep optional flat logging for the desktop workflow, with serialized writes. Persistence failures must be visible to callers and logs.

Expose measured accuracy only from a compatible evaluation artifact whose model hash matches the loaded TFLite artifact; otherwise return an unknown value. History supports bounded pagination. Tests use temporary storage and never clear the repository's existing audit records.

## Reproducible training and evaluation

Refactor `train_model.py` into an import-safe CLI. Training options include dataset directory, output directory, seed, batch size, frozen-stage epochs, and fine-tuning epochs. Default output goes to a separate candidate directory; existing model files are preserved until explicitly selected.

Build a deterministic manifest before training. Hash images, remove same-label duplicate copies, reject duplicates with contradictory labels, and exclude test hashes from training. Split the remaining training hashes into seeded stratified train/validation sets. Do not modify source images. Write split membership and exclusion counts to the output directory. Require every class to have sufficient samples for the requested split.

Augment training only. Validation and test decoding/preprocessing are deterministic. Derive balanced class weights from the actual training subset and use them in both stages. Freeze batch-normalization layers during fine-tuning. Set Python, NumPy and TensorFlow seeds and request deterministic TensorFlow operations where supported.

Select the best validation-loss checkpoint across both stages, then reload that exact checkpoint for export and evaluation. Export Keras and TFLite artifacts from the same weights and write their metadata and hashes. Record training history.

Evaluate the candidate Keras model and exported TFLite model on the deduplicated held-out test set. Write sample counts, accuracy, per-class precision/recall/F1, macro F1, confusion matrix, and Keras/TFLite prediction agreement and probability differences. Record dependency versions and split seed. Without patient identifiers, a hash-disjoint split cannot establish patient-disjoint evaluation; state that limitation in the evaluation artifact and documentation.

## Verification and acceptance

Use a project-local virtual environment. Add regression tests before behavior changes for double softmax, preprocessing consistency, class mapping, runtime failure, interpreter concurrency, quantized tensors, upload traversal/collisions/limits, bad content, readiness, report validation, database aggregates, and hash-disjoint manifests. Use small synthetic fixtures and fake interpreters for fast tests, supplemented by integration tests using real bundled artifacts and isolated database storage.

Run the complete test suite and a real prediction/PDF smoke test with the bundled model. Verify startup readiness and cleanup. Run a short training/export/evaluation smoke test when local resources permit; label its metrics as smoke-test results. A full training run is optional and must not be implied by tests passing. Do not claim an accuracy improvement without a completed held-out evaluation. Document exact commands, configuration, measured checks, and any environment limitations.

## Out of scope

No new backbone, authentication system, cloud deployment, model promotion automation, patient identity management, or clinical certification. Preserve bundled weights and existing dataset files. Make no remote repository changes.

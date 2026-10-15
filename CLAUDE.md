# Brain Health Monitor

MRI brain-tumor classifier (4 classes: `glioma_tumor`, `meningioma_tumor`, `no_tumor`, `pituitary_tumor`) with a FastAPI backend, web UI, Grad-CAM, PDF reports and SQLite storage.

Current work in progress: see `HANDOFF.md`.

## Layout
- `server.py`, `app/app.py`: API; `static/`: web UI.
- `app/inference.py`, `app/gradcam.py`: inference on the bundled TFLite model in `model/`.
- `app/preprocessing.py`: shared decoding and preprocessing (224x224; `mobilenet_v2` = [-1, 1], `legacy_rgb_0_1` = [0, 1]).
- `app/dataset.py`: deterministic hash-disjoint manifests (`build_manifest`) and the pooled cluster hold-out (`build_pooled_manifest`).
- `train_model.py`: trains a candidate into its own directory. It never touches `model/`.
- `evaluate_model.py`: evaluates a model directory on the deduplicated test split (or a saved manifest via `--manifest`).
- `model_candidate*/`: trained candidates, each with `metadata.json`, `manifest.json` and `evaluation.json`.

## Environments
- `.venv/`: project venv with `tensorflow_cpu` 2.21.0. Use it for tests and the app. It cannot use the GPU.
- `~/venvs/bhm-gpu/`: TensorFlow 2.21 with CUDA for training on the RTX 4050 (6 GB).
  TensorFlow only finds the GPU when the bundled CUDA libraries are on the library path:
  ```
  S=~/venvs/bhm-gpu/lib/python3.11/site-packages/nvidia; export LD_LIBRARY_PATH=$(ls -d $S/*/lib | tr '\n' ':')
  ```
  Without this, `libcusolver.so.11` fails to load and TensorFlow silently runs on the CPU.

## Commands
- Tests: `.venv/bin/python -m pytest`
- Train (GPU): `~/venvs/bhm-gpu/bin/python train_model.py --backbone efficientnetv2s --output-dir model_candidate_X ...` (see `--help`)
- Evaluate: `~/venvs/bhm-gpu/bin/python evaluate_model.py --model-dir model_candidate_X --output model_candidate_X/evaluation.json --tflite-only`

## Evaluation rules
- The standard test set is the deduplicated Kaggle `dataset/Testing` folder (314 images). Never train on it or select hyperparameters on it.
- `--pooled` scores are optimistic. The images have no patient IDs, so slices from one patient can fall in both train and test. Never compare pooled scores with Testing-folder scores.
- Extra data (`--extra-class-dir`, `--extra-no-tumor-dir`) goes into the training pool only. Near-duplicates of test images are filtered out.
- Promote a candidate into `model/` only after reviewing its `evaluation.json`.

## Single-channel EEG extension
- Research workspace `/eeg`, served by the existing FastAPI app; MRI remains at `/`.
- `app/eeg/`: raw serial acquisition, timestamp validation, filtering/features, optional experimental model and SQLite recordings. `train_eeg.py` requires an explicit subject-disjoint manifest; no EEG dataset/artifact is bundled.
- Firmware: `firmware/maker_uno_eeg/maker_uno_eeg.ino`, Maker UNO A0, 115200 baud, nominal 250 Hz, raw 10-bit counts. Custom ASCII protocol, not Chords.
- One amplifier is one channel. Simulation requires explicit selection and never produces classifier outputs.
- Use one backend worker. See `docs/HARDWARE.md`, `docs/EEG_ML.md`, `docs/AUDIT.md`, `docs/VALIDATION.md`. Physical hardware/firmware upload validation remains pending.

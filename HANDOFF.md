# Handoff: model accuracy work (2026-10-15)

## Goal
Raise classification accuracy as high as possible using the GPU. The user requests a margin above 90%.

Working target: **95% accuracy**, a five-percentage-point buffer above the **90% minimum**. This margin is an assumption pending the user's reply; it is not an achieved result or a statistical guarantee.
- On the fixed 314-image Testing-folder split, 90% requires at least **283 correct** (at most 31 errors).
- The 95% working target requires at least **299 correct** (at most 15 errors).
- Measure the target on the exported TFLite model using the original Testing-folder protocol. Pooled scores do not satisfy this target.
- Select checkpoints and hyperparameters using validation data only; do not tune against the Testing folder.

## Status
Branch `improve/backend-model`. GPU training and evaluation completed successfully on 2026-10-15 at 11:30 IST; exit code 0. Preparing changes for GitHub.

### Done
- Fixed GPU training: `~/venvs/bhm-gpu` needs `LD_LIBRARY_PATH` set to its bundled CUDA libraries (see `CLAUDE.md`). Verified that TensorFlow sees `GPU:0`.
- `train_model.py`: added `--fine-tune-layers` (0 = unfreeze the whole backbone; default 30), `--fine-tune-lr` (default 1e-4) and `--label-smoothing` (default 0). They are recorded in `metadata.json`. A GPU smoke run passed end-to-end, including the TFLite export.

### Completed CUDA result (2026-10-15)
- EfficientNetV2-S full fine-tuning exported successfully to `model_candidate_eff_full`.
- Original 314-image Testing-folder TFLite accuracy: **78.98%** (248/314); macro F1: **0.7768**.
- Glioma recall: **38.10%** (32/84).
- Improvement over previous 72.93% candidate: **6.05 percentage points**.
- 90% minimum and 95% target remain unmet. No candidate promoted; no training process currently running.
- Evaluation: `model_candidate_eff_full/evaluation.json`. Runner exit/result files remain local under ignored `logs/`.

### CUDA restart on 2026-10-15 (historical launch notes)
User authorized GPU training. TensorFlow 2.21 preflight found the RTX 4050 and successfully executed matrix multiplication on `/GPU:0`.

Restarted the original Testing-folder EfficientNetV2-S experiment using the existing full-fine-tuning settings below. There is no saved checkpoint from the interrupted run, so training restarts from ImageNet weights.
- User systemd service: `bhm-train-eff-full-20261015.service` (independent of the tool/session process; a machine shutdown or user-manager shutdown still stops it).
- Runner: `logs/train_cuda_full.sh`; output: `logs/train_cuda_full.log`.
- Candidate: `model_candidate_eff_full`; evaluation runs automatically after export into `model_candidate_eff_full/evaluation.json`.
- Completion status: `logs/train_cuda_full.exit`; target comparison: `logs/train_cuda_full.result.json` (written only after successful evaluation).
- Check status: `systemctl --user status bhm-train-eff-full-20261015 --no-pager`.
- No pooled run is queued in this restart. No candidate is promoted automatically.
- Target remains 95%, minimum 90%; neither is established by starting training.

### Previous launch on 2026-10-15
The first attempt died at fine-tune epoch 13 when the session ended. Both runs were relaunched as one detached chain (`nohup setsid`), so they survive the session ending. Chain output: `logs/runs_chain.log`. Check with `pgrep -f runs.sh`.
1. `model_candidate_eff_full`: EfficientNetV2-S, full fine-tune, Testing-folder protocol. Log: `logs/train_candidate_eff_full.log`. Expected about 74-77% on the Testing folder.
2. `model_candidate_pooled_full`: the same settings with `--pooled`. Queued to start after run 1. Log: `logs/train_candidate_pooled_full.log`. Expected about 90-95%, but this score is optimistic (see below).

Check a run: `tail logs/train_candidate_*_full.log` and look for `Candidate written to`, then for `model_candidate_*_full/evaluation.json`.

Rerun if a run is missing or incomplete (set `LD_LIBRARY_PATH` first):
```
~/venvs/bhm-gpu/bin/python train_model.py --backbone efficientnetv2s --extra-class-dir ~/datasets_extra/cheng/images --extra-no-tumor-dir dataset/brain_tumor_dataset/no --head-epochs 10 --fine-tune-epochs 30 --fine-tune-layers 0 --fine-tune-lr 5e-5 --label-smoothing 0.1 --output-dir model_candidate_eff_full
~/venvs/bhm-gpu/bin/python evaluate_model.py --model-dir model_candidate_eff_full --output model_candidate_eff_full/evaluation.json --tflite-only
```
For the pooled run, add `--pooled`, use `--output-dir model_candidate_pooled_full`, and evaluate with `--manifest model_candidate_pooled_full/manifest.json`.

Timing: the head stage takes about 85 s per epoch. Full fine-tuning takes about 2-3 min per epoch, with early stopping after 5 epochs without improvement. Each run takes about 1-1.5 h. The bottleneck is CPU augmentation (`num_parallel_calls=1`, kept for determinism), not the GPU.

## Results so far (Testing folder, 314 images, TFLite)
| Candidate | Accuracy | Macro F1 |
|---|---|---|
| bundled `model/` (training may have overlapped the test set) | 74.5% | 0.693 |
| `model_candidate` (MobileNetV2) | 71.7% | 0.696 |
| `model_candidate_aug` | 71.0% | 0.691 |
| `model_candidate_extra` | 72.0% | 0.694 |
| `model_candidate_eff` (EfficientNetV2-S + Cheng + extra no-tumor) | 72.9% | 0.703 |
| `model_candidate_eff_full` (completed full fine-tuning) | 79.0% | 0.777 |

## Key finding
Earlier runs suggest a train/test distribution gap; its cause has not been established. Every backbone and data mix scores 71-73%, while validation accuracy within the training distribution is about 93% or higher. Glioma recall on the test set is very low (the bundled model gets 27%). The test glioma images come from a different distribution than the training ones, and some may be mislabeled. No literature-based upper bound is established here; labels and distribution need independent review.

## Paths to about 90%
- Pooled protocol (run 2): reaches about 90% or more, but the number is optimistic and not comparable to Testing-folder scores.
- An honest 90% needs data only the user can supply:
  1. Several hundred glioma scans that resemble the Testing folder.
  2. Patient IDs for a patient-level split.
  3. Testing-folder labels checked by a radiologist.
  4. Scans from the scanner or hospital where the app will be deployed.
  Supply them as class folders plus an optional `index.json` that maps `class/filename` to a patient ID, and train with `--extra-class-dir`.
- Public options: Br35H adds only no-tumor images. BraTS adds glioma, but its 3D NIfTI volumes must first be converted to 2D slices. The 7,023-image Kaggle set (Nickparvar) mostly duplicates data already used here.

## Next steps
1. Read both `evaluation.json` files and compare them with the 72.9% baseline.
2. Promote a candidate into `model/` only if it beats the current model on the Testing folder. Update `README.md` with the protocol caveat.
3. Run `.venv/bin/python -m pytest` before committing.

## EEG research extension delivered (2026-10-15)
Existing MRI app now also serves `/eeg`. See `docs/VALIDATION.md` for exact changed files, implementation status and results. Final checks: 74 default-suite tests passed, two browser tests passed separately. Firmware/serial/filtering/features/recordings/training-artifact pipeline implemented; no physical board or labeled EEG dataset available, so real acquisition and biological EEG training remain unverified. No model promotion. Project CPU environment upgraded to TF 2.21 to match bundled artifacts. At EEG handoff time, CUDA training was at fine-tune epoch 18/30. It subsequently completed; final Testing accuracy is 78.98% (see completed result above).

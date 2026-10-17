# Handoff: model accuracy work (2026-10-15)

## Goal
Raise classification accuracy as high as possible using the GPU. The user requests a margin above 90%.

Working target: **95% accuracy**, a five-percentage-point buffer above the **90% minimum**. This margin is an assumption pending the user's reply; it is not an achieved result or a statistical guarantee.
- On the fixed 314-image Testing-folder split, 90% requires at least **283 correct** (at most 31 errors).
- The 95% working target requires at least **299 correct** (at most 15 errors).
- Measure the target on the exported TFLite model using the original Testing-folder protocol. Pooled scores do not satisfy this target.
- Select checkpoints and hyperparameters using validation data only; do not tune against the Testing folder.

## Completed BraTS experiment (2026-10-15)

Training, TFLite export and fixed-benchmark evaluation completed successfully at **20:48:14 IST**, exit 0. Service `bhm-train-eff-brats-20261015.service` is inactive; no training remains running or queued.

- Test accuracy **81.21% (255/314)** versus 80.89% (254/314): **+0.32 percentage points / one additional correct image**.
- Glioma recall **60.71% (51/84)** versus 50.00% (42/84).
- Tradeoff: meningioma recall **92.04% (104/113)** versus 98.23% (111/113); pituitary **86.11% (31/36)** versus 88.89% (32/36); no-tumor unchanged **85.19% (69/81)**.
- Macro F1 **0.8007**, slightly below previous 0.8019. Neither 90% minimum nor 95% target achieved. No model promoted; app model unchanged.
- Seven initial head epochs and 16 fine-tuning epochs completed. Best validation-loss checkpoint came from fine-tuning epoch 11, validation accuracy 95.46%, loss approximately 0.4563. Validation is not test accuracy.
- Prepared 4,639 slices from 1,131 unique BraTS patient prefixes across 1,251 source exams; six exams lacked core labels. Overlap screening added 2,224 slices to the original 4,638 training images, for 6,862 total. Original validation (1,168) and test (314) records verified identical. Export artifact checksums verified.
- Results: `model_candidate_eff_brats/evaluation.json`, `logs/train_cuda_brats.result.json`, `logs/train_cuda_brats.exit`. Candidate remains separate in `model_candidate_eff_brats/`.
- Sections below describe the historical launch; their queued/running statuses are superseded by this completed result.

## Historical launch: BraTS preparation and next GPU experiment (2026-10-15)

User accepted Synapse access terms, downloaded the official training ZIP and instructed “its downloaded continue now”. Archive: `/home/vinay/Downloads/ASNR-MICCAI-BraTS2023-GLI-Challenge-TrainingData.zip`, 13,172,616,844 bytes. MD5 matches provider: `1abc1e06776230cc440977e4472dd5e1`. Local free disk increased to 27 GiB after user cleanup; no further deletions authorized or performed.

- Pipeline started around 19:10–19:17 IST. Preparation service `bhm-prepare-brats-20261015.service` validates MD5/SHA-256 and extracts only 2,502 T1c/mask files (3.19 GiB), from 1,251 complete source cases; skips other modalities. Raw/archive are preserved. Script/log: `logs/prepare_brats.py`, `logs/prepare_brats.log`. Output: `/home/vinay/datasets_extra/brats2023_gli/images` after atomic publication.
- Source labels are `{0,1,2,3}`; ET label 3 explicitly remaps to 4 only inside the existing tested UCSF core-slice selector. Unknown labels/registration errors stop preparation. No-core cases are explicitly excluded, remain glioma in raw, and never become no-tumor examples. Up to four axial slices per exam, at least 5 mm apart. Patient IDs drop exam suffixes to group repeated exams. Local conversion checks: **15 passed**; independent review cleared preparation.
- `bhm-audit-brats-20261015.service` waits for successful preparation, then runs `logs/audit_brats_training.py`; log `logs/audit_brats_training.log`, completion `logs/audit_brats_training.exit`. Whole new patients are excluded if any selected image is within six dHash bits of any baseline training/validation/test image. Remaining exact duplicate PNGs are deduplicated. UCSF omitted from this experiment pending cross-source mapping, so shared UCSF/BraTS cases are not counted twice.
- Frozen experiment manifest: `logs/brats_training_manifest.json`, audit `logs/brats_training_audit.json`. Original **4,638 training records remain**, with screened BraTS images appended only to training. Original **1,168 validation and 314 test records stay exactly equal**. Audit hashes every reference and prepared input. Two focused audit integration tests pass, including whole-patient exclusion from one validation match and changed-reference refusal; independent review cleared audit.
- GPU service `bhm-train-eff-brats-20261015.service` is **queued behind preparation/audit**. It launches only after audit exit 0. `logs/train_fixed_brats.py` loads the SHA-verified frozen manifest, validates all image checksums and uses a process-local builder substitution before calling unchanged `train_model.train()`. It never rebuilds the split. The exported manifest must match exactly. Independent review cleared runner and shell syntax.
- Runner `logs/train_cuda_brats.sh`: same EfficientNetV2-S, ImageNet initialization, 10 head / up to 30 full fine-tuning epochs, fine LR 5e-5, smoothing 0.1, batch 16, seed 42, early stopping on validation loss. CUDA required; no CPU fallback. Candidate `model_candidate_eff_brats` must not exist beforehand. Then TFLite evaluation uses the saved original test manifest and compares to 80.89% baseline. Logs/completion/result: `logs/train_cuda_brats.log`, `.exit`, `.result.json`. No promotion.
- Status at handoff (19:21 IST): selected extraction complete; three workers converting slices (100/1,251 cases at last check). CUDA execution preflight passed on the RTX 4050. Audit/training are waiting, not yet training. Best measured accuracy remains **80.89%**. Do not claim improvement before the new evaluation completes. Check all service exit states before reporting completion.
- User offered Google Cloud SSH at 19:24 IST. `gcloud` is not on PATH. Existing SSH alias `kinfolk-hm16.asia-south1-a.project-f0b2aa95-aaf6-4017-bcb` resolves to `34.180.43.42`; strict, batch-mode read-only SSH timed out on port 22. Asked user for current Cloud SSH command or project/zone/instance. No VM creation, spending or cloud transfer performed; local pipeline continues.
- User subsequently instructed “orelse do locally”. Proceed with the existing local pipeline; no cloud details are required and no more SSH attempts are needed. At 19:28 IST, conversion reached 600/1,251 cases (2,215 slices, three explicit no-core exclusions). Audit and GPU services remain waiting on successful preparation.

## Latest work: external MRI acquisition (2026-10-15)

User requested acquiring additional public MRI data after the 80.89% result. See `docs/DATA_ACQUISITION.md` for sources, commands, methods and limitations.

- Public UCSF-PDGM v5 T1c + tumor-mask acquisition completed: **495 unique source patients, 990 files, 1.44 GiB**. Six follow-up exams excluded. Size checks passed and SHA-256 checksums recorded in `/home/vinay/datasets_extra/ucsf_pdgm/download_manifest.json`.
- Download service `bhm-download-ucsf-t1c-20261015.service` is inactive with `ExecMainStatus=0`. Script/log: `logs/fetch_ucsf.py`, `logs/fetch_ucsf.log`; native Aspera SDK and source metadata remain local under ignored `logs/`.
- Conversion and qualified publication completed: **1,516 RGB axial slices from 424 patients** in `/home/vinay/datasets_extra/ucsf_pdgm/images`. Strict service `bhm-prepare-ucsf-20261015.service` exited 1 after reporting 71 cases with `No annotated tumor core` (labels 1/4 absent). These remain valid glioma cases in raw data, not no-tumor examples. After report review, `logs/publish_ucsf_qualified.py` reconciled all 495 patients and atomically published the qualified subset; independent review cleared this path. Logs: `logs/prepare_ucsf.log`, `logs/prepare_ucsf.exit`. Local preprocessing checks: **12 passed**. Optional Nibabel installation moved outside the repository to `/home/vinay/datasets_extra/ucsf_pdgm/python_tools` to keep dependency tests out of project test discovery.
- Overlap audit completed with exit 0: `logs/audit_ucsf_images.py`, log `logs/audit_ucsf_images.log`, report `/home/vinay/datasets_extra/ucsf_pdgm/overlap_audit.json`. All 6,120 existing source checksums matched the saved manifest. Six-bit dHash screening flagged 558 images from 276 patients; `images_filtered/` retains **528 images from 148 patients**, with patient index and complete provenance. No exact duplicate PNG groups among prepared images. Raw and unfiltered prepared data remain intact. These heuristic matches do not prove duplication or shared patients. Default suite: **79 passed, 2 skipped**; local conversion checks: **12 passed**.
- User accepted Synapse terms and downloaded BraTS through the signed-in browser. The archive is now local; no programmatic Synapse credentials are needed for preparation. UCSF metadata contain mappings to BraTS cases; avoid counting shared patients twice. See the active BraTS section above.
- Local disk had only 8.3 GB free before acquisition; full multimodal archives do not fit. Selected T1c/mask files fit with a 3 GiB reserve. No existing files deleted. No hospital outreach or controlled-access requests submitted.
- No new training job has started on these data. Best measured candidate remains **80.89%**; original app model and fixed 314-image benchmark remain unchanged. Freeze existing validation/test records for the next experiment.

## Completed follow-up: grouped validation (2026-10-15)

User approved grouping similar training/validation scans, preserving the original Testing folder, retraining EfficientNetV2-S, and comparing exported TFLite accuracy and glioma recall. No promotion is authorized by this experiment.

Implementation, review and real-data audit passed. GPU run launched at approximately **15:17 IST** and completed at **16:29:36 IST**, exit code 0, under user systemd service `bhm-train-eff-clustered-20261015.service`. Both training stages, TFLite export and original Testing-folder evaluation completed. No training remains running or queued.

### Completed grouped-validation result
- **80.89% TFLite test accuracy (254/314)**, up **1.91 percentage points / six correct images** from 78.98% (248/314).
- Macro F1: **0.8019**, up from 0.7768.
- Glioma recall: **50.00% (42/84)**, up from 38.10% (32/84).
- Pituitary recall: **88.89% (32/36)**, up from 77.78% (28/36).
- Tradeoff: no-tumor recall drops from **93.83% (76/81) to 85.19% (69/81)**; meningioma recall drops from 99.12% (112/113) to 98.23% (111/113).
- Ten head epochs and 21 fine-tuning epochs completed; early stopping restored the checkpoint with lowest grouped validation loss (epoch 16, loss 0.45448, validation accuracy 95.38%). This is not the test score.
- **90% minimum and 95% working target remain unmet.** No candidate promoted; bundled app model hash remains `c034cd57128e44e408587973d9f54da1838acade845236c9580316efbe0b036e`.
- Evaluation: `model_candidate_eff_clustered/evaluation.json`. Audit, comparison and exit files below remain local under ignored `logs/`.

### Implementation and verification
- New `train_model.py --cluster-validation` option; cannot combine with `--pooled`.
- `app/dataset.py` keeps connected components of perceptual hashes (distance <=3) and supplied patient IDs together, including cross-label links. Patient aliases survive exact-image deduplication. Class-coverage backtracking avoids rejecting feasible splits.
- Previous validation audit: 482/1,182 validation images had a training image within three hash bits. This is heuristic image similarity, not proof that all pairs are duplicated scans or the same patient.
- New split: 4,638 training / 1,168 validation / original 314 test images; 1,496 components, largest 134, four cross-label components. The training pool is unchanged. Hashing does not establish patient independence.
- Verification: 79 default-suite tests passed, two optional browser tests skipped. Independent reviewer found two edge cases, both reproduced with real-image regression tests and fixed; follow-up review cleared launch. Eight Ruff findings in the touched Python files were confirmed identical to the pre-existing findings.
- Audit script: `PYTHONPATH=. .venv/bin/python -u logs/audit_clustered_validation.py`; results and manifest: `logs/clustered_validation_audit.json`, `logs/clustered_validation_manifest.json`. Audit confirmed zero cross-split pairs within three hash bits, exact equality of the original test records, and the same training-pool hashes.
- Completed runner: `logs/train_cuda_clustered.sh`; CUDA preflight refused CPU fallback and verified matrix multiplication on `/GPU:0`; candidate output `model_candidate_eff_clustered`. Same backbone, data pool, epoch budgets, learning rate and smoothing as the previous run; only training/validation assignment changes.
- Runner compares its saved manifest with the audited manifest before evaluating the TFLite model on the original test set. Evaluation: `model_candidate_eff_clustered/evaluation.json`; comparison summary: `logs/train_cuda_clustered.result.json`; completion: `logs/train_cuda_clustered.exit`; log: `logs/train_cuda_clustered.log`.
- Completion confirmed: service inactive, `ExecMainStatus=0`; `logs/train_cuda_clustered.exit` records successful completion at 16:29:36 IST. Runner refuses overwriting the existing candidate directory.
- Neither 90% nor 95% is achieved by fixing validation. Compare with the 78.98% baseline after training; repeated testing is a development benchmark, not external validation.

## Previous completed run
Branch `improve/backend-model`. Previous GPU training and evaluation completed successfully on 2026-10-15 at 11:30 IST; exit code 0.

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
| `model_candidate_eff_clustered` (grouped training/validation) | 80.9% | 0.802 |

## Key finding
Earlier runs suggest a train/test distribution gap; its cause has not been established. Every backbone and data mix scores 71-73%, while validation accuracy within the training distribution is about 93% or higher. Glioma recall on the test set is very low (the bundled model gets 27%). The test glioma images come from a different distribution than the training ones, and some may be mislabeled. No literature-based upper bound is established here; labels and distribution need independent review.

## Further accuracy work
- A pooled score would be optimistic and not comparable to Testing-folder scores. No completed pooled result establishes the 90% target.
- Further gains may require representative data and label review; 90% is not guaranteed. Useful inputs include:
  1. Several hundred glioma scans that resemble the Testing folder.
  2. Patient IDs for a patient-level split.
  3. Testing-folder labels checked by a radiologist.
  4. Scans from the scanner or hospital where the app will be deployed.
  Supply them as class folders plus an optional `index.json` that maps `class/filename` to a patient ID, and train with `--extra-class-dir`.
- Public options: Br35H adds only no-tumor images. BraTS adds glioma, but its 3D NIfTI volumes must first be converted to 2D slices. The 7,023-image Kaggle set (Nickparvar) mostly duplicates data already used here.

## Next steps
1. Review the grouped candidate's remaining glioma errors and lower no-tumor recall before considering promotion.
2. Keep grouped validation fixed for further experiments; choose checkpoints/hyperparameters using validation only. The Testing folder is already a repeatedly inspected development benchmark, not independent external validation.
3. No further GPU job is queued. Source changes and new candidate artifacts remain local and uncommitted; no GitHub push or app-model replacement performed in this follow-up.

## EEG research extension delivered (2026-10-15)
Existing MRI app now also serves `/eeg`. See `docs/VALIDATION.md` for exact changed files, implementation status and results. Final checks: 74 default-suite tests passed, two browser tests passed separately. Firmware/serial/filtering/features/recordings/training-artifact pipeline implemented; no physical board or labeled EEG dataset available, so real acquisition and biological EEG training remain unverified. No model promotion. Project CPU environment upgraded to TF 2.21 to match bundled artifacts. At EEG handoff time, CUDA training was at fine-tune epoch 18/30. It subsequently completed; final Testing accuracy is 78.98% (see completed result above).

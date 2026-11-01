# MRI candidate assessment — 2026-11-01

The existing BraTS-extended EfficientNetV2S candidate is now compatible with CORTIA
and verified separately. It is **not promoted** to the active application model.
Higher four-class accuracy comes with worse tumor/no-tumor label errors on the
same repository cohort.

## Comparison on exactly the same 314 images

| Measure | Active original-weight export | Experimental candidate |
| --- | ---: | ---: |
| Four-class accuracy | 75.48% | 80.89% |
| Macro F1 | 0.70665 | 0.79764 |
| Glioma recall | 29.8% (25/84) | 59.5% (50/84) |
| Meningioma recall | 99.1% (112/113) | 92.0% (104/113) |
| No-tumor recall | 98.8% (80/81) | 85.2% (69/81) |
| Pituitary recall | 55.6% (20/36) | 86.1% (31/36) |
| Tumor-labeled images predicted as no tumor | 23/233 | 25/233 |
| No-tumor images predicted as a tumor class | 1/81 | 12/81 |

The candidate corrects 39 previously wrong classifications and introduces 22 new
errors, for 17 more correct four-class labels overall. Some gains concern which
tumor class is selected, while tumor/no-tumor separation becomes worse. This does
not support an automatic replacement based on overall accuracy alone.

These are dataset-label comparisons, **not clinical performance estimates**. The
repository cohort has been reused during development. Test patient identifiers
are absent, and independent external generalization is unverified.

[Per-image candidate results](benchmarks/2026-11-01-mri-candidate-brats.json) ·
[Paired comparison](benchmarks/2026-11-01-mri-comparison.json)

## Implementation and artifact checks

- Imported model files only, with declared class order, hashes, preprocessing,
  repository revision context, training metadata and original unpromoted status.
- Source candidate input is RGB, bilinear 224×224, `/127.5 - 1`. The architecture
  includes its own rescaling. CORTIA applies this declared contract consistently
  during inference, export verification and benchmarking.
- Grad-CAM reconstructs visible RGB before blending its actual classifier saliency.
  Signed model inputs are not used directly as display pixels.
- A separate unoptimized float32 export agrees with Keras on all 314 winning
  classes. Maximum absolute probability difference is **0.000003472022**.
- Actual Grad-CAM succeeds on **314/314** benchmark images. This establishes
  execution, not whether highlighted regions are medically meaningful.
- Newly exported models discard inherited evaluation records. Evaluation-specific
  limitations are attached to the exact evaluated bundle, so source performance
  claims do not automatically become claims about a new export.

Candidate TFLite SHA-256:
`bea0d73e4a9a6e5be4e68fa87bca718d04c9d1c7b9a7c61d9e89548a132d64be`.

The source import lives in `models/mri-candidate-brats`; the separately verified
export lives in `models/mri-candidate-brats-float32`. The active local `.env`
continues to select the original-weight bundle `models/mri-float32`.

## Training provenance audit

The source experiment records manifest SHA-256
`22c5f0bb40975c4b3fadaf5eaf3facdcd9e16b9532117dd466eec1081f9bf0d0`.
The archived `evaluation-manifest.json` matches this byte-for-byte. The adjacent
`manifest.json` has different serialization but identical parsed JSON content.
Importer provenance now identifies the matching archive, instead of assuming one
filename. A missing recorded experiment hash is represented as `null` agreement,
which means it is unverified rather than a successful match.

File checks find:

| Recorded split | Recorded images | Available files with matching hashes | Unavailable files |
| --- | ---: | ---: | ---: |
| Training | 6,862 | 2,238 | 4,624 |
| Validation | 1,168 | 562 | 606 |
| Test | 314 | 314 | 0 |

The missing files come from the recorded Cheng and BraTS extra-data directories.
No copies of a representative missing filename were found in this workspace.
Training cannot be fully reproduced until these data are restored with matching
hashes or a new training protocol and dataset version are established.

Recorded split image hashes, known patient identifiers and validation-cluster keys
have zero observed overlap. However, all 314 test images lack patient identifiers;
some training images also lack grouping metadata. Zero known overlap does not prove
patient independence. The source experiment still records `promoted: false`.

[Compact provenance/data availability audit](benchmarks/2026-11-01-candidate-data-audit.json)

## Reproduce import, export and benchmark

Choose unused output paths; existing model bundles are never overwritten:

```bash
.venv/bin/python scripts/import_mri.py \
  --source /home/vinay/brain_health_monitor \
  --artifact-subdir model_candidate_eff_brats \
  --output models/mri-candidate-new

PYTHONPATH=backend .venv/bin/python -m cortia.mri.export \
  --source models/mri-candidate-new --output models/mri-candidate-new-float32 \
  --images /home/vinay/brain_health_monitor/dataset/no/N1.JPG \
    /home/vinay/brain_health_monitor/dataset/Testing/glioma_tumor/*.jpg \
    /home/vinay/brain_health_monitor/dataset/Testing/meningioma_tumor/*.jpg \
    /home/vinay/brain_health_monitor/dataset/Testing/no_tumor/*.jpg \
    /home/vinay/brain_health_monitor/dataset/Testing/pituitary_tumor/*.jpg

PYTHONPATH=backend .venv/bin/python backend/tests/benchmark_mri.py \
  --model-dir models/mri-candidate-new-float32 \
  --dataset /home/vinay/brain_health_monitor/dataset \
  --split /home/vinay/brain_health_monitor/model_candidate_eff_brats/evaluation-manifest.json \
  --output /tmp/cortia-candidate-new.json
```

Candidate browser verification uses isolated temporary application data:

```bash
cd frontend
CORTIA_MODEL_DIR=/home/vinay/cortia/models/mri-candidate-brats-float32 \
CORTIA_EXPECT_GRADCAM=1 CORTIA_BROWSER=/usr/bin/google-chrome-stable npm run test:e2e
```

## Other verified follow-up

The complete backend suite now has **77 passing tests**. The six browser cases pass
against both active and candidate bundles; the production build passes. Independent
read-only review finds no blocking defects.

Eight DICOM tests verify MR pixel normalization/inversion, rejection of unsupported
or corrupt inputs, flat-image rejection, and an actual repository MRI wrapped in a
test DICOM upload. The stored PNG drops the fixture's DICOM identity tags and retains
the original upload digest. These checks do not establish comprehensive deidentification
or removal of identifiers embedded in image pixels.

Remaining external requirements are unchanged: physical board testing, live AI
provider configuration, restored training data and appropriate independent validation.

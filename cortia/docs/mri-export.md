# MRI float32 export and Grad-CAM

The supplied TFLite artifact and original Keras weights disagree on probability
vectors. On `dataset/no/N1.JPG`, the supplied TFLite artifact assigns approximately
0.94818 to `no_tumor`, while Keras assigns approximately 0.85305. Attribution stays
unavailable for that original export. Relaxing the agreement check would explain
a different computation from the prediction being shown.

## Verified derived version

`models/mri-float32` contains a fresh float32 TFLite conversion of the original
`best_model.h5`. No training or weight changes occur. `models/mri` remains intact.
The ignored workspace `.env` selects the derived directory for local startup.
Fresh installations still default to the original imported bundle.

Nine real repository images were checked: N1.JPG plus two images from each of
the four `Testing` class folders. Every derived prediction agrees with Keras on
winning class; maximum absolute probability difference is below 0.000005.
Every checked image produces genuine Grad-CAM. This verifies conversion and
attribution execution only; it does not establish model accuracy or clinical value.

Subsequent full benchmarking checks 314 unique repository images: winning classes
agree with Keras for all images, maximum absolute probability difference is
0.00002486234, and actual Grad-CAM is available for 308 images. Six correctly
withhold attribution because no positive activation exists. Accuracy is 75.48%
with only 29.8% glioma recall; these known limitations now appear in the selected
bundle's manifest. See [benchmark findings and limits](completion-report.md).

Artifact identity, source hashes, runtime versions and conversion settings appear
in [manifest](../models/mri-float32/manifest.json). Per-image scores and hashes appear
in [verification](../models/mri-float32/verification.json).

New MRI reports identify the derived TFLite SHA-256. Previously saved reports retain
their original model hash, scores and attribution result. Scores can change between
versions because the new export follows Keras instead of the original TFLite export.
Do not treat those changes as changes in the uploaded image or person.

## Reproduce

Run from project root with the actual source artifacts and dataset available:

```bash
PYTHONPATH=backend .venv/bin/python -m cortia.mri.export \
  --source models/mri --output models/mri-float32-v2 \
  --images /path/to/dataset/no/N1.JPG \
    /path/to/dataset/Testing/glioma_tumor/*.jpg \
    /path/to/dataset/Testing/meningioma_tumor/*.jpg \
    /path/to/dataset/Testing/no_tumor/*.jpg \
    /path/to/dataset/Testing/pituitary_tumor/*.jpg
```

The command refuses existing output directories and validates source hashes before
conversion. It publishes a bundle only after every supplied image passes class
agreement and maximum absolute probability difference <=0.001, with at least one
usable Grad-CAM. Failed verification leaves no output bundle. This is a local,
single-operator conversion tool; do not run concurrent exporters to the same path.

Set `CORTIA_MODEL_DIR` in `.env` to the absolute output directory, then restart
`bash scripts/start.sh`. To return to the original export, remove that variable
or point it to `models/mri` using its absolute path.

Browser verification for a selected bundle:

```bash
cd frontend
CORTIA_MODEL_DIR=/absolute/path/to/cortia/models/mri-float32 \
CORTIA_EXPECT_GRADCAM=1 CORTIA_BROWSER=/usr/bin/google-chrome-stable npm run test:e2e
```

Per-image runtime integrity, score-agreement and positive-gradient checks still apply.
Some other images may have no valid attribution. Saliency is not lesion segmentation.

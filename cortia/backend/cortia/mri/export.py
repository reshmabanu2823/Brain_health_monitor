"""Derive a parity-checked float32 export without changing source model weights."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np

from .service import CLASSES, MRIService, validate_image
from .preprocessing import CONTRACTS, preprocess

PARITY_TOLERANCE = .001


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_bundle(source: Path, output: Path, images: list[Path]):
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError('Output already exists; choose a new model version directory')
    if not images:
        raise ValueError('At least one real verification image is required')
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest['classes'] != CLASSES or manifest['preprocessing'] not in CONTRACTS:
        raise ValueError('Unsupported source model contract')
    for name in ('best_model.h5', 'brain_tumor_model.tflite', 'class_indices.json'):
        path = source/name
        if not path.is_file() or sha256(path) != manifest['artifact_hashes'].get(name):
            raise ValueError('Source model integrity check failed: '+name)
    # Decode all inputs before expensive conversion; no application records are created.
    fixtures = [(Path(p), validate_image(Path(p).read_bytes(), Path(p).name)) for p in images]
    import tensorflow as tf
    model = tf.keras.models.load_model(source/'best_model.h5', compile=False)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = []
    converted = converter.convert()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cortia-mri-', dir=output.parent) as temporary:
        staging = Path(temporary)/'bundle'
        staging.mkdir()
        for name in ('best_model.h5', 'class_indices.json'):
            shutil.copyfile(source/name, staging/name)
        (staging/'brain_tumor_model.tflite').write_bytes(converted)
        derived = {**manifest, 'artifact_hashes': {
            name: sha256(staging/name)
            for name in ('best_model.h5', 'brain_tumor_model.tflite', 'class_indices.json')
        }, 'derivation': {
            'method': 'TFLiteConverter.from_keras_model; float32; optimizations=[]; no training',
            'source_artifact_hashes': manifest['artifact_hashes'],
            'tensorflow_version': tf.__version__,
            'keras_version': tf.keras.__version__,
            'parity_tolerance': PARITY_TOLERANCE,
        }}
        # Performance evidence belongs to the exact evaluated artifact, not new exports.
        derived.pop('evaluation',None)
        (staging/'manifest.json').write_text(json.dumps(derived, indent=2)+'\n')
        service = MRIService(staging)
        checked = []
        for path, image in fixtures:
            tensor = preprocess(image, manifest['preprocessing'])
            keras_scores = np.asarray(model(tensor, training=False))[0]
            prediction = service.predict(image)
            lite_scores = np.array([prediction['probabilities'][name] for name in CLASSES])
            if (keras_scores.shape != (4,) or not np.isfinite(keras_scores).all()
                    or np.any(keras_scores < 0) or not np.isclose(keras_scores.sum(), 1, atol=.001)):
                raise ValueError('Invalid source Keras probability distribution')
            difference = float(np.max(np.abs(keras_scores-lite_scores)))
            agreement = int(np.argmax(keras_scores)) == int(np.argmax(lite_scores))
            if not agreement or difference > PARITY_TOLERANCE:
                raise ValueError('Export parity verification failed for '+path.name)
            checked.append(dict(image=path.name, sha256=sha256(path),
                                keras_probabilities=keras_scores.tolist(),
                                tflite_probabilities=lite_scores.tolist(),
                                max_absolute_probability_difference=difference,
                                gradcam_available=prediction['explainability']['available']))
        if not any(item['gradcam_available'] for item in checked):
            raise ValueError('No verification image produced usable Grad-CAM')
        report = dict(verified_images=len(checked), class_agreement=True,
                      max_absolute_probability_difference=max(item['max_absolute_probability_difference'] for item in checked),
                      model_sha256=derived['artifact_hashes']['brain_tumor_model.tflite'],
                      limitation='Software export parity and saliency only; not clinical performance or generalization.',
                      images=checked)
        (staging/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
        if output.exists():
            raise FileExistsError('Output appeared during verification; refusing to replace it')
        staging.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--images', type=Path, nargs='+', required=True)
    args = parser.parse_args()
    report = export_bundle(args.source, args.output, args.images)
    print(json.dumps({key: value for key, value in report.items() if key != 'images'}, indent=2))


if __name__ == '__main__':
    main()

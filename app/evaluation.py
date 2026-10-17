"""Model evaluation without an additional scikit-learn dependency."""
import json
import platform
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import numpy as np
from .artifacts import CLASS_NAMES, sha256_file
from .dataset import build_manifest
from .inference import BrainTumorModel
from .preprocessing import read_mri_file, preprocess_image


def classification_metrics(y_true, y_pred, class_names=None):
    names = class_names or CLASS_NAMES
    truth, predictions = np.asarray(y_true, dtype=int), np.asarray(y_pred, dtype=int)
    if truth.ndim != 1 or truth.shape != predictions.shape or not truth.size or np.any(truth < 0) or np.any(truth >= len(names)) or np.any(predictions < 0) or np.any(predictions >= len(names)):
        raise ValueError('Invalid classification labels')
    confusion = np.zeros((len(names), len(names)), dtype=np.int64)
    np.add.at(confusion, (truth, predictions), 1)
    per_class = {}
    for i, name in enumerate(names):
        true_positive = int(confusion[i, i])
        support = int(confusion[i].sum())
        predicted = int(confusion[:, i].sum())
        precision = true_positive / predicted if predicted else 0
        recall = true_positive / support if support else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        per_class[name] = {'precision': precision, 'recall': recall, 'f1': f1, 'support': support}
    return {'sample_count': int(truth.size), 'accuracy': float(np.trace(confusion) / truth.size), 'macro_f1': float(np.mean([r['f1'] for r in per_class.values()])), 'per_class': per_class, 'confusion_matrix': confusion.tolist()}


def dependency_versions():
    versions = {'python': platform.python_version()}
    for package in ['tensorflow-cpu', 'tensorflow', 'keras', 'numpy', 'Pillow', 'pydicom']:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            pass
    return versions


def evaluate_artifacts(model_dir, dataset_dir, manifest=None, include_keras=True):
    manifest = manifest or build_manifest(dataset_dir)
    directory = Path(model_dir)
    runtime = BrainTumorModel(directory)
    root = Path(dataset_dir)
    keras_model = None
    if include_keras:
        import tensorflow as tf
        keras_model = tf.keras.models.load_model(directory / 'best_model.h5', compile=False)
    truth, lite_outputs, keras_outputs = [], [], []
    for record in manifest['test']:
        image, _ = read_mri_file(root / record['path'])
        _, _, probabilities, _, _ = runtime.predict(image)
        lite_outputs.append(probabilities)
        truth.append(runtime.class_names.index(record['class_name']))
        if keras_model is not None:
            tensor, _ = preprocess_image(image, runtime.contract['preprocessing'])
            output = np.asarray(keras_model(tensor, training=False))[0]
            if runtime.contract['output'] == 'logits':
                output = np.exp(output - output.max())
                output /= output.sum()
            if output.shape != (4,) or not np.isfinite(output).all():
                raise ValueError('Invalid Keras evaluation output')
            keras_outputs.append(output)
    lite_outputs = np.asarray(lite_outputs)
    result = {'schema_version': 1, 'model_sha256': sha256_file(directory / 'brain_tumor_model.tflite'), 'classes': runtime.class_names, 'preprocessing': runtime.contract['preprocessing'], 'seed': manifest['seed'], 'split_counts': {split: len(manifest[split]) for split in ('train', 'validation', 'test')}, 'excluded': manifest['excluded'], 'limitation': manifest['limitation'], 'training_provenance': 'Bundled model training may have used overlapping test images; this evaluation does not establish that its test set was unseen.' if runtime.contract.get('legacy') else 'Candidate trained on recorded train/validation manifest; test images excluded.', 'dependencies': dependency_versions(), 'tflite': classification_metrics(truth, lite_outputs.argmax(axis=1), runtime.class_names)}
    if keras_model is not None:
        keras_outputs = np.asarray(keras_outputs)
        difference = np.abs(lite_outputs - keras_outputs)
        result.update({'keras_model_sha256': sha256_file(directory / 'best_model.h5'), 'keras': classification_metrics(truth, keras_outputs.argmax(axis=1), runtime.class_names), 'export_parity': {'prediction_agreement': float(np.mean(lite_outputs.argmax(axis=1) == keras_outputs.argmax(axis=1))), 'mean_absolute_probability_difference': float(difference.mean()), 'max_absolute_probability_difference': float(difference.max())}})
    return result


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')

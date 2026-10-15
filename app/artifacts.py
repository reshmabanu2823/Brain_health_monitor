"""Versioned preprocessing and label contract for model artifacts."""
import hashlib
import json
from pathlib import Path

CLASS_NAMES = ['glioma_tumor', 'meningioma_tumor', 'no_tumor', 'pituitary_tumor']
DISPLAY_LABELS = {'glioma_tumor': 'Glioma Tumor', 'meningioma_tumor': 'Meningioma Tumor', 'no_tumor': 'No Tumor', 'pituitary_tumor': 'Pituitary Tumor'}
PROBABILITY_LABELS = {'glioma_tumor': 'Glioma', 'meningioma_tumor': 'Meningioma', 'no_tumor': 'No Tumor', 'pituitary_tumor': 'Pituitary'}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(model_dir):
    directory = Path(model_dir)
    mapping_path = directory / 'class_indices.json'
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else dict(zip(CLASS_NAMES, range(4)))
    if set(mapping) != set(CLASS_NAMES) or any(type(v) is not int for v in mapping.values()) or sorted(mapping.values()) != list(range(4)):
        raise ValueError('Invalid class mapping: expected four unique contiguous class indices')
    ordered = sorted(mapping, key=mapping.get)
    metadata_path = directory / 'metadata.json'
    if not metadata_path.exists():
        return {'schema_version': 1, 'preprocessing': 'legacy_rgb_0_1', 'image_size': [224, 224], 'classes': ordered, 'output': 'probabilities', 'legacy': True}
    metadata = json.loads(metadata_path.read_text())
    if metadata.get('schema_version') != 1 or metadata.get('preprocessing') not in ('legacy_rgb_0_1', 'mobilenet_v2'):
        raise ValueError('Unsupported model preprocessing contract')
    if metadata.get('image_size') != [224, 224] or metadata.get('classes') != ordered or metadata.get('output') not in ('probabilities', 'logits'):
        raise ValueError('Model shape, classes or output contract is incompatible')
    for filename, expected in metadata.get('artifact_hashes', {}).items():
        if filename not in ('brain_tumor_model.tflite', 'best_model.h5'):
            raise ValueError('Unknown artifact in metadata')
        if sha256_file(directory / filename) != expected:
            raise ValueError(f'Model artifact hash mismatch: {filename}')
    return metadata

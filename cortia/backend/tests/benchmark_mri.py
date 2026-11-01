"""Offline MRI benchmark; never writes application data or claims clinical validation."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np

from cortia.mri.service import CLASSES, MRIService, validate_image
from cortia.mri.preprocessing import preprocess


def classification_metrics(labels, predictions):
    if not labels or len(labels) != len(predictions):
        raise ValueError('Expected paired nonempty labels and predictions')
    matrix = np.zeros((4,4), dtype=int)
    for actual, predicted in zip(labels, predictions):
        if actual not in range(4) or predicted not in range(4):
            raise ValueError('Invalid class index')
        matrix[actual,predicted] += 1
    per_class = {}
    for index, name in enumerate(CLASSES):
        correct = int(matrix[index,index])
        predicted = int(matrix[:,index].sum())
        support = int(matrix[index,:].sum())
        precision = correct/predicted if predicted else 0.
        recall = correct/support if support else 0.
        f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.
        per_class[name] = dict(precision=precision, recall=recall, f1=f1, support=support)
    return dict(sample_count=len(labels), accuracy=float(np.trace(matrix)/len(labels)),
                macro_f1=sum(item['f1'] for item in per_class.values())/4,
                per_class=per_class, confusion_matrix=matrix.tolist())


def verify_records(dataset, manifest):
    root = Path(dataset).resolve()
    if manifest['classes'] != CLASSES or not manifest['test']:
        raise ValueError('Invalid classes or empty test set')
    reference = {record['sha256'] for split in ('train','validation') for record in manifest[split]}
    seen, verified = set(), []
    for record in manifest['test']:
        path = (root/record['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Image path escapes dataset')
        label = record['class_index']
        if type(label) is not int or label not in range(4) or record['class_name'] != CLASSES[label]:
            raise ValueError('Inconsistent class label')
        digest = record['sha256']
        if digest in reference:
            raise ValueError('Test image overlaps recorded train/validation splits')
        if digest in seen:
            raise ValueError('Duplicate test image hash')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Image hash mismatch')
        seen.add(digest)
        verified.append((record,path))
    return verified


def benchmark(model_dir, dataset, split_file):
    import tensorflow as tf
    split_file = Path(split_file)
    split = json.loads(split_file.read_text())
    records = verify_records(dataset, split)
    service = MRIService(model_dir)
    status = service.status()
    if not status['available']:
        raise ValueError('MRI model unavailable')
    manifest = status['manifest']
    keras_path = Path(model_dir)/'best_model.h5'
    if hashlib.sha256(keras_path.read_bytes()).hexdigest() != manifest['artifact_hashes']['best_model.h5']:
        raise ValueError('Keras integrity mismatch')
    keras = tf.keras.models.load_model(keras_path, compile=False)
    rows, labels, predictions, differences, agreements = [], [], [], [], []
    started = time.perf_counter()
    for index, (record,path) in enumerate(records, 1):
        image = validate_image(path.read_bytes(), path.name)
        result = service.predict(image)
        scores = [result['probabilities'][name] for name in CLASSES]
        tensor = preprocess(image,manifest['preprocessing'])
        original = np.asarray(keras(tensor, training=False))[0]
        difference = float(np.max(np.abs(original-np.asarray(scores))))
        predicted = CLASSES.index(result['label'])
        agreements.append(int(np.argmax(original)) == predicted)
        differences.append(difference)
        labels.append(record['class_index'])
        predictions.append(predicted)
        rows.append(dict(path=record['path'], sha256=record['sha256'], actual=record['class_name'],
                         predicted=result['label'], probabilities=result['probabilities'],
                         keras_probabilities=original.tolist(), max_absolute_probability_difference=difference,
                         gradcam_available=result['explainability']['available'],
                         gradcam_reason=result['explainability'].get('reason')))
        if index % 25 == 0 or index == len(records):
            print(f'Checked {index}/{len(records)} images', flush=True)
    return dict(schema_version=1, classes=CLASSES, model_manifest=manifest,
                split_manifest_sha256=hashlib.sha256(split_file.read_bytes()).hexdigest(),
                split_counts={name:len(split[name]) for name in ('train','validation','test')},
                exclusions=split['excluded'], metrics=classification_metrics(labels,predictions),
                parity=dict(class_agreement=sum(agreements)/len(agreements),
                            max_absolute_probability_difference=max(differences)),
                gradcam_available=sum(row['gradcam_available'] for row in rows),
                elapsed_seconds=time.perf_counter()-started,
                runtime=dict(python=platform.python_version(),tensorflow=tf.__version__,numpy=np.__version__),
                limitations=[
                    'Repository dataset benchmark only; not clinical validation.',
                    ('Recorded candidate training metadata is available; independent patient-level training/test separation is not established.'
                     if manifest.get('experimental_candidate') else
                     'Original model training provenance unknown: these test images may have been seen during original training.'),
                    'Test hashes are unique and disjoint from recorded train/validation splits; patient independence is unknown.',
                    'The repository test set has been reused during development; this is not a new external validation cohort.',
                    'Accuracy on these labeled images does not establish generalization, calibration, or diagnostic safety.',
                ], images=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--split', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Choose a new report path')
    report = benchmark(args.model_dir,args.dataset,args.split)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as file:
        json.dump(report,file,indent=2,allow_nan=False)
        file.write('\n')
    print(json.dumps({key:report[key] for key in ('metrics','parity','gradcam_available','elapsed_seconds')},indent=2))


if __name__ == '__main__':
    main()

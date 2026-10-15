"""Explicit subject-disjoint splits; same windows/features as real-time inference.

Input manifest labels require an independently validated experimental protocol.
No public EEG data are bundled or implicitly downloaded. Exported live ADC-count
recordings require task labels, subject IDs and the documented manifest first.
"""
from dataclasses import asdict
import json
from pathlib import Path
import platform
import numpy as np
import joblib
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix,
                             precision_recall_fscore_support, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .model import digest
from .signal import SignalConfig, FEATURE_NAMES, analyze, segment
from .storage import utc_now


def load_manifest(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    for field in ('task', 'provenance', 'license'):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError(f'Manifest needs {field}')
    if manifest.get('units') != 'adc_counts':
        raise ValueError('Live-compatible training requires adc_counts; do not silently convert public microvolt datasets')
    config = SignalConfig(**{'sample_rate': manifest['sample_rate'], **manifest.get('preprocessing', {})})
    if config.sample_rate != manifest['sample_rate']:
        raise ValueError('Conflicting manifest sample rates')
    subjects, paths, hashes = {}, set(), set()
    records = manifest.get('recordings', [])
    for r in records:
        if r.get('split') not in ('train', 'validation', 'test') or not r.get('subject') or not isinstance(r.get('label'), str) or not r['label'].strip():
            raise ValueError('Every recording needs subject, label and explicit split')
        source = (path.parent/r['path']).resolve()
        sha = digest(source)
        if source in paths or sha in hashes:
            raise ValueError('Duplicate recording path/content; remove repeated recordings')
        paths.add(source); hashes.add(sha)
        if r['subject'] in subjects and subjects[r['subject']] != r['split']:
            raise ValueError('A subject occurs in multiple splits')
        subjects[r['subject']] = r['split']
        r['_path'] = source
        r['_sha256'] = sha
    for split in ('train','validation','test'):
        if not any(r['split'] == split for r in records):
            raise ValueError('Train, validation and held-out test recordings required')
    return manifest, config


def metrics(model, x, y, labels):
    predicted = model.predict(x)
    precision, recall, f1, support = precision_recall_fscore_support(y, predicted, labels=labels, zero_division=0)
    result = {'sample_count': len(y), 'accuracy': float(accuracy_score(y,predicted)),
              'balanced_accuracy': float(balanced_accuracy_score(y,predicted)),
              'macro_f1': float(np.mean(f1)), 'confusion_matrix': confusion_matrix(y,predicted,labels=labels).tolist(),
              'labels': list(labels), 'per_class': {str(k): {'precision': float(p), 'recall': float(r), 'f1': float(f), 'support': int(s)}
              for k,p,r,f,s in zip(labels,precision,recall,f1,support)},
              'roc_auc': None}
    if len(set(y)) == len(labels):
        prob = model.predict_proba(x)
        if len(labels) == 2:
            result['roc_auc'] = float(roc_auc_score(np.asarray(y)==labels[1], prob[:,1]))
        elif len(labels) > 2:
            result['roc_auc'] = float(roc_auc_score(y,prob,labels=labels,multi_class='ovr',average='macro'))
    return result


def write_confusion_svg(path, report):
    # Standalone experimental-result artifact; no plotting dependency necessary.
    from html import escape
    labels = report['labels']; matrix = report['confusion_matrix']
    width = 180 + 100*len(labels); height = 100 + 65*len(labels)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img" aria-label="Held-out test confusion matrix">', '<rect width="100%" height="100%" fill="white"/>', '<text x="12" y="22">Test confusion matrix: rows true, columns predicted</text>']
    for i,label in enumerate(labels):
        parts.append(f'<text x="{180+i*100}" y="55">{escape(label)}</text>')
        parts.append(f'<text x="8" y="{95+i*65}">{escape(label)}</text>')
        for j,value in enumerate(matrix[i]):
            parts.append(f'<rect x="{170+j*100}" y="{65+i*65}" width="95" height="60" fill="#e4edf2"/><text x="{205+j*100}" y="{100+i*65}">{value}</text>')
    path.write_text(''.join(parts)+'</svg>')


def train(manifest_path, output_dir):
    out = Path(output_dir)
    if out.exists():
        raise ValueError('Use a new output directory to preserve prior model/evaluation')
    manifest, config = load_manifest(manifest_path)
    data = {s: {'x': [], 'y': [], 'subjects': set(), 'recordings': 0} for s in ('train','validation','test')}
    rejected = []
    recording_audit = []
    normalized_hashes = set()
    for record in manifest['recordings']:
        values = np.genfromtxt(record['_path'], delimiter=',', names=True)
        if values.ndim != 1 or values.dtype.names != ('timestamp_s','value'):
            raise ValueError('CSV requires exactly timestamp_s,value columns and multiple samples')
        # Canonical numeric hash catches formatting-only duplicate recordings.
        canonical = np.column_stack([values['timestamp_s'], values['value']]).astype('<f8').tobytes()
        import hashlib
        sha = hashlib.sha256(canonical).hexdigest()
        if sha in normalized_hashes:
            raise ValueError('Duplicate numeric recording content')
        normalized_hashes.add(sha)
        recording_audit.append({'recording':record['path'],'split':record['split'],'label':record['label'],
            'samples':len(values),'duration_seconds':float(values['timestamp_s'][-1]-values['timestamp_s'][0]) if np.isfinite(values['timestamp_s']).all() else None,
            'nonfinite_values':int(np.sum(~np.isfinite(values['value']))),
            'discarded_tail_samples':len(values)%config.input_samples})
        item = data[record['split']]
        item['recordings'] += 1
        item['subjects'].add(record['subject'])
        for start,end in segment(len(values), config.input_samples, config.input_samples):
            result = analyze(values['timestamp_s'][start:end], values['value'][start:end], config)
            if result['valid'] and all(v is not None for v in result['features']):
                item['x'].append(result['features']); item['y'].append(record['label'])
            else:
                rejected.append({'recording': record['path'], 'start':start, 'reasons':result.get('reasons') or ['Unsupported bands']})
    labels = sorted(set(data['train']['y']))
    if len(labels)<2:
        raise ValueError('Need at least two training labels after signal validation')
    for split,item in data.items():
        if set(item['y']) != set(labels):
            raise ValueError(f'{split} needs usable windows from every training class')
    x,y = data['train']['x'],data['train']['y']
    candidates = {'dummy': DummyClassifier(strategy='prior'),
                  'logistic_regression': make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,class_weight='balanced',random_state=42)),
                  'random_forest': RandomForestClassifier(n_estimators=100,max_depth=6,min_samples_leaf=2,class_weight='balanced',random_state=42,n_jobs=1)}
    validation = {}
    for name,model in candidates.items():
        model.fit(x,y)
        validation[name] = metrics(model,data['validation']['x'],data['validation']['y'],labels)
    selected = max(candidates,key=lambda name:validation[name]['balanced_accuracy'])
    model = candidates[selected]
    # No refitting on validation and no selection using the final test scores.
    report = {'selected': selected, 'selection_metric':'validation balanced_accuracy', 'validation':validation,
              'test':metrics(model,data['test']['x'],data['test']['y'],labels),
              'baseline_test':metrics(candidates['dummy'],data['test']['x'],data['test']['y'],labels),
              'splits':{s:{'windows':len(d['y']),'subjects':len(d['subjects']),'recordings':d['recordings'],
                           'class_counts':{label:d['y'].count(label) for label in labels}} for s,d in data.items()},
              'recording_audit':recording_audit, 'rejected_windows': rejected, 'limitation':'Subject-disjoint manifest, nonoverlapping windows. Window metrics remain correlated within subjects; domain transfer to Maker UNO requires external validation.'}
    out.mkdir(parents=True)
    joblib.dump(model,out/'model.joblib')
    meta = {'schema_version':1, 'version':utc_now(), 'name':selected, 'task':manifest['task'],
            'units':'adc_counts','feature_names':list(FEATURE_NAMES),'labels':labels,'preprocessing':asdict(config),
            'model_sha256':digest(out/'model.joblib'),'sklearn_version':sklearn.__version__,
            'python_version':platform.python_version(), 'provenance':manifest['provenance'], 'license':manifest['license'],
            'dependencies': {'numpy': np.__version__, 'scipy': __import__('scipy').__version__, 'joblib': joblib.__version__},
            'training':{'seed':42,'selection':'validation balanced_accuracy','window_hop_samples':config.input_samples}}
    (out/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=False))
    (out/'evaluation.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    clean_manifest = {**manifest,'recordings':[{k:v for k,v in r.items() if k!='_path'} for r in manifest['recordings']]}
    (out/'manifest.json').write_text(json.dumps(clean_manifest,indent=2))
    write_confusion_svg(out/'confusion_matrix.svg',report['test'])
    return report

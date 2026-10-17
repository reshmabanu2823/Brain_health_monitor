"""Load trusted local sklearn artifacts only; never accept uploads/pickle paths."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import joblib
import numpy as np
import sklearn
from .signal import FEATURE_NAMES, SignalConfig


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


class EEGModel:
    def __init__(self, directory):
        self.estimator = None
        self.info = {'available': False, 'reason': 'No compatible EEG artifact installed; labeled subject-wise data required'}
        directory = Path(directory)
        try:
            meta = json.loads((directory/'metadata.json').read_text())
            if meta['schema_version'] != 1 or meta['feature_names'] != list(FEATURE_NAMES) or meta['units'] != 'adc_counts':
                raise ValueError('Incompatible feature schema or units')
            SignalConfig(**meta['preprocessing'])
            if meta['sklearn_version'] != sklearn.__version__ or meta['python_version'] != platform.python_version():
                raise ValueError('Artifact dependency versions differ; retrain in this environment')
            if meta['model_sha256'] != digest(directory/'model.joblib'):
                raise ValueError('EEG artifact checksum mismatch')
            estimator = joblib.load(directory/'model.joblib')
            if list(estimator.classes_) != meta['labels'] or estimator.n_features_in_ != len(FEATURE_NAMES):
                raise ValueError('EEG model labels or feature dimensions mismatch')
            self.estimator = estimator
            self.info = {**meta, 'available': True,
                         'limitation': 'Experimental task classifier; probabilities are not calibrated reliability or diagnosis'}
        except Exception:
            # Error text deliberately omits local paths and pickle exception detail.
            self.info['reason'] = 'EEG model absent or incompatible; inspect artifact and environment'

    def predict(self, analysis, config):
        if self.estimator is None:
            return {'available': False, 'reason': self.info['reason']}
        if not analysis.get('valid') or asdict(config) != self.info['preprocessing'] or analysis.get('feature_names') != list(FEATURE_NAMES):
            return {'available': False, 'reason': 'Signal or preprocessing differs from training contract'}
        x = np.asarray(analysis['features'], dtype=float)
        if x.shape != (len(FEATURE_NAMES),) or not np.isfinite(x).all():
            return {'available': False, 'reason': 'Features unavailable or invalid'}
        probabilities = self.estimator.predict_proba(x[None])[0]
        index = int(np.argmax(probabilities))
        return {'available': True, 'label': str(self.estimator.classes_[index]),
                'probabilities': {str(k): float(v) for k, v in zip(self.estimator.classes_, probabilities)},
                'score': float(probabilities[index]), 'model_version': self.info['version'],
                'task': self.info['task'], 'limitation': self.info['limitation']}

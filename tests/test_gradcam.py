import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app'))
from gradcam import generate_gradcam_heatmap, extract_tumor_metrics

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, 'model')
SAMPLE_DIR = os.path.join(BASE_DIR, 'static', 'samples')

def test_extract_tumor_metrics():
    # Synthetic heatmap with a known hotspot
    heat = np.zeros((224, 224), dtype=np.float32)
    heat[80:120, 80:120] = 0.95
    metrics = extract_tumor_metrics(heat)
    assert 'tumor_area_pct' in metrics
    assert metrics['tumor_area_pct'] > 0
    assert metrics['peak_saliency'] >= 0.95
    assert metrics['bbox'] is not None

def test_generate_gradcam_heatmap_with_metrics():
    sample_path = os.path.join(SAMPLE_DIR, 'glioma.jpg')
    overlay, metrics = generate_gradcam_heatmap(sample_path, MODEL_DIR, return_metrics=True)
    assert overlay is not None
    assert overlay.shape == (224, 224, 3)
    assert isinstance(metrics, dict)
    assert 'tumor_area_pct' in metrics
    assert 'peak_saliency' in metrics

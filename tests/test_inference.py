import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app'))
from inference import BrainTumorModel, CLASS_LABELS, read_mri_file

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, 'model')
SAMPLE_DIR = os.path.join(BASE_DIR, 'static', 'samples')

def test_model_initialization():
    model = BrainTumorModel(MODEL_DIR)
    assert model is not None
    assert model.model_dir == MODEL_DIR

def test_preprocessing():
    model = BrainTumorModel(MODEL_DIR)
    sample_path = os.path.join(SAMPLE_DIR, 'glioma.jpg')
    img_tensor, norm_array, meta = model.preprocess(sample_path)
    assert img_tensor.shape == (1, 224, 224, 3)
    assert norm_array.shape == (224, 224, 3)
    assert float(np.max(norm_array)) <= 1.0
    assert float(np.min(norm_array)) >= 0.0

def test_predict_output_structure():
    model = BrainTumorModel(MODEL_DIR)
    sample_path = os.path.join(SAMPLE_DIR, 'notumor.jpg')
    label, confidence, probs, img_array, meta = model.predict(sample_path)
    assert label in CLASS_LABELS.values()
    assert 0.0 <= confidence <= 100.0
    assert len(probs) == 4
    assert np.isclose(np.sum(probs), 1.0, atol=1e-3)

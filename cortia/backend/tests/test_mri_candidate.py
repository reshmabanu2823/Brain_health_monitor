import base64
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from cortia.mri.service import CLASSES, MRIService, validate_image

ROOT = Path(__file__).resolve().parents[2]


def test_real_candidate_uses_declared_signed_input_and_actual_gradcam():
    directory = ROOT/'models/mri-candidate-brats-float32'
    source = Path('/home/vinay/brain_health_monitor/dataset/no/N1.JPG')
    if not directory.exists() or not source.exists():
        pytest.skip('Separate candidate bundle and original MRI fixture required')
    import tensorflow as tf
    image = validate_image(source.read_bytes(),source.name)
    # Independently reproduce the recorded source contract, without CORTIA's helper.
    tensor = np.asarray(image.resize((224,224),Image.Resampling.BILINEAR),dtype=np.float32)[None,...]/127.5-1
    model = tf.keras.models.load_model(directory/'best_model.h5',compile=False)
    expected = np.asarray(model(tensor,training=False))[0]
    result = MRIService(directory).predict(image)
    assert result['label'] == CLASSES[int(np.argmax(expected))]
    assert [result['probabilities'][name] for name in CLASSES] == pytest.approx(expected.tolist(),abs=.001)
    assert '/127.5 - 1' in result['preprocessing']
    assert result['explainability']['available'] is True
    png = base64.b64decode(result['explainability']['overlay'].split(',',1)[1])
    with Image.open(BytesIO(png)) as overlay:
        assert overlay.format == 'PNG'
        assert overlay.size == (224,224)
        overlay.verify()
    assert any('Experimental' in limitation for limitation in result['limitations'])

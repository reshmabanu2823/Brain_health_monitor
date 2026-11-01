from pathlib import Path
from io import BytesIO
import numpy as np
import pytest
from PIL import Image
from cortia.mri.service import MRIService, validate_image

ROOT = Path(__file__).resolve().parents[2]

def test_missing_model_reports_unavailable(tmp_path):
    service = MRIService(tmp_path)
    assert service.status()['available'] is False
    with pytest.raises(RuntimeError):
        service.predict(Image.new('RGB',(224,224)))


def test_invalid_upload():
    with pytest.raises(ValueError):
        validate_image(b'not an image', 'bad.png')
    buffer = BytesIO()
    Image.new('RGB',(20,20)).save(buffer,format='PNG')
    assert validate_image(buffer.getvalue(), 'anything.png').size == (20,20)


def test_real_artifact_prediction():
    service = MRIService(ROOT/'models/mri')
    if not service.status()['available']:
        pytest.skip('MRI artifacts not imported')
    source = Path('/home/vinay/brain_health_monitor/dataset/no/N1.JPG')
    if not source.exists():
        pytest.skip('External real MRI fixture absent')
    result = service.predict(validate_image(source.read_bytes(), source.name))
    assert result['label'] in ['glioma_tumor','meningioma_tumor','no_tumor','pituitary_tumor']
    assert sum(result['probabilities'].values()) == pytest.approx(1,abs=.001)
    assert len(result['model_sha256']) == 64
    assert result['kind'] == 'model_prediction'
    assert result['explainability']['available'] is False or result['explainability']['method'] == 'Grad-CAM'

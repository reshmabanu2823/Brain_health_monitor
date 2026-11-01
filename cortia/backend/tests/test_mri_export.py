import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from cortia.mri.export import export_bundle
from cortia.mri.service import MRIService, validate_image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'models/mri'
IMAGE = Path('/home/vinay/brain_health_monitor/dataset/no/N1.JPG')


def test_export_requires_verification_images(tmp_path):
    with pytest.raises(ValueError, match='verification image'):
        export_bundle(SOURCE, tmp_path/'derived', [])
    assert not (tmp_path/'derived').exists()


def test_export_never_overwrites_existing_output(tmp_path):
    output = tmp_path/'derived'
    output.mkdir()
    (output/'keep').write_text('existing model')
    with pytest.raises(FileExistsError):
        export_bundle(SOURCE, output, [IMAGE])
    assert (output/'keep').read_text() == 'existing model'


def test_export_rejects_changed_source_before_publishing(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    manifest = json.loads((SOURCE/'manifest.json').read_text())
    (source/'manifest.json').write_text(json.dumps(manifest))
    (source/'best_model.h5').write_bytes(b'changed weights')
    with pytest.raises(ValueError, match='integrity'):
        export_bundle(source, tmp_path/'derived', [IMAGE])
    assert not (tmp_path/'derived').exists()


def test_export_does_not_publish_mismatching_converter_output(tmp_path, monkeypatch):
    if not IMAGE.exists() or not (SOURCE/'best_model.h5').exists():
        pytest.skip('Original MRI artifacts and image required')
    import tensorflow as tf
    # Exercise the real verifier with the known mismatching original export.
    converter = SimpleNamespace(convert=lambda: (SOURCE/'brain_tumor_model.tflite').read_bytes())
    monkeypatch.setattr(tf.lite.TFLiteConverter, 'from_keras_model', lambda model: converter)
    output = tmp_path/'derived'
    with pytest.raises(ValueError, match='parity'):
        export_bundle(SOURCE, output, [IMAGE])
    assert not output.exists()
    assert not list(tmp_path.glob('.cortia-mri-*'))


def test_export_does_not_publish_when_all_gradcam_checks_fail(tmp_path, monkeypatch):
    derived = ROOT/'models/mri-float32/brain_tumor_model.tflite'
    if not IMAGE.exists() or not derived.exists():
        pytest.skip('Verified float32 MRI artifact and original image required')
    import tensorflow as tf
    import cortia.mri.explain as attribution
    converter = SimpleNamespace(convert=lambda: derived.read_bytes())
    monkeypatch.setattr(tf.lite.TFLiteConverter, 'from_keras_model', lambda model: converter)
    monkeypatch.setattr(attribution, 'explain', lambda *args: {'available':False,'reason':'Test gradient unavailable'})
    output = tmp_path/'derived'
    with pytest.raises(ValueError, match='Grad-CAM'):
        export_bundle(SOURCE, output, [IMAGE])
    assert not output.exists()
    assert not list(tmp_path.glob('.cortia-mri-*'))


def test_new_export_does_not_inherit_source_specific_evaluation(tmp_path,monkeypatch):
    derived = ROOT/'models/mri-float32/brain_tumor_model.tflite'
    if not IMAGE.exists() or not derived.exists():
        pytest.skip('Verified MRI artifacts and source image required')
    source = tmp_path/'source'
    shutil.copytree(SOURCE,source)
    manifest = json.loads((source/'manifest.json').read_text())
    manifest['evaluation'] = {'accuracy':1,'report_sha256':'previous artifact evaluation'}
    (source/'manifest.json').write_text(json.dumps(manifest))
    import tensorflow as tf
    converter = SimpleNamespace(convert=lambda: derived.read_bytes())
    monkeypatch.setattr(tf.lite.TFLiteConverter,'from_keras_model',lambda model:converter)
    output = tmp_path/'derived'
    export_bundle(source,output,[IMAGE])
    assert 'evaluation' not in json.loads((output/'manifest.json').read_text())
    assert json.loads((source/'manifest.json').read_text())['evaluation']['accuracy'] == 1


def test_float_export_preserves_original_weights_and_enables_real_gradcam(tmp_path):
    if not IMAGE.exists() or not (SOURCE/'best_model.h5').exists():
        pytest.skip('Original MRI artifacts and image required')
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in SOURCE.iterdir() if p.is_file()}
    output = tmp_path/'derived'
    report = export_bundle(SOURCE, output, [IMAGE])
    assert report['verified_images'] == 1
    assert report['max_absolute_probability_difference'] <= .001
    assert report['class_agreement'] is True
    assert report['images'][0]['gradcam_available'] is True
    manifest = json.loads((output/'manifest.json').read_text())
    assert manifest['derivation']['source_artifact_hashes'] == json.loads((SOURCE/'manifest.json').read_text())['artifact_hashes']
    assert manifest['artifact_hashes']['best_model.h5'] == before['best_model.h5']
    result = MRIService(output).predict(validate_image(IMAGE.read_bytes(), IMAGE.name))
    assert result['label'] == 'no_tumor'
    assert result['explainability']['available'] is True
    assert result['explainability']['overlay'].startswith('data:image/png;base64,')
    assert result['model_sha256'] != before['brain_tumor_model.tflite']
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in SOURCE.iterdir() if p.is_file()}

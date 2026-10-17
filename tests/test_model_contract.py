import builtins
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from PIL import Image
from inference import BrainTumorModel, read_mri_file


class Interpreter:
    def __init__(self, output, dtype=np.float32, quantization=(0.0, 0)):
        self.output = np.array([output], dtype=dtype)
        self.tensor = None
        self.running = False
        self.collided = False
        self.dtype = dtype
        self.quantization = quantization

    def allocate_tensors(self):
        pass

    def get_input_details(self):
        return [dict(index=0, shape=np.array([1, 224, 224, 3]), dtype=self.dtype, quantization=self.quantization)]

    def get_output_details(self):
        return [dict(index=1, shape=np.array([1, 4]), dtype=self.dtype, quantization=self.quantization)]

    def set_tensor(self, index, tensor):
        if self.running:
            self.collided = True
        self.tensor = tensor.copy()

    def invoke(self):
        self.running = True
        time.sleep(0.005)
        self.running = False

    def get_tensor(self, index):
        return self.output.copy()


def fake_model(tmp_path, monkeypatch, interpreter):
    (tmp_path / 'class_indices.json').write_text(json.dumps({'glioma_tumor': 0, 'meningioma_tumor': 1, 'no_tumor': 2, 'pituitary_tumor': 3}))
    def load(self):
        self.interpreter = interpreter
        self.input_details = interpreter.get_input_details()
        self.output_details = interpreter.get_output_details()
    monkeypatch.setattr(BrainTumorModel, '_load_model', load)
    return BrainTumorModel(str(tmp_path))


def test_preserves_softmax_probabilities(tmp_path, monkeypatch):
    model = fake_model(tmp_path, monkeypatch, Interpreter([0.84, 0.08, 0.04, 0.04]))
    _, confidence, probs, _, _ = model.predict(Image.new('RGB', (224, 224)))
    assert np.allclose(probs, [0.84, 0.08, 0.04, 0.04])
    assert confidence == pytest.approx(84)


def test_legacy_preprocessing_keeps_rgb(tmp_path, monkeypatch):
    model = fake_model(tmp_path, monkeypatch, Interpreter([1, 0, 0, 0]))
    tensor, _, _ = model.preprocess(Image.new('RGB', (224, 224), (255, 0, 128)))
    assert np.allclose(tensor[0, 0, 0], [1, 0, 128 / 255])


def test_quantized_input_and_output(tmp_path, monkeypatch):
    runtime = Interpreter([84, 8, 4, 4], np.uint8, (0.01, 0))
    model = fake_model(tmp_path, monkeypatch, runtime)
    _, confidence, probs, _, _ = model.predict(Image.new('RGB', (224, 224), (255, 0, 0)))
    assert runtime.tensor.dtype == np.uint8
    assert runtime.tensor[0, 0, 0, 0] == 100
    assert confidence == pytest.approx(84)
    assert np.allclose(probs, [0.84, 0.08, 0.04, 0.04])


def test_interpreter_is_serialized(tmp_path, monkeypatch):
    runtime = Interpreter([1, 0, 0, 0])
    model = fake_model(tmp_path, monkeypatch, runtime)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(model.predict, [Image.new('RGB', (224, 224))] * 20))
    assert not runtime.collided


def test_missing_runtime_fails(tmp_path, monkeypatch):
    (tmp_path / 'brain_tumor_model.tflite').write_bytes(b'placeholder')
    real_import = builtins.__import__
    def unavailable(name, *args, **kwargs):
        if name.startswith(('tensorflow', 'tflite_runtime')):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', unavailable)
    with pytest.raises(RuntimeError, match='runtime'):
        BrainTumorModel(str(tmp_path))


@pytest.mark.parametrize('output', [[float('nan'), 0, 0, 1], [-1, 1, 1, 0], [1, 1, 1, 1]])
def test_rejects_invalid_probabilities(tmp_path, monkeypatch, output):
    model = fake_model(tmp_path, monkeypatch, Interpreter(output))
    with pytest.raises(ValueError):
        model.predict(Image.new('RGB', (224, 224)))


def test_new_preprocessing_contract(tmp_path):
    from artifacts import load_contract
    from preprocessing import preprocess_image
    (tmp_path / 'metadata.json').write_text(json.dumps({'schema_version': 1, 'preprocessing': 'mobilenet_v2', 'image_size': [224, 224], 'classes': ['glioma_tumor', 'meningioma_tumor', 'no_tumor', 'pituitary_tumor'], 'output': 'probabilities'}))
    contract = load_contract(tmp_path)
    tensor, _ = preprocess_image(Image.new('RGB', (224, 224), (255, 0, 128)), contract['preprocessing'])
    assert np.allclose(tensor[0, 0, 0], [1, -1, 128 / 127.5 - 1], atol=1e-7)


def test_invalid_class_mapping(tmp_path):
    from artifacts import load_contract
    (tmp_path / 'class_indices.json').write_text('{"glioma_tumor": 0, "meningioma_tumor": 0}')
    with pytest.raises(ValueError, match='class'):
        load_contract(tmp_path)


def dicom_file(tmp_path, frames=1):
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(str(tmp_path / 'scan.dcm'), {}, file_meta=meta, preamble=b'\0' * 128)
    ds.Rows, ds.Columns = 2, 2
    ds.Modality = 'MR'
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = 'MONOCHROME1'
    ds.BitsAllocated = ds.BitsStored = 16
    ds.HighBit, ds.PixelRepresentation = 15, 0
    ds.NumberOfFrames = frames
    ds.PixelData = np.tile(np.array([0, 10, 20, 30], dtype=np.uint16), frames).tobytes()
    ds.save_as(ds.filename, enforce_file_format=True)
    return ds.filename


def test_dicom_monochrome1_inverted(tmp_path):
    image, meta = read_mri_file(dicom_file(tmp_path))
    assert np.array(image)[0, 0, 0] == 255
    assert np.array(image)[1, 1, 0] == 0
    assert meta['magnetic_field_strength'] is None


def test_dicom_multiframe_rejected(tmp_path):
    with pytest.raises(ValueError, match='single-frame'):
        read_mri_file(dicom_file(tmp_path, frames=2))

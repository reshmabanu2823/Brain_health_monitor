"""Fresh adapter for original, hash-verified four-class MRI model."""
import hashlib
import io
import json
import threading
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from .preprocessing import CONTRACTS, preprocess, description

CLASSES = ['glioma_tumor','meningioma_tumor','no_tumor','pituitary_tumor']


def validate_image(content: bytes, filename: str):
    if len(content) > 10*1024*1024 or not content:
        raise ValueError('Upload a non-empty image up to 10 MB')
    if Path(filename).suffix.lower() in ('.dcm','.dicom'):
        try:
            import pydicom
            ds = pydicom.dcmread(io.BytesIO(content))
            if str(ds.Modality) != 'MR' or int(getattr(ds,'NumberOfFrames',1)) != 1 or int(ds.SamplesPerPixel) != 1:
                raise ValueError('Only single-frame grayscale MR DICOM supported')
            if int(ds.Rows)*int(ds.Columns) > 16_000_000:
                raise ValueError('Image exceeds 16 megapixels')
            photo = str(ds.PhotometricInterpretation)
            if photo not in ('MONOCHROME1','MONOCHROME2'):
                raise ValueError('Unsupported DICOM photometric interpretation')
            values = ds.pixel_array.astype(float) * float(getattr(ds,'RescaleSlope',1)) + float(getattr(ds,'RescaleIntercept',0))
            if values.ndim != 2 or not np.isfinite(values).all() or np.ptp(values) <= 0:
                raise ValueError('Invalid DICOM pixel values')
            values = (values-values.min())/np.ptp(values)
            if photo == 'MONOCHROME1':
                values = 1-values
            return Image.fromarray(np.rint(values*255).astype('uint8')).convert('RGB')
        except ImportError as exc:
            raise ValueError('DICOM support requires optional pydicom dependency') from exc
        except Exception as exc:
            raise ValueError('Invalid or unsupported single-frame MR DICOM') from exc
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format not in ('PNG','JPEG','WEBP','BMP','TIFF') or getattr(source,'n_frames',1) != 1:
                raise ValueError('Supported formats: single-frame PNG, JPEG, WEBP, BMP, TIFF')
            if source.width*source.height > 16_000_000:
                raise ValueError('Image exceeds 16 megapixels')
            return ImageOps.exif_transpose(source).convert('RGB')
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
        raise ValueError('Invalid or oversized image') from exc


class MRIService:
    def __init__(self, model_dir):
        self.directory = Path(model_dir)
        self.lock = threading.Lock()
        self.interpreter = None
        self.manifest = None
        self.error = None

    def _load(self):
        if self.interpreter is not None:
            return
        manifest = json.loads((self.directory/'manifest.json').read_text())
        if manifest['classes'] != CLASSES or manifest['preprocessing'] not in CONTRACTS:
            raise ValueError('Unsupported MRI label or preprocessing contract')
        mapping = json.loads((self.directory/'class_indices.json').read_text())
        if mapping != dict(zip(CLASSES,range(4))):
            raise ValueError('Class order differs from source model')
        for name in ('brain_tumor_model.tflite','class_indices.json'):
            if hashlib.sha256((self.directory/name).read_bytes()).hexdigest() != manifest['artifact_hashes'][name]:
                raise ValueError('MRI model artifact integrity mismatch')
        try:
            from ai_edge_litert.interpreter import Interpreter
        except ImportError:
            try:
                from tensorflow import lite
                Interpreter = lite.Interpreter
            except ImportError as exc:
                raise RuntimeError('Install TensorFlow for actual MRI inference') from exc
        interpreter = Interpreter(model_path=str(self.directory/'brain_tumor_model.tflite'),num_threads=2)
        interpreter.allocate_tensors()
        inputs, outputs = interpreter.get_input_details(), interpreter.get_output_details()
        if len(inputs) != 1 or len(outputs) != 1 or list(inputs[0]['shape']) != [1,224,224,3] or list(outputs[0]['shape']) != [1,4]:
            raise ValueError('MRI model tensor contract mismatch')
        self.input, self.output = inputs[0],outputs[0]
        self.manifest, self.interpreter = manifest,interpreter

    def status(self):
        with self.lock:
            try:
                self._load()
                return dict(available=True, classes=CLASSES, manifest=self.manifest,
                            explainability_artifact_present=(self.directory/'best_model.h5').exists())
            except Exception as exc:
                self.error = str(exc)
                return dict(available=False, reason='MRI model or runtime unavailable. Import artifacts and install MRI dependencies.', classes=CLASSES)

    def predict(self, image):
        with self.lock:
            try:
                self._load()
            except Exception as exc:
                raise RuntimeError('MRI model unavailable or integrity check failed') from exc
            tensor = preprocess(image, self.manifest['preprocessing'])
            dtype = np.dtype(self.input['dtype'])
            if dtype.kind in 'iu':
                scale,zero = self.input['quantization']
                if scale <= 0:
                    raise RuntimeError('Invalid model quantization')
                limits = np.iinfo(dtype)
                value = np.clip(np.rint(tensor/scale+zero),limits.min,limits.max).astype(dtype)
            else:
                value = tensor.astype(dtype)
            self.interpreter.set_tensor(self.input['index'],value)
            self.interpreter.invoke()
            scores = self.interpreter.get_tensor(self.output['index']).astype(float).reshape(-1)
            if np.dtype(self.output['dtype']).kind in 'iu':
                scale,zero = self.output['quantization']
                scores = (scores-zero)*scale
            if scores.shape != (4,) or not np.isfinite(scores).all() or np.any(scores < 0) or not np.isclose(scores.sum(),1,atol=.03):
                raise RuntimeError('Invalid MRI model probability distribution')
            scores /= scores.sum()
            winner = int(np.argmax(scores))
            from .explain import explain
            explanation = explain(self.directory, self.manifest, tensor, scores)
            return dict(kind='model_prediction',label=CLASSES[winner],probabilities=dict(zip(CLASSES,scores.tolist())),
                        model_sha256=self.manifest['artifact_hashes']['brain_tumor_model.tflite'],
                        preprocessing=description(self.manifest['preprocessing']),
                        explainability=explanation,
                        limitations=self.manifest['limitations']+self.manifest.get('evaluation',{}).get('limitations',[])
                        +['Raster validity cannot verify that an uploaded picture is an MRI.'])

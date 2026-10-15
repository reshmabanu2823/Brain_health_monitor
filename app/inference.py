"""Validated and serialized TFLite inference; no synthetic predictions."""
import os
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import threading
import numpy as np
try:
    from .artifacts import CLASS_NAMES, DISPLAY_LABELS, PROBABILITY_LABELS, load_contract
    from .preprocessing import IMG_SIZE, decode_input, preprocess_image, read_mri_file
except ImportError:
    from artifacts import CLASS_NAMES, DISPLAY_LABELS, PROBABILITY_LABELS, load_contract
    from preprocessing import IMG_SIZE, decode_input, preprocess_image, read_mri_file

CLASS_LABELS = {i: DISPLAY_LABELS[name] for i, name in enumerate(CLASS_NAMES)}
CLASS_COLORS = {'Glioma Tumor': '#FF4444', 'Meningioma Tumor': '#FF8800', 'No Tumor': '#00CC66', 'Pituitary Tumor': '#A855F7'}


def _interpreter(path):
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            try:
                from tensorflow.lite.python.interpreter import Interpreter
            except ImportError as exc:
                raise RuntimeError('No TFLite runtime installed; install TensorFlow, ai-edge-litert or tflite-runtime') from exc
    return Interpreter(model_path=path, num_threads=2)


def _quantize(tensor, details):
    dtype = np.dtype(details['dtype'])
    if dtype.kind in 'iu':
        scale, zero = details['quantization']
        if scale <= 0:
            raise ValueError('Invalid quantized tensor scale')
        limits = np.iinfo(dtype)
        return np.clip(np.rint(tensor / scale + zero), limits.min, limits.max).astype(dtype)
    return tensor.astype(dtype)


def _dequantize(tensor, details):
    values = np.asarray(tensor, dtype=np.float32)
    if np.dtype(details['dtype']).kind in 'iu':
        scale, zero = details['quantization']
        if scale <= 0:
            raise ValueError('Invalid quantized output scale')
        values = (values - zero) * scale
    return values


class BrainTumorModel:
    def __init__(self, model_dir):
        self.model_dir = str(model_dir)
        self.contract = load_contract(model_dir)
        self.class_names = self.contract['classes']
        self.labels = [DISPLAY_LABELS[name] for name in self.class_names]
        self.probability_labels = [PROBABILITY_LABELS[name] for name in self.class_names]
        self._lock = threading.Lock()
        self.interpreter = None
        self._load_model()

    def _load_model(self):
        path = os.path.join(self.model_dir, 'brain_tumor_model.tflite')
        if not os.path.isfile(path):
            raise FileNotFoundError(f'Model not found: {path}')
        self.interpreter = _interpreter(path)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        if len(self.input_details) != 1 or len(self.output_details) != 1:
            raise ValueError('Expected one input and one output')
        if tuple(self.input_details[0]['shape']) != (1, 224, 224, 3) or tuple(self.output_details[0]['shape']) != (1, 4):
            raise ValueError('Incompatible model tensor shapes')

    def preprocess(self, image_input):
        image, metadata = decode_input(image_input)
        tensor, array = preprocess_image(image, self.contract['preprocessing'])
        return tensor, array, metadata

    def predict(self, image_input):
        tensor, array, metadata = self.preprocess(image_input)
        if self.interpreter is None:
            raise RuntimeError('TFLite runtime is unavailable')
        with self._lock:
            self.interpreter.set_tensor(self.input_details[0]['index'], _quantize(tensor, self.input_details[0]))
            self.interpreter.invoke()
            output = self.interpreter.get_tensor(self.output_details[0]['index'])
        probabilities = _dequantize(output, self.output_details[0]).reshape(-1)
        if probabilities.shape != (4,) or not np.isfinite(probabilities).all():
            raise ValueError('Invalid model output')
        if self.contract['output'] == 'logits':
            probabilities = np.exp(probabilities - probabilities.max())
            probabilities /= probabilities.sum()
        else:
            scale = self.output_details[0].get('quantization', (0, 0))[0]
            tolerance = max(1e-3, 4 * scale)
            if np.any(probabilities < 0) or np.any(probabilities > 1 + tolerance) or not np.isclose(probabilities.sum(), 1, atol=tolerance):
                raise ValueError('Invalid probability distribution')
            probabilities = probabilities / probabilities.sum()
        index = int(probabilities.argmax())
        return self.labels[index], float(probabilities[index]) * 100, probabilities, array, metadata

    @staticmethod
    def is_tumor(label):
        return label != 'No Tumor'

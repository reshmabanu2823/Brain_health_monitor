"""Actual classifier Grad-CAM; unavailable explanations never use substitute maps."""
import logging
import threading
from pathlib import Path
import numpy as np
from PIL import Image
import cv2
try:
    from .artifacts import load_contract
    from .preprocessing import decode_input, preprocess_image
except ImportError:
    from artifacts import load_contract
    from preprocessing import decode_input, preprocess_image

log = logging.getLogger(__name__)
_cached_model = None
_cached_model_dir = None
_cache_lock = threading.Lock()
_gradient_lock = threading.Lock()


def preload_gradcam_model(model_dir):
    return _get_keras_model(model_dir)


def _get_keras_model(model_dir):
    global _cached_model, _cached_model_dir
    directory = str(Path(model_dir).resolve())
    with _cache_lock:
        if _cached_model is not None and _cached_model_dir == directory:
            return _cached_model
        try:
            import tensorflow as tf
            load_contract(model_dir)
            _cached_model = tf.keras.models.load_model(Path(model_dir) / 'best_model.h5', compile=False)
            _cached_model_dir = directory
            return _cached_model
        except Exception:
            log.exception('Grad-CAM model is unavailable')
            return None


def extract_tumor_metrics(heatmap_raw):
    heat = cv2.resize(np.asarray(heatmap_raw, dtype=np.float32), (224, 224))
    if not np.isfinite(heat).all():
        raise ValueError('Invalid heatmap')
    heat = np.clip(heat, 0, 1)
    mask = heat > .52
    rows, columns = np.where(mask)
    bbox = center = None
    if mask.sum() > 25:
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
        bbox = dict(x=int(x), y=int(y), w=int(w), h=int(h))
        center = dict(x=int(np.rint(columns.mean())), y=int(np.rint(rows.mean())))
    return {'tumor_area_pct': round(float(mask.mean()) * 100, 2), 'bbox': bbox, 'center': center, 'peak_saliency': round(float(heat.max()), 4), 'measurement': 'saliency_coverage', 'coordinate_space': [224, 224], 'threshold': .52}


def _gradient_heatmap(model, tensor, class_index):
    import tensorflow as tf
    # The bundled model and training CLI expose convolutional layers directly.
    layer = next((layer for layer in reversed(model.layers) if isinstance(layer, tf.keras.layers.Conv2D)), None)
    if layer is None:
        raise ValueError('No connected convolutional layer available for Grad-CAM')
    gradient_model = tf.keras.Model(model.inputs, [layer.output, model.output])
    with tf.GradientTape() as tape:
        features, predictions = gradient_model(tf.convert_to_tensor(tensor), training=False)
        index = int(tf.argmax(predictions[0])) if class_index is None else int(class_index)
        if not 0 <= index < 4:
            raise ValueError('Invalid explanation class')
        score = predictions[:, index]
    gradients = tape.gradient(score, features)
    if gradients is None:
        raise ValueError('Disconnected Grad-CAM gradient')
    weights = tf.reduce_mean(gradients, axis=(0, 1, 2))
    heat = tf.nn.relu(tf.reduce_sum(features[0] * weights, axis=-1)).numpy()
    maximum = float(np.max(heat))
    if not np.isfinite(heat).all() or maximum <= 0:
        raise ValueError('No positive Grad-CAM activation')
    return heat / maximum


def generate_gradcam_heatmap(image_input, model_dir, return_metrics=False, class_index=None):
    try:
        image, _ = decode_input(image_input)
        contract = load_contract(model_dir)
        tensor, _ = preprocess_image(image, contract['preprocessing'])
        model = _get_keras_model(model_dir)
        if model is None:
            return (None, {}) if return_metrics else None
        with _gradient_lock:
            heat = _gradient_heatmap(model, tensor, class_index)
        heat_resized = cv2.resize(heat, (224, 224))
        color = cv2.cvtColor(cv2.applyColorMap(np.uint8(np.clip(heat_resized, 0, 1) * 255), cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB)
        original = np.asarray(image.resize((224, 224), Image.Resampling.BILINEAR))
        overlay = (.55 * original + .45 * color).astype(np.uint8)
        return (overlay, extract_tumor_metrics(heat)) if return_metrics else overlay
    except Exception:
        log.exception('Grad-CAM unavailable for this prediction')
        return (None, {}) if return_metrics else None

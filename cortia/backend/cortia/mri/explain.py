"""Grad-CAM from the paired original Keras model, never image-intensity substitutes."""
import base64
import hashlib
import io
import threading
from pathlib import Path
import numpy as np
from PIL import Image
from .preprocessing import display_pixels

_lock = threading.Lock()
_cache = {}


def explain(directory: Path, manifest: dict, tensor, probabilities):
    try:
        import tensorflow as tf
    except ImportError:
        return dict(available=False,reason='Optional TensorFlow runtime is not installed. No substitute heatmap generated.')
    try:
        with _lock:
            path = directory/'best_model.h5'
            expected = manifest['artifact_hashes'].get('best_model.h5')
            if expected is None or not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                return dict(available=False,reason='Matching Keras model unavailable or failed integrity check.')
            if expected not in _cache:
                _cache[expected] = tf.keras.models.load_model(path,compile=False)
            model = _cache[expected]
            keras_probabilities = np.asarray(model(tensor,training=False))[0]
            if int(np.argmax(keras_probabilities)) != int(np.argmax(probabilities)) or not np.allclose(keras_probabilities,probabilities,atol=.05):
                return dict(available=False,reason='Keras/TFLite predictions do not agree; attribution withheld.')
            conv = next(layer for layer in reversed(model.layers) if isinstance(layer,tf.keras.layers.Conv2D))
            gradient_model = tf.keras.Model(model.inputs,[conv.output,model.output])
            winner = int(np.argmax(probabilities))
            with tf.GradientTape() as tape:
                activation, prediction = gradient_model(tf.convert_to_tensor(tensor),training=False)
                target = prediction[:,winner]
            gradients = tape.gradient(target,activation)
            if gradients is None:
                raise ValueError('Disconnected gradients')
            weights = tf.reduce_mean(gradients,axis=(0,1,2))
            heat = tf.nn.relu(tf.reduce_sum(activation[0]*weights,axis=-1)).numpy()
            if not np.isfinite(heat).all() or heat.max() <= 0:
                return dict(available=False,reason='No positive Grad-CAM activation for this prediction.')
            heat /= heat.max()
            heat = np.asarray(Image.fromarray(heat).resize((224,224),Image.Resampling.BILINEAR))
            color = np.stack([heat,np.maximum(0,1-np.abs(heat-.5)*2),1-heat],axis=-1)
            pixels = display_pixels(tensor,manifest['preprocessing'])
            overlay = np.uint8(np.clip(.6*pixels+.4*color,0,1)*255)
            buffer = io.BytesIO()
            Image.fromarray(overlay).save(buffer,format='PNG')
            return dict(available=True,method='Grad-CAM',class_index=winner,
                        overlay='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode(),
                        limitation='Classifier saliency shows influential regions; not lesion location, area or segmentation.')
    except Exception:
        return dict(available=False,reason='Grad-CAM unavailable for this model graph or prediction.')

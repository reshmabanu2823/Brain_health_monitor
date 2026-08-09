import numpy as np
import os

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

# ── Cache the Keras model so it loads only once ───────────────────
_cached_model = None
_cached_model_dir = None

def _get_keras_model(model_dir):
    global _cached_model, _cached_model_dir
    if _cached_model is not None and _cached_model_dir == model_dir:
        return _cached_model
    try:
        import tensorflow as tf
        model_path = os.path.join(model_dir, 'best_model.h5')
        if not os.path.exists(model_path):
            print("[GradCAM] Keras model not found")
            return None
        print("[GradCAM] Loading Keras model (first time only)...")
        _cached_model     = tf.keras.models.load_model(model_path)
        _cached_model_dir = model_dir
        print("[GradCAM] Keras model cached — future calls will be instant")
        return _cached_model
    except Exception as e:
        print(f"[GradCAM] Model load error: {e}")
        return None

def generate_gradcam_heatmap(image_path, model_dir):
    if not HAS_CV2:
        return _simple_heatmap(image_path)
    try:
        import tensorflow as tf
        from PIL import Image

        model = _get_keras_model(model_dir)
        if model is None:
            return _simple_heatmap(image_path)

        img = Image.open(image_path).convert('RGB')
        img = img.resize((224, 224), Image.LANCZOS)
        img_array  = np.array(img, dtype=np.float32) / 255.0
        img_tensor = np.expand_dims(img_array, axis=0)

        last_conv_layer = None
        for layer in reversed(model.layers):
            if isinstance(layer, tf.keras.layers.Conv2D):
                last_conv_layer = layer.name
                break
        if last_conv_layer is None:
            for layer in reversed(model.layers):
                if hasattr(layer, 'layers'):
                    for sub in reversed(layer.layers):
                        if isinstance(sub, tf.keras.layers.Conv2D):
                            last_conv_layer = sub.name
                            break
                if last_conv_layer:
                    break

        if last_conv_layer is None:
            return _simple_heatmap(image_path)

        grad_model = tf.keras.models.Model(
            inputs=model.inputs,
            outputs=[model.get_layer(last_conv_layer).output, model.output]
        )

        with tf.GradientTape() as tape:
            inputs        = tf.cast(img_tensor, tf.float32)
            conv_outputs, predictions = grad_model(inputs)
            pred_index    = tf.argmax(predictions[0])
            class_channel = predictions[:, pred_index]

        grads        = tape.gradient(class_channel, conv_outputs)
        pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        conv_outputs = conv_outputs[0]
        heatmap      = conv_outputs @ pooled_grads[..., tf.newaxis]
        heatmap      = tf.squeeze(heatmap)
        heatmap      = tf.maximum(heatmap, 0) / (tf.math.reduce_max(heatmap) + 1e-8)
        heatmap      = heatmap.numpy()

        heatmap_resized = cv2.resize(heatmap, (224, 224))
        heatmap_colored = cv2.applyColorMap(np.uint8(255 * heatmap_resized), cv2.COLORMAP_JET)
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

        original = np.uint8(255 * img_array)
        overlay  = cv2.addWeighted(original, 0.55, heatmap_colored, 0.45, 0)

        print("[GradCAM] Heatmap generated successfully")
        return overlay

    except Exception as e:
        print(f"[GradCAM] Error: {e}")
        return _simple_heatmap(image_path)

def _simple_heatmap(image_path):
    try:
        from PIL import Image
        img = Image.open(image_path).convert('RGB')
        img = img.resize((224, 224), Image.LANCZOS)
        return np.array(img)
    except:
        return None

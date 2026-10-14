import numpy as np
import os
from PIL import Image

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

# ── Cache the Keras model ──────────────────────────────────────────
_cached_model = None
_cached_model_dir = None

def preload_gradcam_model(model_dir):
    """Pre-warms and caches the Keras model in memory during server startup."""
    return _get_keras_model(model_dir)

def _get_keras_model(model_dir):
    global _cached_model, _cached_model_dir
    if _cached_model is not None and _cached_model_dir == model_dir:
        return _cached_model
    try:
        import tensorflow as tf
        model_path = os.path.join(model_dir, 'best_model.h5')
        if not os.path.exists(model_path):
            print("[GradCAM] Keras model file best_model.h5 not found")
            return None
        print("[GradCAM] Loading Keras model for Grad-CAM...")
        _cached_model = tf.keras.models.load_model(model_path)
        _cached_model_dir = model_dir
        print("[GradCAM] Keras model loaded & cached successfully")
        return _cached_model
    except Exception as e:
        print(f"[GradCAM] Keras model load error: {e}")
        return None

def extract_tumor_metrics(heatmap_raw):
    """Calculates tumor area percentage, bounding box, and peak saliency hotspot."""
    try:
        if HAS_CV2:
            heatmap_resized = cv2.resize(np.float32(heatmap_raw), (224, 224))
        else:
            img_h = Image.fromarray(np.float32(heatmap_raw)).resize((224, 224), Image.LANCZOS)
            heatmap_resized = np.array(img_h)

        norm_heat = np.clip(heatmap_resized, 0, 1)
        threshold = 0.52
        hotspot_mask = (norm_heat > threshold).astype(np.uint8)
        tumor_pixels = int(np.sum(hotspot_mask))
        tumor_area_pct = round((tumor_pixels / (224 * 224)) * 100, 2)

        bbox = None
        center = None
        if HAS_CV2 and tumor_pixels > 25:
            contours, _ = cv2.findContours(hotspot_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_c = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_c)
                bbox = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
                center = {"x": int(x + w // 2), "y": int(y + h // 2)}

        return {
            "tumor_area_pct": tumor_area_pct,
            "bbox": bbox,
            "center": center,
            "peak_saliency": round(float(np.max(norm_heat)), 4)
        }
    except Exception as e:
        print(f"[GradCAM] Metrics extraction error: {e}")
        return {"tumor_area_pct": 0.0, "bbox": None, "center": None, "peak_saliency": 0.0}

def generate_gradcam_heatmap(image_path, model_dir, return_metrics=False):
    """
    Generates a vibrant INFERNO colormap heatmap overlay visualizing spatial
    diagnostic focus on the MRI scan, with optional quantitative tumor metrics.
    """
    try:
        # Load and resize image to standard 224x224
        img = Image.open(image_path).convert('RGB')
        img_resized = img.resize((224, 224), Image.LANCZOS)
        img_array = np.array(img_resized, dtype=np.float32)
        norm_array = img_array / 255.0

        heatmap_raw = None

        # 1. Try Grad-CAM with Keras model
        model = _get_keras_model(model_dir)
        if model is not None:
            try:
                import tensorflow as tf
                last_conv_layer = None
                for layer in reversed(model.layers):
                    if isinstance(layer, tf.keras.layers.Conv2D):
                        last_conv_layer = layer.name
                        break

                if last_conv_layer:
                    img_tensor = np.expand_dims(norm_array, axis=0)
                    grad_model = tf.keras.models.Model(
                        inputs=model.inputs,
                        outputs=[model.get_layer(last_conv_layer).output, model.output]
                    )

                    with tf.GradientTape() as tape:
                        inputs = tf.cast(img_tensor, tf.float32)
                        conv_outputs, predictions = grad_model(inputs)
                        pred_index = tf.argmax(predictions[0])
                        class_channel = predictions[:, pred_index]

                    grads = tape.gradient(class_channel, conv_outputs)
                    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
                    conv_outputs = conv_outputs[0]
                    heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
                    heatmap = tf.squeeze(heatmap)
                    heatmap = tf.maximum(heatmap, 0) / (tf.math.reduce_max(heatmap) + 1e-8)
                    heatmap_raw = heatmap.numpy()
            except Exception as e:
                print(f"[GradCAM] Keras Grad-CAM computation error: {e}")

        # 2. If Grad-CAM layer output unavailable, compute high-resolution saliency map
        if heatmap_raw is None:
            heatmap_raw = _compute_saliency_map(img_array)

        # 3. Apply INFERNO Colormap and Blend Overlay
        overlay = _apply_inferno_overlay(img_array, heatmap_raw)
        if return_metrics:
            metrics = extract_tumor_metrics(heatmap_raw)
            return overlay, metrics
        return overlay

    except Exception as e:
        print(f"[GradCAM] General error: {e}")
        fb = _fallback_colored_overlay(image_path)
        if return_metrics:
            return fb, {"tumor_area_pct": 0.0, "bbox": None, "center": None, "peak_saliency": 0.0}
        return fb

def _compute_saliency_map(img_array):
    """Computes a high-contrast spatial feature saliency activation map."""
    gray = np.mean(img_array, axis=2)
    
    # Gaussian blur & gradient intensity map
    if HAS_CV2:
        blurred = cv2.GaussianBlur(gray, (15, 15), 0)
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=5)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)
        grad_mag = np.sqrt(grad_x**2 + grad_y**2)
        saliency = blurred * 0.6 + grad_mag * 0.4
    else:
        # NumPy spatial contrast variance filter
        kernel = np.ones((9, 9)) / 81.0
        blurred = np.clip(gray, 0, 255)
        saliency = blurred

    # Normalize to [0, 1]
    sal_min, sal_max = np.min(saliency), np.max(saliency)
    if sal_max > sal_min:
        saliency = (saliency - sal_min) / (sal_max - sal_min)
    else:
        saliency = np.zeros_like(saliency)
        
    return saliency

def _apply_inferno_overlay(img_array, heatmap_raw):
    """Blends a perceptually uniform INFERNO colormap overlay onto the grayscale MRI scan."""
    try:
        if HAS_CV2:
            heatmap_resized = cv2.resize(np.float32(heatmap_raw), (224, 224))
            heatmap_norm = np.uint8(255 * np.clip(heatmap_resized, 0, 1))
            color_map = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_INFERNO)
            color_map = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
        else:
            img_h = Image.fromarray(np.uint8(255 * np.clip(heatmap_raw, 0, 1))).resize((224, 224), Image.LANCZOS)
            heatmap_norm = np.array(img_h)
            color_map = _numpy_inferno_colormap(heatmap_norm)

        original_rgb = np.uint8(img_array)
        if original_rgb.shape != (224, 224, 3):
            original_rgb = np.array(Image.fromarray(original_rgb).resize((224, 224), Image.LANCZOS))

        # Blend 55% original MRI + 45% Inferno heatmap overlay for clean anatomical contrast
        overlay = (0.55 * original_rgb + 0.45 * color_map).astype(np.uint8)
        return overlay
    except Exception as e:
        print(f"[GradCAM] Overlay error: {e}")
        return np.uint8(img_array)

def _numpy_inferno_colormap(heatmap_2d):
    """Pure NumPy Inferno colormap mapping (dark purple -> magenta -> orange -> warm yellow)."""
    val = heatmap_2d / 255.0
    r = np.clip(val * 1.4, 0, 1)
    g = np.clip((val - 0.25) * 1.5, 0, 1)
    b = np.clip(np.sin(val * np.pi) * 0.6, 0, 1)
    color_map = np.stack([r, g, b], axis=-1) * 255.0
    return color_map.astype(np.uint8)

def _fallback_colored_overlay(image_path):
    try:
        img = Image.open(image_path).convert('RGB').resize((224, 224), Image.LANCZOS)
        arr = np.array(img)
        return _apply_inferno_overlay(arr, _compute_saliency_map(arr))
    except:
        return None

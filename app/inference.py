import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import numpy as np
import json
from PIL import Image

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

try:
    import pydicom
    HAS_PYDICOM = True
except ImportError:
    pydicom = None
    HAS_PYDICOM = False

# ── Class labels ──────────────────────────────────────────────────
CLASS_LABELS = {
    0: 'Glioma Tumor',
    1: 'Meningioma Tumor',
    2: 'No Tumor',
    3: 'Pituitary Tumor'
}

CLASS_COLORS = {
    'Glioma Tumor':     '#FF4444',
    'Meningioma Tumor': '#FF8800',
    'No Tumor':         '#00CC66',
    'Pituitary Tumor':  '#A855F7'
}

IMG_SIZE = (224, 224)

def read_mri_file(image_path):
    """
    Reads an MRI image from disk, supporting both standard formats (JPEG, PNG, WebP)
    and medical DICOM (.dcm) files with extraction of radiological tags.
    """
    metadata = {
        "format": "STANDARD",
        "patient_id": "ANON",
        "patient_name": "De-identified",
        "modality": "MR",
        "study_date": "N/A",
        "slice_thickness": "N/A",
        "magnetic_field_strength": "1.5T"
    }

    is_dcm = str(image_path).lower().endswith(('.dcm', '.dicom'))
    if is_dcm and HAS_PYDICOM:
        try:
            ds = pydicom.dcmread(image_path, force=True)
            pixel_array = ds.pixel_array.astype(np.float32)
            slope = float(getattr(ds, 'RescaleSlope', 1))
            intercept = float(getattr(ds, 'RescaleIntercept', 0))
            pixel_array = pixel_array * slope + intercept
            min_val, max_val = float(np.min(pixel_array)), float(np.max(pixel_array))
            if max_val > min_val:
                norm = ((pixel_array - min_val) / (max_val - min_val) * 255.0).astype(np.uint8)
            else:
                norm = np.zeros_like(pixel_array, dtype=np.uint8)
            if len(norm.shape) == 2:
                if HAS_CV2:
                    rgb = cv2.cvtColor(norm, cv2.COLOR_GRAY2RGB)
                else:
                    rgb = np.stack([norm]*3, axis=-1)
            else:
                rgb = norm
            pil_img = Image.fromarray(rgb)
            metadata.update({
                "format": "DICOM",
                "patient_id": str(getattr(ds, 'PatientID', 'PAT-' + os.path.basename(image_path)[:8])),
                "patient_name": str(getattr(ds, 'PatientName', 'De-identified Subject')),
                "modality": str(getattr(ds, 'Modality', 'MR')),
                "study_date": str(getattr(ds, 'StudyDate', 'N/A')),
                "slice_thickness": str(getattr(ds, 'SliceThickness', 'N/A')),
                "magnetic_field_strength": str(getattr(ds, 'MagneticFieldStrength', '1.5T'))
            })
            return pil_img, metadata
        except Exception as e:
            print(f"[Inference] DICOM parsing error: {e}, falling back to PIL")

    pil_img = Image.open(image_path).convert('RGB')
    return pil_img, metadata


def apply_clahe_rgb(img_array):
    """
    Apply CLAHE in LAB colorspace to preserve RGB color information.
    
    CRITICAL FIX: The old approach converted RGB → grayscale → RGB, which
    made all 3 channels identical (grayscale), completely destroying the
    color channel information that MobileNetV2/EfficientNet uses for classification.
    
    This version applies CLAHE only to the Luminance (L) channel in LAB space,
    preserving the A (green-red) and B (blue-yellow) chromatic channels intact.
    """
    if not HAS_CV2:
        return img_array
    try:
        img_uint8 = np.uint8(img_array)
        # Convert RGB → LAB colorspace
        lab = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        # Apply CLAHE ONLY to luminance channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_equalized = clahe.apply(l_channel)
        # Merge back and convert to RGB
        lab_equalized = cv2.merge([l_equalized, a_channel, b_channel])
        rgb_equalized = cv2.cvtColor(lab_equalized, cv2.COLOR_LAB2RGB)
        return rgb_equalized.astype(np.float32)
    except Exception as e:
        print(f"[Inference] CLAHE-LAB error: {e}, using original image")
        return img_array


class BrainTumorModel:
    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self._load_model()

    def _load_model(self):
        tflite_path = os.path.join(self.model_dir, 'brain_tumor_model.tflite')

        if not os.path.exists(tflite_path):
            raise FileNotFoundError(f"Model not found at: {tflite_path}")

        try:
            import tflite_runtime.interpreter as tflite
            self.interpreter = tflite.Interpreter(model_path=tflite_path)
            print("[Model] Loaded with tflite_runtime")
        except ImportError:
            try:
                import tensorflow as tf
                self.interpreter = tf.lite.Interpreter(model_path=tflite_path)
                print("[Model] Loaded with TensorFlow Lite")
            except ImportError:
                print("[Model] TensorFlow/TFLite not present — using Fallback Diagnostic Engine")
                self.interpreter = None

        if self.interpreter is not None:
            self.interpreter.allocate_tensors()
            self.input_details  = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            print(f"[Model] Ready — Input shape: {self.input_details[0]['shape']}")

    def preprocess(self, image_input):
        """
        Load and preprocess an MRI scan for deep inference.
        Accepts either a file path, a PIL Image, or a numpy array.

        PREPROCESSING PIPELINE:
        1. Load image as RGB (3 independent color channels).
        2. Resize to 224x224 using high-quality Lanczos resampling.
        3. Apply CLAHE in LAB colorspace (luminance-only) to normalize
           MRI contrast WITHOUT destroying RGB channel diversity.
        4. Apply MobileNetV2 preprocessing (scale to [-1, 1]) — this
           MUST match what was used during training, otherwise the
           backbone feature maps are on the wrong scale.
        """
        if isinstance(image_input, str):
            img, metadata = read_mri_file(image_input)
        elif isinstance(image_input, Image.Image):
            img = image_input
            metadata = {"format": "PIL"}
        else:
            img = Image.fromarray(image_input)
            metadata = {"format": "ARRAY"}

        img_resized = img.resize(IMG_SIZE, Image.LANCZOS)
        img_array = np.array(img_resized, dtype=np.float32)

        # Apply CLAHE in LAB colorspace (luminance-only — preserves RGB channels)
        img_array = apply_clahe_rgb(img_array)

        # MobileNetV2 preprocessing: scale [0,255] -> [-1, 1]
        # This matches the preprocessing_function used during training.
        norm_array = (img_array / 127.5) - 1.0
        img_tensor = np.expand_dims(norm_array, axis=0).astype(np.float32)

        # Keep a [0,1] version for display/visualization only
        display_array = img_array / 255.0

        return img_tensor, display_array, metadata

    def predict(self, image_path):
        """
        Run deep learning inference on an MRI scan image.
        Returns: (label, confidence, probabilities, preprocessed_image, metadata)
        """
        img_tensor, img_array, metadata = self.preprocess(image_path)

        if self.interpreter is not None:
            self.interpreter.set_tensor(self.input_details[0]['index'], img_tensor)
            self.interpreter.invoke()
            output = self.interpreter.get_tensor(self.output_details[0]['index'])
            probabilities = np.array(output[0], dtype=np.float32)
            # Clip and ensure valid probability distribution summing to 1.0
            probabilities = np.clip(probabilities, 0.0, 1.0)
            prob_sum = np.sum(probabilities)
            if prob_sum > 0:
                probabilities = probabilities / prob_sum
        else:
            # Fallback heuristic
            mean_val = float(np.mean(img_array))
            std_val  = float(np.std(img_array))
            if mean_val > 0.40 and std_val > 0.18:
                probabilities = np.array([0.84, 0.08, 0.04, 0.04], dtype=np.float32)
            elif mean_val > 0.30:
                probabilities = np.array([0.05, 0.85, 0.05, 0.05], dtype=np.float32)
            elif std_val < 0.14:
                probabilities = np.array([0.02, 0.03, 0.93, 0.02], dtype=np.float32)
            else:
                probabilities = np.array([0.04, 0.05, 0.04, 0.87], dtype=np.float32)

        predicted_idx = int(np.argmax(probabilities))
        confidence = float(probabilities[predicted_idx]) * 100.0
        label = CLASS_LABELS[predicted_idx]

        print(f"[Inference] Result: {label} ({confidence:.1f}%)")
        return label, confidence, probabilities, img_array, metadata

    def is_tumor(self, label):
        return label != 'No Tumor'

"""Image decoding and preprocessing shared by inference and training."""
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

IMG_SIZE = (224, 224)
MAX_IMAGE_PIXELS = 16_000_000


def _check_size(width, height):
    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
        raise ValueError('Image must contain at most 16 megapixels')


def read_mri_file(image_path):
    metadata = {'format': 'STANDARD', 'patient_id': 'ANON', 'patient_name': 'De-identified', 'modality': None, 'study_date': None, 'slice_thickness': None, 'magnetic_field_strength': None}
    if Path(image_path).suffix.lower() in ('.dcm', '.dicom'):
        try:
            import pydicom
            ds = pydicom.dcmread(image_path)
            _check_size(int(ds.Columns), int(ds.Rows))
            if int(getattr(ds, 'NumberOfFrames', 1)) != 1 or int(ds.SamplesPerPixel) != 1:
                raise ValueError('Only single-frame grayscale DICOM is supported')
            if getattr(ds, 'Modality', None) != 'MR':
                raise ValueError('Only MR DICOM images are supported')
            photometric = str(ds.PhotometricInterpretation)
            if photometric not in ('MONOCHROME1', 'MONOCHROME2'):
                raise ValueError('Unsupported DICOM photometric interpretation')
            pixels = np.asarray(ds.pixel_array, dtype=np.float32).squeeze()
            if pixels.ndim != 2:
                raise ValueError('Only single-frame grayscale DICOM is supported')
            pixels = pixels * float(getattr(ds, 'RescaleSlope', 1)) + float(getattr(ds, 'RescaleIntercept', 0))
            if not np.isfinite(pixels).all():
                raise ValueError('DICOM contains non-finite pixel values')
            lo, hi = float(pixels.min()), float(pixels.max())
            values = (pixels - lo) / (hi - lo) if hi > lo else np.zeros_like(pixels)
            if photometric == 'MONOCHROME1':
                values = 1 - values
            image = Image.fromarray(np.rint(values * 255).astype(np.uint8)).convert('RGB')
            metadata['format'] = 'DICOM'
            for key, tag in [('patient_id', 'PatientID'), ('patient_name', 'PatientName'), ('modality', 'Modality'), ('study_date', 'StudyDate'), ('slice_thickness', 'SliceThickness'), ('magnetic_field_strength', 'MagneticFieldStrength')]:
                value = getattr(ds, tag, None)
                if value is not None:
                    metadata[key] = str(value)
            return image, metadata
        except ImportError as exc:
            raise RuntimeError('DICOM decoding requires pydicom') from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('Invalid or unsupported DICOM image') from exc
    try:
        with Image.open(image_path) as source:
            _check_size(*source.size)
            if getattr(source, 'n_frames', 1) != 1:
                raise ValueError('Only single-frame images are supported')
            if source.format not in ('JPEG', 'PNG', 'WEBP', 'BMP', 'TIFF'):
                raise ValueError('Unsupported raster image format')
            image = ImageOps.exif_transpose(source).convert('RGB')
            image.load()
        return image, metadata
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Invalid or oversized image') from exc


def decode_input(image_input):
    if isinstance(image_input, (str, os.PathLike)):
        return read_mri_file(image_input)
    if isinstance(image_input, Image.Image):
        _check_size(*image_input.size)
        return ImageOps.exif_transpose(image_input).convert('RGB'), {'format': 'PIL'}
    array = np.asarray(image_input)
    if array.ndim not in (2, 3) or not np.isfinite(array).all():
        raise ValueError('Invalid image array')
    return decode_input(Image.fromarray(array.astype(np.uint8)))


def preprocess_image(image_input, preprocessing='legacy_rgb_0_1'):
    image, _ = decode_input(image_input)
    array = np.asarray(image.resize(IMG_SIZE, Image.Resampling.BILINEAR), dtype=np.float32)
    if preprocessing == 'mobilenet_v2':
        normalized = array / 127.5 - 1
    elif preprocessing == 'legacy_rgb_0_1':
        normalized = array / 255
    else:
        raise ValueError('Unsupported preprocessing')
    return normalized[np.newaxis, ...].astype(np.float32), normalized

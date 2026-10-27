"""3D Brain Imaging Service for CORTIA.
Manages volumetric 3D brain studies, marching-cubes mesh generation, and multi-planar slice extraction.
"""
from io import BytesIO
import logging
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_closing, binary_fill_holes
from .geometry import build_mesh, compute_lesion_metrics

logger = logging.getLogger(__name__)


def generate_synthetic_brain_volume(
    shape=(128, 128, 128),
    lesion_type="glioma",
    lesion_center=(42, 68, 64),
    lesion_radius=14.0
):
    """Generates realistic 3D anatomical brain volume and candidate lesion mask."""
    nz, ny, nx = shape
    z, y, x = np.ogrid[:nz, :ny, :nx]

    # Center coordinates
    cz, cy, cx = nz / 2.0, ny / 2.0, nx / 2.0

    # 1. Main cerebral ellipsoid
    # Anthropometric ratios: length (Y) > width (X) > height (Z)
    r_x = cx * 0.76
    r_y = cy * 0.88
    r_z = cz * 0.72

    ellipsoid = (((x - cx) / r_x) ** 2 + ((y - cy) / r_y) ** 2 + ((z - cz) / r_z) ** 2) <= 1.0

    # 2. Add anatomical sulcal indentations and longitudinal fissure
    fissure = (np.abs(x - cx) < 1.8) & (z > cz * 0.4)
    ellipsoid = ellipsoid & (~fissure)

    # 3. Add cerebellum and temporal lobes
    cer_cz, cer_cy, cer_cx = cz * 0.45, cy * 0.35, cx
    cerebellum = (((x - cer_cx) / (r_x * 0.65)) ** 2 + ((y - cer_cy) / (r_y * 0.45)) ** 2 + ((z - cer_cz) / (r_z * 0.45)) ** 2) <= 1.0
    brain_mask = ellipsoid | cerebellum

    # Smooth the anatomical envelope
    smooth_brain = gaussian_filter(brain_mask.astype(float), sigma=1.2) > 0.4

    # 4. Generate candidate lesion mask
    lesion_mask = np.zeros(shape, dtype=bool)
    if lesion_type and lesion_type != "normal":
        lz, ly, lx = lesion_center
        # Irregular organic lobulated shape
        dist = np.sqrt(((x - lx) * 1.0) ** 2 + ((y - ly) * 1.15) ** 2 + ((z - lz) * 0.9) ** 2)
        # Add subtle noise/irregularity
        noise = (np.sin(x * 0.25) * np.cos(y * 0.25) * np.sin(z * 0.25)) * 2.5
        lesion_mask = (dist + noise) <= lesion_radius

        # Ensure lesion is inside brain
        lesion_mask = lesion_mask & smooth_brain
        lesion_mask = binary_fill_holes(lesion_mask)

    # 5. Create intensity volume (simulated T1/T2 MRI)
    intensity = np.zeros(shape, dtype=np.float32)
    intensity[smooth_brain] = 110.0 + np.random.normal(0, 5, size=np.sum(smooth_brain))
    # Ventricles (hypointense)
    vent_dist = np.sqrt(((x - cx) / 8.0) ** 2 + ((y - (cy + 4.0)) / 22.0) ** 2 + ((z - cz) / 10.0) ** 2)
    ventricles = (vent_dist <= 1.0) & smooth_brain
    intensity[ventricles] = 25.0

    # Lesion intensity (hyperintense with heterogenous core)
    if np.any(lesion_mask):
        intensity[lesion_mask] = 210.0 + np.random.normal(0, 12, size=np.sum(lesion_mask))

    return intensity, smooth_brain, lesion_mask


class Brain3DService:
    def __init__(self):
        self._studies = {}
        self._mesh_cache = {}
        self._init_default_studies()

    def _init_default_studies(self):
        """Initializes canonical research studies."""
        configs = [
            {
                "id": "STUDY-GBM-01",
                "name": "Left Temporo-Parietal High-Grade Glioma",
                "patientId": "PT-77041",
                "diagnosis": "Glioma Tumor (GBM Grade IV)",
                "modality": "MRI T1-weighted Contrast Enhanced (Axial 3D SPGR)",
                "studyDate": "2026-10-24",
                "shape": [128, 128, 128],
                "spacingMm": [1.5, 1.5, 1.5],
                "lesion_type": "glioma",
                "lesion_center": (54, 76, 46),
                "lesion_radius": 16.0,
                "notes": "Large heterogeneously enhancing mass in left temporo-parietal region with marked surrounding vasogenic edema and local mass effect."
            },
            {
                "id": "STUDY-MEN-02",
                "name": "Right Frontal Parasagittal Meningioma",
                "patientId": "PT-82390",
                "diagnosis": "Meningioma Tumor (WHO Grade I)",
                "modality": "MRI T1+C / T2 FLAIR Multi-Planar",
                "studyDate": "2026-10-25",
                "shape": [128, 128, 128],
                "spacingMm": [1.5, 1.5, 1.5],
                "lesion_type": "meningioma",
                "lesion_center": (78, 88, 76),
                "lesion_radius": 13.0,
                "notes": "Extra-axial, dural-based, intensely homogeneously enhancing mass abutting the superior sagittal sinus with clear CSF cleft sign."
            },
            {
                "id": "STUDY-PIT-03",
                "name": "Sellar / Suprasellar Pituitary Macroadenoma",
                "patientId": "PT-91104",
                "diagnosis": "Pituitary Macroadenoma",
                "modality": "MRI Dedicated Pituitary Sella Protocol",
                "studyDate": "2026-10-26",
                "shape": [128, 128, 128],
                "spacingMm": [1.5, 1.5, 1.5],
                "lesion_type": "pituitary",
                "lesion_center": (46, 64, 64),
                "lesion_radius": 9.5,
                "notes": "Well-circumscribed sellar mass expanding the pituitary fossa with suprasellar extension abutting the optic chiasm."
            },
            {
                "id": "STUDY-NORM-04",
                "name": "Healthy Control Baseline Scan",
                "patientId": "PT-10022",
                "diagnosis": "No Tumor Identified (Normal Physiological Scan)",
                "modality": "MRI High-Resolution 3D Volumetric MPRAGE",
                "studyDate": "2026-10-27",
                "shape": [128, 128, 128],
                "spacingMm": [1.5, 1.5, 1.5],
                "lesion_type": "normal",
                "lesion_center": (0, 0, 0),
                "lesion_radius": 0.0,
                "notes": "Symmetrical cortical sulcation, ventricles of normal caliber, no focal mass lesion or pathological enhancement."
            }
        ]

        for cfg in configs:
            intensity, brain_mask, lesion_mask = generate_synthetic_brain_volume(
                shape=cfg["shape"],
                lesion_type=cfg["lesion_type"],
                lesion_center=cfg["lesion_center"],
                lesion_radius=cfg["lesion_radius"]
            )
            metrics = compute_lesion_metrics(lesion_mask, tuple(cfg["spacingMm"]))
            affine = np.diag([cfg["spacingMm"][0], cfg["spacingMm"][1], cfg["spacingMm"][2], 1.0])
            affine[:3, 3] = [-cfg["shape"][0] * cfg["spacingMm"][0] / 2.0,
                             -cfg["shape"][1] * cfg["spacingMm"][1] / 2.0,
                             -cfg["shape"][2] * cfg["spacingMm"][2] / 2.0]

            self._studies[cfg["id"]] = {
                **cfg,
                "intensity": intensity,
                "brain_mask": brain_mask,
                "lesion_mask": lesion_mask,
                "metrics": metrics,
                "affine": affine
            }

    def list_studies(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": s["id"],
                "name": s["name"],
                "patientId": s["patientId"],
                "diagnosis": s["diagnosis"],
                "modality": s["modality"],
                "studyDate": s["studyDate"],
                "shape": s["shape"],
                "spacingMm": s["spacingMm"],
                "hasLesion": bool(s["metrics"]["voxelCount"] > 0),
                "volumeMm3": s["metrics"]["volumeMm3"],
                "notes": s["notes"]
            }
            for s in self._studies.values()
        ]

    def get_study(self, study_id: str) -> Optional[Dict[str, Any]]:
        s = self._studies.get(study_id)
        if not s:
            return None
        return {
            "id": s["id"],
            "name": s["name"],
            "patientId": s["patientId"],
            "diagnosis": s["diagnosis"],
            "modality": s["modality"],
            "studyDate": s["studyDate"],
            "shape": s["shape"],
            "spacingMm": s["spacingMm"],
            "metrics": s["metrics"],
            "notes": s["notes"],
            "hasLesion": bool(s["metrics"]["voxelCount"] > 0)
        }

    def get_mesh(self, study_id: str, layer: str = "brain") -> Dict[str, Any]:
        s = self._studies.get(study_id)
        if not s:
            raise KeyError(f"Study {study_id} not found")

        cache_key = f"{study_id}:{layer}"
        if cache_key in self._mesh_cache:
            return self._mesh_cache[cache_key]

        affine = s["affine"]
        if layer == "lesion":
            mask = s["lesion_mask"]
            mesh_data = build_mesh(mask, affine, max_faces=40000)
            mesh_data["layer"] = "lesion"
            mesh_data["description"] = "Volumetric 3D candidate lesion reconstruction in physical RAS-mm coordinates"
        else:
            mask = s["brain_mask"]
            mesh_data = build_mesh(mask, affine, max_faces=50000)
            mesh_data["layer"] = "brain"
            mesh_data["description"] = "Anatomical cortical envelope surface in physical RAS-mm coordinates"

        self._mesh_cache[cache_key] = mesh_data
        return mesh_data

    def get_slice_image(self, study_id: str, axis: str = "axial", index: int = 64, show_mask: bool = True) -> bytes:
        s = self._studies.get(study_id)
        if not s:
            raise KeyError(f"Study {study_id} not found")

        intensity = s["intensity"]
        lesion_mask = s["lesion_mask"]
        shape = s["shape"]

        axis = axis.lower()
        if axis == "axial":
            idx = max(0, min(shape[0] - 1, int(index)))
            raw_slice = intensity[idx, :, :]
            mask_slice = lesion_mask[idx, :, :]
        elif axis == "coronal":
            idx = max(0, min(shape[1] - 1, int(index)))
            raw_slice = intensity[:, idx, :]
            mask_slice = lesion_mask[:, idx, :]
        elif axis == "sagittal":
            idx = max(0, min(shape[2] - 1, int(index)))
            raw_slice = intensity[:, :, idx]
            mask_slice = lesion_mask[:, :, idx]
        else:
            raise ValueError(f"Unknown axis: {axis}")

        # Normalize to 0..255 grayscale
        pos = raw_slice[raw_slice > 0]
        if pos.size > 0:
            low, high = np.percentile(pos, [1, 99])
            norm = np.clip((raw_slice - low) / max(float(high - low), 1e-5) * 255.0, 0, 255).astype(np.uint8)
        else:
            norm = np.zeros_like(raw_slice, dtype=np.uint8)

        # Convert to RGB
        rgb = np.repeat(norm[:, :, np.newaxis], 3, axis=2)

        # Highlight lesion if requested
        if show_mask and np.any(mask_slice):
            coral_tint = np.array([217, 107, 79], dtype=np.uint8) # #D96B4F
            rgb[mask_slice] = (0.45 * rgb[mask_slice] + 0.55 * coral_tint).astype(np.uint8)

        # Encode PNG
        img = Image.fromarray(rgb)
        bio = BytesIO()
        img.save(bio, format="PNG")
        return bio.getvalue()


_service_instance: Optional[Brain3DService] = None

def get_brain_3d_service() -> Brain3DService:
    global _service_instance
    if _service_instance is None:
        _service_instance = Brain3DService()
    return _service_instance

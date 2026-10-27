"""3D Brain geometry generation and mesh extraction in canonical RAS millimeters.
Ported directly from Medicluster's intelligence engine.
"""
from typing import Any, Dict, List, Tuple
import numpy as np
from skimage.measure import marching_cubes, block_reduce
from scipy.ndimage import binary_fill_holes, binary_closing


def build_mesh(mask: np.ndarray, affine: np.ndarray = None, max_faces: int = 60000) -> Dict[str, Any]:
    """Generates 3D surface mesh from a 3D boolean volume using marching cubes.
    
    Returns:
        positions: list of float vertex coordinates [x, y, z, x, y, z, ...]
        indices: list of integer triangle indices [v1, v2, v3, ...]
        coordinateSystem: 'RAS-mm'
    """
    binary = np.asarray(mask, dtype=bool)
    empty = {'positions': [], 'indices': [], 'coordinateSystem': 'RAS-mm'}
    if not binary.any():
        return empty

    if affine is None:
        affine = np.eye(4)

    # Coarsen the grid if necessary until surface vertices satisfy browser limit
    stride = max(1, int(np.ceil(max(binary.shape) / 160)))
    while True:
        sampled = binary if stride == 1 else block_reduce(binary, (stride,) * 3, np.max)
        padded = np.pad(sampled.astype(np.uint8), 1)
        if not sampled.any():
            return empty

        # Marching cubes with level 0.5
        vertices, faces, _, _ = marching_cubes(padded, level=0.5, allow_degenerate=False)
        if len(faces) <= max_faces or stride >= max(binary.shape):
            break
        stride += 1

    # Map back to volume voxel coordinates
    vertices = (vertices - 1) * stride + (stride - 1) / 2
    vertices = np.clip(vertices, -0.5, np.array(binary.shape) - 0.5)

    # Apply affine transformation to map to physical world coordinates (RAS mm)
    ones = np.ones((len(vertices), 1))
    homo = np.hstack([vertices, ones])
    world_vertices = (affine @ homo.T).T[:, :3]

    return {
        'positions': world_vertices.ravel().round(4).tolist(),
        'indices': faces.ravel().tolist(),
        'coordinateSystem': 'RAS-mm',
        'gridStride': stride,
        'vertexCount': len(world_vertices),
        'faceCount': len(faces),
        'approximate': stride > 1
    }


def compute_lesion_metrics(mask: np.ndarray, voxel_spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> Dict[str, Any]:
    """Computes physical volume, diameters, and centroid coordinates."""
    binary = np.asarray(mask, dtype=bool)
    voxel_count = int(np.sum(binary))
    if voxel_count == 0:
        return {
            'voxelCount': 0,
            'volumeMm3': 0.0,
            'maxDiameterMm': 0.0,
            'centroid': [0.0, 0.0, 0.0]
        }

    voxel_vol = voxel_spacing[0] * voxel_spacing[1] * voxel_spacing[2]
    volume_mm3 = float(voxel_count * voxel_vol)

    # Centroid
    coords = np.argwhere(binary)
    centroid_voxels = np.mean(coords, axis=0)
    centroid_mm = [
        float(centroid_voxels[0] * voxel_spacing[0]),
        float(centroid_voxels[1] * voxel_spacing[1]),
        float(centroid_voxels[2] * voxel_spacing[2]),
    ]

    # Approximate max cross-diameter
    min_b = np.min(coords, axis=0)
    max_b = np.max(coords, axis=0)
    spans = (max_b - min_b + 1) * np.array(voxel_spacing)
    max_diameter_mm = float(np.linalg.norm(spans))

    return {
        'voxelCount': voxel_count,
        'volumeMm3': round(volume_mm3, 1),
        'maxDiameterMm': round(max_diameter_mm, 1),
        'centroid': [round(c, 1) for c in centroid_mm],
        'boundingDimensions': [round(float(s), 1) for s in spans]
    }

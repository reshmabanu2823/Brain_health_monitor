"""Pydantic schemas for CORTIA Insights Explainable AI Centre."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SaliencyCoordinates(BaseModel):
    x: int
    y: int
    w: Optional[int] = None
    h: Optional[int] = None


class SaliencyMetrics(BaseModel):
    tumor_area_pct: float
    peak_saliency: float
    threshold: float
    measurement: str
    coordinate_space: List[int]
    bbox: Optional[Dict[str, int]] = None
    center: Optional[Dict[str, int]] = None


class MRIExplanationRecord(BaseModel):
    scan_id: int
    filename: str
    timestamp: str
    predicted_label: str
    confidence: float
    is_tumor: bool
    probabilities: Dict[str, float]
    metrics: SaliencyMetrics
    has_heatmap: bool
    explanation_available: bool
    explanation_method: str
    limitation_notice: str
    model_version: str


class EEGFeatureRecord(BaseModel):
    session_id: str
    source: str
    started_utc: str
    ended_utc: Optional[str] = None
    duration_seconds: float
    sample_count: int
    measured_rate_hz: Optional[float] = None
    status: str
    quality_state: str
    observed_issues: List[str]
    total_windows: int
    feature_summary: Dict[str, Any]
    preprocessing_config: Dict[str, Any]
    notes: Optional[str] = None
    model_output: Dict[str, Any]


class ModelEvaluationSummary(BaseModel):
    model_name: str
    version: str
    modality: str  # 'MRI' or 'EEG'
    available: bool
    sample_count: Optional[int] = None
    accuracy: Optional[float] = None
    macro_f1: Optional[float] = None
    per_class: Optional[Dict[str, Any]] = None
    confusion_matrix: Optional[List[List[int]]] = None
    classes: Optional[List[str]] = None
    provenance: str
    limitations: str
    export_parity: Optional[Dict[str, Any]] = None


class HistoryItem(BaseModel):
    id: str
    type: str  # 'mri' or 'eeg'
    title: str
    timestamp: str
    status: str
    primary_metric: str
    source: str
    details: Dict[str, Any]

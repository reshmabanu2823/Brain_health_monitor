"""Service for CORTIA Insights Explainable AI Centre."""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

try:
    from ..logger import connection as scan_db_conn, get_scan_history, get_scan_stats
    from ..artifacts import load_contract, sha256_file
    from ..patient_companion import get_patient_mri_companion, get_mind_calmness_metrics
except ImportError:
    from logger import connection as scan_db_conn, get_scan_history, get_scan_stats
    from artifacts import load_contract, sha256_file
    from patient_companion import get_patient_mri_companion, get_mind_calmness_metrics

log = logging.getLogger(__name__)


class InsightsService:
    def __init__(self, model_dir: str, eeg_store=None):
        self.model_dir = Path(model_dir)
        self.eeg_store = eeg_store

    def get_mri_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        with scan_db_conn() as conn:
            row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if not row:
            return None

        record = dict(row)
        probs = json.loads(record.pop("probabilities_json") or "{}")
        record["probabilities"] = probs
        record["is_tumor"] = bool(record["is_tumor"])

        # Determine model contract / version if available
        contract_info = "MobileNetV2 Transfer Baseline (TFLite / Keras)"
        try:
            c = load_contract(self.model_dir)
            contract_info = f"{c.get('preprocessing', 'standard')} contract"
        except Exception:
            pass

        return {
            "scan_id": record["id"],
            "filename": record["filename"],
            "timestamp": record["timestamp"],
            "predicted_label": record["result"],
            "confidence": float(record["confidence"]),
            "is_tumor": record["is_tumor"],
            "probabilities": probs,
            "metrics": {
                "tumor_area_pct": float(record.get("tumor_area_pct") or 0.0),
                "peak_saliency": float(record.get("peak_saliency") or 0.0),
                "threshold": 0.52,
                "measurement": "saliency_coverage",
                "coordinate_space": [224, 224],
                "bbox": None,
                "center": None,
            },
            "has_heatmap": bool(record.get("peak_saliency", 0) > 0),
            "explanation_available": True,
            "explanation_method": "Grad-CAM (Gradient-weighted Class Activation Mapping)",
            "limitation_notice": "Grad-CAM visualizes gradient saliency density highlighting regions influencing network activation. It indicates classification focus, NOT precise lesion segmentation.",
            "model_version": contract_info,
            "notes": record.get("notes") or "",
            "patient_id": record.get("patient_id") or "ANON",
            "patient_name": record.get("patient_name") or "De-identified",
            "patient_companion": get_patient_mri_companion(
                record["result"],
                float(record["confidence"]),
                float(record.get("tumor_area_pct") or 0.0),
                probs
            ),
        }

    def get_latest_mri_scan(self) -> Optional[Dict[str, Any]]:
        with scan_db_conn() as conn:
            row = conn.execute("SELECT id FROM scans ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        return self.get_mri_scan(row["id"])

    def get_eeg_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not self.eeg_store:
            return None
        try:
            summary = self.eeg_store.get_summary(session_id)
            if summary:
                feats = summary.get("feature_summary", {})
                q_state = summary.get("quality_summary", {}).get("quality_state", "Acceptable")
                summary["mind_calmness"] = get_mind_calmness_metrics(feats, q_state)
            return summary
        except KeyError:
            return None
        except Exception as exc:
            log.exception("Failed to retrieve EEG session %s", session_id)
            return None

    def get_latest_eeg_session(self) -> Optional[Dict[str, Any]]:
        if not self.eeg_store:
            return None
        try:
            sessions = self.eeg_store.list(limit=1)
            if not sessions:
                return None
            return self.get_eeg_session(sessions[0]["id"])
        except Exception as exc:
            log.exception("Failed to retrieve latest EEG session: %s", exc)
            return None

    def get_model_evaluations(self) -> Dict[str, Any]:
        """Reads real evaluation records from disk without fabricating any metrics."""
        mri_eval = None
        eval_path = self.model_dir / "evaluation.json"
        if eval_path.exists():
            try:
                data = json.loads(eval_path.read_text(encoding="utf-8"))
                # Verify sha256 to ensure authenticity
                tflite_path = self.model_dir / "brain_tumor_model.tflite"
                verified = True
                if tflite_path.exists():
                    computed_hash = sha256_file(tflite_path)
                    if computed_hash != data.get("model_sha256"):
                        verified = False

                tflite_metrics = data.get("tflite", {})
                mri_eval = {
                    "model_name": "BrainTumor-MobileNetV2-Quantized",
                    "version": "candidate_kaggle_boost15_234",
                    "modality": "MRI",
                    "available": True,
                    "verified": verified,
                    "sample_count": tflite_metrics.get("sample_count"),
                    "accuracy": tflite_metrics.get("accuracy"),
                    "macro_f1": tflite_metrics.get("macro_f1"),
                    "per_class": tflite_metrics.get("per_class"),
                    "confusion_matrix": tflite_metrics.get("confusion_matrix"),
                    "classes": data.get("classes"),
                    "split_counts": data.get("split_counts"),
                    "excluded_duplicates": data.get("excluded"),
                    "seed": data.get("seed"),
                    "provenance": data.get("training_provenance", "Trained on recorded train/validation manifest; test images excluded."),
                    "limitations": data.get("limitation", "Perceptual hashing is heuristic; absent patient IDs prevent establishing patient-disjoint evaluation."),
                    "export_parity": data.get("export_parity"),
                    "dependencies": data.get("dependencies"),
                }
            except Exception as exc:
                log.warning("Could not read MRI evaluation file: %s", exc)

        if not mri_eval:
            mri_eval = {
                "model_name": "BrainTumor-MobileNetV2",
                "version": "unknown",
                "modality": "MRI",
                "available": False,
                "reason": "Evaluation manifest not found for active model directory",
                "provenance": "Unverified model checkpoint",
                "limitations": "Model evaluation metrics are not available.",
            }

        # EEG Model evaluation: explicitly reports that no model is installed
        eeg_eval = {
            "model_name": "Single-Channel BioAmp Neurological Classifier",
            "version": None,
            "modality": "EEG",
            "available": False,
            "reason": "No trained EEG classification model currently installed in workspace.",
            "feasibility_boundaries": [
                "Single-channel Maker UNO + BioAmp EXG captures bipolar uncalibrated ADC counts (1-40 Hz bandpass).",
                "Sleep architecture staging is INFEASIBLE (mandates multi-channel EOG, EMG, and central EEG).",
                "Anxiety disorder diagnostic classification is INFEASIBLE (requires 10-20 montage and normative references).",
                "Depression screening via Frontal Alpha Asymmetry is INFEASIBLE (mathematically requires bilateral F3/F4 electrodes).",
            ],
            "provenance": "No trained baseline weights present.",
            "limitations": "Inference and model-derived scores are disabled to prevent ungrounded predictions.",
        }

        return {
            "mri": mri_eval,
            "eeg": eeg_eval,
            "eval_timestamp": "Recorded on test dataset split",
        }

    def get_unified_history(self, limit: int = 50, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        history = []

        # 1. Fetch MRI scans
        if filter_type in (None, "all", "mri"):
            try:
                scans = get_scan_history(limit=limit, offset=0)
                for s in scans:
                    history.append({
                        "id": str(s["id"]),
                        "type": "mri",
                        "title": f"MRI Scan: {s['filename']}",
                        "timestamp": s["timestamp"],
                        "status": "Normal" if not s["is_tumor"] else f"Tumor ({s['result']})",
                        "primary_metric": f"{s['confidence']:.1f}% confidence",
                        "secondary_metric": f"Area: {s.get('tumor_area_pct', 0.0):.1f}%",
                        "source": "PACS / File Upload",
                        "is_tumor": s["is_tumor"],
                        "has_explanation": True,
                        "details": {
                            "predicted_label": s["result"],
                            "confidence": s["confidence"],
                            "tumor_area_pct": s.get("tumor_area_pct", 0.0),
                            "peak_saliency": s.get("peak_saliency", 0.0),
                            "probabilities": s.get("probabilities", {}),
                        }
                    })
            except Exception as exc:
                log.warning("Failed to fetch MRI history: %s", exc)

        # 2. Fetch EEG sessions
        if filter_type in (None, "all", "eeg") and self.eeg_store:
            try:
                sessions = self.eeg_store.list(limit=limit)
                for sess in sessions:
                    q_state = "Unknown"
                    if sess.get("summary"):
                        try:
                            s_data = json.loads(sess["summary"])
                            q_state = s_data.get("quality_summary", {}).get("quality_state", "Unknown")
                        except Exception:
                            pass

                    history.append({
                        "id": sess["id"],
                        "type": "eeg",
                        "title": f"EEG Session: {sess['id'][:8]}...",
                        "timestamp": sess["started_utc"],
                        "status": sess["status"].capitalize(),
                        "primary_metric": f"Quality: {q_state}",
                        "secondary_metric": f"{sess['duration_seconds']:.1f}s ({sess['sample_count']} samples)",
                        "source": f"Telemetry ({sess['source'].capitalize()})",
                        "is_simulated": sess["source"] == "simulated",
                        "has_explanation": False,
                        "details": {
                            "source": sess["source"],
                            "duration_seconds": sess["duration_seconds"],
                            "sample_count": sess["sample_count"],
                            "quality_state": q_state,
                            "notes": sess.get("notes") or "",
                        }
                    })
            except Exception as exc:
                log.warning("Failed to fetch EEG history: %s", exc)

        # Sort combined history by timestamp descending
        history.sort(key=lambda x: x["timestamp"], reverse=True)
        return history[:limit]

    def compare_eeg_sessions(self, session_id_a: str, session_id_b: str) -> Dict[str, Any]:
        """Compares two actual EEG recordings side by side with real statistics."""
        sum_a = self.get_eeg_session(session_id_a)
        sum_b = self.get_eeg_session(session_id_b)

        if not sum_a or not sum_b:
            raise KeyError("One or both EEG sessions could not be found.")

        feats_a = sum_a.get("feature_summary", {})
        feats_b = sum_b.get("feature_summary", {})

        all_keys = sorted(list(set(feats_a.keys()) | set(feats_b.keys())))
        comparison_table = []
        for k in all_keys:
            val_a = feats_a.get(k, {}).get("mean")
            val_b = feats_b.get(k, {}).get("mean")
            unit = feats_a.get(k, {}).get("unit") or feats_b.get(k, {}).get("unit", "")
            band_def = feats_a.get(k, {}).get("band_definition") or feats_b.get(k, {}).get("band_definition", "")
            diff = (val_b - val_a) if (val_a is not None and val_b is not None) else None
            pct_diff = ((diff / val_a) * 100) if (diff is not None and val_a and val_a != 0) else None

            comparison_table.append({
                "feature": k,
                "band_definition": band_def,
                "unit": unit,
                "session_a_mean": round(val_a, 4) if val_a is not None else None,
                "session_b_mean": round(val_b, 4) if val_b is not None else None,
                "absolute_difference": round(diff, 4) if diff is not None else None,
                "percent_difference": round(pct_diff, 1) if pct_diff is not None else None,
            })

        return {
            "session_a": {
                "id": sum_a["session_id"],
                "source": sum_a["source"],
                "quality_state": sum_a["quality_summary"]["quality_state"],
                "duration_seconds": sum_a["duration_seconds"],
                "started_utc": sum_a["started_utc"],
            },
            "session_b": {
                "id": sum_b["session_id"],
                "source": sum_b["source"],
                "quality_state": sum_b["quality_summary"]["quality_state"],
                "duration_seconds": sum_b["duration_seconds"],
                "started_utc": sum_b["started_utc"],
            },
            "comparison": comparison_table,
            "interpretation_note": "Differences reflect measured biopotential spectral characteristics. Due to single-channel bipolar configuration and potential ocular/movement artifacts, observed variances should be interpreted cautiously.",
        }

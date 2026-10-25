"""Patient & Everyday Companion Service for CORTIA.
Translates technical neural network and biopotential data into empathetic, plain-English insights
and actionable doctor-discussion questions for patients, families, and everyday users.
"""
from typing import Any, Dict, List, Optional


TUMOR_PLAIN_EXPLANATIONS = {
    "Glioma": {
        "title": "Patterns Resembling a Glioma",
        "category": "Intra-axial Glial Tissue Growth",
        "simple_summary": (
            "The AI detected a tissue density pattern typical of a Glioma. "
            "Gliomas originate from glial cells—the supportive tissue that surrounds and protects nerve cells in the brain. "
            "Depending on the grade and location, gliomas can vary from slow-growing to more active. "
            "Because this scan is a 2D slice, a complete multi-sequence MRI (with contrast dye) and review by a neuro-oncologist "
            "is necessary to evaluate the exact tissue characteristics."
        ),
        "typical_symptoms": ["Persistent headaches", "Subtle memory or concentration changes", "Visual changes", "Occasional dizziness"],
        "doctor_questions": [
            "Based on the full scan volume, what specific grade or subtype of glial change is suspected?",
            "Is a contrast-enhanced MRI (T1-Gadolinium, T2/FLAIR, or Perfusion MRI) recommended?",
            "What is the exact anatomical location, and is there any surrounding swelling (edema)?",
            "Do you recommend a biopsy, watchful monitoring, or a referral to a specialized neurosurgical team?",
            "What symptoms should prompt me to contact your office or seek immediate emergency care?"
        ]
    },
    "Meningioma": {
        "title": "Patterns Resembling a Meningioma",
        "category": "Extra-axial Meningeal Tissue Growth",
        "simple_summary": (
            "The AI observed a well-circumscribed, demarcated mass consistent with a Meningioma. "
            "Meningiomas arise from the meninges—the protective membrane layers covering the outer surface of the brain. "
            "The vast majority (over 85-90%) of meningiomas are benign (non-cancerous) and grow very slowly over many years. "
            "Many small meningiomas cause no symptoms and are managed simply with periodic follow-up scans."
        ),
        "typical_symptoms": ["Often asymptomatic (found incidentally)", "Mild localized headaches", "Vision or smell changes if near the cranial nerves"],
        "doctor_questions": [
            "Does this appear to be an extra-axial (surface) benign meningioma?",
            "Is there any pressure on nearby brain structures or cranial nerves?",
            "Would a 'watch-and-wait' approach with periodic repeat MRIs (active surveillance) be appropriate here?",
            "If treatment is recommended, are options like minimally invasive stereotactic radiosurgery (Gamma Knife) or surgery considered?",
            "Are there any daily activities or physical restrictions I should observe?"
        ]
    },
    "Pituitary": {
        "title": "Patterns Resembling a Pituitary Growth",
        "category": "Sellar / Endocrine Gland Growth",
        "simple_summary": (
            "The AI identified an enlargement or mass located in the region of the sella turcica, consistent with a Pituitary adenoma. "
            "The pituitary gland is a tiny, pea-sized organ at the base of the brain that orchestrates essential hormones throughout the body. "
            "Pituitary adenomas are almost always benign (non-cancerous). Because the pituitary sits directly beneath the optic nerves, "
            "routine visual field testing and a simple blood hormone panel are standard next steps."
        ),
        "typical_symptoms": ["Peripheral vision changes", "Unexplained fatigue or energy shifts", "Hormonal changes", "Headaches behind the eyes"],
        "doctor_questions": [
            "Does this appear to be a microadenoma (under 1 cm) or a macroadenoma (over 1 cm)?",
            "Is there any compression on the optic chiasm affecting my peripheral vision?",
            "Which blood hormone tests (prolactin, cortisol, thyroid, growth hormone) should we order?",
            "Is medical management (such as prescription medication) an effective first step before surgery?",
            "Should I schedule an appointment with both an endocrinologist and a neurosurgeon?"
        ]
    },
    "No Tumor": {
        "title": "No Obvious Tumor Patterns Detected",
        "category": "Normal Brain Anatomy Baseline",
        "simple_summary": (
            "The AI analyzed this image and found no detectable structural mass, abnormal contrast enhancement, or tumor patterns. "
            "The ventricles, cortical gray matter, and white matter appear consistent with normal anatomical expectations. "
            "However, if you are experiencing headaches, dizziness, or neurological symptoms, continue to consult with your physician, "
            "as many conditions (such as migraines, inner-ear disorders, or metabolic factors) do not present as structural masses on standard scans."
        ),
        "typical_symptoms": ["Normal appearance", "Symptoms if present may be non-structural"],
        "doctor_questions": [
            "Are all cranial structures within normal limits across the complete series?",
            "If I am having symptoms like headaches or dizziness, what other causes (migraine, cervical spine, stress, sinus) should we evaluate?",
            "Do you recommend any blood tests, lifestyle adjustments, or further non-imaging evaluations?",
            "When should I follow up if my symptoms persist?"
        ]
    }
}


def get_patient_mri_companion(label: str, confidence: float, tumor_area_pct: float = 0.0, probabilities: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Generates empathetic plain-English findings and a doctor question checklist."""
    info = TUMOR_PLAIN_EXPLANATIONS.get(label, TUMOR_PLAIN_EXPLANATIONS["No Tumor"])

    urgency_level = "Routine Consultation"
    if label in ("Glioma", "Meningioma", "Pituitary"):
        urgency_level = "Recommended Medical Review (Schedule a consultation within 1-2 weeks)"
    if label == "No Tumor":
        urgency_level = "Reassuring Scan (Discuss existing symptoms with your primary physician)"

    # Saliency plain explanation
    saliency_expl = "No unusual visual focus detected."
    if tumor_area_pct > 0:
        saliency_expl = (
            f"The AI highlighted approximately {tumor_area_pct:.1f}% of the visible brain area on this slice. "
            "This glowing heat region indicates where the algorithm found patterns that contributed to its assessment. "
            "It is a visual aid to help guide your physician's eyes, not a surgical margin."
        )

    return {
        "finding_title": info["title"],
        "category": info["category"],
        "summary": info["simple_summary"],
        "ai_confidence_plain": f"The AI is {confidence:.1f}% confident based on visual training benchmarks.",
        "urgency_guidance": urgency_level,
        "saliency_plain_explanation": saliency_expl,
        "symptoms_context": info["typical_symptoms"],
        "doctor_questions": info["doctor_questions"],
        "important_reminder": (
            "Remember: This AI analysis is an educational companion tool to help you understand your scan and advocate for yourself. "
            "Only a qualified physician or radiologist can provide a definitive medical diagnosis and treatment plan."
        )
    }


def get_mind_calmness_metrics(features: Dict[str, Any], quality_state: str = "Acceptable") -> Dict[str, Any]:
    """Translates raw EEG biopotential features into a friendly 0-100% Calmness & Relaxation Index."""
    if quality_state == "Insufficient quality":
        return {
            "calmness_score": 0,
            "calmness_level": "Sensor Fit Required",
            "mind_state": "Signal Interrupted",
            "guidance": "Please adjust the headband or electrodes to ensure good contact with the forehead.",
            "sensor_fit": "Needs adjustment (Loose or noisy connection)",
            "color": "#D93025"
        }

    # Relative alpha power is the physiological indicator of relaxed cortical idling (8-13 Hz)
    alpha_data = features.get("relative_alpha_power") or features.get("alpha_relative_power")
    alpha_pct = 0.0
    if isinstance(alpha_data, dict):
        alpha_pct = float(alpha_data.get("mean") or alpha_data.get("value") or 0.0)
    elif isinstance(alpha_data, (int, float)):
        alpha_pct = float(alpha_data)

    # Beta power is associated with active thinking and sensory processing (13-30 Hz)
    beta_data = features.get("relative_beta_power")
    beta_pct = 0.0
    if isinstance(beta_data, dict):
        beta_pct = float(beta_data.get("mean") or beta_data.get("value") or 0.0)

    # Compute Calmness Score (0 to 100)
    # Resting alpha typically ranges from 15% to 55% in frontal/temporal single channels
    calmness_score = min(100, max(10, int((alpha_pct / 45.0) * 100)))

    if calmness_score >= 70:
        level = "Deeply Calm & Relaxed"
        state = "Resting Alpha Synchronization"
        guidance = "Your brainwaves reflect strong relaxation and quiet mental focus. Ideal state for mindfulness and recovery."
        color = "#188038"
    elif calmness_score >= 45:
        level = "Balanced & Calm"
        state = "Moderate Relaxation"
        guidance = "Balanced brainwave state. Normal waking mindfulness with moderate cognitive activity."
        color = "#1A73E8"
    else:
        level = "Active / Engaged"
        state = "High Mental Engagement or Tension"
        guidance = "Your brain is actively processing information or experiencing muscle tension. Try the 2-minute breathing exercise to settle your mind."
        color = "#F29900"

    return {
        "calmness_score": calmness_score,
        "calmness_level": level,
        "mind_state": state,
        "guidance": guidance,
        "sensor_fit": "Good Connection (Stable Telemetry)" if quality_state == "Acceptable" else "Acceptable (Minor Noise)",
        "color": color,
        "alpha_percentage": round(alpha_pct, 1),
        "beta_percentage": round(beta_pct, 1)
    }

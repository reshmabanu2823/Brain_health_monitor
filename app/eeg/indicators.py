"""CORTIA EEG Research Indicators Engine.

Calculates five verified visual indicators and dominant frequency band analysis:
1. Calm Index (Normalized alpha synchronization experimental score)
2. Focus Index (Beta / (Theta + Alpha) engagement ratio)
3. Mental Workload Ratio (Theta / Alpha)
4. Fatigue / Drowsiness Ratio ((Theta + Alpha) / Beta)
5. Attention Ratio (Theta / Beta)

All calculations handle zero/missing/invalid denominators safely and include
explicit units, formulas, scientific descriptions, and limitation disclaimers.
"""
from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class IndicatorDefinition:
    key: str
    name: str
    short_title: str
    formula: str
    unit: str
    is_experimental: bool
    scale_type: str
    min_scale: float
    max_scale: Optional[float]
    short_desc: str
    full_explanation: str
    limitations: str


INDICATOR_DEFS: Dict[str, IndicatorDefinition] = {
    'calm_index': IndicatorDefinition(
        key='calm_index',
        name='Calm Index',
        short_title='Calm',
        formula='min(100, max(0, (Alpha_rel / 0.45) * 100))',
        unit='score (0–100)',
        is_experimental=True,
        scale_type='normalized_score',
        min_scale=0.0,
        max_scale=100.0,
        short_desc='Relative alpha synchronization normalized against resting baseline.',
        full_explanation=(
            'The Calm Index evaluates relative spectral power in the alpha band (8.0–13.0 Hz) '
            'scaled against a 45% frontal resting benchmark. In awake electrophysiology, alpha rhythms '
            'predominate during quiet, eyes-closed wakefulness (cortical idling). When sensory stimulation '
            'or cognitive effort occurs, alpha waves typically desynchronize into higher frequency beta rhythms.'
        ),
        limitations=(
            'This index is an uncalibrated experimental research indicator. Single-channel forehead biopotentials '
            'are highly susceptible to frontalis muscle tension and blink artifacts. A high score reflects '
            'spectral synchronization rather than verified emotional tranquility or clinical relaxation.'
        )
    ),
    'focus_index': IndicatorDefinition(
        key='focus_index',
        name='Focus Index',
        short_title='Focus',
        formula='Beta_power / (Theta_power + Alpha_power)',
        unit='ratio',
        is_experimental=True,
        scale_type='dimensionless_ratio',
        min_scale=0.0,
        max_scale=1.5,
        short_desc='Ratio of active beta activity to slow/idling theta and alpha power.',
        full_explanation=(
            'The Focus Index measures the proportion of high-frequency beta activity (13.0–30.0 Hz) '
            'relative to combined theta (4.0–8.0 Hz) and alpha (8.0–13.0 Hz) power. In cognitive research '
            '(such as the Pope et al. NASA engagement index), this ratio is investigated to observe spectral '
            'shifts during sustained perceptual and psychomotor tasks.'
        ),
        limitations=(
            'This ratio is an exploratory feature and does not independently prove concentration or attention. '
            'Temporal and facial muscle micro-contractions readily inject high-amplitude artifacts across the '
            'beta spectrum on single-channel systems, which can artificially inflate the computed ratio.'
        )
    ),
    'mental_workload_ratio': IndicatorDefinition(
        key='mental_workload_ratio',
        name='Mental Workload Ratio',
        short_title='Workload',
        formula='Theta_power / Alpha_power',
        unit='ratio',
        is_experimental=True,
        scale_type='dimensionless_ratio',
        min_scale=0.0,
        max_scale=3.0,
        short_desc='Frontal theta engagement relative to alpha power.',
        full_explanation=(
            'The Mental Workload Ratio compares theta oscillations (4.0–8.0 Hz) to alpha rhythms (8.0–13.0 Hz). '
            'In cognitive neuroscience literature, working memory demands and mental arithmetic tasks often '
            'elicit increases in frontal midline theta alongside alpha suppression (event-related desynchronization).'
        ),
        limitations=(
            'Workload research requires standardized baseline subtraction and multi-channel spatial decomposition. '
            'Elevated theta can also arise from drowsiness or ocular blinks. A higher ratio alone does not establish '
            'elevated cognitive load.'
        )
    ),
    'fatigue_drowsiness_ratio': IndicatorDefinition(
        key='fatigue_drowsiness_ratio',
        name='Fatigue / Drowsiness Ratio',
        short_title='Fatigue',
        formula='(Theta_power + Alpha_power) / Beta_power',
        unit='ratio',
        is_experimental=True,
        scale_type='dimensionless_ratio',
        min_scale=0.0,
        max_scale=6.0,
        short_desc='Low-frequency synchronization relative to fast desynchronized beta.',
        full_explanation=(
            'The Fatigue / Drowsiness Ratio examines slow and idling cortical frequencies (theta plus alpha) '
            'divided by faster beta oscillations. During progressive vigilance depletion, cortical slowing '
            'often manifests as synchronized theta/alpha increases with concurrent drops in beta activity.'
        ),
        limitations=(
            'This exploratory ratio must not be used to diagnose fatigue or evaluate fitness for safety-critical tasks. '
            'Passive eyes-closed relaxation produces a similar spectral elevation without subjective exhaustion.'
        )
    ),
    'attention_ratio': IndicatorDefinition(
        key='attention_ratio',
        name='Attention Ratio (Theta/Beta)',
        short_title='Theta/Beta',
        formula='Theta_power / Beta_power',
        unit='ratio',
        is_experimental=True,
        scale_type='dimensionless_ratio',
        min_scale=0.0,
        max_scale=4.0,
        short_desc='Classic Theta-to-Beta Ratio (TBR) explored in attention research.',
        full_explanation=(
            'The Attention Ratio (Theta/Beta Ratio or TBR) quantifies low-frequency theta power relative to '
            'beta power. While historically evaluated in neurofeedback and cognitive research protocols, '
            'normative values vary substantially with subject age, time of day, and electrode placement.'
        ),
        limitations=(
            'TBR is NOT an ADHD risk index, diagnostic tool, or standalone assessment of attention deficit. '
            'Its clinical utility is strongly contested. Frontal single-channel montages differ fundamentally '
            'from standard vertex (Cz/Pz) research protocols.'
        )
    ),
}

BAND_EXPLANATIONS = {
    'delta': {
        'name': 'Delta',
        'range': '1.0–4.0 Hz (hardware-bounded)',
        'description': 'Slow-wave rhythm. In waking recordings, elevated delta is commonly influenced by galvanic skin response, eye blinks, or movement transients.',
        'clinical_caveat': 'Delta dominance in an alert subject must not be equated with deep sleep or organic pathology without verified multi-channel clinical diagnostics.'
    },
    'theta': {
        'name': 'Theta',
        'range': '4.0–8.0 Hz',
        'description': 'Intermediate rhythm linked to working memory maintenance, cognitive navigation, and transition states between wakefulness and drowsiness.',
        'clinical_caveat': 'Easily contaminated by vertical eye movements and micro-blinks in single-channel frontal electrode montages.'
    },
    'alpha': {
        'name': 'Alpha',
        'range': '8.0–13.0 Hz',
        'description': 'Classic resting rhythm reflecting cortical idling and thalamocortical synchronization during quiet wakefulness (prominent with eyes closed).',
        'clinical_caveat': 'Alpha synchronization signifies reduced visual/sensory processing; it cannot confirm emotional contentment or meditation depth on its own.'
    },
    'beta': {
        'name': 'Beta',
        'range': '13.0–30.0 Hz',
        'description': 'Fast desynchronized rhythm associated with active thinking, alertness, sensory processing, and motor planning.',
        'clinical_caveat': 'Extremely sensitive to frontalis and temporalis muscle electromyographic (EMG) tone, which can falsely mimic high cognitive arousal.'
    },
    'gamma_partial': {
        'name': 'Gamma (Partial)',
        'range': '30.0–40.0 Hz (sampling-bounded)',
        'description': 'High-frequency oscillation linked in research to multi-modal cognitive binding and sensory integration.',
        'clinical_caveat': 'Subject to severe electromyographic contamination in single-channel frontal leads; bounded at 40 Hz due to 250 Hz sampling.'
    }
}


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def calculate_eeg_indicators(bands_data: Dict[str, Any], quality_state: str = "Acceptable") -> Dict[str, Any]:
    """Calculate the five visual indicators from verified band power measurements.

    Parameters
    ----------
    bands_data : dict
        Band dictionary containing 'delta', 'theta', 'alpha', 'beta', 'gamma_partial'
        with 'relative' (fraction 0-1) and 'absolute' (ADC counts²) values.
    quality_state : str
        Signal quality classification: 'Acceptable', 'Needs review', or 'Insufficient quality'.

    Returns
    -------
    dict
        Structured indicator results with exact values, formulas, units, and availability.
    """
    is_valid_quality = quality_state != "Insufficient quality"

    # Extract relative band powers safely
    def get_band_power(b_name: str) -> Optional[float]:
        b = bands_data.get(b_name)
        if isinstance(b, dict):
            return _safe_float(b.get('relative') if b.get('relative') is not None else b.get('mean') or b.get('value'))
        return _safe_float(b)

    d_pow = get_band_power('delta')
    t_pow = get_band_power('theta')
    a_pow = get_band_power('alpha')
    b_pow = get_band_power('beta')
    g_pow = get_band_power('gamma_partial') or get_band_power('gamma')

    indicators = {}

    # 1. Calm Index
    if is_valid_quality and a_pow is not None:
        raw_score = (a_pow / 0.45) * 100.0
        calm_score = min(100.0, max(0.0, raw_score))
        indicators['calm_index'] = {
            'value': round(calm_score, 1),
            'display_value': f"{round(calm_score):d}%",
            'raw_feature_value': round(a_pow * 100.0, 1),
            'raw_feature_unit': '% relative alpha',
            'available': True,
            'unit': 'score (0–100)',
            'quality_state': quality_state,
            'definition': INDICATOR_DEFS['calm_index'],
        }
    else:
        indicators['calm_index'] = {
            'value': None,
            'display_value': '—',
            'raw_feature_value': None,
            'raw_feature_unit': '% relative alpha',
            'available': False,
            'unit': 'score (0–100)',
            'quality_state': quality_state,
            'definition': INDICATOR_DEFS['calm_index'],
            'reason': 'Insufficient signal quality or missing alpha band' if not is_valid_quality else 'Missing alpha data'
        }

    # 2. Focus Index: Beta / (Theta + Alpha)
    if is_valid_quality and b_pow is not None and t_pow is not None and a_pow is not None:
        denom = t_pow + a_pow
        if denom > 1e-9:
            f_ratio = b_pow / denom
            indicators['focus_index'] = {
                'value': round(f_ratio, 3),
                'display_value': f"{f_ratio:.2f}",
                'available': True,
                'unit': 'ratio',
                'quality_state': quality_state,
                'definition': INDICATOR_DEFS['focus_index'],
            }
        else:
            indicators['focus_index'] = {
                'value': None,
                'display_value': '—',
                'available': False,
                'unit': 'ratio',
                'quality_state': quality_state,
                'definition': INDICATOR_DEFS['focus_index'],
                'reason': 'Zero denominator (Theta + Alpha ~ 0)'
            }
    else:
        indicators['focus_index'] = {
            'value': None,
            'display_value': '—',
            'available': False,
            'unit': 'ratio',
            'quality_state': quality_state,
            'definition': INDICATOR_DEFS['focus_index'],
            'reason': 'Insufficient signal quality or missing band powers'
        }

    # 3. Mental Workload Ratio: Theta / Alpha
    if is_valid_quality and t_pow is not None and a_pow is not None:
        if a_pow > 1e-9:
            mw_ratio = t_pow / a_pow
            indicators['mental_workload_ratio'] = {
                'value': round(mw_ratio, 3),
                'display_value': f"{mw_ratio:.2f}",
                'available': True,
                'unit': 'ratio',
                'quality_state': quality_state,
                'definition': INDICATOR_DEFS['mental_workload_ratio'],
            }
        else:
            indicators['mental_workload_ratio'] = {
                'value': None,
                'display_value': '—',
                'available': False,
                'unit': 'ratio',
                'quality_state': quality_state,
                'definition': INDICATOR_DEFS['mental_workload_ratio'],
                'reason': 'Zero denominator (Alpha power ~ 0)'
            }
    else:
        indicators['mental_workload_ratio'] = {
            'value': None,
            'display_value': '—',
            'available': False,
            'unit': 'ratio',
            'quality_state': quality_state,
            'definition': INDICATOR_DEFS['mental_workload_ratio'],
            'reason': 'Insufficient signal quality or missing band powers'
        }

    # 4. Fatigue / Drowsiness Ratio: (Theta + Alpha) / Beta
    if is_valid_quality and t_pow is not None and a_pow is not None and b_pow is not None:
        if b_pow > 1e-9:
            fatigue_ratio = (t_pow + a_pow) / b_pow
            indicators['fatigue_drowsiness_ratio'] = {
                'value': round(fatigue_ratio, 3),
                'display_value': f"{fatigue_ratio:.2f}",
                'available': True,
                'unit': 'ratio',
                'quality_state': quality_state,
                'definition': INDICATOR_DEFS['fatigue_drowsiness_ratio'],
            }
        else:
            indicators['fatigue_drowsiness_ratio'] = {
                'value': None,
                'display_value': '—',
                'available': False,
                'unit': 'ratio',
                'quality_state': quality_state,
                'definition': INDICATOR_DEFS['fatigue_drowsiness_ratio'],
                'reason': 'Zero denominator (Beta power ~ 0)'
            }
    else:
        indicators['fatigue_drowsiness_ratio'] = {
            'value': None,
            'display_value': '—',
            'available': False,
            'unit': 'ratio',
            'quality_state': quality_state,
            'definition': INDICATOR_DEFS['fatigue_drowsiness_ratio'],
            'reason': 'Insufficient signal quality or missing band powers'
        }

    # 5. Attention Ratio (Theta/Beta)
    if is_valid_quality and t_pow is not None and b_pow is not None:
        if b_pow > 1e-9:
            attn_ratio = t_pow / b_pow
            indicators['attention_ratio'] = {
                'value': round(attn_ratio, 3),
                'display_value': f"{attn_ratio:.2f}",
                'available': True,
                'unit': 'ratio',
                'quality_state': quality_state,
                'definition': INDICATOR_DEFS['attention_ratio'],
            }
        else:
            indicators['attention_ratio'] = {
                'value': None,
                'display_value': '—',
                'available': False,
                'unit': 'ratio',
                'quality_state': quality_state,
                'definition': INDICATOR_DEFS['attention_ratio'],
                'reason': 'Zero denominator (Beta power ~ 0)'
            }
    else:
        indicators['attention_ratio'] = {
            'value': None,
            'display_value': '—',
            'available': False,
            'unit': 'ratio',
            'quality_state': quality_state,
            'definition': INDICATOR_DEFS['attention_ratio'],
            'reason': 'Insufficient signal quality or missing band powers'
        }

    return indicators


def determine_dominant_band(bands_data: Dict[str, Any], quality_state: str = "Acceptable") -> Dict[str, Any]:
    """Identify the dominant frequency band from real relative/absolute powers."""
    if quality_state == "Insufficient quality":
        return {
            'available': False,
            'band_key': None,
            'name': 'Unknown (Signal Insufficient)',
            'range_hz': '—',
            'relative_power_pct': None,
            'absolute_power': None,
            'description': 'Band dominance withheld due to insufficient window quality.',
            'scientific_statement': 'No authoritative spectral dominance can be calculated when signal quality fails validation thresholds.',
            'all_bands': []
        }

    valid_candidates = []
    all_bands = []

    for b_key in ['delta', 'theta', 'alpha', 'beta', 'gamma_partial']:
        b = bands_data.get(b_key)
        rel_val = None
        abs_val = None
        if isinstance(b, dict):
            rel_val = _safe_float(b.get('relative') if b.get('relative') is not None else b.get('mean'))
            abs_val = _safe_float(b.get('absolute'))
        elif isinstance(b, (int, float)):
            rel_val = _safe_float(b)

        meta = BAND_EXPLANATIONS.get(b_key, {'name': b_key.capitalize(), 'range': 'N/A', 'description': ''})
        all_bands.append({
            'key': b_key,
            'name': meta['name'],
            'range_hz': meta['range'],
            'relative_power': rel_val,
            'relative_power_pct': round(rel_val * 100.0, 1) if rel_val is not None else None,
            'absolute_power': round(abs_val, 2) if abs_val is not None else None
        })

        if rel_val is not None:
            valid_candidates.append((rel_val, abs_val, b_key, meta))

    if not valid_candidates:
        return {
            'available': False,
            'band_key': None,
            'name': 'Unavailable',
            'range_hz': '—',
            'relative_power_pct': None,
            'absolute_power': None,
            'description': 'No valid band power measurements available.',
            'scientific_statement': 'Band dominance requires at least one active, filtered frequency window.',
            'all_bands': all_bands
        }

    valid_candidates.sort(key=lambda item: item[0], reverse=True)
    best_rel, best_abs, best_key, best_meta = valid_candidates[0]
    best_pct = round(best_rel * 100.0, 1)

    abs_str = f" (absolute power: {best_abs:.1f} counts²)" if best_abs is not None else ""
    statement = (
        f"{best_meta['name']} ({best_meta['range']}) was the dominant measured frequency band in this recording, "
        f"accounting for {best_pct}% of total passband power{abs_str}. "
        f"The physiological significance of this pattern depends on recording conditions, task, electrode placement, "
        f"signal quality, and research protocol. {best_meta['description']} {best_meta.get('clinical_caveat', '')}"
    )

    return {
        'available': True,
        'band_key': best_key,
        'name': best_meta['name'],
        'range_hz': best_meta['range'],
        'relative_power': best_rel,
        'relative_power_pct': best_pct,
        'absolute_power': best_abs,
        'description': best_meta['description'],
        'scientific_statement': statement,
        'all_bands': all_bands
    }

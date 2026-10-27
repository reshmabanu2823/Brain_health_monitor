"""CORTIA Neural Test Session Documentation Generator.

Generates comprehensive, professional research documentation for recorded EEG sessions.
Sections:
  SECTION A: Session Overview
  SECTION B: Summary of the Five Indicators
  SECTION C: Frequency-Band Analysis
  SECTION D: Changes During the Session (Temporal Dynamics)
  SECTION E: Signal Quality and Reliability
  SECTION F: Overall Research Interpretation
"""
from typing import Any, Dict, List, Optional
import numpy as np
from .indicators import BAND_EXPLANATIONS, INDICATOR_DEFS, calculate_eeg_indicators, determine_dominant_band


def generate_session_documentation(
    session: Dict[str, Any],
    summary: Dict[str, Any],
    window_timeline: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Generate structured, multi-section scientific report for an EEG session."""
    q_summary = summary.get('quality_summary', {})
    q_state = q_summary.get('quality_state', 'Unknown')
    q_issues = q_summary.get('observed_issues', [])
    f_sum = summary.get('feature_summary', {})
    prep = summary.get('preprocessing_config', {})
    source_raw = session.get('source', 'unknown')
    source_name = 'Maker UNO Serial (BioAmp EXG Pill)' if source_raw == 'serial' else 'Simulated Biopotential Stream (Synthetic 10 Hz + 6 Hz)'
    duration_s = session.get('duration_seconds', 0.0)
    sample_count = session.get('sample_count', 0)
    sample_rate = session.get('measured_rate_hz') or session.get('config', {}).get('sample_rate', 250)
    notes = session.get('notes') or summary.get('notes') or 'No protocol notes recorded.'

    # Reconstruct bands dictionary for indicators calculation
    bands_input = {
        'delta': {'relative': f_sum.get('delta_relative_power', {}).get('mean'), 'absolute': f_sum.get('delta_absolute_power', {}).get('mean')},
        'theta': {'relative': f_sum.get('theta_relative_power', {}).get('mean'), 'absolute': f_sum.get('theta_absolute_power', {}).get('mean')},
        'alpha': {'relative': f_sum.get('alpha_relative_power', {}).get('mean'), 'absolute': f_sum.get('alpha_absolute_power', {}).get('mean')},
        'beta': {'relative': f_sum.get('beta_relative_power', {}).get('mean'), 'absolute': f_sum.get('beta_absolute_power', {}).get('mean')},
        'gamma_partial': {'relative': f_sum.get('gamma_partial_relative_power', {}).get('mean'), 'absolute': f_sum.get('gamma_partial_absolute_power', {}).get('mean')},
    }

    # If keys were named relative_delta_power (backwards compat)
    if bands_input['delta']['relative'] is None and 'relative_delta_power' in f_sum:
        for b in ['delta', 'theta', 'alpha', 'beta', 'gamma']:
            key = f'relative_{b}_power'
            b_key = 'gamma_partial' if b == 'gamma' else b
            if key in f_sum:
                bands_input[b_key]['relative'] = f_sum[key].get('mean')

    indicators = calculate_eeg_indicators(bands_input, quality_state=q_state)
    dominant_band = determine_dominant_band(bands_input, quality_state=q_state)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION A: Session Overview
    # ──────────────────────────────────────────────────────────────────────────
    window_count = q_summary.get('total_windows', 0)
    sec_a = {
        'title': 'Section A — Session Overview',
        'session_id': session.get('id', 'N/A'),
        'started_utc': session.get('started_utc', 'N/A'),
        'ended_utc': session.get('ended_utc', 'N/A'),
        'duration_seconds': duration_s,
        'duration_formatted': f"{duration_s:.2f} seconds ({duration_s / 60.0:.1f} minutes)",
        'hardware_source': source_name,
        'sampling_rate_hz': round(float(sample_rate), 1) if sample_rate else 250.0,
        'sample_count': sample_count,
        'usable_windows': window_count,
        'quality_state': q_state,
        'preprocessing_details': {
            'filter_type': prep.get('filter_type', 'Butterworth 4th-order zero-phase'),
            'passband_hz': prep.get('cutoffs_hz', [1.0, 40.0]),
            'notch_hz': prep.get('notch_hz', 50.0),
            'window_seconds': prep.get('window_seconds', 4.0),
            'guard_seconds': prep.get('guard_seconds', 1.0)
        },
        'narrative': (
            f"This session was acquired on {session.get('started_utc', 'N/A')} utilizing {source_name}. "
            f"A total of {sample_count:,} biopotential samples were logged across a duration of {duration_s:.2f} seconds "
            f"at an effective sampling rate of {round(float(sample_rate), 1) if sample_rate else 250.0} Hz. "
            f"The continuous signal was buffered into {window_count} sliding analysis windows (4.0 s window duration with 1.0 s edge guards). "
            f"Pre-filtering applied a zero-phase 4th-order Butterworth bandpass (1.0–40.0 Hz) and a 50 Hz notch filter to attenuate mains interference. "
            f"Hardware constraints: Uncalibrated 10-bit analog-to-digital converter (0–1023 integer counts) recorded from a single bipolar biopotential channel."
        )
    }

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION B: Summary of the Five Indicators
    # ──────────────────────────────────────────────────────────────────────────
    sec_b_indicators = []
    for key in ['calm_index', 'focus_index', 'mental_workload_ratio', 'fatigue_drowsiness_ratio', 'attention_ratio']:
        ind = indicators[key]
        defn = ind['definition']
        val_str = ind['display_value']
        unit_str = ind['unit']

        # Construct specific clinical/scientific narrative for each indicator
        if ind['available'] and ind['value'] is not None:
            val = ind['value']
            if key == 'calm_index':
                meaning = (
                    f"A Calm Index of {val_str} reflects a relative alpha power contribution of {ind.get('raw_feature_value', 0.0)}% "
                    f"across the recording. In resting awake state, higher alpha power indicates synchronized cortical idling. "
                    f"This score suggests the subject maintained moderate-to-strong rhythmic occipital/frontal alpha synchronization."
                )
            elif key == 'focus_index':
                meaning = (
                    f"The computed Focus Ratio of {val_str} ({unit_str}) indicates that beta activity comprised approximately "
                    f"{val:.2f} times the combined power of slow theta and alpha waves. In engagement protocols, higher beta proportions "
                    f"reflect cortical desynchronization accompanying alert processing."
                )
            elif key == 'mental_workload_ratio':
                meaning = (
                    f"A Mental Workload Ratio of {val_str} (Theta/Alpha) documents the spectral relationship between memory/executive theta "
                    f"and sensory idling alpha. Ratios below 1.0 indicate dominant alpha power, whereas values above 1.0 reflect prominent theta "
                    f"engagement relative to resting rhythm."
                )
            elif key == 'fatigue_drowsiness_ratio':
                meaning = (
                    f"The Fatigue / Drowsiness Ratio of {val_str} expresses the sum of slow oscillations (Theta + Alpha) divided by fast Beta. "
                    f"Elevated values occur during periods of deep relaxation or progressive drowsiness, as well as during passive eyes-closed resting."
                )
            elif key == 'attention_ratio':
                meaning = (
                    f"The Attention Ratio (TBR) was calculated at {val_str}. In research literature, Theta/Beta ratios are monitored to track "
                    f"shifts between low-frequency and high-frequency spectral density. This value serves as a descriptive baseline for this recording setup."
                )
            else:
                meaning = f"Calculated value: {val_str} {unit_str}."
        else:
            meaning = f"Indicator unavailable: {ind.get('reason', 'Quality check failure or zero denominator')}."

        sec_b_indicators.append({
            'key': key,
            'name': defn.name,
            'short_title': defn.short_title,
            'value': ind['value'],
            'display_value': val_str,
            'unit': unit_str,
            'formula': defn.formula,
            'available': ind['available'],
            'quality_state': ind['quality_state'],
            'what_it_measures': defn.short_desc,
            'how_calculated': f"Calculated as: {defn.formula}. Both numerator and denominator were extracted using Welch PSD over 4.0-second epochs with 1.0-second guard bands.",
            'what_result_means': meaning,
            'important_limitations': defn.limitations
        })

    sec_b = {
        'title': 'Section B — Summary of the Five Indicators',
        'indicators': sec_b_indicators,
        'summary_statement': (
            "All five indicators are experimental research metrics derived from single-channel biopotential spectral density. "
            "They are not clinical diagnoses, psychological state certifications, or standalone tests of mental health."
        )
    }

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION C: Frequency-Band Analysis
    # ──────────────────────────────────────────────────────────────────────────
    bands_list = []
    for b_key in ['delta', 'theta', 'alpha', 'beta', 'gamma_partial']:
        meta = BAND_EXPLANATIONS.get(b_key, {})
        rel_key = f"{b_key}_relative_power"
        abs_key = f"{b_key}_absolute_power"
        rel_val = f_sum.get(rel_key, {}).get('mean')
        abs_val = f_sum.get(abs_key, {}).get('mean')

        # Fallback for alternative naming
        if rel_val is None:
            old_rel = f"relative_{b_key.replace('_partial', '')}_power"
            if old_rel in f_sum:
                rel_val = f_sum[old_rel].get('mean')

        rel_pct_str = f"{rel_val * 100.0:.1f}%" if rel_val is not None else "N/A"
        abs_str = f"{abs_val:.2f} counts²" if abs_val is not None else "N/A"

        bands_list.append({
            'key': b_key,
            'name': meta.get('name', b_key.capitalize()),
            'frequency_range': meta.get('range', '—'),
            'relative_power_fraction': round(rel_val, 4) if rel_val is not None else None,
            'relative_power_pct_display': rel_pct_str,
            'absolute_power': round(abs_val, 2) if abs_val is not None else None,
            'absolute_power_display': abs_str,
            'description': meta.get('description', ''),
            'interpretation_boundaries': meta.get('clinical_caveat', '')
        })

    sec_c = {
        'title': 'Section C — Frequency-Band Analysis',
        'dominant_band': dominant_band,
        'bands': bands_list,
        'narrative': (
            f"{dominant_band.get('scientific_statement', '')} "
            "Power units represent uncalibrated ADC counts² from the 10-bit hardware converter; "
            "relative powers express each band's fractional contribution to total integrated 1.0–40.0 Hz passband energy."
        )
    }

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION D: Changes During the Session (Temporal Dynamics)
    # ──────────────────────────────────────────────────────────────────────────
    timeline_available = window_timeline is not None and len(window_timeline) >= 2
    timeline_summary = {}

    if timeline_available:
        n_win = len(window_timeline)
        first_win = window_timeline[0]
        last_win = window_timeline[-1]

        # Beginning vs end window comparisons
        start_calm = first_win.get('indicators', {}).get('calm_index', {}).get('value')
        end_calm = last_win.get('indicators', {}).get('calm_index', {}).get('value')
        start_focus = first_win.get('indicators', {}).get('focus_index', {}).get('value')
        end_focus = last_win.get('indicators', {}).get('focus_index', {}).get('value')
        start_workload = first_win.get('indicators', {}).get('mental_workload_ratio', {}).get('value')
        end_workload = last_win.get('indicators', {}).get('mental_workload_ratio', {}).get('value')

        timeline_narrative = (
            f"Temporal analysis across {n_win} successive recording epochs demonstrated dynamic spectral modulation. "
            f"The Calm Index evolved from an initial {start_calm if start_calm is not None else 'N/A'}% to {end_calm if end_calm is not None else 'N/A'}% in the final window. "
            f"The Focus Index recorded {start_focus if start_focus is not None else 'N/A'} initially and {end_focus if end_focus is not None else 'N/A'} at session conclusion. "
            f"The Mental Workload Ratio moved from {start_workload if start_workload is not None else 'N/A'} to {end_workload if end_workload is not None else 'N/A'}. "
            "Observed variations reflect real physiological transitions, ocular adaptation, or posture shifts throughout the acquisition period."
        )

        timeline_summary = {
            'available': True,
            'window_count': n_win,
            'first_window_timestamp_s': first_win.get('timestamp_s', 0.0),
            'last_window_timestamp_s': last_win.get('timestamp_s', duration_s),
            'calm_trajectory': {'start': start_calm, 'end': end_calm},
            'focus_trajectory': {'start': start_focus, 'end': end_focus},
            'workload_trajectory': {'start': start_workload, 'end': end_workload},
            'narrative': timeline_narrative
        }
    else:
        timeline_summary = {
            'available': False,
            'window_count': window_count,
            'narrative': (
                "Longitudinal session trend analysis requires multiple contiguous recording epochs (minimum 2 analysis windows). "
                f"This session was recorded with a short duration ({duration_s:.1f} s, {window_count} complete window); "
                "consequently, longitudinal intra-session trend modeling is unavailable for this specific test."
            )
        }

    sec_d = {
        'title': 'Section D — Changes During the Session',
        'timeline': timeline_summary,
        'windows': window_timeline or []
    }

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION E: Signal Quality and Reliability
    # ──────────────────────────────────────────────────────────────────────────
    passed_all = q_state == 'Acceptable'
    sec_e = {
        'title': 'Section E — Signal Quality and Reliability',
        'overall_quality_state': q_state,
        'acceptable_windows': q_summary.get('acceptable_windows', 0),
        'needs_review_windows': q_summary.get('needs_review_windows', 0),
        'insufficient_windows': q_summary.get('insufficient_windows', 0),
        'total_windows': window_count,
        'observed_quality_issues': q_issues,
        'passed_verification': passed_all,
        'narrative': (
            f"The overall recording quality was classified as **{q_state}**. "
            f"{'The biopotential telemetry remained within acceptable physiological ADC count boundaries throughout the session.' if passed_all else f'Quality checks identified the following observed conditions: {', '.join(q_issues) if q_issues else 'elevated variance or noise transients'}.'} "
            "Quality heuristics actively monitor for sensor clipping (0 or 1023 count saturation), flatline (<0.5 ADC variance), "
            "abrupt baseline steps (>150 counts), and packet jitter (>15%). "
            f"{'Because the recording met validation criteria, derived band powers and spectral ratios provide reliable experimental measures.' if passed_all else 'When quality is downgraded, downstream ratio calculations may be perturbed by mechanical electrode movement or muscle tension.'}"
        )
    }

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION F: Overall Research Interpretation
    # ──────────────────────────────────────────────────────────────────────────
    interpretation_points = []
    interpretation_points.append(f"Recorded biopotential activity was characterized by dominant **{dominant_band.get('name', 'spectral')}** power ({dominant_band.get('relative_power_pct', 0.0)}% of total energy).")
    if indicators['calm_index']['available']:
        interpretation_points.append(f"Calm Index of {indicators['calm_index']['display_value']} indicates moderate-to-strong alpha synchronization.")
    if indicators['focus_index']['available']:
        interpretation_points.append(f"Focus Ratio of {indicators['focus_index']['display_value']} indicates balanced high-frequency to slow-frequency spectral energy.")
    if indicators['mental_workload_ratio']['available']:
        interpretation_points.append(f"Mental Workload Ratio of {indicators['mental_workload_ratio']['display_value']} reflects low-to-moderate frontal theta predominance relative to resting alpha.")

    sec_f = {
        'title': 'Section F — Overall Research Interpretation',
        'protocol_notes': notes,
        'observations': interpretation_points,
        'ethical_boundaries': [
            "This documentation report is strictly intended for scientific research and educational protocol validation.",
            "Single-channel frontal biopotentials CANNOT diagnose psychiatric or neurological conditions (e.g., ADHD, clinical depression, anxiety disorders, epilepsy, sleep staging).",
            "No combined or composite 'brain health score' is generated, as such universal metrics lack scientific foundation in single-lead electrophysiology."
        ],
        'conclusion_narrative': (
            f"In summary, session #{session.get('id', 'N/A')[:8]} provided {duration_s:.1f} seconds of biopotential recording with {q_state.lower()} signal fidelity. "
            f"The spectral profile demonstrated dominant {dominant_band.get('name', 'band')} oscillations. "
            "These findings provide reproducible experimental baseline telemetry for the specified research protocol. "
            "Further comparative studies under controlled task conditions (eyes-open vs. eyes-closed, cognitive challenge) are recommended to establish individualized reactivity."
        )
    }

    return {
        'session_overview': sec_a,
        'indicators_summary': sec_b,
        'frequency_band_analysis': sec_c,
        'session_temporal_dynamics': sec_d,
        'signal_quality_assessment': sec_e,
        'overall_research_interpretation': sec_f,
        'dominant_band': dominant_band,
        'five_indicators': indicators
    }


def get_historical_comparisons(
    current_session_id: str,
    recent_sessions: List[Dict[str, Any]],
    store: Any
) -> Dict[str, Any]:
    """Compare the active session with prior comparable sessions of the same hardware protocol."""
    curr = store.get(current_session_id)
    curr_source = curr.get('source')
    curr_summary = store.get_summary(current_session_id, refresh_docs=False)
    curr_indicators = curr_summary.get('indicators', {})

    comparable_sessions = []
    for s in recent_sessions:
        if s.get('id') == current_session_id:
            continue
        if s.get('source') == curr_source and s.get('status') == 'completed':
            try:
                s_sum = store.get_summary(s['id'], refresh_docs=False)
                s_ind = s_sum.get('indicators', {})
                s_dom = s_sum.get('dominant_band', {})
                comparable_sessions.append({
                    'id': s['id'],
                    'started_utc': s.get('started_utc'),
                    'duration_seconds': s.get('duration_seconds', 0.0),
                    'quality_state': s_sum.get('quality_summary', {}).get('quality_state', 'Unknown'),
                    'calm_index': s_ind.get('calm_index', {}).get('value'),
                    'focus_index': s_ind.get('focus_index', {}).get('value'),
                    'workload_ratio': s_ind.get('mental_workload_ratio', {}).get('value'),
                    'fatigue_ratio': s_ind.get('fatigue_drowsiness_ratio', {}).get('value'),
                    'attention_ratio': s_ind.get('attention_ratio', {}).get('value'),
                    'dominant_band': s_dom.get('name', 'N/A')
                })
            except Exception:
                continue

        if len(comparable_sessions) >= 5:
            break

    if not comparable_sessions:
        return {
            'available': False,
            'reason': 'No prior completed sessions with matching protocol were found in local storage.',
            'sessions': []
        }

    # Compute comparative deltas with the most recent prior session
    prior = comparable_sessions[0]
    deltas = {}
    for key, curr_val, prior_val in [
        ('calm_index', curr_indicators.get('calm_index', {}).get('value'), prior.get('calm_index')),
        ('focus_index', curr_indicators.get('focus_index', {}).get('value'), prior.get('focus_index')),
        ('workload_ratio', curr_indicators.get('mental_workload_ratio', {}).get('value'), prior.get('workload_ratio')),
        ('fatigue_ratio', curr_indicators.get('fatigue_drowsiness_ratio', {}).get('value'), prior.get('fatigue_ratio')),
        ('attention_ratio', curr_indicators.get('attention_ratio', {}).get('value'), prior.get('attention_ratio')),
    ]:
        if curr_val is not None and prior_val is not None:
            diff = round(curr_val - prior_val, 2)
            deltas[key] = {
                'current': curr_val,
                'prior': prior_val,
                'delta': diff,
                'direction': 'increased' if diff > 0 else ('decreased' if diff < 0 else 'unchanged')
            }

    narrative = (
        f"Comparing current session #{current_session_id[:8]} with the immediate prior test on {prior['started_utc']} "
        f"({prior['duration_seconds']:.1f} s, quality: {prior['quality_state']}): "
    )
    if 'calm_index' in deltas:
        narrative += f"Calm Index shifted from {prior['calm_index']}% to {curr_indicators.get('calm_index', {}).get('value')}% (Δ {deltas['calm_index']['delta']:+0.1f}%). "
    if 'focus_index' in deltas:
        narrative += f"Focus Ratio shifted from {prior['focus_index']} to {curr_indicators.get('focus_index', {}).get('value')} (Δ {deltas['focus_index']['delta']:+0.2f}). "
    narrative += "Variations across test sessions can arise from skin-electrode impedance fluctuations, ambient electrical environment, circadian phase, or baseline alertness."

    return {
        'available': True,
        'comparable_count': len(comparable_sessions),
        'prior_session_id': prior['id'],
        'prior_session_date': prior['started_utc'],
        'deltas': deltas,
        'narrative': narrative,
        'sessions': comparable_sessions
    }

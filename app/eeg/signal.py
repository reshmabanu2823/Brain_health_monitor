"""Validated offline windows. Power units: ADC counts²; PSD: counts²/Hz.

Quality checks are engineering heuristics, not electrode/contact or disease
validation. Finite windows use explicit edge guards; no zero-filled missing data.
"""
from dataclasses import asdict, dataclass
import math
import numpy as np
from scipy.signal import butter, detrend, iirnotch, sosfiltfilt, tf2sos, welch

PIPELINE_VERSION = "2.5.0-signal-intelligence"

# Exact band definitions: Delta is bounded at 1.0 Hz (not 0.5) due to hardware highpass and baseline drift.
# Gamma is bounded at 40.0 Hz (partial gamma) due to 250 Hz sampling and high-frequency muscle sensitivity.
BANDS = {'delta': (1., 4.), 'theta': (4., 8.), 'alpha': (8., 13.),
         'beta': (13., 30.), 'gamma_partial': (30., 40.)}
FEATURE_NAMES = tuple([f'{b}_relative_power' for b in BANDS] +
                      ['variance', 'hjorth_mobility', 'hjorth_complexity', 'spectral_entropy'])

# Explicit three-state quality taxonomy
QUALITY_ACCEPTABLE = "Acceptable"
QUALITY_NEEDS_REVIEW = "Needs review"
QUALITY_INSUFFICIENT = "Insufficient quality"


@dataclass(frozen=True)
class SignalConfig:
    sample_rate: int = 250
    window_seconds: float = 4.
    guard_seconds: float = 1.
    low_hz: float = 1.
    high_hz: float = 40.
    notch_hz: float | None = 50.
    adc_max: int = 1023
    max_step: float = 150.
    rate_tolerance: float = .02
    jitter_tolerance: float = .15

    def __post_init__(self):
        numbers = [v for v in asdict(self).values() if v is not None]
        if not all(math.isfinite(v) for v in numbers):
            raise ValueError('Signal settings must be finite')
        if not 100 <= self.sample_rate <= 250 or not 0 < self.low_hz < self.high_hz < self.sample_rate / 2:
            raise ValueError('Need 100–250 Hz sample rate and 0 < low < high < Nyquist')
        if self.notch_hz is not None and not 0 < self.notch_hz < self.sample_rate / 2:
            raise ValueError('Notch must be below Nyquist; use null to disable')
        if not 2 <= self.window_seconds <= 30 or not 1 <= self.guard_seconds <= 5:
            raise ValueError('Window must be 2–30 s with 1–5 s edge guards')
        if self.adc_max != 1023 or self.max_step <= 0 or not 0 < self.rate_tolerance <= .1 or not 0 < self.jitter_tolerance < .5:
            raise ValueError('Invalid ADC or quality settings')

    @property
    def input_samples(self):
        return round(self.sample_rate * (self.window_seconds + 2 * self.guard_seconds))


def get_preprocessing_record(config: SignalConfig):
    """Structured record of exact filter & window parameters for scientific reproducibility."""
    return {
        'filter_type': 'butterworth',
        'filter_order': 4,
        'filter_mode': 'sosfiltfilt_zero_phase',
        'cutoffs_hz': [config.low_hz, config.high_hz],
        'notch_hz': config.notch_hz,
        'notch_q': 30.0 if config.notch_hz else None,
        'window_seconds': config.window_seconds,
        'guard_seconds': config.guard_seconds,
        'sample_rate_hz': config.sample_rate,
        'adc_max': config.adc_max,
        'software_version': PIPELINE_VERSION
    }


def segment(length, size, hop):
    if size <= 0 or hop <= 0:
        raise ValueError('Positive segment and hop sizes required')
    for start in range(0, length - size + 1, hop):
        yield start, start + size


def analyze(timestamps, values, config):
    """Evaluate quality, filter window, and extract spectral features.
    
    Withholds inference on Insufficient quality; never invents values or calls
    signals clinically normal/abnormal.
    """
    t, x = np.asarray(timestamps, dtype=float), np.asarray(values, dtype=float)
    prep_record = get_preprocessing_record(config)

    def invalid(human_reason, machine_reason, quality_state=QUALITY_INSUFFICIENT):
        return {
            'valid': False,
            'quality_state': quality_state,
            'quality_reasons': [machine_reason],
            'reasons': [human_reason],
            'units': 'adc_counts',
            'features': None,
            'feature_metrics': None,
            'synchronized_waveform': None,
            'prediction': None,
            'preprocessing': prep_record
        }

    if t.ndim != 1 or x.ndim != 1 or len(t) != len(x):
        return invalid('Expected matching one-dimensional timestamps and samples', 'dimension_mismatch')
    if len(x) < config.input_samples:
        return invalid('Insufficient samples including filter edge guards', 'insufficient_duration')
    t, x = t[-config.input_samples:], x[-config.input_samples:]
    if not np.isfinite(t).all() or not np.isfinite(x).all():
        return invalid('Missing or non-finite samples', 'missing_or_non_finite_samples')
    dt = np.diff(t)
    if np.any(dt <= 0):
        return invalid('Non-increasing timestamps', 'non_increasing_timestamps')
    fs = float((len(t) - 1) / (t[-1] - t[0]))
    if abs(fs / config.sample_rate - 1) > config.rate_tolerance:
        return invalid('Measured sampling rate differs from configured rate', 'sampling_rate_deviation')
    max_jitter = float(np.max(np.abs(dt * fs - 1)))
    if max_jitter > config.jitter_tolerance:
        return invalid('Sampling jitter or missing samples exceeds tolerance', 'sampling_jitter_exceeded')
    if np.any((x < 0) | (x > config.adc_max)):
        return invalid('Sample outside ADC range', 'sample_outside_adc_range')
    clip_ratio = float(np.mean((x <= 1) | (x >= config.adc_max - 1)))
    if clip_ratio > .01:
        return invalid('ADC clipping exceeds 1%', 'saturation_clipping')
    raw_std = float(np.std(x))
    flat_ratio = float(np.mean(np.diff(x) == 0))
    if raw_std < .5 or flat_ratio > .95:
        return invalid('Flat or near-flat input', 'flatline')
    max_step_val = float(np.max(np.abs(np.diff(x))))
    if max_step_val > config.max_step:
        return invalid('Abrupt transient exceeds configured ADC-count limit', 'excessive_noise_step')
    if raw_std > 350. or float(np.ptp(x)) > 950.:
        return invalid('Excessive raw biopotential amplitude', 'excessive_amplitude')

    # Preprocessing: detrend, notch, 4th-order Butterworth bandpass
    y = detrend(x, type='linear')
    if config.notch_hz:
        if config.notch_hz >= fs / 2:
            return invalid('Notch is invalid at measured rate', 'notch_exceeds_nyquist')
        b, a = iirnotch(config.notch_hz, 30, fs=fs)
        y = sosfiltfilt(tf2sos(b, a), y)
    if config.high_hz >= fs / 2:
        return invalid('Bandpass is invalid at measured rate', 'bandpass_exceeds_nyquist')
    y = sosfiltfilt(butter(4, [config.low_hz, config.high_hz], btype='bandpass', fs=fs, output='sos'), y)

    # Discard 1s edge guards to eliminate filter ringing transients
    guard = round(config.guard_seconds * config.sample_rate)
    filtered_active = y[guard:-guard]
    raw_active = x[guard:-guard]
    active_t = t[guard:-guard]

    # Spectral Estimation via Welch Periodogram
    f, psd = welch(filtered_active, fs=fs, nperseg=min(len(filtered_active), round(2 * fs)),
                   detrend='constant', scaling='density')
    df = f[1] - f[0]
    selection = (f >= config.low_hz) & (f <= config.high_hz)
    total = float(np.sum(psd[selection]) * df)
    if total <= np.finfo(float).eps:
        return invalid('No measurable power in passband', 'no_passband_power')

    # Band power decomposition
    bands = {}
    for name, (lo, hi) in BANDS.items():
        available = lo >= config.low_hz and hi <= config.high_hz
        mask = (f >= lo) & (f < hi)
        power = float(np.sum(psd[mask]) * df) if available else None
        bands[name] = {
            'range_hz': [lo, hi],
            'absolute': power,
            'relative': power / total if power is not None else None,
            'available': available
        }

    # Core statistical and complexity metrics
    variance = float(np.var(filtered_active))
    mean_val = float(np.mean(filtered_active))
    rms_val = float(np.sqrt(np.mean(filtered_active ** 2)))
    d1 = np.diff(filtered_active) * fs
    d2 = np.diff(filtered_active, n=2) * fs ** 2
    mobility = float(np.sqrt(np.var(d1) / max(variance, 1e-15)))
    complexity = float(np.sqrt(np.var(d2) / max(np.var(d1), 1e-15)) / max(mobility, 1e-15))
    p = psd[selection] / np.sum(psd[selection])
    entropy = float(-np.sum(p * np.log2(p + 1e-30)) / np.log2(len(p)))
    peak_idx = int(np.argmax(psd[selection]))
    peak_freq = float(f[selection][peak_idx])

    # Preserved 9-element feature vector for backwards-compatible model inference
    features = [bands[b]['relative'] for b in BANDS] + [variance, mobility, complexity, entropy]

    # Evaluated 3-state quality taxonomy and machine-readable reasons
    quality_state = QUALITY_ACCEPTABLE
    quality_reasons = []
    if clip_ratio > 0.0:
        quality_state = QUALITY_NEEDS_REVIEW
        quality_reasons.append('minor_clipping_observed')
    if max_step_val > 90.:
        quality_state = QUALITY_NEEDS_REVIEW
        quality_reasons.append('moderate_transient_detected')
    if max_jitter > 0.08:
        quality_state = QUALITY_NEEDS_REVIEW
        quality_reasons.append('elevated_sampling_jitter')
    if float(np.std(filtered_active)) > 110.:
        quality_state = QUALITY_NEEDS_REVIEW
        quality_reasons.append('elevated_filtered_amplitude')
    if bands['gamma_partial']['relative'] and bands['gamma_partial']['relative'] > 0.35:
        quality_state = QUALITY_NEEDS_REVIEW
        quality_reasons.append('suspected_muscle_contamination_in_gamma')

    # Rich feature dictionary with explicit units, window durations, and band limits
    feature_metrics = {
        'delta_relative_power': {'value': bands['delta']['relative'], 'unit': 'fraction', 'window_length_s': config.window_seconds, 'band_definition': '1.0–4.0 Hz (hardware-bounded)'},
        'delta_absolute_power': {'value': bands['delta']['absolute'], 'unit': 'adc_counts_squared', 'window_length_s': config.window_seconds, 'band_definition': '1.0–4.0 Hz (hardware-bounded)'},
        'theta_relative_power': {'value': bands['theta']['relative'], 'unit': 'fraction', 'window_length_s': config.window_seconds, 'band_definition': '4.0–8.0 Hz'},
        'theta_absolute_power': {'value': bands['theta']['absolute'], 'unit': 'adc_counts_squared', 'window_length_s': config.window_seconds, 'band_definition': '4.0–8.0 Hz'},
        'alpha_relative_power': {'value': bands['alpha']['relative'], 'unit': 'fraction', 'window_length_s': config.window_seconds, 'band_definition': '8.0–13.0 Hz'},
        'alpha_absolute_power': {'value': bands['alpha']['absolute'], 'unit': 'adc_counts_squared', 'window_length_s': config.window_seconds, 'band_definition': '8.0–13.0 Hz'},
        'beta_relative_power': {'value': bands['beta']['relative'], 'unit': 'fraction', 'window_length_s': config.window_seconds, 'band_definition': '13.0–30.0 Hz'},
        'beta_absolute_power': {'value': bands['beta']['absolute'], 'unit': 'adc_counts_squared', 'window_length_s': config.window_seconds, 'band_definition': '13.0–30.0 Hz'},
        'gamma_partial_relative_power': {'value': bands['gamma_partial']['relative'], 'unit': 'fraction', 'window_length_s': config.window_seconds, 'band_definition': 'partial 30.0–40.0 Hz (muscle sensitive)'},
        'gamma_partial_absolute_power': {'value': bands['gamma_partial']['absolute'], 'unit': 'adc_counts_squared', 'window_length_s': config.window_seconds, 'band_definition': 'partial 30.0–40.0 Hz (muscle sensitive)'},
        'peak_frequency_hz': {'value': peak_freq, 'unit': 'Hz', 'window_length_s': config.window_seconds, 'band_definition': '1.0–40.0 Hz passband peak'},
        'mean': {'value': mean_val, 'unit': 'adc_counts', 'window_length_s': config.window_seconds, 'band_definition': 'filtered baseline'},
        'variance': {'value': variance, 'unit': 'adc_counts_squared', 'window_length_s': config.window_seconds, 'band_definition': 'filtered variance'},
        'rms': {'value': rms_val, 'unit': 'adc_counts', 'window_length_s': config.window_seconds, 'band_definition': 'root-mean-square amplitude'},
        'signal_power': {'value': total, 'unit': 'adc_counts_squared', 'window_length_s': config.window_seconds, 'band_definition': 'total integrated passband power'},
        'spectral_entropy': {'value': entropy, 'unit': 'dimensionless', 'window_length_s': config.window_seconds, 'band_definition': 'normalized spectral entropy (0–1)'},
        'hjorth_mobility': {'value': mobility, 'unit': 'dimensionless', 'window_length_s': config.window_seconds, 'band_definition': 'mean frequency indicator'},
        'hjorth_complexity': {'value': complexity, 'unit': 'dimensionless', 'window_length_s': config.window_seconds, 'band_definition': 'bandwidth indicator'}
    }

    # Synchronized raw vs. filtered waveform for UI comparison
    synchronized_waveform = {
        'timestamps_s': [round(float(s), 4) for s in active_t],
        'raw_adc': [float(v) for v in raw_active],
        'filtered_adc': [round(float(v), 2) for v in filtered_active],
        'units': 'adc_counts',
        'window_length_s': config.window_seconds
    }

    return {
        'valid': True,
        'quality_state': quality_state,
        'quality_reasons': quality_reasons,
        'reasons': [],
        'units': 'adc_counts',
        'measured_rate_hz': fs,
        'window_start_s': float(active_t[0]),
        'window_end_s': float(active_t[-1]),
        'bands': bands,
        'frequencies_hz': f[selection].tolist(),
        'psd': psd[selection].tolist(),
        'power_units': 'adc_counts_squared',
        'feature_names': list(FEATURE_NAMES),
        'features': features,
        'feature_metrics': feature_metrics,
        'synchronized_waveform': synchronized_waveform,
        'preprocessing': prep_record,
        'warnings': [
            'Quality checks cannot verify EEG origin or exclude muscle/eye artifacts.',
            '30–40 Hz is partial gamma and sensitive to muscle contamination.'
        ]
    }

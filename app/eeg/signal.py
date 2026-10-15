"""Validated offline windows. Power units: ADC counts²; PSD: counts²/Hz.

Quality checks are engineering heuristics, not electrode/contact or disease
validation. Finite windows use explicit edge guards; no zero-filled missing data.
"""
from dataclasses import asdict, dataclass
import math
import numpy as np
from scipy.signal import butter, detrend, iirnotch, sosfiltfilt, tf2sos, welch

BANDS = {'delta': (1., 4.), 'theta': (4., 8.), 'alpha': (8., 13.),
         'beta': (13., 30.), 'gamma_partial': (30., 40.)}
FEATURE_NAMES = tuple([f'{b}_relative_power' for b in BANDS] +
                      ['variance', 'hjorth_mobility', 'hjorth_complexity', 'spectral_entropy'])


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


def segment(length, size, hop):
    if size <= 0 or hop <= 0:
        raise ValueError('Positive segment and hop sizes required')
    for start in range(0, length - size + 1, hop):
        yield start, start + size


def analyze(timestamps, values, config):
    """Return unavailable with reasons on invalid windows; never impute gaps."""
    t, x = np.asarray(timestamps, dtype=float), np.asarray(values, dtype=float)
    invalid = lambda reason: {'valid': False, 'reasons': [reason], 'units': 'adc_counts',
                               'features': None, 'prediction': None}
    if t.ndim != 1 or x.ndim != 1 or len(t) != len(x):
        return invalid('Expected matching one-dimensional timestamps and samples')
    if len(x) < config.input_samples:
        return invalid('Insufficient samples including filter edge guards')
    t, x = t[-config.input_samples:], x[-config.input_samples:]
    if not np.isfinite(t).all() or not np.isfinite(x).all():
        return invalid('Missing or non-finite samples')
    dt = np.diff(t)
    if np.any(dt <= 0):
        return invalid('Non-increasing timestamps')
    fs = float((len(t)-1)/(t[-1]-t[0]))
    if abs(fs/config.sample_rate - 1) > config.rate_tolerance:
        return invalid('Measured sampling rate differs from configured rate')
    if np.max(np.abs(dt * fs - 1)) > config.jitter_tolerance:
        return invalid('Sampling jitter or missing samples exceeds tolerance')
    if np.any((x < 0) | (x > config.adc_max)):
        return invalid('Sample outside ADC range')
    if np.mean((x <= 1) | (x >= config.adc_max-1)) > .01:
        return invalid('ADC clipping exceeds 1%')
    if np.std(x) < .5 or np.mean(np.diff(x) == 0) > .95:
        return invalid('Flat or near-flat input')
    if np.max(np.abs(np.diff(x))) > config.max_step:
        return invalid('Abrupt transient exceeds configured ADC-count limit')
    y = detrend(x, type='linear')
    if config.notch_hz:
        if config.notch_hz >= fs / 2:
            return invalid('Notch is invalid at measured rate')
        b, a = iirnotch(config.notch_hz, 30, fs=fs)
        y = sosfiltfilt(tf2sos(b, a), y)
    if config.high_hz >= fs/2:
        return invalid('Bandpass is invalid at measured rate')
    y = sosfiltfilt(butter(4, [config.low_hz, config.high_hz], btype='bandpass', fs=fs, output='sos'), y)
    guard = round(config.guard_seconds * config.sample_rate)
    y = y[guard:-guard]
    f, psd = welch(y, fs=fs, nperseg=min(len(y), round(2*fs)), detrend='constant', scaling='density')
    df = f[1]-f[0]
    selection = (f >= config.low_hz) & (f <= config.high_hz)
    total = float(np.sum(psd[selection]) * df)
    if total <= np.finfo(float).eps:
        return invalid('No measurable power in passband')
    bands = {}
    for name, (lo, hi) in BANDS.items():
        available = lo >= config.low_hz and hi <= config.high_hz
        mask = (f >= lo) & (f < hi)
        power = float(np.sum(psd[mask]) * df) if available else None
        bands[name] = {'range_hz': [lo, hi], 'absolute': power,
                       'relative': power/total if power is not None else None,
                       'available': available}
    variance = float(np.var(y))
    d1, d2 = np.diff(y) * fs, np.diff(y, n=2) * fs**2
    mobility = float(np.sqrt(np.var(d1)/variance))
    complexity = float(np.sqrt(np.var(d2)/max(np.var(d1), 1e-15))/max(mobility, 1e-15))
    p = psd[selection] / np.sum(psd[selection])
    entropy = float(-np.sum(p*np.log2(p+1e-30))/np.log2(len(p)))
    features = [bands[b]['relative'] for b in BANDS] + [variance, mobility, complexity, entropy]
    return {'valid': True, 'reasons': [], 'units': 'adc_counts', 'measured_rate_hz': fs,
            'window_start_s': float(t[guard]), 'window_end_s': float(t[-guard-1]),
            'bands': bands, 'frequencies_hz': f[selection].tolist(),
            'psd': psd[selection].tolist(), 'power_units': 'adc_counts_squared',
            'feature_names': list(FEATURE_NAMES), 'features': features,
            'warnings': ['Quality checks cannot verify EEG origin or exclude muscle/eye artifacts.',
                         '30–40 Hz is partial gamma and sensitive to muscle contamination.']}

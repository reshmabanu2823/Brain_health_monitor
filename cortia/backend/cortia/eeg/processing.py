"""Versioned eight-second EEG windows. Quality rules are exploratory heuristics."""
import numpy as np
from scipy.signal import butter, sosfiltfilt, welch, iirnotch, filtfilt

PIPELINE_VERSION = 'cortia-eeg-1'
BANDS = {'delta': (.5, 4.), 'theta': (4., 8.), 'alpha': (8., 13.), 'beta': (13., 29.5)}


def integrate(f, p, lo, hi):
    inside = (f > lo) & (f < hi)
    frequencies = np.r_[lo, f[inside], hi]
    powers = np.r_[np.interp(lo, f, p), p[inside], np.interp(hi, f, p)]
    return float(np.trapezoid(powers, frequencies))


def analyze(samples, fs: float, gaps: int = 0, line_hz: float | None = None) -> dict:
    x = np.asarray(samples, dtype=float)
    if fs not in (250, 500) or x.ndim != 1 or len(x) < fs * 8 or not np.isfinite(x).all():
        raise ValueError('Expected finite eight-second one-channel window at 250 or 500 Hz')
    reasons = []
    if gaps:
        reasons.append('missing_samples')
    if np.std(x) < .5 or np.mean(np.diff(x) == 0) > .98:
        reasons.append('flatline')
    clipping = float(np.mean((x <= 1) | (x >= 16382)))
    if clipping > .01:
        reasons.append('clipping')
    differences = np.diff(x)
    mad = float(np.median(np.abs(differences - np.median(differences))))
    if np.max(np.abs(differences)) > max(2500, 20 * 1.4826 * mad):
        reasons.append('abrupt_step')
    result = dict(pipeline_version=PIPELINE_VERSION, sample_count=len(x), sampling_hz=fs,
                  units='ADC_count_squared', duration_seconds=len(x)/fs,
                  quality=dict(usable=not reasons, reasons=reasons, clipped_fraction=clipping,
                               missing_samples=gaps, method='unvalidated_single_channel_heuristics'),
                  bands={k: dict(low_hz=v[0], high_hz=v[1]) for k, v in BANDS.items()},
                  power=None, relative_power=None, ratios=None, psd=None, fft=None, peak_hz=None,
                  notch_applied=False, limitations=['Single-channel artifact heuristics cannot reliably separate eye, muscle and brain activity.',
                  'Beta is truncated at 29.5 Hz. Gamma unavailable. ADC amplitude is uncalibrated.',
                  'Ratios and baseline deviations do not diagnose disease or measure attention.'])
    if reasons:
        return result
    centered = x - np.mean(x)
    # Line suppression outside passband is supplied by bandpass; no redundant notch claim.
    if line_hz is not None and .5 < line_hz < 29.5:
        b, a = iirnotch(line_hz, 30, fs)
        centered = filtfilt(b, a, centered)
        result['notch_applied'] = True
    filtered = sosfiltfilt(butter(4, [.5, 29.5], btype='bandpass', fs=fs, output='sos'), centered)
    f, p = welch(filtered, fs=fs, window='hann', nperseg=int(fs*4), noverlap=int(fs*2), scaling='density')
    power = {k: integrate(f, p, *limits) for k, limits in BANDS.items()}
    total = sum(power.values())
    if total <= np.finfo(float).eps:
        result['quality'].update(usable=False, reasons=['insufficient_power'])
        return result
    def ratio(a, b):
        return power[a] / power[b] if power[b] > max(1e-12, total * 1e-6) else None
    retained = (f >= .5) & (f <= 29.5)
    ff = np.fft.rfftfreq(len(filtered), 1/fs)
    amplitude = 2 * np.abs(np.fft.rfft(filtered * np.hanning(len(filtered)))) / np.hanning(len(filtered)).sum()
    mask = (ff >= .5) & (ff <= 29.5)
    result.update(power=power, relative_power={k: v/total for k,v in power.items()},
                  ratios={'alpha_theta': ratio('alpha', 'theta'), 'theta_beta': ratio('theta', 'beta'),
                          'beta_alpha': ratio('beta', 'alpha')},
                  psd={'frequency_hz': f[retained].tolist(), 'density': p[retained].tolist(), 'units':'ADC_count_squared_per_Hz'},
                  fft={'frequency_hz': ff[mask].tolist(), 'amplitude': amplitude[mask].tolist(), 'units': 'ADC_count'},
                  peak_hz=float(f[retained][np.argmax(p[retained])]))
    return result


def feature_vector(result):
    if not result['quality']['usable']:
        return {}
    features = {f'relative_{k}': v for k,v in result['relative_power'].items()}
    features.update({f'power_{k}': v for k,v in result['power'].items()})
    features.update({k: v for k,v in result['ratios'].items() if v is not None})
    return features

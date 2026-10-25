import numpy as np
import pytest
from app.eeg.signal import (
    SignalConfig, analyze, segment,
    QUALITY_ACCEPTABLE, QUALITY_NEEDS_REVIEW, QUALITY_INSUFFICIENT
)


def wave(fs=250, seconds=6, frequency=10):
    t = np.arange(int(fs * seconds)) / fs
    return t, 512 + 30 * np.sin(2 * np.pi * frequency * t)


def test_alpha_power_and_filter_rejects_high_frequency():
    t, x = wave()
    x += 30 * np.sin(2 * np.pi * 80 * t)
    result = analyze(t, x, SignalConfig())
    assert result['valid'], result
    assert result['measured_rate_hz'] == pytest.approx(250)
    assert result['bands']['alpha']['relative'] > .95
    assert result['bands']['alpha']['absolute'] == pytest.approx(450, rel=.15)
    assert result['units'] == 'adc_counts'
    assert len(result['features']) == len(result['feature_names'])


def test_three_state_quality_and_rich_feature_metrics():
    # 1. Clean alpha signal -> Acceptable
    t, x = wave(frequency=10)
    result = analyze(t, x, SignalConfig())
    assert result['valid'] is True
    assert result['quality_state'] == QUALITY_ACCEPTABLE
    assert result['quality_reasons'] == []
    metrics = result['feature_metrics']
    assert metrics is not None
    assert metrics['peak_frequency_hz']['value'] == pytest.approx(10.0, abs=1.0)
    assert metrics['peak_frequency_hz']['unit'] == 'Hz'
    assert metrics['rms']['unit'] == 'adc_counts'
    assert metrics['variance']['unit'] == 'adc_counts_squared'
    assert 'partial 30.0–40.0 Hz' in metrics['gamma_partial_relative_power']['band_definition']
    assert '1.0–4.0 Hz' in metrics['delta_relative_power']['band_definition']
    # Synchronized waveform
    sync_wave = result['synchronized_waveform']
    assert sync_wave is not None
    assert len(sync_wave['raw_adc']) == 1000  # 4 seconds * 250 Hz active
    assert len(sync_wave['filtered_adc']) == 1000

    # 2. Moderate transient -> Needs review
    t, x = wave(frequency=10)
    x[700] += 100.0  # transient jump of 100 counts (above 90, below 150)
    rev_result = analyze(t, x, SignalConfig())
    assert rev_result['valid'] is True
    assert rev_result['quality_state'] == QUALITY_NEEDS_REVIEW
    assert 'moderate_transient_detected' in rev_result['quality_reasons']

    # 3. Fatal artifact -> Insufficient quality
    t, x = wave(frequency=10)
    x[:100] = 1023  # >1% saturation
    ins_result = analyze(t, x, SignalConfig())
    assert ins_result['valid'] is False
    assert ins_result['quality_state'] == QUALITY_INSUFFICIENT
    assert ins_result['features'] is None
    assert ins_result['feature_metrics'] is None
    assert 'saturation_clipping' in ins_result['quality_reasons']


@pytest.mark.parametrize('kind', ['nan', 'flat', 'clip', 'gap', 'short', 'jitter'])
def test_unusable_windows_rejected(kind):
    t, x = wave()
    if kind == 'nan': x[42] = np.nan
    if kind == 'flat': x[:] = 512
    if kind == 'clip': x[:100] = 1023
    if kind == 'gap': t[500:] += .04
    if kind == 'short': t, x = t[:200], x[:200]
    if kind == 'jitter': t[1::2] += .0015
    res = analyze(t, x, SignalConfig())
    assert not res['valid']
    assert res['quality_state'] == QUALITY_INSUFFICIENT


def test_invalid_filter_rate_and_config():
    with pytest.raises(ValueError): SignalConfig(sample_rate=70)
    with pytest.raises(ValueError): SignalConfig(notch_hz=125)
    with pytest.raises(ValueError): SignalConfig(low_hz=0)
    with pytest.raises(ValueError): SignalConfig(window_seconds=float('nan'))
    t, x = wave(fs=240)
    assert not analyze(t, x, SignalConfig())['valid']


def test_fixed_nonoverlapping_segmentation():
    assert list(segment(3500, 1500, 1500)) == [(0, 1500), (1500, 3000)]
    with pytest.raises(ValueError): list(segment(10, 0, 1))

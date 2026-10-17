import numpy as np
import pytest
from app.eeg.signal import SignalConfig, analyze, segment


def wave(fs=250, seconds=6, frequency=10):
    t=np.arange(int(fs*seconds))/fs
    return t, 512+30*np.sin(2*np.pi*frequency*t)


def test_alpha_power_and_filter_rejects_high_frequency():
    t,x=wave()
    x += 30*np.sin(2*np.pi*80*t)
    result=analyze(t,x,SignalConfig())
    assert result['valid'], result
    assert result['measured_rate_hz'] == pytest.approx(250)
    assert result['bands']['alpha']['relative'] > .95
    assert result['bands']['alpha']['absolute'] == pytest.approx(450,rel=.15)
    assert result['units']=='adc_counts'
    assert len(result['features']) == len(result['feature_names'])


@pytest.mark.parametrize('kind',['nan','flat','clip','gap','short','jitter'])
def test_unusable_windows_rejected(kind):
    t,x=wave()
    if kind=='nan': x[42]=np.nan
    if kind=='flat': x[:]=512
    if kind=='clip': x[:100]=1023
    if kind=='gap': t[500:]+=.04
    if kind=='short': t,x=t[:200],x[:200]
    if kind=='jitter': t[1::2]+=.0015
    assert not analyze(t,x,SignalConfig())['valid']


def test_invalid_filter_rate_and_config():
    with pytest.raises(ValueError): SignalConfig(sample_rate=70)
    with pytest.raises(ValueError): SignalConfig(notch_hz=125)
    with pytest.raises(ValueError): SignalConfig(low_hz=0)
    with pytest.raises(ValueError): SignalConfig(window_seconds=float('nan'))
    t,x=wave(fs=240)
    assert not analyze(t,x,SignalConfig())['valid']


def test_fixed_nonoverlapping_segmentation():
    assert list(segment(3500,1500,1500)) == [(0,1500),(1500,3000)]
    with pytest.raises(ValueError): list(segment(10,0,1))

"""Analytical fixtures only. Never used as application recordings."""
import numpy as np
import pytest
from cortia.eeg.protocol import ChordsParser
from cortia.eeg.processing import analyze


def packet(counter, value=8192):
    return b'\xc7\x7c' + bytes([counter]) + value.to_bytes(2, 'big') * 6 + b'\x01'


def test_fragmented_protocol_wrap_and_loss():
    parser = ChordsParser(channel=0)
    raw = packet(254) + packet(255) + packet(0) + packet(3)
    assert parser.feed(raw[:7]) == []
    items = parser.feed(raw[7:])
    assert [s['counter'] for s in items] == [254, 255, 0, 3]
    assert [s['missing'] for s in items] == [0, 0, 0, 2]
    assert all(s['value'] == 8192 for s in items)


def test_corruption_resync_and_duplicates():
    parser = ChordsParser()
    items = parser.feed(b'garbage' + packet(1)[:-1] + b'\x00' + packet(2) + packet(2) + packet(3))
    assert [s['counter'] for s in items] == [2, 3]
    assert parser.corrupted > 0
    assert parser.duplicates == 1


def test_alpha_power_and_conservation():
    t = np.arange(4000) / 500
    result = analyze(8192 + 100 * np.sin(2 * np.pi * 10 * t), 500)
    assert result['quality']['usable']
    assert result['relative_power']['alpha'] > .95
    assert sum(result['relative_power'].values()) == pytest.approx(1, abs=1e-8)
    assert result['peak_hz'] == pytest.approx(10, abs=.25)
    assert result['bands']['beta']['high_hz'] == 29.5
    assert result['units'] == 'ADC_count_squared'
    assert 'gamma' not in result['power']


@pytest.mark.parametrize('samples,gaps,reason', [
    (np.full(4000, 8192.), 0, 'flatline'),
    (np.tile([0., 16383.], 2000), 0, 'clipping'),
    (8192 + np.sin(np.arange(4000)), 2, 'missing_samples'),
])
def test_quality_rejects(samples, gaps, reason):
    result = analyze(samples, 500, gaps=gaps)
    assert not result['quality']['usable']
    assert reason in result['quality']['reasons']
    assert result['power'] is None


@pytest.mark.parametrize('samples,fs', [([1, float('nan')] * 2000, 500), ([1]*40, 500), ([1]*4000, 30)])
def test_invalid_windows(samples, fs):
    with pytest.raises(ValueError):
        analyze(samples, fs)


def test_invalid_adc_packets_rejected():
    parser = ChordsParser()
    assert parser.feed(packet(1, 65535)) == []

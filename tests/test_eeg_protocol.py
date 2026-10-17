import pytest
from app.eeg.protocol import SerialParser, SampleClock


def test_fragments_bad_lines_and_adc_limits():
    p=SerialParser()
    assert p.feed(b'0,123')==[]
    assert p.feed(b'4,512\n')[0]==(0,1234,512)
    assert p.feed(b'bad\n1,4,1024\n2,5,-1\n')==[]
    assert p.errors==3
    assert p.feed(b'3,8000,500\n')==[(3,8000,500)]
    p.feed(b'x'*300)
    assert len(p.buffer)<=p.max_line
    assert p.feed(b'0,1,3\n')==[] # discard remainder of overlong line
    assert p.feed(b'1,4,512\n')==[(1,4,512)]


def test_rollover_gap_and_reset():
    c=SampleClock()
    t,discontinuity=c.push(0,2**32-2000)
    t2,discontinuity=c.push(1,2000)
    assert t2-t==pytest.approx(.004)
    assert not discontinuity
    assert c.push(3,10000)[1]
    assert c.push(0,100)[1]


def test_duplicate_timestamp_rejected():
    c=SampleClock(); c.push(0,100)
    assert c.push(1,100)[1]


def test_firmware_and_host_rate_stay_within_ascii_bandwidth():
    from pathlib import Path
    from app.eeg.signal import SignalConfig
    with pytest.raises(ValueError): SignalConfig(sample_rate=500)
    sketch=(Path(__file__).resolve().parents[1]/'firmware/maker_uno_eeg/maker_uno_eeg.ino').read_text()
    assert 'SAMPLE_RATE > 250' in sketch
    assert 28 * 250 < 115200/10 # worst-case bytes/frame; UART start/stop bits

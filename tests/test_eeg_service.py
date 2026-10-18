import time
import numpy as np
import pytest
from app.eeg.service import EEGService
from app.eeg.storage import RecordingStore
from app.eeg.signal import SignalConfig


def test_recording_source_export_and_finalization(tmp_path):
    store=RecordingStore(tmp_path/'eeg.db')
    rid=store.start('simulated', {'sample_rate':250})
    store.append(rid,[(0,0.,512,'2026-10-15T00:00:00+00:00')])
    store.finish(rid,'completed')
    row=store.list()[0]
    assert row['source']=='simulated' and row['sample_count']==1
    assert 'simulated' in ''.join(store.export(rid))
    with pytest.raises(KeyError): store.get('missing')
    assert store.get(rid)['status']=='completed'


def test_demo_requires_explicit_start_no_predictions(tmp_path):
    s=EEGService(RecordingStore(tmp_path/'eeg.db'),SignalConfig())
    assert s.snapshot()['source'] is None
    assert s.snapshot()['analysis'] is None
    s.connect('simulated')
    try:
        rid=s.start_recording()
        time.sleep(.15)
        assert s.snapshot()['source']=='simulated'
        assert len(s.snapshot()['samples'])>0
        assert s.snapshot()['prediction']['available'] is False
        with pytest.raises(ValueError): s.connect('serial','COM0')
        s.stop_recording()
        assert s.store.get(rid)['sample_count']>0
    finally: s.disconnect()
    assert s.snapshot()['samples']==[]
    assert s.snapshot()['analysis'] is None


def test_disconnect_marks_recording_interrupted(tmp_path):
    s=EEGService(RecordingStore(tmp_path/'eeg.db'),SignalConfig())
    s.connect('simulated'); rid=s.start_recording(); time.sleep(.03); s.disconnect()
    assert s.store.get(rid)['status']=='interrupted'


def test_serial_failure_never_uses_simulated_source(tmp_path):
    def unavailable(*args,**kwargs): raise OSError('device gone')
    s=EEGService(RecordingStore(tmp_path/'eeg.db'),SignalConfig(),serial_factory=unavailable,retry_seconds=.01,max_retries=2)
    s.connect('serial','test-port')
    time.sleep(.1)
    state=s.snapshot()
    assert state['source']=='serial' and state['state']=='error'
    assert state['samples']==[] and state['analysis'] is None
    assert state['prediction']['available'] is False
    s.disconnect()


def test_reconnect_clears_windows_and_counts_bad_lines(tmp_path):
    class Device:
        def __init__(self): self.count=0
        def read(self,n):
            self.count+=1
            if self.count==1: return b'bad\n0,1000,512\n1,5000,520\n'
            raise OSError('removed')
        def close(self): pass
    s=EEGService(RecordingStore(tmp_path/'eeg.db'),SignalConfig(),serial_factory=lambda *a,**k:Device(),retry_seconds=.01,max_retries=1)
    s.connect('serial','test-port'); time.sleep(.15)
    snap=s.snapshot()
    assert snap['malformed_lines']>=1
    assert snap['analysis'] is None and snap['samples']==[]
    s.disconnect()


def test_rate_is_reported_before_analysis_and_recording_has_summary(tmp_path):
    s=EEGService(RecordingStore(tmp_path/'eeg.db'),SignalConfig())
    with s.lock:
        s.source='serial';s.state='connected'
    rid=s.start_recording()
    s._accept([(i,i/250,512+(i%10)) for i in range(20)])
    assert s.snapshot()['measured_rate_hz']==pytest.approx(250)
    s.stop_recording()
    assert s.store.get(rid)['measured_rate_hz']==pytest.approx(250)


def test_stale_input_and_discontinuity_clear_prediction_and_recording(tmp_path):
    s=EEGService(RecordingStore(tmp_path/'eeg.db'),SignalConfig())
    s.state='connected';s.source='serial'
    s._accept([(i,i/250,512+(i%10)) for i in range(20)])
    rid=s.start_recording()
    s.analysis={'valid':True};s.prediction={'available':True,'label':'test fixture'}
    s.last_received=time.monotonic()-3
    snap=s.snapshot()
    assert snap['stale'] and snap['analysis'] is None
    assert snap['samples']==[] and not snap['prediction']['available']
    s._accept([(22,.088,515)],discontinuity=True)
    assert s.store.get(rid)['status']=='interrupted'
    assert s.snapshot()['analysis'] is None and len(s.snapshot()['samples'])==1


def test_serial_unplug_during_active_recording_interrupts_and_recovers(tmp_path):
    class MockDevice:
        def __init__(self):
            self.unplugged = False
            self.seq = 0
        def read(self, n):
            if self.unplugged:
                raise OSError('Device unplugged during acquisition')
            time.sleep(0.01)
            self.seq += 1
            return f'{self.seq},{self.seq * 4000},512\n'.encode()
        def close(self):
            pass

    device = MockDevice()
    store = RecordingStore(tmp_path / 'eeg.db')
    s = EEGService(store, SignalConfig(), serial_factory=lambda *a, **k: device, retry_seconds=0.02, max_retries=3)
    s.connect('serial', 'COM3')

    for _ in range(50):
        if s.state == 'connected':
            break
        time.sleep(0.01)
    assert s.state == 'connected'

    rid = s.start_recording()
    assert s.recording == rid

    # Trigger unplug during active recording
    device.unplugged = True

    # Wait for the unplug OSError to mark recording as interrupted
    for _ in range(50):
        if store.get(rid)['status'] == 'interrupted':
            break
        time.sleep(0.01)

    assert store.get(rid)['status'] == 'interrupted'
    assert s.recording is None
    assert s.snapshot()['analysis'] is None

    # Plug device back in
    device.unplugged = False

    # Wait for reconnection with fresh buffer
    for _ in range(50):
        if s.state == 'connected':
            break
        time.sleep(0.01)

    assert s.state == 'connected'
    assert s.recording is None  # Does not auto-resume old recording
    assert len(s.snapshot()['samples']) > 0
    s.disconnect()

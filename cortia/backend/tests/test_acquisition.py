import numpy as np
import pytest
from cortia.config import Settings
from cortia.db import setup
from cortia.models import User, Recording, Segment
from cortia.eeg.acquisition import Acquisition
from cortia.eeg.protocol import ChordsParser


def test_disconnected_cannot_start(tmp_path):
    _, db = setup(Settings(data_dir=tmp_path))
    manager = Acquisition(db, tmp_path)
    with pytest.raises(ValueError, match='live'):
        manager.start_recording('user', {'eyes':'closed','task':'rest','montage':'Fp1-ear'})


def test_only_owner_reads_or_records(tmp_path):
    _, db = setup(Settings(data_dir=tmp_path))
    manager = Acquisition(db, tmp_path)
    manager.owner = 'first'
    manager.state = 'streaming'
    assert manager.snapshot('second')['state'] == 'busy'
    assert manager.snapshot('second')['samples'] == []
    with pytest.raises(ValueError):
        manager.start_recording('second', {})


def test_recording_persists_only_received_samples(tmp_path):
    _, db = setup(Settings(data_dir=tmp_path))
    with db() as session:
        user = User(username='fixture', password_hash='not-a-real-account')
        session.add(user)
        session.commit()
        owner = user.id
    manager = Acquisition(db, tmp_path)
    manager.owner = owner
    manager.state = 'streaming'
    manager.config = {'sampling_hz':500, 'channel':0, 'bandwidth':[.5,29.5], 'units':'ADC_count', 'pipeline':'cortia-eeg-1'}
    manager.last_sample_at = __import__('time').monotonic()
    row = manager.start_recording(owner, {'eyes':'closed','task':'rest','montage':'Fp1-ear'})
    t = np.arange(4000)/500
    samples = [{'counter':i%256,'value':int(8192+100*np.sin(2*np.pi*10*t[i])), 'missing':0,'discontinuity':False} for i in range(4000)]
    manager.accept(samples)
    manager.stop_recording(owner)
    with db() as session:
        record = session.get(Recording, row['id'])
        assert record.sample_count == 4000
        assert record.valid_windows == 1
        assert record.state == 'completed'
        assert record.features['relative_alpha'] > .9
        segment = session.query(Segment).one()
        assert segment.start_index == 0 and segment.end_index == 4000
        assert len((tmp_path/record.raw_path).read_text().splitlines()) == 4001


def test_disconnect_cancels_pending_handshake(tmp_path,monkeypatch):
    import threading
    from cortia.eeg import acquisition
    _, db=setup(Settings(data_dir=tmp_path))
    manager=Acquisition(db,tmp_path)
    with db() as session:
        session.add(User(id='first',username='first',password_hash='fixture-only'))
        session.commit()
    entered=threading.Event();release=threading.Event()
    class Port:
        closed=False
        def reset_input_buffer(self):pass
        def write(self,data):pass
        def readline(self):
            entered.set();release.wait(timeout=5);return b'UNO-R4\n'
        def close(self):self.closed=True
    port=Port()
    monkeypatch.setattr(manager,'ports',lambda:[{'port':'fixture','description':'test'}])
    monkeypatch.setattr(acquisition.serial,'Serial',lambda *a,**kw:port)
    monkeypatch.setattr(acquisition.time,'sleep',lambda _:None)
    failures=[]
    def connect():
        try:manager.connect('first','fixture')
        except ValueError as exc:failures.append(str(exc))
    worker=threading.Thread(target=connect)
    worker.start();assert entered.wait(timeout=2)
    manager.disconnect('first')
    release.set();worker.join(timeout=5)
    assert manager.state=='disconnected'
    assert manager.connection is None
    assert port.closed
    assert failures


def test_reader_closes_device_even_when_storage_finalization_fails(tmp_path,monkeypatch):
    _,db=setup(Settings(data_dir=tmp_path))
    manager=Acquisition(db,tmp_path)
    class BrokenPort:
        in_waiting=0
        closed=False
        def read(self,n):raise OSError('unplugged fixture')
        def write(self,b):pass
        def close(self):self.closed=True
    port=BrokenPort()
    manager.connection=port;manager.state='streaming';manager.config={'sampling_hz':500}
    def storage_error(*args):raise OSError('fixture disk failure')
    monkeypatch.setattr(manager,'_finish',storage_error)
    manager._reader()
    assert manager.state=='disconnected'
    assert manager.connection is None
    assert port.closed
    assert 'finaliz' in manager.error.lower()


def test_old_disconnect_does_not_erase_new_connection_reservation(tmp_path):
    _,db=setup(Settings(data_dir=tmp_path))
    manager=Acquisition(db,tmp_path)
    manager.owner='old';manager.state='streaming'
    class FinishedReader:
        def join(self,timeout):
            # Another request reserves a new connection after the old reader exits.
            with manager.lock:
                manager.generation+=1
                manager.owner='new';manager.state='connecting'
        def is_alive(self):return False
    manager.thread=FinishedReader()
    manager.disconnect('old')
    assert manager.owner=='new'
    assert manager.state=='connecting'

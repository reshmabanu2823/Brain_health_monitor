"""Single-process, exclusive serial ownership. No production signal generator."""
import csv
import threading
import time
from collections import deque
from pathlib import Path
import serial
from serial.tools import list_ports
from ..db import now, uid
from ..models import Device, Recording, Segment, Feature, Anomaly
from ..analytics.anomalies import quality_events
from .protocol import ChordsParser
from .processing import analyze, feature_vector, PIPELINE_VERSION

class Acquisition:
    def __init__(self, factory, data_dir):
        self.db = factory
        self.data_dir = Path(data_dir)
        self.lock = threading.RLock()
        self.owner = None
        self.state = 'disconnected'
        self.error = None
        self.config = {}
        self.device_id = None
        self.connection = None
        self.thread = None
        self.stop_event = threading.Event()
        self.samples = deque(maxlen=2500)
        self.sequence = 0
        self.last_sample_at = 0
        self.latest = None
        self.live_window = []
        self.live_gaps = 0
        self.recording_id = None
        self.raw_file = None
        self.window = []
        self.window_gaps = 0
        self.window_start = 0
        self.feature_sums = {}
        self.feature_counts = {}
        self.count = 0
        self.missing = 0
        self.valid = self.invalid = 0
        self.parser = None
        self.sample_clock = 0
        self.generation = 0

    @staticmethod
    def ports():
        return [{'port':p.device, 'description':p.description} for p in list_ports.comports()]

    def connect(self, owner, port, sampling_hz=500, channel=0):
        with self.lock:
            if self.state in ('connecting', 'streaming') or self.connection is not None:
                raise ValueError('Device already owned; disconnect first')
            if port not in {p['port'] for p in self.ports()}:
                raise ValueError('Select an available serial port')
            self.generation += 1
            ticket = self.generation
            self.state, self.owner, self.error = 'connecting', owner, None
        connection = None
        try:
            connection = serial.Serial(port, 230400, timeout=.15, write_timeout=1, exclusive=True)
            time.sleep(1.5)
            connection.reset_input_buffer()
            connection.write(b'WHORU\n')
            deadline = time.monotonic()+3
            identity = b''
            while time.monotonic() < deadline and b'UNO-R4' not in identity:
                identity += connection.readline()
                if len(identity) > 4096:
                    break
            if b'UNO-R4' not in identity:
                raise ValueError('UNO-R4 Chords handshake failed. Check firmware and close Serial Monitor.')
            connection.reset_input_buffer()
            with self.lock:
                if ticket != self.generation or self.state != 'connecting' or self.owner != owner:
                    raise ValueError('Connection attempt cancelled')
                self.config = dict(port=port, baud=230400, board='UNO-R4', sampling_hz=sampling_hz,
                                   channel=channel, bandwidth=[.5,29.5], units='ADC_count', pipeline=PIPELINE_VERSION,
                                   rate_source='operator_firmware_setting', calibrated=False)
                with self.db() as db:
                    device = Device(user_id=owner, config=self.config)
                    db.add(device)
                    db.commit()
                    self.device_id = device.id
                self.connection = connection
                self.parser = ChordsParser(channel)
                self.samples.clear()
                self.latest = None
                self.live_window = []
                self.live_gaps = 0
                self.sequence = self.sample_clock = 0
                self.stop_event.clear()
                self.last_sample_at = 0
                self.state = 'streaming'
                connection.write(b'START\n')
                self.thread = threading.Thread(target=self._reader, daemon=True, name='cortia-usb')
                self.thread.start()
            return self.snapshot(owner)
        except Exception:
            if connection:
                connection.close()
            with self.lock:
                if ticket == self.generation:
                    self.connection = None
                    self.state = 'disconnected'
                    self.owner = None
            raise

    def _reader(self):
        rate_start = time.monotonic()
        rate_samples = 0
        try:
            while not self.stop_event.is_set():
                batch_bytes = 16 * max(1, int(self.config['sampling_hz'] * .05))
                raw = self.connection.read(min(8192, max(batch_bytes, self.connection.in_waiting)))
                if raw:
                    parsed = self.parser.feed(raw)
                    self.accept(parsed)
                    rate_samples += len(parsed) + sum(s['missing'] for s in parsed)
                elapsed = time.monotonic()-rate_start
                if elapsed >= 5:
                    observed = rate_samples/elapsed
                    if not .85*self.config['sampling_hz'] <= observed <= 1.15*self.config['sampling_hz']:
                        raise ValueError('Observed sample rate differs from selected firmware rate; recording interrupted. Verify 250/500 Hz setting.')
                    rate_samples = 0
                    rate_start = time.monotonic()
                if time.monotonic()-max(self.last_sample_at, rate_start) > 2.5:
                    raise ValueError('No valid EEG samples for 2.5 seconds. Live data unavailable.')
        except Exception as exc:
            with self.lock:
                self.error = str(exc) if isinstance(exc, ValueError) else 'Serial acquisition failed. Check device connection and storage.'
        finally:
            with self.lock:
                try:
                    self._finish('interrupted', self.error or 'Device disconnected')
                except Exception:
                    self.error = 'Recording finalization failed. Raw data or metadata may be incomplete; inspect storage before continuing.'
                if self.connection:
                    try:
                        self.connection.write(b'STOP\n')
                    except Exception:
                        pass
                    try:
                        self.connection.close()
                    except Exception:
                        pass
                self.connection = None
                self.state = 'disconnected'
                self.latest = None
                self.samples.clear()

    def accept(self, samples):
        """Receive decoded hardware packets. Called only by serial reader in production."""
        if not samples:
            return
        with self.lock:
            received = time.time()
            self.last_sample_at = time.monotonic()
            fs = self.config['sampling_hz']
            for sample in samples:
                self.sequence += 1
                self.sample_clock += 1 + sample['missing']
                discontinuity = sample.get('discontinuity', False)
                point = dict(sequence=self.sequence, sample_time=self.sample_clock/fs,
                             received_at=received, counter=sample['counter'], value=sample['value'],
                             missing=sample['missing'], discontinuity=discontinuity)
                self.samples.append(point)
                self.live_window.append(sample['value'])
                self.live_gaps += sample['missing'] + int(discontinuity)
                if len(self.live_window) == fs*8:
                    self.latest = analyze(self.live_window, fs, gaps=self.live_gaps)
                    self.live_window, self.live_gaps = [], 0
                if self.recording_id:
                    self.writer.writerow([self.count, sample['counter'], self.sample_clock/fs, received,
                                          sample['value'], sample['missing'], int(discontinuity)])
                    self.count += 1
                    self.missing += sample['missing']
                    self.window.append(sample['value'])
                    self.window_gaps += sample['missing'] + int(discontinuity)
                    if len(self.window) == fs*8:
                        result = analyze(self.window, fs, gaps=self.window_gaps)
                        values = feature_vector(result)
                        with self.db() as db:
                            segment = Segment(session_id=self.recording_id, start_index=self.window_start,
                                              end_index=self.count, result=result)
                            db.add(segment)
                            db.flush()
                            db.add(Feature(segment_id=segment.id, values=values))
                            if result['quality']['usable']:
                                self.valid += 1
                                for name, value in values.items():
                                    self.feature_sums[name] = self.feature_sums.get(name,0)+value
                                    self.feature_counts[name] = self.feature_counts.get(name,0)+1
                            else:
                                self.invalid += 1
                                for event in quality_events(result['quality']):
                                    db.add(Anomaly(session_id=self.recording_id, segment_id=segment.id, **event))
                            db.commit()
                        self.window, self.window_gaps, self.window_start = [], 0, self.count
            if self.recording_id:
                self.raw_file.flush()
                self._sync_record()

    def _sync_record(self):
        with self.db() as db:
            row = db.get(Recording, self.recording_id)
            row.sample_count, row.missing_samples = self.count, self.missing
            row.valid_windows, row.invalid_windows = self.valid, self.invalid
            row.features = {k:v/self.feature_counts[k] for k,v in self.feature_sums.items()}
            db.commit()

    def start_recording(self, owner, context):
        with self.lock:
            if self.state != 'streaming' or owner != self.owner or time.monotonic()-self.last_sample_at > 2.5:
                raise ValueError('Connect hardware and wait for live EEG samples before recording')
            if self.recording_id:
                raise ValueError('Recording already active')
            sid = uid()
            path = Path('raw')/f'{sid}.csv'
            file = (self.data_dir/path).open('x', newline='')
            (self.data_dir/path).chmod(0o600)
            try:
                with self.db() as db:
                    row = Recording(id=sid, user_id=owner, device_id=self.device_id, context=context,
                                    config=self.config, raw_path=str(path))
                    db.add(row)
                    db.commit()
            except Exception:
                file.close()
                (self.data_dir/path).unlink(missing_ok=True)
                raise
            self.recording_id, self.raw_file = sid, file
            self.writer = csv.writer(file)
            self.writer.writerow(['sample_index','device_counter','device_time_seconds','received_unix_seconds','adc_count','missing_before','discontinuity'])
            file.flush()
            self.window, self.window_gaps, self.window_start = [], 0, 0
            self.feature_sums, self.feature_counts = {}, {}
            self.count = self.missing = self.valid = self.invalid = 0
            return dict(id=sid, state='recording')

    def _finish(self, state, reason):
        if not self.recording_id:
            return
        sid = self.recording_id
        try:
            self.raw_file.flush()
            self._sync_record()
            with self.db() as db:
                row = db.get(Recording, sid)
                row.state, row.end_reason, row.ended_at = state, reason, now()
                db.commit()
        finally:
            self.raw_file.close()
            self.recording_id, self.raw_file = None, None
            self.window = []

    def stop_recording(self, owner):
        with self.lock:
            if owner != self.owner or not self.recording_id:
                raise ValueError('No active recording for this user')
            sid = self.recording_id
            self._finish('completed', 'Stopped by user; trailing partial window retained as raw samples only.')
            return {'id':sid, 'state':'completed'}

    def disconnect(self, owner=None):
        with self.lock:
            if owner is not None and owner != self.owner:
                raise ValueError('Device belongs to another signed-in user')
            self.generation += 1
            ticket = self.generation
            self.stop_event.set()
            thread = self.thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5)
        with self.lock:
            if ticket == self.generation and (not thread or not thread.is_alive()):
                self._finish('interrupted', 'Disconnected')
                self.state, self.owner = 'disconnected', None

    def snapshot(self, owner, after=0):
        with self.lock:
            if self.owner is not None and self.owner != owner and self.state != 'disconnected':
                return dict(state='busy', samples=[], recording_id=None, latest=None)
            live = self.state == 'streaming' and time.monotonic()-self.last_sample_at <= 2.5
            return dict(state=self.state, live_available=live, error=self.error,
                        stream_id=self.generation if owner == self.owner else None,
                        config=self.config if owner == self.owner else None,
                        samples=[s for s in self.samples if s['sequence'] > after] if live and owner == self.owner else [],
                        recording_id=self.recording_id if owner == self.owner else None,
                        recording_samples=self.count if self.recording_id and owner == self.owner else 0,
                        latest=self.latest if live and owner == self.owner else None,
                        corrupted_bytes=self.parser.corrupted if self.parser and owner == self.owner else 0,
                        duplicates=self.parser.duplicates if self.parser and owner == self.owner else 0)

"""One process owns one serial device; acquisition never runs on request threads."""
from collections import deque
from dataclasses import asdict
import logging
import math
import threading
import time
from .protocol import SerialParser, SampleClock
from .signal import analyze
from .storage import utc_now

log = logging.getLogger(__name__)


class EEGService:
    def __init__(self, store, config, model=None, serial_factory=None, retry_seconds=2., max_retries=5, max_record_seconds=3600):
        self.store, self.config, self.model = store, config, model
        self.serial_factory = serial_factory
        self.retry_seconds, self.max_retries = retry_seconds, max_retries
        self.max_record_seconds = max_record_seconds
        self.lock = threading.RLock()
        self.control = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.device = None
        self.buffer = deque(maxlen=config.input_samples)
        self.source = None
        self.state = 'disconnected'
        self.error = None
        self.analysis = None
        self.recording = None
        self.last_received = None
        self.prediction = self.unavailable('No EEG model installed')
        self.malformed = self.discontinuities = self.received = self.evicted = 0

    @staticmethod
    def unavailable(reason):
        return {'available': False, 'reason': reason}

    def connect(self, source, port=None):
        with self.control:
            if self.thread and self.thread.is_alive():
                raise ValueError('Disconnect current source before reconnecting')
            if source not in ('serial', 'simulated') or (source == 'serial' and not port):
                raise ValueError('Explicit source and serial port required')
            with self.lock:
                self.stop.clear()
                self.buffer.clear()
                self.analysis = None
                self.prediction = self.unavailable('Waiting for valid real EEG window')
                self.source, self.state, self.error = source, 'connecting', None
                self.malformed = self.discontinuities = self.received = self.evicted = 0
                self.last_received = None
            self.thread = threading.Thread(target=self._run, args=(port,), name='bhm-eeg', daemon=True)
            self.thread.start()

    def disconnect(self):
        with self.control:
            self.stop.set()
            if self.thread:
                self.thread.join(timeout=5)
                if self.thread.is_alive():
                    raise RuntimeError('Acquisition worker did not stop; port remains owned')
            with self.lock:
                self._finish_recording('interrupted')
                self.state = 'disconnected'
                self.buffer.clear()
                self.analysis = None
                self.prediction = self.unavailable('Device disconnected')

    def start_recording(self):
        with self.lock:
            if self.state != 'connected' or self.recording:
                raise ValueError('Connect a source and stop any active recording first')
            rid = self.store.start(self.source, asdict(self.config))
            self.recording = rid
            self.recording_started = time.monotonic()
            return rid

    def _finish_recording(self, status):
        if self.recording:
            self.store.finish(self.recording, status)
            self.recording = None

    def stop_recording(self):
        with self.lock:
            if not self.recording:
                raise ValueError('No active recording')
            rid = self.recording
            self._finish_recording('completed')
            return rid

    def snapshot(self):
        with self.lock:
            stale = self.state == 'connected' and self.last_received is not None and time.monotonic()-self.last_received > 2
            measured = None
            if len(self.buffer) > 1:
                duration = self.buffer[-1]['seconds']-self.buffer[0]['seconds']
                measured = (len(self.buffer)-1)/duration if duration > 0 else None
            return {'measured_rate_hz': measured if not stale else None, 'state': self.state, 'source': self.source, 'simulated': self.source == 'simulated',
                    'channels': 1, 'units': 'adc_counts', 'configured_rate_hz': self.config.sample_rate,
                    'buffer_capacity_samples': self.buffer.maxlen, 'received_samples': self.received,
                    'buffer_evictions': self.evicted, 'malformed_lines': self.malformed,
                    'discontinuities': self.discontinuities, 'error': self.error, 'stale': stale,
                    'recording_id': self.recording, 'samples': list(self.buffer) if not stale else [],
                    'analysis': self.analysis if not stale else None,
                    'prediction': self.prediction if not stale else self.unavailable('Input stale'),
                    'server_utc': utc_now()}

    def _accept(self, samples, discontinuity=False):
        with self.lock:
            if discontinuity:
                self.discontinuities += 1
                self.buffer.clear()
                self.analysis = None
                self.prediction = self.unavailable('Input discontinuity; collecting new window')
                self._finish_recording('interrupted')
            now = utc_now()
            rows = []
            for seq, seconds, adc in samples:
                self.evicted += int(len(self.buffer) == self.buffer.maxlen)
                self.buffer.append({'sequence': seq, 'seconds': seconds, 'value': adc})
                rows.append((seq, seconds, adc, now))
            self.received += len(samples)
            if samples:
                self.last_received = time.monotonic()
            if self.recording:
                self.store.append(self.recording, rows)
                if time.monotonic()-self.recording_started >= self.max_record_seconds:
                    self._finish_recording('duration_limit')
            data = list(self.buffer)
        if len(data) == self.config.input_samples and time.monotonic()-getattr(self, '_last_analysis', 0) >= 1:
            self._last_analysis = time.monotonic()
            result = analyze([s['seconds'] for s in data], [s['value'] for s in data], self.config)
            result['source'] = self.source
            result['analyzed_utc'] = utc_now()
            prediction = self.unavailable('Simulated input; classification disabled') if self.source == 'simulated' else self.unavailable('Signal invalid')
            if self.source == 'serial' and result['valid']:
                prediction = self.model.predict(result, self.config) if self.model else self.unavailable('No EEG model installed; labeled dataset required')
            with self.lock:
                self.analysis, self.prediction = result, prediction

    def _run(self, port):
        try:
            if self.source == 'simulated':
                self._demo()
            else:
                self._serial(port)
        except Exception:
            log.exception('EEG acquisition worker failed')
            with self.lock:
                self.error = 'Acquisition or recording failed; inspect local server log'
                self.state = 'error'
        finally:
            with self.lock:
                if self.state != 'connected' or self.stop.is_set():
                    try:
                        self._finish_recording('interrupted')
                    except Exception:
                        log.exception('Could not finalize EEG recording')
                    self.buffer.clear()
                    self.analysis = None
                    self.prediction = self.unavailable('Acquisition stopped')

    def _demo(self):
        with self.lock:
            self.state = 'connected'
        start = time.monotonic()
        seq = 0
        while not self.stop.wait(.02):
            target = int((time.monotonic()-start)*self.config.sample_rate)
            rows = []
            while seq < target:
                t = seq/self.config.sample_rate
                adc = round(512 + 30*math.sin(2*math.pi*10*t) + 8*math.sin(2*math.pi*6*t))
                rows.append((seq, t, adc))
                seq += 1
            self._accept(rows)

    def _serial(self, port):
        import serial
        factory = self.serial_factory or serial.Serial
        failures = 0
        while not self.stop.is_set() and failures < self.max_retries:
            try:
                self.device = factory(port, baudrate=115200, timeout=.2, write_timeout=.2)
                parser, clock = SerialParser(), SampleClock()
                with self.lock:
                    self.state = 'connecting'
                last_valid = time.monotonic()
                while not self.stop.is_set():
                    chunk = self.device.read(512)
                    before = parser.errors
                    records = parser.feed(chunk)
                    with self.lock:
                        self.malformed += parser.errors-before
                    batch = []
                    for seq, micros, adc in records:
                        seconds, broken = clock.push(seq, micros)
                        if broken:
                            if batch:
                                self._accept(batch)
                                batch = []
                            self._accept([], discontinuity=True)
                        batch.append((seq, seconds, adc))
                    if batch:
                        with self.lock:
                            self.state, self.error = 'connected', None
                        self._accept(batch)
                        last_valid = time.monotonic()
                    if time.monotonic()-last_valid > 3:
                        raise OSError('No valid samples for three seconds')
            except (OSError, serial.SerialException):
                failures += 1
                with self.lock:
                    self.state = 'reconnecting'
                    self.error = f'Serial input unavailable; attempt {failures}/{self.max_retries}'
                    self.buffer.clear()
                    self.analysis = None
                    self.prediction = self.unavailable('Serial input disconnected')
                    self._finish_recording('interrupted')
                if self.stop.wait(self.retry_seconds):
                    break
            finally:
                if self.device is not None:
                    self.device.close()
                    self.device = None
        if not self.stop.is_set():
            with self.lock:
                self.state = 'error'
                self.error = 'Serial retry limit reached; reconnect explicitly'

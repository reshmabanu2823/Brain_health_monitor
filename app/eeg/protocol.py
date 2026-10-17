"""BHM raw serial protocol v1: uint32 sequence,micros,10-bit ADC + LF.

Not compatible with Chords binary packets. Comments begin with '#'. Framing
persists across reads; overlong lines are discarded through the next newline.
"""
import re


class SerialParser:
    max_line = 80

    def __init__(self):
        self.buffer = bytearray()
        self.errors = 0
        self.discard = False

    def feed(self, data):
        samples = []
        for byte in data:
            if byte == 10:
                if not self.discard:
                    line = bytes(self.buffer).rstrip(b'\r')
                    if line and not line.startswith(b'#'):
                        if re.fullmatch(rb'\d{1,10},\d{1,10},\d{1,4}', line):
                            seq, micros, adc = map(int, line.split(b','))
                            if seq < 2**32 and micros < 2**32 and 0 <= adc <= 1023:
                                samples.append((seq, micros, adc))
                            else:
                                self.errors += 1
                        else:
                            self.errors += 1
                self.buffer.clear()
                self.discard = False
            elif not self.discard:
                self.buffer.append(byte)
                if len(self.buffer) > self.max_line:
                    self.errors += 1
                    self.buffer.clear()
                    self.discard = True
        return samples


class SampleClock:
    """Unwrap uint32 micros; flag sequence loss, reboot or non-forward time."""

    def __init__(self):
        self.previous = None
        self.elapsed_us = 0

    def push(self, seq, micros):
        broken = False
        if self.previous is not None:
            old_seq, old_us = self.previous
            delta = (micros - old_us) % 2**32
            broken = seq != (old_seq + 1) % 2**32 or not 0 < delta < 1_000_000
            self.elapsed_us += delta if 0 < delta < 1_000_000 else 1
        self.previous = (seq, micros)
        return self.elapsed_us / 1e6, broken

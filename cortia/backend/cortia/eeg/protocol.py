"""Independent decoder for documented Chords UNO-R4 six-channel packets."""
class ChordsParser:
    def __init__(self, channel=0):
        if not 0 <= channel < 6:
            raise ValueError('Channel must be 0–5')
        self.channel = channel
        self.buffer = bytearray()
        self.last = None
        self.corrupted = 0
        self.duplicates = 0
        self.pending_corruption = False

    def feed(self, data: bytes) -> list[dict]:
        self.buffer.extend(data)
        out = []
        while len(self.buffer) >= 16:
            index = self.buffer.find(b'\xc7\x7c')
            if index < 0:
                self.corrupted += len(self.buffer) - 1
                self.buffer[:] = self.buffer[-1:]
                self.pending_corruption = True
                break
            if index:
                self.corrupted += index
                del self.buffer[:index]
                self.pending_corruption = True
            if len(self.buffer) < 16:
                break
            values = [int.from_bytes(self.buffer[i:i+2], 'big') for i in range(3, 15, 2)]
            if self.buffer[15] != 1 or any(v > 16383 for v in values):
                self.corrupted += 1
                del self.buffer[0]
                self.pending_corruption = True
                continue
            counter = self.buffer[2]
            del self.buffer[:16]
            if self.last is not None and counter == self.last:
                self.duplicates += 1
                self.pending_corruption = True
                continue
            missing = 0 if self.last is None else (counter - self.last - 1) % 256
            self.last = counter
            out.append(dict(counter=counter, value=values[self.channel], missing=missing,
                            discontinuity=self.pending_corruption))
            self.pending_corruption = False
        return out

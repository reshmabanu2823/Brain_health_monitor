"""Local SQLite recordings, no personal identifiers. Explicit source per session."""
import csv
import io
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class RecordingStore:
    def __init__(self, path):
        self.path = Path(path)
        with self.connection() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS eeg_sessions (id TEXT PRIMARY KEY, started_utc TEXT, ended_utc TEXT, source TEXT, status TEXT, config TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS eeg_samples (session_id TEXT, sequence INTEGER, device_seconds REAL, adc INTEGER, received_utc TEXT)')
            c.execute('CREATE INDEX IF NOT EXISTS eeg_session_samples ON eeg_samples(session_id)')
            # Sessions left open by process death cannot be resumed silently.
            c.execute("UPDATE eeg_sessions SET status='interrupted',ended_utc=? WHERE status='recording'", (utc_now(),))

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(self.path, timeout=5)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def start(self, source, config):
        if source not in ('serial', 'simulated'):
            raise ValueError('Unknown recording source')
        rid = uuid.uuid4().hex
        with self.connection() as c:
            c.execute('INSERT INTO eeg_sessions VALUES (?,?,?,?,?,?)', (rid, utc_now(), None, source, 'recording', json.dumps(config, allow_nan=False)))
        return rid

    def append(self, rid, samples):
        with self.connection() as c:
            c.executemany('INSERT INTO eeg_samples VALUES (?,?,?,?,?)', [(rid, *s) for s in samples])

    def finish(self, rid, status):
        with self.connection() as c:
            c.execute("UPDATE eeg_sessions SET ended_utc=?,status=? WHERE id=? AND status='recording'", (utc_now(), status, rid))

    def get(self, rid):
        with self.connection() as c:
            row = c.execute('SELECT s.*, COUNT(v.rowid) AS sample_count, MIN(device_seconds) AS first_s, MAX(device_seconds) AS last_s FROM eeg_sessions s LEFT JOIN eeg_samples v ON v.session_id=s.id WHERE s.id=? GROUP BY s.id', (rid,)).fetchone()
        if row is None:
            raise KeyError('Recording not found')
        r = dict(row)
        r['config'] = json.loads(r['config'])
        r['duration_seconds'] = max(0., (r.pop('last_s') or 0) - (r.pop('first_s') or 0))
        r['measured_rate_hz'] = (r['sample_count']-1)/r['duration_seconds'] if r['duration_seconds'] > 0 and r['sample_count'] > 1 else None
        return r

    def list(self, limit=100):
        with self.connection() as c:
            ids = [r[0] for r in c.execute('SELECT id FROM eeg_sessions ORDER BY started_utc DESC,rowid DESC LIMIT ?', (limit,))]
        return [self.get(rid) for rid in ids]

    def export(self, rid):
        session = self.get(rid)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['source', 'sequence', 'device_seconds', 'adc_counts', 'received_utc'])
        yield output.getvalue()
        with self.connection() as c:
            cursor = c.execute('SELECT sequence,device_seconds,adc,received_utc FROM eeg_samples WHERE session_id=? ORDER BY rowid', (rid,))
            while rows := cursor.fetchmany(500):
                output.seek(0); output.truncate(0)
                for row in rows:
                    writer.writerow([session['source'], *row])
                yield output.getvalue()

"""Local SQLite recordings, no personal identifiers. Explicit source per session."""
import csv
import io
import json
import math
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import numpy as np


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class RecordingStore:
    def __init__(self, path):
        self.path = Path(path)
        with self.connection() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS eeg_sessions (id TEXT PRIMARY KEY, started_utc TEXT, ended_utc TEXT, source TEXT, status TEXT, config TEXT, notes TEXT, summary TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS eeg_samples (session_id TEXT, sequence INTEGER, device_seconds REAL, adc INTEGER, received_utc TEXT)')
            c.execute('CREATE INDEX IF NOT EXISTS eeg_session_samples ON eeg_samples(session_id)')
            # Backward compatibility column migrations if table already existed without notes/summary
            cols = [r[1] for r in c.execute('PRAGMA table_info(eeg_sessions)').fetchall()]
            if 'notes' not in cols:
                c.execute('ALTER TABLE eeg_sessions ADD COLUMN notes TEXT')
            if 'summary' not in cols:
                c.execute('ALTER TABLE eeg_sessions ADD COLUMN summary TEXT')
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

    def start(self, source, config, notes=None):
        if source not in ('serial', 'simulated'):
            raise ValueError('Unknown recording source')
        rid = uuid.uuid4().hex
        with self.connection() as c:
            c.execute(
                'INSERT INTO eeg_sessions (id, started_utc, ended_utc, source, status, config, notes, summary) VALUES (?,?,?,?,?,?,?,?)',
                (rid, utc_now(), None, source, 'recording', json.dumps(config, allow_nan=False), notes, None)
            )
        return rid

    def append(self, rid, samples):
        with self.connection() as c:
            c.executemany('INSERT INTO eeg_samples VALUES (?,?,?,?,?)', [(rid, *s) for s in samples])

    def finish(self, rid, status):
        with self.connection() as c:
            c.execute("UPDATE eeg_sessions SET ended_utc=?,status=? WHERE id=? AND status='recording'", (utc_now(), status, rid))

    def update_notes(self, rid, notes):
        with self.connection() as c:
            c.execute('UPDATE eeg_sessions SET notes=? WHERE id=?', (notes, rid))
            row = c.execute('SELECT summary FROM eeg_sessions WHERE id=?', (rid,)).fetchone()
            if row and row['summary']:
                try:
                    s = json.loads(row['summary'])
                    s['notes'] = notes
                    c.execute('UPDATE eeg_sessions SET summary=? WHERE id=?', (json.dumps(s, allow_nan=False), rid))
                except Exception:
                    pass

    def update_summary(self, rid, summary):
        with self.connection() as c:
            c.execute('UPDATE eeg_sessions SET summary=? WHERE id=?', (json.dumps(summary, allow_nan=False), rid))

    def get(self, rid):
        with self.connection() as c:
            row = c.execute(
                'SELECT s.*, COUNT(v.rowid) AS sample_count, MIN(device_seconds) AS first_s, MAX(device_seconds) AS last_s FROM eeg_sessions s LEFT JOIN eeg_samples v ON v.session_id=s.id WHERE s.id=? GROUP BY s.id',
                (rid,)
            ).fetchone()
        if row is None:
            raise KeyError('Recording not found')
        r = dict(row)
        r['config'] = json.loads(r['config'])
        r['duration_seconds'] = max(0., (r.pop('last_s') or 0) - (r.pop('first_s') or 0))
        r['measured_rate_hz'] = (r['sample_count'] - 1) / r['duration_seconds'] if r['duration_seconds'] > 0 and r['sample_count'] > 1 else None
        return r

    def get_summary(self, rid):
        session = self.get(rid)
        if session.get('summary'):
            try:
                s = json.loads(session['summary'])
                s['notes'] = session.get('notes') or ''
                return s
            except Exception:
                pass

        with self.connection() as c:
            rows = c.execute('SELECT device_seconds, adc FROM eeg_samples WHERE session_id=? ORDER BY rowid', (rid,)).fetchall()

        from .signal import SignalConfig, analyze, segment, get_preprocessing_record
        raw_cfg = session.get('config') or {}
        clean_cfg = {k: v for k, v in raw_cfg.items() if k in SignalConfig.__dataclass_fields__}
        cfg = SignalConfig(**clean_cfg) if clean_cfg else SignalConfig()
        prep_rec = raw_cfg.get('preprocessing') or get_preprocessing_record(cfg)

        total_windows = 0
        acceptable_count = 0
        needs_review_count = 0
        insufficient_count = 0
        all_reasons = []
        feature_accumulator = {}

        if rows and len(rows) >= cfg.input_samples:
            t_arr = [r[0] for r in rows]
            v_arr = [r[1] for r in rows]
            step = round(cfg.window_seconds * cfg.sample_rate)
            for start_idx, end_idx in segment(len(rows), cfg.input_samples, step):
                total_windows += 1
                w_res = analyze(t_arr[start_idx:end_idx], v_arr[start_idx:end_idx], cfg)
                q_state = w_res.get('quality_state', 'Insufficient quality')
                if q_state == 'Acceptable':
                    acceptable_count += 1
                elif q_state == 'Needs review':
                    needs_review_count += 1
                else:
                    insufficient_count += 1

                if w_res.get('quality_reasons'):
                    all_reasons.extend(w_res['quality_reasons'])

                if w_res.get('valid') and w_res.get('feature_metrics'):
                    for f_name, f_data in w_res['feature_metrics'].items():
                        if f_name not in feature_accumulator:
                            feature_accumulator[f_name] = {'values': [], 'unit': f_data['unit'], 'band_definition': f_data['band_definition']}
                        if f_data['value'] is not None and math.isfinite(f_data['value']):
                            feature_accumulator[f_name]['values'].append(f_data['value'])

        feature_summary = {}
        for f_name, data in feature_accumulator.items():
            vals = data['values']
            if vals:
                feature_summary[f_name] = {
                    'mean': float(np.mean(vals)),
                    'std': float(np.std(vals)),
                    'min': float(np.min(vals)),
                    'max': float(np.max(vals)),
                    'window_count': len(vals),
                    'unit': data['unit'],
                    'band_definition': data['band_definition']
                }

        overall_state = 'Acceptable' if (acceptable_count > 0 and acceptable_count >= needs_review_count + insufficient_count) else ('Needs review' if needs_review_count > 0 else ('Insufficient quality' if total_windows > 0 else 'No windows'))

        summary_obj = {
            'session_id': rid,
            'source': session['source'],
            'started_utc': session['started_utc'],
            'ended_utc': session['ended_utc'],
            'duration_seconds': session['duration_seconds'],
            'sample_count': session['sample_count'],
            'measured_rate_hz': session['measured_rate_hz'],
            'status': session['status'],
            'quality_summary': {
                'total_windows': total_windows,
                'acceptable_windows': acceptable_count,
                'needs_review_windows': needs_review_count,
                'insufficient_windows': insufficient_count,
                'quality_state': overall_state,
                'observed_issues': sorted(list(set(all_reasons)))
            },
            'preprocessing_config': prep_rec,
            'feature_summary': feature_summary,
            'model_output': {'available': False, 'reason': 'No trained EEG model installed; labeled dataset required'},
            'notes': session.get('notes') or '',
            'summarized_utc': utc_now()
        }
        return summary_obj

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
                output.seek(0)
                output.truncate(0)
                for row in rows:
                    writer.writerow([session['source'], *row])
                yield output.getvalue()

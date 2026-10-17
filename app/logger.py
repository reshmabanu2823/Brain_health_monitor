"""SQLite-backed audit persistence with measured model statistics."""
import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    from .artifacts import CLASS_NAMES, DISPLAY_LABELS, PROBABILITY_LABELS, sha256_file
except ImportError:
    from artifacts import CLASS_NAMES, DISPLAY_LABELS, PROBABILITY_LABELS, sha256_file

BASE_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = Path(os.getenv('BHM_LOG_DIR', str(BASE_DIR / 'logs')))
LOG_FILE = str(LOGS_DIR / 'results_log.txt')
DB_FILE = str(LOGS_DIR / 'bhm_scans.db')
_text_lock = threading.Lock()
log = logging.getLogger(__name__)


@contextmanager
def connection():
    Path(DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('''CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, patient_name TEXT,
            filename TEXT NOT NULL, timestamp TEXT NOT NULL, result TEXT NOT NULL,
            confidence REAL NOT NULL, is_tumor INTEGER NOT NULL,
            tumor_area_pct REAL DEFAULT 0.0, peak_saliency REAL DEFAULT 0.0,
            probabilities_json TEXT, notes TEXT DEFAULT '')''')


def log_result(image_path, label, confidence, probabilities=None, patient_id='ANON', patient_name='De-identified', tumor_area_pct=0.0, peak_saliency=0.0, notes=''):
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    filename = Path(str(image_path).replace('\\', '/')).name.replace('\n', ' ').replace('\r', ' ')
    if probabilities is None:
        probability_dict = {}
    elif isinstance(probabilities, dict):
        probability_dict = {str(k): float(v) for k, v in probabilities.items()}
    else:
        probability_dict = {PROBABILITY_LABELS[name]: float(value) * 100 for name, value in zip(CLASS_NAMES, probabilities)}
    with connection() as conn:
        cursor = conn.execute('''INSERT INTO scans(patient_id,patient_name,filename,timestamp,result,confidence,is_tumor,tumor_area_pct,peak_saliency,probabilities_json,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (patient_id, patient_name, filename, timestamp, label, float(confidence), int(label != 'No Tumor'), float(tumor_area_pct), float(peak_saliency), json.dumps(probability_dict, allow_nan=False), notes))
        scan_id = cursor.lastrowid
    try:
        with _text_lock:
            Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, 'a') as stream:
                stream.write(f'[{timestamp}] | File: {filename} | Result: {label} | Confidence: {confidence:.1f}% | {"NORMAL" if label == "No Tumor" else "TUMOR DETECTED"}\n')
    except OSError:
        log.exception('Optional text audit write failed; scan %s persisted in SQLite', scan_id)
    return scan_id


def get_log_path():
    return LOG_FILE


def get_scan_history(limit=100, offset=0):
    if not 1 <= limit <= 1000 or offset < 0:
        raise ValueError('History limit must be 1..1000 and offset nonnegative')
    with connection() as conn:
        rows = conn.execute('SELECT * FROM scans ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    results = []
    for row in rows:
        record = dict(row)
        record['probabilities'] = json.loads(record.pop('probabilities_json') or '{}')
        record['is_tumor'] = bool(record['is_tumor'])
        record['tumor_flag'] = 'TUMOR DETECTED' if record['is_tumor'] else 'NORMAL'
        record['tumor_area_pct'] = float(record['tumor_area_pct'] or 0)
        record['peak_saliency'] = float(record['peak_saliency'] or 0)
        results.append(record)
    return results


def get_scan_stats(model_dir=None):
    with connection() as conn:
        rows = conn.execute('SELECT result, COUNT(*) AS count, SUM(is_tumor) AS tumors FROM scans GROUP BY result').fetchall()
    total = sum(row['count'] for row in rows)
    tumors = sum(row['tumors'] for row in rows)
    counts = {label: 0 for label in DISPLAY_LABELS.values()}
    for row in rows:
        counts[row['result']] = row['count']
    accuracy = None
    evaluation = None
    if model_dir is not None:
        try:
            directory = Path(model_dir)
            measured = json.loads((directory / 'evaluation.json').read_text())
            value = measured['tflite']['accuracy']
            if measured['model_sha256'] == sha256_file(directory / 'brain_tumor_model.tflite') and isinstance(value, (int, float)) and 0 <= value <= 1:
                accuracy = f'{value * 100:.1f}%'
                evaluation = measured
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return {'total_scans': total, 'tumors_detected': tumors, 'normal_scans': total - tumors, 'class_counts': counts, 'model_accuracy': accuracy, 'evaluation': evaluation}


def clear_scan_history():
    with connection() as conn:
        conn.execute('DELETE FROM scans')
    with _text_lock:
        if Path(LOG_FILE).exists():
            Path(LOG_FILE).write_text('')
    return True

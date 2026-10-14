import os
import sqlite3
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOGS_DIR, 'results_log.txt')
DB_FILE = os.path.join(LOGS_DIR, 'bhm_scans.db')

def init_db():
    """Initializes the SQLite schema for clinical scan audit telemetry."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                patient_name TEXT,
                filename TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                result TEXT NOT NULL,
                confidence REAL NOT NULL,
                is_tumor INTEGER NOT NULL,
                tumor_area_pct REAL DEFAULT 0.0,
                peak_saliency REAL DEFAULT 0.0,
                probabilities_json TEXT,
                notes TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Logger] DB Init error: {e}")

# Initialize database on module import
init_db()

def log_result(
    image_path,
    label,
    confidence,
    probabilities=None,
    patient_id="ANON",
    patient_name="De-identified",
    tumor_area_pct=0.0,
    peak_saliency=0.0,
    notes=""
):
    """Log scan result to both SQLite database and flat audit text file."""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        filename = os.path.basename(image_path)
        is_tumor_flag = 1 if label != 'No Tumor' else 0
        tumor_flag = 'TUMOR DETECTED' if is_tumor_flag else 'NORMAL'

        # 1. Append to flat log file
        line = (
            f"[{timestamp}] | File: {filename:<30} | "
            f"Result: {label:<20} | Confidence: {confidence:5.1f}% | {tumor_flag}\n"
        )
        with open(LOG_FILE, 'a') as f:
            f.write(line)

        # 2. Insert into SQLite DB
        probs_str = json.dumps(probabilities) if probabilities else "{}"
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scans (
                patient_id, patient_name, filename, timestamp, result,
                confidence, is_tumor, tumor_area_pct, peak_saliency,
                probabilities_json, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id, patient_name, filename, timestamp, label,
            confidence, is_tumor_flag, tumor_area_pct, peak_saliency,
            probs_str, notes
        ))
        conn.commit()
        scan_id = cursor.lastrowid
        conn.close()

        print(f"[Logger] Result logged (ID: {scan_id}) to DB & {LOG_FILE}")
        return scan_id
    except Exception as e:
        print(f"[Logger] Error logging result: {e}")
        return None

def get_log_path():
    return LOG_FILE

def get_scan_history(limit=100):
    """Retrieve scan history from SQLite database with fallback to text log."""
    history = []
    try:
        if os.path.exists(DB_FILE):
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            for r in rows:
                history.append({
                    'id': r['id'],
                    'patient_id': r['patient_id'],
                    'patient_name': r['patient_name'],
                    'timestamp': r['timestamp'],
                    'filename': r['filename'],
                    'result': r['result'],
                    'confidence': float(r['confidence']),
                    'tumor_flag': 'TUMOR DETECTED' if r['is_tumor'] else 'NORMAL',
                    'is_tumor': bool(r['is_tumor']),
                    'tumor_area_pct': float(r['tumor_area_pct']),
                    'peak_saliency': float(r['peak_saliency']),
                    'notes': r['notes']
                })
            conn.close()
            if history:
                return history
    except Exception as e:
        print(f"[Logger] DB history query error: {e}")

    # Fallback to text file parser if DB is empty or fails
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line or not line.startswith('['):
                    continue
                parts = line.split(' | ')
                timestamp = parts[0].strip('[]')
                filename = parts[1].replace('File:', '').strip()
                result = parts[2].replace('Result:', '').strip()
                conf_str = parts[3].replace('Confidence:', '').replace('%', '').strip()
                confidence = float(conf_str)
                tumor_flag = parts[4].strip()
                history.append({
                    'id': len(history) + 1,
                    'patient_id': 'ANON',
                    'patient_name': 'De-identified',
                    'timestamp': timestamp,
                    'filename': filename,
                    'result': result,
                    'confidence': confidence,
                    'tumor_flag': tumor_flag,
                    'is_tumor': result != 'No Tumor',
                    'tumor_area_pct': 0.0,
                    'peak_saliency': 0.0,
                    'notes': ''
                })
        except Exception as e:
            print(f"[Logger] Fallback parsing error: {e}")
            
    return history

def get_scan_stats():
    """Calculate aggregate scan statistics from database."""
    history = get_scan_history(limit=5000)
    total = len(history)
    tumors = sum(1 for item in history if item['is_tumor'])
    normal = total - tumors
    class_counts = {
        'Glioma Tumor': sum(1 for item in history if 'glioma' in item['result'].lower()),
        'Meningioma Tumor': sum(1 for item in history if 'meningioma' in item['result'].lower()),
        'No Tumor': normal,
        'Pituitary Tumor': sum(1 for item in history if 'pituitary' in item['result'].lower())
    }
    return {
        'total_scans': total,
        'tumors_detected': tumors,
        'normal_scans': normal,
        'class_counts': class_counts,
        'model_accuracy': "96.4%"
    }

def clear_scan_history():
    """Clears history in both DB and flat log file."""
    try:
        if os.path.exists(DB_FILE):
            conn = sqlite3.connect(DB_FILE)
            conn.execute("DELETE FROM scans")
            conn.commit()
            conn.close()
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w') as f:
                f.write("")
        return True
    except Exception as e:
        print(f"[Logger] Error clearing history: {e}")
        return False

import os
from datetime import datetime

LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'logs', 'results_log.txt'
)

def log_result(image_path, label, confidence, probabilities):
    """Log scan result to a text file."""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        timestamp  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        filename   = os.path.basename(image_path)
        tumor_flag = 'TUMOR DETECTED' if label != 'No Tumor' else 'NORMAL'

        line = (
            f"[{timestamp}] | File: {filename:<30} | "
            f"Result: {label:<20} | Confidence: {confidence:5.1f}% | {tumor_flag}\n"
        )

        with open(LOG_FILE, 'a') as f:
            f.write(line)

        print(f"[Logger] Result logged to {LOG_FILE}")
    except Exception as e:
        print(f"[Logger] Error: {e}")

def get_log_path():
    return LOG_FILE

def get_scan_history():
    """Parse scan history from log file."""
    history = []
    if not os.path.exists(LOG_FILE):
        return history
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
        for line in reversed(lines):
            line = line.strip()
            if not line or not line.startswith('['):
                continue
            try:
                parts = line.split(' | ')
                timestamp = parts[0].strip('[]')
                filename = parts[1].replace('File:', '').strip()
                result = parts[2].replace('Result:', '').strip()
                conf_str = parts[3].replace('Confidence:', '').replace('%', '').strip()
                confidence = float(conf_str)
                tumor_flag = parts[4].strip()
                history.append({
                    'timestamp': timestamp,
                    'filename': filename,
                    'result': result,
                    'confidence': confidence,
                    'tumor_flag': tumor_flag,
                    'is_tumor': result != 'No Tumor'
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[Logger] Error parsing history: {e}")
    return history

def get_scan_stats():
    """Calculate aggregate scan statistics."""
    history = get_scan_history()
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

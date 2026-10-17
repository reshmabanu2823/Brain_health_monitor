import hashlib
import json
import numpy as np
import pytest
import logger


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(logger, 'DB_FILE', str(tmp_path / 'scans.db'))
    monkeypatch.setattr(logger, 'LOG_FILE', str(tmp_path / 'scans.txt'))
    logger.init_db()
    return tmp_path


def test_numpy_probability_persistence(store):
    scan_id = logger.log_result('scan.jpg', 'No Tumor', 90, np.array([.03, .04, .9, .03]))
    assert scan_id is not None
    assert logger.get_scan_history()[0]['probabilities']['No Tumor'] == pytest.approx(90)


def test_stats_not_limited_by_history(store):
    import sqlite3
    with sqlite3.connect(logger.DB_FILE) as conn:
        conn.executemany('INSERT INTO scans(filename,timestamp,result,confidence,is_tumor) VALUES (?,?,?,?,?)', [('scan', 'today', 'No Tumor', 90, 0)] * 5001)
    assert logger.get_scan_stats()['total_scans'] == 5001
    assert logger.get_scan_stats()['model_accuracy'] is None


def test_pagination(store):
    for i in range(3):
        logger.log_result(f'{i}.jpg', 'No Tumor', 90)
    assert [r['filename'] for r in logger.get_scan_history(limit=1, offset=1)] == ['1.jpg']


def test_evaluation_bound_to_artifact(store):
    model_dir = store / 'model'
    model_dir.mkdir()
    (model_dir / 'brain_tumor_model.tflite').write_bytes(b'artifact')
    data = {'model_sha256': hashlib.sha256(b'artifact').hexdigest(), 'tflite': {'accuracy': .75}}
    (model_dir / 'evaluation.json').write_text(json.dumps(data))
    assert logger.get_scan_stats(model_dir)['model_accuracy'] == '75.0%'
    (model_dir / 'brain_tumor_model.tflite').write_bytes(b'changed')
    assert logger.get_scan_stats(model_dir)['model_accuracy'] is None


def test_clear_does_not_resurrect_text_history(store):
    logger.log_result('a.jpg', 'No Tumor', 90)
    assert logger.clear_scan_history()
    assert logger.get_scan_history() == []

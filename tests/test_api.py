import asyncio
import base64
import io
from pathlib import Path
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
import logger
import server


class Model:
    def __init__(self, *args):
        pass

    def predict(self, path):
        image, metadata = (path, {}) if isinstance(path, Image.Image) else server.read_mri_file(path)
        return 'No Tumor', 90, np.array([.03, .04, .9, .03]), np.array(image), metadata


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('BHM_EEG_DB', str(tmp_path / 'eeg.db'))
    monkeypatch.setattr(logger, 'DB_FILE', str(tmp_path / 'scans.db'))
    monkeypatch.setattr(logger, 'LOG_FILE', str(tmp_path / 'scans.txt'))
    logger.init_db()
    monkeypatch.setattr(server, 'BrainTumorModel', Model)
    monkeypatch.setattr(server, 'preload_gradcam_model', lambda *a: None)
    monkeypatch.setattr(server, 'generate_gradcam_heatmap', lambda *a, **kw: (None, {}))
    monkeypatch.setattr(server, 'UPLOADS_DIR', str(tmp_path / 'uploads'))
    with TestClient(server.app) as c:
        yield c


def png():
    data = io.BytesIO()
    Image.new('RGB', (32, 32), 'white').save(data, format='PNG')
    return data.getvalue()


def upload(client, name='scan.png', data=None):
    return client.post('/api/predict', files={'file': (name, png() if data is None else data, 'image/png')})


def test_api_health(client):
    assert client.get('/api/health').json()['model_loaded']
    assert client.get('/api/ready').status_code == 200


def test_api_stats(client):
    stats = client.get('/api/stats').json()
    assert stats['total_scans'] == 0
    assert stats['model_accuracy'] is None


def test_api_predict(client):
    response = upload(client)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['confidence'] == 90
    assert result['heatmap_b64'] is None
    assert result['explanation']['available'] is False
    assert result['tumor_metrics'] == {}
    assert result['scan_id'] > 0
    assert client.get('/api/scans').json()[0]['filename'] == 'scan.png'


def test_traversal_filename_is_display_only(client, tmp_path):
    outside = tmp_path / 'victim.png'
    outside.write_bytes(b'keep')
    response = upload(client, '../victim.png')
    assert response.status_code == 200
    assert response.json()['filename'] == 'victim.png'
    assert outside.read_bytes() == b'keep'
    assert not list((tmp_path / 'uploads').iterdir())


@pytest.mark.parametrize('name,data,status', [('file.exe', b'x', 415), ('scan.png', b'not an image', 422), ('scan.png', b'', 422)])
def test_invalid_upload(client, name, data, status):
    assert upload(client, name, data).status_code == status


def test_upload_size_limit(client, monkeypatch):
    monkeypatch.setattr(server, 'MAX_UPLOAD_BYTES', 100)
    assert upload(client, data=b'x' * 101).status_code == 413


def test_missing_model_returns_503(client):
    server.app.state.model = None
    assert client.get('/api/ready').status_code == 503
    assert client.get('/api/health').json()['status'] == 'degraded'
    assert upload(client).status_code == 503


def test_concurrent_same_filename(client, tmp_path):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: upload(client), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert client.get('/api/stats').json()['total_scans'] == 2
    assert not list((tmp_path / 'uploads').iterdir())


def test_saturation_returns_503(client):
    gate = server.app.state.analysis_slots
    for _ in range(server.MAX_CONCURRENT_ANALYSES):
        assert gate.acquire(blocking=False)
    try:
        assert upload(client).status_code == 503
    finally:
        for _ in range(server.MAX_CONCURRENT_ANALYSES):
            gate.release()


def test_pdf_without_explanation(client):
    result = upload(client).json()
    response = client.post('/api/report/pdf', json={k: result[k] for k in ['filename', 'label', 'confidence', 'probabilities', 'tumor_metrics', 'original_b64', 'heatmap_b64']})
    assert response.status_code == 200, response.text
    assert response.content.startswith(b'%PDF')


def test_pdf_invalid_image_is_422(client):
    payload = {'filename': 'scan.png', 'label': 'No Tumor', 'confidence': 90, 'probabilities': {'No Tumor': 90}, 'original_b64': 'invalid', 'heatmap_b64': None}
    assert client.post('/api/report/pdf', json=payload).status_code == 422
    payload['confidence'] = 120
    assert client.post('/api/report/pdf', json=payload).status_code == 422


def test_pdf_escapes_user_text(client):
    result = upload(client).json()
    payload = {k: result[k] for k in ['filename', 'label', 'confidence', 'probabilities', 'original_b64', 'heatmap_b64']}
    payload['notes'] = '<b>unfinished & <broken>'
    payload['patient_name'] = '<b>unfinished'
    assert client.post('/api/report/pdf', json=payload).status_code == 200


def test_scans_pagination(client):
    upload(client)
    upload(client)
    assert len(client.get('/api/scans?limit=1&offset=1').json()) == 1
    assert client.get('/api/scans?limit=0').status_code == 422


def test_cancelled_worker_holds_slot(tmp_path):
    async def scenario():
        entered = threading.Event()
        finish = threading.Event()
        gate = threading.BoundedSemaphore(1)
        def worker():
            entered.set()
            finish.wait(2)
            return 42
        task = asyncio.create_task(server.run_analysis(worker, gate))
        while not entered.is_set():
            await asyncio.sleep(.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert not gate.acquire(blocking=False)
        finish.set()
        for _ in range(100):
            await asyncio.sleep(.01)
            if gate.acquire(blocking=False):
                gate.release()
                return
        pytest.fail('slot leaked after worker completion')
    asyncio.run(scenario())


def test_existing_history_does_not_expose_identity_fields(client):
    logger.log_result('deidentified.png','No Tumor',90,{'No Tumor':90},patient_id='PRIVATE-ID',patient_name='PRIVATE-NAME')
    row=client.get('/api/scans').json()[0]
    assert row['patient_id']=='ANON'
    assert row['patient_name']=='De-identified'

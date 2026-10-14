import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import app

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DIR = os.path.join(BASE_DIR, 'static', 'samples')

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_api_health(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'healthy'
    assert 'system' in data

def test_api_stats(client):
    res = client.get('/api/stats')
    assert res.status_code == 200
    data = res.json()
    assert 'total_scans' in data
    assert 'tumors_detected' in data

def test_api_scans(client):
    res = client.get('/api/scans')
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)

def test_api_predict(client):
    sample_path = os.path.join(SAMPLE_DIR, 'glioma.jpg')
    with open(sample_path, 'rb') as f:
        res = client.post(
            '/api/predict',
            files={'file': ('glioma.jpg', f, 'image/jpeg')}
        )
    assert res.status_code == 200
    data = res.json()
    assert data['success'] is True
    assert 'label' in data
    assert 'confidence' in data
    assert 'probabilities' in data
    assert 'tumor_metrics' in data
    assert data['original_b64'] is not None
    assert data['heatmap_b64'] is not None

def test_api_report_pdf(client):
    sample_path = os.path.join(SAMPLE_DIR, 'notumor.jpg')
    with open(sample_path, 'rb') as f:
        pred_res = client.post(
            '/api/predict',
            files={'file': ('notumor.jpg', f, 'image/jpeg')}
        )
    assert pred_res.status_code == 200
    pred_data = pred_res.json()

    payload = {
        "patient_id": "TEST-PAT-001",
        "patient_name": "Test Subject",
        "filename": "notumor.jpg",
        "label": pred_data['label'],
        "confidence": pred_data['confidence'],
        "probabilities": pred_data['probabilities'],
        "tumor_metrics": pred_data.get('tumor_metrics', {}),
        "original_b64": pred_data['original_b64'],
        "heatmap_b64": pred_data['heatmap_b64'],
        "notes": "Automated unit test execution."
    }

    res = client.post('/api/report/pdf', json=payload)
    assert res.status_code == 200
    assert res.headers['content-type'] == 'application/pdf'
    assert len(res.content) > 1000

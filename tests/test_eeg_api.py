import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.eeg.api import router
from app.eeg.service import EEGService
from app.eeg.storage import RecordingStore
from app.eeg.signal import SignalConfig


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    app.include_router(router)
    app.state.eeg = EEGService(RecordingStore(tmp_path / 'eeg.db'), SignalConfig())
    with TestClient(app) as client:
        yield client
    app.state.eeg.disconnect()


def test_unavailable_and_explicit_simulation(client):
    assert client.get('/api/eeg/live').json()['source'] is None
    assert not client.get('/api/eeg/model/info').json()['available']
    assert client.post('/api/device/connect', json={'source': 'simulated'}).status_code == 200
    time.sleep(.06)
    response = client.post('/api/eeg/recordings')
    assert response.status_code == 200, response.text
    rid = response.json()['id']
    time.sleep(.06)
    assert client.get('/api/eeg/live').json()['simulated']
    assert client.post('/api/eeg/recordings/stop').status_code == 200
    rows = client.get('/api/eeg/recordings').json()
    assert rows[0]['source'] == 'simulated' and rows[0]['sample_count'] > 0
    exported = client.get(f'/api/eeg/recordings/{rid}/export')
    assert 'simulated' in exported.text
    assert exported.headers['content-type'].startswith('text/csv')
    assert client.post('/api/device/disconnect').status_code == 200
    assert client.get('/api/eeg/live').json()['samples'] == []


def test_model_registry_and_session_summary(client):
    # 1. Check Model Registry
    reg = client.get('/api/eeg/models/registry').json()
    assert reg['registry_version'] == '2.0'
    assert len(reg['modules']) == 6
    module_ids = [m['module_id'] for m in reg['modules']]
    assert 'stress_state_index' in module_ids
    assert 'relaxation_alpha_reactivity' in module_ids
    assert 'cognitive_attention_engagement' in module_ids
    assert 'sleep_polysomnography_staging' in module_ids
    assert 'anxiety_disorder_assessment' in module_ids
    assert 'depression_screening_module' in module_ids
    for mod in reg['modules']:
        assert mod['availability'] is False
        assert mod['version'] is None
        assert len(mod['reason']) > 0
        assert len(mod['limitations']) > 0

    # 2. Check Session Summary & Research Notes
    client.post('/api/device/connect', json={'source': 'simulated'})
    time.sleep(.06)
    start_resp = client.post('/api/eeg/recordings', json={'notes': 'Baseline resting state test'})
    assert start_resp.status_code == 200
    rid = start_resp.json()['id']
    time.sleep(.1)
    client.post('/api/eeg/recordings/stop')
    client.post('/api/device/disconnect')

    # Get summary
    sum_resp = client.get(f'/api/eeg/recordings/{rid}/summary')
    assert sum_resp.status_code == 200
    summary = sum_resp.json()
    assert summary['session_id'] == rid
    assert summary['source'] == 'simulated'
    assert summary['notes'] == 'Baseline resting state test'
    assert 'preprocessing_config' in summary
    assert summary['preprocessing_config']['filter_type'] == 'butterworth'
    assert summary['preprocessing_config']['cutoffs_hz'] == [1.0, 40.0]
    assert 'quality_summary' in summary

    # Update notes
    note_resp = client.post(f'/api/eeg/recordings/{rid}/notes', json={'notes': 'Updated protocol notes'})
    assert note_resp.status_code == 200
    updated_summary = client.get(f'/api/eeg/recordings/{rid}/summary').json()
    assert updated_summary['notes'] == 'Updated protocol notes'


def test_invalid_ports_and_missing_recordings(client):
    assert client.post('/api/device/connect', json={'source': 'serial', 'port': '/etc/passwd'}).status_code == 422
    assert client.post('/api/device/connect', json={'source': 'unknown'}).status_code == 422
    assert client.post('/api/eeg/recordings').status_code == 409
    assert client.post('/api/eeg/recordings/stop').status_code == 409
    assert client.get('/api/eeg/recordings/missing/export').status_code == 404
    assert client.get('/api/eeg/recordings/missing/summary').status_code == 404


def test_foreign_origin_cannot_control_device(client):
    r = client.post('/api/device/connect', json={'source': 'simulated'}, headers={'Origin': 'https://unrelated.example'})
    assert r.status_code == 403
    assert client.get('/api/eeg/live').json()['source'] is None

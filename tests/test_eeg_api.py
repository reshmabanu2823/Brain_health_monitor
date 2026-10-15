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
    app=FastAPI(); app.include_router(router)
    app.state.eeg=EEGService(RecordingStore(tmp_path/'eeg.db'),SignalConfig())
    with TestClient(app) as client:
        yield client
    app.state.eeg.disconnect()


def test_unavailable_and_explicit_simulation(client):
    assert client.get('/api/eeg/live').json()['source'] is None
    assert not client.get('/api/eeg/model/info').json()['available']
    assert client.post('/api/device/connect',json={'source':'simulated'}).status_code==200
    time.sleep(.06)
    response=client.post('/api/eeg/recordings')
    assert response.status_code==200, response.text
    rid=response.json()['id']
    time.sleep(.06)
    assert client.get('/api/eeg/live').json()['simulated']
    assert client.post('/api/eeg/recordings/stop').status_code==200
    rows=client.get('/api/eeg/recordings').json()
    assert rows[0]['source']=='simulated' and rows[0]['sample_count']>0
    exported=client.get(f'/api/eeg/recordings/{rid}/export')
    assert 'simulated' in exported.text
    assert exported.headers['content-type'].startswith('text/csv')
    assert client.post('/api/device/disconnect').status_code==200
    assert client.get('/api/eeg/live').json()['samples']==[]


def test_invalid_ports_and_missing_recordings(client):
    assert client.post('/api/device/connect',json={'source':'serial','port':'/etc/passwd'}).status_code==422
    assert client.post('/api/device/connect',json={'source':'unknown'}).status_code==422
    assert client.post('/api/eeg/recordings').status_code==409
    assert client.post('/api/eeg/recordings/stop').status_code==409
    assert client.get('/api/eeg/recordings/missing/export').status_code==404


def test_foreign_origin_cannot_control_device(client):
    r=client.post('/api/device/connect',json={'source':'simulated'},headers={'Origin':'https://unrelated.example'})
    assert r.status_code==403
    assert client.get('/api/eeg/live').json()['source'] is None

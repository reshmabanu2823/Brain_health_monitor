import pytest
from fastapi.testclient import TestClient
from cortia.main import create_app
from cortia.config import Settings

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, testing=True))) as c:
        yield c


def signup(client, name='person'):
    r = client.post('/api/auth/register', json={'username':name,'password':'valid-test-password-47'})
    assert r.status_code == 201, r.text
    return r.json()


def test_auth_empty_states_and_logout(client):
    assert client.get('/api/sessions').status_code == 401
    signup(client)
    assert client.get('/api/sessions').json() == []
    assert client.get('/api/baselines').json() == []
    assert client.get('/api/mri/history').json() == []
    assert client.get('/api/devices/status').json()['state'] == 'disconnected'
    assert client.post('/api/baselines', json={}).status_code == 422
    client.post('/api/auth/logout')
    assert client.get('/api/auth/me').status_code == 401


def test_password_and_origin_validation(client):
    assert client.post('/api/auth/register', json={'username':'a','password':'x'}).status_code == 422
    signup(client)
    assert client.post('/api/auth/logout', headers={'origin':'https://evil.test'}).status_code == 403


def test_cross_user_missing_resource_no_leak(client):
    signup(client, 'first')
    assert client.get('/api/sessions/missing').status_code == 404
    client.post('/api/auth/logout')
    signup(client, 'second')
    assert client.get('/api/sessions/missing/report').status_code == 404
    assert client.get('/api/mri/missing/image').status_code == 404


def test_no_hardware_no_recording(client):
    signup(client)
    assert client.post('/api/sessions/start', json={'eyes':'closed','task':'rest','montage':'Fp1-ear'}).status_code == 409
    assert client.get('/api/sessions').json() == []


def test_websocket_rejects_unauthenticated(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/api/live'):
            pass


def test_websocket_cursor_resets_on_new_acquisition(client):
    import time
    user=signup(client,'streamowner')
    manager=client.app.state.acquisition
    with manager.lock:
        manager.owner=user['id'];manager.state='streaming';manager.last_sample_at=time.monotonic()
        manager.generation=1;manager.sequence=1000
        manager.samples.append({'sequence':1000,'value':8000})
    with client.websocket_connect('/api/live') as ws:
        first=ws.receive_json()
        assert first['samples'][0]['sequence']==1000
        with manager.lock:
            manager.generation=2;manager.sequence=1;manager.samples.clear()
            manager.samples.append({'sequence':1,'value':8100})
        for _ in range(10):
            next_run=ws.receive_json()
            if next_run.get('stream_id')==2:
                break
        assert next_run['samples']==[{'sequence':1,'value':8100}]

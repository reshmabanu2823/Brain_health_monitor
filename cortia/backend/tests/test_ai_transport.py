"""Real loopback HTTP verifies transport contracts, never claims live-provider testing."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from cortia.config import Settings
from cortia.main import create_app
from cortia.models import Explanation
from test_api import signup
from test_integrity import insert_sessions


@pytest.fixture
def provider():
    state = dict(status=200,content=json.dumps({'statement_ids':['band_alpha']}),requests=[])
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state['requests'].append(dict(body=json.loads(self.rfile.read(int(self.headers['Content-Length']))),
                                          authorization=self.headers.get('Authorization')))
            body = json.dumps({'choices':[{'message':{'content':state['content']}}]}).encode()
            self.send_response(state['status'])
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)
        def log_message(self,*args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker = threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
    worker.start()
    state['endpoint'] = f'http://127.0.0.1:{server.server_port}/chat/completions'
    try:
        yield state
    finally:
        server.shutdown();server.server_close();worker.join(timeout=2)


def prepared_app(tmp_path,provider):
    return create_app(Settings(data_dir=tmp_path,testing=True,ai_endpoint=provider['endpoint'],
                               ai_key='loopback-test-secret',ai_model='loopback-test-model'))


def test_consented_ai_request_round_trip_saves_only_verified_statements(tmp_path,provider):
    app = prepared_app(tmp_path,provider)
    with TestClient(app) as client:
        user = signup(client,'aiowner')
        sid = insert_sessions(app,user['id'],n=1)[0]
        response = client.post(f'/api/sessions/{sid}/explanations',json={'use_external_ai':True,'consent_to_send_metrics':True})
        assert response.status_code == 200,response.text
        result = response.json()
        assert result['ai_generated'] is True
        assert result['provider'] == 'loopback-test-model'
        assert len(result['evidence_digest']) == 64
        assert 'Mean alpha relative band power is 40.0%.' in result['statements']
        assert len(result['statements']) == 3  # Quality + chosen evidence + limitations.
        assert 'cannot establish' in result['statements'][-1]
        assert len(client.get(f'/api/sessions/{sid}/explanations').json()) == 1
        request = provider['requests'][0]
        assert request['authorization'] == 'Bearer loopback-test-secret'
        assert request['body']['model'] == 'loopback-test-model'
        transmitted = json.dumps(request['body'])
        assert user['id'] not in transmitted and 'aiowner' not in transmitted
        assert 'raw_path' not in transmitted and 'password' not in transmitted


def test_no_consent_never_contacts_configured_provider(tmp_path,provider):
    app = prepared_app(tmp_path,provider)
    with TestClient(app) as client:
        user = signup(client,'noconsent')
        sid = insert_sessions(app,user['id'],n=1)[0]
        response = client.post(f'/api/sessions/{sid}/explanations',json={'use_external_ai':True})
        assert response.status_code == 422
        assert provider['requests'] == []
        assert client.get(f'/api/sessions/{sid}/explanations').json() == []


@pytest.mark.parametrize('content',[
    '{"statement_ids":["invented_diagnosis"]}',
    '{"statement_ids":["band_alpha"],"text":"Invented diagnosis"}',
    'Invented diagnosis, not JSON',
])
def test_invalid_provider_findings_never_persist(tmp_path,provider,content):
    provider['content'] = content
    app = prepared_app(tmp_path,provider)
    with TestClient(app) as client:
        user = signup(client,'invalidprovider')
        sid = insert_sessions(app,user['id'],n=1)[0]
        response = client.post(f'/api/sessions/{sid}/explanations',json={'use_external_ai':True,'consent_to_send_metrics':True})
        assert response.status_code == 422
        assert client.get(f'/api/sessions/{sid}/explanations').json() == []
        with app.state.db() as db:
            assert db.query(Explanation).count() == 0


def test_failed_provider_returns_safe_error_without_saved_findings(tmp_path,provider):
    provider['status'] = 503
    app = prepared_app(tmp_path,provider)
    with TestClient(app) as client:
        user = signup(client,'providerdown')
        sid = insert_sessions(app,user['id'],n=1)[0]
        response = client.post(f'/api/sessions/{sid}/explanations',json={'use_external_ai':True,'consent_to_send_metrics':True})
        assert response.status_code == 502
        assert 'loopback-test-secret' not in response.text
        assert provider['endpoint'] not in response.text
        assert client.get(f'/api/sessions/{sid}/explanations').json() == []

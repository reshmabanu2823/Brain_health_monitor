from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from cortia.main import create_app
from cortia.config import Settings
from cortia.models import User, Recording, Baseline, MRIUpload, MRIPrediction
from test_api import signup


def context():
    return {'eyes':'closed','task':'rest','montage':'Fp1-ear','notes':'different notes allowed'}

def insert_sessions(app,user_id,n=3):
    ids=[]
    with app.state.db() as db:
        for i in range(n):
            r=Recording(user_id=user_id,state='completed',context=context(),config={'sampling_hz':500},raw_path='raw/test.csv',
                        sample_count=12000,valid_windows=3,features={'relative_alpha':.4+i*.1})
            db.add(r);db.flush();ids.append(r.id)
        db.commit()
    return ids


def test_owner_isolation_and_baseline_comparison(tmp_path):
    app=create_app(Settings(data_dir=tmp_path,testing=True))
    with TestClient(app) as first, TestClient(app) as second:
        user=signup(first,'owner')
        ids=insert_sessions(app,user['id'])
        base=first.post('/api/baselines',json={'session_ids':ids})
        assert base.status_code==201,base.text
        detail=first.get('/api/sessions/'+ids[0]).json()
        assert detail['baseline']['available']
        assert detail['baseline']['included_in_baseline']
        assert detail['baseline']['deviations']['relative_alpha']['z_score'] < 0
        signup(second,'outsider')
        for suffix in ('','/segments','/anomalies','/report','/raw','/explanations'):
            assert second.get('/api/sessions/'+ids[0]+suffix).status_code==404
        assert second.post('/api/baselines',json={'session_ids':ids}).status_code==404
        assert second.get('/api/baselines').json()==[]
        assert second.post('/api/sessions/'+ids[0]+'/explanations',json={}).status_code==404
        summary=first.post('/api/sessions/'+ids[0]+'/explanations',json={})
        assert summary.status_code==200
        assert not summary.json()['ai_generated']
        assert first.post('/api/sessions/'+ids[0]+'/explanations',json={'use_external_ai':True}).status_code==422


def test_mri_real_upload_isolation_and_report(tmp_path):
    source=Path('/home/vinay/brain_health_monitor/dataset/no/N1.JPG')
    if not source.exists():
        import pytest
        pytest.skip('Source MRI fixture absent')
    app=create_app(Settings(data_dir=tmp_path,testing=True))
    with TestClient(app) as first,TestClient(app) as second:
        signup(first,'mriowner')
        response=first.post('/api/mri/predict',files={'file':('real.jpg',source.read_bytes(),'image/jpeg')})
        assert response.status_code==201,response.text
        mid=response.json()['id']
        assert first.get('/api/mri/'+mid+'/image').status_code==200
        assert first.get('/api/mri/'+mid+'/report').json()['result']['kind']=='model_prediction'
        signup(second,'mrioutsider')
        assert second.get('/api/mri/'+mid+'/image').status_code==404
        assert second.get('/api/mri/'+mid+'/report').status_code==404
        assert second.get('/api/mri/history').json()==[]


def test_oversized_content_length_rejected(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path,testing=True))) as client:
        assert client.post('/api/auth/register',content=b'x',headers={'content-length':str(20*1024*1024)}).status_code==413


def test_baseline_insufficient_windows_rejected(tmp_path):
    app=create_app(Settings(data_dir=tmp_path,testing=True))
    with TestClient(app) as client:
        user=signup(client,'baselineuser')
        ids=insert_sessions(app,user['id'])
        with app.state.db() as db:
            db.get(Recording,ids[0]).valid_windows=2
            db.commit()
        assert client.post('/api/baselines',json={'session_ids':ids}).status_code==422


def test_chunked_upload_body_limit_before_multipart_parse(tmp_path):
    app=create_app(Settings(data_dir=tmp_path,testing=True,max_upload_bytes=1024))
    with TestClient(app) as client:
        # Unknown content length, as with chunked transfer. Guard before multipart parser.
        def chunks():
            for _ in range(100):
                yield b'x'*1024
        response=client.post('/api/auth/register',content=chunks(),headers={'content-type':'application/json'})
        assert response.status_code==413

from dataclasses import asdict
import json
import numpy as np
import pytest
from app.eeg.training import load_manifest, train
from app.eeg.model import EEGModel
from app.eeg.signal import SignalConfig, analyze


def dataset(tmp_path):
    records=[]
    for split in ['train','validation','test']:
        for label,freq in [('eyes_open',18),('eyes_closed',10)]:
            for subject in range(2):
                index=len(records)
                t=np.arange(1500)/250
                x=np.rint(512+30*np.sin(2*np.pi*freq*t + index*.1))
                p=tmp_path/f'{index}.csv'
                np.savetxt(p,np.column_stack([t,x]),delimiter=',',header='timestamp_s,value',comments='')
                records.append({'path':p.name,'subject':f'{split}_{label}_{subject}', 'label':label,'split':split})
    p=tmp_path/'manifest.json'
    p.write_text(json.dumps({'task':'test fixture eyes state','provenance':'generated test fixture only', 'license':'test fixture', 'units':'adc_counts', 'sample_rate':250,'recordings':records}))
    return p


def test_subject_and_duplicate_leakage_rejected(tmp_path):
    p=dataset(tmp_path); d=json.loads(p.read_text())
    d['recordings'][-1]['subject']=d['recordings'][0]['subject']
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match='subject'): load_manifest(p)
    p=dataset(tmp_path); d=json.loads(p.read_text())
    d['recordings'][-1]['path']=d['recordings'][0]['path']
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match='Duplicate'): load_manifest(p)


def test_training_roundtrip_and_corrupt_artifact(tmp_path):
    p=dataset(tmp_path); out=tmp_path/'artifact'
    report=train(p,out)
    assert report['test']['sample_count']==4
    assert report['baseline_test']['sample_count']==4
    assert set(report['splits'])=={'train','validation','test'}
    model=EEGModel(out)
    assert model.info['available']
    t=np.arange(1500)/250; x=512+30*np.sin(2*np.pi*10*t)
    result=analyze(t,x,SignalConfig())
    assert model.predict(result,SignalConfig())['available']
    assert not model.predict(result,SignalConfig(high_hz=35))['available']
    (out/'model.joblib').write_bytes(b'corrupt')
    assert not EEGModel(out).info['available']


def test_no_model_is_explicitly_unavailable(tmp_path):
    assert not EEGModel(tmp_path/'absent').info['available']

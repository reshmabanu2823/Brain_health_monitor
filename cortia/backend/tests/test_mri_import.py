import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from cortia.mri.importer import import_bundle
from cortia.mri.service import CLASSES


@pytest.fixture
def repository(tmp_path):
    root = tmp_path/'repo'
    directory = root/'candidate'
    directory.mkdir(parents=True)
    for name in ('brain_tumor_model.tflite','best_model.h5'):
        (directory/name).write_bytes(b'test import artifact, not an inference model')
    (directory/'class_indices.json').write_text(json.dumps(dict(zip(CLASSES,range(4)))))
    metadata = dict(schema_version=1,preprocessing='mobilenet_v2',image_size=[224,224],classes=CLASSES,
                    output='probabilities',training={'backbone':'efficientnetv2s','split_counts':{'train':10,'validation':4}},
                    artifact_hashes={name:hashlib.sha256((directory/name).read_bytes()).hexdigest()
                                     for name in ('brain_tumor_model.tflite','best_model.h5')})
    (directory/'metadata.json').write_text(json.dumps(metadata))
    (directory/'manifest.json').write_text('{"train":[],"validation":[],"test":[]}')
    subprocess.run(['git','init','-q',str(root)],check=True)
    subprocess.run(['git','-C',str(root),'add','.'],check=True)
    subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.invalid',
                    'commit','-qm','fixture'],check=True)
    return root


def test_import_preserves_contract_hashes_and_training_provenance(repository,tmp_path):
    output = tmp_path/'bundle'
    result = import_bundle(repository,'candidate',output)
    assert result['preprocessing'] == 'mobilenet_v2'
    assert result['experimental_candidate'] is True
    assert result['source_artifacts_in_commit'] is True
    assert result['architecture'] == 'efficientnetv2s'
    assert result['training_provenance']['training_metadata']['split_counts']['train'] == 10
    assert len(result['training_provenance']['dataset_manifest_sha256']) == 64
    for name,digest in result['artifact_hashes'].items():
        assert hashlib.sha256((output/name).read_bytes()).hexdigest() == digest
        assert (output/name).read_bytes() == (repository/'candidate'/name).read_bytes()


def test_import_rejects_tampered_artifacts_before_output(repository,tmp_path):
    (repository/'candidate/best_model.h5').write_bytes(b'changed')
    with pytest.raises(ValueError,match='integrity'):
        import_bundle(repository,'candidate',tmp_path/'bundle')
    assert not (tmp_path/'bundle').exists()


def test_import_rejects_unknown_contract_and_unlabelled_candidate(repository,tmp_path):
    path = repository/'candidate/metadata.json'
    metadata = json.loads(path.read_text());metadata['preprocessing']='unknown'
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError,match='contract'):
        import_bundle(repository,'candidate',tmp_path/'bundle')
    path.unlink()
    with pytest.raises(ValueError,match='metadata'):
        import_bundle(repository,'candidate',tmp_path/'bundle')


@pytest.mark.parametrize('value',[{},[]])
def test_import_rejects_empty_candidate_metadata(repository,tmp_path,value):
    (repository/'candidate/metadata.json').write_text(json.dumps(value))
    with pytest.raises(ValueError,match='contract'):
        import_bundle(repository,'candidate',tmp_path/'bundle')
    assert not (tmp_path/'bundle').exists()


def test_import_refuses_existing_output_and_external_source(repository,tmp_path):
    output = tmp_path/'bundle';output.mkdir();(output/'keep').write_text('keep')
    with pytest.raises(FileExistsError):
        import_bundle(repository,'candidate',output)
    assert (output/'keep').read_text() == 'keep'
    with pytest.raises(ValueError,match='path'):
        import_bundle(repository,'../outside',tmp_path/'other')


def test_import_records_modified_artifacts_outside_commit(repository,tmp_path):
    source = repository/'candidate'
    (source/'best_model.h5').write_bytes(b'new local training output')
    metadata = json.loads((source/'metadata.json').read_text())
    metadata['artifact_hashes']['best_model.h5']=hashlib.sha256((source/'best_model.h5').read_bytes()).hexdigest()
    (source/'metadata.json').write_text(json.dumps(metadata))
    result = import_bundle(repository,'candidate',tmp_path/'bundle')
    assert result['source_artifacts_in_commit'] is False


def test_legacy_import_retains_original_source_contract(repository,tmp_path):
    (repository/'candidate').rename(repository/'model')
    (repository/'model/metadata.json').unlink()
    result = import_bundle(repository,'model',tmp_path/'bundle')
    assert result['preprocessing'] == 'legacy_rgb_0_1'
    assert result['experimental_candidate'] is False
    assert result['classes'] == CLASSES


def test_import_does_not_accept_boolean_class_indices(repository,tmp_path):
    mapping = dict(zip(CLASSES,range(4)))
    mapping['meningioma_tumor'] = True
    (repository/'candidate/class_indices.json').write_text(json.dumps(mapping))
    with pytest.raises(ValueError,match='class contract'):
        import_bundle(repository,'candidate',tmp_path/'bundle')


def test_import_locates_archived_manifest_matching_recorded_experiment(repository,tmp_path):
    source = repository/'candidate'
    archived = b'{"train":[],"validation":[],"test":[],"seed":42}'
    (source/'evaluation-manifest.json').write_bytes(archived)
    expected = hashlib.sha256(archived).hexdigest()
    (source/'experiment.json').write_text(json.dumps({'manifest_sha256':expected,'promoted':False}))
    result = import_bundle(repository,'candidate',tmp_path/'bundle')
    provenance = result['training_provenance']
    assert provenance['dataset_manifest_sha256'] == expected
    assert provenance['dataset_manifest_file'] == 'evaluation-manifest.json'
    assert provenance['dataset_manifest_matches_experiment'] is True
    assert provenance['source_promoted'] is False


def test_import_marks_unverifiable_training_record(repository,tmp_path):
    source = repository/'candidate'
    (source/'experiment.json').write_text(json.dumps({'manifest_sha256':'0'*64,'promoted':False}))
    result = import_bundle(repository,'candidate',tmp_path/'bundle')
    assert result['training_provenance']['dataset_manifest_matches_experiment'] is False
    assert any('training manifest' in text for text in result['limitations'])

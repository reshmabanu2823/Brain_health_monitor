import hashlib

import pytest

from benchmark_mri import classification_metrics, verify_records
from cortia.mri.service import CLASSES


def test_metrics_capture_wrong_classes_and_missing_predictions():
    result = classification_metrics([0,0,1,1,2,2,3,3], [0,1,1,1,2,0,3,2])
    assert result['confusion_matrix'] == [[1,1,0,0],[0,2,0,0],[1,0,1,0],[0,0,1,1]]
    assert result['accuracy'] == .625
    assert result['macro_f1'] == pytest.approx(.6166666666666667)
    assert result['per_class']['glioma_tumor'] == {'precision':.5, 'recall':.5, 'f1':.5, 'support':2}
    assert result['per_class']['meningioma_tumor']['recall'] == 1
    assert result['per_class']['pituitary_tumor']['precision'] == 1
    with pytest.raises(ValueError):
        classification_metrics([0], [])


def manifest_record(path, content, label=0):
    return dict(path=path, sha256=hashlib.sha256(content).hexdigest(),
                class_name=CLASSES[label], class_index=label)


def test_manifest_rejects_recorded_split_overlap(tmp_path):
    (tmp_path/'image.jpg').write_bytes(b'fixture')
    record = manifest_record('image.jpg', b'fixture')
    with pytest.raises(ValueError, match='overlap'):
        verify_records(tmp_path, dict(classes=CLASSES, train=[record], validation=[], test=[record]))


def test_manifest_rejects_changed_file_and_label(tmp_path):
    (tmp_path/'image.jpg').write_bytes(b'changed')
    record = manifest_record('image.jpg', b'original')
    manifest = dict(classes=CLASSES, train=[], validation=[], test=[record])
    with pytest.raises(ValueError, match='hash'):
        verify_records(tmp_path, manifest)
    record['sha256'] = hashlib.sha256(b'changed').hexdigest()
    record['class_name'] = 'no_tumor'
    with pytest.raises(ValueError, match='label'):
        verify_records(tmp_path, manifest)


def test_manifest_rejects_duplicates_and_external_paths(tmp_path):
    record = manifest_record('../outside.jpg', b'fixture')
    manifest = dict(classes=CLASSES, train=[], validation=[], test=[record])
    with pytest.raises(ValueError, match='path'):
        verify_records(tmp_path, manifest)
    (tmp_path/'image.jpg').write_bytes(b'fixture')
    record['path'] = 'image.jpg'
    manifest['test'] = [record, record]
    with pytest.raises(ValueError, match='(?i)duplicate'):
        verify_records(tmp_path, manifest)

import json
import numpy as np
import pytest
from PIL import Image


def dataset(tmp_path):
    classes = ['glioma_tumor', 'meningioma_tumor', 'no_tumor', 'pituitary_tumor']
    for split in ['Training', 'Testing']:
        for c, name in enumerate(classes):
            path = tmp_path / split / name
            path.mkdir(parents=True)
            for i in range(6 if split == 'Training' else 2):
                Image.new('RGB', (8, 8), (c * 50, i * 20, 0 if split == 'Training' else 100)).save(path / f'{i}.png')
    return tmp_path


def test_manifest_disjoint_and_reproducible(tmp_path):
    from app.dataset import build_manifest
    root = dataset(tmp_path)
    duplicate = root / 'Training/glioma_tumor/copy.png'
    duplicate.write_bytes((root / 'Testing/glioma_tumor/0.png').read_bytes())
    manifest = build_manifest(root, seed=42)
    hashes = {split: {r['sha256'] for r in manifest[split]} for split in ['train', 'validation', 'test']}
    assert not hashes['train'] & hashes['validation']
    assert not (hashes['train'] | hashes['validation']) & hashes['test']
    assert manifest['excluded']['test_overlap'] == 1
    assert manifest == build_manifest(root, seed=42)
    assert all(sum(r['class_index'] == c for r in manifest['validation']) >= 1 for c in range(4))


def test_conflicting_duplicate_labels_fail(tmp_path):
    from app.dataset import build_manifest
    root = dataset(tmp_path)
    (root / 'Training/meningioma_tumor/conflict.png').write_bytes((root / 'Testing/glioma_tumor/0.png').read_bytes())
    with pytest.raises(ValueError, match='conflicting'):
        build_manifest(root)


def test_balanced_weights():
    from app.dataset import balanced_class_weights
    weights = balanced_class_weights([0, 0, 0, 1, 2, 3])
    assert weights[0] == pytest.approx(.5)
    assert weights[1] == pytest.approx(1.5)
    with pytest.raises(ValueError):
        balanced_class_weights([0, 1])


def test_classification_metrics():
    from app.evaluation import classification_metrics
    report = classification_metrics([0, 0, 1, 2, 3], [0, 1, 1, 2, 3])
    assert report['accuracy'] == pytest.approx(.8)
    assert report['confusion_matrix'][0] == [1, 1, 0, 0]
    assert report['per_class']['glioma_tumor']['recall'] == pytest.approx(.5)
    assert report['per_class']['meningioma_tumor']['precision'] == pytest.approx(.5)
    json.dumps(report, allow_nan=False)


def test_training_import_has_no_side_effects(tmp_path):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-c', 'import train_model; print("import-safe")'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'import-safe'


def test_extra_no_tumor_images_join_training_pool_only(tmp_path):
    from app.dataset import build_manifest
    root = dataset(tmp_path)
    extra = tmp_path / 'extra'
    extra.mkdir()
    Image.new('RGB', (8, 8), (9, 9, 9)).save(extra / 'new.png')
    (extra / 'dup.png').write_bytes((root / 'Testing/no_tumor/0.png').read_bytes())
    manifest = build_manifest(root, seed=42, extra_no_tumor_dir=extra)
    paths = {r['path'] for split in ('train', 'validation') for r in manifest[split]}
    assert any(p.endswith('new.png') for p in paths)
    assert not any(p.endswith('dup.png') for p in paths)
    assert manifest['excluded']['test_overlap'] == 1
    assert manifest['test'] == build_manifest(root, seed=42)['test']


def _textured(seed, size=64):
    import numpy as np
    rng = np.random.default_rng(seed)
    base = np.kron(rng.random((8, 8)), np.ones((size // 8, size // 8)))
    return Image.fromarray((base * 200 + 30).astype('uint8')).convert('RGB')


def test_extra_class_dir_drops_near_duplicates_and_splits_by_patient(tmp_path):
    from app.dataset import build_manifest
    root = dataset(tmp_path)
    _textured(1).save(root / 'Testing/glioma_tumor/textured.png')
    extra = tmp_path / 'extra'
    (extra / 'glioma_tumor').mkdir(parents=True)
    _textured(1).resize((100, 100)).save(extra / 'glioma_tumor/copy.png')
    index = {}
    for patient in range(6):
        for n in range(3):
            name = f'p{patient}_{n}.png'
            _textured(100 + patient * 10 + n).save(extra / 'glioma_tumor' / name)
            index[f'glioma_tumor/{name}'] = f'p{patient}'
    (extra / 'index.json').write_text(json.dumps(index))
    manifest = build_manifest(root, seed=42, extra_class_dir=extra)
    assert manifest['excluded']['extra_near_test_duplicates'] == 1
    patients = {s: {r['patient'] for r in manifest[s] if r.get('patient')} for s in ('train', 'validation')}
    assert patients['validation'] and patients['train']
    assert not patients['train'] & patients['validation']
    assert manifest['test'] == build_manifest(root, seed=42)['test']


def test_pooled_manifest_keeps_clusters_and_patients_together(tmp_path):
    from app.dataset import build_pooled_manifest
    root = dataset(tmp_path)
    for split in ('Training', 'Testing'):
        for c, name in enumerate(['glioma_tumor', 'meningioma_tumor', 'no_tumor', 'pituitary_tumor']):
            for i in range(20):
                _textured(1000 + c * 100 + i + (50 if split == 'Testing' else 0)).save(root / split / name / f'tex{i}.png')
    _textured(1000).resize((90, 90)).save(root / 'Testing/glioma_tumor/near_copy.png')
    manifest = build_pooled_manifest(root, seed=1)
    where = {r['path']: split for split in ('train', 'validation', 'test') for r in manifest[split]}
    assert where['Testing/glioma_tumor/near_copy.png'] == where['Training/glioma_tumor/tex0.png']
    assert all({r['class_index'] for r in manifest[s]} == {0, 1, 2, 3} for s in ('train', 'validation', 'test'))
    assert manifest == build_pooled_manifest(root, seed=1)


def test_clustered_validation_keeps_similar_images_and_cross_label_patients_together(tmp_path):
    from app.dataset import build_manifest, perceptual_hash
    root = tmp_path / 'data'
    names = ['glioma_tumor', 'meningioma_tumor', 'no_tumor', 'pituitary_tumor']
    for split in ('Training', 'Testing'):
        for c, name in enumerate(names):
            folder = root / split / name
            folder.mkdir(parents=True)
            for i in range(12 if split == 'Training' else 2):
                _textured(1000 + c * 100 + i + (50 if split == 'Testing' else 0)).save(folder / f'{i}.png')
    _textured(1000).resize((128, 128)).save(root / 'Training/meningioma_tumor/near_copy.png')
    extra = tmp_path / 'extra'
    index = {}
    for c, name in enumerate(names[:2]):
        (extra / name).mkdir(parents=True)
        for i in range(4):
            filename = f'patient{i}.png'
            _textured(5000 + c * 100 + i).save(extra / name / filename)
            index[f'{name}/{filename}'] = f'patient{i}'
    (extra / 'index.json').write_text(json.dumps(index))
    baseline = build_manifest(root, extra_class_dir=extra)
    manifest = build_manifest(root, extra_class_dir=extra, cluster_validation=True)
    assert manifest['test'] == baseline['test']
    assert {r['sha256'] for s in ('train', 'validation') for r in manifest[s]} == {
        r['sha256'] for s in ('train', 'validation') for r in baseline[s]
    }
    assert manifest == build_manifest(root, extra_class_dir=extra, cluster_validation=True)
    where = {r['path']: s for s in ('train', 'validation') for r in manifest[s]}
    assert where['Training/glioma_tumor/0.png'] == where['Training/meningioma_tumor/near_copy.png']
    patients = {s: {r['patient'] for r in manifest[s] if r.get('patient')} for s in ('train', 'validation')}
    assert not patients['train'] & patients['validation']
    train_hashes = [perceptual_hash(root / r['path']) for r in manifest['train']]
    for r in manifest['validation']:
        h = perceptual_hash(root / r['path'])
        assert all((h ^ other).bit_count() > 3 for other in train_hashes)
    assert all({r['class_index'] for r in manifest[s]} == {0, 1, 2, 3} for s in ('train', 'validation'))
    assert manifest['validation_grouping']['max_hash_distance'] == 3


def test_clustered_validation_rejects_unsplittable_groups(tmp_path):
    from app.dataset import build_manifest
    # Flat images all share one perceptual hash; splitting them would leak.
    with pytest.raises(ValueError, match='cluster'):
        build_manifest(dataset(tmp_path), cluster_validation=True)


def test_cluster_validation_cannot_silently_use_pooled_test_protocol():
    from train_model import parse_args
    with pytest.raises(SystemExit) as error:
        parse_args(['--cluster-validation', '--pooled'])
    assert error.value.code == 2


def test_clustered_validation_preserves_patient_links_through_exact_deduplication(tmp_path):
    from app.dataset import build_manifest
    root = tmp_path / 'data'
    names = ['glioma_tumor', 'meningioma_tumor', 'no_tumor', 'pituitary_tumor']
    for split in ('Training', 'Testing'):
        for c, name in enumerate(names):
            folder = root / split / name
            folder.mkdir(parents=True)
            for i in range(12 if split == 'Training' else 2):
                _textured(1000 + c * 100 + i + (50 if split == 'Testing' else 0)).save(folder / f'{i}.png')
    extra = tmp_path / 'extra'
    folder = extra / 'glioma_tumor'
    folder.mkdir(parents=True)
    original = root / 'Training/glioma_tumor/0.png'
    (folder / 'copy_a.png').write_bytes(original.read_bytes())
    (folder / 'copy_b.png').write_bytes(original.read_bytes())
    _textured(5001).save(folder / 'other_a.png')
    _textured(5002).save(folder / 'other_b.png')
    (extra / 'index.json').write_text(json.dumps({
        'glioma_tumor/copy_a.png': 'patient_a', 'glioma_tumor/other_a.png': 'patient_a',
        'glioma_tumor/copy_b.png': 'patient_b', 'glioma_tumor/other_b.png': 'patient_b',
    }))
    for seed in (1, 42):
        manifest = build_manifest(root, seed=seed, extra_class_dir=extra, cluster_validation=True)
        where = {r['path']: s for s in ('train', 'validation') for r in manifest[s]}
        assert where['Training/glioma_tumor/0.png'] == where[str(folder / 'other_a.png')]
        assert where[str(folder / 'other_a.png')] == where[str(folder / 'other_b.png')]


def test_clustered_validation_backtracks_for_feasible_class_coverage(tmp_path):
    from app.artifacts import sha256_file
    from app.dataset import _clustered_validation_split
    vectors = [(0, 0, 1, 1), (3, 2, 0, 1), (2, 0, 0, 1), (0, 2, 2, 3)]
    records = []
    for group, vector in enumerate(vectors):
        for c, count in enumerate(vector):
            for i in range(count):
                path = tmp_path / f'cluster{group}_{c}_{i}.png'
                _textured(10000 + len(records)).save(path)
                records.append({'path': path.name, 'class_index': c, 'sha256': sha256_file(path), 'patient': f'p{group}'})
    train, validation, _ = _clustered_validation_split(records, tmp_path, 42, .2)
    assert {r['class_index'] for r in train} == {0, 1, 2, 3}
    assert {r['class_index'] for r in validation} == {0, 1, 2, 3}
    assert not {r['patient'] for r in train} & {r['patient'] for r in validation}

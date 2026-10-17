"""Deterministic hash-disjoint MRI dataset manifests."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import numpy as np
from PIL import Image
from .artifacts import CLASS_NAMES, sha256_file

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff'}


NEAR_DUPLICATE_BITS = 6
CLUSTER_BITS = 3


def perceptual_hash(path):
    """64-bit difference hash of the brain-cropped image; survives re-encoding, resizing and cropping."""
    with Image.open(path) as image:
        gray = np.asarray(image.convert('L'), dtype=np.float32)
    rows, cols = np.where(gray > gray.max() * .1)
    if rows.size:
        gray = gray[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    small = np.asarray(Image.fromarray(gray.astype(np.uint8)).resize((9, 8), Image.Resampling.BILINEAR), dtype=np.float32)
    return int(''.join('1' if bit else '0' for bit in (small[:, 1:] > small[:, :-1]).flatten()), 2)


def build_manifest(dataset_dir, seed=42, validation_fraction=.2, extra_no_tumor_dir=None, extra_class_dir=None, cluster_validation=False):
    if not 0 < validation_fraction < 1:
        raise ValueError('Validation fraction must be between zero and one')
    root = Path(dataset_dir).resolve()
    records = []
    for split in ('Training', 'Testing'):
        split_dir = root / split
        if not split_dir.is_dir():
            raise ValueError(f'Missing dataset directory: {split_dir}')
        unknown = {p.name for p in split_dir.iterdir() if p.is_dir()} - set(CLASS_NAMES)
        if unknown:
            raise ValueError(f'Unknown dataset classes: {sorted(unknown)}')
        for index, name in enumerate(CLASS_NAMES):
            folder = split_dir / name
            files = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
            if not files:
                raise ValueError(f'Missing images for {split}/{name}')
            for path in files:
                records.append({'path': path.relative_to(root).as_posix(), 'class_name': name, 'class_index': index, 'sha256': sha256_file(path), 'source_split': split})
    if extra_no_tumor_dir is not None:
        # Certain-label supplementary images: training pool only, never the test partition.
        extra_dir = Path(extra_no_tumor_dir).resolve()
        for path in sorted(p for p in extra_dir.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES):
            records.append({'path': path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path), 'class_name': 'no_tumor', 'class_index': CLASS_NAMES.index('no_tumor'), 'sha256': sha256_file(path), 'source_split': 'Extra'})
    near_duplicates = 0
    if extra_class_dir is not None:
        # External labelled slices (class folders + optional index.json of patient ids): training pool only.
        extra_root = Path(extra_class_dir).resolve()
        patients_path = extra_root / 'index.json'
        patients = json.loads(patients_path.read_text()) if patients_path.exists() else {}
        test_hashes = [perceptual_hash(root / r['path']) for r in records if r['source_split'] == 'Testing']
        for index, name in enumerate(CLASS_NAMES):
            folder = extra_root / name
            for path in sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES) if folder.is_dir() else []:
                phash = perceptual_hash(path)
                if any(bin(phash ^ other).count('1') <= NEAR_DUPLICATE_BITS for other in test_hashes):
                    near_duplicates += 1
                    continue
                records.append({'path': str(path), 'class_name': name, 'class_index': index, 'sha256': sha256_file(path), 'source_split': 'Extra', 'patient': patients.get(f'{name}/{path.name}')})
    groups = defaultdict(list)
    for record in records:
        groups[record['sha256']].append(record)
    conflicts = [group for group in groups.values() if len({r['class_index'] for r in group}) > 1]
    if conflicts:
        raise ValueError(f'Dataset has {len(conflicts)} duplicate groups with conflicting class labels')
    excluded = {'training_duplicates': 0, 'testing_duplicates': 0, 'test_overlap': 0, 'extra_near_test_duplicates': near_duplicates}
    excluded_records = []
    training, test = [], []
    for group in groups.values():
        testing = [r for r in group if r['source_split'] == 'Testing']
        train = [r for r in group if r['source_split'] != 'Testing']
        if testing:
            test.append(testing[0])
            excluded['testing_duplicates'] += len(testing) - 1
            excluded['test_overlap'] += len(train)
            excluded_records.extend(dict(r, reason='testing_duplicate') for r in testing[1:])
            excluded_records.extend(dict(r, reason='test_overlap') for r in train)
        else:
            retained = train[0]
            if cluster_validation:
                # Exact copies can carry additional patient IDs or aliases.
                # Preserve every link even when the retained original has none.
                patient_ids = sorted({r['patient'] for r in train if r.get('patient')})
                if patient_ids:
                    retained = dict(retained, patients=patient_ids)
            training.append(retained)
            excluded['training_duplicates'] += len(train) - 1
            excluded_records.extend(dict(r, reason='training_duplicate') for r in train[1:])
    if cluster_validation:
        train, validation, grouping = _clustered_validation_split(training, root, seed, validation_fraction)
        return {'schema_version': 1, 'dataset_dir': str(root), 'seed': seed, 'validation_fraction': validation_fraction, 'classes': CLASS_NAMES, 'train': train, 'validation': validation, 'test': sorted(test, key=lambda r: r['path']), 'excluded': excluded, 'excluded_records': excluded_records, 'validation_grouping': grouping, 'limitation': 'Training/validation keep perceptually similar images and supplied patient IDs together. Test folder unchanged. Perceptual hashing is heuristic; absent patient IDs prevent establishing patient-disjoint evaluation.'}
    train, validation = [], []
    rng = random.Random(seed)
    for index in range(4):
        candidates = sorted((r for r in training if r['class_index'] == index), key=lambda r: r['path'])
        if len(candidates) < 2 or not any(r['class_index'] == index for r in test):
            raise ValueError(f'Insufficient unique examples for class {CLASS_NAMES[index]}')
        # Whole patients (or single images when no patient id exists) move together.
        units = defaultdict(list)
        for r in candidates:
            units[r.get('patient') or r['sha256']].append(r)
        keys = sorted(units)
        if len(keys) < 2:
            raise ValueError(f'Insufficient unique examples for class {CLASS_NAMES[index]}')
        rng.shuffle(keys)
        target = max(1, min(len(candidates) - 1, round(len(candidates) * validation_fraction)))
        chosen = []
        for key in keys[:-1]:
            if len(chosen) >= target:
                break
            chosen.extend(units[key])
        chosen_ids = {id(r) for r in chosen}
        validation.extend(chosen)
        train.extend(r for r in candidates if id(r) not in chosen_ids)
    return {'schema_version': 1, 'dataset_dir': str(root), 'seed': seed, 'validation_fraction': validation_fraction, 'classes': CLASS_NAMES, 'train': train, 'validation': validation, 'test': sorted(test, key=lambda r: r['path']), 'excluded': excluded, 'excluded_records': excluded_records, 'limitation': 'Hash-disjoint image splits; patient identifiers are unavailable, so patient-disjoint evaluation cannot be established.'}


def _image_files(folder):
    folder = Path(folder)
    return sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES) if folder.is_dir() else []


def _near_duplicate_pairs(hashes, max_bits=NEAR_DUPLICATE_BITS):
    values = np.asarray(hashes, dtype=np.uint64)
    for i in range(len(values) - 1):
        bits = np.unpackbits((values[i] ^ values[i + 1:]).view(np.uint8).reshape(-1, 8), axis=1).sum(axis=1)
        for j in np.nonzero(bits <= max_bits)[0]:
            yield i, i + 1 + int(j)


def _clustered_validation_split(records, root, seed, fraction):
    """Hold out whole connected components, including links across class labels.

    Hash distance is an image-similarity heuristic, not patient identification.
    Test images are deliberately absent from grouping and split selection.
    """
    records = sorted(records, key=lambda r: r['path'])
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)

    patients = {}
    for i, record in enumerate(records):
        patient_ids = set(record.get('patients', []))
        if record.get('patient'):
            patient_ids.add(record['patient'])
        for patient in sorted(patient_ids):
            union(i, patients.setdefault(patient, i))
    hashes = [perceptual_hash(root / r['path']) for r in records]
    for i, j in _near_duplicate_pairs(hashes, CLUSTER_BITS):
        union(i, j)
    groups = defaultdict(list)
    for i, record in enumerate(records):
        groups[find(i)].append(record)
    clusters = list(groups.values())
    random.Random(seed).shuffle(clusters)
    totals = Counter(r['class_index'] for r in records)
    targets = {c: max(1, round(totals[c] * fraction)) for c in range(len(CLASS_NAMES))}
    counts = [Counter(r['class_index'] for r in group) for group in clusters]
    held_out = Counter()
    selected = set()

    def can_hold_out(count, current=None):
        current = held_out if current is None else current
        return all(current[c] + count[c] < totals[c] for c in totals)

    def cost(count):
        return sum(((count[c] - targets[c]) / targets[c]) ** 2 for c in targets)

    def cover_classes(chosen, current):
        missing = [c for c in totals if not current[c]]
        if not missing:
            return chosen, current
        c = min(missing, key=lambda c: sum(count[c] > 0 and can_hold_out(count, current) for count in counts))
        candidates = [i for i, count in enumerate(counts) if count[c] and can_hold_out(count, current)]
        tried_supports = set()
        for i in sorted(candidates, key=lambda i: cost(current + counts[i])):
            # Components with the same class support are interchangeable for
            # feasibility. Try the best cost first; at most 15 supports exist.
            support = frozenset(counts[i])
            if support in tried_supports:
                continue
            tried_supports.add(support)
            result = cover_classes(chosen | {i}, current + counts[i])
            if result is not None:
                return result
        return None

    # Backtrack to cover every class without exhausting any training class.
    # Whole components take precedence over exact split sizes.
    coverage = cover_classes(set(), Counter())
    if coverage is None:
        raise ValueError('Cannot create class-complete train/validation splits without breaking clusters')
    selected, held_out = coverage
    for i, count in enumerate(counts):
        if i not in selected and can_hold_out(count) and cost(held_out + count) < cost(held_out):
            selected.add(i)
            held_out.update(count)
    train, validation = [], []
    for i, group in enumerate(clusters):
        cluster_id = min(r['sha256'] for r in group)
        destination = validation if i in selected else train
        destination.extend(dict(r, validation_cluster=cluster_id) for r in group)
    if any({r['class_index'] for r in split} != set(range(len(CLASS_NAMES))) for split in (train, validation)):
        raise ValueError('Insufficient class coverage after cluster split')
    summary = {'method': 'connected_components_dhash_and_patient', 'max_hash_distance': CLUSTER_BITS,
               'clusters': len(clusters), 'largest_cluster': max(map(len, clusters)),
               'cross_label_clusters': sum(len(count) > 1 for count in counts),
               'class_counts': {s: {CLASS_NAMES[c]: sum(r['class_index'] == c for r in rows) for c in targets}
                                for s, rows in (('train', train), ('validation', validation))}}
    return sorted(train, key=lambda r: r['path']), sorted(validation, key=lambda r: r['path']), summary


def build_pooled_manifest(dataset_dir, seed=42, test_fraction=.15, validation_fraction=.15, extra_no_tumor_dir=None, extra_class_dir=None):
    """Pool every source and hold out whole near-duplicate/patient clusters.

    The Kaggle folders carry no patient ids, so neighbouring slices of one patient
    can still fall on both sides of the split; scores from this protocol are optimistic.
    """
    root = Path(dataset_dir).resolve()
    records = []
    for split in ('Training', 'Testing'):
        for index, name in enumerate(CLASS_NAMES):
            for path in _image_files(root / split / name):
                records.append({'path': path.relative_to(root).as_posix(), 'class_name': name, 'class_index': index, 'source_split': split, 'patient': None})
    if extra_no_tumor_dir is not None:
        for path in _image_files(extra_no_tumor_dir):
            records.append({'path': str(path.resolve()), 'class_name': 'no_tumor', 'class_index': CLASS_NAMES.index('no_tumor'), 'source_split': 'Extra', 'patient': None})
    if extra_class_dir is not None:
        extra_root = Path(extra_class_dir).resolve()
        patients_path = extra_root / 'index.json'
        patients = json.loads(patients_path.read_text()) if patients_path.exists() else {}
        for index, name in enumerate(CLASS_NAMES):
            for path in _image_files(extra_root / name):
                records.append({'path': str(path), 'class_name': name, 'class_index': index, 'source_split': 'Extra', 'patient': patients.get(f'{name}/{path.name}')})
    by_hash, unique, duplicates = {}, [], 0
    for record in records:
        path = root / record['path']
        record['sha256'] = sha256_file(path)
        seen = by_hash.get(record['sha256'])
        if seen is None:
            by_hash[record['sha256']] = record
            unique.append(record)
        elif seen['class_index'] != record['class_index']:
            raise ValueError('Dataset has duplicate images with conflicting class labels')
        else:
            duplicates += 1
    parent = list(range(len(unique)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)

    first_of_patient = {}
    for i, record in enumerate(unique):
        if record['patient']:
            union(i, first_of_patient.setdefault(record['patient'], i))
    for i, j in _near_duplicate_pairs([perceptual_hash(root / r['path']) for r in unique], CLUSTER_BITS):
        if unique[i]['class_index'] == unique[j]['class_index']:
            union(i, j)
    clusters = defaultdict(list)
    for i, record in enumerate(unique):
        clusters[find(i)].append(record)
    keys = sorted(clusters, key=lambda k: min(r['path'] for r in clusters[k]))
    random.Random(seed).shuffle(keys)
    totals = Counter(r['class_index'] for r in unique)
    if set(totals) != set(range(len(CLASS_NAMES))):
        raise ValueError('Dataset must include all four classes')
    splits = {'test': [], 'validation': [], 'train': []}
    filled = {'test': Counter(), 'validation': Counter()}
    targets = {'test': {c: max(1, round(n * test_fraction)) for c, n in totals.items()}, 'validation': {c: max(1, round(n * validation_fraction)) for c, n in totals.items()}}
    for key in keys:
        members = clusters[key]
        classes = {r['class_index'] for r in members}
        for name in ('test', 'validation'):
            if any(filled[name][c] < targets[name][c] for c in classes):
                splits[name].extend(members)
                filled[name].update(r['class_index'] for r in members)
                break
        else:
            splits['train'].extend(members)
    for name, rows in splits.items():
        if {r['class_index'] for r in rows} != set(range(len(CLASS_NAMES))):
            raise ValueError(f'Pooled {name} split is missing a class')
    biggest = max(len(m) for m in clusters.values())
    return {'schema_version': 1, 'protocol': 'pooled', 'dataset_dir': str(root), 'seed': seed, 'validation_fraction': validation_fraction, 'test_fraction': test_fraction, 'classes': CLASS_NAMES, 'train': sorted(splits['train'], key=lambda r: r['path']), 'validation': sorted(splits['validation'], key=lambda r: r['path']), 'test': sorted(splits['test'], key=lambda r: r['path']), 'excluded': {'exact_duplicates': duplicates, 'clusters': len(clusters), 'largest_cluster': biggest}, 'excluded_records': [], 'limitation': 'Pooled random hold-out of near-duplicate/patient clusters. Kaggle images have no patient ids, so same-patient slices may span splits; scores are optimistic and not comparable to the Testing-folder protocol.'}


def balanced_class_weights(labels):
    counts = Counter(int(label) for label in labels)
    if set(counts) != set(range(4)):
        raise ValueError('Training subset must include all four classes')
    total = sum(counts.values())
    return {index: total / (4 * counts[index]) for index in range(4)}

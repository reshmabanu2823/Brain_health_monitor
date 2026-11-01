"""Import versioned model artifacts and provenance without source application code."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .preprocessing import CONTRACTS
from .service import CLASSES

FILES = ('brain_tumor_model.tflite','best_model.h5','class_indices.json')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def in_commit(repository, revision, paths):
    for path in paths:
        relative = str(path.relative_to(repository))
        committed = subprocess.run(['git','-C',str(repository),'rev-parse','--verify',f'{revision}:{relative}'],
                                   capture_output=True,text=True)
        local = subprocess.check_output(['git','-C',str(repository),'hash-object',str(path)],text=True).strip()
        if committed.returncode or committed.stdout.strip() != local:
            return False
    return True


def import_bundle(repository: Path, subdirectory: str, output: Path):
    repository, output = Path(repository).resolve(), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError('Output exists; choose a new model version directory')
    source = (repository/subdirectory).resolve()
    if not source.is_relative_to(repository) or source == repository:
        raise ValueError('Artifact path must stay inside source repository')
    for name in FILES:
        if not (source/name).is_file():
            raise ValueError('Missing required model artifact: '+name)
    mapping = json.loads((source/'class_indices.json').read_text())
    if mapping != dict(zip(CLASSES,range(4))) or any(type(value) is not int for value in mapping.values()):
        raise ValueError('Unsupported source class contract')
    candidate = str(source.relative_to(repository)) != 'model'
    metadata_path = source/'metadata.json'
    if candidate and not metadata_path.is_file():
        raise ValueError('Candidate requires explicit source metadata')
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    if metadata_path.is_file() and (not isinstance(metadata,dict)
                     or type(metadata.get('schema_version')) is not int or metadata.get('schema_version') != 1
                     or metadata.get('preprocessing') not in CONTRACTS
                     or metadata.get('image_size') != [224,224] or metadata.get('classes') != CLASSES
                     or metadata.get('output') != 'probabilities'):
        raise ValueError('Unsupported source model contract')
    hashes = {name:sha256(source/name) for name in FILES}
    if metadata:
        for name in FILES[:2]:
            if metadata.get('artifact_hashes',{}).get(name) != hashes[name]:
                raise ValueError('Source artifact integrity mismatch: '+name)
    revision = subprocess.check_output(['git','-C',str(repository),'rev-parse','HEAD'],text=True).strip()
    training = metadata.get('training',{})
    manifest = dict(source='https://github.com/reshmabanu2823/Brain_health_monitor',source_commit=revision,
                    source_artifact_subdirectory=str(source.relative_to(repository)),
                    source_artifacts_in_commit=in_commit(repository,revision,[source/name for name in FILES]),
                    source_metadata_sha256=sha256(metadata_path) if metadata else None,
                    architecture=training.get('backbone','Unspecified four-class classifier') if metadata else
                                 'MobileNetV2 feature extractor, global average pooling, dense classifier',
                    preprocessing=metadata.get('preprocessing','legacy_rgb_0_1'),input_shape=[1,224,224,3],
                    classes=CLASSES,artifact_hashes=hashes,experimental_candidate=candidate,
                    limitations=['Four-class image classifier only; not lesion segmentation or general brain-health diagnosis.',
                                 'No verified clinical performance or out-of-distribution rejection. Scores are not calibrated clinical confidence.'])
    if candidate:
        experiment = source/'experiment.json'
        experiment_record = json.loads(experiment.read_text()) if experiment.exists() else {}
        expected_manifest = experiment_record.get('manifest_sha256')
        source_manifest = source/'manifest.json'
        choices = [source_manifest,source/'evaluation-manifest.json']
        dataset_manifest = next((path for path in choices if path.is_file()
                                 and expected_manifest and sha256(path) == expected_manifest),
                                source_manifest if source_manifest.exists() else None)
        selected_hash = sha256(dataset_manifest) if dataset_manifest else None
        matched = selected_hash == expected_manifest if expected_manifest else None
        manifest['training_provenance'] = dict(training_metadata=training,
            dataset_manifest_file=dataset_manifest.name if dataset_manifest else None,
            dataset_manifest_sha256=selected_hash,
            dataset_manifest_matches_experiment=matched,
            source_manifest_sha256=sha256(source_manifest) if source_manifest.exists() else None,
            experiment_sha256=sha256(experiment) if experiment.exists() else None,
            source_promoted=experiment_record.get('promoted'))
        manifest['limitations'] += [
            'Experimental source candidate. Recorded image grouping does not prove cross-source patient independence.',
            'The repository test set has been reused during development; benchmark gains are not independent clinical validation.']
        if matched is False:
            manifest['limitations'].append('Cannot verify training manifest against recorded source experiment; training lineage is unverified.')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cortia-import-',dir=output.parent) as temporary:
        staging = Path(temporary)/'bundle';staging.mkdir()
        for name in FILES:
            shutil.copyfile(source/name,staging/name)
            if sha256(staging/name) != hashes[name]:
                raise ValueError('Source changed during import; integrity check failed')
        (staging/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        if output.exists() or output.is_symlink():
            raise FileExistsError('Output appeared during import')
        staging.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Local Brain_health_monitor repository')
    parser.add_argument('--artifact-subdir',default='model')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[3]/'models/mri')
    args = parser.parse_args()
    manifest = import_bundle(args.source,args.artifact_subdir,args.output)
    print(json.dumps(dict(output=str(args.output),preprocessing=manifest['preprocessing'],
                         experimental_candidate=manifest['experimental_candidate'],
                         source_artifacts_in_commit=manifest['source_artifacts_in_commit']),indent=2))


if __name__ == '__main__':
    main()

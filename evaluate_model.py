"""Evaluate existing model artifacts on the deduplicated test partition."""
import argparse
import json
from pathlib import Path
from app.dataset import build_manifest
from app.evaluation import evaluate_artifacts, write_json


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-dir', type=Path, default=root / 'dataset')
    parser.add_argument('--model-dir', type=Path, default=root / 'model')
    parser.add_argument('--output', type=Path, default=root / 'evaluation' / 'bundled-evaluation.json')
    parser.add_argument('--manifest', type=Path, default=None, help='Evaluate on the test split of a saved manifest (e.g. a candidate manifest.json)')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--tflite-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text()) if args.manifest else build_manifest(args.dataset_dir, args.seed)
    report = evaluate_artifacts(args.model_dir, args.dataset_dir, manifest, not args.tflite_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    write_json(args.output.with_name(args.output.stem + '-manifest.json'), manifest)
    print(f"Evaluated {report['tflite']['sample_count']} unique test images; accuracy {report['tflite']['accuracy']:.2%}; macro F1 {report['tflite']['macro_f1']:.4f}")
    print(f'Report: {args.output}')


if __name__ == '__main__':
    main()

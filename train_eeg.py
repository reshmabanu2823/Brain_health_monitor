"""Train experimental single-channel EEG baselines from an explicit manifest."""
import argparse
import json
from pathlib import Path
from app.eeg.training import train

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    result=train(args.manifest,args.output_dir)
    print(json.dumps({'selected':result['selected'],'test':result['test'],'baseline_test':result['baseline_test']},indent=2))

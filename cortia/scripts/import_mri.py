"""Command wrapper; imports model artifacts only, with explicit contracts and hashes."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from cortia.mri.importer import main

if __name__ == '__main__':
    main()

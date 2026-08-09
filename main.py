import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app'))

from app import launch

if __name__ == "__main__":
    print("=" * 50)
    print("   BRAIN TUMOR DETECTION SYSTEM")
    print("   Starting application...")
    print("=" * 50)
    launch()

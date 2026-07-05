import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import main

if __name__ == "__main__":
    sys.argv.append("--mode")
    sys.argv.append("editor")
    main()

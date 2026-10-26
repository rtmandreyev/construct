"""construct command line (Hermes optional skill). Run by absolute path from any folder."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
main = importlib.import_module("construct_hologram.__main__").main

if __name__ == "__main__":
    sys.exit(main())

"""Portable stdio entrypoint. Run by absolute path from any working directory."""
from pathlib import Path
import importlib
import sys

# the package is this folder, whatever it is called
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
main = importlib.import_module(Path(__file__).resolve().parent.name + ".mcp_server").main

if __name__ == "__main__":
    main()

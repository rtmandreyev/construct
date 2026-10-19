"""Portable stdio entrypoint. Run by absolute path from any working directory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hologram.mcp_server import main

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Thin compatibility shim for running w2r from source checkout."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from w2r.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

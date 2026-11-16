#!/usr/bin/env python3
"""Isolated-mode launcher: puts the repo on sys.path, then runs samplekit.

Invoked as:  python3 -I tools/run_samplekit.py --root ... build ...
The -I flag keeps site packages and caller-controlled environment variables
out of the interpreter; only the repository path computed from this file is
added.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from samplekit.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

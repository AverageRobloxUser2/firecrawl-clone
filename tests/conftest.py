"""Pytest configuration."""

import sys
import pathlib

# ensure src/ is on the path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

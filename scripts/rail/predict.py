"""Compatibility CLI using the canonical frozen RAIL bundle (no training)."""
from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    script = Path(__file__).resolve().parents[1] / "predict.py"
    sys.argv = [str(script), "--subsystem", "rail", *sys.argv[1:]]
    runpy.run_path(str(script), run_name="__main__")

"""Explicit default deployment; historical results remain immutable archives."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN = ROOT / "outputs/combined/architecture-audit-final"

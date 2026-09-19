"""Bind frozen artifacts to the exact inference dependencies that produced them."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = {"door.joblib", "rail.joblib", "acv.pkl", "shm.joblib", "shm.json"}


def inference_fingerprint():
    paths = []
    for subsystem in ("door", "acv", "rail", "shm"):
        paths.extend((ROOT / "src/railpulse" / subsystem).glob("*.py"))
    paths.extend(ROOT / "src/railpulse/core" / name for name in
                 ("inference.py", "predictions.py", "data_validation.py", "bundle_contract.py"))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}

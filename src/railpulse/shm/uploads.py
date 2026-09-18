"""Application adapter using the identical frozen inference and export path as the CLI."""
from pathlib import Path
from tempfile import TemporaryDirectory

from .pipeline import analyse_shm, load_artifact, write_predictions


def analyse_uploads(files: list[tuple[str, bytes]], artifact_path):
    names = [name for name, _ in files]
    if not names or len(set(names)) != len(names):
        raise ValueError("Upload at least one recording with unique filenames")
    if any(Path(name).name != name or "/" in name or "\\" in name or not name.lower().endswith(".csv") for name in names):
        raise ValueError("Upload filenames must be plain CSV basenames")
    artifact = load_artifact(artifact_path)
    with TemporaryDirectory(prefix="railpulse-shm-") as directory:
        root = Path(directory)
        results = []
        for name, content in files:
            path = root / name
            path.write_bytes(content)
            results.append(analyse_shm(path, artifact=artifact))
        output = root / "submission" / "shm_predictions.csv"
        write_predictions(output, results, names)
        return results, output.read_bytes()


"""Download only SHM assets from a pinned organiser commit, verifying Git blob hashes."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

REPOSITORY = "aochinwen/NebulaX-Hackathon-ProblemStatement"
COMMIT = "966c976005db2e3e40a691cff268fdb8f396a5df"
ROOT = Path(__file__).resolve().parents[2]


def fetch(url: str) -> bytes:
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={"User-Agent": "RailPulse-SHM"}), timeout=120) as response:
                return response.read()
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Unreachable")


def blob_hash(content: bytes) -> str:
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    tree = json.loads(fetch(f"https://api.github.com/repos/{REPOSITORY}/git/trees/{COMMIT}?recursive=1"))
    targets = []
    for item in tree["tree"]:
        source = item["path"]
        if item["type"] != "blob":
            continue
        if source.startswith("PS3/02_Datasets/SHM/"):
            destination = "data/SHM/" + source.removeprefix("PS3/02_Datasets/SHM/")
        elif source == "PS3/03_References/SHM/SHM_Info_Kit.md":
            destination = "references/SHM/SHM_Info_Kit.md"
        elif source == "PS3/01_Problem_Statement_3_Specifications.md":
            destination = "references/SHM/Problem_Statement_3_Specifications.md"
        elif source == "PS3/04_Example_Submission/shm_predictions.csv":
            destination = "references/SHM/example_shm_predictions.csv"
        else:
            continue
        targets.append((item, destination))

    def download(target):
        item, destination = target
        path = args.root / destination
        if path.exists():
            content = path.read_bytes()
            if blob_hash(content) != item["sha"]:
                raise ValueError(f"Existing file differs from pinned source; refusing overwrite: {path}")
        else:
            content = fetch(f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/{item['path']}")
            if blob_hash(content) != item["sha"]:
                raise ValueError(f"Download integrity failure: {item['path']}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        print(f"Verified {destination}", flush=True)
        return {"path": destination, "bytes": len(content), "git_blob_sha1": item["sha"],
                "sha256": hashlib.sha256(content).hexdigest()}

    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest = list(pool.map(download, targets))
    provenance = args.root / "references/SHM/source_manifest.json"
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps({"repository": REPOSITORY, "commit": COMMIT,
                                     "files": manifest}, indent=2) + "\n")


if __name__ == "__main__":
    main()

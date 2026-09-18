"""Explicitly rebuild the reviewed dataset inventory after changing data_sources.json."""
from pathlib import Path
import argparse
import json
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/data_sources.json")
    parser.add_argument("--output", type=Path, default=ROOT / "configs/dataset_lock.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    url = f"https://api.github.com/repos/{config['repository']}/git/trees/{config['commit']}?recursive=1"
    with urlopen(Request(url, headers={"User-Agent": "RailPulse-data-preparation"}), timeout=60) as response:
        tree = json.load(response)
    if tree.get("truncated"):
        raise ValueError("GitHub returned an incomplete inventory")
    files = []
    for item in tree["tree"]:
        if item["type"] != "blob":
            continue
        source = item["path"]
        destination = subsystem = None
        if source == "PS3/01_Problem_Statement_3_Specifications.md":
            destination, subsystem = "references/Problem_Statement_3_Specifications.md", "shared"
        for key, spec in config["subsystems"].items():
            raw_prefix = f"PS3/02_Datasets/{spec['source']}/"
            reference_prefix = f"PS3/03_References/{spec['source']}/"
            if source.startswith(raw_prefix):
                destination, subsystem = f"data/{spec['destination']}/" + source.removeprefix(raw_prefix), key
            elif source.startswith(reference_prefix):
                destination, subsystem = f"references/{spec['source']}/" + source.removeprefix(reference_prefix), key
            elif source == f"PS3/04_Example_Submission/{key}_predictions.csv":
                destination, subsystem = f"examples/{key}_predictions.csv", key
        if destination:
            if item["mode"] not in ("100644", "100755"):
                raise ValueError(f"Unexpected source file mode: {source}")
            files.append({"subsystem": subsystem, "source": source, "path": destination,
                          "bytes": item["size"], "git_blob_sha1": item["sha"]})
    if not files:
        raise ValueError("No dataset assets found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"version": 1, **config, "files": sorted(files, key=lambda f: f['path'])}, indent=2) + "\n")
    print(f"Locked {len(files)} files ({sum(f['bytes'] for f in files):,} bytes) at {config['commit']}")


if __name__ == "__main__":
    main()

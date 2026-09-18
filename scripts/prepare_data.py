"""Download and validate pinned Door, ACV, Rail and SHM datasets in their expected locations."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "src"))
from railpulse.core.data_preparation import load_lock, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subsystem", nargs="+", choices=["all", "door", "acv", "rail", "shm"], default=["all"])
    parser.add_argument("--root", type=Path, default=ROOT, help="Destination project root (must exist)")
    parser.add_argument("--lock", type=Path, default=ROOT / "configs/dataset_lock.json")
    parser.add_argument("--workers", type=int, default=4)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true", help="Offline integrity/schema verification; no writes")
    mode.add_argument("--plan", action="store_true", help="Offline preview of missing bytes and conflicts; no writes")
    args = parser.parse_args()
    try:
        if not args.root.is_dir():
            raise ValueError("Destination root must be an existing directory")
        prepare(args.root, load_lock(args.lock), args.subsystem, verify_only=args.verify_only,
                plan=args.plan, workers=args.workers)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Data preparation failed: {exc}\n")


if __name__ == "__main__":
    main()

"""Reproducible, non-overwriting dataset preparation using a checked-in inventory."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

CHUNK = 1024 * 1024


def safe_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if not relative or parts.is_absolute() or ".." in parts.parts or "\\" in relative:
        raise ValueError(f"Unsafe inventory path: {relative}")
    path = root
    for part in parts.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Symlink destinations are unsupported: {path}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes dataset root: {relative}")
    return path


def load_lock(path: Path) -> dict:
    lock = json.loads(path.read_text())
    if lock.get("version") != 1 or not re.fullmatch(r"[0-9a-f]{40}", lock.get("commit", "")):
        raise ValueError("Expected a version-1 inventory pinned to a full commit SHA")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", lock.get("repository", "")):
        raise ValueError("Invalid repository name")
    paths = set()
    for entry in lock["files"]:
        if entry["path"] in paths or not re.fullmatch(r"[0-9a-f]{40}", entry["git_blob_sha1"]):
            raise ValueError("Duplicate destination or invalid source hash")
        if not isinstance(entry["bytes"], int) or entry["bytes"] < 0:
            raise ValueError("Invalid source size")
        if entry["subsystem"] not in {*lock["subsystems"], "shared"}:
            raise ValueError("Unknown subsystem in inventory")
        for name in ("path", "source"):
            p = PurePosixPath(entry[name])
            if p.is_absolute() or ".." in p.parts or "\\" in entry[name]:
                raise ValueError("Unsafe path in inventory")
        paths.add(entry["path"])
    if not paths:
        raise ValueError("Empty dataset inventory")
    return lock


def fingerprints(path: Path) -> dict:
    size = path.stat().st_size
    blob = hashlib.sha1(f"blob {size}\0".encode())
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            blob.update(block)
            sha256.update(block)
    return {"bytes": size, "git_blob_sha1": blob.hexdigest(), "sha256": sha256.hexdigest()}


def inspect_files(root: Path, entries: list[dict]) -> list[dict]:
    results = []
    for entry in entries:
        path = safe_path(root, entry["path"])
        if not path.exists():
            results.append({**entry, "status": "missing"})
            continue
        if not path.is_file():
            raise ValueError(f"Expected a regular file: {path}")
        actual = fingerprints(path)
        status = "verified" if all(actual[k] == entry[k] for k in ("bytes", "git_blob_sha1")) else "modified"
        if status == "modified" and path.suffix.lower() in (".csv", ".md", ".txt"):
            # Git checkouts can change CRLF to LF. Only accept if that conversion
            # alone reproduces the exact locked source bytes/hash; never rewrite.
            data = path.read_bytes().replace(b"\r\n", b"\n")
            # Some official CSVs use LF for the header and CRLF for records.
            # Git normalizes those too; accept only an exact locked hash match.
            header, separator, body = data.partition(b"\n")
            variants = (data, data.replace(b"\n", b"\r\n"),
                        header + separator + body.replace(b"\n", b"\r\n"),
                        header + (b"\r\n" if separator else b"") + body)
            for variant in variants:
                digest = hashlib.sha1(f"blob {len(variant)}\0".encode() + variant).hexdigest()
                if len(variant) == entry["bytes"] and digest == entry["git_blob_sha1"]:
                    status = "verified_line_endings"
                    break
        results.append({**entry, "status": status, "actual": actual})
    return results


def download_file(root: Path, entry: dict, lock: dict, opener=urlopen) -> dict:
    destination = safe_path(root, entry["path"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://raw.githubusercontent.com/{lock['repository']}/{lock['commit']}/{quote(entry['source'], safe='/')}"
    for attempt in range(4):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".download-", delete=False) as handle:
                temporary = Path(handle.name)
                with opener(Request(url, headers={"User-Agent": "RailPulse-data-preparation"}), timeout=90) as response:
                    received = 0
                    while block := response.read(CHUNK):
                        received += len(block)
                        if received > entry["bytes"]:
                            raise ValueError(f"Download exceeds locked size: {entry['path']}")
                        handle.write(block)
                handle.flush()
                os.fsync(handle.fileno())
            actual = fingerprints(temporary)
            if any(actual[k] != entry[k] for k in ("bytes", "git_blob_sha1")):
                raise ValueError(f"Downloaded content failed integrity check: {entry['path']}")
            safe_path(root, entry["path"])
            # Atomic publication without replacing a file created by another process.
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if fingerprints(destination) != actual:
                    raise ValueError(f"Destination changed during download; preserved: {destination}")
            return {**entry, "status": "verified", "actual": actual}
        except (OSError, HTTPError) as exc:
            if attempt == 3 or isinstance(exc, HTTPError) and exc.code in (401, 403, 404):
                raise
            time.sleep(2 ** attempt)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    raise RuntimeError("Unreachable")


def prepare(root: Path, lock: dict, subsystems: list[str], *, verify_only=False, plan=False, workers=4) -> dict:
    root = root.resolve()
    selected = list(lock["subsystems"]) if "all" in subsystems else list(dict.fromkeys(subsystems))
    if not selected or any(key not in lock["subsystems"] for key in selected):
        raise ValueError("Unknown or empty subsystem selection")
    if not 1 <= workers <= 8:
        raise ValueError("Use between 1 and 8 download workers")
    entries = [entry for entry in lock["files"] if entry["subsystem"] in [*selected, "shared"]]
    state = inspect_files(root, entries)
    missing = [r for r in state if r["status"] == "missing"]
    conflicts = [r["path"] for r in state if r["status"] == "modified"]
    summary = {"repository": lock["repository"], "commit": lock["commit"], "subsystems": selected,
               "expected_files": len(entries), "missing_files": len(missing),
               "download_bytes": sum(e["bytes"] for e in missing), "modified_files": conflicts,
               "line_ending_variants": [r["path"] for r in state if r["status"] == "verified_line_endings"]}
    print(json.dumps(summary, indent=2), flush=True)
    if plan:
        return summary
    if conflicts:
        raise ValueError("Existing files differ from the pinned source; no files were downloaded or overwritten:\n" + "\n".join(conflicts))
    if verify_only and missing:
        raise ValueError("Missing files (run without --verify-only to download):\n" + "\n".join(e["path"] for e in missing))
    if missing:
        if shutil.disk_usage(root).free < summary["download_bytes"] + 128 * CHUNK:
            raise ValueError("Insufficient disk space for missing files plus download buffers")
        completed = {entry["path"]: entry for entry in state if entry["status"].startswith("verified")}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(download_file, root, entry, lock): entry for entry in missing}
            for future in as_completed(futures):
                result = future.result()
                completed[result["path"]] = result
                print(f"Verified {len(completed)}/{len(entries)}: {result['path']}", flush=True)
        state = [completed[e["path"]] for e in entries]
    from .data_validation import validate_subsystem
    reports = {}
    for key in selected:
        print(f"Validating {key} schemas and label coverage…", flush=True)
        validation = validate_subsystem(root, key, lock["subsystems"][key], entries)
        report = {"repository": lock["repository"], "commit": lock["commit"], "subsystem": key,
                  "validation": validation,
                  "files": [{"path": r["path"], "source": r["source"], "verification": r["status"],
                             "source_git_blob_sha1": r["git_blob_sha1"], "source_bytes": r["bytes"], **r["actual"]}
                            for r in state if r["subsystem"] in (key, "shared")]}
        reports[key] = report
    # Publish manifests only after every selected subsystem passes.
    if not verify_only:
        for key, report in reports.items():
            target = safe_path(root, f"outputs/data_preparation/{key}_manifest.json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("All selected datasets passed integrity and schema validation.", flush=True)
    return reports

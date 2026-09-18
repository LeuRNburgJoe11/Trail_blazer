# Reproducible dataset preparation

The shared preparation command places the official data, documentation and example
submission schemas where RailPulse expects them. It does not train models, fit
preprocessing, clean signals or mix training and test recordings.

## Quick start

Use Python 3.11+ and install the project dependencies from `requirements.txt`.
Validation requires numpy, pandas and openpyxl. `--plan` uses only the standard
library. If using the existing local environment, substitute `.venv/bin/python`
for `python` in these commands.

```bash
# Preview missing download size and modified files without network access or writes.
python scripts/prepare_data.py --subsystem all --plan

# Fetch missing assets, validate all files, and write manifests.
python scripts/prepare_data.py --subsystem all

# Fetch only one or several subsystems.
python scripts/prepare_data.py --subsystem shm
python scripts/prepare_data.py --subsystem door acv

# Recheck content, schemas, counts and label coverage offline, with no writes.
python scripts/prepare_data.py --subsystem all --verify-only
```

Arguments also include `--root /path/to/existing/project` for another destination
and `--workers 1` through `8` (default 4). The inventory path can be supplied via
`--lock`. A nonzero exit code means the selected setup is incomplete or invalid;
the command reports missing files or conflicts. Rerunning after an interrupted
download reuses every verified completed file.

## Locations and inventory

| Subsystem | Destination | Training inputs | Test inputs | Raw download size |
|---|---|---:|---:|---:|
| Door | `data/Door/` | 1 continuous stream | 1 continuous stream | 1.57 MB |
| ACV | `data/acv/` | 6 XLSX cases | 1 XLSX case | 44.51 MB |
| Rail | `data/Rail_Corrugation/` | 272 CSV recordings | 68 CSV recordings | 5.88 GB |
| SHM | `data/SHM/` | 64 CSV recordings | 16 CSV recordings | 525.69 MB |

Labels remain alongside their subsystem's Train and Test directories. Door keeps
its existing three-file layout, including `Train_Segments_Answer.csv`. References
go under `references/{Door,ACV,Rail_Corrugation,SHM}/`, including images with their
relative paths preserved. The shared specification goes to
`references/Problem_Statement_3_Specifications.md`; the existing root-level stub is
preserved. Illustrative submission files go to `examples/*_predictions.csv` and
must not be submitted as actual model predictions.

The complete inventory contains 446 assets totalling 6,455,932,359 bytes, pinned to
organiser commit `966c976005db2e3e40a691cff268fdb8f396a5df`. Only missing files are
downloaded, with available disk space checked first. The original SHM downloader
remains available for compatibility with the validated SHM source snapshot; the
shared command is the preferred entry point for new setups.

## Integrity and safe reruns

`configs/data_sources.json` defines the source-to-destination mapping and expected
counts. `configs/dataset_lock.json` records each exact source path, destination,
byte size and Git blob hash. Normal preparation reads this checked-in inventory;
it does not query a moving branch or require the GitHub API. To intentionally
upgrade the dataset, change the full commit SHA in `data_sources.json`, run
`python scripts/lock_datasets.py`, and review the inventory diff before preparing
data. Existing conflicting data must be backed up or relocated explicitly first.
Updating the lock does not authorise overwriting local files.

Every existing asset is checked before any download starts. Substantively modified
files stop preparation and are listed; there is no force-overwrite option. Text
files altered only by Git's LF/CRLF conversion are accepted only when converting
line endings reproduces the exact locked source byte size and hash. Those files
remain untouched. Manifests distinguish exact matches from line-ending variants
and record both the original source hash and the actual local hashes. The three
existing Door CSVs have this line-ending-only difference.

Downloads stream to temporary files beside their destination, with retries for
transient network failures. They are checked for size and source hash before an
atomic, non-overwriting publication. Partial or corrupt downloads never become
dataset files. Unsafe inventory paths and symlink destinations are rejected.
Successful downloads remain usable if a later file fails; the next run resumes
from that state. No archives are unpacked and no repository clone is needed.

## Validation

Integrity checks cover every selected raw file, reference and example. Schema
validation scans the actual recordings rather than just their headers:

- Door: the 17 ordered columns, finite telemetry, valid increasing timestamps,
  unique segment IDs, valid labels/operations, and exact annotation boundaries and
  row counts within the training stream; segment overlaps are rejected.
- ACV: dynamic per-car parameter columns, eight original two-digit car IDs,
  explicit timestamps, nonempty recordings, unique labels and exact case coverage.
  Each labelled faulty car must occur in its case. Missing telemetry (including
  textual markers such as `None`, without rewriting those values) and timestamp
  order/duplicates are recorded without changing data; missing timestamps fail.
- Rail: exact order and names of all 129 channels, binary rotational sensor values,
  finite readings, 10,000 samples per recording, and valid class labels for all
  training filenames.
- SHM: one headerless finite numeric column, equal-length recordings, and positive
  finite damage labels with exact training-file coverage.

Train/test counts are checked against the inventory. Extra CSV/XLSX files in raw
folders fail validation so accidental prediction outputs cannot silently enter
training. Train/test filename overlap and identical cross-split source hashes are
rejected for the file-based tasks. The existing misplaced Rail Info Kit under
`data/Rail_Corrugation/Test/` is preserved; the canonical copy and its images are
also downloaded to the correct references directory.

Manifests are written to `outputs/data_preparation/{subsystem}_manifest.json` only
after every selected subsystem passes. They include file sizes, SHA-256 and Git
hashes, provenance, schemas, recording counts, label summaries and quality
warnings. `--verify-only` performs the same checks but does not update manifests.

New raw downloads, Python caches and temporary downloads are ignored by Git.
Previously tracked Door/ACV data are left tracked; this change does not rewrite
repository history or untrack teammates' existing files. Commit the lock,
configuration, code and manifests to share a reproducible setup without adding
the 5.9 GB Rail dataset to Git.

## Tests

```bash
python -m pytest -q tests/test_data_preparation.py
python -m pytest -q
```

Tests cover content verification, corrupted/truncated downloads, atomic publication,
concurrent destination changes, conflict preflight, read-only offline modes,
newline equivalence, path traversal/symlinks, lock validity, schema checks,
leading-zero car IDs and expected inventory mappings. Test downloads use local
in-memory responses and require no network.

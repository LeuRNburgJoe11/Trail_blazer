"""Train-only fitting, frozen four-subsystem inference, and checked packaging."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold

from .data_preparation import load_lock, prepare
from .inference import load_bundle, predict_file
from .metrics import door_iou_weighted_f1
from .predictions import csv_bytes


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def train_door(root, output):
    from railpulse.door.loader import load_stream
    from railpulse.door.pipeline import DoorModel, labelled_training_rows, predict_intervals

    directory = root / "data/Door"
    samples = load_stream(directory / "Train.csv")
    with (directory / "Train_Segments_Answer.csv").open() as handle:
        labels = list(csv.DictReader(handle))
    # Split between complete annotated cycles; no cycle straddles train/validation.
    split = int(len(labels) * 0.7)
    boundary = next(i for i, sample in enumerate(samples) if sample.timestamp == labels[split]["start_time"])
    features, targets = labelled_training_rows(samples[:boundary], directory / "Train_Segments_Answer.csv")
    holdout_model = DoorModel().fit(features, targets)
    predictions = predict_intervals(samples[boundary:], holdout_model)
    score = door_iou_weighted_f1(predictions, labels[split:])
    features, targets = labelled_training_rows(samples, directory / "Train_Segments_Answer.csv")
    if len(targets) != len(labels):
        raise ValueError("Door training segmentation does not cover every annotated cycle")
    model = DoorModel().fit(features, targets)
    if model.classifier is None:
        raise ValueError("Door classifier was not fitted")
    joblib.dump(model, output / "models/door.joblib")
    return {"protocol": "chronological first 70% cycles fit / last 30% held out",
            "iou_weighted_f1": score, "n_train_cycles": split,
            "n_validation_cycles": len(labels) - split, "n_final_fit_cycles": len(labels)}


def train_rail(root, output):
    from railpulse.rail.loader import list_recordings, load_labels, load_recording
    from railpulse.rail.side_model import RailClassifier
    from railpulse.rail.spectral_features import extract_features
    from railpulse.rail.spatial import PooledSideClassifier, extract_spatial_features

    directory = root / "data/Rail_Corrugation"
    paths = list_recordings(directory / "Train")
    labels = load_labels(directory / "Train_Labels.csv")
    if set(labels) != {path.name for path in paths}:
        raise ValueError("Rail training files and labels differ")
    features = {"extra_trees": [], "pooled_spatial": []}
    for i, path in enumerate(paths, 1):
        values = load_recording(path).values
        features["extra_trees"].append(extract_features(values))
        features["pooled_spatial"].append(extract_spatial_features(values))
        if i % 20 == 0 or i == len(paths):
            print(f"Rail training features: {i}/{len(paths)}", flush=True)
    names = [path.name for path in paths]
    targets = np.array([labels[name] for name in names])
    factories = {"extra_trees": RailClassifier, "pooled_spatial": PooledSideClassifier}
    splits = list(StratifiedKFold(5, shuffle=True, random_state=42).split(names, targets))
    report, all_oof = {}, []
    for kind, factory in factories.items():
        rows = features[kind]
        pd.DataFrame(rows, index=names).rename_axis("file_id").to_csv(output / f"rail_{kind}_train_features.csv")
        fold_scores, oof = [], [None] * len(names)
        for fold, (train, valid) in enumerate(splits):
            model = factory().fit([rows[i] for i in train], targets[train].tolist())
            predicted = model.predict([rows[i] for i in valid])
            score = f1_score(targets[valid], predicted, labels=["Normal", "Side I", "Side II"], average="macro", zero_division=0)
            fold_scores.append(float(score))
            for i, prediction in zip(valid, predicted):
                oof[i] = prediction
                all_oof.append({"model": kind, "fold": fold, "file_id": names[i],
                                "truth": targets[i], "prediction": prediction})
        report[kind] = {"mean_fold_macro_f1": float(np.mean(fold_scores)), "fold_macro_f1": fold_scores,
                        "pooled_oof_macro_f1": float(f1_score(targets, oof, average="macro"))}
        print(f"Rail {kind}: mean CV macro F1={np.mean(fold_scores):.4f}", flush=True)
    # Stable tie-break: retain the simpler existing implementation.
    winner = max(factories, key=lambda name: report[name]["mean_fold_macro_f1"])
    fitted = factories[winner]().fit(features[winner], targets.tolist())
    joblib.dump(fitted, output / "models/rail.joblib")
    pd.DataFrame(all_oof).to_csv(output / "rail_oof_predictions.csv", index=False)
    return {"selected_model": winner, "protocol": "5-fold file-level stratified CV, random_state=42",
            "candidates": report, "n_training_files": len(paths),
            "limitations": "CV used for model selection, not an unbiased post-selection estimate. Nearby recording/session grouping is unavailable; file-level CV may be optimistic."}


def evaluate_acv(root, output):
    from railpulse.acv.loader import load_acv_case
    from railpulse.acv.feature_pipeline import build_features_for_case
    from railpulse.acv.validation import evaluate_baseline_loocv

    directory = root / "data/acv"
    labels = pd.read_csv(directory / "Train_Labels.csv", dtype=str)
    label_map = dict(zip(labels.filename, labels.faulty_car))
    tables = []
    for path in sorted((directory / "Train").glob("*.xlsx")):
        print(f"ACV training features: {path.name}", flush=True)
        tables.append(build_features_for_case(load_acv_case(str(path))))
    features = pd.concat(tables, ignore_index=True)
    if set(features.case_id) != set(label_map):
        raise ValueError("ACV training feature/label coverage mismatch")
    folds = evaluate_baseline_loocv(features, label_map)
    features.to_csv(output / "acv_train_features.csv", index=False)
    folds.to_csv(output / "acv_validation.csv", index=False)
    # Retain the ACV branch's selected frozen baseline, not an unfitted fallback.
    source = root / "models/acv/acv_model_artifact.pkl"
    artifact = joblib.load(source)
    expected = ["temp_error_median", "peer_context_residual_median",
                "peer_context_longest_persistent_deviation", "active_cooling_duty_cycle"]
    if artifact.get("model_type") != "baseline" or artifact["feature_schema"] != expected:
        raise ValueError("ACV frozen model changed; reevaluate the selected model before packaging")
    if set(artifact["training_cases"]) != set(label_map):
        raise ValueError("ACV artifact training cases differ from current data")
    shutil.copy2(source, output / "models/acv.pkl")
    return {"selected_model": "frozen ACV baseline from ACV branch", "protocol": "leave-one-case-out",
            "rank_decay_score": float(folds.rank_decay_score.mean()),
            "top_1_count": int((folds.true_car_rank == 1).sum()), "n_cases": len(folds),
            "limitations": "Only six independent cases; baseline was selected using these same cases."}


def run_all(root, output, *, verify_data=True):
    root, output = Path(root).resolve(), Path(output).resolve()
    # Refuse to overwrite any earlier run, including its ZIP or trained artifacts.
    output.mkdir(parents=True, exist_ok=False)
    (output / "models").mkdir()
    started = time.perf_counter()
    summary = {"status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
               "test_labels_available": False, "validation": {}, "predictions": {}}
    try:
        summary["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        summary["git_dirty_at_start"] = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root, text=True).strip())
        summary["runtime_versions"] = {name: importlib.metadata.version(name) for name in
                                       ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "rainflow", "openpyxl")}
        summary["source_sha256"] = {str(path.relative_to(root)): sha256(path)
                                    for path in sorted((root / "src/railpulse").rglob("*.py"))
                                    if "rail/railpulse/" not in str(path.relative_to(root))}
        lock = load_lock(root / "configs/dataset_lock.json")
        summary["dataset_commit"] = lock["commit"]
        summary["dataset_lock_sha256"] = sha256(root / "configs/dataset_lock.json")
        summary["data_integrity_verified"] = verify_data
        if verify_data:
            prepare(root, lock, ["all"], verify_only=True)
        print("Fitting Door on training data…", flush=True)
        summary["validation"]["door"] = train_door(root, output)
        print("Comparing Rail models on training-only folds…", flush=True)
        summary["validation"]["rail"] = train_rail(root, output)
        print("Rechecking the selected ACV baseline…", flush=True)
        summary["validation"]["acv"] = evaluate_acv(root, output)
        for suffix in ("joblib", "json"):
            shutil.copy2(root / f"models/shm/model.{suffix}", output / f"models/shm.{suffix}")
        summary["validation"]["shm"] = {"protocol": "existing frozen SHM nested-CV report (not rerun)",
                                          "report": "outputs/shm/training_summary.json",
                                          "report_sha256": sha256(root / "outputs/shm/training_summary.json")}
        model_files = sorted((output / "models").iterdir())
        metadata = {"version": 1, "rail_model": summary["validation"]["rail"]["selected_model"],
                    "sha256": {path.name: sha256(path) for path in model_files},
                    "runtime_versions": summary["runtime_versions"]}
        write_json(output / "models/bundle.json", metadata)
        bundle = load_bundle(output / "models")
        inputs = {"door": [root / "data/Door/Test.csv"],
                  "acv": sorted((root / "data/acv/Test").glob("*.xlsx")),
                  "rail": sorted((root / "data/Rail_Corrugation/Test").glob("*.csv")),
                  "shm": sorted((root / "data/SHM/Test").glob("*.csv"))}
        for subsystem, paths in inputs.items():
            print(f"Frozen {subsystem} inference: {len(paths)} test files…", flush=True)
            if len(paths) != lock["subsystems"][subsystem]["test_files"]:
                raise ValueError(f"{subsystem}: unexpected test file count")
            frames, warnings = [], {}
            for path in paths:
                result = predict_file(subsystem, path, bundle)
                frames.append(result.frame)
                if result.warnings:
                    warnings[path.name] = result.warnings
            frame = pd.concat(frames, ignore_index=True)
            exported = csv_bytes(subsystem, frame, expected_ids=None if subsystem == "door" else [p.name for p in paths])
            target = output / f"{subsystem}_predictions.csv"
            target.write_bytes(exported)
            summary["predictions"][subsystem] = {"input_files": len(paths), "prediction_rows": len(frame),
                                                   "sha256": sha256(target), "warnings": warnings}
        for name, checksum in metadata["sha256"].items():
            if sha256(output / "models" / name) != checksum:
                raise ValueError("Inference modified a frozen artifact")
        # Publish the ZIP only after every prediction passes schema/coverage checks.
        temporary_zip = output / "predictions.zip.tmp"
        with zipfile.ZipFile(temporary_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in inputs:
                filename = f"{name}_predictions.csv"
                info = zipfile.ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, (output / filename).read_bytes())
        temporary_zip.rename(output / "predictions.zip")
        summary.update(status="complete", frozen_artifacts_unchanged=True,
                       predictions_zip_sha256=sha256(output / "predictions.zip"))
    except Exception as exc:
        summary.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        summary["elapsed_seconds"] = time.perf_counter() - started
        write_json(output / "run_summary.json", summary)
    return summary

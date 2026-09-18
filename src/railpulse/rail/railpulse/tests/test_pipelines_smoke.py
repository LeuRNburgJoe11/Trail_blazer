"""
End-to-end smoke tests. These need the actual datasets on disk and are
skipped (not failed) when they're not found -- set RAILPULSE_DOOR_DIR /
RAILPULSE_ACV_DIR to point at your local PS3/02_Datasets/{Door,ACV} folders
to run them for real, e.g.:

    RAILPULSE_DOOR_DIR=./data/Door RAILPULSE_ACV_DIR=./data/ACV pytest -v
"""
import os

import pytest

DOOR_DIR = os.environ.get("RAILPULSE_DOOR_DIR")
ACV_DIR = os.environ.get("RAILPULSE_ACV_DIR")
RAIL_FEATURE_CACHE = os.environ.get("RAILPULSE_RAIL_FEATURE_CACHE")
RAIL_LABELS = os.environ.get("RAILPULSE_RAIL_LABELS")


@pytest.mark.skipif(not DOOR_DIR, reason="set RAILPULSE_DOOR_DIR to run")
def test_door_pipeline_beats_trivial_baseline():
    from railpulse.door.loader import load_answer, load_stream
    from railpulse.door.pipeline import DoorPipeline, time_holdout_split

    stream = load_stream(f"{DOOR_DIR}/Train.csv")
    answer = load_answer(f"{DOOR_DIR}/Train_Segments_Answer.csv")
    fit_stream, held_stream, fit_answer, held_answer = time_holdout_split(stream, answer)

    pipeline = DoorPipeline()
    pipeline.fit(fit_stream, fit_answer)
    score = pipeline.evaluate(held_stream, held_answer)

    # Not a tight regression bound -- just a sanity floor so a broken
    # segmentation/feature change gets caught before it reaches the app.
    assert score > 0.5, f"held-out IoU-F1 dropped to {score:.3f}"


@pytest.mark.skipif(not ACV_DIR, reason="set RAILPULSE_ACV_DIR to run")
def test_acv_pipeline_beats_trivial_baseline():
    from railpulse.acv.pipeline import ACVPipeline

    pipeline = ACVPipeline()
    results = pipeline.leave_one_case_out(ACV_DIR, f"{ACV_DIR}/Train_Labels.csv")
    found = results[results["found"]]
    assert len(found) > 0, "no labelled cases found under RAILPULSE_ACV_DIR"
    assert found["score"].mean() > 0.5, f"mean LOCO score dropped to {found['score'].mean():.3f}"


@pytest.mark.skipif(
    not (RAIL_FEATURE_CACHE and RAIL_LABELS),
    reason="set RAILPULSE_RAIL_FEATURE_CACHE (from scripts/extract_rail_features.py) and RAILPULSE_RAIL_LABELS to run",
)
def test_rail_pipeline_beats_trivial_baseline():
    import pandas as pd

    from railpulse.rail.pipeline import RailPipeline

    cache = pd.read_csv(RAIL_FEATURE_CACHE)
    labels = pd.read_csv(RAIL_LABELS)

    pipeline = RailPipeline()
    cv_results = pipeline.evaluate_stratified_cv(cache, labels, n_splits=5)
    mean_score = cv_results["macro_f1"].mean()
    # An always-predict-Normal model scores ~0.33 per the Info Kit's own
    # worked example -- this is the floor a real pipeline must clear.
    assert mean_score > 0.4, f"mean CV macro F1 dropped to {mean_score:.3f}"

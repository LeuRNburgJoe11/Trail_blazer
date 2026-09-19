"""Read models for dashboards: coverage and review counts, never guessed test scores."""
from .scoring import SUBSYSTEMS, combined_scores


def dashboard_summary(records, expected_files=None):
    expected_files = expected_files or {}
    rows = []
    for name in SUBSYSTEMS:
        selected = [record for record in records if record["subsystem"] == name]
        files = {record["file_id"] for record in selected}
        expected = set(expected_files.get(name, []))
        rows.append({"subsystem": name, "uploaded_files": len(files), "findings": len(selected),
                     "review_required": sum(record["review_required"] for record in selected),
                     "flagged_candidates": sum(record["finding"] in ("fault_candidate", "suspected_car") for record in selected),
                     "quality_flags": sum(record["quality"] != "passed" for record in selected),
                     "expected_files": len(expected) if expected else None,
                     "missing_filenames": sorted(expected - files), "unexpected_filenames": sorted(files - expected) if expected else [],
                     "filename_coverage": "not_attempted" if not files else "unknown" if not expected else
                                          "complete" if files == expected else "partial_or_unexpected",
                     "held_out_score": None})
    attempted = [row["subsystem"] for row in rows if row["uploaded_files"]]
    return {"subsystems": rows, "scoring": combined_scores({}, attempted=attempted, basis="held_out"),
            "coverage_note": "Filename coverage only; arbitrary uploads are not automatically the official test set."}

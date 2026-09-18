"""
ACV pipeline (architecture review Section 03 + Section 07 inference
contract). The current ranker is rule-based (no fitting step) -- predict()
is the whole pipeline. Validation uses leave-one-case-out since each case
is an independent example (n=6 training cases).
"""
from __future__ import annotations

import glob
import os

import pandas as pd

from railpulse.acv.loader import load_case
from railpulse.acv.ranking import rank_cars
from railpulse.core.metrics import acv_rank_decay_score
from railpulse.core.schemas import ACVResult


class ACVPipeline:
    def predict_file(self, path: str) -> ACVResult:
        df = load_case(path)
        ranked, scores = rank_cars(df)
        return ACVResult(
            file_id=os.path.basename(path),
            ranked_cars=ranked,
            scores=scores.to_dict(),
        )

    def leave_one_case_out(self, data_dir: str, labels_path: str) -> pd.DataFrame:
        """Runs predict_file on every labelled training case and scores
        each one independently against its own disclosed faulty car --
        this IS leave-one-case-out for a rule-based (non-fitted) ranker,
        since no case's label ever informs another case's score."""
        labels = pd.read_csv(labels_path)
        labels.columns = [c.strip() for c in labels.columns]
        labels["faulty_car"] = labels["faulty_car"].astype(str).str.zfill(2)

        rows = []
        for _, row in labels.iterrows():
            matches = glob.glob(f"{data_dir}/**/{row['filename']}", recursive=True)
            if not matches:
                rows.append({"filename": row["filename"], "found": False})
                continue
            result = self.predict_file(matches[0])
            score = acv_rank_decay_score(result.ranked_cars, row["faulty_car"])
            rank = (
                result.ranked_cars.index(row["faulty_car"]) + 1
                if row["faulty_car"] in result.ranked_cars
                else None
            )
            rows.append({
                "filename": row["filename"],
                "found": True,
                "true_faulty_car": row["faulty_car"],
                "predicted_rank": rank,
                "n_cars": len(result.ranked_cars),
                "score": score,
                "ranking": "|".join(result.ranked_cars),
            })
        return pd.DataFrame(rows)

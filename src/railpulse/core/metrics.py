"""Official task evaluators."""

from railpulse.door.loader import parse_timestamp


def door_iou_weighted_f1(predictions, reference):
    """Same-label, descending-IoU greedy one-to-one matching (official metric)."""
    def interval(row):
        return parse_timestamp(row["start_time"]), parse_timestamp(row["end_time"])

    pairs = []
    for i, pred in enumerate(predictions):
        start, end = interval(pred)
        for j, truth in enumerate(reference):
            if pred.get("prediction", pred.get("status")) != truth.get("prediction", truth.get("status")):
                continue
            true_start, true_end = interval(truth)
            overlap = max(0, min(end, true_end) - max(start, true_start))
            union = end - start + true_end - true_start - overlap
            if overlap > 0 and union > 0:
                pairs.append((overlap / union, i, j))
    used_pred, used_true, credit = set(), set(), 0.0
    for value, i, j in sorted(pairs, key=lambda item: (-item[0], item[1], item[2])):
        if i not in used_pred and j not in used_true:
            used_pred.add(i)
            used_true.add(j)
            credit += value
    return 2 * credit / (len(predictions) + len(reference)) if predictions or reference else 0.0

# Rubric audit and dashboard decision layer

**Runtime update:** the [architecture audit](ARCHITECTURE_AUDIT.md) makes
`outputs/combined/architecture-audit-final/models` the default model bundle.
The first replay described below is historical; use the current bundle for
new inference. It also supports idle Door inputs without inventing an operation.

## Assessment

The existing four model pipelines support all four required scored tasks. They
do **not** justify treating everything as binary fault classification, or turning
model scores into a fleet health/safety score. This audit uses the supplied
rubric images and the checked-in official subsystem info kits as requirements
evidence, not as instructions to carry out unrelated actions.

| Subsystem | Required output/metric | Current support | Decision-layer interpretation |
|---|---|---|---|
| Door | Timed segments + Normal/Abnormal resistance; IoU-weighted F1 | Supported, including chronological end-to-end validation and three-column export | One review finding per segment; keep boundaries and original label |
| ACV | Complete native-ID ranking; linear rank decay | Supported; selected baseline reproduces 0.97917 LOCO score | Suspected top car, full ranking, raw score margin, ties/unknown evidence; never confirmed leak probability |
| Rail | Normal/Side I/Side II; macro F1 equally across all three classes | Supported; selected pooled spatial model gives 0.78764 mean fold macro F1 | Review the predicted side; Normal is not a safety clearance |
| SHM | Numeric cumulative damage; max(0, 1−MAPE) using fractional MAPE | Supported; existing frozen nested-CV score 0.97438 | Report recording damage and domain warnings; no arbitrary damage threshold, remaining life or forecast |

Door's recorded chronological holdout score is 1.000 on 33 cycles, not proof of
perfect generalisation. ACV has six cases, and Rail's CV also selected the model.
These protocols are different and may be optimistic. Test labels are unavailable.

## What was missing and has been implemented

1. **Separate decisions from scored predictions.** `core/decisions.py` wraps
   frozen inference. It does not change the model, class, ranking, damage value,
   or official CSV schema. Review-queue CSV/JSON are separate dashboard artifacts;
   do not put them inside the official `predictions.zip`.
2. **Quality gates.** Door requires ordered finite telemetry and increasing unique
   timestamps. ACV requires the native eight-car schema and timestamps, surfaces
   missing telemetry/duplicates, and rejects entirely missing telemetry. Rail/SHM
   retain their strict loaders. No Rail speed pulses trigger a review warning.
   Invalid batches do not produce official exports.
3. **Honest uncertainty.** Confidence is `null/not_calibrated`, never a fabricated
   percentage. ACV ranking scores remain explicitly uncalibrated. Tied or missing
   score evidence becomes ambiguous localisation. SHM extrapolation warnings are
   retained. Quality checks are input-contract checks, not a universal drift test.
4. **Traceable review records.** Each record has stable ID, schema/policy version,
   subsystem, filename, segment/entity identity, finding, disposition, reasons,
   evidence, warnings, review action, input SHA-256 and bundle SHA-256. Unknown
   evidence serialises as JSON `null`, not NaN/Infinity. File identities are not
   silently joined into a shared train/asset identity.
5. **Persistent dashboard state.** Evidence and review queues survive ordinary
   UI reruns. Files accumulate across batches without duplicate findings. Failed
   replacement batches invalidate that subsystem's exports and retain rejection
   diagnostics. Changing the model bundle clears stale results immediately.
6. **Exact score aggregation.** `core/scoring.py` implements fixed-three-class
   Rail macro F1, coverage-checked ACV rank decay, Overall=sum/4 and
   Average=sum/attempted. Existing Door IoU matching and SHM fraction-MAPE remain
   unchanged. Unattempted tasks contribute zero to Overall; an attempted failure
   is explicitly zero and stays in Average's denominator. Missing ground truth
   is unknown (`None`), not zero or a perfect score. Validation aggregates are
   explicitly proxy values, never presented as official held-out performance.

## Review policy (not physical severity)

| Queue priority | Meaning | Human disposition |
|---|---|---|
| 30 | Input quality not verified/degraded, or model/domain warning | Review data and applicability before using the model finding |
| 20 | Door/Rail fault-class candidate or ACV localisation | Corroborate the flagged interval, side or ranked cars |
| 10 | SHM damage estimate without approved asset-specific limits | Obtain engineering context before a maintenance decision |
| 0 | Normal model observation with passed input checks | Retain observation; not a safe-to-operate certification |

Priority numbers define deterministic queue order only. They are not calibrated
risk, urgency, severity, probability, or instructions to stop/dispatch a train.
Data rejection appears separately as a failed batch, never as a Normal prediction.

## Dashboard/API use

```bash
python -m streamlit run app/main.py
python scripts/build_decisions.py
```

The replay writes `decisions.json` and `summary.json` to a new timestamped
directory under `outputs/dashboard/`, refusing to overwrite an existing
directory. Use `--output NEW_DIRECTORY` to choose a destination. The completed
reference replay is directly under `outputs/dashboard/`. It processes all distributed test inputs, asserts that all four official
CSVs are byte-identical to the merged-main run, and records per-file evidence.
It does not retrain or retune on test inputs. Models/official CSVs are unchanged.

The completed replay produced 123 review records: 38 Door segments, one ACV
ranking, 68 Rail classifications and 16 SHM estimates. It surfaced nine Rail
recordings with no detected speed pulses, missing ACV telemetry, and the two
existing SHM training-range warnings. All four official CSVs remained
byte-identical. See `outputs/dashboard/summary.json` for coverage and hashes.

```python
from railpulse.core.inference import load_bundle
from railpulse.core.decisions import analyse_decision, decision_payload

bundle = load_bundle("outputs/combined/architecture-audit-final/models")  # trusted artifacts only
prediction, records = analyse_decision("rail", "data/Rail_Corrugation/Test/Test1.csv", bundle)
dashboard_json = decision_payload(records)
```

The UI shows subsystem coverage, findings requiring review, persistent evidence,
input/model provenance, downloadable review artifacts, and separate official
prediction downloads. Coverage means matching expected filenames, **not** proof
that arbitrary uploads are official test data. Overall/Average test scores remain
unavailable because the ground truth is held by the organisers.

## Remaining limits against the overall rubric

- Classification/ranking/regression contracts are covered, but model validation
  does not guarantee leaderboard performance.
- Forecasting and remaining useful life are **not established** by isolated
  recordings. They require longitudinal asset-linked observations, units,
  exposure/duty-cycle context, and suitable targets; inventing a forecast would
  weaken technical validity.
- Operational alert thresholds, calibrated probabilities, severity and maintenance
  deadlines need domain-approved policy and independent validation.
- The dashboard provides review support. It is not a production safety system;
  access control, durable audit/event storage, asset registry linkage and live
  monitoring remain deployment work.
- A clear demo video and usability review are still required for Ease of Use;
  backend correctness alone does not fulfil those deliverables.

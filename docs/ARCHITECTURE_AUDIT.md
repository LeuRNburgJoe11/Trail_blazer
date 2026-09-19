# End-to-end architecture audit — 19 September 2026

## Verdict

The architecture is suitable for the next **prototype integration/demo stage**
after the fixes below. It is not a production railway safety or dispatch system.
The implementation was assessed through code, counterexamples, regression tests
and training-only evaluation—not by which person or AI wrote a subsystem.

The existing raw datasets, original models and `outputs/combined/merged-main/`
reports are retained. The corrected, source-bound deployment is
`outputs/combined/architecture-audit-final/`; `core/runtime.py` selects it for
the dashboard, shared CLI, and decision replay. Historical version-1 bundles
are deliberately rejected by current integrated inference: their code semantics
are no longer guaranteed to match the corrected features.

The final full run completed in about 197 seconds. All four official prediction
CSVs remain byte-identical to the original merge run: 38 Door segments, one ACV
ranking, 68 Rail predictions and 16 SHM estimates. Correctness hardening did not
silently alter the submitted results. The refreshed dashboard replay is in
`outputs/dashboard/architecture-audit/`.
The final test suite passed **149 tests with zero warnings**, including actual
app-vs-batch prediction checks, nested split disjointness, idle Door streams,
source/runtime/artifact tampering, invalid data, and a no-training frozen CLI.

## Confirmed defects and fixes

| Area | Reproduced problem | Correction |
|---|---|---|
| ACV semantics | Grounding detection was treated as data validity | Removed unsupported equivalence; missing validity remains unknown |
| ACV data quality | Substring matching counted `Invalid` as valid | Exact known-state matching, with unknown values not fabricated as valid |
| ACV aliases | A canonical `Cooling Setpoint` column could disappear when only alias names were checked | Canonical name takes precedence, followed by documented aliases |
| ACV peer features | MAD mixed absolute residuals with the signed median; missing rows joined separate anomaly runs | Correct signed-residual MAD; missing observations break persistence |
| ACV control features | `Not cooling` matched cooling; missing timestamps were assigned a fictitious one-hour duration | Exclude negated states; unknown duration produces missing rate, not invented elapsed time |
| ACV timestamps/schema | Raw strings could sort lexicographically; no timestamp field fell back to sensor data; duplicate parameter mappings overwrote each other | Require one explicit timestamp field, parse dates, stable chronological ordering, reject duplicate mappings |
| ACV evaluation | Missing case labels could be silently skipped; standalone baseline reports could remain stale | Require exact case/car/label coverage and save current baseline folds |
| Door segmentation | Idle input produced an invented operation; advertised gap handling was unused | Activity-aware start/end detection, bridged short gaps, no operation for idle input; all 110 official training boundaries remain matched |
| Door inputs | Missing/nonfinite fields and non-increasing timestamps were not consistently rejected by standalone loading | Full documented feature columns, finite values, unique increasing timestamps |
| Door/Rail fitting | Unfitted models or missing dependencies silently produced majority/Normal predictions | Fail explicitly; validate training coverage/labels, deterministic fitted classifiers |
| Rail inputs | Duplicate labels could overwrite records; malformed blanks could be silently skipped | Reject incomplete/duplicate/invalid labels and malformed numeric samples |
| Rail evaluation | Best-candidate CV was also model-selection evidence | Add 5 outer / 3 inner file-level nested selection, retaining split logs for leakage tests |
| Model registry | Bundle checksums did not require every artifact; unknown Rail model names defaulted to another extractor; source/runtime drift was unchecked | Version-2 bundles require all five artifacts, known model kind, exact inference-source fingerprints and runtime versions before deserialization |
| Entry points | ACV CLI duplicated scoring logic; Rail `predict.py` retrained a different baseline | Shared frozen `scripts/predict.py`; ACV/Rail wrappers use the same bundle/exporter as the app |
| Reproducibility | Code could change while a combined run was building artifacts | Refuse successful publication if the canonical source snapshot changes during the run |

An idle Door stream can now legitimately export only its three-column header.
The dashboard records `no_operations_detected` rather than a fabricated healthy
cycle. It does not equate no detected operations with good equipment health.

## Model review and validation interpretation

- **Door:** Retain deterministic segmentation and Extra Trees. The corrected
  implementation preserves the official training boundaries and the 77/33
  chronological split. A perfect small holdout is not proof of generalisation.
  The effort-reset rule is dataset-specific and needs independent operational
  validation; it has not become a universal door detector.
- **ACV:** Retain the selected transparent baseline. Re-extract all six cases and
  compare it again with logistic regression, random forest, gradient boosting,
  and linear SVM using case-held-out folds and fold-local scaling. Do not replace
  a better validated baseline merely with a more complex model. Peer matching
  has progressively weaker fallbacks; descriptions must not claim every peer
  comparison always satisfies the strictest operating context.
  On corrected features the baseline scored 0.97917; the best challenger, linear
  SVM, scored 0.875. Raw operating-state encodings and the meaning of validity
  signals still need domain confirmation before a live deployment; current peer
  fallback is not proof of sensor validity.
- **Rail:** Retain the pooled side model and separate vibration/shock features.
  Odd/even position mapping, pulse decoding and wavenumber features are aligned
  with the supplied schema. Both side vectors of a file remain in the same fold.
  The selected candidate's mean macro F1 is about **0.788**, while the nested
  selection workflow scores about **0.726**. The latter is the more cautious
  selection assessment, not a newly degraded test score. Session/route grouping
  is unavailable; correlated recordings remain a limitation even with nesting.
- **SHM:** No material defect found in the active rainflow model, positive-target
  fractional-MAPE scoring, half-cycle handling, nested selection, frozen export
  or upload adapter. Preserve the established model rather than introduce
  speculative changes. Its existing nested score is **0.97438**; the full audit
  reruns inference, not expensive SHM model selection. Stress units, fatigue
  limits and service-life interpretation remain explicitly unknown.

ACV and Rail evaluation results are validation evidence on tiny/limited datasets,
not organiser-held test performance. Do not average those numbers and present
them as an official leaderboard result.

## Reproduce

```bash
python -m pip install -r requirements-all.txt
python scripts/prepare_data.py --subsystem all
python scripts/run_all.py --output outputs/combined/NEW_RUN_NAME
python -m pytest -q
python -m streamlit run app/main.py
python scripts/predict.py --subsystem rail --input data/Rail_Corrugation/Test --output NEW_rail_predictions.csv
python scripts/build_decisions.py --output outputs/dashboard/NEW_REPLAY_NAME
```

Use `--bundle NEW_RUN_NAME/models` for frozen CLI inference with a newly validated
run, or choose it in the dashboard sidebar. Existing output paths are not
overwritten. Regenerate a bundle after changing any bound inference code or
runtime dependency; changing a checksum manifest to bypass a mismatch is not a
valid migration. Pickle/joblib bundles must still come from a trusted source:
hashes detect accidental inconsistency, not malicious artifacts from an untrusted
author.

## What is still outside the completed prototype

- Independently collected validation data and calibrated probabilities.
- Confirmed physical units/maintenance limits for SHM; longitudinal targets for
  remaining-life forecasting.
- Asset identities, event time, durable audit storage, access controls and live
  data-drift monitoring for deployment.
- Better generalisation evidence for Door, more independent ACV cases, and
  session/route groups for Rail.
- The nested `src/railpulse/rail/railpulse/` tree is preserved historical work,
  **not** the active application. Its duplicated package should not be installed
  over the canonical `src/railpulse` tree.

These are explicit next-stage limitations, not reasons to fabricate confidence,
maintenance urgency, or test scores in the current dashboard.

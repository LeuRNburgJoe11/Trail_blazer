# Engineering explanation and review assistant

## Role

The assistant supports understanding results, evaluating applicability, preparing
an investigation and drafting a handover. It cannot authorise maintenance or
dispatch, approve thresholds, infer asset histories, or certify safety. Dashboard
navigation guidance remains deferred until the final dashboard is available.

Use **Instructions** above the React composer, or the similarly
named Streamlit expander. Choose a reader, level of detail and investigation focus.
Example: `Explain for a technician; define acronyms; focus on ACV missing telemetry.`

In React, click **Instructions** again, its close button, or Escape to collapse
the panel. Closing it preserves your entered values. **Sample queries** opens a
separate guide with Operational review, Model & evaluation, Terms explained and
Data limits categories. Selecting one of the 14 examples fills the composer and
closes the guide; it never sends automatically or changes the selected scope.
Each example explains its purpose and relevant limits. Review the prompt, then
press Send. Only one helper panel is expanded at a time; the close control stays
outside the scrollable content.

Supported free-text hints are explicitly listed in the answer. Audience, detail,
term definitions and quality/evaluation/review focus are recognised; a single
subsystem name can narrow an unselected scope. An explicit selected subsystem
takes precedence. Conflicts produce a warning. Other directives are not executed.
Focus only changes generic summaries/briefings, never a specific safety question.
This is bounded instruction parsing, not unrestricted natural-language automation.

Recording notes are attributed to the entered name/role **as self-reported**.
They remain `user_provided_unverified`, separate from facts, predictions and policy.
For example, “sensor disconnected after service” is not verified acquisition
metadata and does not suppress a model warning. Proposed thresholds and purported
approvals remain notes, not maintenance rules. There is no authenticated sign-off.

Instructions and notes are processed locally and are not included in the optional
LLM evidence-selection payload. The ordinary question and compact evidence still
follow the existing consent flow. Notes appear in the downloaded response JSON;
review it before sharing. No durable note database is introduced.

React notes clear on new conversation or recording/subsystem change. Presentation
preferences persist in tab memory. Each answer keeps its own input snapshot.
Streamlit notes are keyed to the evidence/scope; preference changes invalidate the
displayed answer. No notes are joined between users or inferred common assets.

## Answers and supported questions

- `How does this model work?`: input validation, feature extraction, model and output.
- `What does macro F1 mean?`: a contextual definition, rather than unrelated results.
- `What am I looking at?`: output meaning with actual selected evidence.
- `Explain validation metrics`: separates software tests, validation and input quality.
- `Prepare an inspection briefing`: review candidates, recorded quality warnings,
  verification suggestions and limitations. Human review is required.
- `Prepare a handover`: the same scoped evidence package, with attributed notes in
  its own section. It is not an approved operational instruction.
- `Compare ...`: the existing within-subsystem comparison, without a deterioration
  claim or assumption of chronological/asset linkage.

Response schema 2 retains the existing facts, citations and provenance, adding
`explanation.sections`, `engineer_input`, `next_questions`, and a hash of engineer
input. Sections explain meaning, optional backend detail, evaluation boundaries
and what to verify. Technical reader/detailed modes expose additional pipeline
steps. The renderer never turns engineer notes into cited model facts. Optional
Optional AI prose is labelled and cited; it cannot alter these local explanation
sections or canonical source cards. Citation/numeric checks are not a guarantee of
factual correctness. Verify generated wording against the evidence.

Unscoped “this model” or “this result” prompts now ask which subsystem or recording
is intended. Clarification choices can be clicked in React or entered as the next
reply. “Explain review policy” describes the rules; “Which findings need review?”
retrieves the queue. A generic “explain it” asks which use case is intended instead
of returning all four subsystem descriptions. Scope changes discard pending context.

Model mechanisms describe the reviewed implementation, with bundle-dependent
choices explicitly identified. They are not a faithful feature attribution for
an individual tree prediction or proof of a physical cause. See
[the architecture audit](ARCHITECTURE_AUDIT.md) and [SHM methodology](SHM.md).

## Glossary

- **IoU:** intersection duration divided by union duration for predicted and
  reference intervals. Door evaluation considers both timing and labels.
- **Precision:** correct positive predictions divided by positive predictions.
- **Recall:** correctly detected reference positives divided by reference positives.
- **False positive / false negative:** a class is respectively predicted in error
  or missed. Define the positive class and denominator before reporting rates.
- **F1:** harmonic mean of precision and recall, `2PR/(P+R)`, with the evaluator's
  defined handling of empty denominators. It is not accuracy.
- **Macro F1:** equal-weight average of per-class F1. Rail always uses Normal,
  Side I and Side II; the majority class cannot dominate by sample count alone.
- **MAPE:** mean absolute error relative to each reference value. Fractional 0.02
  is 2% error, not confidence. SHM score is `max(0, 1 − MAPE)`. The supplied positive
  targets do not establish an official zero-target rule.
- **Linear rank decay:** `(n − r + 1)/n` for n cars and one-based true-car rank r.
  Ranking scores do not become leak probabilities.
- **Cross-validation:** repeated fit/held-out evaluation with independent units
  kept together. ACV case rows are not independent cases.
- **Nested validation:** inner model selection within each outer training split,
  followed by evaluation on untouched outer examples. Unknown acquisition/session
  correlation remains a limitation.
- **Data leakage:** held-out information influences fitting or selection. It is
  different from the physical ACV refrigerant leakage task.
- **Rainflow:** cycle counting from stress reversals; amplitude is range/2 and
  residual half cycles carry count 0.5 in the SHM implementation.
- **Extrapolation:** evidence outside the training envelope. A range flag is not
  an error bar; being inside the envelope does not guarantee correctness.
- **Calibration:** correspondence between stated probability and measured
  correctness. Current outputs do not provide calibrated fault probabilities.
- **Remaining useful life (RUL):** remaining exposure until a specified endpoint.
  Per-record damage without verified history/exposure and approved limits cannot
  establish it. Definitions are answerable even when operational estimates are not.

## Verification

Run `python -m pytest -q`. Engineering tests exercise all four pipeline explainers,
glossary routing, briefings, focus hints, attribution, scope conflicts, unsupported
threshold instructions, invalid inputs and isolation of notes from provider calls.
The original prediction and model tests must continue passing. No live model API
calls or railway operational validation are claimed by these tests.

"""Dashboard-specific context; never substitutes the audited reference replay."""
import json
import re
import sys

from .service import EvidenceAssistant, ROOT, LIMIT, METRICS, digest
from .catalog import MODELS, validate_model
from .explanations import definition_facts
from .terminology import definition_targets
from .routing import intent

GUIDES = {
    "door": [
        ("envelope current trace replay", "The Normal envelope is the pointwise 90th percentile of labelled Normal cycles of the same opening/closing operation. Above-envelope intervals show current exceeding that reference; they do not establish the failed component. Replay shows measured leaf positions and switch states, not a simulation."),
        ("confidence score vote", "The optional Door score is an uncalibrated ExtraTrees class vote. It is not a validated probability of correctness."),
        ("panel dashboard navigation", "Open Show evidence on a cycle to inspect its measured replay, current trace, above-envelope intervals and indicators against Normal cycles. Select a cycle in chat to ask about that cycle specifically."),
    ],
    "acv": [
        ("suspicion index score ranking lead", "The suspicion index rescales ranking scores within this uploaded train to 0–100. It is a relative ordering, not a failure probability. Lead over next car is the difference in displayed index points."),
        ("near tie cluster consist cab", "The consist groups cars within 0.02 in the normalised ranking index as near ties. Cab positions at both ends are a formation convention, not measured car-type telemetry."),
        ("residual mad warmest duty persistent", "Peer residual is cabin temperature minus the simultaneous peer median. Warmest share counts how often a car is warmest; duty cycle counts cooling-mode rows. Persistent-run minutes measure an uninterrupted positive peer residual. Missing indicators are not zero."),
        ("panel dashboard navigation chart temperature", "Select a car in the train formation or consist checklist to inspect its indicators and temperature chart. Use the chat's car selector to match that view. The time series is dashboard evidence, not a forecast."),
    ],
    "rail": [
        ("side positions sensor layout", "Odd axle-box positions 1, 3, 5 and 7 correspond to Side I; even positions 2, 4, 6 and 8 correspond to Side II. This is a sensor layout, not an exact track location."),
        ("validation fold score ready", "The Rail panel reports the registered model's stored validation: individual file-level stratified cross-validation fold macro F1 scores and their mean. This mean is not pooled out-of-fold macro F1 or held-out test performance. Missing model metadata is shown as unavailable, not replaced with example scores. Inspect current result metadata for the numeric values."),
        ("panel dashboard navigation", "The panel shows sensor mapping, class balance and a current-batch summary. The results table lists flagged files and Side I/Side II scores; Show all includes Normal predictions. Side scores are not calibrated probabilities."),
    ],
    "shm": [
        ("half fraction", "Half-cycle fraction is the sum of residual half-cycle weights divided by total weighted cycle count. Each residual half cycle contributes 0.5; this is not a probability or a damage percentage."),
        ("rms std quantile p90 p99", "Stress RMS is root-mean-square stress; stress std measures variation about its mean. Amplitude p90/p99 are quantiles of the rainflow amplitude distribution, not confidence levels. Source stress units are unspecified."),
        ("miner limit bar percent threshold", "SHM bars use D = 1 as a theoretical Miner reference, not percentage of lifetime consumed, an approved inspection trigger or a validated failure threshold for this fitted proxy. Displayed bar widths are capped; read the numeric damage value."),
        ("spread exponent amplitude cycle", "Damage sums weighted amplitude-power contributions across counted cycles. The dashboard's peak-amplitude ratio illustrates exponent sensitivity; it does not by itself explain the complete damage ratio. Cycle count and the full amplitude distribution also matter."),
        ("panel dashboard navigation evidence", "Recordings are sorted by estimated damage. Open Evidence for sample count, rainflow cycles, half-cycle fraction, amplitude quantiles, stress statistics and fitted exponent. Sorting is not a maintenance-priority ranking."),
    ],
}


def flatten(value, prefix="", depth=0):
    """Exact display scalars, bounded traversal; traces stay local unless selected."""
    if depth > 7:
        return []
    if isinstance(value, dict):
        return [item for key, part in value.items() if key not in {"submission_csv", "motion", "trace", "series"}
                for item in flatten(part, f"{prefix} / {key}" if prefix else key, depth + 1)]
    if isinstance(value, list):
        return [item for i, part in enumerate(value[:100]) for item in flatten(part, f"{prefix} / {i + 1}", depth + 1)]
    if value is None or isinstance(value, (str, bool, int, float)):
        return [(prefix, "Not reported" if value is None else format(value, ".6g") if isinstance(value, float) else str(value)[:1200])]
    return []


class DashboardAssistant:
    def __init__(self, domain, snapshot=None):
        if domain not in {*GUIDES, "general"}:
            raise ValueError("Invalid subsystem")
        if domain == "general" and snapshot is not None:
            raise ValueError("Select a subsystem to use uploaded results")
        self.domain, self.snapshot = domain, snapshot or {}
        self.rows = self.snapshot.get("rows", [])
        self.base = EvidenceAssistant([], run_directory=ROOT / "outputs/dashboard-live-context", bundle_sha256="dashboard-context")
        self.base.source_warnings = [w for w in self.base.source_warnings if not w.startswith("No matching bundle")]

    def answer(self, question, *, file_id=None, row_index=None, car_id=None, selector=None, consent=False, previous_question=None, **settings):
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
            raise ValueError("Invalid question")
        if self.domain == "general":
            if any(v is not None for v in (file_id, row_index, car_id)):
                raise ValueError("Select a subsystem before selecting result evidence")
            reference = self.base.ask(question, previous_question=previous_question, **settings)
            if reference["status"] != "insufficient_evidence" and re.search(r"\b(what can (?:you|this assistant)|help me (?:use|navigate)|navigate|navigation|use the dashboard)\b", question, re.I):
                text = "I’m RailPulser. I explain terminology, physics, evaluation metrics and dashboard evidence. Open Door, ACV, Rail or SHM, upload recordings and run analysis; then select the same file/cycle/car in chat to discuss its results. The Assistant workspace provides a larger chat view. General has documentation only, not a combined result set. I cannot certify safety, confirm root causes or invent remaining life."
                fact = {"id": "dashboard:general-guide", "text": text, "source": "docs/DASHBOARD_ASSISTANT_INTEGRATION.md"}
                reference = self.base._response([fact], "answered", "", None, [])
                reference["answer"] = text
            result_request = intent(question) in {"summary", "record", "review", "quality", "briefing", "compare"} or re.search(
                r"\b(my|uploaded|this result|this prediction|current batch|highest|lowest|how many)\b", question, re.I)
            if result_request and reference["status"] != "insufficient_evidence" and reference.get("presentation") != "verified_definition":
                reference = self.base._response([], "needs_clarification", "", None, [])
                reference["answer"] = "Select Door, ACV, Rail or SHM in the workspace subsystem menu to discuss its uploaded results. General covers terminology, evaluation metrics and dashboard guidance; it does not combine uploaded batches."
            reference["dataset_label"] = "General documentation · no uploaded results connected"
            if reference["status"] == "answered" and reference.get("presentation") != "verified_definition":
                return self.base._with_provider(reference, question, selector, consent)
            return reference
        rows = [(i, r) for i, r in enumerate(self.rows) if file_id is None or r.get("file_id") == file_id]
        if file_id is not None and not rows:
            raise ValueError("Unknown file")
        if row_index is not None:
            if type(row_index) is not int or not any(i == row_index for i, _ in rows):
                raise ValueError("Unknown row")
            rows = [(i, r) for i, r in rows if i == row_index]
        q = question.lower()
        if definition_targets(question) in (["mad"], ["csv"]):
            term = definition_targets(question)[0]
            explanation = {"mad": "MAD means Median Absolute Deviation. It is a robust spread measure used for peer-relative ACV comparisons.", "csv": "CSV means Comma-Separated Values, the plain-text table format used for recordings and prediction exports."}[term]
            fact = {"id": f"term:dashboard-{term}", "text": explanation, "source": "app/railpulse/frontend/src/terms.js"}
            response = self.base._response([fact], "answered", "", self.domain, [])
            response.update(answer=explanation, presentation="verified_definition")
            return response
        if match := re.search(r"\brow (\d+)\b", q):
            number = int(match[1]) - 1
            rows = [(i, r) for i, r in rows if i == number]
            if not rows:
                raise ValueError("Row outside scope")
        filenames = re.findall(r"[\w.-]+\.(?:csv|xlsx)\b", question, re.I)
        if filenames:
            rows = [(i, r) for i, r in rows if r.get("file_id", "").lower() in {f.lower() for f in filenames}]
            if not rows:
                raise ValueError("File outside scope")
        if car_id is not None and (self.domain != "acv" or not rows or not all(car_id in r.get("ranked_cars", []) for _, r in rows)):
            raise ValueError("Car outside selected scope")
        # Reuse terminology, refusal and document routes; no replay or stored
        # canonical validation is installed in this assistant instance.
        reference = self.base.ask(question, subsystem=self.domain, selector=None, consent=False, **settings)
        targets = definition_targets(question)
        is_term = bool(targets and (definition_facts(question) or self.base.terminology.lookup(targets)[0]))
        if reference["status"] == "insufficient_evidence" or reference.get("presentation") == "verified_definition" or is_term:
            reference["dataset_label"] = "Dashboard documentation · not reference replay"
            return reference
        route = intent(question)
        facts = []
        def add(text, source, value=None):
            facts.append({"id": f"dashboard:{len(facts)}", "text": text, "source": source, "value": value})
        guides = [(len(set(re.findall(r"\w+", q)) & set(keys.split())), text) for keys, text in GUIDES[self.domain]]
        best = max(guides, key=lambda x: x[0])
        numeric_request = bool(re.search(r"\b(highest|lowest|maximum|minimum|peak|how many)\b", q))
        general = not filenames and row_index is None and not numeric_request and not re.search(r"\b(this result|this prediction|row \d+|my|uploaded|current batch)\b", q)
        if best[0] and general and route not in {"summary", "review", "briefing", "quality", "compare"}:
            add(best[1], f"dashboard-guide:{self.domain}")
        elif route in {"evaluation", "official_score"}:
            add(METRICS[self.domain], f"metric-contract:{self.domain}")
            values = flatten({k: self.snapshot[k] for k in ("validation", "model_score") if k in self.snapshot})
            add("\n".join(f"{k.replace('_', ' ')}: {v}" for k, v in values) if values else "No validation values were supplied with this dashboard result. Official test scores cannot be inferred from predictions.", "dashboard:validation")
        elif route == "pipeline":
            add("This dashboard uses the canonical subprocess for Door and SHM, its local rule-based ranker for ACV, and its registered model for Rail. Do not assume all panels use the audited replay's model bundle.", "dashboard-guide:runtime")
            add(GUIDES[self.domain][-1][1], f"dashboard-guide:{self.domain}")
        elif route in {"summary", "record", "review", "quality", "briefing", "compare"} or numeric_request or rows and (filenames or row_index is not None or re.search(r"\b(car|cycle|recording|prediction|result|damage|rank)\b", q)):
            if not rows:
                add("No analysed dashboard results are connected for this subsystem. Upload files and run analysis first. I can still explain terms and panel controls.", "dashboard:empty")
            elif route == "record" and len(rows) > 1:
                response = self.base._clarify(question, "Which file or cycle do you mean? Choose a row or use the chat scope selectors.", self.domain, [], [(f"Row {i + 1} · {r.get('file_id', 'cycle')}", f"Explain this result for row {i + 1}") for i, r in rows])
                return response
            else:
                add(f"Current dashboard selection: {len(rows)} result rows across {len({r.get('file_id') for _, r in rows})} files. These are uploaded results, not the saved reference replay.", "dashboard:selection")
                if self.domain in {"door", "rail"}:
                    count = sum(r.get("prediction") != "Normal" for _, r in rows)
                    add(f"{count} of {len(rows)} selected rows have a non-Normal prediction. A Normal prediction is not a safety clearance.", "dashboard:selection")
                if self.domain == "shm":
                    values = [r["prediction"] for _, r in rows]
                    add(f"Estimated recording damage ranges from {min(values):.6g} to {max(values):.6g}. This is not remaining life or an approved severity scale.", "dashboard:selection")
                    rows = sorted(rows, key=lambda item: -item[1]["prediction"])
                if route == "review" and self.domain in {"door", "rail"}:
                    rows = [(i, r) for i, r in rows if r.get("prediction") != "Normal"]
                for i, row in rows[:4]:
                    if row.get("warnings"):
                        add(f"Row {i + 1} warnings: " + " ".join(row["warnings"]), f"dashboard:row:{i}")
                    value = row
                    if car_id:
                        car = next((c for c in row.get("consist", {}).get("rows", []) if c.get("car") == car_id), {})
                        value = {"file_id": row.get("file_id"), "car": car_id, "rank": row["ranked_cars"].index(car_id) + 1,
                                 "suspicion_index": row.get("display_scores", {}).get(car_id), "indicators": car}
                    scalars = flatten(value)
                    if re.search(r"\b(trace|chart|temperature|current|peak)\b", q):
                        trace = row.get("evidence", {}).get("trace", [])
                        currents = [p["current"] for p in trace if isinstance(p.get("current"), (int, float))]
                        if currents:
                            scalars += [("displayed trace / current min", str(min(currents))), ("displayed trace / current max", str(max(currents))), ("displayed trace / points", str(len(currents)))]
                        for car, points in row.get("series", {}).get("by_car", {}).items():
                            if car_id and car != car_id:
                                continue
                            values = [v for v in points if isinstance(v, (int, float))]
                            if values:
                                scalars += [(f"displayed temperature chart / car {car} min", str(min(values))), (f"displayed temperature chart / car {car} max", str(max(values)))]
                        scalars.append(("chart limitation", "Extrema use the displayed, potentially downsampled points; they are not raw-stream extrema."))
                    query_words = set(re.findall(r"\w+", q)) - {"what", "this", "the", "result", "explain"}
                    relevant = [(k, v) for k, v in scalars if query_words & set(re.findall(r"\w+", k.replace("_", " ").lower()))]
                    picked = relevant[:14] if relevant else scalars[:12]
                    add(f"Row {i + 1} · {row.get('file_id', 'cycle')}\n" + "\n".join(f"{k.replace('_', ' ')}: {v}" for k, v in picked), f"dashboard:row:{i}", value)
                if len(rows) > 4:
                    add(f"Showing 4 of {len(rows)} matching rows. Choose a file/cycle for full detail.", "dashboard:selection")
        else:
            if reference["status"] == "answered":
                return self.base._with_provider(reference, question, selector, consent)
            return reference
        response = self.base._response(facts, "answered", "", self.domain, [])
        response["answer"] = "\n\n".join(f["text"] for f in facts)
        response["dataset_label"] = "Current dashboard results" if self.rows else "Dashboard guide · no analysis loaded"
        response["provenance"]["dashboard_snapshot_sha256"] = digest(self.snapshot)
        response["routing"] = {"intent": route, "question": question}
        response["engineer_input"] = reference.get("engineer_input")
        response["warnings"].extend(reference.get("warnings", []))
        response["scope"].update(file_ids=sorted({r.get("file_id", "") for _, r in rows}), row_index=row_index, car_id=car_id)
        return self.base._with_provider(response, question, selector, consent)


def main():
    request = json.load(sys.stdin)
    if request.get("action") == "context":
        print(json.dumps({"models": MODELS, "integration_version": 1}))
        return
    assistant = DashboardAssistant(request["subsystem"], request.get("dashboard_snapshot"))
    selector, warning = None, None
    if request.get("provider"):
        validate_model(request["provider"], request.get("model"))
        if request.get("consent") is True and isinstance(request.get("api_key"), str) and request["api_key"].strip():
            try:
                from .llm import make_selector
                selector = make_selector(provider=request["provider"], model=request["model"], api_key=request["api_key"])
            except Exception:
                warning = "Provider unavailable; using local evidence."
        else:
            warning = "No authorised API key supplied; using local evidence."
    fields = {k: request[k] for k in ("file_id", "row_index", "car_id", "previous_question", "engineer_instructions", "engineer_context", "detail", "audience") if k in request}
    result = assistant.answer(request["question"], selector=selector, consent=request.get("consent") is True, **fields)
    if warning:
        result["warnings"].append(warning)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()

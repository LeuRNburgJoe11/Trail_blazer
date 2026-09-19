# Dashboard assistant integration

## Run locally

For a fresh clone, follow [teammate installation and acceptance tests](DASHBOARD_SETUP.md)
first. `requirements-dashboard.txt` includes the upload dependency; Door and Rail
also need the generated assets documented there.

Use the repository virtual environment, not an editable installation of the nested
duplicate `railpulse` package. From the repository root:

```bash
cd app/railpulse
../../.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal:

```bash
cd app/railpulse/frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend proxies `/api` to port 8000, including
assistant requests. Port 8766 and the standalone assistant prototype are **not
required**. Vite dev and preview both configure this proxy. `VITE_API_URL` can
override it for an explicitly configured deployment. HTML API responses now produce
a useful connection message instead of a raw JSON parsing exception.

## Interface

The assistant is named **RailPulser**, with a scalable rail-and-pulse SVG avatar.
The workspace defaults to **General**: documentation, metrics and navigation,
without connecting or pooling uploaded results. Choose a specific subsystem to
use its latest upload snapshot. General rejects result snapshots and row selectors.
RailPulser explains evidence; it cannot certify safety, confirm root causes or
invent remaining life. Upload recordings and run analysis in a subsystem, then
match the chat file/cycle/car selector to the object you are inspecting.

Each scope starts with editable, tailored explanation preferences in Instructions;
Restore defaults resets them. These are preferences, not authority to override
evidence or safety boundaries. Local mode uses supported template preferences,
not unrestricted natural-language instruction execution.

- Each subsystem has a compact chat panel with collapsible instructions, local
  sample questions, the shared OpenAI/Anthropic model catalog, key entry and consent.
- The Assistant workspace tab provides a larger conversation area in the existing
  dashboard theme (including its dark palette), with a subsystem selector.
- Successful results remain available when changing dashboard tabs. Workspace chat
  uses that subsystem's latest result set. Nothing is persisted across page reloads.
- File/cycle and ACV car selectors explicitly scope chat; they do not automatically
  follow selections inside the chart components. Match the selectors to the object
  being inspected. Changing scope clears the conversation and attributed notes.
- Keys exist only in component memory, are never stored in browser storage, and
  clear on unmount/model change/reload. Model invocation requires explicit consent.

## Evidence and explanations

There is no saved reference replay in integrated chat. A prediction endpoint stores
its own response as an opaque, expiring snapshot capability. The chat endpoint
accepts that capability plus bounded selectors, not client-supplied result facts.
Snapshot storage is process-local, limited to 16 entries / 24 MB total and a one-hour
TTL. Large results can still be displayed but may not fit chat context. Expired or
evicted snapshots require rerunning analysis. Use one backend worker for this demo.

The backend invokes the canonical assistant in a separate process because the
dashboard imports a different `railpulse` package. Requests (including optional
keys) travel over stdin, never command-line arguments or temporary credential files.
Captured provider/process errors are not echoed. Only compact selected fact text
goes to the provider; entire recordings, traces and engineer notes do not.

`DashboardAssistant` covers:

- Door cycle predictions, timings, current-envelope rationale, available indicators
  and trace summaries. The class vote is uncalibrated.
- ACV rankings, suspicion index, consist ties, selected-car indicators and displayed
  temperature ranges. Ranges from thinned chart points are not raw-stream extrema.
- Rail side mapping, current classifications and side scores, validation metadata
  when supplied, and navigation of the static reference cards.
- SHM damage ranges, selected recording features/warnings, fitted exponent,
  amplitude/cycle interpretation and the theoretical Miner reference.
- The existing source-backed definitions, document retrieval, operational limits,
  optional cited generation and no-key fallback.

Local answers show bounded evidence (up to four rows, selected fields); choose a
specific row for detail. This is not arbitrary natural-language querying of every
raw sample, nor unrestricted causal diagnosis. Clarification and absent-evidence
responses are intentional. Ordinary documentation does not override snapshot facts.

## Important existing dashboard distinctions

Door and SHM use canonical subprocess inference; ACV uses the dashboard rule-based
ranker; Rail uses its registry model. Chat does not claim these are all the audited
bundle or attach canonical replay validation to different models.

Rail's component contains static fold scores, pooled OOF value, fallback score and
a readiness label. Chat explicitly identifies these as UI reference literals, not
fresh validation or proof of availability. Actual Rail inference still requires a
trained registry model. The existing Door status endpoint can report no registry
model even though Door inference uses the canonical subprocess; this integration
does not replace the dashboard's model-status implementation.

SHM's D = 1 bar reference is not an approved threshold for the calibrated proxy.
The integrated assistant does not turn it into a lifetime percentage or maintenance
trigger. No actual predictive models were retrained or changed in this integration.

A pre-existing SHM temporary-output filename collision was removed: concurrent
requests now use unique output names so one request cannot pick up another's result.

## Security and deployment boundary

This remains a local demo, not a production multi-user service. Assistant endpoints
restrict host/origin; CORS is narrowed to local frontend origins. Snapshot tokens
are bearer capabilities and are not account authentication. Production requires
TLS, authenticated ownership, shared bounded storage for multiple workers, request
rate/concurrency limits, proper upload lifecycle management and deployment-specific
origins. Do not expose the development backend publicly.

## Verification

Tests cover current-result vs replay separation, absent results, selected rows/cars,
documentation, operational refusals, consent, snapshot isolation/expiry, payload
tampering, origin and size limits, and the real canonical subprocess bridge.
Browser smoke testing used a synthetic SHM file; this checks integration, not model
accuracy. Paid provider calls were not made; existing offline adapter tests remain.

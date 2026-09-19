# RailPulse evidence assistant

The [engineering explanation layer](ENGINEERING_ASSISTANT.md) adds bounded engineer
instructions, attributed unverified notes, contextual definitions, pipeline
walkthroughs and inspection/handover preparation. It does not grant operational
authority. The shared API now returns additive schema-2 explanation fields.

## Implemented scope

Launch `python -m streamlit run app/main.py`. The **Ask RailPulse** panel works
without an API key or new dependencies. Select a subsystem, optional recording(s)
and optional individual finding. Ask a suggested question or type a question.
Source cards and a downloadable JSON response retain evidence and provenance.

The assistant supports session summaries, quality warnings, result explanations,
two-recording within-subsystem comparisons, all four metric contracts, stored model
comparisons and validation evidence, and local reference search. Comparisons show
the actual evidence side by side; they do not infer chronology or common assets.
Rejected batches remain visible. Test scores stay unknown. Data-free sessions do
not invent observations. SHM validation is read from its hash-verified linked report.

This is a first, constrained release—not a general-purpose autonomous agent.
The optional LLM writes short, cited explanations of retrieved evidence. Generated
paragraphs are labelled separately from unchanged canonical source cards. Outputs
must pass structural, citation-membership, numeric-support and conservative
operational-language checks; failures fall back locally. These checks **do not prove
semantic entailment**: users must verify AI wording against the cited source cards.
Legacy evidence-ID selectors remain supported for existing integrations. The
[local hybrid knowledge base](KNOWLEDGE_BASE.md) uses lexical and LSA vector
retrieval; it can still miss paraphrases. Retrieval relevance is not certainty.

Routing distinguishes model walkthroughs, definitions, evaluation, review policy,
review findings, quality warnings, individual recordings and batch summaries.
Ambiguous model/recording references ask for scope before any provider invocation.
`clarification.options` supplies labels and explicit follow-up questions. Send a
label with `previous_question` to resolve it; the service recomputes valid options
against the current authorised scope. A new explicit question replaces the pending
clarification. This is bounded clarification context, not general chat memory.
The React UI displays the real `answer`, route and resolved scope rather than a
fixed successful-answer header and universal explanation boilerplate.

## Optional providers

The adapters support Anthropic and OpenAI via LangChain. Both the Streamlit panel
and the [React prototype](../app/assistant-ui/README.md) use the reviewed shared
model catalog. Install optional dependencies
while retaining the inference runtime constraints:

```bash
python -m pip install -r requirements-all.txt -r requirements-assistant.txt
python -m pytest -q
```

Select a model available to your account and enter that provider's key in the optional
panel. Explicit consent is required. The Streamlit password form clears after submission;
the service does not write credentials or conversation history to disk or globals.
This is not a guarantee of secure memory erasure. Deploy over TLS; do not use a
shared account/session. Question and compact evidence text, including filenames,
are sent to the provider, but raw recordings and artifact files are not.

The adapter makes at most one model invocation, with a 90-second SDK timeout,
zero retries and 8,192 output tokens including reasoning where applicable. Unknown IDs, unsupported numeric literals, malformed output, errors,
missing dependencies, or denied consent select the deterministic fallback.
Provider exception text is never shown. External LangChain/LangSmith tracing must
be disabled. No browsing, shell execution, dynamic code, arbitrary SQL, retraining,
prediction mutation or autonomous maintenance actions are exposed.

Direct optional dependencies are pinned to tested versions; resolve a full
deployment lock before public release. No paid live-provider verification is
claimed by the offline test suite. All eight catalog models have SDK request
serialization tests; account access cannot be inferred from catalog membership.

## Reusable backend contract

`src/railpulse/assistant/service.py` is independent of Streamlit and the model
training/inference packages. The existing React/FastAPI prototype is not modified.
Your colleague can wrap this API after authenticating the request:

```python
from railpulse.assistant import EvidenceAssistant

service = EvidenceAssistant(
    authorised_session_records,
    run_directory=trusted_run_directory,
    bundle_sha256=selected_bundle_hash,
    failures=authorised_session_failures,
)
response = service.ask(
    "Show quality warnings",
    subsystem="rail",
    file_ids=selected_session_filenames,
)
```

Never accept `run_directory`, document paths, raw records, or bundle hashes as
trusted values directly from an unauthenticated client. Resolve them on the server.
Authorisation must happen before constructing this service; it is not an HTTP
authentication system. No process-global session cache is used.

The JSON response includes `schema_version`, `answer`, `mode`, `status`, `scope`,
typed `facts`, `citations`, `warnings`, `limitations`, `suggested_questions`, and
`provenance` with bundle/corpus/snapshot hashes. Render source text as plain text,
not executable HTML or arbitrary links. Citation `source` values are identifiers
for reviewed documents or scoped decision records, not URLs to fetch blindly.

The UI invalidates answers after bundle, evidence, failure or selection changes.
The service deep-copies input records and rejects wrong-bundle records and unknown
file/finding IDs. It does not infer identity from equal filenames across subsystems.
Validation reports are trusted local run artifacts, not signed organiser results.

## Retrieval and remaining work

Only the explicit document allowlist is searched. Historical duplicate application
trees, uploads and arbitrary filesystem paths are excluded. Each document passage
has a content hash and section reference. Methodology documents describe their own
dated scope; live results come only from selected-session records. Documents remain
untrusted data to the LLM, which is only allowed to return existing evidence IDs.

This release does not implement a vector database, multi-agent delegation, RUL,
damage thresholds, a causal diagnosis, calibrated uncertainty, fleet linkage,
SHM what-if simulation or a validation failure-gallery UI. These require separate
analysis and evaluation. Human-reviewed retrieval/answer benchmarks and paid-model
quality/latency evaluation are still needed before a public deployment. The test
suite provides deterministic correctness, scope and failure-path checks, not a
claim of general natural-language accuracy or production railway safety.

# RailPulse agent interface — React prototype

A standalone, warm-neutral chat workspace with subsystem navigation, a persistent
composer, source notebook, model search and bring-your-own-key connection dialog.
Inspired by conversational AI products without copying their branding. It preserves
the colleague's separate `app/railpulse/frontend` application unchanged.

## Run

From the **repository root**, install the backend and launch it on loopback only:

```bash
python -m pip install -r requirements-all.txt -r requirements-assistant.txt
PYTHONPATH=src python -m uvicorn app.assistant_api:app --host 127.0.0.1 --port 8766 --no-access-log
```

In a second terminal:

```bash
cd app/assistant-ui
npm ci
npm run dev
```

Open **http://127.0.0.1:5174**. Vite proxies `/api/assistant` to port 8766.
`npm run build` creates the production frontend; `npm run preview` uses the same
proxy for local build verification. Do not expose either server publicly.

## Model selection

Select the model in the upper-right corner, enter **that provider's API key**,
and authorise sending the question and compact evidence. No environment variable
or hand-entered model ID is needed. The key remains in a React ref in that tab's
memory, not localStorage, sessionStorage, cookies, URLs, server files, or chat
history. Disconnect or reload to clear it. This is not secure memory erasure.
Each request sends the key to the local backend; deploy only over TLS if adapting
this beyond loopback. Neither real keys nor paid calls were needed for tests.

Catalog verified 2026-09-19 against:

- [OpenAI model catalog](https://developers.openai.com/api/docs/models): GPT-6 Astra;
  GPT-5.6 Sol, Terra and Luna.
- [Anthropic model catalog](https://platform.claude.com/docs/en/models/overview):
  Claude Fable 5.1, Opus 5, Sonnet 5 and Haiku 4.5.

These are the current general-purpose model lineup, including flagship and
lighter alternatives—not every historical or specialised audio/image model.
Access depends on the user's account and provider billing. Model metadata is
centralised in `src/railpulse/assistant/catalog.py`; review it as models change.
New models are never silently substituted when a selected model fails.

OpenAI uses Responses with `store=False` and low reasoning effort. Both providers
use one bounded request, no automatic retries, a 90-second SDK timeout and an
8,192-token output budget (including reasoning where applicable). These limits
may cause a demanding request to fall back; they are not latency guarantees.
Provider hosts are fixed in code, not supplied by clients or overridden by
provider base-URL environment variables. Typed reasoning blocks are excluded
from displayed output. SDK dependencies are pinned at the versions tested here.

## Evidence and prototype boundaries

This UI uses the fixed **audited reference replay**, containing 123 findings from
86 recordings. It does not read private Streamlit sessions or support live uploads.
The label stays visible. Questions use the selected scope; only a pending
clarification's original question is carried forward, not the full conversation.
Scope changes reset answers. API schema 4 is required: restart the Python backend
after updating to load the local knowledge base, then reload the UI.

The local [knowledge base](../../docs/KNOWLEDGE_BASE.md) indexes all four subsystem
kits and the Door header glossary, together with allowlisted implementation docs.
Sample queries include DCSR, S–N curves, rail ripples and refrigerant heat transport.
Retrieved source cards identify document section and line range.

No-key mode uses intent-specific local evidence templates and clarification choices.
With a key and consent, the model produces short cited explanations. Citation,
numeric and operational-language checks reject invalid output, but cannot prove
every paraphrase is faithful. AI wording is labelled; check it against the unchanged
source cards. The source notebook retains the full evidence record. Downloaded JSON
excludes credentials. Missing keys, denied consent, provider errors and invalid output fall back
visibly. Existing predictions, model artifacts and scoring outputs are unchanged.

`app/assistant_api.py` serves a fixed reviewed replay, rejects unknown fields,
foreign origins/hosts, unsupported provider/model combinations, arbitrary file
paths and oversized request bodies. Errors never echo request values or provider
exception text. It is a **local demo**, not a production authentication gateway.
Before public deployment add authenticated server-side session ownership, TLS,
rate/concurrency limits, managed secret handling, audit policy and load testing.

## Integration handoff

Keep `src/railpulse/assistant` as the shared source of truth. The colleague can
reuse `ModelDialog`, the source cards and the `/api/assistant` JSON contract without
installing the duplicate modelling package in `app/railpulse/src`.
The authoritative inference bundle stays untouched.

Check backend behavior with `python -m pytest -q tests/test_assistant_api.py`.
Tests cover real SDK request serialization for all eight models without contacting
providers, mocked provider success/failure, consent, catalog mismatches, request
limits and secret redaction. Live account access and response quality still need
testing with the user's own authorised keys.

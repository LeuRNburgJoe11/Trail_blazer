"""Reusable Streamlit adapter over the framework-independent assistant service."""
import hashlib
import json
from pathlib import Path

import streamlit as st

from railpulse.assistant import EvidenceAssistant
from railpulse.assistant.service import SUGGESTIONS
from railpulse.assistant.catalog import MODELS


def render_assistant(records, model_directory, bundle_signature, failures):
    st.subheader("Ask RailPulse — evidence assistant")
    st.caption("Read-only explanations. No API key needed. Optional AI explanations cite source evidence; verify their wording against the unchanged source cards.")
    # Fingerprint even rejected/cleared batches so an old answer never survives a
    # changed evidence snapshot. No conversation history is shared between users.
    signature = hashlib.sha256(json.dumps([records, failures, str(model_directory), bundle_signature], sort_keys=True).encode()).hexdigest()
    if st.session_state.get("assistant_snapshot") != signature:
        st.session_state.pop("assistant_answer", None)
        st.session_state.assistant_snapshot = signature
    domain = st.selectbox("Assistant subsystem", ["all", "door", "acv", "rail", "shm"], key="assistant_domain")
    available = sorted({r["file_id"] for r in records if domain == "all" or r["subsystem"] == domain})
    files = st.multiselect("Assistant recordings (optional)", available, key=f"assistant_files_{signature}_{domain}")
    findings = [r for r in records if (domain == "all" or r["subsystem"] == domain) and (not files or r["file_id"] in files)]
    labels = {r["decision_id"]: f"{r['subsystem']} / {r['file_id']} / {r['entity_id']}" for r in findings}
    finding = st.selectbox("Assistant finding (optional)", [None, *labels], format_func=lambda key: labels.get(key, "All selected findings"), key=f"assistant_finding_{signature}_{domain}_{','.join(files)}")
    scope = (domain, tuple(files), finding)
    if st.session_state.get("assistant_scope") != scope:
        st.session_state.pop("assistant_answer", None)
        st.session_state.assistant_scope = scope
    prompt = st.selectbox("Suggested question", SUGGESTIONS, key="assistant_suggestion")
    question = st.text_input("Or ask your own question", max_chars=2000, key="assistant_question")
    with st.expander("Engineer instructions and attributed context"):
        audience = st.selectbox("Explain for", ["plain", "technician", "engineer"], key="assistant_audience")
        detail = st.selectbox("Explanation detail", ["concise", "detailed"], key="assistant_detail")
        focus = st.selectbox("Investigation focus", ["auto", "quality", "evaluation", "review"], key="assistant_focus")
        instructions = st.text_area("Explanation / investigation instructions", max_chars=1500, key="assistant_instructions")
        author = st.text_input("Engineer name or role (self-reported)", max_chars=80, key="assistant_author")
        context_key = "assistant_note_" + hashlib.sha256(repr((signature, scope)).encode()).hexdigest()
        engineer_context = st.text_area("Recording context / investigation notes (unverified)", max_chars=2000, key=context_key)
        st.caption("Supported hints: audience, detail, definitions and focus. Other directives are not executed. Notes are exported separately, not verified evidence or approved policy, and are not sent to the provider.")
    preferences = (audience, detail, focus, instructions, author, engineer_context)
    if st.session_state.get("assistant_preferences") != preferences:
        st.session_state.pop("assistant_answer", None)
        st.session_state.assistant_preferences = preferences
    consent = False
    with st.expander("Optional external LLM (Anthropic / OpenAI via LangChain)"):
        st.caption("Requires optional dependencies. Your question and compact evidence text (including selected filenames) leave this machine. Raw recordings and model files are never sent. Use only if authorised. No external tracing is permitted.")
        model = st.selectbox("Provider model", MODELS, format_func=lambda m: m["name"], key="assistant_model_choice")
        # A form clears the password widget immediately after each submission.
        with st.form("assistant_external", clear_on_submit=True):
            api_key = st.text_input("API key (one request only)", type="password")
            consent = st.checkbox("I authorise sending this question and evidence to the provider")
            external = st.form_submit_button("Ask with optional LLM")
    offline = st.button("Ask using local evidence")
    if offline or external:
        try:
            service = EvidenceAssistant(records, run_directory=Path(model_directory).parent,
                                        bundle_sha256=bundle_signature, failures=failures)
            selector = None
            warning = None
            if external:
                if not consent:
                    warning = "External request not authorised; using local evidence."
                else:
                    try:
                        from railpulse.assistant.llm import make_selector
                        selector = make_selector(provider=model["provider"], model=model["id"], api_key=api_key)
                    except Exception:
                        warning = "Optional LLM configuration unavailable; using local evidence."
            answer = service.ask(question or prompt, subsystem=None if domain == "all" else domain,
                                 previous_question=st.session_state.get("assistant_answer", {}).get("clarification", {}).get("question"),
                                 file_ids=files, decision_id=finding, selector=selector, consent=consent,
                                 engineer_instructions=instructions, engineer_context=engineer_context,
                                 engineer_author=author, audience=audience, detail=detail, focus=focus)
            if warning:
                answer["warnings"].append(warning)
            st.session_state.assistant_answer = answer
        except (ValueError, OSError, KeyError, TypeError):
            st.session_state.pop("assistant_answer", None)
            st.error("Assistant evidence is unavailable or inconsistent. Check the selected scope and trusted bundle.")
    answer = st.session_state.get("assistant_answer")
    if answer:
        st.caption(f"Mode: {answer['mode']} · Status: {answer['status']}")
        # Plain text prevents source content from becoming active HTML/Markdown links.
        st.text(answer["answer"])
        if answer.get("clarification"):
            st.caption("Reply using one of these labels, or select a recording/subsystem and ask again:")
            st.write(" · ".join(o["label"] for o in answer["clarification"]["options"]))
        for warning in answer["warnings"]:
            if warning in answer.get("reference_caveats", []) and not warning.startswith("Theoretical Miner's-rule"):
                continue
            st.warning(warning)
        st.caption(" ".join(answer["limitations"]))
        with st.expander("Assistant source cards and provenance"):
            st.json(answer)
        st.download_button("Download assistant evidence", json.dumps(answer, indent=2), "assistant_evidence.json", "application/json")

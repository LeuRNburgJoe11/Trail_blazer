import { useEffect, useRef, useState } from "react";
import { assistantContext, askAssistant } from "../api";
import "./AssistantChat.css";

const QUERIES = {
  general: [
    "What does SHM mean?",
    "What does ACV mean?",
    "Explain the evaluation metrics",
    "What can this assistant help me with?",
    "Summarise my uploaded results",
  ],
  door: [
    "Explain the Normal envelope",
    "What does DCSR mean?",
    "Summarise this batch",
    "Explain this result",
    "What does the confidence score mean?",
  ],
  acv: [
    "What does ACV mean?",
    "Explain the suspicion index",
    "Explain near ties in the consist",
    "Summarise this batch",
    "Explain the temperature chart",
  ],
  rail: [
    "Explain the Side I and Side II sensor positions",
    "Explain the validation fold scores",
    "Which findings need review?",
    "What does macro F1 mean?",
    "Explain this result",
  ],
  shm: [
    "What does SHM mean?",
    "Explain the Miner reference",
    "Why is the damage spread so wide?",
    "Summarise this batch",
    "Explain this result",
  ],
};

const DEFAULT_INSTRUCTIONS = {
  general: "Use concise, plain language and define unfamiliar terms. Clarify the subsystem when scope is ambiguous. Separate documentation and historical validation from current uploaded results. For result-specific questions, ask me to select a subsystem. Do not infer missing measurements or approve operational actions.",
  door: "Explain Door results in plain language. Identify the selected file and opening/closing cycle. Distinguish segmentation timing from Normal / Abnormal resistance classification. Explain switch states, current traces and the Normal envelope only when relevant. Describe confidence as uncalibrated; flag missing evidence. Do not infer the failed component or certify safety.",
  acv: "Explain ACV rankings in plain language. Identify the selected train/file and car. Compare available peer-relative temperature and operating indicators; explain near ties and missing telemetry. Suspicion indices are relative rankings, not probabilities or confirmed refrigerant leaks. Separate historical validation from uploaded results. Ask for a car selection when needed.",
  rail: "Explain Rail results in plain language. Distinguish Normal, Side I and Side II; explain sensor mapping and macro F1 when relevant. Separate static validation cards from current uploaded predictions. Flag missing speed pulses and uncertain location metadata. Side scores are not calibrated probabilities; do not invent track locations or treat Normal as safety clearance.",
  shm: "Explain SHM results in plain language. Identify the selected recording and distinguish cumulative damage estimates, rainflow cycle counts and stress/amplitude statistics. Explain units and acquisition limitations. D = 1 is a theoretical Miner reference, not an approved threshold or percentage of lifetime used. Do not infer remaining life, replacement dates or maintenance priority from damage alone.",
};

export default function AssistantChat({
  subsystem,
  result,
  workspace = false,
}) {
  const [catalog, setCatalog] = useState([]);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState(null);
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [consent, setConsent] = useState(false);
  const [instructions, setInstructions] = useState(DEFAULT_INSTRUCTIONS[subsystem] || "");
  const [notes, setNotes] = useState("");
  const [detail, setDetail] = useState("concise");
  const [row, setRow] = useState("");
  const [car, setCar] = useState("");
  const input = useRef(null);
  const controller = useRef(null);
  const bottom = useRef(null);
  const rows = result?.rows || [];
  const selected = row === "" ? null : rows[Number(row)];
  const selectedModel = catalog.find((m) => m.id === model);
  const load = () =>
    assistantContext()
      .then((v) => {
        setCatalog(v.models);
        setError("");
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
    return () => controller.current?.abort();
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest" });
  }, [messages, busy]);

  function resetConversation() {
    controller.current?.abort();
    controller.current = null;
    setMessages([]);
    setBusy(false);
    setError("");
    setNotes("");
    setQuestion("");
  }
  function scopeRow(value) {
    resetConversation();
    setRow(value);
    setCar("");
  }
  async function send(text = question, previous = null) {
    if (!text.trim() || busy) return;
    const abort = new AbortController();
    controller.current = abort;
    const pending =
      previous ?? messages.at(-1)?.result?.clarification?.question ?? null;
    setMessages((old) => [...old, { role: "user", text }]);
    setQuestion("");
    setBusy(true);
    setError("");
    try {
      const answer = await askAssistant(
        {
          question: text,
          subsystem,
          snapshot: result?.assistant_snapshot ?? null,
          row_index: row === "" ? null : Number(row),
          file_id: selected?.file_id ?? null,
          car_id: car || null,
          previous_question: pending,
          engineer_instructions: instructions,
          engineer_context: notes,
          detail,
          provider: selectedModel?.provider ?? null,
          model: selectedModel?.id ?? null,
          api_key: selectedModel ? apiKey : null,
          consent: selectedModel ? consent : false,
        },
        abort.signal,
      );
      if (controller.current !== abort) return;
      setMessages((old) => [...old, { role: "assistant", result: answer }]);
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      if (controller.current === abort) {
        setBusy(false);
        controller.current = null;
      }
    }
  }
  return (
    <section
      className={`assistant-chat${workspace ? " assistant-chat--workspace" : ""}`}
      aria-label={`${subsystem.toUpperCase()} assistant`}
    >
      <header className="assistant-chat__heading">
        <div>
          <h3>
            <img className="assistant-chat__avatar" src="/railpulser.svg" alt="" />
            {workspace
              ? "RailPulser · Evidence workspace"
              : `RailPulser · ${subsystem.toUpperCase()}`}
          </h3>
          <p>
            {subsystem === "general"
              ? "General guidance · select a subsystem to discuss uploaded results"
              : rows.length
              ? `${rows.length} current result rows connected`
              : "Documentation & dashboard guidance · run analysis for result questions"}
          </p>
        </div>
        <button className="link-button" onClick={resetConversation}>
          New chat
        </button>
      </header>
      {rows.length > 0 && (
        <div className="assistant-chat__scope">
          <label>
            Chat evidence scope
            <select value={row} onChange={(e) => scopeRow(e.target.value)}>
              <option value="">All current results</option>
              {rows.map((r, i) => (
                <option key={i} value={i}>
                  {i + 1} · {r.file_id || "Cycle"}
                  {r.start_time ? ` · ${r.start_time}` : ""}
                </option>
              ))}
            </select>
          </label>
          {subsystem === "acv" && selected && (
            <label>
              Car
              <select
                value={car}
                onChange={(e) => {
                  resetConversation();
                  setCar(e.target.value);
                }}
              >
                <option value="">All cars</option>
                {selected.ranked_cars.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </label>
          )}
          <small>
            Choose the same file/cycle/car you are inspecting above.
          </small>
        </div>
      )}
      {result?.assistant_warning && (
        <p className="banner">{result.assistant_warning}</p>
      )}
      <div
        className="assistant-chat__messages"
        aria-live="polite"
        aria-busy={busy}
      >
        {messages.map((message, i) =>
          message.role === "user" ? (
            <div key={i} className="assistant-chat__user">
              {message.text}
            </div>
          ) : (
            <article className="assistant-chat__answer" key={i}>
              <strong>
                RailPulser{" "}
                <small>
                  {message.result.presentation === "verified_definition"
                    ? "Verified definition"
                    : message.result.mode === "grounded_llm"
                      ? "AI · cited evidence"
                      : "Local evidence"}
                </small>
              </strong>
              <p className="assistant-chat__text">{message.result.answer}</p>
              {message.result.clarification?.options?.map((o) => (
                <button
                  className="button"
                  disabled={busy}
                  key={o.question}
                  onClick={() =>
                    send(o.question, message.result.clarification.question)
                  }
                >
                  {o.label}
                </button>
              ))}
              {message.result.warnings
                ?.filter((w) => !message.result.reference_caveats?.includes(w))
                .map((w, j) => (
                  <p className="banner" key={j}>
                    {w}
                  </p>
                ))}
              <details>
                <summary>Sources & interpretation limits</summary>
                <p>{message.result.dataset_label}</p>
                {message.result.facts?.map((f) => (
                  <div className="assistant-chat__source" key={f.id}>
                    <small>
                      {f.source}
                      {f.line_start
                        ? ` · lines ${f.line_start}–${f.line_end}`
                        : ""}
                    </small>
                    <p>{f.source_quote || f.text}</p>
                  </div>
                ))}
                <p>{message.result.limitations?.join(" ")}</p>
                {message.result.reference_caveats?.map((c) => (
                  <p key={c}>{c}</p>
                ))}
              </details>
            </article>
          ),
        )}
        {busy && <p className="muted">Checking the selected evidence…</p>}
        <div ref={bottom} />
      </div>
      <div className="assistant-chat__tools">
        {[
          ["instructions", "Instructions"],
          ["queries", "Sample queries"],
          ["model", selectedModel?.name || "Local · no API key"],
        ].map(([id, label]) => (
          <button
            key={id}
            className="button"
            aria-expanded={panel === id}
            aria-controls={`assistant-${subsystem}-${id}`}
            onClick={() => setPanel(panel === id ? null : id)}
          >
            {label} {panel === id ? "−" : "+"}
          </button>
        ))}
      </div>
      {panel && (
        <div
          className="assistant-chat__panel"
          id={`assistant-${subsystem}-${panel}`}
          onKeyDown={(e) => {
            if (e.key === "Escape") setPanel(null);
          }}
        >
          <button
            className="assistant-chat__close"
            aria-label="Close chat settings"
            onClick={() => setPanel(null)}
          >
            ×
          </button>
          {panel === "queries" && (
            <>
              <h4>{subsystem.toUpperCase()} sample questions</h4>
              {QUERIES[subsystem].map((q) => (
                <button
                  className="assistant-chat__sample"
                  key={q}
                  onClick={() => {
                    setQuestion(q);
                    setPanel(null);
                    input.current?.focus();
                  }}
                >
                  {q} ↗
                </button>
              ))}
            </>
          )}
          {panel === "instructions" && (
            <>
              <label>
                Explanation preferences
                <textarea
                  maxLength={1500}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="Plain language; define terms; focus on quality…"
                />
              </label>
              <button type="button" className="link-button" onClick={() => setInstructions(DEFAULT_INSTRUCTIONS[subsystem])}>
                Restore {subsystem === "general" ? "General" : subsystem.toUpperCase()} defaults
              </button>
              <label>
                Unverified engineer notes
                <textarea
                  maxLength={2000}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </label>
              <label>
                Detail
                <select
                  value={detail}
                  onChange={(e) => setDetail(e.target.value)}
                >
                  <option value="concise">Concise</option>
                  <option value="detailed">Detailed</option>
                </select>
              </label>
              <small>
                Notes cannot change predictions, approve actions or override
                evidence. They are not sent to the provider.
              </small>
            </>
          )}
          {panel === "model" && (
            <>
              <label>
                Model
                <select
                  value={model}
                  onChange={(e) => {
                    setModel(e.target.value);
                    setApiKey("");
                    setConsent(false);
                  }}
                >
                  <option value="">Local evidence · no key needed</option>
                  {catalog.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.provider} · {m.name}
                    </option>
                  ))}
                </select>
              </label>
              {model && (
                <>
                  <label>
                    Provider API key
                    <input
                      type="password"
                      autoComplete="off"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                    />
                  </label>
                  <label className="assistant-chat__consent">
                    <input
                      type="checkbox"
                      checked={consent}
                      onChange={(e) => setConsent(e.target.checked)}
                    />
                    I authorise sending my question and selected evidence to
                    this provider.
                  </label>
                  <small>
                    Key stays in this component's memory and is cleared on
                    subsystem/workspace changes or reload. Raw recordings are
                    not uploaded to the provider.
                  </small>
                </>
              )}
            </>
          )}
        </div>
      )}
      {error && (
        <p className="banner banner--error">
          {error}{" "}
          <button className="link-button" onClick={load}>
            Retry connection
          </button>
        </p>
      )}
      <form
        className="assistant-chat__composer"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <textarea
          ref={input}
          aria-label="Message RailPulse"
          maxLength={2000}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={`Ask about ${subsystem.toUpperCase()}…`}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <div>
          <small>
            {subsystem.toUpperCase()} ·{" "}
            {selected ? selected.file_id : "Current subsystem"}
          </small>
          <button
            className="button button--primary"
            disabled={busy || !question.trim()}
            type="submit"
            aria-label="Send message"
          >
            ↑ Send
          </button>
        </div>
      </form>
      <p className="assistant-chat__boundary">
        Read-only engineering support. Not a safety clearance, diagnosis
        confirmation or maintenance instruction.
      </p>
    </section>
  );
}

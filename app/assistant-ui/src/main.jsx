import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import SAMPLE_QUERIES from "./sampleQueries.json";

function Icon({ name, size = 18 }) {
  const paths = {
    plus: <path d="M12 5v14M5 12h14" />,
    arrow: <path d="M12 19V5m-6 6 6-6 6 6" />,
    chevron: <path d="m7 10 5 5 5-5" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    chat: <path d="M20 11a8 8 0 0 1-8 8H5l-3 3V11a9 9 0 0 1 18 0Z" />,
    shield: (
      <>
        <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
    book: (
      <>
        <path d="M12 5v15M12 5C8 2 3 4 3 4v15s5-2 9 1c4-3 9-1 9-1V4s-5-2-9 1Z" />
      </>
    ),
    rails: (
      <>
        <path d="M8 3 5 21M16 3l3 18M7 7h10M6 13h12M5 19h14" />
      </>
    ),
    key: (
      <>
        <circle cx="8" cy="8" r="5" />
        <path d="m12 12 9 9m-4-4 3-3m-6 0 3-3" />
      </>
    ),
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 6 6" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    panel: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <path d="M15 4v16" />
      </>
    ),
    door: (
      <>
        <rect x="5" y="3" width="14" height="18" rx="2" />
        <path d="M12 3v18M9 11v3M15 11v3" />
      </>
    ),
    acv: (
      <>
        <path d="M3 8h13a3 3 0 1 0-3-3M3 12h17M3 16h10a3 3 0 1 1-3 3" />
      </>
    ),
    shm: <path d="M2 12h4l3-7 5 14 3-7h5" />,
    rail: (
      <>
        <path d="m4 20 5-16m6 0 5 16M7 8h10M5 15h14" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.chat}
    </svg>
  );
}

const DOMAINS = [
  {
    id: "all",
    title: "All subsystems",
    note: "A complete picture",
    icon: "panel",
  },
  {
    id: "door",
    title: "Door operations",
    note: "Timing & resistance",
    icon: "door",
  },
  {
    id: "acv",
    title: "Air conditioning",
    note: "Car-level localisation",
    icon: "acv",
  },
  {
    id: "rail",
    title: "Rail corrugation",
    note: "Side I / Side II",
    icon: "rail",
  },
  {
    id: "shm",
    title: "Structural health",
    note: "Recording damage",
    icon: "shm",
  },
];
const STARTERS = [
  {
    icon: "panel",
    title: "Give me the big picture",
    text: "Summarise the findings in this batch",
    eyebrow: "BATCH BRIEFING",
  },
  {
    icon: "shield",
    title: "What needs a closer look?",
    text: "Show quality warnings and findings needing review",
    eyebrow: "REVIEW SUPPORT",
  },
  {
    icon: "book",
    title: "Understand the models",
    text: "Explain validation metrics and model selection",
    eyebrow: "MODEL EVIDENCE",
  },
  {
    icon: "shm",
    title: "Know the limits",
    text: "What information is missing for remaining life?",
    eyebrow: "RESPONSIBLE ANALYSIS",
  },
];

function ModelDialog({ models, current, onConnect, onClose }) {
  const dialog = useRef(null);
  const [selected, setSelected] = useState(current);
  const [search, setSearch] = useState("");
  const [key, setKey] = useState("");
  const [consent, setConsent] = useState(false);
  useEffect(() => {
    dialog.current.showModal();
  }, []);
  const choose = (value) => {
    setSelected(value);
    setKey("");
    setConsent(false);
  };
  return (
    <dialog
      ref={dialog}
      className="model-dialog"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === dialog.current) onClose();
      }}
    >
      <div className="dialog-heading">
        <div>
          <span className="eyebrow">YOUR WORKSPACE, YOUR MODEL</span>
          <h2>Choose your intelligence.</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close model picker"
        >
          <Icon name="close" />
        </button>
      </div>
      <label className="search-field">
        <Icon name="search" />
        <input
          autoFocus
          placeholder="Search models or providers"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search models"
        />
      </label>
      <div className="model-list">
        {!search && (
          <button
            className={`model-option ${!selected ? "chosen" : ""}`}
            onClick={() => choose(null)}
          >
            <span className="provider-symbol local">
              <Icon name="book" />
            </span>
            <span>
              <strong>Local evidence</strong>
              <small>Private, deterministic · no API key</small>
            </span>
            {!selected && <Icon name="check" />}
          </button>
        )}
        {["anthropic", "openai"]
          .filter((provider) =>
            models.some(
              (m) =>
                m.provider === provider &&
                `${m.name} ${m.provider}`
                  .toLowerCase()
                  .includes(search.toLowerCase()),
            ),
          )
          .map((provider) => (
            <section key={provider}>
              <h3>{provider === "openai" ? "OpenAI" : "Anthropic"}</h3>
              {models
                .filter(
                  (m) =>
                    m.provider === provider &&
                    `${m.name} ${m.provider}`
                      .toLowerCase()
                      .includes(search.toLowerCase()),
                )
                .map((model) => (
                  <button
                    key={model.id}
                    className={`model-option ${selected?.id === model.id ? "chosen" : ""}`}
                    onClick={() => choose(model)}
                  >
                    <span className={`provider-symbol ${provider}`}>
                      {provider === "openai" ? "◎" : "✳"}
                    </span>
                    <span>
                      <strong>{model.name}</strong>
                      <small>{model.description}</small>
                    </span>
                    <span className="tier">{model.tier}</span>
                    {selected?.id === model.id && <Icon name="check" />}
                  </button>
                ))}
            </section>
          ))}
      </div>
      <form
        className="connection"
        onSubmit={(e) => {
          e.preventDefault();
          onConnect(selected, key, consent);
          setKey("");
        }}
      >
        {selected ? (
          <>
            <label className="key-label" htmlFor="api-key">
              <Icon name="key" /> Your{" "}
              {selected.provider === "openai" ? "OpenAI" : "Anthropic"} API key
            </label>
            <input
              id="api-key"
              type="password"
              autoComplete="off"
              spellCheck="false"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="Paste your API key"
              required
              maxLength={512}
            />
            <label className="consent">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                required
              />
              <span>
                I allow my questions and compact evidence to be sent to this
                provider. API usage may incur charges.
              </span>
            </label>
            <p className="micro">
              Held in this tab’s memory only. Never saved in browser storage.
              Cleared on disconnect or reload. Account access to the selected
              model is required.
            </p>
          </>
        ) : (
          <p className="micro">
            Search and explain the audited evidence locally. No external model,
            no key, no provider charges.
          </p>
        )}
        <button
          className="primary full"
          disabled={!!selected && (!key.trim() || !consent)}
        >
          {selected ? `Use ${selected.name}` : "Use local evidence"}
          <Icon name="arrow" size={16} />
        </button>
      </form>
    </dialog>
  );
}

function visibleFacts(result) {
  return result.selected_citation_ids
    ? result.selected_citation_ids
        .map((id) => result.facts.find((f) => f.id === id))
        .filter(Boolean)
    : result.facts;
}

function FactContent({ fact }) {
  if (fact.value?.recordings !== undefined) {
    return (
      <div className="coverage-facts">
        {[
          ["Recordings", fact.value.recordings],
          ["Findings", fact.value.findings],
          ["For review", fact.value.review_required],
        ].map(([label, value]) => (
          <div key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </div>
    );
  }
  if (
    fact.source.startsWith("run_summary.json") ||
    fact.source === "outputs/shm/training_summary.json"
  ) {
    return (
      <>
        <p className="validation-label">
          {fact.source.includes("/validation/")
            ? fact.source.split("/").pop().toUpperCase()
            : "SHM"}{" "}
          · stored validation, not test performance
        </p>
        <dl className="validation-values">
          {Object.entries(fact.value || {}).map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>
                {value !== null && typeof value === "object" ? (
                  <details>
                    <summary>View breakdown</summary>
                    <pre>{JSON.stringify(value, null, 2)}</pre>
                  </details>
                ) : (
                  String(value)
                )}
              </dd>
            </div>
          ))}
        </dl>
      </>
    );
  }
  return <p>{fact.text}</p>;
}

function App() {
  const [context, setContext] = useState(null);
  const [error, setError] = useState("");
  const [domain, setDomain] = useState("all");
  const [file, setFile] = useState("");
  const [model, setModel] = useState(null);
  const [picker, setPicker] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [evidence, setEvidence] = useState(null);
  const [sidebar, setSidebar] = useState(false);
  const [instructions, setInstructions] = useState("");
  const [engineerContext, setEngineerContext] = useState("");
  const [author, setAuthor] = useState("");
  const [audience, setAudience] = useState("plain");
  const [detail, setDetail] = useState("concise");
  const [focus, setFocus] = useState("auto");
  const [helperPanel, setHelperPanel] = useState(null);
  const [queryGroup, setQueryGroup] = useState("All");
  const composerInput = useRef(null);
  const helperButtons = useRef({});
  const closeHelper = () => {
    const previous = helperPanel;
    setHelperPanel(null);
    helperButtons.current[previous]?.focus();
  };
  const useSample = (sample) => {
    setQuestion(sample);
    setHelperPanel(null);
    requestAnimationFrame(() => composerInput.current?.focus());
  };
  const credentials = useRef({ key: "", consent: false });
  const controller = useRef(null);
  const bottom = useRef(null);
  const load = () => {
    setError("");
    fetch("/api/assistant/context")
      .then((r) => {
        if (!r.ok)
          throw Error(
            "Evidence API is offline. Start the local backend on port 8766, then retry.",
          );
        return r.json();
      })
      .then((data) => {
        if (data.api_schema_version !== 4)
          throw Error(
            "The backend needs a restart to enable the local knowledge base. Restart your backend terminal, then retry connection.",
          );
        setContext(data);
      })
      .catch((error) =>
        setError(
          error.message ||
            "Evidence API unavailable. Restart the backend and retry.",
        ),
      );
  };
  useEffect(() => {
    load();
    return () => controller.current?.abort();
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);
  const reset = () => {
    controller.current?.abort();
    controller.current = null;
    setBusy(false);
    setMessages([]);
    setEvidence(null);
    setQuestion("");
    setSidebar(false);
    setEngineerContext("");
  };
  const switchDomain = (value) => {
    reset();
    setDomain(value);
    setFile("");
  };
  const connect = (value, key, consent) => {
    credentials.current = { key, consent };
    setModel(value);
    setPicker(false);
  };
  const send = async (text = question, previousQuestion = undefined) => {
    if (!text.trim() || busy || !context) return;
    if (context.api_schema_version !== 4) {
      setContext(null);
      setError(
        "The backend needs a restart to enable the local knowledge base. Restart your backend terminal, then retry connection.",
      );
      return;
    }
    setQuestion("");
    setError("");
    setBusy(true);
    setMessages((old) => [
      ...old,
      { role: "user", text, id: crypto.randomUUID() },
    ]);
    const request = new AbortController();
    controller.current = request;
    try {
      const response = await fetch("/api/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: request.signal,
        body: JSON.stringify({
          question: text,
          previous_question:
            previousQuestion ??
            messages.at(-1)?.result?.clarification?.question ??
            null,
          subsystem: file
            ? file.split(":")[0]
            : domain === "all"
              ? null
              : domain,
          file_ids: file ? [file.slice(file.indexOf(":") + 1)] : [],
          provider: model?.provider || null,
          model: model?.id || null,
          api_key: model ? credentials.current.key : null,
          consent: model ? credentials.current.consent : false,
          engineer_instructions: instructions,
          engineer_context: engineerContext,
          engineer_author: author,
          audience,
          detail,
          focus,
        }),
      });
      if (!response.ok)
        throw Error(
          "The request could not be completed. Check the selected scope or try local evidence.",
        );
      const result = await response.json();
      if (controller.current !== request) return;
      setMessages((old) => [
        ...old,
        { role: "assistant", result, id: crypto.randomUUID() },
      ]);
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      if (controller.current === request) {
        setBusy(false);
        controller.current = null;
      }
    }
  };
  const exportAnswer = (result) => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "railpulse-evidence.json";
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className={`workspace ${sidebar ? "nav-open" : ""}`}>
      {sidebar && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            reset();
          }}
        >
          <span className="brand-mark">
            <Icon name="rails" size={22} />
          </span>
          <span>
            railpulse<span className="brand-dot">.</span>
          </span>
          <span className="beta">LAB</span>
        </a>
        <button className="new-chat" onClick={reset}>
          <Icon name="plus" /> New conversation <span>↗</span>
        </button>
        <div className="nav-section">
          <span className="eyebrow">WORKSPACE</span>
          <button className="nav-item active" onClick={() => setSidebar(false)}>
            <Icon name="chat" /> Evidence assistant
            <span className="tiny-dot" />
          </button>
        </div>
        <div className="nav-section">
          <span className="eyebrow">EXPLORE SUBSYSTEMS</span>
          {DOMAINS.map((item) => (
            <button
              key={item.id}
              className={`domain-item ${domain === item.id ? "selected" : ""}`}
              onClick={() => switchDomain(item.id)}
            >
              <Icon name={item.icon} />
              <span>
                {item.title}
                <small>{item.note}</small>
              </span>
              {domain === item.id && <span className="selection-mark" />}
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="reference-card">
            <span className="reference-label">
              <span className="tiny-dot" /> REFERENCE WORKSPACE
            </span>
            <strong>Evidence, not assumptions.</strong>
            <p>
              Four specialist models.
              <br />
              One traceable conversation.
            </p>
            <span className="reference-count">
              {context
                ? `${context.record_count} findings available`
                : "Connecting to evidence…"}
              <Icon name="book" size={15} />
            </span>
            {context?.knowledge && (
              <p className="micro">
                Local knowledge: {context.knowledge.documents} documents ·{" "}
                {context.knowledge.chunks} passages
              </p>
            )}
          </div>
          <div className="profile">
            <span className="avatar">TB</span>
            <span>
              Team TrailBlazer<small>Local prototype</small>
            </span>
            <Icon name="shield" />
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              onClick={() => setSidebar(true)}
              aria-label="Open navigation"
            >
              <Icon name="panel" />
            </button>
            <span>Workspace</span>
            <span className="slash">/</span>
            <strong>Evidence assistant</strong>
          </div>
          <div className="top-actions">
            <span className="prototype-tag">PROTOTYPE</span>
            <button
              className="model-trigger"
              onClick={() => setPicker(true)}
              disabled={!context}
            >
              <span className={`model-dot ${model?.provider || "local"}`} />
              {model?.name || "Local evidence"}
              <Icon name="chevron" size={15} />
            </button>
          </div>
        </header>
        <div className="context-bar">
          <span>
            <Icon name="book" size={14} /> Audited reference replay{" "}
            <span className="context-separator">·</span> Not live telemetry
          </span>
          <label>
            <Icon name="panel" size={14} />
            <select
              aria-label="Recording scope"
              value={file}
              onChange={(e) => {
                reset();
                setFile(e.target.value);
              }}
            >
              <option value="">
                All {domain === "all" ? "" : domain.toUpperCase() + " "}
                recordings
              </option>
              {(context?.files || [])
                .filter((f) => domain === "all" || f.subsystem === domain)
                .map((f) => (
                  <option
                    key={`${f.subsystem}:${f.file_id}`}
                    value={`${f.subsystem}:${f.file_id}`}
                  >
                    {f.subsystem.toUpperCase()} · {f.file_id}
                  </option>
                ))}
            </select>
          </label>
        </div>
        <div
          className={`conversation ${messages.length ? "has-messages" : ""}`}
        >
          {!messages.length ? (
            <section className="welcome">
              <div className="hero-emblem">
                <Icon name="rails" size={33} />
                <span />
              </div>
              <div className="welcome-kicker">
                YOUR CONDITION-MONITORING COPILOT
              </div>
              <h1>
                A clearer view.
                <br />
                <em>A better question.</em>
              </h1>
              <p>
                Explore your train data with an assistant that
                <br className="desktop-break" /> shows its evidence, and knows
                its limits.
              </p>
              <div className="starter-grid">
                {STARTERS.map((item) => (
                  <button
                    className="starter"
                    key={item.title}
                    onClick={() => send(item.text)}
                    disabled={busy || !context}
                  >
                    <div>
                      <Icon name={item.icon} />
                      <span>↗</span>
                    </div>
                    <span className="eyebrow">{item.eyebrow}</span>
                    <strong>{item.title}</strong>
                  </button>
                ))}
              </div>
              <div className="grounding-note">
                <Icon name="shield" size={14} /> Grounded in results. Read-only
                by design.
              </div>
            </section>
          ) : (
            <div className="messages" aria-live="polite">
              {messages.map((message) =>
                message.role === "user" ? (
                  <div key={message.id} className="user-message">
                    {message.text}
                  </div>
                ) : (
                  <article key={message.id} className="assistant-message">
                    <div className="answer-heading">
                      <span className="answer-mark">
                        <Icon name="rails" size={18} />
                      </span>
                      <strong>RailPulse</strong>
                      <span>
                        {message.result.mode === "grounded_llm"
                          ? message.result.generated_explanation
                            ? "AI explanation · cited evidence"
                            : "LLM-selected evidence"
                          : message.result.presentation === "verified_definition"
                            ? "Verified definition"
                            : "Local evidence"}
                      </span>
                    </div>
                    <div className="answer-body">
                      <div
                        className="answer-intro"
                        style={{ whiteSpace: "pre-wrap" }}
                      >
                        {message.result.answer}
                      </div>
                      {message.result.answer_citation_ids?.map((id) => {
                        const fact = message.result.facts.find(
                          (item) => item.id === id,
                        );
                        return fact ? (
                          <button
                            className="source-chip"
                            key={id}
                            onClick={() =>
                              setEvidence({ fact, result: message.result })
                            }
                          >
                            <Icon name="book" size={12} />
                            {fact.source
                              .split("/")
                              .at(-1)
                              .replace(/\.md(#.*)?$/, "")}{" "}
                            ↗
                          </button>
                        ) : null;
                      })}
                      {message.result.routing && (
                        <p className="micro">
                          Route:{" "}
                          {message.result.routing.intent.replaceAll("_", " ")} ·
                          Scope:{" "}
                          {message.result.scope.subsystem ||
                            message.result.scope.subsystems.join(", ") ||
                            "No recordings"}
                        </p>
                      )}
                      {message.result.clarification?.options && (
                        <div
                          className="clarification-options"
                          aria-label="Clarification choices"
                        >
                          {message.result.clarification.options.map(
                            (option) => (
                              <button
                                key={option.question}
                                disabled={busy}
                                onClick={() =>
                                  send(
                                    option.label,
                                    message.result.clarification.question,
                                  )
                                }
                              >
                                {option.label}
                              </button>
                            ),
                          )}
                        </div>
                      )}
                      <details className="limits">
                        <summary>Source evidence & structured details</summary>
                        {visibleFacts(message.result)
                          .slice(0, 5)
                          .map((fact) => (
                            <div className="fact" key={fact.id}>
                              <FactContent fact={fact} />
                              {fact.evidence_type === "reference_document" && (
                                <p className="micro">
                                  Reference document · {fact.section} · lines{" "}
                                  {fact.line_start}–{fact.line_end}. Retrieval
                                  relevance is not confidence.
                                </p>
                              )}
                              <button
                                className="source-chip"
                                onClick={() =>
                                  setEvidence({ fact, result: message.result })
                                }
                              >
                                <Icon name="book" size={12} />
                                {fact.source.startsWith("decision:")
                                  ? "Recording evidence"
                                  : fact.source === "session"
                                    ? "Session snapshot"
                                    : fact.source}
                                <span>↗</span>
                              </button>
                            </div>
                          ))}
                        {visibleFacts(message.result).length > 5 && (
                          <p className="micro">
                            {visibleFacts(message.result).length - 5} more
                            source cards in the full evidence record.
                          </p>
                        )}
                        {message.result.reference_caveats?.map((note) => (
                          <p className="micro" key={note}>
                            {note}
                          </p>
                        ))}
                      </details>
                      {message.result.warnings
                        .filter(
                          (warning) =>
                            !message.result.reference_caveats?.includes(
                              warning,
                            ) || warning.startsWith("Theoretical Miner's-rule"),
                        )
                        .map((warning, i) => (
                          <p className="warning" key={i}>
                            {warning}
                          </p>
                        ))}
                      <details className="limits">
                        <summary>Interpretation limits</summary>
                        <p>{message.result.limitations.join(" ")}</p>
                      </details>
                      {message.result.engineer_input && (
                        <details className="limits">
                          <summary>
                            Engineer instructions & attributed context
                          </summary>
                          <p>{message.result.engineer_input.boundary}</p>
                          <p>
                            Applied:{" "}
                            {message.result.engineer_input.applied_hints.join(
                              "; ",
                            ) || "Selected presentation preferences"}
                          </p>
                          {message.result.engineer_input.instructions && (
                            <p>
                              Requested instructions:{" "}
                              {message.result.engineer_input.instructions}
                            </p>
                          )}
                          {message.result.engineer_input.context.text && (
                            <div className="engineer-note">
                              <strong>
                                {message.result.engineer_input.context.author} ·
                                unverified note
                              </strong>
                              <p>
                                {message.result.engineer_input.context.text}
                              </p>
                              <small>
                                Applies to this answer’s selected scope only;
                                not an approval or policy.
                              </small>
                            </div>
                          )}
                        </details>
                      )}
                      <div className="answer-actions">
                        <button
                          onClick={() =>
                            setEvidence({ result: message.result })
                          }
                        >
                          <Icon name="panel" size={15} /> View all sources
                        </button>
                        <button onClick={() => exportAnswer(message.result)}>
                          <Icon name="download" size={15} /> Export evidence
                        </button>
                      </div>
                    </div>
                  </article>
                ),
              )}
              {busy && (
                <div className="thinking">
                  <span className="answer-mark">
                    <Icon name="rails" size={18} />
                  </span>
                  <span>
                    Retrieving evidence<span className="thinking-dots">…</span>
                  </span>
                </div>
              )}
              <div ref={bottom} />
            </div>
          )}
        </div>
        <div className="composer-area">
          <div
            className="helper-workspace"
            onKeyDown={(event) => {
              if (event.key === "Escape" && helperPanel) {
                event.stopPropagation();
                closeHelper();
              }
            }}
          >
            <div className="helper-tabs" aria-label="Chat guidance">
              {[
                { id: "instructions", label: "Instructions", icon: "book" },
                { id: "queries", label: "Sample queries", icon: "chat" },
              ].map((item) => (
                <button
                  key={item.id}
                  type="button"
                  ref={(element) => {
                    helperButtons.current[item.id] = element;
                  }}
                  id={`helper-${item.id}-button`}
                  className={helperPanel === item.id ? "selected" : ""}
                  aria-expanded={helperPanel === item.id}
                  aria-controls={`helper-${item.id}`}
                  onClick={() =>
                    setHelperPanel(helperPanel === item.id ? null : item.id)
                  }
                >
                  <Icon name={item.icon} size={14} />
                  {item.label}
                  <span
                    className={`helper-chevron ${helperPanel === item.id ? "open" : ""}`}
                  >
                    <Icon name="chevron" size={13} />
                  </span>
                </button>
              ))}
            </div>
            <section
              id="helper-instructions"
              aria-labelledby="helper-instructions-button"
              hidden={helperPanel !== "instructions"}
              className="helper-panel"
            >
              <div className="helper-heading">
                <strong>Engineer instructions & context</strong>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Close instructions"
                  onClick={closeHelper}
                >
                  <Icon name="close" size={16} />
                </button>
              </div>
              <div className="engineer-controls">
                <div className="engineer-fields">
                  <label>
                    Explain for
                    <select
                      value={audience}
                      onChange={(e) => setAudience(e.target.value)}
                    >
                      <option value="plain">Non-technical reader</option>
                      <option value="technician">Technician</option>
                      <option value="engineer">Engineer</option>
                    </select>
                  </label>
                  <label>
                    Detail
                    <select
                      value={detail}
                      onChange={(e) => setDetail(e.target.value)}
                    >
                      <option value="concise">Concise</option>
                      <option value="detailed">Step by step</option>
                    </select>
                  </label>
                  <label>
                    Focus
                    <select
                      value={focus}
                      onChange={(e) => setFocus(e.target.value)}
                    >
                      <option value="auto">Follow my question</option>
                      <option value="quality">Data quality</option>
                      <option value="evaluation">Evaluation</option>
                      <option value="review">Review preparation</option>
                    </select>
                  </label>
                </div>
                <label className="engineer-label">
                  Explanation / investigation instructions
                  <textarea
                    value={instructions}
                    maxLength={1500}
                    onChange={(e) => setInstructions(e.target.value)}
                    placeholder="Explain for a technician; define acronyms; focus on ACV missing telemetry."
                  />
                </label>
                <p className="micro">
                  Supported hints: audience, concise/detailed, terminology and
                  quality/evaluation/review focus. Other directives are not
                  executed. A subsystem hint can narrow an unselected scope.
                </p>
                <label className="engineer-label">
                  Engineer name or role (self-reported)
                  <input
                    value={author}
                    maxLength={80}
                    onChange={(e) => setAuthor(e.target.value)}
                    placeholder="e.g. Duty engineer"
                  />
                </label>
                <label className="engineer-label">
                  Recording context / investigation notes
                  <textarea
                    value={engineerContext}
                    maxLength={2000}
                    onChange={(e) => setEngineerContext(e.target.value)}
                    placeholder="e.g. The recording was collected after servicing; sensor status still needs confirmation."
                  />
                </label>
                <p className="micro">
                  Notes are unverified, kept separate from evidence and not sent
                  to the optional provider. They appear in exported evidence.
                  Cleared on new conversation or scope change; never stored as
                  an approved rule.
                </p>
              </div>
            </section>
            <section
              id="helper-queries"
              aria-labelledby="helper-queries-button"
              hidden={helperPanel !== "queries"}
              className="helper-panel"
            >
              <div className="helper-heading">
                <strong>What can I ask RailPulse?</strong>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Close sample queries"
                  onClick={closeHelper}
                >
                  <Icon name="close" size={16} />
                </button>
              </div>
              <div className="query-library">
                <p className="query-intro">
                  1. Choose your subsystem or recording. 2. Pick a question. 3.
                  Review it and press Send. Samples never submit automatically
                  or change your scope.
                </p>
                <div
                  className="query-categories"
                  aria-label="Sample query categories"
                >
                  {[
                    "All",
                    ...new Set(SAMPLE_QUERIES.map((item) => item.group)),
                  ].map((group) => (
                    <button
                      key={group}
                      type="button"
                      aria-pressed={queryGroup === group}
                      onClick={() => setQueryGroup(group)}
                    >
                      {group}
                    </button>
                  ))}
                </div>
                {SAMPLE_QUERIES.filter(
                  (item) => queryGroup === "All" || item.group === queryGroup,
                ).map((item) => (
                  <button
                    className="sample-query"
                    type="button"
                    key={item.question}
                    aria-label={`Use sample: ${item.question}`}
                    onClick={() => useSample(item.question)}
                  >
                    <span className="eyebrow">{item.group}</span>
                    <strong>
                      {item.question}
                      <span aria-hidden="true">↗</span>
                    </strong>
                    <small>{item.help}</small>
                  </button>
                ))}
                <p className="query-limits">
                  Supports explanation and investigation preparation—not safety
                  clearance, approved maintenance instructions, or a confirmed
                  diagnosis. Existing instruction preferences still apply; check
                  them if an answer seems differently focused.
                </p>
              </div>
            </section>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
              {!context && <button onClick={load}>Retry connection</button>}
            </div>
          )}
          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <textarea
              aria-label="Message RailPulse"
              ref={composerInput}
              placeholder={`Ask about ${domain === "all" ? "your results" : DOMAINS.find((d) => d.id === domain).title.toLowerCase()}…`}
              value={question}
              maxLength={2000}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <div className="composer-bottom">
              <span className="scope-pill">
                <span className="tiny-dot" />
                {DOMAINS.find((d) => d.id === domain).title}
              </span>
              <div>
                <button
                  type="button"
                  className="composer-model"
                  onClick={() => setPicker(true)}
                  disabled={!context}
                >
                  {model?.name || "No API key needed"}
                  <Icon name="chevron" size={14} />
                </button>
                <button
                  type="submit"
                  className="send-button"
                  disabled={!question.trim() || busy || !context}
                  aria-label="Send message"
                >
                  <Icon name="arrow" size={20} />
                </button>
              </div>
            </div>
          </form>
          <div className="composer-footer">
            <span>
              Advisory only. Not a safety clearance. Each question uses the
              selected scope.
            </span>
            {model && (
              <button onClick={() => connect(null, "", false)}>
                Disconnect key
              </button>
            )}
          </div>
        </div>
      </main>
      {evidence && (
        <aside className="evidence-panel">
          <div className="evidence-header">
            <div>
              <span className="eyebrow">TRACEABLE BY DESIGN</span>
              <h2>Source notebook</h2>
            </div>
            <button
              className="icon-button"
              onClick={() => setEvidence(null)}
              aria-label="Close evidence"
            >
              <Icon name="close" />
            </button>
          </div>
          <p className="micro">
            Exact records from the audited reference replay.
          </p>
          {(evidence.fact ? [evidence.fact] : evidence.result.facts).map(
            (fact) => (
              <section key={fact.id} className="notebook-card">
                <span className="eyebrow">{fact.id}</span>
                <p>{fact.text}</p>
                <small>{fact.source}</small>
                {fact.value && (
                  <details>
                    <summary>Structured evidence</summary>
                    <pre>{JSON.stringify(fact.value, null, 2)}</pre>
                  </details>
                )}
              </section>
            ),
          )}
          <details className="provenance">
            <summary>Run & provenance</summary>
            <pre>{JSON.stringify(evidence.result.provenance, null, 2)}</pre>
          </details>
        </aside>
      )}
      {picker && (
        <ModelDialog
          models={context?.models || []}
          current={model}
          onConnect={connect}
          onClose={() => setPicker(false)}
        />
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);

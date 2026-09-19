import { useEffect, useRef, useState } from "react";
import AssistantChat from "./components/AssistantChat";
import "./App.css";
import Dropzone from "./components/Dropzone";
import DoorResults from "./components/DoorResults";
import AcvResults from "./components/AcvResults";
import RailResults from "./components/RailResults";
import ShmResults from "./components/ShmResults";
import RailDashboard from "./components/RailDashboard";
import Glossary, { Term } from "./components/Glossary";
import { TERMS } from "./terms";
import Icon from "./components/Icon";
import {
  getStatus,
  predictDoor,
  predictAcv,
  predictRail,
  predictShm,
  downloadCsv,
} from "./api";

// `icon` pairs every subsystem label with a glyph, so a tab is not identified
// by an acronym alone -- the acronyms themselves are defined in the glossary.
const SUBSYSTEMS = [
  {
    key: "door",
    label: "Door",
    icon: "door",
    accept: ".csv",
    hint: "Continuous door-controller stream (.csv)",
  },
  {
    key: "acv",
    label: "ACV",
    icon: "acv",
    term: "ACV",
    accept: ".xlsx",
    hint: "ACV case file (.xlsx)",
  },
  {
    key: "rail",
    label: "Rail corrugation",
    icon: "rail",
    accept: ".csv",
    hint: "1-second axle-box recording (.csv) -- select all at once",
  },
  {
    key: "shm",
    label: "SHM",
    icon: "shm",
    term: "SHM",
    accept: ".csv",
    hint: "Headerless stress recordings (.csv) -- select all at once",
  },
];

const PREDICTORS = {
  door: predictDoor,
  acv: predictAcv,
  rail: predictRail,
  shm: predictShm,
};
const RESULT_COMPONENTS = {
  door: DoorResults,
  acv: AcvResults,
  rail: RailResults,
  shm: ShmResults,
};
const SUBMISSION_FILENAMES = {
  door: "door_predictions.csv",
  acv: "acv_predictions.csv",
  rail: "rail_predictions.csv",
  shm: "shm_predictions.csv",
};

export default function App() {
  const [active, setActive] = useState("door");
  const [status, setStatus] = useState(null);
  const [files, setFiles] = useState([]);
  const [results, setResults] = useState({});
  const [workspaceDomain, setWorkspaceDomain] = useState("general");
  const generation = useRef(0);
  const result = results[active] || null;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  function switchSubsystem(key) {
    setActive(key);
    setFiles([]);
    generation.current += 1;
    setLoading(false);
    setError(null);
  }

  async function runPrediction() {
    const request = ++generation.current;
    const domain = active;
    setLoading(true);
    setError(null);
    setResults((old) => ({ ...old, [domain]: null }));
    try {
      const data = await PREDICTORS[active](files);
      if (request === generation.current)
        setResults((old) => ({ ...old, [domain]: data }));
    } catch (e) {
      if (request === generation.current) setError(e.message);
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }

  const current = SUBSYSTEMS.find((s) => s.key === active);
  const ResultComponent = RESULT_COMPONENTS[active];
  const subsystemStatus = status?.[active];

  return (
    <div className="page">
      <header className="header">
        <div className="header__row">
          <h1>RailPulse</h1>
          <Glossary />
        </div>
        <p className="subtitle">
          Upload the held-out test set for a subsystem and see which files or
          cycles are flagged with a fault.
        </p>
      </header>

      {status?._demo && (
        <p className="banner">
          Public hackathon demo · use non-sensitive recordings only. Maximum 8 files / 24 MiB per batch.
          Uploads are temporary; results expire after an hour or a service restart.
          API keys are optional and remain in session memory. Advisory only—not a safety clearance.
        </p>
      )}

      <nav className="tabs">
        {SUBSYSTEMS.map((s) => (
          <button
            key={s.key}
            className={`tab${active === s.key ? " tab--active" : ""}`}
            disabled={s.disabled}
            onClick={() => switchSubsystem(s.key)}
          >
            <Icon name={s.icon} size={15} />
            {s.label}
          </button>
        ))}
        <button
          className={`tab${active === "assistant" ? " tab--active" : ""}`}
          onClick={() => switchSubsystem("assistant")}
        >
          Assistant workspace
        </button>
      </nav>

      {active === "assistant" ? (
        <main className="card">
          <label className="assistant-workspace-scope">
            Subsystem{" "}
            <select
              value={workspaceDomain}
              onChange={(e) => setWorkspaceDomain(e.target.value)}
            >
              <option value="general">General</option>
              {SUBSYSTEMS.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <AssistantChat
            key={`workspace-${workspaceDomain}-${results[workspaceDomain]?.assistant_snapshot || "empty"}`}
            subsystem={workspaceDomain}
            result={results[workspaceDomain]}
            workspace
          />
        </main>
      ) : (
        <main className="card">
          <h2 className="subsystem">
            <Icon name={current.icon} size={19} />
            {current.term ? (
              <>
                <Term k={current.term} />{" "}
                <span className="subsystem__expansion">
                  {TERMS[current.term].expansion}
                </span>
              </>
            ) : (
              current.label
            )}
          </h2>
          {current.disabled ? (
            <p className="muted">This subsystem isn't implemented yet.</p>
          ) : (
            <>
              {active === "rail" && (
                <RailDashboard data={result} status={subsystemStatus} />
              )}
              {subsystemStatus && !subsystemStatus.available && (
                <p className="banner banner--error">
                  No trained model registered for {current.label}. Run the
                  matching <code>scripts/train_*.py</code> first.
                </p>
              )}
              {subsystemStatus?.fold_scores && (
                <p className="muted">
                  Model score:{" "}
                  {Object.entries(subsystemStatus.fold_scores)
                    .filter(([k]) => !k.endsWith("_per_fold"))
                    .map(
                      ([k, v]) =>
                        `${k} = ${typeof v === "number" ? v.toFixed(3) : v}`,
                    )
                    .join(", ")}
                </p>
              )}

              <Dropzone
                accept={current.accept}
                multiple
                hint={current.hint}
                onFilesSelected={setFiles}
              />

              <button
                className="button button--primary"
                disabled={files.length === 0 || loading}
                onClick={runPrediction}
                style={{ marginTop: "1rem" }}
              >
                {loading ? "Running..." : "Run fault detection"}
              </button>

              {error && (
                <p
                  className="banner banner--error"
                  style={{ marginTop: "1rem" }}
                >
                  {error}
                </p>
              )}

              {result && (
                <div style={{ marginTop: "1.5rem" }}>
                  <ResultComponent data={result} />
                  <button
                    className="button"
                    style={{ marginTop: "1rem" }}
                    onClick={() =>
                      downloadCsv(
                        SUBMISSION_FILENAMES[active],
                        result.submission_csv,
                      )
                    }
                  >
                    Download {SUBMISSION_FILENAMES[active]}
                  </button>
                </div>
              )}
            </>
          )}
          <AssistantChat
            key={`${active}-${result?.assistant_snapshot || "empty"}`}
            subsystem={active}
            result={result}
          />
        </main>
      )}
    </div>
  );
}

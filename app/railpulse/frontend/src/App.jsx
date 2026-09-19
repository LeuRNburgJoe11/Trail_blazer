import { useEffect, useState } from "react";
import "./App.css";
import Dropzone from "./components/Dropzone";
import DoorResults from "./components/DoorResults";
import AcvResults from "./components/AcvResults";
import RailResults from "./components/RailResults";
import Glossary, { Term } from "./components/Glossary";
import { TERMS } from "./terms";
import Icon from "./components/Icon";
import { getStatus, predictDoor, predictAcv, predictRail, downloadCsv } from "./api";

// `icon` pairs every subsystem label with a glyph, so a tab is not identified
// by an acronym alone -- the acronyms themselves are defined in the glossary.
const SUBSYSTEMS = [
  { key: "door", label: "Door", icon: "door", accept: ".csv", hint: "Continuous door-controller stream (.csv)" },
  { key: "acv", label: "ACV", icon: "acv", term: "ACV", accept: ".xlsx", hint: "ACV case file (.xlsx)" },
  { key: "rail", label: "Rail corrugation", icon: "rail", accept: ".csv", hint: "1-second axle-box recording (.csv) -- select all at once" },
  { key: "shm", label: "SHM", icon: "shm", term: "SHM", disabled: true, hint: "Not implemented yet" },
];

const PREDICTORS = { door: predictDoor, acv: predictAcv, rail: predictRail };
const RESULT_COMPONENTS = { door: DoorResults, acv: AcvResults, rail: RailResults };
const SUBMISSION_FILENAMES = { door: "door_predictions.csv", acv: "acv_predictions.csv", rail: "rail_predictions.csv" };

export default function App() {
  const [active, setActive] = useState("door");
  const [status, setStatus] = useState(null);
  const [files, setFiles] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  function switchSubsystem(key) {
    setActive(key);
    setFiles([]);
    setResult(null);
    setError(null);
  }

  async function runPrediction() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await PREDICTORS[active](files);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
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
        <p className="subtitle">Upload the held-out test set for a subsystem and see which files or cycles are flagged with a fault.</p>
      </header>

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
      </nav>

      <main className="card">
        <h2 className="subsystem">
          <Icon name={current.icon} size={19} />
          {current.term ? (
            <>
              <Term k={current.term} />{" "}
              <span className="subsystem__expansion">{TERMS[current.term].expansion}</span>
            </>
          ) : (
            current.label
          )}
        </h2>
        {current.disabled ? (
          <p className="muted">This subsystem isn't implemented yet.</p>
        ) : (
          <>
            {subsystemStatus && !subsystemStatus.available && (
              <p className="banner banner--error">
                No trained model registered for {current.label}. Run the matching <code>scripts/train_*.py</code> first.
              </p>
            )}
            {subsystemStatus?.fold_scores && (
              <p className="muted">
                Model score:{" "}
                {Object.entries(subsystemStatus.fold_scores)
                  .filter(([k]) => !k.endsWith("_per_fold"))
                  .map(([k, v]) => `${k} = ${typeof v === "number" ? v.toFixed(3) : v}`)
                  .join(", ")}
              </p>
            )}

            <Dropzone accept={current.accept} multiple hint={current.hint} onFilesSelected={setFiles} />

            <button
              className="button button--primary"
              disabled={files.length === 0 || loading}
              onClick={runPrediction}
              style={{ marginTop: "1rem" }}
            >
              {loading ? "Running..." : "Run fault detection"}
            </button>

            {error && <p className="banner banner--error" style={{ marginTop: "1rem" }}>{error}</p>}

            {result && (
              <div style={{ marginTop: "1.5rem" }}>
                <ResultComponent data={result} />
                <button
                  className="button"
                  style={{ marginTop: "1rem" }}
                  onClick={() => downloadCsv(SUBMISSION_FILENAMES[active], result.submission_csv)}
                >
                  Download {SUBMISSION_FILENAMES[active]}
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

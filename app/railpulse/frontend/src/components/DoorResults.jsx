import { useState } from "react";
import DoorTrace from "./DoorTrace";
import DoorSchematic from "./DoorSchematic";
import Icon from "./Icon";

/**
 * One reviewable finding per door cycle: status, when it happened, and the
 * indicator behind the call -- not just "abnormal resistance".
 *
 * Confidence is opt-in and off by default. The model's score is an uncalibrated
 * ExtraTrees class vote, not a validated probability of correctness, so it is
 * shown only when an engineer asks for it and is labelled for what it is.
 */
function StatusBadge({ status }) {
  const fault = status !== "Normal";
  return (
    <span className={`status ${fault ? "status--fault" : "status--clear"}`}>
      <span className="status__dot" />
      {status}
    </span>
  );
}

function Cycle({ row, showConfidence }) {
  const [open, setOpen] = useState(false);
  const fault = row.prediction !== "Normal";
  const evidence = row.evidence ?? {};
  const regions = evidence.regions ?? [];
  const confidence = row.confidence;

  return (
    <div className={`cycle${fault ? " cycle--fault" : ""}`}>
      <div className="cycle__head">
        <StatusBadge status={row.prediction} />
        <span className="cycle__when">
          {evidence.start_clock ?? row.start_time} <span className="cycle__arrow">&rarr;</span>{" "}
          {evidence.end_clock ?? row.end_time}
        </span>
        <span className="cycle__meta">
          {evidence.operation ? `${evidence.operation} · ` : ""}
          {evidence.duration_seconds ? `${evidence.duration_seconds.toFixed(2)} s` : ""}
        </span>
        {showConfidence && (
          <span className="cycle__confidence" title="Uncalibrated ExtraTrees class score. Not a validated probability of correctness.">
            {confidence === null || confidence === undefined
              ? "score n/a"
              : `score ${(confidence * 100).toFixed(0)}%`}
          </span>
        )}
        <button className="cycle__toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "Hide evidence" : "Show evidence"}
        </button>
      </div>

      {evidence.reason && <p className="cycle__reason">{evidence.reason}</p>}

      {open && (
        <div className="cycle__evidence">
          {evidence.motion && (
            <>
              <h4 className="section-label">Replay &mdash; what the leaves did</h4>
              <DoorSchematic
                motion={evidence.motion}
                trace={evidence.trace}
                status={row.prediction}
                operation={evidence.operation}
              />
            </>
          )}

          {evidence.trace?.length > 0 && (
            <DoorTrace
              trace={evidence.trace}
              regions={regions}
              status={row.prediction}
              startClock={evidence.start_clock}
            />
          )}

          {regions.length > 0 && (
            <>
              <h4 className="section-label">Intervals above the Normal envelope</h4>
              <ul className="interval-list">
                {regions.map((region) => (
                  <li key={`${region.start_offset}-${region.end_offset}`}>
                    <span className="interval-list__time">
                      {region.start_clock} &rarr; {region.end_clock}
                    </span>
                    <span className="interval-list__len">{region.seconds.toFixed(2)} s</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {evidence.indicators?.length > 0 && (
            <>
              <h4 className="section-label">Indicators against Normal {evidence.operation?.toLowerCase()} cycles</h4>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Indicator</th>
                      <th>This cycle</th>
                      <th>Normal median</th>
                      <th>Ratio</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidence.indicators.map((indicator) => (
                      <tr key={indicator.name}>
                        <td>{indicator.label}</td>
                        <td>{indicator.value.toLocaleString()}{indicator.unit}</td>
                        <td>{indicator.normal_median.toLocaleString()}{indicator.unit}</td>
                        <td className={indicator.ratio > 1.05 ? "ratio ratio--high" : "ratio"}>
                          {indicator.ratio === null ? "--" : `${indicator.ratio.toFixed(2)}x`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {/* Per cycle, only what differs between cycles. The method behind the
              comparison is stated once for the whole panel, not on every card. */}
          <p className="cycle__source">
            {[row.source_file, evidence.n_samples ? `${evidence.n_samples} samples` : null,
              evidence.motion?.available ? `${evidence.motion.peak_current} mA peak` : null]
              .filter(Boolean).join(" · ")}
          </p>
        </div>
      )}
    </div>
  );
}

export default function DoorResults({ data }) {
  const [showConfidence, setShowConfidence] = useState(false);
  if (!data) return null;
  const rows = data.rows ?? [];
  const abnormal = rows.filter((r) => r.prediction !== "Normal").length;

  return (
    <div>
      <div className="door__summary">
        <p className="headline">
          <strong>{rows.length} door cycles</strong> detected &mdash;{" "}
          {abnormal > 0 ? (
            <strong className="status status--fault">
              <span className="status__dot" />
              {abnormal} abnormal resistance
            </strong>
          ) : (
            <strong className="status status--clear">
              <span className="status__dot" />
              none flagged
            </strong>
          )}
        </p>
        <label className="opt-in" title="Uncalibrated model score, off by default">
          <input type="checkbox" checked={showConfidence} onChange={(e) => setShowConfidence(e.target.checked)} />
          <Icon name="info" size={14} />
          Show model score
        </label>
      </div>

      {showConfidence && (
        <p className="banner banner--caution">
          The score is the classifier&apos;s uncalibrated class vote, not a validated probability that the
          call is correct. Treat it as a tie-breaker for review order, never as evidence on its own.
        </p>
      )}

      {rows.map((row, index) => (
        <Cycle key={`${row.start_time}-${index}`} row={row} showConfidence={showConfidence} />
      ))}

      {rows.length > 0 && (
        <p className="muted note door__method">
          Each cycle is compared with the median Normal cycle of the same operation from the
          labelled training segments. The Normal envelope is the 90th percentile of those cycles&apos;
          motor current at each point of cycle progress, so &ldquo;above envelope&rdquo; means this
          cycle drew more than roughly nine in ten Normal ones did at the same part of the stroke.
          The replay is measured leaf position and real switch states, not a simulation.
        </p>
      )}
    </div>
  );
}

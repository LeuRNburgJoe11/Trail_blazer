import { useState } from "react";
import { Term } from "./Glossary";

/**
 * Cumulative fatigue damage per recording.
 *
 * Damage is a MAGNITUDE, not a status, so the bars use one hue scaled by length
 * rather than the red/amber/neutral status code used elsewhere in the app.
 * Painting them as severity tiers would assert inspection bands that do not
 * exist for this fleet -- docs/DECISION_LAYER.md rules out operational alert
 * thresholds without domain-approved policy, and the pipeline's own metadata
 * says the value is "not remaining life or a maintenance deadline".
 *
 * The one reference line drawn is D = 1.0, which is Palmgren-Miner's own
 * crack-initiation criterion -- part of the method, not a maintenance policy.
 */
const MINER_LIMIT = 1.0;

function MethodCard({ entry, index }) {
  return (
    <div className="method">
      <span className="method__step">Step {index + 1} &middot; {entry.step}</span>
      <h4 className="method__title">{entry.title}</h4>
      <p className="method__detail">{entry.detail}</p>
    </div>
  );
}

function Recording({ row }) {
  const [open, setOpen] = useState(false);
  const evidence = row.evidence ?? {};
  const damage = row.prediction;
  const share = Math.max(0, Math.min(1, damage / MINER_LIMIT));

  return (
    <div className={`rec${row.warnings?.length ? " rec--warned" : ""}`}>
      <div className="rec__row">
        <span className="rec__file">{row.file_id}</span>
        <div className="rec__track" title={`${(share * 100).toFixed(1)}% of the Miner limit D = 1.0`}>
          <div className="rec__fill" style={{ width: `${share * 100}%` }} />
        </div>
        <span className="rec__value">{damage.toFixed(4)}</span>
        <button className="rec__toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "Hide" : "Evidence"}
        </button>
      </div>

      {row.warnings?.length > 0 && (
        <p className="rec__warning">{row.warnings.join(" ")}</p>
      )}

      {open && (
        <div className="rec__evidence">
          <dl className="rec__grid">
            <Pair label="Samples" value={evidence.n_samples?.toLocaleString()} />
            <Pair label="Rainflow cycles" value={evidence.cycle_count?.toLocaleString()} />
            <Pair label="Half-cycle fraction" value={fmt(evidence.half_cycle_fraction, 3)} />
            <Pair label="Amplitude p90" value={fmt(evidence.amplitude_q90, 2)} />
            <Pair label="Amplitude p99" value={fmt(evidence.amplitude_q99, 2)} />
            <Pair label="Amplitude max" value={fmt(evidence.amplitude_max, 2)} />
            <Pair label="Stress RMS" value={fmt(evidence.stress_rms, 2)} />
            <Pair label="Stress std" value={fmt(evidence.stress_std, 2)} />
            <Pair label="Exponent used" value={fmt(evidence.effective_exponent, 1)} />
          </dl>
          <p className="muted note">
            {row.metadata?.model && <>Model <code>{row.metadata.model}</code>. </>}
            {row.metadata?.stress_units && <>Stress units: {row.metadata.stress_units}. </>}
            {row.metadata?.interpretation}
          </p>
        </div>
      )}
    </div>
  );
}

function Pair({ label, value }) {
  return (
    <div className="pair">
      <dt>{label}</dt>
      <dd>{value ?? "—"}</dd>
    </div>
  );
}

function fmt(value, digits) {
  return value === null || value === undefined ? null : Number(value).toFixed(digits);
}

export default function ShmResults({ data }) {
  if (!data) return null;
  const rows = [...(data.rows ?? [])].sort((a, b) => b.prediction - a.prediction);
  if (rows.length === 0) return null;

  const method = data.method ?? {};
  const highest = rows[0];
  const lowest = rows[rows.length - 1];
  const maxDamage = highest.prediction;
  const exponent = highest.evidence?.effective_exponent;

  // The sensitivity argument, computed from these two recordings rather than
  // quoted from an example: damage scales with amplitude to the exponent.
  const hiAmp = highest.evidence?.amplitude_max;
  const loAmp = lowest.evidence?.amplitude_max;
  const ampRatio = hiAmp && loAmp ? hiAmp / loAmp : null;
  const damageRatio = lowest.prediction > 0 ? highest.prediction / lowest.prediction : null;

  return (
    <div className="shm">
      <p className="headline">
        <strong>{rows.length} recordings</strong> analysed &mdash; cumulative fatigue damage{" "}
        <strong>{lowest.prediction.toFixed(3)}</strong> to <strong>{maxDamage.toFixed(3)}</strong>.
      </p>

      {method.steps?.length > 0 && (
        <>
          <h3 className="section-label">How the damage index is computed</h3>
          <div className="methods">
            {method.steps.map((entry, index) => (
              <MethodCard key={entry.step} entry={entry} index={index} />
            ))}
          </div>
        </>
      )}

      <h3 className="section-label">Damage per recording, against the Miner limit</h3>
      <div className="recs">
        {rows.map((row) => (
          <Recording key={row.file_id} row={row} />
        ))}
      </div>
      <p className="muted note">
        Bars are scaled to <strong>D = 1.0</strong>, the Palmgren&ndash;Miner crack-initiation
        criterion. That is the method&apos;s own reference point, not an inspection trigger.
      </p>

      {ampRatio && exponent && (
        <div className="callout">
          <h4 className="callout__title">Why the spread is so wide</h4>
          <p>
            Damage scales with stress amplitude raised to the power{" "}
            <strong>{exponent.toFixed(1)}</strong>, so small differences in peak stress dominate the
            result. <code>{highest.file_id}</code> peaks at {hiAmp.toFixed(1)} against{" "}
            {loAmp.toFixed(1)} for <code>{lowest.file_id}</code> &mdash; a{" "}
            <strong>{ampRatio.toFixed(2)}&times;</strong> amplitude ratio, which raised to the power{" "}
            {exponent.toFixed(1)} is about <strong>{Math.pow(ampRatio, exponent).toFixed(0)}&times;</strong>.
            {damageRatio && (
              <> The damage values actually differ by {damageRatio.toFixed(0)}&times;. The two do not
              match because D sums amplitude<sup>{exponent.toFixed(0)}</sup> over every counted
              cycle, so the peak is an illustration of the sensitivity rather than the whole sum &mdash;
              the full amplitude distribution and the cycle count ({highest.evidence.cycle_count.toLocaleString()}{" "}
              against {lowest.evidence.cycle_count.toLocaleString()}) decide the rest.</>
            )}
          </p>
        </div>
      )}

      {method.caveats?.length > 0 && (
        <div className="caveats">
          <h4 className="caveats__title">What this number is not</h4>
          <ul>
            {method.caveats.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </div>
      )}

      <p className="muted note">
        <Term k="SHM" /> damage is reported per recording and is dimensionless, because the source
        data carries no stress units. Values are comparable between these files and not to any
        other fleet or dataset.
      </p>
    </div>
  );
}

import { useState } from "react";
import TrainDiagram from "./TrainDiagram";
import ConsistChecklist from "./ConsistChecklist";
import AcvCarDetail from "./AcvCarDetail";
import AcvSummaryBar, { AcvValidationStrip } from "./AcvSummaryBar";
import { Term } from "./Glossary";

const MISSING = "Not reported";

/** Formation order, numeric where the IDs are numeric ("2" before "10"). */
function inFormationOrder(cars) {
  const numeric = cars.every((c) => /^\d+$/.test(c));
  return cars.slice().sort((a, b) => (numeric ? Number(a) - Number(b) : a.localeCompare(b)));
}

function temperature(value) {
  return value === null || value === undefined ? MISSING : `${value.toFixed(1)} °C`;
}

function whenever(stamp) {
  if (!stamp) return null;
  const parsed = new Date(stamp.replace(" ", "T"));
  if (Number.isNaN(parsed.getTime())) return stamp;
  return parsed.toLocaleString(undefined, {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

function Field({ label, value, tone = "" }) {
  return (
    <div className="field">
      <dt className="field__label">{label}</dt>
      <dd className={`field__value${tone ? ` field__value--${tone}` : ""}`}>{value}</dd>
    </div>
  );
}

/** One uploaded case file. Selection is per file, so two files do not fight. */
function AcvFile({ row, validation }) {
  const context = row.context ?? {};
  const flagged = row.flagged_car ?? row.ranked_cars[0];
  // Older payloads carry no consist block; fall back to bare ranking order.
  const consist = row.consist ?? {
    rows: inFormationOrder(row.ranked_cars).map((car) => ({
      car, position: Number(car), rank: row.ranked_cars.indexOf(car) + 1,
      score: row.display_scores[car] / 100, tier: car === flagged ? "primary" : "nominal",
      headline: "Indicator breakdown unavailable for this payload",
    })),
    cluster: [], near_tie_threshold: null, car_type_source: null,
  };
  const [selected, setSelected] = useState(flagged);
  const index = row.display_scores[flagged];
  const deviation = context.indoor_deviation_by_car?.[flagged];
  const window = [whenever(context.time_start), whenever(context.time_end)].filter(Boolean).join("  →  ");
  const selectedCar = consist.rows.find((car) => car.car === selected) ?? consist.rows[0];

  return (
    <div className="result">
      <p className="result__file">{row.file_id}</p>

      <AcvSummaryBar consist={consist} validation={validation} context={context} />

      <div className="io">
        <section className="io__box">
          <h3 className="io__title">Readings in</h3>
          <dl className="io__fields">
            <Field label="Train" value={context.train_number ?? MISSING} />
            <Field label="Window" value={window || MISSING} />
            <Field label="Samples" value={context.n_samples ? context.n_samples.toLocaleString() : MISSING} />
            <Field label="Outdoor air" value={temperature(context.outdoor_temp)} />
            <Field label="Cooling setpoint" value={temperature(context.cooling_setpoint)} />
            <Field label="Running mode" value={context.running_mode ?? MISSING} />
            <Field label="Control" value={context.setting_mode ?? MISSING} />
            <Field
              label="Signals used"
              value={[context.temp_signal, context.pressure_signal].filter(Boolean).join(", ") || MISSING}
            />
          </dl>
        </section>

        <section className="io__box io__box--fault">
          <h3 className="io__title">Assessment out</h3>
          <dl className="io__fields">
            <Field label="Status" value="Anomaly detected" tone="fault" />
            <Field label="Location" value={`Car ${flagged}`} tone="fault" />
            <Field label="Suspicion index" value={`${index} / 100`} tone="fault" />
            <Field
              label="Lead over next car"
              value={row.lead_over_next === null || row.lead_over_next === undefined
                ? MISSING
                : `${row.lead_over_next} points over Car ${row.ranked_cars[1]}`}
            />
            <Field
              label="Cabin air vs peers"
              value={deviation === null || deviation === undefined
                ? MISSING
                : `${deviation > 0 ? "+" : ""}${deviation.toFixed(1)} °C`}
            />
            <Field label="Fleet cabin median" value={temperature(context.indoor_temp_median)} />
          </dl>
        </section>
      </div>

      <h3 className="section-label">Where &mdash; train formation</h3>
      <TrainDiagram
        cars={consist.rows}
        cluster={consist.cluster}
        nearTieThreshold={consist.near_tie_threshold}
        selected={selected}
        onSelect={setSelected}
      />

      <AcvCarDetail car={selectedCar} series={row.series} />

      <ConsistChecklist
        cars={consist.rows}
        nearTieThreshold={consist.near_tie_threshold}
        selected={selected}
        onSelect={setSelected}
      />

      <h3 className="section-label">Why &mdash; ranking across all cars</h3>
      <div className="bar-chart">
        {row.ranked_cars.map((car) => (
          <div className="bar-row" key={car}>
            <span className="bar-row__label">{car}</span>
            <div className="bar-row__track">
              <div
                className={`bar-row__fill${car === flagged ? " bar-row__fill--fault" : ""}`}
                style={{ width: `${row.display_scores[car]}%` }}
              />
            </div>
            <span className="bar-row__value">{row.display_scores[car]}</span>
          </div>
        ))}
      </div>
      <p className="muted note">
        Cars are ranked by how far each one drifts from its context-matched peers on the signals
        listed above, measured in <Term k="MAD" /> units and averaged over the window. The
        suspicion index rescales those scores to 0&ndash;100 within this train, so it ranks cars
        against each other &mdash; it is not a probability of failure.
        {!context.pressure_signal &&
          " No refrigerant pressure parameter is present in this file, so the ranking rests on cabin temperature alone."}
      </p>

      <AcvValidationStrip validation={validation} />
    </div>
  );
}

export default function AcvResults({ data }) {
  if (!data) return null;
  return (
    <div>
      {data.rows.map((row) => (
        <AcvFile key={row.file_id} row={row} validation={data.validation} />
      ))}
    </div>
  );
}

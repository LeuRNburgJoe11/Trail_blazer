import TrainDiagram from "./TrainDiagram";
import { Term } from "./Glossary";

const MISSING = "Not reported";

/** Formation order, numeric where the IDs are numeric ("2" before "10"). */
function inFormationOrder(cars) {
  const numeric = cars.every((c) => /^\d+$/.test(c));
  return cars.slice().sort((a, b) => (numeric ? Number(a) - Number(b) : a.localeCompare(b)));
}

function temperature(value) {
  return value === null || value === undefined ? MISSING : `${value.toFixed(1)} \u00b0C`;
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

export default function AcvResults({ data }) {
  if (!data) return null;

  return (
    <div>
      {data.rows.map((row) => {
        const context = row.context ?? {};
        const flagged = row.flagged_car ?? row.ranked_cars[0];
        const cars = inFormationOrder(row.ranked_cars);
        const index = row.display_scores[flagged];
        const deviation = context.indoor_deviation_by_car?.[flagged];
        const window = [whenever(context.time_start), whenever(context.time_end)]
          .filter(Boolean)
          .join("  \u2192  ");

        return (
          <div key={row.file_id} className="result">
            <p className="result__file">{row.file_id}</p>

            <div className="io">
              <section className="io__box">
                <h3 className="io__title">Readings in</h3>
                <dl className="io__fields">
                  <Field label="Train" value={context.train_number ?? MISSING} />
                  <Field label="Window" value={window || MISSING} />
                  <Field
                    label="Samples"
                    value={context.n_samples ? context.n_samples.toLocaleString() : MISSING}
                  />
                  <Field label="Outdoor air" value={temperature(context.outdoor_temp)} />
                  <Field label="Cooling setpoint" value={temperature(context.cooling_setpoint)} />
                  <Field label="Running mode" value={context.running_mode ?? MISSING} />
                  <Field label="Control" value={context.setting_mode ?? MISSING} />
                  <Field
                    label="Signals used"
                    value={
                      [context.temp_signal, context.pressure_signal].filter(Boolean).join(", ") || MISSING
                    }
                  />
                </dl>
              </section>

              <section className="io__box io__box--fault">
                <h3 className="io__title">Assessment out</h3>
                <dl className="io__fields">
                  <Field label="Status" value="Anomaly detected" tone="fault" />
                  <Field label="Location" value={`Car ${flagged}`} tone="fault" />
                  <Field
                    label="Suspicion index"
                    value={`${index} / 100`}
                    tone="fault"
                  />
                  <Field
                    label="Lead over next car"
                    value={row.lead_over_next === null || row.lead_over_next === undefined
                      ? MISSING
                      : `${row.lead_over_next} points over Car ${row.ranked_cars[1]}`}
                  />
                  <Field
                    label="Cabin air vs peers"
                    value={
                      deviation === null || deviation === undefined
                        ? MISSING
                        : `${deviation > 0 ? "+" : ""}${deviation.toFixed(1)} \u00b0C`
                    }
                  />
                  <Field label="Fleet cabin median" value={temperature(context.indoor_temp_median)} />
                </dl>
              </section>
            </div>

            <h3 className="section-label">Where -- train formation</h3>
            <TrainDiagram
              cars={cars}
              flagged={flagged}
              faultLabel="Suspected refrigerant leak"
              faultValue={`Suspicion ${index}/100`}
              valueByCar={context.indoor_deviation_by_car}
              valueUnit={"\u00b0"}
              valueTitle={"Median cabin temperature minus the fleet median, in \u00b0C"}
            />

            <h3 className="section-label">Why -- ranking across all cars</h3>
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
              Cars are ranked by how far each one drifts from its context-matched peers on the
              signals listed above, measured in <Term k="MAD" /> units and averaged over the
              window. The suspicion index rescales those scores to 0-100 within this train, so it
              ranks cars against each other -- it is not a probability of failure.
              {!context.pressure_signal &&
                " No refrigerant pressure parameter is present in this file, so the ranking rests on cabin temperature alone."}
            </p>
          </div>
        );
      })}
    </div>
  );
}

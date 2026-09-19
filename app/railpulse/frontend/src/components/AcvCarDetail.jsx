import AcvTempChart from "./AcvTempChart";

/**
 * Per-car diagnostic for whichever car is selected in the consist.
 *
 * Every tile is a measured quantity with its own units. There is deliberately
 * no suction pressure, refrigerant weight or component-level leak location
 * here: the case files carry no pressure channel, and the model localises to a
 * CAR, never to a valve or a coil. Naming a component would be a guess wearing
 * the costume of a reading.
 */
const TIER_HEADING = {
  primary: "Strongest peer-relative deviation in the consist",
  co_suspect: "Within a tie margin of the car above",
  nominal: "No separation from peers",
};

function Tile({ label, value, sub, tone }) {
  return (
    <div className="tile">
      <span className="tile__label">{label}</span>
      <span className={`tile__value${tone ? ` tile__value--${tone}` : ""}`}>{value}</span>
      {sub && <span className="tile__sub">{sub}</span>}
    </div>
  );
}

export default function AcvCarDetail({ car, series }) {
  if (!car) return null;
  const indicators = car.indicators ?? {};
  const tier = car.tier ?? "nominal";
  const residual = indicators.peer_residual_mean;
  const tone = tier === "primary" ? "fault" : tier === "co_suspect" ? "tie" : null;

  return (
    <section className={`detail detail--${tier}`}>
      <header className="detail__head">
        <div>
          <h3 className="detail__title">
            Car {car.car}
            <span className="detail__type"> · {car.car_type}</span>
          </h3>
          <p className="detail__sub">{TIER_HEADING[tier]}</p>
        </div>
        <span className={`pill pill--${tier}`}>
          {tier === "primary" ? "Primary suspect" : tier === "co_suspect" ? "Co-suspect" : "Nominal"}
          {car.rank ? ` · rank #${car.rank}` : ""}
        </span>
      </header>

      <p className="detail__summary">{car.summary}</p>

      <div className="tiles">
        <Tile
          label="Peer temperature gap"
          value={residual == null ? "—" : `${residual > 0 ? "+" : ""}${residual.toFixed(2)} °C`}
          sub="mean vs train median"
          tone={tone}
        />
        <Tile
          label="Warmest car"
          value={indicators.warmest_share == null ? "—" : `${indicators.warmest_share.toFixed(0)}%`}
          sub="of the recorded window"
          tone={tone}
        />
        <Tile
          label="Longest warm run"
          value={indicators.persistent_run_minutes == null ? "—" : `${indicators.persistent_run_minutes.toFixed(0)} min`}
          sub="unbroken above peers"
          tone={tone}
        />
        <Tile
          label="Ranking score"
          value={car.score == null ? "—" : car.score.toFixed(2)}
          sub="relative within this train"
          tone={tone}
        />
        <Tile
          label="Telemetry valid"
          value={indicators.telemetry_valid == null ? "—" : `${indicators.telemetry_valid.toFixed(0)}%`}
          sub="samples marked valid"
        />
      </div>

      <h4 className="section-label">Cabin temperature against the train</h4>
      <AcvTempChart series={series} car={car.car} tier={tier} />
    </section>
  );
}

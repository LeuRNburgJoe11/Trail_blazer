/**
 * Sequential car-by-car checklist, ordered Car 1 to Car N to match the order an
 * engineer walks the train at the depot -- not ranked order, which would send
 * them back and forth along the platform.
 *
 * The margin column is the point of the table: a rank is only worth acting on
 * if the car below it is actually separated, so a tight margin is called out
 * as a tie warning rather than hidden behind a confident-looking rank.
 */
const TIER_TEXT = { primary: "Primary Suspect", co_suspect: "Co-Suspect", nominal: "Nominal" };

export default function ConsistChecklist({ cars, nearTieThreshold }) {
  if (!cars || cars.length === 0) return null;

  return (
    <section className="checklist">
      <header className="checklist__head">
        <div>
          <h3 className="checklist__title">
            Consist fleet checklist (sequential Car {cars[0].position ?? 1} &rarr;{" "}
            {cars[cars.length - 1].position ?? cars.length})
          </h3>
          <p className="checklist__subtitle">Ordered for walk-through depot inspection routes</p>
        </div>
        <span className="checklist__count">{cars.length} cars monitored</span>
      </header>

      <div className="table-wrap">
        <table className="checklist__table">
          <thead>
            <tr>
              <th>Car (order)</th>
              <th>Rank</th>
              <th>Ranking score</th>
              <th>Margin (tie warning)</th>
              <th>Status</th>
              <th>Key physical indicator</th>
            </tr>
          </thead>
          <tbody>
            {cars.map((car) => {
              const tier = car.tier ?? "nominal";
              return (
                <tr key={car.car} className={`checklist__row checklist__row--${tier}`}>
                  <td className="checklist__car">
                    <strong>Car {car.position ?? car.car}</strong>
                    {car.car_type && <span className="checklist__type"> ({car.car_type})</span>}
                  </td>
                  <td className="checklist__rank">{car.rank == null ? "—" : `#${car.rank}`}</td>
                  <td className="checklist__score">{car.score == null ? "—" : car.score.toFixed(2)}</td>
                  <td>
                    {car.rank === 1 ? (
                      <span className="checklist__top">Top anomaly</span>
                    ) : car.near_tie ? (
                      <span className="pill pill--tie">
                        &Delta; = {car.margin_to_next?.toFixed(2)} (near tie)
                      </span>
                    ) : (
                      <span className="checklist__none">&mdash;</span>
                    )}
                  </td>
                  <td>
                    <span className={`pill pill--${tier}`}>{TIER_TEXT[tier]}</span>
                  </td>
                  <td className="checklist__indicator">{car.headline}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted note">
        Ranking score is the peer-residual index rescaled to 0&ndash;1 within this train, so it orders
        cars against each other and is not a probability of failure. A margin at or below{" "}
        {nearTieThreshold ?? 0.02} is flagged as a tie: the two cars are not meaningfully separated and
        both warrant a look.
      </p>
    </section>
  );
}

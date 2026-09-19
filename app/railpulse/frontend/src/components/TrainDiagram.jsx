/**
 * Consist diagram: cars in formation order, Car 1 (lead) to Car N (tail).
 *
 * Three status tiers, each with a word as well as a colour so the tier never
 * rests on hue alone: PRIMARY (red), CO-SUSPECT (amber), and the car type --
 * CAB or TRAILER -- in neutral ink when nothing is flagged. The co-suspect
 * bracket is drawn only when the ranking margin is genuinely tight; a clear
 * winner shows one red car and no bracket.
 */
const TIER_LABEL = { primary: "PRIMARY", co_suspect: "CO-SUSPECT" };

export default function TrainDiagram({ cars, cluster = [], nearTieThreshold, carTypeSource }) {
  if (!cars || cars.length === 0) return null;

  const clusterSet = new Set(cluster);
  // Bracket only CONTIGUOUS runs. Spanning min..max would draw a bracket over
  // nominal cars sitting between two suspects and imply they are included.
  const runs = [];
  cars.forEach((car, index) => {
    if (!clusterSet.has(car.car)) return;
    const last = runs[runs.length - 1];
    if (last && last.end === index - 1) last.end = index;
    else runs.push({ start: index, end: index });
  });
  const brackets = runs.filter((run) => run.end > run.start);
  const columns = { gridTemplateColumns: `repeat(${cars.length}, minmax(0, 1fr))` };
  const first = cars[0];
  const last = cars[cars.length - 1];

  return (
    <div className="consist">
      <p className="consist__caption">
        Showing Cars {first.position ?? 1} to {last.position ?? cars.length}, lead{" "}
        {(first.car_type ?? "car").toLowerCase()} to tail {(last.car_type ?? "car").toLowerCase()}
        {carTypeSource ? <span className="consist__assumed" title={carTypeSource}> (car type assumed)</span> : null}
      </p>

      {brackets.length > 0 && (
        <div className="consist__bracket-row" style={columns}>
          {brackets.map((run) => (
            <div
              key={run.start}
              className="consist__bracket"
              style={{ gridColumn: `${run.start + 1} / ${run.end + 2}` }}
            >
              <span className="consist__bracket-label">
                Thermal co-suspect cluster{nearTieThreshold ? ` (Δ ≤ ${nearTieThreshold})` : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="consist__cars" style={columns}>
        {cars.map((car) => {
          const tier = car.tier ?? "nominal";
          const label = TIER_LABEL[tier] ?? (car.car_type ?? "CAR").toUpperCase();
          return (
            <div className="consist__slot" key={car.car}>
              <span className="consist__position">{car.position ?? car.car}</span>
              <div
                className={`consist__car consist__car--${tier}`}
                title={
                  tier === "nominal"
                    ? `Car ${car.car} -- no anomaly detected`
                    : `Car ${car.car} -- ${label.toLowerCase()}`
                }
              >
                <span className="consist__car-label">{label}</span>
                {car.rank != null && <span className="consist__car-rank">#{car.rank}</span>}
              </div>
              <span className={`consist__score consist__score--${tier}`}>
                {car.score == null ? "—" : car.score.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="consist__legend">
        <span className="consist__key"><span className="consist__swatch consist__swatch--primary" /> Primary suspect</span>
        <span className="consist__key"><span className="consist__swatch consist__swatch--co_suspect" /> Co-suspect (near tie)</span>
        <span className="consist__key"><span className="consist__swatch consist__swatch--nominal" /> Nominal</span>
      </div>
    </div>
  );
}

export default function AcvResults({ data }) {
  if (!data) return null;

  return (
    <div>
      {data.rows.map((r) => {
        const topCar = r.ranked_cars[0];
        return (
          <div key={r.file_id} className="card" style={{ marginBottom: "1rem" }}>
            <p className="headline">
              <strong>{r.file_id}</strong> -- most likely faulty car:{" "}
              <span className="badge badge--danger">{topCar}</span> (suspicion {r.display_scores[topCar]}/100)
            </p>
            <div className="bar-chart">
              {r.ranked_cars.map((car) => (
                <div className="bar-row" key={car}>
                  <span className="bar-row__label">{car}</span>
                  <div className="bar-row__track">
                    <div
                      className={`bar-row__fill${car === topCar ? " bar-row__fill--danger" : ""}`}
                      style={{ width: `${r.display_scores[car]}%` }}
                    />
                  </div>
                  <span className="bar-row__value">{r.display_scores[car]}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

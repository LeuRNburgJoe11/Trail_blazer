/**
 * Eight-car train diagram (Car 1 to Car 8, in formation order).
 *
 * Colour code, shared with every other module: black = no anomaly detected,
 * red = anomaly detected. Nothing else in the diagram carries colour, so red
 * never has to compete for attention.
 */
export default function TrainDiagram({
  cars,
  flagged,
  faultLabel,
  faultValue,
  valueByCar,
  valueUnit = "",
  valueTitle = "",
}) {
  if (!cars || cars.length === 0) return null;
  const flaggedSet = new Set(Array.isArray(flagged) ? flagged : flagged ? [flagged] : []);

  return (
    <div className="train">
      <div className="train__cars">
        {cars.map((car) => {
          const isFlagged = flaggedSet.has(car);
          const value = valueByCar?.[car];
          return (
            <div className="train__slot" key={car}>
              <div
                className={`train__car${isFlagged ? " train__car--fault" : ""}`}
                title={isFlagged ? `Car ${car} -- anomaly detected` : `Car ${car} -- no anomaly detected`}
              >
                <span className="train__car-caption">Car</span>
                <span className="train__car-number">{car}</span>
                {value !== null && value !== undefined && (
                  <span className="train__car-value" title={valueTitle}>
                    {value > 0 ? "+" : ""}
                    {value}
                    {valueUnit}
                  </span>
                )}
              </div>
              {isFlagged && (
                <div className="train__fault">
                  {faultLabel && <span className="train__fault-label">{faultLabel}</span>}
                  {faultValue && <span className="train__fault-value">{faultValue}</span>}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="train__legend">
        <span className="train__key">
          <span className="train__swatch train__swatch--fault" /> Anomaly detected
        </span>
        <span className="train__key">
          <span className="train__swatch" /> No anomaly detected
        </span>
      </div>
    </div>
  );
}

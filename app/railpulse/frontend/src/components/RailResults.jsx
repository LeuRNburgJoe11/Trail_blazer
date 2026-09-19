import { useState } from "react";

export default function RailResults({ data }) {
  const [showAll, setShowAll] = useState(false);
  if (!data) return null;

  const flagged = data.rows.filter((r) => r.prediction !== "Normal");
  const sideI = flagged.filter((r) => r.prediction === "Side I").length;
  const sideII = flagged.filter((r) => r.prediction === "Side II").length;

  const badgeClass = (pred) =>
    pred === "Normal" ? "badge badge--neutral" : pred === "Side I" ? "badge badge--danger" : "badge badge--pink";

  const renderRows = (rows) =>
    rows.map((r) => (
      <tr key={r.file_id}>
        <td>{r.file_id}</td>
        <td>
          <span className={badgeClass(r.prediction)}>{r.prediction}</span>
        </td>
        <td>{r.side_scores["Side I"]}</td>
        <td>{r.side_scores["Side II"]}</td>
      </tr>
    ));

  return (
    <div>
      <p className="headline">
        <strong>
          {flagged.length} of {data.rows.length} files
        </strong>{" "}
        flagged with corrugation ({sideI} Side I, {sideII} Side II).
      </p>

      {flagged.length > 0 && (
        <>
          <p className="section-label">Flagged files</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Prediction</th>
                  <th>Side I score</th>
                  <th>Side II score</th>
                </tr>
              </thead>
              <tbody>{renderRows(flagged)}</tbody>
            </table>
          </div>
        </>
      )}

      <button className="link-button" onClick={() => setShowAll((v) => !v)}>
        {showAll ? "Hide" : "Show"} all {data.rows.length} files
      </button>
      {showAll && (
        <div className="table-wrap" style={{ marginTop: "0.75rem" }}>
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Prediction</th>
                <th>Side I score</th>
                <th>Side II score</th>
              </tr>
            </thead>
            <tbody>{renderRows(data.rows)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

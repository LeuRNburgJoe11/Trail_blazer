export default function DoorResults({ data }) {
  if (!data) return null;
  const abnormal = data.rows.filter((r) => r.prediction === "Abnormal resistance").length;

  return (
    <div>
      <p className="headline">
        <strong>{data.rows.length} cycles found</strong> across the uploaded file(s) --{" "}
        <strong className="badge badge--danger">{abnormal} flagged as abnormal resistance</strong>.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Start</th>
              <th>End</th>
              <th>Prediction</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r, i) => (
              <tr key={i}>
                <td>{r.source_file}</td>
                <td>{r.start_time}</td>
                <td>{r.end_time}</td>
                <td>
                  <span className={`badge ${r.prediction === "Normal" ? "badge--neutral" : "badge--danger"}`}>
                    {r.prediction}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

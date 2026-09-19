const TRAINING_CLASSES = [
  { label: "Normal", count: 234, tone: "clear" },
  { label: "Side I", count: 14, tone: "fault" },
  { label: "Side II", count: 24, tone: "fault-alt" },
];

function scoreText(value) {
  return typeof value === "number" ? value.toFixed(3) : "--";
}

export default function RailDashboard({ data, status }) {
  const rows = data?.rows || [];
  const counts = rows.reduce(
    (all, row) => ({ ...all, [row.prediction]: (all[row.prediction] || 0) + 1 }),
    { Normal: 0, "Side I": 0, "Side II": 0 },
  );
  const validation = data?.validation || status?.fold_scores;
  const modelScore = validation?.cv_macro_f1_mean;
  const foldScores = validation?.cv_macro_f1_per_fold || [];
  const maxFold = Math.max(0.001, ...foldScores);
  const flagged = rows.filter((row) => row.prediction !== "Normal");

  return (
    <section className="rail-dashboard" aria-label="Rail corrugation dashboard">
      <div className="rail-dashboard__intro">
        <div>
          <p className="eyebrow">Rail condition / side-aware review</p>
          <h3>Corrugation watch</h3>
          <p className="rail-dashboard__lede">
            Axle-box vibration is classified into Normal, Side I, or Side II. The layout below shows which sensor positions feed each rail-side decision.
          </p>
        </div>
        <div className="rail-dashboard__status">
          <span className="status-dot" />
          <span>{status?.available ? "Model ready" : "Model unavailable"}</span>
          <strong>{scoreText(modelScore)} CV macro F1</strong>
        </div>
      </div>

      <div className="rail-dashboard__hero">
        <div className="rail-dashboard__diagram">
          <img src="/rail-sensor-layout.png" alt="Eight axle-box positions across the train, with odd positions on Side I and even positions on Side II" />
          <div className="rail-dashboard__legend">
            <span><i className="legend-swatch legend-swatch--clear" />No anomaly detected</span>
            <span><i className="legend-swatch legend-swatch--fault" />Anomaly candidate</span>
          </div>
        </div>
        <div className="rail-dashboard__facts">
          <div className="fact"><span>Recording format</span><strong>1 s / 10,000 samples</strong></div>
          <div className="fact"><span>Input channels</span><strong>129 total</strong><small>1 speed + 128 vibration/shock</small></div>
          <div className="fact"><span>Side I positions</span><strong>1 · 3 · 5 · 7</strong></div>
          <div className="fact"><span>Side II positions</span><strong>2 · 4 · 6 · 8</strong></div>
        </div>
      </div>

      <div className="rail-dashboard__grid">
        <article className="insight-panel">
          <div className="panel-heading"><span>Training set</span><strong>272 recordings</strong></div>
          <div className="class-bars">
            {TRAINING_CLASSES.map((item) => (
              <div className="class-bar" key={item.label}>
                <div className="class-bar__meta"><span>{item.label}</span><strong>{item.count}</strong></div>
                <div className="class-bar__track"><span className={`class-bar__fill class-bar__fill--${item.tone}`} style={{ width: `${(item.count / 234) * 100}%` }} /></div>
              </div>
            ))}
          </div>
          <p className="panel-note">Fault classes are intentionally kept visible because macro F1 values minority-class recall.</p>
        </article>

        <article className="insight-panel">
          <div className="panel-heading"><span>Registered model validation</span><strong>{foldScores.length ? `${foldScores.length}-fold stratified CV` : "Unavailable"}</strong></div>
          <div className="validation-score"><strong>{scoreText(modelScore)}</strong><span>mean fold macro F1</span></div>
          <div className="fold-row" aria-label="Macro F1 by validation fold">
            {foldScores.map((score, index) => (
              <div className="fold-column" key={index} title={`Fold ${index + 1}: ${scoreText(score)}`}>
                <span style={{ height: `${(score / maxFold) * 100}%` }} />
                <small>{index + 1}</small>
              </div>
            ))}
          </div>
          <p className="panel-note">Selected model: pooled spatial features. Test labels are unavailable, so live outputs stay predictions.</p>
        </article>

        <article className="insight-panel insight-panel--batch">
          <div className="panel-heading"><span>Current batch</span><strong>{rows.length ? `${rows.length} files` : "Awaiting files"}</strong></div>
          <div className="batch-counts">
            <div><strong>{counts.Normal}</strong><span>Normal</span></div>
            <div className="batch-count--fault"><strong>{counts["Side I"]}</strong><span>Side I</span></div>
            <div className="batch-count--fault-alt"><strong>{counts["Side II"]}</strong><span>Side II</span></div>
          </div>
          <p className="panel-note">
            {flagged.length ? `${flagged.length} file${flagged.length === 1 ? "" : "s"} need rail-side review.` : "Run a batch to populate the review summary."}
          </p>
        </article>
      </div>
    </section>
  );
}

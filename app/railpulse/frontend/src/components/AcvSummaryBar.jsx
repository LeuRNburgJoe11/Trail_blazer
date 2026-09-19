/**
 * Headline figures for the consist, and the recorded validation result.
 *
 * The validation block is read from outputs/acv/validation_results_baseline.csv
 * at request time rather than typed in, so it cannot drift from what the team
 * actually measured. It is a leave-one-case-out result on six cases, which is
 * why it is labelled as the protocol rather than as held-out test performance.
 */
function Kpi({ label, value, sub, tone, badge }) {
  return (
    <div className={`kpi${tone ? ` kpi--${tone}` : ""}`}>
      <div className="kpi__top">
        <span className="kpi__label">{label}</span>
        {badge && <span className="kpi__badge">{badge}</span>}
      </div>
      <span className="kpi__value">{value}</span>
      {sub && <span className="kpi__sub">{sub}</span>}
    </div>
  );
}

export default function AcvSummaryBar({ consist, validation, context }) {
  const rows = consist?.rows ?? [];
  if (rows.length === 0) return null;
  const ranked = [...rows].filter((r) => r.rank != null).sort((a, b) => a.rank - b.rank);
  const first = ranked[0];
  const second = ranked[1];

  return (
    <div className="kpis">
      <Kpi
        label="Consist"
        value={`${rows.length} cars`}
        sub={context?.train_number ? `Train ${context.train_number}` : "lead cab to tail cab"}
        badge={context?.n_samples ? `${context.n_samples.toLocaleString()} samples` : null}
      />
      {first && (
        <Kpi
          label="Top suspect"
          tone="fault"
          badge="Rank #1"
          value={`Car ${first.car}`}
          sub={first.indicators?.peer_residual_mean == null
            ? "peer-relative deviation"
            : `${first.indicators.peer_residual_mean > 0 ? "+" : ""}${first.indicators.peer_residual_mean.toFixed(2)} °C vs train median`}
        />
      )}
      {second && (
        <Kpi
          label="Next to check"
          tone={second.tier === "co_suspect" ? "tie" : null}
          badge="Rank #2"
          value={`Car ${second.car}`}
          sub={first?.margin_to_next == null
            ? "margin unavailable"
            : `${first.margin_to_next.toFixed(2)} behind${first.margin_to_next <= (consist.near_tie_threshold ?? 0.02) ? " — near tie" : ""}`}
        />
      )}
      {validation?.available && (
        <Kpi
          label="Validation"
          badge="Rank-decay"
          value={validation.mean_rank_decay.toFixed(3)}
          sub={`${validation.top1} of ${validation.n_cases} cases at rank 1 · worst rank ${validation.worst_rank}`}
        />
      )}
    </div>
  );
}

export function AcvValidationStrip({ validation }) {
  if (!validation?.available) return null;
  return (
    <section className="validation">
      <div className="validation__head">
        <h4 className="validation__title">Leave-one-case-out breakdown</h4>
        <span className="validation__source">{validation.source}</span>
      </div>
      <div className="validation__cases">
        {validation.cases.map((entry) => (
          <div key={entry.case} className={`vcase${entry.rank === 1 ? " vcase--top" : " vcase--miss"}`}>
            <span className="vcase__id">{entry.case.replace("acv_case_", "Case ")}</span>
            <span className="vcase__rank">#{entry.rank}</span>
            <span className="vcase__score">{entry.score.toFixed(3)}</span>
          </div>
        ))}
      </div>
      <p className="muted note">
        {validation.protocol} over {validation.n_cases} labelled cases &mdash; a small sample, and a
        different protocol from the held-out test set, so treat it as the team&apos;s recorded
        validation rather than expected performance on unseen trains.
      </p>
    </section>
  );
}

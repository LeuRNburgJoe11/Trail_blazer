import { useState } from "react";

/**
 * Motor current through one door cycle, against the Normal envelope.
 *
 * Two series on ONE axis (both are mA). The trace wears the module status
 * colour -- black for Normal, red for Abnormal resistance -- and the envelope
 * is a recessive dashed grey, so the chart never introduces a palette that
 * competes with the app-wide colour code. Both are direct-labelled, so identity
 * survives greyscale printing and colour-vision deficiency; exceedance regions
 * additionally carry a hatch texture rather than relying on the wash alone.
 */
const W = 720;
const H = 200;
const PAD = { top: 16, right: 64, bottom: 28, left: 48 };

function niceTicks(max, count = 4) {
  const raw = max / count;
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? magnitude * 10;
  return Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step);
}

export default function DoorTrace({ trace, regions = [], status, startClock }) {
  const [hover, setHover] = useState(null);
  if (!trace || trace.length < 2) return null;

  const fault = status !== "Normal";
  const traceColor = fault ? "var(--status-fault)" : "var(--status-clear)";
  const duration = trace[trace.length - 1].t || 1;
  const peak = Math.max(...trace.map((p) => Math.max(p.current, p.envelope)));
  const yMax = peak * 1.08;

  const x = (t) => PAD.left + (t / duration) * (W - PAD.left - PAD.right);
  const y = (v) => H - PAD.bottom - (v / yMax) * (H - PAD.top - PAD.bottom);
  const path = (key) => trace.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(" ");

  function onMove(event) {
    const box = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - box.left) / box.width;
    const t = Math.max(0, Math.min(duration, ((ratio * W) - PAD.left) / (W - PAD.left - PAD.right) * duration));
    let nearest = 0;
    for (let i = 1; i < trace.length; i += 1) {
      if (Math.abs(trace[i].t - t) < Math.abs(trace[nearest].t - t)) nearest = i;
    }
    setHover(trace[nearest]);
  }

  return (
    <figure className="trace">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="trace__svg"
        role="img"
        aria-label={`Motor current through the cycle against the Normal envelope. ${regions.length} interval(s) above the envelope.`}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <pattern id="trace-hatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--status-fault)" strokeWidth="1.5" opacity="0.28" />
          </pattern>
        </defs>

        {niceTicks(yMax).map((value) => (
          <g key={value}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(value)} y2={y(value)} className="trace__grid" />
            <text x={PAD.left - 8} y={y(value) + 4} className="trace__axis" textAnchor="end">{value}</text>
          </g>
        ))}

        {/* Where the cycle draws more than Normal cycles do -- the part to inspect. */}
        {regions.map((region) => (
          <rect
            key={`${region.start_offset}-${region.end_offset}`}
            x={x(region.start_offset)}
            y={PAD.top}
            width={Math.max(x(region.end_offset) - x(region.start_offset), 1.5)}
            height={H - PAD.top - PAD.bottom}
            fill="url(#trace-hatch)"
          />
        ))}

        <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} className="trace__axis-line" />
        <path d={path("envelope")} className="trace__envelope" />
        <path d={path("current")} style={{ stroke: traceColor }} className="trace__current" />

        <text x={W - PAD.right + 6} y={y(trace[trace.length - 1].current) + 4} className="trace__label" style={{ fill: traceColor }}>
          Current
        </text>
        <text x={W - PAD.right + 6} y={y(trace[trace.length - 1].envelope) + 4} className="trace__label trace__label--muted">
          Normal
        </text>

        {[0, duration / 2, duration].map((t) => (
          <text key={t} x={x(t)} y={H - 8} className="trace__axis" textAnchor="middle">
            +{t.toFixed(2)}s
          </text>
        ))}

        {hover && (
          <g pointerEvents="none">
            <line x1={x(hover.t)} x2={x(hover.t)} y1={PAD.top} y2={H - PAD.bottom} className="trace__crosshair" />
            <circle cx={x(hover.t)} cy={y(hover.current)} r="4" style={{ fill: traceColor }} />
            <circle cx={x(hover.t)} cy={y(hover.envelope)} r="3.5" className="trace__dot-envelope" />
          </g>
        )}
      </svg>

      <figcaption className="trace__caption">
        {hover ? (
          <span className="trace__readout">
            +{hover.t.toFixed(2)}s &middot; current <strong>{hover.current} mA</strong> &middot; Normal envelope{" "}
            {hover.envelope} mA
          </span>
        ) : (
          <span>
            Motor current (mA) from {startClock}. Hatched bands mark where this cycle draws above the
            Normal envelope{regions.length ? "" : " (none in this cycle)"}.
          </span>
        )}
      </figcaption>
    </figure>
  );
}

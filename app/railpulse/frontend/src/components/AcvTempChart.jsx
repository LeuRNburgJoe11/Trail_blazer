import { useState } from "react";

/**
 * Cabin temperature for the selected car against its peers.
 *
 * Same visual language as the Door trace: the subject wears the status colour,
 * the reference it is judged against is a recessive grey, and the commanded
 * setpoint is a dashed rule. Three series on ONE axis -- all three are degrees
 * Celsius, so there is no second scale to mislead anyone.
 */
const W = 720;
const H = 190;
const PAD = { top: 14, right: 74, bottom: 26, left: 44 };

export default function AcvTempChart({ series, car, tier }) {
  const [hover, setHover] = useState(null);
  if (!series?.available) return null;

  const values = series.by_car?.[car] ?? [];
  const peers = series.peer_median ?? [];
  const n = Math.min(values.length, peers.length);
  if (n < 2) return null;

  const pool = [...values, ...peers, series.setpoint].filter((v) => v !== null && v !== undefined);
  const lo = Math.min(...pool) - 0.4;
  const hi = Math.max(...pool) + 0.4;
  const color = tier === "primary" ? "var(--status-fault)"
    : tier === "co_suspect" ? "var(--status-tie)" : "var(--status-clear)";

  const x = (i) => PAD.left + (i / (n - 1)) * (W - PAD.left - PAD.right);
  const y = (v) => H - PAD.bottom - ((v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);
  const path = (data) => data.slice(0, n).map((v, i) =>
    v === null || v === undefined ? null : `${i && data[i - 1] !== null ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`
  ).filter(Boolean).join(" ");

  const ticks = [lo, (lo + hi) / 2, hi].map((v) => Number(v.toFixed(1)));

  function onMove(event) {
    const box = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - box.left) / box.width;
    const i = Math.round(((ratio * W) - PAD.left) / (W - PAD.left - PAD.right) * (n - 1));
    if (i >= 0 && i < n) setHover(i);
  }

  return (
    <figure className="tempchart">
      <svg viewBox={`0 0 ${W} ${H}`} className="trace__svg" role="img"
           aria-label={`Cabin temperature for car ${car} against the train median`}
           onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        {ticks.map((value) => (
          <g key={value}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(value)} y2={y(value)} className="trace__grid" />
            <text x={PAD.left - 7} y={y(value) + 4} className="trace__axis" textAnchor="end">{value}</text>
          </g>
        ))}

        {series.setpoint !== null && series.setpoint !== undefined && (
          <>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(series.setpoint)} y2={y(series.setpoint)}
                  className="tempchart__setpoint" />
            <text x={W - PAD.right + 6} y={y(series.setpoint) + 4} className="trace__label trace__label--muted">
              Setpoint
            </text>
          </>
        )}

        <path d={path(peers)} className="trace__envelope" />
        <path d={path(values)} className="trace__current" style={{ stroke: color }} />

        <text x={W - PAD.right + 6} y={y(values[n - 1] ?? lo) + 4} className="trace__label" style={{ fill: color }}>
          Car {car}
        </text>
        <text x={W - PAD.right + 6} y={y(peers[n - 1] ?? lo) + 14} className="trace__label trace__label--muted">
          Train median
        </text>

        {hover !== null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={H - PAD.bottom} className="trace__crosshair" />
            {values[hover] != null && <circle cx={x(hover)} cy={y(values[hover])} r="4" style={{ fill: color }} />}
            {peers[hover] != null && <circle cx={x(hover)} cy={y(peers[hover])} r="3.5" className="trace__dot-envelope" />}
          </g>
        )}
      </svg>
      <figcaption className="trace__caption">
        {hover !== null && values[hover] != null ? (
          <span className="trace__readout">
            Car {car} <strong>{values[hover].toFixed(2)} &deg;C</strong> &middot; train median{" "}
            {peers[hover]?.toFixed(2)} &deg;C &middot; gap{" "}
            {(values[hover] - (peers[hover] ?? 0)).toFixed(2)} &deg;C
          </span>
        ) : (
          <span>
            Measured cabin temperature, every {series.stride}
            {series.stride === 1 ? "st" : "th"} sample across the recorded window.
          </span>
        )}
      </figcaption>
    </figure>
  );
}

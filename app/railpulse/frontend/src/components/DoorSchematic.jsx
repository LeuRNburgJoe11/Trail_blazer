import { useEffect, useRef, useState } from "react";

/**
 * Bi-parting saloon door, replayed from the recorded telemetry.
 *
 * Every moving part is driven by measured channels, not a tween: leaf travel is
 * "Door leaf position" scaled against the widest opening in the recording, the
 * effort readout is "Motor current(mA)" at that frame, and the interlock lamps
 * are the real DCSR/DCSL/DLSR/DLSL switch states. Where the cycle drew more
 * than the Normal envelope, the marker sits at the leaf position where that
 * actually happened -- so it points at a part of the stroke, not a guess about
 * the cause. The telemetry says an interval took extra effort; it does not say
 * whether that was debris, a seal, or a dry guide, and this does not claim to.
 */
const MAX_SLIDE = 150;
const APERTURE = { x: 150, y: 122, w: 400, h: 184 };

function switchStateAt(events, t) {
  if (!events || events.length === 0) return null;
  let value = events[0].value;
  for (const event of events) {
    if (event.t <= t) value = event.value;
    else break;
  }
  return value;
}

export default function DoorSchematic({ motion, trace, status, operation }) {
  // null means "rest at the end of the cycle", which is where a door actually
  // sits once the operation completes. Deriving it beats syncing it in an
  // effect, which would re-render once more every time the cycle changes.
  const [frame, setFrame] = useState(null);
  const [playing, setPlaying] = useState(false);
  const raf = useRef(null);
  const startedAt = useRef(0);

  const frames = trace ?? [];
  const lastIndex = Math.max(frames.length - 1, 0);
  const index = frame === null ? lastIndex : Math.min(frame, lastIndex);
  const duration = frames.length ? frames[lastIndex].t : 0;

  useEffect(() => () => cancelAnimationFrame(raf.current), []);

  function play() {
    if (!frames.length || playing) return;
    setPlaying(true);
    startedAt.current = performance.now();
    const tick = (now) => {
      const elapsed = (now - startedAt.current) / 1000;
      const at = frames.findIndex((point) => point.t >= elapsed);
      if (elapsed >= duration || at < 0) {
        setFrame(lastIndex);
        setPlaying(false);
        return;
      }
      setFrame(at);
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  }

  if (!motion?.available) {
    return <p className="muted">{motion?.note ?? "No leaf-position channel: the cycle cannot be replayed."}</p>;
  }

  const point = frames[index] ?? {};
  const openPct = point.open_pct ?? 0;
  const slide = (openPct / 100) * MAX_SLIDE;
  const elevatedNow = point.current > point.envelope;
  const fault = status !== "Normal";
  const windows = motion.elevated_windows ?? [];
  const marker = windows.length
    ? windows.reduce((a, b) => (b.to_open_pct - b.from_open_pct > a.to_open_pct - a.from_open_pct ? b : a))
    : null;
  const markerX = marker
    ? APERTURE.x + APERTURE.w * (1 - ((marker.from_open_pct + marker.to_open_pct) / 2) / 100)
    : null;

  return (
    <div className="schematic">
      <div className="schematic__bar">
        <span className={`pill pill--${fault ? "primary" : "nominal"}`}>{operation?.toUpperCase()} CYCLE</span>
        <button className="button button--primary schematic__play" onClick={play} disabled={playing || !frames.length}>
          {playing ? "Replaying…" : "▶ Replay motion"}
        </button>
        <input
          className="schematic__scrub"
          type="range"
          min="0"
          max={Math.max(frames.length - 1, 0)}
          value={index}
          onChange={(event) => { setPlaying(false); setFrame(Number(event.target.value)); }}
          aria-label="Scrub through the cycle"
        />
        <span className="schematic__time">+{(point.t ?? 0).toFixed(2)}s</span>
      </div>

      <svg viewBox="0 0 700 340" className="schematic__svg" role="img"
           aria-label={`Bi-parting door at ${openPct.toFixed(0)} percent open, motor current ${point.current} milliamps`}>
        <rect x="20" y="15" width="660" height="310" rx="12" className="sc-body" />

        {/* Overhead drive housing */}
        <rect x="60" y="48" width="580" height="34" rx="4" className="sc-housing" />
        <text x="74" y="70" className="sc-label">OVERHEAD DRIVE BELT &amp; MOTOR GEARBOX</text>
        <circle cx="596" cy="65" r="11" className={`sc-motor${elevatedNow ? " sc-motor--hot" : ""}`} />
        <text x="592" y="69" className="sc-motor-text">M</text>

        {/* Limit and interlock switches, lit from the recorded states */}
        {[["DLSL", 74], ["DCSL", 150]].map(([name, x]) => (
          <g key={name}>
            <circle cx={x} cy="101" r="5"
                    className={`sc-lamp${switchStateAt(motion.switches?.[name], point.t) ? " sc-lamp--on" : ""}`} />
            <text x={x + 10} y="105" className="sc-switch">{name}</text>
          </g>
        ))}
        {[["DCSR", 500], ["DLSR", 576]].map(([name, x]) => (
          <g key={name}>
            <circle cx={x} cy="101" r="5"
                    className={`sc-lamp${switchStateAt(motion.switches?.[name], point.t) ? " sc-lamp--on" : ""}`} />
            <text x={x + 10} y="105" className="sc-switch">{name}</text>
          </g>
        ))}

        <line x1="60" y1="118" x2="640" y2="118" className="sc-track" />

        {/* Saloon interior behind the leaves */}
        <rect x={APERTURE.x} y={APERTURE.y} width={APERTURE.w} height={APERTURE.h} className="sc-interior" />
        <text x="350" y="220" className="sc-interior-text" textAnchor="middle">SALOON</text>

        {/* Leaves: translation is measured leaf position, not an animation curve */}
        <g transform={`translate(${-slide}, 0)`}>
          <rect x="150" y="122" width="198" height="184" rx="3" className="sc-leaf" />
          <rect x="175" y="145" width="140" height="82" rx="8" className="sc-window" />
          <line x1="330" y1="170" x2="330" y2="258" className="sc-rail" />
        </g>
        <g transform={`translate(${slide}, 0)`}>
          <rect x="352" y="122" width="198" height="184" rx="3" className="sc-leaf" />
          <rect x="385" y="145" width="140" height="82" rx="8" className="sc-window" />
          <line x1="370" y1="170" x2="370" y2="258" className="sc-rail" />
        </g>

        {/* Threshold sill */}
        <rect x="60" y="306" width="580" height="14" rx="3" className="sc-sill" />

        {/* Where the cycle drew above the Normal envelope */}
        {fault && marker && (
          <g>
            <circle cx={markerX} cy="313" r="7" className="sc-marker" />
            <text x={markerX + 12} y="317" className="sc-marker-text">
              Elevated effort {marker.start_clock}&ndash;{marker.end_clock}
            </text>
          </g>
        )}
      </svg>

      <div className="schematic__readouts">
        <div className="readout">
          <span className="readout__label">Leaf opening</span>
          <div className="readout__bar">
            <div className="readout__fill" style={{ width: `${Math.max(0, Math.min(100, openPct))}%` }} />
          </div>
          <span className="readout__value">{openPct.toFixed(0)}%</span>
        </div>
        <div className="readout">
          <span className="readout__label">Motor effort</span>
          <span className={`readout__value${elevatedNow ? " readout__value--fault" : ""}`}>
            {point.current} mA
          </span>
          <span className="readout__sub">
            {elevatedNow ? "above Normal envelope" : "within envelope"} &middot; peak {motion.peak_current} mA
          </span>
        </div>
        <div className="readout">
          <span className="readout__label">Interlocks</span>
          <span className="readout__switches">
            {["DCSR", "DCSL", "DLSR", "DLSL"].map((name) => (
              <span key={name}
                    className={`chip${switchStateAt(motion.switches?.[name], point.t) ? " chip--on" : ""}`}>
                {name}
              </span>
            ))}
          </span>
        </div>
      </div>
    </div>
  );
}

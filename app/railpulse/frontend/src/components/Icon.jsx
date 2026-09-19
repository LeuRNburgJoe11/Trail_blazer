/**
 * Subsystem icons. Every glyph is stroke-only and uses `currentColor`, so a
 * parent that is black (no anomaly) or red (anomaly detected) colours the icon
 * with it -- the colour code stays in one place instead of per-icon fills.
 */
const PATHS = {
  // Train door: leaf split down the middle, with the two door handles.
  door: (
    <>
      <rect x="4" y="2.5" width="16" height="19" rx="1.5" />
      <path d="M12 2.5v19" />
      <path d="M10 12.5v-2M14 12.5v-2" />
    </>
  ),
  // Air conditioning unit: wall-mounted box with airflow below it.
  acv: (
    <>
      <rect x="2.5" y="4" width="19" height="7" rx="1.5" />
      <path d="M6 8h12" />
      <path d="M6.5 14.5c1.2 0 1.2 1.6 2.4 1.6s1.2-1.6 2.4-1.6 1.2 1.6 2.4 1.6 1.2-1.6 2.4-1.6" />
      <path d="M6.5 18.5c1.2 0 1.2 1.6 2.4 1.6s1.2-1.6 2.4-1.6 1.2 1.6 2.4 1.6 1.2-1.6 2.4-1.6" />
    </>
  ),
  // Rail track seen in perspective: two rails over sleepers.
  rail: (
    <>
      <path d="M8 2.5 5 21.5M16 2.5l3 19" />
      <path d="M6.6 8.5h10.8M6.2 13h11.6M5.7 17.5h12.6" />
    </>
  ),
  // Structural health: a bogie/carbody frame with a stress crack.
  shm: (
    <>
      <rect x="2.5" y="5.5" width="19" height="13" rx="1.5" />
      <path d="M2.5 12h6l2.5-3.5L14 15.5l2-3.5h5.5" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 11v5.5" />
      <path d="M12 7.5h.01" />
    </>
  ),
};

export default function Icon({ name, size = 18, className = "" }) {
  const glyph = PATHS[name];
  if (!glyph) return null;
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {glyph}
    </svg>
  );
}

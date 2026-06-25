// Taqdeer (تقدير) brand mark.
//
// Icon story: three ascending strokes (a messy scope becoming ordered, priced
// quantities) traced by a rising green line that ticks up to a confidence point
// — estimation resolving into an approved, confident BoQ.
// Palette: petrol teal (trust/precision) + confident green (approved/score).

export const BRAND = {
  teal: "#0E5F63",
  tealSoft: "#5FC9C2",
  green: "#27C08D",
  ink: "#EAF6F4",
};

export function LogoMark({ size = 30, rounded = true }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Taqdeer"
      style={{ display: "block", flexShrink: 0 }}
    >
      <rect width="48" height="48" rx={rounded ? 11 : 0} fill={BRAND.teal} />
      {/* ascending quantities — chaos becoming ordered line items */}
      <g fill={BRAND.ink}>
        <rect x="11" y="29" width="5" height="8" rx="2" />
        <rect x="18.5" y="24" width="5" height="13" rx="2" />
        <rect x="26" y="19" width="5" height="18" rx="2" />
      </g>
      {/* rising estimate line that ticks up into a confidence point */}
      <path
        d="M13.5 29 L21 24 L28.5 19 L38 12"
        stroke={BRAND.green}
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="38" cy="12" r="2.4" fill={BRAND.green} />
    </svg>
  );
}

/**
 * Full lockup: mark + bilingual wordmark.
 * tone="light"  -> for dark backgrounds (top bar): white Latin, soft-teal Arabic
 * tone="dark"   -> for light backgrounds (login):  ink Latin, teal Arabic
 */
export function Logo({ size = 30, tone = "light", showArabic = true, gap = 11 }) {
  const latin = tone === "light" ? "#FFFFFF" : "var(--text)";
  const arabic = tone === "light" ? BRAND.tealSoft : BRAND.teal;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap }}>
      <LogoMark size={size} />
      <span style={{ display: "inline-flex", alignItems: "baseline", gap: 8 }}>
        <span
          style={{
            fontWeight: 800,
            fontSize: Math.round(size * 0.62),
            letterSpacing: "-0.012em",
            textTransform: "none",
            color: latin,
            lineHeight: 1,
          }}
        >
          Taqdeer
        </span>
        {showArabic && (
          <span
            lang="ar"
            dir="rtl"
            style={{
              fontWeight: 700,
              fontSize: Math.round(size * 0.58),
              color: arabic,
              lineHeight: 1,
            }}
          >
            تقدير
          </span>
        )}
      </span>
    </span>
  );
}

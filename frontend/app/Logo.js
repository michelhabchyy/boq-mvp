// Taqdeer (تقدير) brand mark.
//
// Icon: two brackets [ ] frame the priced line items (a BoQ is structured,
// quantified), with a green check = the human approval / confidence at the core.
// Palette: petrol teal (trust/precision) + confident green (approved/score).

export const BRAND = {
  teal: "#0E6E6E",
  green: "#2FB573",
  tag: "#7a8888",
};

export function LogoMark({ size = 30 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 56 56"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Taqdeer"
      style={{ display: "block", flexShrink: 0 }}
    >
      <rect x="4" y="4" width="48" height="48" rx="8" fill={BRAND.teal} />
      {/* brackets — framing / quantifying the line items */}
      <path d="M18 14 L14 14 L14 42 L18 42" fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M38 14 L42 14 L42 42 L38 42" fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {/* approval / confidence */}
      <path d="M23 30 L27 35 L35 23" fill="none" stroke={BRAND.green} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * Concept 4 — the process mark: messy input (muted-slate strokes) is
 * transformed (teal arrow) into ordered, priced line items, the last of which
 * is approved (confidence green). Used as a branding graphic on pages with room.
 */
export function ProcessMark({ width = 200 }) {
  return (
    <svg
      width={width}
      height={(width * 90) / 160}
      viewBox="0 0 160 90"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="From scope to approved BoQ"
      style={{ display: "block" }}
    >
      {/* chaotic scope input */}
      <line x1="14" y1="28" x2="40" y2="23" stroke="#9CB8B8" strokeWidth="4" strokeLinecap="round" />
      <line x1="14" y1="44" x2="36" y2="50" stroke="#9CB8B8" strokeWidth="4" strokeLinecap="round" />
      <line x1="14" y1="60" x2="42" y2="55" stroke="#9CB8B8" strokeWidth="4" strokeLinecap="round" />
      <line x1="14" y1="76" x2="34" y2="69" stroke="#9CB8B8" strokeWidth="4" strokeLinecap="round" />
      {/* transform */}
      <path d="M62 49 L86 49" stroke="#0E6E6E" strokeWidth="3.5" strokeLinecap="round" />
      <path d="M81 44 L88 49 L81 54" fill="none" stroke="#0E6E6E" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {/* ordered, priced BoQ — last line approved */}
      <rect x="108" y="22" width="38" height="7" rx="3.5" fill="#0E6E6E" />
      <rect x="108" y="38" width="38" height="7" rx="3.5" fill="#0E6E6E" />
      <rect x="108" y="54" width="38" height="7" rx="3.5" fill="#0E6E6E" />
      <rect x="108" y="70" width="38" height="7" rx="3.5" fill="#2FB573" />
    </svg>
  );
}

/**
 * Full lockup: mark + bilingual wordmark (+ optional tagline).
 * tone="dark"  -> light backgrounds (login):   teal Latin + Arabic, grey tag
 * tone="light" -> dark backgrounds (top bar):  white Latin, soft-teal Arabic
 */
export function Logo({ size = 30, tone = "light", showArabic = true, showTag = false }) {
  const name = tone === "light" ? "#FFFFFF" : BRAND.teal;
  const tagColor = tone === "light" ? "rgba(255,255,255,0.6)" : BRAND.tag;
  const arabic = tone === "light" ? "#7FD4CF" : BRAND.teal;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: Math.round(size * 0.25) }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: Math.round(size * 0.29) }}>
        <LogoMark size={size} />
        <span style={{ display: "flex", flexDirection: "column", lineHeight: 1 }}>
          <span
            style={{
              fontSize: Math.round(size * 0.68),
              fontWeight: 600,
              color: name,
              letterSpacing: "-0.5px",
              textTransform: "none",
            }}
          >
            Taqdeer
          </span>
          {showTag && (
            <span
              style={{
                fontSize: Math.max(10, Math.round(size * 0.2)),
                color: tagColor,
                marginTop: 4,
                letterSpacing: "0.2px",
                textTransform: "none",
              }}
            >
              estimating intelligence
            </span>
          )}
        </span>
      </span>
      {showArabic && (
        <span
          lang="ar"
          dir="rtl"
          style={{
            fontSize: Math.round(size * 0.74),
            fontWeight: 600,
            color: arabic,
            fontFamily: "var(--font-ar)",
            lineHeight: 1,
          }}
        >
          تقدير
        </span>
      )}
    </span>
  );
}

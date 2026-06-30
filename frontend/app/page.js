"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getToken } from "../lib/api";
import { Logo, ProcessMark } from "./Logo";

// Small inline icons (stroke = currentColor).
const Icon = ({ d }) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {d}
  </svg>
);
const icons = {
  ai: <Icon d={<><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8" /><circle cx="12" cy="12" r="3" /></>} />,
  doc: <Icon d={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M9 13h6M9 17h6" /></>} />,
  match: <Icon d={<><circle cx="6" cy="6" r="3" /><circle cx="18" cy="18" r="3" /><path d="M9 6h6a3 3 0 0 1 3 3v6M6 9v6a3 3 0 0 0 3 3h6" /></>} />,
  shield: <Icon d={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></>} />,
  globe: <Icon d={<><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15 15 0 0 1 0 20a15 15 0 0 1 0-20z" /></>} />,
  gauge: <Icon d={<><path d="M12 14a4 4 0 1 0-4-4" /><path d="M12 14v-1M20 12a8 8 0 1 0-16 0" /></>} />,
  check: <Icon d={<path d="m5 12 4 4L19 7" />} />,
};

const FEATURES = [
  { i: "ai", h: "AI scope analysis", p: "Drop in a messy RFP: Excel, Word, or PDF, Arabic or English, and the engine reads the whole document, structuring it into clean, sectioned work items." },
  { i: "match", h: "Smart catalog matching", p: "Each line is matched against your priced catalog with confidence scoring, so your estimators review and approve instead of pricing from scratch." },
  { i: "doc", h: "Bilingual BoQ export", p: "Produce a polished, bilingual (AR/EN) Bill of Quantities ready to send; every section, item and total, in one click." },
  { i: "globe", h: "Subcontractor network", p: "Subcontractors maintain their own price lists and receive Official and Signed documents, all isolated and pooled into your catalog automatically." },
  { i: "gauge", h: "Cost under control", p: "Weekly AI-token plans per company and live per-user usage tracking mean you always know; and cap; what each tender costs." },
  { i: "shield", h: "Secure by design", p: "Two-factor authentication, strict per-company isolation, encrypted transport, and a full edit/audit history on every record." },
];

const STEPS = [
  { h: "Upload the RFP", p: "Add the scope of work and, optionally, a reference BoQ template and instructions for the AI." },
  { h: "AI structures & prices", p: "The document is parsed into sections and items, then matched to your catalog with confidence scores." },
  { h: "Review & export", p: "Approve the lines you trust, adjust the rest, and export a clean bilingual BoQ; fast." },
];

export default function Landing() {
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    setSignedIn(!!getToken());
    // Reveal-on-scroll for elements marked [data-reveal].
    const els = document.querySelectorAll("[data-reveal]");
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("lp-in")),
      { threshold: 0.12 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  const primaryHref = signedIn ? "/rfps" : "/pricing";
  const primaryLabel = signedIn ? "Open workspace" : "Get started";

  return (
    <div className="lp">
      <div className="lp-orb a" />
      <div className="lp-orb b" />
      <div className="lp-orb c" />

      <div className="lp-wrap">
        {/* Nav */}
        <nav className="lp-nav">
          <Logo size={30} tone="light" showTag={false} />
          <div className="lp-nav-links">
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <Link href="/pricing">Pricing</Link>
            {signedIn ? (
              <Link className="lp-btn lp-btn-primary sm" href="/rfps">Open app</Link>
            ) : (
              <>
                <Link className="lp-btn lp-btn-ghost sm" href="/login">Sign in</Link>
                <Link className="lp-btn lp-btn-primary sm" href="/pricing">Get started</Link>
              </>
            )}
          </div>
        </nav>

        {/* Hero */}
        <header className="lp-hero">
          <div>
            <span className="lp-pill"><span className="dot" /> Bilingual estimation</span>
            <h1 className="lp-h1">
              From chaotic RFP to a priced, <span className="grad">bilingual BoQ</span> — in minutes.
            </h1>
            <p className="lp-lead">
              Taqdeer reads your scope of work, structures it, and matches it to your
              catalog with confidence scores, so your team approves a precise Bill
              of Quantities instead of building one by hand.
            </p>
            <div className="lp-cta-row">
              <Link className="lp-btn lp-btn-primary" href={primaryHref}>{primaryLabel} →</Link>
              <a className="lp-btn lp-btn-ghost" href="#how">See how it works</a>
            </div>
            <div className="lp-trust">
              <span><span className="ic">{icons.check}</span> Arabic + English, native</span>
              <span><span className="ic">{icons.check}</span> Two-factor secured</span>
              <span><span className="ic">{icons.check}</span> Catalog-priced, never guessed</span>
            </div>
          </div>

          <div className="lp-visual" data-reveal>
            <div className="cap">RFP → ordered, approved BoQ</div>
            <div style={{ display: "flex", justifyContent: "center", margin: "6px 0 10px" }}>
              <ProcessMark width={220} />
            </div>
          </div>
        </header>

        {/* Stat band */}
        <section className="lp-section" style={{ paddingTop: 10 }}>
          <div className="lp-stats" data-reveal>
            {[
              { v: <><span className="grad">10×</span></>, k: "Faster than pricing by hand" },
              { v: "AR / EN", k: "Bilingual, end to end" },
              { v: <><span className="grad">100%</span></>, k: "Catalog-based pricing" },
              { v: "2FA", k: "Secured accounts" },
            ].map((s, i) => (
              <div className="lp-stat" key={i}>
                <div className="v">{s.v}</div>
                <div className="k">{s.k}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section className="lp-section" id="features">
          <div data-reveal>
            <div className="lp-eyebrow">What it does</div>
            <h2 className="lp-h2">Everything from scope to signed quote</h2>
            <p className="lp-sub">
              A focused toolchain for contractors and their subcontractors; built
              around the way bids actually get priced.
            </p>
          </div>
          <div className="lp-grid">
            {FEATURES.map((f) => (
              <div className="lp-card" key={f.h} data-reveal>
                <div className="ic">{icons[f.i]}</div>
                <h3>{f.h}</h3>
                <p>{f.p}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section className="lp-section" id="how">
          <div data-reveal>
            <div className="lp-eyebrow">How it works</div>
            <h2 className="lp-h2">Three steps to a finished BoQ</h2>
          </div>
          <div className="lp-steps">
            {STEPS.map((s, i) => (
              <div className="lp-step" key={s.h} data-reveal>
                <div className="num">{i + 1}</div>
                <h3>{s.h}</h3>
                <p>{s.p}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Trust / security */}
        <section className="lp-section" id="trust">
          <div data-reveal>
            <div className="lp-eyebrow">Trust</div>
            <h2 className="lp-h2">Serious about your data</h2>
            <p className="lp-sub">
              Pricing and contracts are sensitive. Taqdeer is built so each company's
              data stays its own, and only the right people get in.
            </p>
          </div>
          <div className="lp-points" data-reveal>
            {[
              "Two-factor authentication with one-time recovery codes",
              "Strict per-company isolation, tenants never see each other's data",
              "Encrypted in transit, with security headers and a hardened API",
              "Full edit & deletion history on catalog and documents",
            ].map((t) => (
              <div className="lp-point" key={t}>
                <span className="ic">{icons.check}</span>
                <div>{t}</div>
              </div>
            ))}
          </div>
          <div className="lp-chipline center" style={{ marginTop: 18 }}>
            <span className="lp-chip">2FA</span>
            <span className="lp-chip">Tenant isolation</span>
            <span className="lp-chip">Audit history</span>
            <span className="lp-chip">Token quotas</span>
            <span className="lp-chip">Recovery codes</span>
            <span className="lp-chip">HTTPS · CSP</span>
          </div>
        </section>

        {/* CTA band */}
        <section className="lp-section">
          <div className="lp-band" data-reveal>
            <h2>Price your next tender with confidence.</h2>
            <p>Bilingual, catalog-accurate, and secure, from the first RFP.</p>
            <Link className="lp-btn lp-btn-primary" href={primaryHref}>{primaryLabel} →</Link>
          </div>
        </section>

        {/* Footer */}
        <footer className="lp-footer">
          <Logo size={26} tone="light" showTag={false} />
          <div>© {2026} Taqdeer · تقدير — estimating intelligence</div>
          <Link href={primaryHref} style={{ color: "var(--g)" }}>{primaryLabel} →</Link>
        </footer>
      </div>
    </div>
  );
}

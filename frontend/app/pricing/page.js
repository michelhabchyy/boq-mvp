"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Logo } from "../Logo";

// Edit these to your real sales contacts.
const CONTACT_EMAIL = "TBC@taqdeer-co.com";

const Icon = ({ d }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{d}</svg>
);
const check = <Icon d={<path d="m5 12 4 4L19 7" />} />;
const phone = <Icon d={<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.4-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z" />} />;
const mail = <Icon d={<><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 7-10 6L2 7" /></>} />;

// Token allowances mirror the backend default plans (≈200k tokens per RFP).
const PLANS = [
  {
    name: "Starter",
    price: "SAR 1,500",
    tag: "For a small contractor getting started.",
    rfps: "~5 RFPs / week",
    features: ["AI RFP analysis (AR/EN)", "Catalog matching & bilingual BoQ export", "Up to 5 team members", "1,000,000 AI tokens / week", "Email support"],
  },
  {
    name: "Professional",
    price: "SAR 4,500",
    tag: "For active estimating teams bidding weekly.",
    rfps: "~15 RFPs / week",
    popular: true,
    features: ["Everything in Starter", "Subcontractor network & price lists", "Signed document exchange", "3,000,000 AI tokens / week", "Per-user usage & cost tracking", "Priority support"],
  },
  {
    name: "Enterprise",
    price: "Custom",
    tag: "For large contractors with bespoke needs.",
    rfps: "50+ RFPs / week",
    features: ["Everything in Professional", "Custom AI-token allowance", "Onboarding & training", "Data residency options", "Dedicated account manager", "SLA"],
  },
];

export default function PricingPage() {
  const [form, setForm] = useState({ name: "", company: "", email: "", message: "" });
  const contactRef = useRef(null);

  useEffect(() => {
    const els = document.querySelectorAll("[data-reveal]");
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("lp-in")),
      { threshold: 0.12 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  function choose(plan) {
    setForm((f) => ({ ...f, message: `I'd like to subscribe to the ${plan} plan.` }));
    contactRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  function submit(e) {
    e.preventDefault();
    const subject = encodeURIComponent("Taqdeer — subscription / inquiry");
    const body = encodeURIComponent(
      `Name: ${form.name}\nCompany: ${form.company}\nEmail: ${form.email}\n\n${form.message}`
    );
    window.location.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="lp">
      <div className="lp-orb a" />
      <div className="lp-orb b" />

      <div className="lp-wrap">
        <nav className="lp-nav">
          <Link href="/"><Logo size={30} tone="light" showTag={false} /></Link>
          <div className="lp-nav-links">
            <Link href="/">Home</Link>
            <Link className="lp-btn lp-btn-ghost sm" href="/login">Sign in</Link>
          </div>
        </nav>

        {/* Header */}
        <section className="lp-section" style={{ paddingTop: 40 }}>
          <div data-reveal>
            <div className="lp-eyebrow">Plans &amp; pricing</div>
            <h2 className="lp-h2">Choose a plan that fits your bidding volume</h2>
            <p className="lp-sub">
              Every plan includes the full estimation workflow. Plans differ by team
              size and weekly AI capacity. Not sure? Talk to us below.
            </p>
          </div>

          {/* Plans */}
          <div className="lp-plans">
            {PLANS.map((p) => (
              <div className={`lp-plan ${p.popular ? "pop" : ""}`} key={p.name} data-reveal>
                {p.popular && <span className="badge-pop">Most popular</span>}
                <h3>{p.name}</h3>
                <div className="tag2">{p.tag}</div>
                <div className="price">{p.price}</div>
                <div className="per">{p.price === "Custom" ? "tailored to you" : "per month"} · {p.rfps}</div>
                <ul>
                  {p.features.map((f) => (
                    <li key={f}><span className="ic">{check}</span> {f}</li>
                  ))}
                </ul>
                <button
                  className={`lp-btn ${p.popular ? "lp-btn-primary" : "lp-btn-ghost"}`}
                  onClick={() => choose(p.name)}
                >
                  {p.price === "Custom" ? "Contact sales" : "Subscribe"}
                </button>
              </div>
            ))}
          </div>
          <p className="lp-sub" style={{ marginTop: 18, fontSize: 13 }}>
            Already a customer? <Link href="/login" style={{ color: "#5ee0ad" }}>Sign in →</Link>
          </p>
        </section>

        {/* Contact */}
        <section className="lp-section" id="contact" ref={contactRef}>
          <div data-reveal>
            <div className="lp-eyebrow">Talk to us</div>
            <h2 className="lp-h2">Subscribe, book a call, or ask a question</h2>
            <p className="lp-sub">
              We set up your company and assign your plan. Reach out and we'll get you
              running — usually within one business day.
            </p>
          </div>

          <div className="lp-contact" data-reveal>
            <div className="lp-actions">
              <div className="lp-action">
                <span className="ic">{mail}</span>
                <div>
                  <h4>Email us</h4>
                  <p><a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
                </div>
              </div>
              <div className="lp-action">
                <span className="ic">{check}</span>
                <div>
                  <h4>What happens next</h4>
                  <p>We provision your company, assign the plan, and send your admin login.</p>
                </div>
              </div>
            </div>

            <form className="lp-form" onSubmit={submit}>
              <div>
                <div className="lp-label">Name</div>
                <input className="lp-input" value={form.name} onChange={set("name")} required />
              </div>
              <div>
                <div className="lp-label">Company</div>
                <input className="lp-input" value={form.company} onChange={set("company")} />
              </div>
              <div>
                <div className="lp-label">Email</div>
                <input className="lp-input" type="email" value={form.email} onChange={set("email")} required />
              </div>
              <div>
                <div className="lp-label">Message</div>
                <textarea className="lp-input" rows={4} value={form.message} onChange={set("message")}
                  placeholder="Which plan are you interested in? Any questions?" />
              </div>
              <button className="lp-btn lp-btn-primary" type="submit" style={{ justifyContent: "center" }}>
                Send inquiry
              </button>
              <p style={{ fontSize: 11, color: "var(--lp-muted)", margin: 0, textAlign: "center" }}>
                Opens your email app to send to {CONTACT_EMAIL}.
              </p>
            </form>
          </div>
        </section>

        <footer className="lp-footer">
          <Link href="/"><Logo size={26} tone="light" showTag={false} /></Link>
          <div>© 2026 Taqdeer · تقدير — estimating intelligence</div>
          <div className="lp-foot-right">
            <a
              className="lp-social"
              href="https://www.instagram.com/taqdeer.ksa"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Taqdeer on Instagram"
              title="Follow us on Instagram"
            >
              <Icon d={<><rect x="2" y="2" width="20" height="20" rx="5" /><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" /><line x1="17.5" y1="6.5" x2="17.51" y2="6.5" /></>} />
            </a>
            <Link href="/login" style={{ color: "var(--g)" }}>Sign in →</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}

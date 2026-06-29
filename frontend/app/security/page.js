"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

export default function SecurityPage() {
  const { user, loading } = useAuth();
  const [enabled, setEnabled] = useState(null);
  const [remaining, setRemaining] = useState(0);
  const [setup, setSetup] = useState(null); // {secret, otpauth_uri, qr_svg}
  const [codes, setCodes] = useState(null); // recovery codes shown once
  const [regen, setRegen] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(null);

  const loadStatus = useCallback(() => {
    api
      .get("/auth/2fa/status")
      .then((s) => { setEnabled(s.enabled); setRemaining(s.recovery_codes_remaining || 0); })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (!loading && user) loadStatus();
  }, [loading, user, loadStatus]);

  async function run(key, fn) {
    setBusy(key);
    setError(null);
    setMsg(null);
    try {
      return await fn();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  async function startSetup() {
    const s = await run("setup", () => api.post("/auth/2fa/setup"));
    if (s) { setSetup(s); setCodes(null); }
  }

  async function verify() {
    const res = await run("verify", () => api.post("/auth/2fa/verify", { code }));
    if (res) {
      setEnabled(true);
      setSetup(null);
      setCode("");
      setCodes(res.recovery_codes);
      loadStatus();
      setMsg("Two-factor authentication is now enabled. Save your recovery codes below.");
    }
  }

  async function regenerate() {
    const res = await run("regen", () => api.post("/auth/2fa/recovery-codes", { code }));
    if (res) {
      setCode("");
      setRegen(false);
      setCodes(res.recovery_codes);
      loadStatus();
      setMsg("New recovery codes generated — your previous codes no longer work.");
    }
  }

  async function disable() {
    const res = await run("disable", () => api.post("/auth/2fa/disable", { code }));
    if (res) {
      setEnabled(false);
      setSetup(null);
      setCodes(null);
      setCode("");
      setMsg("Two-factor authentication has been disabled.");
    }
  }

  if (loading) return <main className="container" />;

  return (
    <main className="container narrow">
      <div className="eyebrow">Account security</div>
      <h1 className="page-title">Two-factor authentication</h1>
      <p className="page-sub">
        Add a one-time code from an authenticator app (Google Authenticator, Authy,
        1Password…) on top of your password. Strongly recommended for admin and
        owner accounts.
      </p>

      {error && <div className="alert">{error}</div>}
      {msg && (
        <div className="alert" style={{ background: "var(--success-soft)", color: "var(--success)", borderColor: "#bbf7d0" }}>
          {msg}
        </div>
      )}

      {codes && <CodesBox codes={codes} onDone={() => setCodes(null)} />}

      <section className="panel" style={{ padding: 18 }}>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <strong>Status</strong>
          <span className={`badge ${enabled ? "badge-green" : "badge-gray"}`}>
            {enabled == null ? "…" : enabled ? "Enabled" : "Disabled"}
          </span>
        </div>

        {enabled === false && !setup && (
          <button className="btn btn-primary" disabled={busy === "setup"} onClick={startSetup}>
            {busy === "setup" ? "Preparing…" : "Enable two-factor"}
          </button>
        )}

        {setup && (
          <div>
            <p style={{ fontSize: 13, marginTop: 0 }}>1. Scan this QR code with your authenticator app:</p>
            <div
              style={{ width: 180, height: 180, background: "#fff", padding: 8, border: "1px solid var(--border)", borderRadius: 8 }}
              dangerouslySetInnerHTML={{ __html: setup.qr_svg }}
            />
            <p style={{ fontSize: 12, marginTop: 10 }} className="muted">
              Or enter this key manually:{" "}
              <code style={{ userSelect: "all", fontWeight: 700 }}>{setup.secret}</code>
            </p>
            <p style={{ fontSize: 13, marginBottom: 6 }}>2. Enter the 6-digit code to confirm:</p>
            <div className="row">
              <input className="input" style={{ width: 140 }} inputMode="numeric" placeholder="6-digit code"
                value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} />
              <button className="btn btn-primary" disabled={busy === "verify" || code.length < 6} onClick={verify}>
                {busy === "verify" ? "Verifying…" : "Verify & enable"}
              </button>
              <button className="btn btn-ghost" onClick={() => { setSetup(null); setCode(""); }}>Cancel</button>
            </div>
          </div>
        )}

        {enabled === true && (
          <div>
            <p style={{ fontSize: 13, marginTop: 0 }} className="muted">
              Two-factor is active. You have <strong>{remaining}</strong> recovery code{remaining === 1 ? "" : "s"} left.
            </p>
            <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
              {!regen ? (
                <button className="btn btn-sm" onClick={() => { setRegen(true); setCode(""); }}>
                  Regenerate recovery codes
                </button>
              ) : (
                <>
                  <input className="input" style={{ width: 150 }} placeholder="current code"
                    value={code} onChange={(e) => setCode(e.target.value)} />
                  <button className="btn btn-sm btn-primary" disabled={busy === "regen" || code.length < 6} onClick={regenerate}>
                    {busy === "regen" ? "Generating…" : "Generate new codes"}
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => { setRegen(false); setCode(""); }}>Cancel</button>
                </>
              )}
            </div>
            <div style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
              <p style={{ fontSize: 13, marginTop: 0 }} className="muted">
                To turn 2FA off, enter a current code (or a recovery code).
              </p>
              <div className="row">
                <input className="input" style={{ width: 150 }} placeholder="code"
                  value={code} onChange={(e) => setCode(e.target.value)} />
                <button className="btn btn-danger-ghost" disabled={busy === "disable" || code.length < 6} onClick={disable}>
                  {busy === "disable" ? "Disabling…" : "Disable two-factor"}
                </button>
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

function CodesBox({ codes, onDone }) {
  const text = codes.join("\n");
  function download() {
    const blob = new Blob([`Taqdeer recovery codes\n\n${text}\n`], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "taqdeer-recovery-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="panel" style={{ padding: 18, borderColor: "var(--accent)" }}>
      <strong>Save your recovery codes</strong>
      <p className="muted" style={{ fontSize: 12, margin: "4px 0 10px" }}>
        Each code works once. Store them somewhere safe — if you lose your
        authenticator device, a recovery code is the only way back in. They won't
        be shown again.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontFamily: "var(--mono)", fontSize: 14, fontWeight: 700 }}>
        {codes.map((c) => (
          <div key={c} style={{ userSelect: "all", padding: "4px 8px", background: "var(--surface-2)", borderRadius: 6 }}>{c}</div>
        ))}
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn btn-sm" onClick={download}>⬇ Download</button>
        <button className="btn btn-sm" onClick={() => navigator.clipboard?.writeText(text)}>Copy</button>
        <button className="btn btn-sm btn-primary" onClick={onDone}>I've saved them</button>
      </div>
    </section>
  );
}

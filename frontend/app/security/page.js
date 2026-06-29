"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

export default function SecurityPage() {
  const { user, loading } = useAuth();
  const [enabled, setEnabled] = useState(null);
  const [setup, setSetup] = useState(null); // {secret, otpauth_uri, qr_svg}
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(null);

  const loadStatus = useCallback(() => {
    api.get("/auth/2fa/status").then((s) => setEnabled(s.enabled)).catch((e) => setError(String(e.message || e)));
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
    if (s) setSetup(s);
  }

  async function verify() {
    const res = await run("verify", () => api.post("/auth/2fa/verify", { code }));
    if (res) {
      setEnabled(true);
      setSetup(null);
      setCode("");
      setMsg("Two-factor authentication is now enabled.");
    }
  }

  async function disable() {
    const res = await run("disable", () => api.post("/auth/2fa/disable", { code }));
    if (res) {
      setEnabled(false);
      setSetup(null);
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

      <section className="panel" style={{ padding: 18 }}>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <strong>Status</strong>
          <span className={`badge ${enabled ? "badge-green" : "badge-gray"}`}>
            {enabled == null ? "…" : enabled ? "Enabled" : "Disabled"}
          </span>
        </div>

        {/* Not enabled, not mid-setup */}
        {enabled === false && !setup && (
          <button className="btn btn-primary" disabled={busy === "setup"} onClick={startSetup}>
            {busy === "setup" ? "Preparing…" : "Enable two-factor"}
          </button>
        )}

        {/* Enrolment in progress */}
        {setup && (
          <div>
            <p style={{ fontSize: 13, marginTop: 0 }}>
              1. Scan this QR code with your authenticator app:
            </p>
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
              <input
                className="input"
                style={{ width: 140 }}
                inputMode="numeric"
                placeholder="6-digit code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              />
              <button className="btn btn-primary" disabled={busy === "verify" || code.length < 6} onClick={verify}>
                {busy === "verify" ? "Verifying…" : "Verify & enable"}
              </button>
              <button className="btn btn-ghost" onClick={() => { setSetup(null); setCode(""); }}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Enabled -> allow disable with a current code */}
        {enabled === true && (
          <div>
            <p style={{ fontSize: 13, marginTop: 0 }} className="muted">
              Two-factor is active. To turn it off, enter a current code from your app.
            </p>
            <div className="row">
              <input
                className="input"
                style={{ width: 140 }}
                inputMode="numeric"
                placeholder="6-digit code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              />
              <button className="btn btn-danger-ghost" disabled={busy === "disable" || code.length < 6} onClick={disable}>
                {busy === "disable" ? "Disabling…" : "Disable two-factor"}
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

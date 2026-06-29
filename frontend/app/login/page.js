"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import { Logo, ProcessMark } from "../Logo";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [mfa, setMfa] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.login(username, password, mfa ? otp : undefined);
      if (res.mfaRequired) {
        setMfa(true);
        setBusy(false);
        return; // show the 2FA code field and wait for it
      }
      router.push("/");
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div style={{ marginBottom: 16 }}>
          <Logo size={46} tone="dark" showTag />
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            padding: "14px 0 18px",
            marginBottom: 18,
            borderBottom: "1px solid var(--border)",
          }}
        >
          <ProcessMark width={210} />
        </div>
        <h1>Sign in</h1>
        <p className="muted" style={{ margin: "2px 0 4px", fontSize: 12 }}>
          Use the credentials provided to your company.
        </p>

        {error && <div className="alert">{error}</div>}

        <div className="field">
          <label>Username</label>
          <input
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
          />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={mfa}
          />
        </div>
        {mfa && (
          <div className="field">
            <label>Authentication code</label>
            <input
              className="input"
              autoComplete="one-time-code"
              placeholder="6-digit or recovery code"
              value={otp}
              autoFocus
              onChange={(e) => setOtp(e.target.value.replace(/[^0-9A-Za-z-]/g, "").slice(0, 12))}
            />
            <p className="muted" style={{ margin: "4px 0 0", fontSize: 11 }}>
              Enter the code from your authenticator app, or a recovery code.
            </p>
          </div>
        )}
        <button
          className="btn btn-primary"
          style={{ width: "100%", justifyContent: "center", marginTop: 18 }}
          disabled={busy || !username || !password || (mfa && otp.length < 6)}
        >
          {busy ? "Signing in…" : mfa ? "Verify & sign in" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

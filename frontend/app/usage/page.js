"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

const fmt = (n) => (Number(n) || 0).toLocaleString();
const POLL_MS = 8000;

export default function UsagePage() {
  const { user, loading, canAdmin } = useAuth();
  const isOwner = user?.role === "owner";
  const [me, setMe] = useState(null);
  const [co, setCo] = useState(null); // company breakdown (admin only)
  const [history, setHistory] = useState(null); // weekly per-user history (admin)
  const [weeksSel, setWeeksSel] = useState(8);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);
  const aliveRef = useRef(true);

  const isCompanyUser =
    user && (user.role === "admin" || user.role === "reviewer" || (user.role === "owner" && canAdmin));

  const load = useCallback(async () => {
    try {
      const mine = await api.get("/usage/me");
      if (!aliveRef.current) return;
      setMe(mine);
      if (canAdmin) {
        const breakdown = await api.get("/usage/users");
        if (aliveRef.current) setCo(breakdown);
        const hist = await api.get(`/usage/history?weeks=${weeksSel}`);
        if (aliveRef.current) setHistory(hist);
      }
      setError(null);
    } catch (e) {
      if (aliveRef.current) setError(String(e.message || e));
    }
  }, [canAdmin, weeksSel]);

  useEffect(() => {
    aliveRef.current = true;
    if (!loading && isCompanyUser) {
      load();
      const id = setInterval(() => {
        load();
        setTick((t) => t + 1);
      }, POLL_MS);
      return () => {
        aliveRef.current = false;
        clearInterval(id);
      };
    }
    return () => {
      aliveRef.current = false;
    };
  }, [loading, isCompanyUser, load]);

  if (loading) return <main className="container" />;
  if (user && !isCompanyUser)
    return (
      <main className="container narrow">
        <div className="panel">
          <div className="empty">Token usage is tracked for company users.</div>
        </div>
      </main>
    );

  const limit = me?.company_weekly_limit || 0;
  const used = me?.company_weekly_used || 0;
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const over = limit && used >= limit;

  return (
    <main className="container">
      <div className="eyebrow">AI consumption</div>
      <h1 className="page-title">
        Token usage <LiveDot tick={tick} />
      </h1>
      <p className="page-sub">
        Live tracker of AI tokens spent on RFP analysis and matching. The weekly
        company allowance resets every Monday. Updates automatically.
      </p>

      {error && <div className="alert">{error}</div>}

      {/* Company weekly allowance */}
      <section className="panel" style={{ padding: 18 }}>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
          <strong>Company — this week</strong>
          <span className={`badge ${over ? "badge-red" : pct >= 80 ? "badge-amber" : "badge-green"}`}>
            {over ? "limit reached" : `${pct}% used`}
          </span>
        </div>
        <div className={`meter ${over ? "over" : ""}`}>
          <span style={{ width: `${pct}%` }} />
        </div>
        <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }} >
          <span className="muted" style={{ fontSize: 13 }}>
            {fmt(used)} / {fmt(limit)} tokens
          </span>
          <span className="muted" style={{ fontSize: 13 }}>
            {fmt(me?.company_weekly_remaining)} remaining
          </span>
        </div>
      </section>

      {/* The signed-in user's own spend */}
      <div className="statbar">
        <Stat k="You — this week" v={fmt(me?.tokens_this_week)} />
        <Stat k="You — all time" v={fmt(me?.tokens_all_time)} />
        {canAdmin && <Stat k="Team members" v={co ? co.users.length : "—"} />}
      </div>

      {/* Per-user breakdown (admins / owner acting) */}
      {canAdmin && (
        <section className="panel">
          <div className="panel-head">
            <h2>Per-user spend</h2>
            <span className="tag">
              {isOwner && co?.billing_multiplier > 1
                ? `billed (${co.billing_multiplier}×) · actual`
                : "this week · all-time"}
            </span>
          </div>
          {!co && <div className="empty">Loading…</div>}
          {co && co.users.length === 0 && (
            <div className="empty">No users yet.</div>
          )}
          {co && co.users.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th className="num">This week</th>
                  <th>Share of company week</th>
                  {isOwner && <th className="num">Actual this week</th>}
                  <th className="num">All time</th>
                </tr>
              </thead>
              <tbody>
                {co.users.map((u) => {
                  const share = used ? Math.round((u.tokens_this_week / used) * 100) : 0;
                  return (
                    <tr key={u.user_id ?? "former"}>
                      <td>
                        <strong>{u.full_name || u.username}</strong>{" "}
                        {(u.full_name && (
                          <span className="muted" style={{ fontSize: 12 }}>
                            {u.username}
                          </span>
                        )) ||
                          null}
                        {u.user_id === me?.user_id && (
                          <span className="badge badge-green" style={{ marginLeft: 6 }}>you</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${u.role === "admin" ? "badge-amber" : "badge-gray"}`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="num nums">{fmt(u.tokens_this_week)}</td>
                      <td>
                        <div className="meter" style={{ maxWidth: 220 }}>
                          <span style={{ width: `${share}%` }} />
                        </div>
                        <span className="muted" style={{ fontSize: 11 }}>{share}%</span>
                      </td>
                      {isOwner && (
                        <td className="num nums muted">{fmt(u.actual_this_week)}</td>
                      )}
                      <td className="num nums">{fmt(u.tokens_all_time)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      )}

      {/* Weekly history — who spends the most over time (admins / owner) */}
      {canAdmin && (
        <section className="panel">
          <div className="panel-head">
            <h2>Weekly history</h2>
            <select
              className="input"
              style={{ width: 130 }}
              value={weeksSel}
              onChange={(e) => setWeeksSel(Number(e.target.value))}
            >
              <option value={4}>Last 4 weeks</option>
              <option value={8}>Last 8 weeks</option>
              <option value={12}>Last 12 weeks</option>
              <option value={26}>Last 26 weeks</option>
            </select>
          </div>
          {!history && <div className="empty">Loading…</div>}
          {history && history.users.length === 0 && (
            <div className="empty">No usage recorded yet.</div>
          )}
          {history && history.users.length > 0 && (
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>User</th>
                    {history.weeks.map((w, i) => (
                      <th key={w} className="num" title={`Week of ${w}`}>
                        {weekLabel(w)}
                        {i === history.weeks.length - 1 && (
                          <span className="muted" style={{ fontSize: 10 }}> (now)</span>
                        )}
                      </th>
                    ))}
                    <th className="num">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {history.users.map((u, ui) => {
                    const peak = Math.max(1, ...u.weekly);
                    return (
                      <tr key={u.user_id ?? `former-${ui}`}>
                        <td>
                          <strong>{u.full_name || u.username}</strong>
                          {ui === 0 && u.total > 0 && (
                            <span className="badge badge-amber" style={{ marginLeft: 6 }}>
                              top spender
                            </span>
                          )}
                        </td>
                        {u.weekly.map((v, wi) => (
                          <td key={wi} className="num nums" title={fmt(v) + " tokens"}>
                            {v > 0 ? (
                              <>
                                <span>{fmt(v)}</span>
                                <div className="meter" style={{ marginTop: 3, opacity: 0.8 }}>
                                  <span style={{ width: `${Math.round((v / peak) * 100)}%` }} />
                                </div>
                              </>
                            ) : (
                              <span className="muted">·</span>
                            )}
                          </td>
                        ))}
                        <td className="num nums">
                          <strong>{fmt(u.total)}</strong>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="panel-body">
            <div className="tag">
              Billed tokens per ISO week (resets Mondays). Sorted by who spent the
              most over the period.
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

// "2026-06-22" -> "Jun 22"
function weekLabel(iso) {
  const [y, m, d] = (iso || "").split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  if (!m || !d) return iso;
  return `${months[m - 1]} ${d}`;
}

function LiveDot({ tick }) {
  return (
    <span
      title="Updates automatically"
      style={{
        display: "inline-block",
        width: 9,
        height: 9,
        borderRadius: "50%",
        background: "#10b981",
        marginLeft: 8,
        verticalAlign: "middle",
        opacity: tick % 2 ? 0.55 : 1,
        transition: "opacity .4s",
      }}
    />
  );
}

function Stat({ k, v }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

const fmt = (n) => (Number(n) || 0).toLocaleString();

export default function CompaniesPage() {
  const { user, loading, enterCompany } = useAuth();
  const [companies, setCompanies] = useState(null);
  const [plans, setPlans] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [adding, setAdding] = useState(false);
  const [nc, setNc] = useState({ name: "", admin_username: "", admin_full_name: "", admin_password: "", plan_id: "" });

  const load = useCallback(async () => {
    try {
      const [cos, pls] = await Promise.all([api.get("/companies"), api.get("/plans")]);
      setCompanies(cos);
      setPlans(pls);
    } catch (e) {
      setError(String(e.message || e));
    }
  }, []);

  useEffect(() => {
    if (!loading && user?.role === "owner") load();
  }, [loading, user, load]);

  async function act(key, fn) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <main className="container" />;
  if (user && user.role !== "owner")
    return (
      <main className="container narrow">
        <div className="panel"><div className="empty">Owner only.</div></div>
      </main>
    );

  return (
    <main className="container">
      <div className="eyebrow">Platform administration</div>
      <h1 className="page-title">Companies</h1>
      <p className="page-sub">
        Each company is an isolated tenant on a subscription plan. The plan caps
        its weekly AI-token usage (resets Mondays); edit limits under Plans.
      </p>

      <div className="statbar">
        <Stat k="Companies" v={companies?.length ?? "—"} />
        <Stat k="Active" v={companies ? companies.filter((c) => c.is_active).length : "—"} />
        <div className="actions">
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            + New company
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      {adding && (
        <form
          className="panel"
          style={{ padding: 16 }}
          onSubmit={(e) => {
            e.preventDefault();
            act("create", async () => {
              const body = { ...nc };
              if (body.plan_id) body.plan_id = Number(body.plan_id);
              else delete body.plan_id;
              await api.post("/companies", body);
              setNc({ name: "", admin_username: "", admin_full_name: "", admin_password: "", plan_id: "" });
              setAdding(false);
            });
          }}
        >
          <div className="eyebrow" style={{ marginBottom: 8 }}>New company + first admin</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 10 }}>
            <Field label="Company name">
              <input className="input" value={nc.name} onChange={(e) => setNc({ ...nc, name: e.target.value })} required />
            </Field>
            <Field label="Plan">
              <select className="input" value={nc.plan_id} onChange={(e) => setNc({ ...nc, plan_id: e.target.value })}>
                <option value="">Default (cheapest)</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} — {fmt(p.weekly_token_limit)}/wk</option>
                ))}
              </select>
            </Field>
            <Field label="Admin username / email">
              <input className="input" value={nc.admin_username} onChange={(e) => setNc({ ...nc, admin_username: e.target.value })} required placeholder="adminclient1@gmail.com" />
            </Field>
            <Field label="Admin password">
              <input className="input" value={nc.admin_password} onChange={(e) => setNc({ ...nc, admin_password: e.target.value })} required />
            </Field>
            <Field label="Admin full name">
              <input className="input" value={nc.admin_full_name} onChange={(e) => setNc({ ...nc, admin_full_name: e.target.value })} />
            </Field>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" type="submit" disabled={busy === "create"}>
              {busy === "create" ? "Creating…" : "Create company"}
            </button>
            <button className="btn btn-sm btn-ghost" type="button" onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </form>
      )}

      <section className="panel">
        <div className="panel-head"><h2>Tenants</h2></div>
        {!companies && <div className="empty">Loading…</div>}
        {companies && companies.length === 0 && (
          <div className="empty">No companies yet — create one above.</div>
        )}
        {companies && companies.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Plan</th>
                <th>Weekly tokens (used / limit)</th>
                <th className="num">Users</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((co) => {
                const pct = co.weekly_token_limit
                  ? Math.min(100, Math.round((co.weekly_tokens_used / co.weekly_token_limit) * 100))
                  : 0;
                const over = co.weekly_token_limit && co.weekly_tokens_used >= co.weekly_token_limit;
                return (
                  <tr key={co.id}>
                    <td>
                      <strong>{co.name}</strong>{" "}
                      <span className="muted nums" style={{ fontSize: 12 }}>#{co.id}</span>
                    </td>
                    <td>
                      <select
                        className="input"
                        style={{ width: 140 }}
                        value={co.plan_id ?? ""}
                        onChange={(e) =>
                          act(`plan-${co.id}`, () =>
                            api.patch(`/companies/${co.id}`, { plan_id: Number(e.target.value) })
                          )
                        }
                      >
                        {co.plan_id == null && <option value="">— none —</option>}
                        {plans.map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className="nums">
                      <span style={{ color: over ? "var(--danger)" : "var(--text)" }}>
                        {fmt(co.weekly_tokens_used)}
                      </span>{" "}
                      / {fmt(co.weekly_token_limit)}{" "}
                      <span className="muted" style={{ fontSize: 11 }}>({pct}%)</span>
                    </td>
                    <td className="num">{co.user_count}</td>
                    <td>
                      <span className={`badge ${co.is_active ? "badge-green" : "badge-gray"}`}>
                        {co.is_active ? "active" : "disabled"}
                      </span>
                    </td>
                    <td className="cell-actions">
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => enterCompany({ id: co.id, name: co.name })}
                        title="Open this company and manage it as its admin"
                      >
                        Open →
                      </button>
                      <button
                        className="btn btn-sm"
                        onClick={() =>
                          act(`toggle-${co.id}`, () =>
                            api.patch(`/companies/${co.id}`, { is_active: !co.is_active })
                          )
                        }
                      >
                        {co.is_active ? "Disable" : "Enable"}
                      </button>
                      <button
                        className="btn btn-sm btn-danger-ghost"
                        onClick={() =>
                          confirm(
                            `Delete ${co.name}? This permanently removes its users and all catalog/RFP/BoQ data.`
                          ) && act(`del-${co.id}`, () => api.del(`/companies/${co.id}`))
                        }
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

function Field({ label, children }) {
  return (
    <div className="field" style={{ marginTop: 0 }}>
      <label>{label}</label>
      {children}
    </div>
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

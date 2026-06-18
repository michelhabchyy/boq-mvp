"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

export default function CompaniesPage() {
  const { user, loading } = useAuth();
  const [companies, setCompanies] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [adding, setAdding] = useState(false);
  const [nc, setNc] = useState({ name: "", admin_username: "", admin_full_name: "", admin_password: "" });

  const load = useCallback(
    () => api.get("/companies").then(setCompanies).catch((e) => setError(String(e.message || e))),
    []
  );

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
        <div className="panel">
          <div className="empty">Owner only.</div>
        </div>
      </main>
    );

  return (
    <main className="container narrow">
      <div className="eyebrow">Platform administration</div>
      <h1 className="page-title">Companies</h1>
      <p className="page-sub">
        Each company is an isolated tenant. Create one with its first admin — that
        admin signs in and sees only their own catalog, RFPs and BoQs.
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
              await api.post("/companies", nc);
              setNc({ name: "", admin_username: "", admin_full_name: "", admin_password: "" });
              setAdding(false);
            });
          }}
        >
          <div className="eyebrow" style={{ marginBottom: 8 }}>
            New company + first admin
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 10 }}>
            <Field label="Company name">
              <input className="input" value={nc.name} onChange={(e) => setNc({ ...nc, name: e.target.value })} required />
            </Field>
            <Field label="Admin full name">
              <input className="input" value={nc.admin_full_name} onChange={(e) => setNc({ ...nc, admin_full_name: e.target.value })} />
            </Field>
            <Field label="Admin username / email">
              <input className="input" value={nc.admin_username} onChange={(e) => setNc({ ...nc, admin_username: e.target.value })} required placeholder="adminclient1@gmail.com" />
            </Field>
            <Field label="Admin password">
              <input className="input" value={nc.admin_password} onChange={(e) => setNc({ ...nc, admin_password: e.target.value })} required />
            </Field>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" type="submit" disabled={busy === "create"}>
              {busy === "create" ? "Creating…" : "Create company"}
            </button>
            <button className="btn btn-sm btn-ghost" type="button" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Tenants</h2>
        </div>
        {!companies && <div className="empty">Loading…</div>}
        {companies && companies.length === 0 && (
          <div className="empty">No companies yet — create one above.</div>
        )}
        {companies && companies.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th className="num">Users</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((co) => (
                <tr key={co.id}>
                  <td>
                    <strong>{co.name}</strong>{" "}
                    <span className="muted nums" style={{ fontSize: 12 }}>#{co.id}</span>
                  </td>
                  <td className="num">{co.user_count}</td>
                  <td>
                    <span className={`badge ${co.is_active ? "badge-green" : "badge-gray"}`}>
                      {co.is_active ? "active" : "disabled"}
                    </span>
                  </td>
                  <td className="cell-actions">
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
              ))}
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

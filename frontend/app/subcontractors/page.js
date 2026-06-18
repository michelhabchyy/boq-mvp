"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

export default function SubcontractorsPage() {
  const { user, loading } = useAuth();
  const [subs, setSubs] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [adding, setAdding] = useState(false);
  const [ns, setNs] = useState({ name: "", trade: "" });
  const [openId, setOpenId] = useState(null);

  const load = useCallback(
    () => api.get("/subcontractors").then(setSubs).catch((e) => setError(String(e.message || e))),
    []
  );
  useEffect(() => {
    if (!loading && user?.role === "admin") load();
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
  if (user && user.role !== "admin")
    return (
      <main className="container narrow">
        <div className="panel">
          <div className="empty">Admin only.</div>
        </div>
      </main>
    );

  return (
    <main className="container">
      <div className="eyebrow">Contractor</div>
      <h1 className="page-title">Subcontractors</h1>
      <p className="page-sub">
        Create subcontractors and their logins. Each subcontractor maintains its own
        item list, which pools into your catalog tagged by subcontractor.
      </p>

      <div className="statbar">
        <Stat k="Subcontractors" v={subs?.length ?? "—"} />
        <Stat k="Active" v={subs ? subs.filter((s) => s.is_active).length : "—"} />
        <div className="actions">
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            + New subcontractor
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
              await api.post("/subcontractors", ns);
              setNs({ name: "", trade: "" });
              setAdding(false);
            });
          }}
        >
          <div className="eyebrow" style={{ marginBottom: 8 }}>New subcontractor</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 10 }}>
            <Field label="Name">
              <input className="input" value={ns.name} onChange={(e) => setNs({ ...ns, name: e.target.value })} required />
            </Field>
            <Field label="Trade / discipline">
              <input className="input" value={ns.trade} onChange={(e) => setNs({ ...ns, trade: e.target.value })} placeholder="Electrical, Plumbing…" />
            </Field>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" type="submit">Create</button>
            <button className="btn btn-sm btn-ghost" type="button" onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </form>
      )}

      <section className="panel">
        <div className="panel-head"><h2>Subcontractors</h2></div>
        {!subs && <div className="empty">Loading…</div>}
        {subs && subs.length === 0 && <div className="empty">None yet — add one above.</div>}
        {subs && subs.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th><th>Trade</th><th>Status</th>
                <th className="num">Users</th><th className="num">Items</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.trade || <span className="muted">—</span>}</td>
                  <td><span className={`badge ${s.is_active ? "badge-green" : "badge-gray"}`}>{s.is_active ? "active" : "disabled"}</span></td>
                  <td className="num">{s.user_count}</td>
                  <td className="num">{s.item_count}</td>
                  <td className="cell-actions">
                    <button className="btn btn-sm" onClick={() => setOpenId(openId === s.id ? null : s.id)}>
                      {openId === s.id ? "Hide users" : "Users"}
                    </button>
                    <button className="btn btn-sm" onClick={() => act(`t-${s.id}`, () => api.patch(`/subcontractors/${s.id}`, { is_active: !s.is_active }))}>
                      {s.is_active ? "Disable" : "Enable"}
                    </button>
                    <button className="btn btn-sm btn-danger-ghost" onClick={() => confirm(`Delete ${s.name}? Removes its users and items.`) && act(`d-${s.id}`, () => api.del(`/subcontractors/${s.id}`))}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {openId && <SubUsers subId={openId} setError={setError} />}
    </main>
  );
}

function SubUsers({ subId, setError }) {
  const [users, setUsers] = useState(null);
  const [nu, setNu] = useState({ username: "", full_name: "", password: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api.get(`/subcontractors/${subId}/users`).then(setUsers).catch((e) => setError(String(e.message || e))),
    [subId, setError]
  );
  useEffect(() => { load(); }, [load]);

  async function call(fn) {
    setBusy(true); setError(null);
    try { await fn(); await load(); } catch (e) { setError(String(e.message || e)); } finally { setBusy(false); }
  }

  return (
    <section className="panel">
      <div className="panel-head"><h2>Subcontractor logins</h2></div>
      <div className="panel-body">
        <form
          className="row"
          style={{ gap: 8, marginBottom: 12, flexWrap: "wrap" }}
          onSubmit={(e) => { e.preventDefault(); call(async () => { await api.post(`/subcontractors/${subId}/users`, nu); setNu({ username: "", full_name: "", password: "" }); }); }}
        >
          <input className="input" style={{ width: 220 }} placeholder="username / email" value={nu.username} onChange={(e) => setNu({ ...nu, username: e.target.value })} required />
          <input className="input" style={{ width: 160 }} placeholder="full name" value={nu.full_name} onChange={(e) => setNu({ ...nu, full_name: e.target.value })} />
          <input className="input" style={{ width: 160 }} placeholder="password" value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })} required />
          <button className="btn btn-sm btn-primary" disabled={busy}>Add login</button>
        </form>
        {!users && <div className="muted">Loading…</div>}
        {users && users.length === 0 && <div className="muted">No logins yet.</div>}
        {users && users.length > 0 && (
          <table className="table">
            <thead><tr><th>User</th><th>Status</th><th style={{ textAlign: "right" }}>Actions</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td><strong>{u.username}</strong>{u.full_name && <span className="muted" style={{ fontSize: 12 }}> · {u.full_name}</span>}</td>
                  <td><span className={`badge ${u.is_active ? "badge-green" : "badge-gray"}`}>{u.is_active ? "active" : "disabled"}</span></td>
                  <td className="cell-actions">
                    <button className="btn btn-sm" onClick={() => call(() => api.patch(`/subcontractors/${subId}/users/${u.id}`, { is_active: !u.is_active }))}>{u.is_active ? "Disable" : "Enable"}</button>
                    <button className="btn btn-sm" onClick={() => { const pw = prompt(`New password for ${u.username}:`); if (pw) call(() => api.patch(`/subcontractors/${subId}/users/${u.id}`, { password: pw })); }}>Reset pw</button>
                    <button className="btn btn-sm btn-danger-ghost" onClick={() => confirm(`Delete ${u.username}?`) && call(() => api.del(`/subcontractors/${subId}/users/${u.id}`))}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function Field({ label, children }) {
  return (<div className="field" style={{ marginTop: 0 }}><label>{label}</label>{children}</div>);
}
function Stat({ k, v }) {
  return (<div className="stat"><div className="k">{k}</div><div className="v">{v}</div></div>);
}

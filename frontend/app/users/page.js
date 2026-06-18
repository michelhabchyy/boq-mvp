"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

export default function UsersPage() {
  const { user, loading } = useAuth();
  const [users, setUsers] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [adding, setAdding] = useState(false);
  const [nu, setNu] = useState({ username: "", full_name: "", password: "", role: "reviewer" });

  const load = useCallback(() => api.get("/users").then(setUsers).catch((e) => setError(String(e.message || e))), []);

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
    <main className="container narrow">
      <div className="eyebrow">Access control</div>
      <h1 className="page-title">Users</h1>

      <div className="statbar">
        <Stat k="Users" v={users?.length ?? "—"} />
        <Stat k="Admins" v={users ? users.filter((u) => u.role === "admin").length : "—"} />
        <div className="actions">
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            + New user
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
              await api.post("/users", nu);
              setNu({ username: "", full_name: "", password: "", role: "reviewer" });
              setAdding(false);
            });
          }}
        >
          <div className="eyebrow" style={{ marginBottom: 8 }}>
            New user
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 10 }}>
            <Field label="Username">
              <input className="input" value={nu.username} onChange={(e) => setNu({ ...nu, username: e.target.value })} required />
            </Field>
            <Field label="Full name">
              <input className="input" value={nu.full_name} onChange={(e) => setNu({ ...nu, full_name: e.target.value })} />
            </Field>
            <Field label="Password">
              <input className="input" type="text" value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })} required />
            </Field>
            <Field label="Role">
              <select className="input" value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}>
                <option value="reviewer">reviewer</option>
                <option value="admin">admin</option>
              </select>
            </Field>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" type="submit">
              Create user
            </button>
            <button className="btn btn-sm btn-ghost" type="button" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Accounts</h2>
        </div>
        {!users && <div className="empty">Loading…</div>}
        {users && (
          <table className="table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const self = u.id === user?.id;
                return (
                  <tr key={u.id}>
                    <td>
                      <strong>{u.username}</strong>
                      {self && <span className="tag" style={{ marginLeft: 6 }}>you</span>}
                      {u.full_name && (
                        <div className="muted" style={{ fontSize: 12 }}>
                          {u.full_name}
                        </div>
                      )}
                    </td>
                    <td>
                      <select
                        className="input"
                        style={{ width: 110 }}
                        value={u.role}
                        disabled={self}
                        onChange={(e) =>
                          act(`role-${u.id}`, () => api.patch(`/users/${u.id}`, { role: e.target.value }))
                        }
                      >
                        <option value="reviewer">reviewer</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td>
                      <span className={`badge ${u.is_active ? "badge-green" : "badge-gray"}`}>
                        {u.is_active ? "active" : "disabled"}
                      </span>
                    </td>
                    <td className="cell-actions">
                      <button
                        className="btn btn-sm"
                        disabled={self}
                        onClick={() =>
                          act(`active-${u.id}`, () =>
                            api.patch(`/users/${u.id}`, { is_active: !u.is_active })
                          )
                        }
                      >
                        {u.is_active ? "Disable" : "Enable"}
                      </button>
                      <button
                        className="btn btn-sm"
                        onClick={() => {
                          const pw = prompt(`New password for ${u.username}:`);
                          if (pw) act(`pw-${u.id}`, () => api.patch(`/users/${u.id}`, { password: pw }));
                        }}
                      >
                        Reset pw
                      </button>
                      <button
                        className="btn btn-sm btn-danger-ghost"
                        disabled={self}
                        onClick={() =>
                          confirm(`Delete user ${u.username}?`) &&
                          act(`del-${u.id}`, () => api.del(`/users/${u.id}`))
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

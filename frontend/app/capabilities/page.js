"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

export default function CapabilitiesPage() {
  const { user, loading, canAdmin } = useAuth();
  const [tree, setTree] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const canView = canAdmin || user?.role === "reviewer";

  const load = useCallback(() => {
    api.get("/capabilities").then(setTree).catch((e) => setError(String(e.message || e)));
  }, []);
  useEffect(() => { if (!loading && canView) load(); }, [loading, canView, load]);

  async function call(fn) {
    setBusy(true); setError(null);
    try { setTree(await fn()); } catch (e) { setError(String(e.message || e)); } finally { setBusy(false); }
  }

  if (loading) return <main className="container" />;
  if (user && !canView)
    return <main className="container narrow"><div className="panel"><div className="empty">Company team only.</div></div></main>;

  return (
    <main className="container narrow">
      <div className="eyebrow">Company profile</div>
      <h1 className="page-title">Fields, services &amp; sub-services</h1>
      <p className="page-sub">
        Define the <strong>fields</strong> your company works in, the <strong>services</strong> you
        provide in each, and the <strong>sub-services</strong> under them — marking each as done
        in-house or externally. New projects pick from this structure.
      </p>

      {error && <div className="alert">{error}</div>}

      {canAdmin && (
        <div className="panel" style={{ padding: 14, marginBottom: 16 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Add a field</div>
          <AddInline placeholder="e.g. MEP, Civil, Finishing" btn="Add field" busy={busy}
            onAdd={(name) => call(() => api.post("/capabilities/fields", { name }))} />
        </div>
      )}

      {!tree && <div className="empty">Loading…</div>}
      {tree && tree.length === 0 && (
        <div className="empty">No fields yet.{canAdmin ? " Add your first field above." : ""}</div>
      )}

      {tree && tree.map((field) => (
        <section className="panel" key={field.id} style={{ marginBottom: 14 }}>
          <div className="panel-head">
            <h2 style={{ textTransform: "none", fontSize: 14, color: "var(--text)" }}>{field.name}</h2>
            {canAdmin && (
              <div className="row">
                <button className="btn btn-sm" disabled={busy} onClick={() => {
                  const n = prompt("Rename field", field.name);
                  if (n && n.trim()) call(() => api.patch(`/capabilities/fields/${field.id}`, { name: n.trim() }));
                }}>Rename</button>
                <button className="btn btn-sm btn-danger-ghost" disabled={busy} onClick={() =>
                  confirm(`Delete field "${field.name}" and all its services?`) &&
                  call(() => api.del(`/capabilities/fields/${field.id}`))
                }>Delete</button>
              </div>
            )}
          </div>

          <div className="panel-body">
            {field.services.length === 0 && (
              <div className="muted" style={{ fontSize: 13, marginBottom: canAdmin ? 10 : 0 }}>No services yet.</div>
            )}

            {field.services.map((svc) => (
              <div key={svc.id} style={{ borderLeft: "3px solid var(--accent)", paddingLeft: 12, margin: "0 0 14px" }}>
                <div className="between">
                  <strong style={{ fontSize: 13 }}>{svc.name}</strong>
                  {canAdmin && (
                    <div className="row">
                      <button className="btn btn-sm" disabled={busy} onClick={() => {
                        const n = prompt("Rename service", svc.name);
                        if (n && n.trim()) call(() => api.patch(`/capabilities/services/${svc.id}`, { name: n.trim() }));
                      }}>Rename</button>
                      <button className="btn btn-sm btn-danger-ghost" disabled={busy} onClick={() =>
                        confirm(`Delete service "${svc.name}"?`) &&
                        call(() => api.del(`/capabilities/services/${svc.id}`))
                      }>Delete</button>
                    </div>
                  )}
                </div>

                {/* sub-services */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "8px 0" }}>
                  {svc.sub_services.length === 0 && <span className="muted" style={{ fontSize: 12 }}>No sub-services.</span>}
                  {svc.sub_services.map((ss) => (
                    <span key={ss.id} className="badge" style={{
                      display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 8px",
                      background: ss.in_house ? "var(--success-soft)" : "var(--warn-soft)",
                      color: ss.in_house ? "var(--success)" : "var(--accent-text)",
                      border: "1px solid var(--border)",
                    }}>
                      {ss.name}
                      <em style={{ fontStyle: "normal", opacity: 0.8, fontWeight: 600 }}>· {ss.in_house ? "In-house" : "External"}</em>
                      {canAdmin && (
                        <>
                          <button title="Toggle in-house / external" style={miniBtn} disabled={busy}
                            onClick={() => call(() => api.patch(`/capabilities/subservices/${ss.id}`, { in_house: !ss.in_house }))}>⇄</button>
                          <button title="Delete" style={miniBtn} disabled={busy}
                            onClick={() => call(() => api.del(`/capabilities/subservices/${ss.id}`))}>×</button>
                        </>
                      )}
                    </span>
                  ))}
                </div>

                {canAdmin && (
                  <SubAdd busy={busy} onAdd={(name, in_house) =>
                    call(() => api.post(`/capabilities/services/${svc.id}/subservices`, { name, in_house }))} />
                )}
              </div>
            ))}

            {canAdmin && (
              <div style={{ marginTop: 6 }}>
                <AddInline placeholder="Add a service (e.g. HVAC)" btn="Add service" busy={busy}
                  onAdd={(name) => call(() => api.post(`/capabilities/fields/${field.id}/services`, { name }))} />
              </div>
            )}
          </div>
        </section>
      ))}
    </main>
  );
}

const miniBtn = {
  border: "none", background: "transparent", cursor: "pointer", fontWeight: 700,
  color: "inherit", padding: "0 2px", lineHeight: 1,
};

function AddInline({ placeholder, btn, onAdd, busy }) {
  const [v, setV] = useState("");
  return (
    <form className="row" style={{ gap: 6 }} onSubmit={(e) => { e.preventDefault(); if (v.trim()) { onAdd(v.trim()); setV(""); } }}>
      <input className="input" style={{ maxWidth: 260 }} placeholder={placeholder} value={v} onChange={(e) => setV(e.target.value)} />
      <button className="btn btn-sm btn-primary" disabled={busy || !v.trim()}>{btn}</button>
    </form>
  );
}

function SubAdd({ onAdd, busy }) {
  const [v, setV] = useState("");
  const [ih, setIh] = useState(true);
  return (
    <form className="row" style={{ gap: 6, flexWrap: "wrap" }} onSubmit={(e) => { e.preventDefault(); if (v.trim()) { onAdd(v.trim(), ih); setV(""); } }}>
      <input className="input" style={{ maxWidth: 200 }} placeholder="Add a sub-service" value={v} onChange={(e) => setV(e.target.value)} />
      <select className="input" style={{ width: 120 }} value={ih ? "in" : "ex"} onChange={(e) => setIh(e.target.value === "in")}>
        <option value="in">In-house</option>
        <option value="ex">External</option>
      </select>
      <button className="btn btn-sm" disabled={busy || !v.trim()}>Add</button>
    </form>
  );
}

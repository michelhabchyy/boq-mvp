"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

const STATUSES = [
  { key: "lead", label: "Lead", color: "#64748b" },
  { key: "bidding", label: "Bidding", color: "#0e6e6e" },
  { key: "shortlisted", label: "Shortlisted", color: "#2563eb" },
  { key: "awarded", label: "Awarded", color: "#2fb573" },
  { key: "in_progress", label: "In progress", color: "#b45309" },
  { key: "completed", label: "Completed", color: "#15803d" },
  { key: "lost", label: "Lost", color: "#b3261e" },
];
const LABEL = Object.fromEntries(STATUSES.map((s) => [s.key, s.label]));
const COLOR = Object.fromEntries(STATUSES.map((s) => [s.key, s.color]));

const BLANK = {
  name: "", industry: "", fields: "", description: "", awarded_from: "", start_date: "", end_date: "",
};
const fmtDate = (d) => (d ? new Date(d).toLocaleDateString() : "");

export default function ProjectsPage() {
  const { user, loading, canAdmin } = useAuth();
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dragId, setDragId] = useState(null);
  const [overCol, setOverCol] = useState(null);
  const [modal, setModal] = useState(null); // {mode:"new"} | {mode:"edit", id}

  const canView = canAdmin || user?.role === "reviewer";

  const load = useCallback(() => {
    api.get("/projects?limit=1000").then(setProjects).catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (!loading && canView) load();
  }, [loading, canView, load]);

  async function move(id, status) {
    const p = projects?.find((x) => x.id === id);
    if (!p || p.status === status) return;
    setProjects((ps) => ps.map((x) => (x.id === id ? { ...x, status } : x))); // optimistic
    try {
      await api.post(`/projects/${id}/status`, { status });
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      load();
    }
  }

  if (loading) return <main className="container" />;
  if (user && !canView)
    return (
      <main className="container narrow">
        <div className="panel"><div className="empty">Company team only.</div></div>
      </main>
    );

  const byStatus = (k) => (projects || []).filter((p) => p.status === k);

  return (
    <main className="container">
      <div className="eyebrow">Business development</div>
      <div className="between">
        <div>
          <h1 className="page-title">Projects pipeline</h1>
          <p className="page-sub" style={{ margin: 0 }}>
            Track every opportunity from lead to completion — drag a card to move it
            along the pipeline.
          </p>
        </div>
        {canAdmin && (
          <button className="btn btn-primary" onClick={() => setModal({ mode: "new" })}>+ New project</button>
        )}
      </div>

      {error && <div className="alert" style={{ marginTop: 12 }}>{error}</div>}

      {!projects && <div className="empty">Loading…</div>}

      {projects && (
        <div className="kanban" style={{ marginTop: 14 }}>
          {STATUSES.map((s) => {
            const cards = byStatus(s.key);
            return (
              <div
                key={s.key}
                className={`kan-col ${overCol === s.key ? "over" : ""}`}
                onDragOver={(e) => { if (canAdmin) { e.preventDefault(); setOverCol(s.key); } }}
                onDragLeave={() => setOverCol((c) => (c === s.key ? null : c))}
                onDrop={(e) => { e.preventDefault(); setOverCol(null); if (dragId != null) move(dragId, s.key); }}
              >
                <div className="kan-col-head" style={{ "--kc": s.color }}>
                  <span className="lbl"><span className="d" /> {s.label}</span>
                  <span className="count">{cards.length}</span>
                </div>
                <div className="kan-col-body">
                  {cards.length === 0 && <div className="kan-empty">—</div>}
                  {cards.map((p) => (
                    <div
                      key={p.id}
                      className={`kan-card ${dragId === p.id ? "dragging" : ""}`}
                      draggable={canAdmin}
                      onDragStart={() => setDragId(p.id)}
                      onDragEnd={() => setDragId(null)}
                      onClick={() => setModal({ mode: "edit", id: p.id })}
                    >
                      <div className="nm">{p.name}</div>
                      <div className="meta">
                        {p.industry && <span className="badge badge-amber">{p.industry}</span>}
                        {p.awarded_from && <span>· {p.awarded_from}</span>}
                      </div>
                      {(p.start_date || p.end_date) && (
                        <div className="meta">
                          🗓 {fmtDate(p.start_date) || "…"} – {fmtDate(p.end_date) || "…"}
                        </div>
                      )}
                      {p.fields && <div className="meta muted">{p.fields}</div>}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modal && (
        <ProjectModal
          mode={modal.mode}
          id={modal.id}
          canAdmin={canAdmin}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); load(); }}
          setBusy={setBusy}
          busy={busy}
        />
      )}
    </main>
  );
}

function ProjectModal({ mode, id, canAdmin, onClose, onSaved, busy, setBusy }) {
  const isNew = mode === "new";
  const [f, setF] = useState(BLANK);
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("lead");
  const [note, setNote] = useState("");
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  useEffect(() => {
    if (isNew) return;
    api.get(`/projects/${id}`).then((d) => {
      const p = d.project;
      setF({
        name: p.name || "", industry: p.industry || "", fields: p.fields || "",
        description: p.description || "", awarded_from: p.awarded_from || "",
        start_date: p.start_date || "", end_date: p.end_date || "",
      });
      setStatus(p.status);
      setEvents(d.events || []);
    }).catch((e) => setErr(String(e.message || e)));
  }, [isNew, id]);

  const payload = () => ({
    name: f.name,
    industry: f.industry || null,
    fields: f.fields || null,
    description: f.description || null,
    awarded_from: f.awarded_from || null,
    start_date: f.start_date || null,
    end_date: f.end_date || null,
  });

  async function run(fn) {
    setBusy(true); setErr(null);
    try { await fn(); } catch (e) { setErr(String(e.message || e)); setBusy(false); }
  }

  const save = () =>
    run(async () => {
      if (isNew) await api.post("/projects", payload());
      else await api.patch(`/projects/${id}`, payload());
      onSaved();
    });

  const applyStatus = (s) =>
    run(async () => {
      await api.post(`/projects/${id}/status`, { status: s, note: note || undefined });
      onSaved();
    });

  const remove = () =>
    confirm(`Delete "${f.name}"? This removes the project and its history.`) &&
    run(async () => { await api.del(`/projects/${id}`); onSaved(); });

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{isNew ? "New project" : "Project details"}</h2>
          <button className="modal-x" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {err && <div className="alert">{err}</div>}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 10 }}>
            <Field label="Project name" full>
              <input className="input" value={f.name} onChange={set("name")} disabled={!canAdmin} required />
            </Field>
            <Field label="Industry">
              <input className="input" value={f.industry} onChange={set("industry")} disabled={!canAdmin} placeholder="Electrical, Civil…" />
            </Field>
            <Field label="Awarded from / client">
              <input className="input" value={f.awarded_from} onChange={set("awarded_from")} disabled={!canAdmin} placeholder="Ministry of…, ACME Dev" />
            </Field>
            <Field label="Fields / scope">
              <input className="input" value={f.fields} onChange={set("fields")} disabled={!canAdmin} placeholder="HVAC, Plumbing, Fit-out" />
            </Field>
            <Field label="">
              <div className="row" style={{ gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <div className="lp-label" style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>Start</div>
                  <input className="input" type="date" value={f.start_date} onChange={set("start_date")} disabled={!canAdmin} />
                </div>
                <div style={{ flex: 1 }}>
                  <div className="lp-label" style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>End</div>
                  <input className="input" type="date" value={f.end_date} onChange={set("end_date")} disabled={!canAdmin} />
                </div>
              </div>
            </Field>
            <Field label="Description" full>
              <textarea className="input" rows={3} value={f.description} onChange={set("description")} disabled={!canAdmin} />
            </Field>
          </div>

          {canAdmin && (
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn btn-primary btn-sm" disabled={busy || !f.name} onClick={save}>
                {isNew ? "Create project" : "Save changes"}
              </button>
              {!isNew && (
                <button className="btn btn-sm btn-danger-ghost" disabled={busy} onClick={remove}>Delete</button>
              )}
              <button className="btn btn-sm btn-ghost" onClick={onClose}>Cancel</button>
            </div>
          )}

          {!isNew && (
            <>
              <div style={{ borderTop: "1px solid var(--border)", margin: "16px 0", paddingTop: 14 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>Pipeline status</div>
                <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                  <select
                    className="input" style={{ width: 160 }} value={status}
                    onChange={(e) => setStatus(e.target.value)} disabled={!canAdmin}
                  >
                    {STATUSES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                  </select>
                  {canAdmin && (
                    <>
                      <input className="input" style={{ flex: 1, minWidth: 140 }} placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
                      <button className="btn btn-sm btn-primary" disabled={busy} onClick={() => applyStatus(status)}>Update status</button>
                    </>
                  )}
                </div>
              </div>

              <div className="eyebrow" style={{ marginBottom: 4 }}>History</div>
              {events.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No history yet.</div>}
              <ul className="timeline">
                {events.map((e) => (
                  <li key={e.id}>
                    <span className="when">{new Date(e.created_at).toLocaleString()}</span>
                    <span>
                      <span className="badge" style={{ background: "var(--surface-3)", color: COLOR[e.to_status], border: "1px solid var(--border)" }}>
                        {e.from_status ? `${LABEL[e.from_status]} → ${LABEL[e.to_status]}` : LABEL[e.to_status]}
                      </span>
                      {e.note && <span className="muted"> · {e.note}</span>}
                      {e.username && <span className="muted" style={{ fontSize: 11 }}> — {e.username}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children, full }) {
  return (
    <div className="field" style={{ marginTop: 0, gridColumn: full ? "1 / -1" : "auto" }}>
      {label && <label>{label}</label>}
      {children}
    </div>
  );
}

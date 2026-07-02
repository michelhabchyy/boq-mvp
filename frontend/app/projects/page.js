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
const ORDER = ["lead", "bidding", "shortlisted", "awarded", "in_progress", "completed"];

const BLANK = {
  name: "", industry: "", fields: "", description: "", awarded_from: "", start_date: "", end_date: "",
  rfp_id: "", planned_value: "", contract_value: "", actual_cost: "", currency: "SAR",
};
const fmtDate = (d) => (d ? new Date(d).toLocaleDateString() : "");
const fmtWhen = (d) => (d ? new Date(d).toLocaleString() : "");
const money = (n, cur = "SAR") =>
  n == null || n === "" ? "—" : `${cur} ${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

function progress(status) {
  if (status === "lost") return { pct: 100, color: COLOR.lost };
  const i = ORDER.indexOf(status);
  return { pct: ((i + 1) / ORDER.length) * 100, color: COLOR[status] };
}

export default function ProjectsPage() {
  const { user, loading, canAdmin } = useAuth();
  const [projects, setProjects] = useState(null);
  const [activity, setActivity] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dragId, setDragId] = useState(null);
  const [overCol, setOverCol] = useState(null);
  const [modal, setModal] = useState(null);

  const canView = canAdmin || user?.role === "reviewer";

  const load = useCallback(() => {
    Promise.all([api.get("/projects?limit=1000"), api.get("/projects/activity").catch(() => [])])
      .then(([p, a]) => { setProjects(p); setActivity(a); })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (!loading && canView) load();
  }, [loading, canView, load]);

  async function move(id, status) {
    const p = projects?.find((x) => x.id === id);
    if (!p || p.status === status) return;
    setProjects((ps) => ps.map((x) => (x.id === id ? { ...x, status } : x)));
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

  const list = projects || [];
  const countIn = (keys) => list.filter((p) => keys.includes(p.status)).length;
  const kpis = [
    { k: "Total", v: list.length, c: "var(--text)" },
    { k: "In pipeline", v: countIn(["lead", "bidding", "shortlisted"]), c: COLOR.bidding },
    { k: "Awarded", v: countIn(["awarded", "in_progress", "completed"]), c: COLOR.awarded },
    { k: "Completed", v: countIn(["completed"]), c: COLOR.completed },
    { k: "Lost", v: countIn(["lost"]), c: COLOR.lost },
  ];

  const finSum = (key, arr = list) => arr.reduce((a, p) => a + (Number(p[key]) || 0), 0);
  const totalContract = finSum("contract_value");
  const totalActual = finSum("actual_cost");
  const grossMargin = totalContract - totalActual;
  const costed = list.filter((p) => p.actual_cost != null && p.actual_cost !== "");
  const plannedSum = finSum("planned_value", costed);
  const actualSum = finSum("actual_cost", costed);
  const hasFin = totalContract || totalActual || plannedSum;

  return (
    <main className="container">
      <div className="eyebrow">Business development</div>
      <div className="between">
        <div>
          <h1 className="page-title">Projects pipeline</h1>
          <p className="page-sub" style={{ margin: 0 }}>
            Every opportunity from lead to completion — change a project's stage right
            on its card, or open it to edit details and see its history.
          </p>
        </div>
        {canAdmin && <button className="btn btn-primary" onClick={() => setModal({ mode: "new" })}>+ New project</button>}
      </div>

      {error && <div className="alert" style={{ marginTop: 12 }}>{error}</div>}

      {/* KPIs */}
      <div className="statbar" style={{ marginTop: 14 }}>
        {kpis.map((s) => (
          <div className="stat" key={s.k}>
            <div className="k">{s.k}</div>
            <div className="v" style={{ color: s.c }}>
              {s.k !== "Total" && <span className="kpi-dot" style={{ background: s.c }} />}{s.v}
            </div>
          </div>
        ))}
      </div>

      {!projects && <div className="empty">Loading…</div>}

      {/* Full-view pipeline (all stages visible) */}
      {projects && (
        <div className="pipeline">
          {STATUSES.map((s) => {
            const cards = list.filter((p) => p.status === s.key);
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
                  {cards.map((p) => {
                    const pr = progress(p.status);
                    return (
                      <div
                        key={p.id}
                        className={`kan-card ${dragId === p.id ? "dragging" : ""}`}
                        draggable={canAdmin}
                        onDragStart={() => setDragId(p.id)}
                        onDragEnd={() => setDragId(null)}
                        onClick={() => setModal({ mode: "edit", id: p.id })}
                        title="Click to edit details & view history"
                      >
                        <div className="nm">{p.name}</div>
                        <div className="meta">
                          {p.industry && <span className="badge badge-amber">{p.industry}</span>}
                          {p.awarded_from && <span className="chip-i">🏛 {p.awarded_from}</span>}
                        </div>
                        {(p.start_date || p.end_date) && (
                          <div className="meta">🗓 {fmtDate(p.start_date) || "…"} – {fmtDate(p.end_date) || "…"}</div>
                        )}
                        <div className="kan-prog"><span style={{ width: `${pr.pct}%`, background: pr.color }} /></div>
                        {canAdmin && (
                          <div className="kan-foot" onClick={(e) => e.stopPropagation()}>
                            <select value={p.status} onChange={(e) => move(p.id, e.target.value)}>
                              {STATUSES.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
                            </select>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Financials summary */}
      {projects && hasFin ? (
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="panel-head">
            <h2>Financials</h2>
            <span className="tag">planned vs actual</span>
          </div>
          <div className="panel-body">
            <div className="statbar" style={{ margin: 0 }}>
              <div className="stat"><div className="k">Contract value awarded</div><div className="v">{money(totalContract)}</div></div>
              <div className="stat"><div className="k">Actual cost</div><div className="v">{money(totalActual)}</div></div>
              <div className="stat"><div className="k">Gross margin</div><div className="v" style={{ color: grossMargin >= 0 ? "var(--success)" : "var(--danger)" }}>{money(grossMargin)}</div></div>
            </div>
            {plannedSum > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                  Planned (from BoQ) vs actual — across projects with a recorded cost
                </div>
                <div style={{ display: "grid", gap: 8, maxWidth: 520 }}>
                  <BarRow label="Planned" val={plannedSum} pct={(plannedSum / Math.max(plannedSum, actualSum, 1)) * 100} color="var(--accent)" />
                  <BarRow label="Actual" val={actualSum} pct={(actualSum / Math.max(plannedSum, actualSum, 1)) * 100} color={actualSum > plannedSum ? "var(--danger)" : "var(--success)"} />
                </div>
                <div style={{ fontSize: 13, marginTop: 8 }}>
                  Variance:{" "}
                  <strong style={{ color: actualSum > plannedSum ? "var(--danger)" : "var(--success)" }}>
                    {actualSum > plannedSum ? "+" : ""}{money(actualSum - plannedSum)} {actualSum > plannedSum ? "(over budget)" : "(under budget)"}
                  </strong>
                </div>
              </div>
            )}
          </div>
        </section>
      ) : null}

      {/* Global activity log */}
      <section className="panel" style={{ marginTop: 22 }}>
        <div className="panel-head">
          <h2>Activity log</h2>
          <span className="tag">all pipeline updates</span>
        </div>
        <div className="panel-body">
          {activity.length === 0 ? (
            <div className="empty" style={{ padding: 10 }}>No updates yet.</div>
          ) : (
            <ul className="act">
              {activity.map((e) => (
                <li key={e.id}>
                  <span className="when">{fmtWhen(e.created_at)}</span>
                  <span style={{ flex: 1 }}>
                    <span className="pname">{e.project_name}</span>{" "}
                    <span className="badge" style={{ background: "var(--surface-3)", color: COLOR[e.to_status], border: "1px solid var(--border)" }}>
                      {e.from_status ? `${LABEL[e.from_status]} → ${LABEL[e.to_status]}` : LABEL[e.to_status]}
                    </span>
                    {e.note && <span className="muted"> · {e.note}</span>}
                  </span>
                  {e.username && <span className="who">{e.username}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {modal && (
        <ProjectModal
          mode={modal.mode} id={modal.id} canAdmin={canAdmin}
          onClose={() => setModal(null)} onSaved={() => { setModal(null); load(); }}
          busy={busy} setBusy={setBusy}
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
  const [rfps, setRfps] = useState([]);
  const [boqTotal, setBoqTotal] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const num = (v) => (v === "" || v == null ? null : Number(v));

  useEffect(() => {
    api.get("/rfps?limit=1000").then(setRfps).catch(() => {});
  }, []);

  useEffect(() => {
    if (isNew) return;
    api.get(`/projects/${id}`).then((d) => {
      const p = d.project;
      setF({
        name: p.name || "", industry: p.industry || "", fields: p.fields || "",
        description: p.description || "", awarded_from: p.awarded_from || "",
        start_date: p.start_date || "", end_date: p.end_date || "",
        rfp_id: p.rfp_id ?? "", planned_value: p.planned_value ?? "",
        contract_value: p.contract_value ?? "", actual_cost: p.actual_cost ?? "",
        currency: p.currency || "SAR",
      });
      setStatus(p.status);
      setEvents(d.events || []);
      setBoqTotal(d.boq_total);
    }).catch((e) => setErr(String(e.message || e)));
  }, [isNew, id]);

  const payload = () => ({
    name: f.name, industry: f.industry || null, fields: f.fields || null,
    description: f.description || null, awarded_from: f.awarded_from || null,
    start_date: f.start_date || null, end_date: f.end_date || null,
    rfp_id: f.rfp_id ? Number(f.rfp_id) : null,
    planned_value: num(f.planned_value), contract_value: num(f.contract_value),
    actual_cost: num(f.actual_cost), currency: f.currency || "SAR",
  });

  const cur = f.currency || "SAR";
  const planned = num(f.planned_value);
  const contract = num(f.contract_value);
  const actual = num(f.actual_cost);
  const variance = planned != null && actual != null ? actual - planned : null; // + = over budget
  const margin = contract != null && actual != null ? contract - actual : null;
  const marginPct = margin != null && contract ? (margin / contract) * 100 : null;

  async function run(fn) {
    setBusy(true); setErr(null);
    try { await fn(); } catch (e) { setErr(String(e.message || e)); setBusy(false); }
  }
  const save = () => run(async () => { isNew ? await api.post("/projects", payload()) : await api.patch(`/projects/${id}`, payload()); onSaved(); });
  const applyStatus = () => run(async () => { await api.post(`/projects/${id}/status`, { status, note: note || undefined }); onSaved(); });
  const remove = () => confirm(`Delete "${f.name}"?`) && run(async () => { await api.del(`/projects/${id}`); onSaved(); });

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
            <Field label="Timing">
              <div className="row" style={{ gap: 8 }}>
                <input className="input" type="date" value={f.start_date} onChange={set("start_date")} disabled={!canAdmin} title="Start" />
                <input className="input" type="date" value={f.end_date} onChange={set("end_date")} disabled={!canAdmin} title="End" />
              </div>
            </Field>
            <Field label="Description" full>
              <textarea className="input" rows={3} value={f.description} onChange={set("description")} disabled={!canAdmin} />
            </Field>
          </div>

          {/* Financials — planned (from RFP/BoQ) vs actual */}
          <div style={{ borderTop: "1px solid var(--border)", margin: "16px 0 0", paddingTop: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Financials — planned vs actual</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 10 }}>
              <Field label="Linked RFP (planned budget from its BoQ)" full>
                <select className="input" value={f.rfp_id} onChange={set("rfp_id")} disabled={!canAdmin}>
                  <option value="">— none —</option>
                  {rfps.map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}
                </select>
              </Field>
              {boqTotal != null && (
                <div style={{ gridColumn: "1 / -1", fontSize: 12.5 }} className="muted">
                  Planned from linked BoQ: <strong style={{ color: "var(--accent)" }}>{money(boqTotal, cur)}</strong>
                  {canAdmin && (
                    <button
                      type="button" className="btn btn-sm btn-ghost" style={{ marginLeft: 8 }}
                      onClick={() => setF((p) => ({ ...p, planned_value: Math.round(boqTotal) }))}
                    >
                      Use as planned
                    </button>
                  )}
                </div>
              )}
              <Field label={`Planned value (${cur})`}>
                <input className="input" type="number" value={f.planned_value} onChange={set("planned_value")} disabled={!canAdmin} />
              </Field>
              <Field label={`Contract value / awarded (${cur})`}>
                <input className="input" type="number" value={f.contract_value} onChange={set("contract_value")} disabled={!canAdmin} />
              </Field>
              <Field label={`Actual cost (${cur})`}>
                <input className="input" type="number" value={f.actual_cost} onChange={set("actual_cost")} disabled={!canAdmin} />
              </Field>
              <Field label="Currency">
                <input className="input" value={f.currency} onChange={set("currency")} disabled={!canAdmin} placeholder="SAR" />
              </Field>
            </div>
            {(variance != null || margin != null) && (
              <div className="row" style={{ gap: 16, marginTop: 10, flexWrap: "wrap", fontSize: 13 }}>
                {variance != null && (
                  <span>
                    Variance vs planned:{" "}
                    <strong style={{ color: variance > 0 ? "var(--danger)" : "var(--success)" }}>
                      {variance > 0 ? "+" : ""}{money(variance, cur)} {variance > 0 ? "(over)" : "(under)"}
                    </strong>
                  </span>
                )}
                {margin != null && (
                  <span>
                    Margin:{" "}
                    <strong style={{ color: margin >= 0 ? "var(--success)" : "var(--danger)" }}>
                      {money(margin, cur)}{marginPct != null ? ` (${marginPct.toFixed(1)}%)` : ""}
                    </strong>
                  </span>
                )}
              </div>
            )}
          </div>

          {canAdmin && (
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn btn-primary btn-sm" disabled={busy || !f.name} onClick={save}>
                {isNew ? "Create project" : "Save changes"}
              </button>
              {!isNew && <button className="btn btn-sm btn-danger-ghost" disabled={busy} onClick={remove}>Delete</button>}
              <button className="btn btn-sm btn-ghost" onClick={onClose}>Cancel</button>
            </div>
          )}

          {!isNew && (
            <>
              <div style={{ borderTop: "1px solid var(--border)", margin: "16px 0", paddingTop: 14 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>Change stage</div>
                <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                  <select className="input" style={{ width: 160 }} value={status} onChange={(e) => setStatus(e.target.value)} disabled={!canAdmin}>
                    {STATUSES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                  </select>
                  {canAdmin && (
                    <>
                      <input className="input" style={{ flex: 1, minWidth: 140 }} placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
                      <button className="btn btn-sm btn-primary" disabled={busy} onClick={applyStatus}>Update stage</button>
                    </>
                  )}
                </div>
              </div>
              <div className="eyebrow" style={{ marginBottom: 4 }}>History</div>
              {events.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No history yet.</div>}
              <ul className="timeline">
                {events.map((e) => (
                  <li key={e.id}>
                    <span className="when">{fmtWhen(e.created_at)}</span>
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

function BarRow({ label, val, pct, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 13 }}>
      <span style={{ width: 66, color: "var(--text-muted)" }}>{label}</span>
      <span style={{ flex: 1, height: 10, background: "var(--surface-3)", borderRadius: 6, overflow: "hidden" }}>
        <span style={{ display: "block", height: "100%", width: `${pct}%`, background: color, borderRadius: 6 }} />
      </span>
      <span style={{ width: 120, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{money(val)}</span>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";
import { STATUSES, LABEL, COLOR, money, fmtWhen } from "./shared";

const BLANK = {
  name: "", industry: "", fields: "", description: "", awarded_from: "", start_date: "", end_date: "",
  rfp_id: "", planned_value: "", contract_value: "", actual_cost: "", currency: "SAR",
};
const fmtSize = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.round((n || 0) / 1024) + " KB");

export default function ProjectDetail({ projectId }) {
  const router = useRouter();
  const { user, loading, canAdmin } = useAuth();
  const isNew = !projectId;
  const canView = canAdmin || user?.role === "reviewer";

  const [f, setF] = useState(BLANK);
  const [status, setStatus] = useState("lead");
  const [events, setEvents] = useState([]);
  const [boqTotal, setBoqTotal] = useState(null);
  const [caps, setCaps] = useState([]);
  const [rfps, setRfps] = useState([]);
  const [files, setFiles] = useState([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState(null);

  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const num = (v) => (v === "" || v == null ? null : Number(v));

  const loadDetail = useCallback(() => {
    api.get(`/projects/${projectId}`).then((d) => {
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
  }, [projectId]);
  const loadFiles = useCallback(() => {
    api.get(`/projects/${projectId}/files`).then(setFiles).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    api.get("/capabilities").then(setCaps).catch(() => {});
    api.get("/rfps?limit=1000").then(setRfps).catch(() => {});
  }, []);
  useEffect(() => { if (!isNew) { loadDetail(); loadFiles(); } }, [isNew, loadDetail, loadFiles]);

  if (loading) return <main className="container" />;
  if (user && !canView)
    return <main className="container narrow"><div className="panel"><div className="empty">Company team only.</div></div></main>;

  const payload = () => ({
    name: f.name, industry: f.industry || null, fields: f.fields || null,
    description: f.description || null, awarded_from: f.awarded_from || null,
    start_date: f.start_date || null, end_date: f.end_date || null,
    rfp_id: f.rfp_id ? Number(f.rfp_id) : null,
    planned_value: num(f.planned_value), contract_value: num(f.contract_value),
    actual_cost: num(f.actual_cost), currency: f.currency || "SAR",
  });

  async function run(key, fn) {
    setBusy(key); setErr(null);
    try { return await fn(); } catch (e) { setErr(String(e.message || e)); } finally { setBusy(null); }
  }
  const save = () => run("save", async () => {
    if (isNew) { const r = await api.post("/projects", payload()); router.push(`/projects/${r.id}`); }
    else { await api.patch(`/projects/${projectId}`, payload()); loadDetail(); }
  });
  const applyStatus = () => run("status", async () => { await api.post(`/projects/${projectId}/status`, { status, note: note || undefined }); setNote(""); loadDetail(); });
  const remove = () => confirm(`Delete "${f.name}"? This removes the project, its files and history.`) &&
    run("del", async () => { await api.del(`/projects/${projectId}`); router.push("/projects"); });
  const upload = (kind, file) => file && run(`up-${kind}`, async () => { await api.upload(`/projects/${projectId}/files?kind=${kind}`, file); loadFiles(); });
  const delFile = (fid) => run(`df-${fid}`, async () => { await api.del(`/projects/files/${fid}`); loadFiles(); });
  const runFile = (fid) => run(`rf-${fid}`, async () => { await api.post(`/projects/files/${fid}/run`); loadFiles(); });

  const cur = f.currency || "SAR";
  const planned = num(f.planned_value), contract = num(f.contract_value), actual = num(f.actual_cost);
  const variance = planned != null && actual != null ? actual - planned : null;
  const margin = contract != null && actual != null ? contract - actual : null;
  const marginPct = margin != null && contract ? (margin / contract) * 100 : null;

  const capField = caps.find((c) => c.name === f.industry);
  const selServices = (f.fields || "").split(",").map((s) => s.trim()).filter(Boolean);
  const onFieldChange = (e) => setF((p) => ({ ...p, industry: e.target.value, fields: "" }));
  const toggleSvc = (name) => setF((p) => {
    const s2 = new Set((p.fields || "").split(",").map((x) => x.trim()).filter(Boolean));
    s2.has(name) ? s2.delete(name) : s2.add(name);
    return { ...p, fields: [...s2].join(", ") };
  });

  const rfpFiles = files.filter((x) => x.kind === "rfp");
  const tmplFiles = files.filter((x) => x.kind === "boq_template");

  return (
    <main className="container">
      <Link href="/projects" className="crumb">← Projects</Link>
      <div className="between" style={{ marginTop: 4 }}>
        <div>
          <div className="eyebrow">{isNew ? "New project" : "Project"}</div>
          <h1 className="page-title" style={{ margin: 0 }}>{isNew ? "New project" : f.name || "Project"}</h1>
        </div>
        {!isNew && (
          <span className="badge" style={{ background: "var(--surface-3)", color: COLOR[status], border: "1px solid var(--border)", fontSize: 12 }}>
            {LABEL[status]}
          </span>
        )}
      </div>

      {err && <div className="alert" style={{ marginTop: 12 }}>{err}</div>}

      {/* Details */}
      <section className="panel" style={{ marginTop: 14 }}>
        <div className="panel-head"><h2>Details</h2></div>
        <div className="panel-body">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 12 }}>
            <Field label="Project name" full>
              <input className="input" value={f.name} onChange={set("name")} disabled={!canAdmin} required />
            </Field>
            <Field label="Field">
              {caps.length ? (
                <select className="input" value={f.industry} onChange={onFieldChange} disabled={!canAdmin}>
                  <option value="">— select field —</option>
                  {caps.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                  {f.industry && !capField && <option value={f.industry}>{f.industry}</option>}
                </select>
              ) : (
                <input className="input" value={f.industry} onChange={set("industry")} disabled={!canAdmin} placeholder="Electrical…" />
              )}
            </Field>
            <Field label="Awarded from / client">
              <input className="input" value={f.awarded_from} onChange={set("awarded_from")} disabled={!canAdmin} />
            </Field>
            <Field label="Services / scope" full>
              {caps.length === 0 ? (
                <input className="input" value={f.fields} onChange={set("fields")} disabled={!canAdmin} placeholder="HVAC, Plumbing" />
              ) : !capField ? (
                <span className="muted" style={{ fontSize: 12 }}>Select a field to choose its services.</span>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {capField.services.length === 0 && <span className="muted" style={{ fontSize: 12 }}>No services defined for this field.</span>}
                  {capField.services.map((sv) => {
                    const on = selServices.includes(sv.name);
                    return (
                      <label key={sv.id} className="badge" style={{ cursor: canAdmin ? "pointer" : "default", display: "inline-flex", alignItems: "center", gap: 6, background: on ? "var(--accent-soft)" : "var(--surface-3)", color: on ? "var(--accent-text)" : "var(--text-muted)", border: "1px solid var(--border)" }}>
                        <input type="checkbox" checked={on} disabled={!canAdmin} onChange={() => toggleSvc(sv.name)} style={{ margin: 0 }} /> {sv.name}
                      </label>
                    );
                  })}
                </div>
              )}
            </Field>
            <Field label="Timing (start / end)" full>
              <div className="row" style={{ gap: 8 }}>
                <input className="input" type="date" value={f.start_date} onChange={set("start_date")} disabled={!canAdmin} />
                <input className="input" type="date" value={f.end_date} onChange={set("end_date")} disabled={!canAdmin} />
              </div>
            </Field>
            <Field label="Description" full>
              <textarea className="input" rows={4} value={f.description} onChange={set("description")} disabled={!canAdmin} />
            </Field>
          </div>
          {canAdmin && (
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn btn-primary btn-sm" disabled={busy === "save" || !f.name} onClick={save}>
                {isNew ? "Create project" : "Save changes"}
              </button>
              {!isNew && <button className="btn btn-sm btn-danger-ghost" disabled={busy === "del"} onClick={remove}>Delete project</button>}
              <Link className="btn btn-sm btn-ghost" href="/projects">Cancel</Link>
            </div>
          )}
        </div>
      </section>

      {/* Financials */}
      <section className="panel">
        <div className="panel-head"><h2>Financials — planned vs actual</h2></div>
        <div className="panel-body">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 12 }}>
            <Field label="Linked RFP (planned budget from its BoQ)" full>
              <select className="input" value={f.rfp_id} onChange={set("rfp_id")} disabled={!canAdmin}>
                <option value="">— none —</option>
                {rfps.map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}
              </select>
            </Field>
            {boqTotal != null && (
              <div style={{ gridColumn: "1 / -1", fontSize: 12.5 }} className="muted">
                Planned from linked BoQ: <strong style={{ color: "var(--accent)" }}>{money(boqTotal, cur)}</strong>
                {canAdmin && <button type="button" className="btn btn-sm btn-ghost" style={{ marginLeft: 8 }} onClick={() => setF((p) => ({ ...p, planned_value: Math.round(boqTotal) }))}>Use as planned</button>}
              </div>
            )}
            <Field label={`Planned value (${cur})`}><input className="input" type="number" value={f.planned_value} onChange={set("planned_value")} disabled={!canAdmin} /></Field>
            <Field label={`Contract value / awarded (${cur})`}><input className="input" type="number" value={f.contract_value} onChange={set("contract_value")} disabled={!canAdmin} /></Field>
            <Field label={`Actual cost (${cur})`}><input className="input" type="number" value={f.actual_cost} onChange={set("actual_cost")} disabled={!canAdmin} /></Field>
            <Field label="Currency"><input className="input" value={f.currency} onChange={set("currency")} disabled={!canAdmin} /></Field>
          </div>
          {(variance != null || margin != null) && (
            <div className="row" style={{ gap: 16, marginTop: 10, flexWrap: "wrap", fontSize: 13 }}>
              {variance != null && <span>Variance vs planned: <strong style={{ color: variance > 0 ? "var(--danger)" : "var(--success)" }}>{variance > 0 ? "+" : ""}{money(variance, cur)} {variance > 0 ? "(over)" : "(under)"}</strong></span>}
              {margin != null && <span>Margin: <strong style={{ color: margin >= 0 ? "var(--success)" : "var(--danger)" }}>{money(margin, cur)}{marginPct != null ? ` (${marginPct.toFixed(1)}%)` : ""}</strong></span>}
            </div>
          )}
          {canAdmin && !isNew && (
            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn btn-primary btn-sm" disabled={busy === "save"} onClick={save}>Save financials</button>
            </div>
          )}
        </div>
      </section>

      {isNew ? (
        <p className="muted" style={{ fontSize: 13 }}>Create the project to attach RFP files, BoQ templates and track its stage history.</p>
      ) : (
        <>
          {/* Files */}
          <section className="panel">
            <div className="panel-head"><h2>Files — RFPs &amp; BoQ templates</h2></div>
            <div className="panel-body">
              <FileGroup
                title="RFP documents" kind="rfp" files={rfpFiles} canAdmin={canAdmin} busy={busy}
                onUpload={upload} onDelete={delFile} onRun={runFile}
              />
              <div style={{ height: 16 }} />
              <FileGroup
                title="BoQ templates" kind="boq_template" files={tmplFiles} canAdmin={canAdmin} busy={busy}
                onUpload={upload} onDelete={delFile}
              />
              <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
                RFP files can be <strong>run</strong> from here or from the RFP page — running one
                analyzes it (using a BoQ template as reference if attached) and adds it to your RFPs.
              </p>
            </div>
          </section>

          {/* Status + history */}
          <section className="panel">
            <div className="panel-head"><h2>Pipeline &amp; history</h2></div>
            <div className="panel-body">
              <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                <select className="input" style={{ width: 170 }} value={status} onChange={(e) => setStatus(e.target.value)} disabled={!canAdmin}>
                  {STATUSES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                </select>
                {canAdmin && (
                  <>
                    <input className="input" style={{ flex: 1, minWidth: 160 }} placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
                    <button className="btn btn-sm btn-primary" disabled={busy === "status"} onClick={applyStatus}>Update stage</button>
                  </>
                )}
              </div>
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
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function FileGroup({ title, kind, files, canAdmin, busy, onUpload, onDelete, onRun }) {
  return (
    <div>
      <div className="between" style={{ marginBottom: 8 }}>
        <strong style={{ fontSize: 13 }}>{title}</strong>
        {canAdmin && (
          <label className="btn btn-sm" style={{ cursor: busy === `up-${kind}` ? "wait" : "pointer" }}>
            {busy === `up-${kind}` ? "Uploading…" : "⬆ Add file"}
            <input type="file" hidden disabled={busy === `up-${kind}`}
              onChange={(e) => { onUpload(kind, e.target.files?.[0]); e.target.value = ""; }} />
          </label>
        )}
      </div>
      {files.length === 0 ? (
        <div className="muted" style={{ fontSize: 12 }}>No files.</div>
      ) : (
        <table className="table">
          <tbody>
            {files.map((x) => (
              <tr key={x.id}>
                <td><strong>{x.filename}</strong> <span className="muted" style={{ fontSize: 11 }}>{fmtSize(x.size)}</span></td>
                <td className="cell-actions">
                  {kind === "rfp" && (
                    x.rfp_document_id ? (
                      <Link className="btn btn-sm" href={`/review/${x.rfp_document_id}`}>Open RFP →</Link>
                    ) : canAdmin ? (
                      <button className="btn btn-sm btn-primary" disabled={busy === `rf-${x.id}`} onClick={() => onRun(x.id)}>
                        {busy === `rf-${x.id}` ? "Running…" : "▶ Run"}
                      </button>
                    ) : null
                  )}
                  <button className="btn btn-sm" onClick={() => api.download(`/projects/files/${x.id}/download`, x.filename)}>⬇</button>
                  {canAdmin && <button className="btn btn-sm btn-danger-ghost" disabled={busy === `df-${x.id}`} onClick={() => onDelete(x.id)}>Delete</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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

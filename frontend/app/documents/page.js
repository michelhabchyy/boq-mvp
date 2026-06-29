"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

const fmtSize = (n) => {
  n = Number(n) || 0;
  if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
  if (n >= 1024) return Math.round(n / 1024) + " KB";
  return n + " B";
};
const fmtDate = (s) => (s ? new Date(s).toLocaleString() : "");

export default function DocumentsPage() {
  const { user, loading, canAdmin, acting } = useAuth();
  const role = user?.role;
  const ownerIdle = role === "owner" && !acting;
  const companyContext = canAdmin || role === "reviewer"; // admin, owner-acting, reviewer
  const isSub = role === "subcontractor";

  if (loading) return <main className="container" />;
  if (!user) return <main className="container" />;

  return (
    <main className="container">
      <div className="eyebrow">Official documents</div>
      <h1 className="page-title">Documents</h1>
      <p className="page-sub">
        Signed official documents shared along your relationships. Recipients can
        review and download; only the sender can remove a file.
      </p>

      {ownerIdle && <OwnerDocs />}
      {companyContext && <CompanyDocs canAdmin={canAdmin} />}
      {isSub && <SubDocs />}
    </main>
  );
}

/* ----------------------------- Owner → company ---------------------------- */
function OwnerDocs() {
  const [companies, setCompanies] = useState([]);
  const [cid, setCid] = useState("");
  const [docs, setDocs] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    api.get("/companies").then(setCompanies).catch((e) => setError(String(e.message || e)));
  }, []);

  const loadDocs = useCallback((companyId) => {
    if (!companyId) return setDocs(null);
    api.get(`/documents/company/${companyId}`).then(setDocs).catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => loadDocs(cid), [cid, loadDocs]);

  async function act(key, fn) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      loadDocs(cid);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      {error && <div className="alert">{error}</div>}
      <section className="panel">
        <div className="panel-head">
          <h2>Share with a company</h2>
          <select className="input" style={{ width: 240 }} value={cid} onChange={(e) => setCid(e.target.value)}>
            <option value="">Select a company…</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        {!cid && <div className="empty">Choose a company to view and upload its documents.</div>}
        {cid && (
          <div style={{ padding: 16 }}>
            <UploadBox
              busy={busy === "up"}
              onUpload={(fd) => act("up", () => api.uploadForm(`/documents/company/${cid}`, fd))}
            />
            <DocList
              docs={docs}
              canDelete
              busy={busy}
              onAct={act}
            />
          </div>
        )}
      </section>
    </>
  );
}

/* ----------------- Company: inbox + send to subcontractors ---------------- */
function CompanyDocs({ canAdmin }) {
  const [inbox, setInbox] = useState(null);
  const [subs, setSubs] = useState([]);
  const [subId, setSubId] = useState("");
  const [subDocs, setSubDocs] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  const loadInbox = useCallback(() => {
    api.get("/documents/inbox").then(setInbox).catch((e) => setError(String(e.message || e)));
  }, []);
  useEffect(() => {
    loadInbox();
    api.get("/subcontractors").then(setSubs).catch(() => {});
  }, [loadInbox]);

  const loadSubDocs = useCallback((sid) => {
    if (!sid) return setSubDocs(null);
    api.get(`/documents/subcontractor/${sid}`).then(setSubDocs).catch((e) => setError(String(e.message || e)));
  }, []);
  useEffect(() => loadSubDocs(subId), [subId, loadSubDocs]);

  async function act(key, fn, reload) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      {error && <div className="alert">{error}</div>}

      <section className="panel">
        <div className="panel-head">
          <h2>From the platform</h2>
          <span className="tag">{inbox ? `${inbox.length} document(s)` : ""}</span>
        </div>
        <div style={{ padding: 16 }}>
          <DocList docs={inbox} busy={busy} onAct={(k, fn) => act(k, fn, loadInbox)} />
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Share with a subcontractor</h2>
          <select className="input" style={{ width: 240 }} value={subId} onChange={(e) => setSubId(e.target.value)}>
            <option value="">Select a subcontractor…</option>
            {subs.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        {!subId && <div className="empty">Choose a subcontractor to view and upload their documents.</div>}
        {subId && (
          <div style={{ padding: 16 }}>
            {canAdmin && (
              <UploadBox
                busy={busy === "up"}
                onUpload={(fd) => act("up", () => api.uploadForm(`/documents/subcontractor/${subId}`, fd), () => loadSubDocs(subId))}
              />
            )}
            <DocList
              docs={subDocs}
              canDelete={canAdmin}
              busy={busy}
              onAct={(k, fn) => act(k, fn, () => loadSubDocs(subId))}
            />
          </div>
        )}
      </section>
    </>
  );
}

/* -------------------------- Subcontractor inbox --------------------------- */
function SubDocs() {
  const [docs, setDocs] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(() => {
    api.get("/documents/my").then(setDocs).catch((e) => setError(String(e.message || e)));
  }, []);
  useEffect(() => load(), [load]);

  async function act(key, fn) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      {error && <div className="alert">{error}</div>}
      <section className="panel">
        <div className="panel-head">
          <h2>Documents from your contractor</h2>
          <span className="tag">{docs ? `${docs.length} document(s)` : ""}</span>
        </div>
        <div style={{ padding: 16 }}>
          <DocList docs={docs} busy={busy} onAct={act} />
        </div>
      </section>
    </>
  );
}

/* ------------------------------ shared bits ------------------------------- */
function UploadBox({ onUpload, busy }) {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");

  function submit(e) {
    e.preventDefault();
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    if (title.trim()) fd.append("title", title.trim());
    onUpload(fd);
    setFile(null);
    setTitle("");
    e.target.reset();
  }

  return (
    <form
      onSubmit={submit}
      style={{
        display: "flex",
        gap: 10,
        alignItems: "center",
        flexWrap: "wrap",
        padding: 14,
        marginBottom: 14,
        border: "1px dashed var(--border-strong)",
        borderRadius: "var(--radius-sm)",
        background: "var(--surface-2)",
      }}
    >
      <input
        type="text"
        className="input"
        style={{ width: 220 }}
        placeholder="Title / description (optional)"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} required />
      <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !file}>
        {busy ? "Uploading…" : "⬆ Upload document"}
      </button>
      <span className="muted" style={{ fontSize: 11 }}>Max 25 MB · PDF, images, Office files</span>
    </form>
  );
}

function DocList({ docs, canDelete = false, busy, onAct }) {
  if (!docs) return <div className="empty">Loading…</div>;
  if (docs.length === 0) return <div className="empty">No documents yet.</div>;
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Document</th>
          <th className="num">Size</th>
          <th>Shared by</th>
          <th>Date</th>
          <th style={{ textAlign: "right" }}>Actions</th>
        </tr>
      </thead>
      <tbody>
        {docs.map((d) => (
          <tr key={d.id}>
            <td>
              <strong>{d.title || d.filename}</strong>
              {d.title && <div className="muted" style={{ fontSize: 12 }}>{d.filename}</div>}
            </td>
            <td className="num">{fmtSize(d.size)}</td>
            <td className="muted" style={{ fontSize: 12 }}>{d.uploaded_by_name || "—"}</td>
            <td className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>{fmtDate(d.created_at)}</td>
            <td className="cell-actions">
              <button
                className="btn btn-sm"
                disabled={busy === `view-${d.id}`}
                onClick={() => onAct(`view-${d.id}`, () => api.openInNewTab(`/documents/${d.id}/download?inline=true`))}
              >
                Review
              </button>
              <button
                className="btn btn-sm btn-primary"
                disabled={busy === `dl-${d.id}`}
                onClick={() => onAct(`dl-${d.id}`, () => api.download(`/documents/${d.id}/download`, d.filename))}
              >
                ⬇ Download
              </button>
              {canDelete && (
                <button
                  className="btn btn-sm btn-danger-ghost"
                  disabled={busy === `del-${d.id}`}
                  onClick={() =>
                    confirm(`Delete "${d.title || d.filename}"?`) &&
                    onAct(`del-${d.id}`, () => api.del(`/documents/${d.id}`))
                  }
                >
                  Delete
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

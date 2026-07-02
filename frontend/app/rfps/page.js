"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";

export default function RfpsPage() {
  const [rfps, setRfps] = useState(null);
  const [runnable, setRunnable] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [aiAnalyze, setAiAnalyze] = useState(true);
  const [rfpFile, setRfpFile] = useState(null);
  const [sampleFile, setSampleFile] = useState(null);
  const [description, setDescription] = useState("");
  const [formKey, setFormKey] = useState(0);

  const load = useCallback(
    () =>
      Promise.all([
        api.get("/rfps"),
        api.get("/projects/rfp-files").catch(() => []),
      ])
        .then(([r, f]) => { setRfps(r); setRunnable(f); })
        .catch((e) => setError(String(e.message || e))),
    []
  );

  useEffect(() => {
    load();
  }, [load]);

  // While any RFP is still being analyzed in the background, poll for updates.
  useEffect(() => {
    if (rfps && rfps.some((r) => r.status === "analyzing")) {
      const t = setTimeout(load, 4000);
      return () => clearTimeout(t);
    }
  }, [rfps, load]);

  async function doUpload() {
    if (!rfpFile) return;
    setBusy("upload");
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", rfpFile);
      if (description.trim()) fd.append("description", description.trim());
      if (aiAnalyze && sampleFile) fd.append("sample", sampleFile);
      await api.uploadForm(`/rfps/upload?analyze=${aiAnalyze}`, fd);
      setRfpFile(null);
      setSampleFile(null);
      setDescription("");
      setFormKey((k) => k + 1); // remount file inputs to clear them
      await load();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(null);
    }
  }

  async function runFromProject(fileId) {
    setBusy(`run-${fileId}`);
    setError(null);
    try {
      await api.post(`/projects/files/${fileId}/run`);
      await load();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(null);
    }
  }

  async function runMatching(id) {
    setBusy(`match-${id}`);
    setError(null);
    try {
      await api.post(`/matching/run/${id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="container narrow">
      <div className="eyebrow">Bill of Quantities · AR / EN</div>
      <h1 className="page-title">RFP Workspace</h1>
      <p className="page-sub">
        Upload a scope of work, run the matching engine, then review and export a
        bilingual BoQ.
      </p>

      {error && <div className="alert">{error}</div>}

      <section className="panel">
        <div className="panel-head">
          <h2>Upload RFP</h2>
          <span className="tag">.xlsx · .docx · .pdf</span>
        </div>
        <div className="panel-body">
          <div className="field" style={{ marginTop: 0 }}>
            <label>RFP file</label>
            <input
              key={`rfp-${formKey}`}
              type="file"
              accept=".xlsx,.docx,.pdf"
              onChange={(e) => setRfpFile(e.target.files?.[0] || null)}
              disabled={busy === "upload"}
            />
          </div>

          <label className="row" style={{ marginTop: 12, gap: 6, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={aiAnalyze}
              onChange={(e) => setAiAnalyze(e.target.checked)}
            />
            <span style={{ fontSize: 13 }}>
              <strong>AI analysis</strong> — reads the whole document (multi-sheet
              Excel, Word, or PDF) and extracts sections + items. Required for PDF;
              uncheck only for a clean single-sheet BoQ table.
            </span>
          </label>

          {aiAnalyze && (
            <>
              <div className="field">
                <label>Your prompt / instructions for the AI (optional)</label>
                <textarea
                  className="input"
                  rows={4}
                  placeholder={
                    "Describe the RFP and tell the agent how to analyze and distribute it. e.g.:\n" +
                    "• MEP tender for a hospital — group items into scopes by discipline (HVAC, Electrical, Plumbing).\n" +
                    "• Quantities are in the 'Qty' column; ignore the preliminaries/terms.\n" +
                    "• Keep item names short; split civil vs finishing into separate scopes."
                  }
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
                <div className="tag" style={{ marginTop: 4 }}>
                  Combined with the built-in prompt to steer the section/item
                  distribution and level of detail.
                </div>
              </div>

              <div className="field">
                <label>Reference BoQ template / sample (optional)</label>
                <input
                  key={`sample-${formKey}`}
                  type="file"
                  accept=".xlsx,.docx,.pdf"
                  onChange={(e) => setSampleFile(e.target.files?.[0] || null)}
                />
                <div className="tag" style={{ marginTop: 4 }}>
                  If you have a sample BoQ, the AI mirrors its structure & columns.
                </div>
              </div>
            </>
          )}

          <div className="row" style={{ marginTop: 14 }}>
            <button
              className="btn btn-primary"
              onClick={doUpload}
              disabled={!rfpFile || busy === "upload"}
            >
              {busy === "upload"
                ? aiAnalyze
                  ? "Uploading…"
                  : "Processing…"
                : aiAnalyze
                ? "Upload & analyze"
                : "Upload"}
            </button>
            {rfpFile && <span className="muted" style={{ fontSize: 13 }}>{rfpFile.name}</span>}
          </div>
        </div>
      </section>

      {runnable.length > 0 && (
        <section className="panel">
          <div className="panel-head">
            <h2>From your projects</h2>
            <span className="tag">choose one to run</span>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>RFP file</th>
                <th>Project</th>
                <th style={{ textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {runnable.map((f) => (
                <tr key={f.file_id}>
                  <td><strong>{f.filename}</strong></td>
                  <td>
                    <Link href={`/projects/${f.project_id}`} className="pname">{f.project_name}</Link>
                  </td>
                  <td className="cell-actions">
                    {f.rfp_document_id ? (
                      <Link className="btn btn-sm" href={`/review/${f.rfp_document_id}`}>Open →</Link>
                    ) : (
                      <button
                        className="btn btn-sm btn-primary"
                        disabled={busy === `run-${f.file_id}`}
                        onClick={() => runFromProject(f.file_id)}
                      >
                        {busy === `run-${f.file_id}` ? "Running…" : "▶ Run"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>RFPs</h2>
          <span className="tag">{rfps ? `${rfps.length} total` : ""}</span>
        </div>
        {!rfps && !error && <div className="empty">Loading…</div>}
        {rfps && rfps.length === 0 && (
          <div className="empty">No RFPs yet — upload one above to get started.</div>
        )}
        {rfps && rfps.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>RFP</th>
                <th>Project</th>
                <th>Type</th>
                <th>Status</th>
                <th className="num">Lines</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rfps.map((r) => {
                const ready = r.status === "ready";
                return (
                  <tr key={r.id}>
                    <td>
                      <span className="muted nums">#{r.id}</span>{" "}
                      <strong>{r.filename}</strong>
                    </td>
                    <td>
                      {r.project_name ? (
                        <Link href={`/projects/${r.project_id}`} className="pname">{r.project_name}</Link>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      <span className="badge badge-gray">{r.source_type}</span>
                    </td>
                    <td>
                      {r.status === "analyzing" && (
                        <span className="badge badge-amber">analyzing…</span>
                      )}
                      {r.status === "ready" && (
                        <span className="badge badge-green">ready</span>
                      )}
                      {r.status === "failed" && (
                        <div>
                          <span className="badge badge-red">failed</span>
                          {r.error && (
                            <div style={{ fontSize: 11, color: "var(--danger)", marginTop: 3, maxWidth: 320 }}>
                              {r.error}
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="num">{r.line_count}</td>
                    <td className="cell-actions">
                      <button
                        className="btn btn-sm"
                        onClick={() => runMatching(r.id)}
                        disabled={!ready || busy === `match-${r.id}`}
                        title={ready ? "" : "Wait for analysis to finish"}
                      >
                        {busy === `match-${r.id}` ? "Matching…" : "Run matching"}
                      </button>
                      {ready ? (
                        <Link className="btn btn-sm btn-primary" href={`/review/${r.id}`}>
                          Review →
                        </Link>
                      ) : (
                        <button className="btn btn-sm btn-primary" disabled>
                          Review →
                        </button>
                      )}
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

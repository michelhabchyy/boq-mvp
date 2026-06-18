"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";

export default function Home() {
  const [rfps, setRfps] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [aiAnalyze, setAiAnalyze] = useState(true);

  const load = () =>
    api
      .get("/rfps")
      .then(setRfps)
      .catch((e) => setError(String(e)));

  useEffect(() => {
    load();
  }, []);

  async function onUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    setError(null);
    try {
      await api.upload(`/rfps/upload?analyze=${aiAnalyze}`, file);
      await load();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(null);
      e.target.value = "";
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
          <span className="tag">.xlsx · .docx</span>
        </div>
        <div className="panel-body">
          <div className="row">
            <input
              type="file"
              accept=".xlsx,.docx"
              onChange={onUpload}
              disabled={busy === "upload"}
            />
            {busy === "upload" && <span className="muted">{aiAnalyze ? "Analyzing…" : "Uploading…"}</span>}
          </div>
          <label className="row" style={{ marginTop: 10, gap: 6, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={aiAnalyze}
              onChange={(e) => setAiAnalyze(e.target.checked)}
            />
            <span style={{ fontSize: 13 }}>
              <strong>AI analysis</strong> — read the whole document and extract
              sections + items (for narrative RFPs). Uncheck for a clean BoQ table.
            </span>
          </label>
        </div>
      </section>

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
                <th>Type</th>
                <th className="num">Lines</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rfps.map((r) => (
                <tr key={r.id}>
                  <td>
                    <span className="muted nums">#{r.id}</span>{" "}
                    <strong>{r.filename}</strong>
                  </td>
                  <td>
                    <span className="badge badge-gray">{r.source_type}</span>
                  </td>
                  <td className="num">{r.line_count}</td>
                  <td className="cell-actions">
                    <button
                      className="btn btn-sm"
                      onClick={() => runMatching(r.id)}
                      disabled={busy === `match-${r.id}`}
                    >
                      {busy === `match-${r.id}` ? "Matching…" : "Run matching"}
                    </button>
                    <Link className="btn btn-sm btn-primary" href={`/review/${r.id}`}>
                      Review →
                    </Link>
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

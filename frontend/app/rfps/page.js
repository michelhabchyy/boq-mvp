"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";

export default function RfpsPage() {
  const [rfps, setRfps] = useState(null);
  const [runnable, setRunnable] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

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

  const pending = runnable.filter((f) => !f.rfp_document_id);

  return (
    <main className="container">
      <div className="eyebrow">Bill of Quantities · AR / EN</div>
      <div className="between">
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>RFP Workspace</h1>
          <p className="page-sub" style={{ margin: "6px 0 0" }}>
            Run an RFP attached to one of your projects, then review and export a
            bilingual BoQ.
          </p>
        </div>
        <Link className="btn btn-primary" href="/projects">Manage projects →</Link>
      </div>

      {error && <div className="alert" style={{ marginTop: 12 }}>{error}</div>}

      <section className="panel" style={{ marginTop: 14 }}>
        <div className="panel-head">
          <h2>From your projects</h2>
          <span className="tag">{pending.length ? `${pending.length} ready to run` : "attach RFPs in Projects"}</span>
        </div>
        {runnable.length === 0 ? (
          <div className="empty">
            No RFP files yet. Open a project and add an RFP under{" "}
            <strong>Files — RFPs &amp; BoQ templates</strong>, then run it here or from the project.
            <div style={{ marginTop: 12 }}>
              <Link className="btn btn-sm btn-primary" href="/projects">Go to Projects</Link>
            </div>
          </div>
        ) : (
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
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>RFPs</h2>
          <span className="tag">{rfps ? `${rfps.length} total` : ""}</span>
        </div>
        {!rfps && !error && <div className="empty">Loading…</div>}
        {rfps && rfps.length === 0 && (
          <div className="empty">No RFPs yet — attach one to a project and run it above.</div>
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
                            <div style={{ fontSize: 11, color: "var(--danger)", marginTop: 3, maxWidth: 320, whiteSpace: "normal" }}>
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

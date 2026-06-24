"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, money } from "../../lib/api";
import { useAuth } from "../AppChrome";

const STATUS_BADGE = { ready: "badge-green", analyzing: "badge-amber", failed: "badge-red" };

export default function CompanyOverviewPage() {
  const { user, loading, canAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [openSub, setOpenSub] = useState(null);

  const canView = canAdmin || user?.role === "reviewer";

  const load = useCallback(() => {
    api.get("/dashboard").then(setData).catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (!loading && canView) load();
  }, [loading, canView, load]);

  async function download(key, path, name) {
    setBusy(key);
    setError(null);
    try {
      await api.download(path, name);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <main className="container" />;
  if (user && !canView)
    return (
      <main className="container narrow">
        <div className="panel"><div className="empty">Company team only.</div></div>
      </main>
    );

  const t = data?.totals;
  const cards = [
    { k: "RFPs", v: t?.rfps ?? "—" },
    { k: "BoQ lines", v: t?.boq_lines ?? "—" },
    { k: "Subcontractors", v: t?.subcontractors ?? "—" },
    { k: "Total BoQ value", v: t ? money(t.total_value) : "—" },
  ];

  return (
    <main className="container">
      <div className="eyebrow">Company</div>
      <h1 className="page-title">Dashboard</h1>
      <p className="page-sub">
        All your RFPs and their Bills of Quantities, broken down by subcontractor.
        Open or download any of them on the go.
      </p>

      {error && <div className="alert">{error}</div>}

      <div className="cards">
        {cards.map((c) => (
          <div className="bigstat" key={c.k}>
            <div className="k">{c.k}</div>
            <div className="v">{c.v}</div>
          </div>
        ))}
      </div>

      {/* RFPs */}
      <section className="panel">
        <div className="panel-head">
          <h2>RFPs &amp; BoQs</h2>
          <span className="tag">{data ? `${data.rfps.length} RFPs` : ""}</span>
        </div>
        {!data && <div className="empty">Loading…</div>}
        {data && data.rfps.length === 0 && (
          <div className="empty">No RFPs yet. <Link href="/">Upload one →</Link></div>
        )}
        {data && data.rfps.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>RFP</th>
                <th>Status</th>
                <th className="num">Scope lines</th>
                <th className="num">BoQ lines</th>
                <th className="num">Value</th>
                <th>Subcontractors</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.rfps.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.filename}</strong>{" "}
                    <span className="muted nums" style={{ fontSize: 12 }}>#{r.id}</span>
                  </td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[r.status] || "badge-gray"}`}>{r.status}</span>
                  </td>
                  <td className="num">{r.scope_lines}</td>
                  <td className="num">{r.boq_lines}</td>
                  <td className="num">{money(r.total_value)}</td>
                  <td>
                    {r.subcontractors.length === 0 ? (
                      <span className="muted" style={{ fontSize: 12 }}>—</span>
                    ) : (
                      r.subcontractors.map((s) => (
                        <span key={s} className="badge badge-gray" style={{ marginRight: 4 }}>{s}</span>
                      ))
                    )}
                  </td>
                  <td className="cell-actions">
                    <Link className="btn btn-sm" href={`/review/${r.id}`}>Open →</Link>
                    <button
                      className="btn btn-sm btn-primary"
                      disabled={!r.boq_lines || busy === `rfp-${r.id}`}
                      onClick={() =>
                        download(`rfp-${r.id}`, `/output/rfp/${r.id}/boq.xlsx?include_unapproved=true`, `BoQ_${r.id}.xlsx`)
                      }
                      title={r.boq_lines ? "Download the full BoQ (Excel)" : "No BoQ lines yet — run matching first"}
                    >
                      ⬇ BoQ
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Subcontractors */}
      <section className="panel">
        <div className="panel-head">
          <h2>By subcontractor</h2>
          <span className="tag">{data ? `${data.subcontractors.length}` : ""}</span>
        </div>
        {!data && <div className="empty">Loading…</div>}
        {data && data.subcontractors.length === 0 && (
          <div className="empty">No subcontractors yet.</div>
        )}
        {data && data.subcontractors.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Subcontractor</th>
                <th className="num">Catalog items</th>
                <th className="num">BoQ lines</th>
                <th className="num">Awarded value</th>
                <th className="num">RFPs</th>
                <th style={{ textAlign: "right" }}></th>
              </tr>
            </thead>
            <tbody>
              {data.subcontractors.map((s) => {
                const key = s.id ?? "own";
                const open = openSub === key;
                return (
                  <Fragment key={key}>
                    <tr>
                      <td>
                        <strong>{s.name}</strong>
                        {s.trade && <span className="muted" style={{ fontSize: 12 }}> · {s.trade}</span>}
                      </td>
                      <td className="num">{s.catalog_items}</td>
                      <td className="num">{s.boq_lines}</td>
                      <td className="num">{money(s.total_value)}</td>
                      <td className="num">{s.rfps.length}</td>
                      <td className="cell-actions">
                        <button
                          className="btn btn-sm"
                          disabled={s.rfps.length === 0}
                          onClick={() => setOpenSub(open ? null : key)}
                        >
                          {open ? "Hide" : "View RFPs"}
                        </button>
                      </td>
                    </tr>
                    {open &&
                      s.rfps.map((sr) => (
                        <tr key={`${key}-${sr.rfp_id}`} style={{ background: "var(--accent-soft)" }}>
                          <td style={{ paddingLeft: 24 }}>
                            <span className="muted">↳</span> {sr.filename}{" "}
                            <span className="muted nums" style={{ fontSize: 12 }}>#{sr.rfp_id}</span>
                          </td>
                          <td className="num"></td>
                          <td className="num">{sr.boq_lines}</td>
                          <td className="num">{money(sr.total_value)}</td>
                          <td className="num"></td>
                          <td className="cell-actions">
                            <Link className="btn btn-sm" href={`/review/${sr.rfp_id}`}>Open →</Link>
                            {s.id != null && (
                              <button
                                className="btn btn-sm btn-primary"
                                disabled={busy === `sub-${key}-${sr.rfp_id}`}
                                onClick={() =>
                                  download(
                                    `sub-${key}-${sr.rfp_id}`,
                                    `/output/rfp/${sr.rfp_id}/boq.xlsx?include_unapproved=true&subcontractor_id=${s.id}`,
                                    `BoQ_${sr.rfp_id}_${s.name}.xlsx`
                                  )
                                }
                                title={`Download ${s.name}'s portion of this BoQ`}
                              >
                                ⬇ Their BoQ
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

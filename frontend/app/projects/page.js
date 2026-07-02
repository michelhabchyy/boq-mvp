"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";
import { STATUSES, LABEL, COLOR, money, fmtDate, fmtWhen, progress } from "./shared";

export default function ProjectsPage() {
  const { user, loading, canAdmin } = useAuth();
  const [projects, setProjects] = useState(null);
  const [activity, setActivity] = useState([]);
  const [error, setError] = useState(null);
  const [dragId, setDragId] = useState(null);
  const [overCol, setOverCol] = useState(null);

  const canView = canAdmin || user?.role === "reviewer";

  const load = useCallback(() => {
    Promise.all([api.get("/projects?limit=1000"), api.get("/projects/activity").catch(() => [])])
      .then(([p, a]) => { setProjects(p); setActivity(a); })
      .catch((e) => setError(String(e.message || e)));
  }, []);
  useEffect(() => { if (!loading && canView) load(); }, [loading, canView, load]);

  async function move(id, status) {
    const p = projects?.find((x) => x.id === id);
    if (!p || p.status === status) return;
    setProjects((ps) => ps.map((x) => (x.id === id ? { ...x, status } : x)));
    try { await api.post(`/projects/${id}/status`, { status }); }
    catch (e) { setError(String(e.message || e)); }
    finally { load(); }
  }

  if (loading) return <main className="container" />;
  if (user && !canView)
    return <main className="container narrow"><div className="panel"><div className="empty">Company team only.</div></div></main>;

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
            Change a project's stage on its card, or open it for full details, files and history.
          </p>
        </div>
        {canAdmin && <Link className="btn btn-primary" href="/projects/new">+ New project</Link>}
      </div>

      {error && <div className="alert" style={{ marginTop: 12 }}>{error}</div>}

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
                      >
                        <Link href={`/projects/${p.id}`} style={{ color: "inherit", textDecoration: "none" }}>
                          <div className="nm">{p.name}</div>
                          <div className="meta">
                            {p.industry && <span className="badge badge-amber">{p.industry}</span>}
                            {p.awarded_from && <span className="chip-i">🏛 {p.awarded_from}</span>}
                          </div>
                          {(p.start_date || p.end_date) && (
                            <div className="meta">🗓 {fmtDate(p.start_date) || "…"} – {fmtDate(p.end_date) || "…"}</div>
                          )}
                          <div className="kan-prog"><span style={{ width: `${pr.pct}%`, background: pr.color }} /></div>
                        </Link>
                        {canAdmin && (
                          <div className="kan-foot">
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

      {projects && hasFin ? (
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="panel-head"><h2>Financials</h2><span className="tag">planned vs actual</span></div>
          <div className="panel-body">
            <div className="statbar" style={{ margin: 0 }}>
              <div className="stat"><div className="k">Contract value awarded</div><div className="v">{money(totalContract)}</div></div>
              <div className="stat"><div className="k">Actual cost</div><div className="v">{money(totalActual)}</div></div>
              <div className="stat"><div className="k">Gross margin</div><div className="v" style={{ color: grossMargin >= 0 ? "var(--success)" : "var(--danger)" }}>{money(grossMargin)}</div></div>
            </div>
            {plannedSum > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>Planned (from BoQ) vs actual — projects with a recorded cost</div>
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

      <section className="panel" style={{ marginTop: 20 }}>
        <div className="panel-head"><h2>Activity log</h2><span className="tag">all pipeline updates</span></div>
        <div className="panel-body">
          {activity.length === 0 ? (
            <div className="empty" style={{ padding: 10 }}>No updates yet.</div>
          ) : (
            <ul className="act">
              {activity.map((e) => (
                <li key={e.id}>
                  <span className="when">{fmtWhen(e.created_at)}</span>
                  <span style={{ flex: 1 }}>
                    <Link href={`/projects/${e.project_id}`} className="pname">{e.project_name}</Link>{" "}
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
    </main>
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

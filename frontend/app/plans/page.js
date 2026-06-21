"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

export default function PlansPage() {
  const { user, loading } = useAuth();
  const [plans, setPlans] = useState(null);
  const [error, setError] = useState(null);

  const load = () =>
    api.get("/plans").then(setPlans).catch((e) => setError(String(e.message || e)));

  useEffect(() => {
    if (!loading && user?.role === "owner") load();
  }, [loading, user]);

  if (loading) return <main className="container" />;
  if (user && user.role !== "owner")
    return (
      <main className="container narrow">
        <div className="panel">
          <div className="empty">Owner only.</div>
        </div>
      </main>
    );

  return (
    <main className="container narrow">
      <div className="eyebrow">Subscriptions</div>
      <h1 className="page-title">Plans</h1>
      <p className="page-sub">
        Each plan caps how many AI tokens a company can use per week (resets every
        Monday). Assign plans to companies on the Companies page.
      </p>

      {error && <div className="alert">{error}</div>}

      <section className="panel">
        <div className="panel-head">
          <h2>Plans</h2>
          <span className="tag">weekly token limits</span>
        </div>
        {!plans && <div className="empty">Loading…</div>}
        {plans && (
          <table className="table">
            <thead>
              <tr>
                <th>Plan</th>
                <th className="num">Weekly token limit</th>
                <th className="num">≈ RFPs/week*</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <PlanRow key={p.id} plan={p} onSaved={load} setError={setError} />
              ))}
            </tbody>
          </table>
        )}
        <div className="panel-body">
          <div className="tag">
            *Rough guide assuming ~200,000 tokens per RFP (analysis + matching).
          </div>
        </div>
      </section>
    </main>
  );
}

function PlanRow({ plan, onSaved, setError }) {
  const [limit, setLimit] = useState(plan.weekly_token_limit);
  const [busy, setBusy] = useState(false);
  useEffect(() => setLimit(plan.weekly_token_limit), [plan.weekly_token_limit]);
  const dirty = Number(limit) !== Number(plan.weekly_token_limit);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/plans/${plan.id}`, { weekly_token_limit: Number(limit) });
      await onSaved();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr>
      <td>
        <strong>{plan.name}</strong>
      </td>
      <td className="num">
        <input
          className="input num"
          style={{ width: 130 }}
          type="number"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
        />
      </td>
      <td className="num">~{Math.max(0, Math.round(Number(limit) / 200000))}</td>
      <td style={{ textAlign: "right" }}>
        {dirty && (
          <button className="btn btn-sm btn-primary" disabled={busy} onClick={save}>
            Save
          </button>
        )}
      </td>
    </tr>
  );
}

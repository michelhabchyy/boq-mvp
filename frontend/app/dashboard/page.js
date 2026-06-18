"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";
import { useAuth } from "../AppChrome";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const [ov, setOv] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!loading && user?.role === "owner")
      api.get("/companies/overview").then(setOv).catch((e) => setError(String(e.message || e)));
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

  const cards = ov
    ? [
        { k: "Companies", v: ov.companies, sub: `${ov.active} active · ${ov.disabled} disabled` },
        { k: "Users", v: ov.users },
        { k: "Catalog items", v: ov.catalog_items },
        { k: "RFPs", v: ov.rfps },
        { k: "BoQ lines", v: ov.boq_lines },
      ]
    : [];

  return (
    <main className="container">
      <div className="between">
        <div>
          <div className="eyebrow">Platform administration</div>
          <h1 className="page-title">Dashboard</h1>
        </div>
        <div className="row">
          <Link className="btn" href="/companies">
            Manage companies
          </Link>
          <Link className="btn btn-primary" href="/companies">
            + New company
          </Link>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      <div className="cards">
        {!ov &&
          [0, 1, 2, 3, 4].map((i) => (
            <div className="bigstat" key={i}>
              <div className="k">—</div>
              <div className="v">—</div>
            </div>
          ))}
        {ov &&
          cards.map((c) => (
            <div className="bigstat" key={c.k}>
              <div className="k">{c.k}</div>
              <div className="v">{c.v}</div>
              {c.sub && <div className="sub">{c.sub}</div>}
            </div>
          ))}
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>Companies usage</h2>
          <span className="tag">{ov ? `${ov.breakdown.length} tenants` : ""}</span>
        </div>
        {!ov && <div className="empty">Loading…</div>}
        {ov && ov.breakdown.length === 0 && (
          <div className="empty">
            No companies yet. <Link href="/companies">Create your first company →</Link>
          </div>
        )}
        {ov && ov.breakdown.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Status</th>
                <th className="num">Users</th>
                <th className="num">Catalog</th>
                <th className="num">RFPs</th>
                <th className="num">BoQ lines</th>
              </tr>
            </thead>
            <tbody>
              {ov.breakdown.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.name}</strong>{" "}
                    <span className="muted nums" style={{ fontSize: 12 }}>#{c.id}</span>
                  </td>
                  <td>
                    <span className={`badge ${c.is_active ? "badge-green" : "badge-gray"}`}>
                      {c.is_active ? "active" : "disabled"}
                    </span>
                  </td>
                  <td className="num">{c.users}</td>
                  <td className="num">{c.catalog_items}</td>
                  <td className="num">{c.rfps}</td>
                  <td className="num">{c.boq_lines}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

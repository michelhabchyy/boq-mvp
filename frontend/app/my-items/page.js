"use client";

import { useCallback, useEffect, useState } from "react";
import { api, money } from "../../lib/api";
import { useAuth } from "../AppChrome";

const BLANK = {
  item_code: "",
  description_en: "",
  description_ar: "",
  unit: "",
  material_cost: 0,
  labour_cost: 0,
  markup: 0,
  brand: "",
};

export default function MyItemsPage() {
  const { user, loading } = useAuth();
  const [items, setItems] = useState(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback((query = "") => {
    api
      .get(`/my-items${query ? `?q=${encodeURIComponent(query)}` : ""}`)
      .then(setItems)
      .catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (!loading && user?.role === "subcontractor") load();
  }, [loading, user, load]);

  async function act(key, fn) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await load(q);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <main className="container" />;
  if (user && user.role !== "subcontractor")
    return (
      <main className="container narrow">
        <div className="panel"><div className="empty">Subcontractor accounts only.</div></div>
      </main>
    );

  return (
    <main className="container">
      <div className="eyebrow">Subcontractor</div>
      <h1 className="page-title">My Items</h1>
      <p className="page-sub">
        Your price list. The contractor matches RFP work against these items —
        each is searchable as soon as you save it.
      </p>

      <div className="statbar">
        <Stat k="Items" v={items?.length ?? "—"} />
        <div className="actions">
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>+ New item</button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      {adding && (
        <ItemForm
          title="New item"
          initial={BLANK}
          submitLabel="Create"
          onCancel={() => setAdding(false)}
          onSubmit={(data) => act("create", async () => { await api.post("/my-items", data); setAdding(false); })}
        />
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Items</h2>
          <div className="row">
            <input className="input" style={{ width: 220 }} placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load(q)} />
            <button className="btn btn-sm" onClick={() => load(q)}>Search</button>
          </div>
        </div>
        {!items && <div className="empty">Loading…</div>}
        {items && items.length === 0 && <div className="empty">No items yet — add your first above.</div>}
        {items && items.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Code</th><th>Description (EN / AR)</th><th>Unit</th>
                <th className="num">Material</th><th className="num">Labour</th>
                <th className="num">Markup %</th><th>Brand</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) =>
                editing === it.id ? (
                  <tr key={it.id}><td colSpan={8} style={{ padding: 0 }}>
                    <ItemForm title={`Edit ${it.item_code}`} initial={it} submitLabel="Save" embedded
                      onCancel={() => setEditing(null)}
                      onSubmit={(data) => act("edit", async () => { await api.patch(`/my-items/${it.id}`, data); setEditing(null); })} />
                  </td></tr>
                ) : (
                  <tr key={it.id}>
                    <td><strong>{it.item_code}</strong></td>
                    <td dir="auto">{it.description_en}{it.description_ar && <div className="muted" style={{ fontSize: 12 }} dir="auto">{it.description_ar}</div>}</td>
                    <td>{it.unit}</td>
                    <td className="num">{money(it.material_cost)}</td>
                    <td className="num">{money(it.labour_cost)}</td>
                    <td className="num">{it.markup}</td>
                    <td>{it.brand}</td>
                    <td className="cell-actions">
                      <button className="btn btn-sm" onClick={() => setEditing(it.id)}>Edit</button>
                      <button className="btn btn-sm btn-danger-ghost" onClick={() => confirm(`Delete ${it.item_code}?`) && act(`d-${it.id}`, () => api.del(`/my-items/${it.id}`))}>Delete</button>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

function ItemForm({ title, initial, submitLabel, onSubmit, onCancel, embedded }) {
  const [f, setF] = useState({ ...BLANK, ...initial });
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const num = (v) => (v === "" || v == null ? 0 : Number(v));
  function submit(e) {
    e.preventDefault();
    onSubmit({
      item_code: f.item_code,
      description_en: f.description_en || null,
      description_ar: f.description_ar || null,
      unit: f.unit || null,
      material_cost: num(f.material_cost),
      labour_cost: num(f.labour_cost),
      markup: num(f.markup),
      brand: f.brand || null,
    });
  }
  return (
    <form onSubmit={submit} className={embedded ? "" : "panel"} style={embedded ? { padding: 14, background: "var(--surface-2)" } : { padding: 16 }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>{title}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        <Field label="Item code"><input className="input" value={f.item_code} onChange={set("item_code")} required /></Field>
        <Field label="Unit"><input className="input" value={f.unit || ""} onChange={set("unit")} /></Field>
        <Field label="Brand"><input className="input" value={f.brand || ""} onChange={set("brand")} /></Field>
        <Field label="Markup %"><input className="input" type="number" value={f.markup} onChange={set("markup")} /></Field>
        <Field label="Description (EN)"><input className="input" value={f.description_en || ""} onChange={set("description_en")} /></Field>
        <Field label="Description (AR)"><input className="input" dir="auto" value={f.description_ar || ""} onChange={set("description_ar")} /></Field>
        <Field label="Material cost"><input className="input" type="number" value={f.material_cost} onChange={set("material_cost")} /></Field>
        <Field label="Labour cost"><input className="input" type="number" value={f.labour_cost} onChange={set("labour_cost")} /></Field>
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn btn-primary btn-sm" type="submit">{submitLabel}</button>
        <button className="btn btn-sm btn-ghost" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function Field({ label, children }) {
  return (<div className="field" style={{ marginTop: 0 }}><label>{label}</label>{children}</div>);
}
function Stat({ k, v }) {
  return (<div className="stat"><div className="k">{k}</div><div className="v">{v}</div></div>);
}

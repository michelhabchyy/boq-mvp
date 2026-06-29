"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, money } from "../../lib/api";
import { useAuth } from "../AppChrome";
import { ItemHistory } from "../catalog/page";

const BLANK = {
  item_code: "",
  description_en: "",
  description_ar: "",
  unit: "",
  count_unit: "",
  unit_cost: 0,
  brand: "",
  industry: "",
  category: "",
  supplier: "",
  model_number: "",
  link: "",
  notes: "",
};

export default function MyItemsPage() {
  const { user, loading } = useAuth();
  const [items, setItems] = useState(null);
  const [history, setHistory] = useState(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState(null);
  const [uploadMsg, setUploadMsg] = useState(null);
  const [busy, setBusy] = useState(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async (query = "") => {
    try {
      const [list, hist] = await Promise.all([
        api.get(`/my-items${query ? `?q=${encodeURIComponent(query)}` : ""}`),
        api.get("/my-items/history"),
      ]);
      setItems(list);
      setHistory(hist);
    } catch (e) {
      setError(String(e.message || e));
    }
  }, []);

  useEffect(() => {
    if (!loading && user?.role === "subcontractor") load();
  }, [loading, user, load]);

  // Suggest industries the subcontractor already used (for the picker).
  const industries = useMemo(
    () => [...new Set((items || []).map((i) => i.industry).filter(Boolean))].sort(),
    [items]
  );

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

  async function onUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    setError(null);
    setUploadMsg(null);
    try {
      const res = await api.upload("/my-items/upload?replace=false&skip_invalid=true", file);
      let msg = `Loaded ${res.loaded} item${res.loaded === 1 ? "" : "s"}.`;
      if (res.skipped) msg += ` Skipped ${res.skipped} invalid row(s).`;
      if (res.loaded === 0) msg += " Nothing imported — check the file matches the sample template.";
      setUploadMsg({ text: msg, ok: res.loaded > 0, errors: res.row_errors || [] });
      await load(q);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(null);
      e.target.value = "";
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
        each is searchable as soon as you save it. <strong>Each item can be
        edited only once per calendar month.</strong>
      </p>

      <div className="statbar">
        <Stat k="Items" v={items?.length ?? "—"} />
        <Stat k="Industries" v={industries.length || "—"} />
        <div className="actions">
          <button
            className="btn"
            disabled={busy === "template"}
            onClick={() => act("template", () => api.download("/my-items/template.xlsx", "items-template.xlsx"))}
            title="Download a blank template to fill in and upload"
          >
            ⬇ Sample template
          </button>
          <label className="btn" style={{ cursor: busy === "upload" ? "wait" : "pointer" }}>
            {busy === "upload" ? "Uploading…" : "⬆ Upload sheet"}
            <input type="file" accept=".csv,.xlsx" hidden disabled={busy === "upload"} onChange={onUpload} />
          </label>
          <button
            className="btn"
            disabled={busy === "export"}
            onClick={() => act("export", () => api.download("/my-items/export", "my-items.xlsx"))}
            title="Download your items as an Excel sheet"
          >
            ⬇ Export Excel
          </button>
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>+ New item</button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      {uploadMsg && (
        <div
          className="alert"
          style={{
            background: uploadMsg.ok ? "var(--success-soft)" : "var(--warn-soft)",
            color: uploadMsg.ok ? "var(--success)" : "var(--accent-text)",
            borderColor: uploadMsg.ok ? "#bbf7d0" : "var(--border)",
          }}
        >
          {uploadMsg.text}
          {uploadMsg.errors.length > 0 && (
            <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 12 }}>
              {uploadMsg.errors.slice(0, 5).map((re) => (
                <li key={re.row}>Row {re.row}: {re.errors.join("; ")}</li>
              ))}
              {uploadMsg.errors.length > 5 && <li>…and {uploadMsg.errors.length - 5} more</li>}
            </ul>
          )}
        </div>
      )}

      {adding && (
        <ItemForm
          title="New item"
          initial={BLANK}
          submitLabel="Create"
          industries={industries}
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
                <th>Code</th>
                <th>Description (EN / AR)</th>
                <th>Industry / Category</th>
                <th>Units (measure / count)</th>
                <th className="num">Unit cost</th>
                <th>Brand / Supplier</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) =>
                editing === it.id ? (
                  <tr key={it.id}><td colSpan={7} style={{ padding: 0 }}>
                    <ItemForm title={`Edit ${it.item_code}`} initial={it} submitLabel="Save" embedded industries={industries}
                      onCancel={() => setEditing(null)}
                      onSubmit={(data) => act("edit", async () => { await api.patch(`/my-items/${it.id}`, data); setEditing(null); })} />
                  </td></tr>
                ) : (
                  <tr key={it.id}>
                    <td>
                      <strong>{it.item_code}</strong>
                      {it.link && (
                        <>
                          {" "}
                          <a href={it.link} target="_blank" rel="noreferrer" title={it.link}>🔗</a>
                        </>
                      )}
                      {it.model_number && (
                        <div className="muted" style={{ fontSize: 11 }}>{it.model_number}</div>
                      )}
                    </td>
                    <td dir="auto">
                      {it.description_en}
                      {it.description_ar && <div className="muted" style={{ fontSize: 12 }} dir="auto">{it.description_ar}</div>}
                      {it.notes && (
                        <div className="muted" style={{ fontSize: 11, fontStyle: "italic" }} dir="auto">
                          {it.notes.length > 80 ? it.notes.slice(0, 80) + "…" : it.notes}
                        </div>
                      )}
                    </td>
                    <td>
                      {it.industry ? (
                        <span className="badge badge-amber">{it.industry}</span>
                      ) : (
                        <span className="muted" style={{ fontSize: 12 }}>—</span>
                      )}
                      {it.category && <div className="muted" style={{ fontSize: 11 }}>{it.category}</div>}
                    </td>
                    <td>
                      {it.unit || <span className="muted">—</span>}
                      {it.count_unit && <span className="muted"> / {it.count_unit}</span>}
                    </td>
                    <td className="num">{money(it.unit_cost)}</td>
                    <td>
                      {it.brand}
                      {it.supplier && <div className="muted" style={{ fontSize: 11 }}>{it.supplier}</div>}
                    </td>
                    <td className="cell-actions">
                      {(() => {
                        const lock = editableAgainOn(it.last_edited_at);
                        return (
                          <button
                            className="btn btn-sm"
                            disabled={!!lock}
                            onClick={() => setEditing(it.id)}
                            title={lock ? `Already edited this month — editable again on ${lock.toLocaleDateString()}` : "Edit"}
                          >
                            {lock ? "Edit 🔒" : "Edit"}
                          </button>
                        );
                      })()}
                      <button className="btn btn-sm btn-danger-ghost" onClick={() => confirm(`Delete ${it.item_code}?`) && act(`d-${it.id}`, () => api.del(`/my-items/${it.id}`))}>Delete</button>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        )}
      </section>

      <ItemHistory history={history} />
    </main>
  );
}

function ItemForm({ title, initial, submitLabel, onSubmit, onCancel, embedded, industries = [] }) {
  const [f, setF] = useState({ ...BLANK, ...initial });
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const num = (v) => (v === "" || v == null ? 0 : Number(v));
  function submit(e) {
    e.preventDefault();
    onSubmit({
      description_en: f.description_en || null,
      description_ar: f.description_ar || null,
      unit: f.unit || null,
      count_unit: f.count_unit || null,
      unit_cost: num(f.unit_cost),
      brand: f.brand || null,
      industry: f.industry || null,
      category: f.category || null,
      supplier: f.supplier || null,
      model_number: f.model_number || null,
      link: f.link || null,
      notes: f.notes || null,
    });
  }
  return (
    <form onSubmit={submit} className={embedded ? "" : "panel"} style={embedded ? { padding: 14, background: "var(--surface-2)" } : { padding: 16 }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>{title}</div>

      <div className="form-section-label">Identification</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        <Field label="Item code"><input className="input" value={f.item_code || "— assigned on save —"} disabled title="Generated automatically by the system" /></Field>
        <Field label="Measure unit"><input className="input" value={f.unit || ""} onChange={set("unit")} placeholder="m, m², kg, L…" /></Field>
        <Field label="Count unit"><input className="input" value={f.count_unit || ""} onChange={set("count_unit")} placeholder="each, pcs, set, box…" /></Field>
        <Field label="Model / part no."><input className="input" value={f.model_number || ""} onChange={set("model_number")} /></Field>
        <Field label="Brand"><input className="input" value={f.brand || ""} onChange={set("brand")} /></Field>
      </div>

      <div className="form-section-label">Classification & price</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        <Field label="Industry / trade">
          <input className="input" list="myitems-industries" value={f.industry || ""} onChange={set("industry")} placeholder="Electrical, Plumbing…" />
          <datalist id="myitems-industries">
            {industries.map((i) => <option key={i} value={i} />)}
          </datalist>
        </Field>
        <Field label="Category"><input className="input" value={f.category || ""} onChange={set("category")} placeholder="Cables, Valves…" /></Field>
        <Field label="Supplier / vendor"><input className="input" value={f.supplier || ""} onChange={set("supplier")} /></Field>
        <Field label="Unit cost"><input className="input" type="number" step="0.01" value={f.unit_cost} onChange={set("unit_cost")} /></Field>
      </div>

      <div className="form-section-label">Descriptions</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
        <Field label="Description (EN)"><input className="input" value={f.description_en || ""} onChange={set("description_en")} /></Field>
        <Field label="Description (AR)"><input className="input" dir="auto" value={f.description_ar || ""} onChange={set("description_ar")} /></Field>
      </div>

      <div className="form-section-label">References</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <Field label="Link (product / datasheet / spec URL)">
          <input className="input" type="url" value={f.link || ""} onChange={set("link")} placeholder="https://…" />
        </Field>
        <Field label="Notes / specifications">
          <input className="input" dir="auto" value={f.notes || ""} onChange={set("notes")} />
        </Field>
      </div>

      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn btn-primary btn-sm" type="submit">{submitLabel}</button>
        <button className="btn btn-sm btn-ghost" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

// If the item was already edited THIS calendar month (UTC, matching the
// backend), return the Date editing is allowed again; otherwise null.
function editableAgainOn(lastEditedAt) {
  if (!lastEditedAt) return null;
  const le = new Date(lastEditedAt);
  const now = new Date();
  if (le.getUTCFullYear() === now.getUTCFullYear() && le.getUTCMonth() === now.getUTCMonth()) {
    const last = now.getUTCMonth() === 11;
    return new Date(Date.UTC(now.getUTCFullYear() + (last ? 1 : 0), last ? 0 : now.getUTCMonth() + 1, 1));
  }
  return null;
}

function Field({ label, children }) {
  return (<div className="field" style={{ marginTop: 0 }}><label>{label}</label>{children}</div>);
}
function Stat({ k, v }) {
  return (<div className="stat"><div className="k">{k}</div><div className="v">{v}</div></div>);
}

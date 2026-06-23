"use client";

import { useCallback, useEffect, useState } from "react";
import { api, money } from "../../lib/api";
import { useAuth } from "../AppChrome";

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

export default function CatalogPage() {
  const { user, loading, canAdmin } = useAuth();
  const [items, setItems] = useState(null);
  const [status, setStatus] = useState(null);
  const [subs, setSubs] = useState({});
  const [industries, setIndustries] = useState([]);
  const [history, setHistory] = useState(null);
  const [q, setQ] = useState("");
  const [industry, setIndustry] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async (query = "", ind = "") => {
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (query) params.set("q", query);
      if (ind) params.set("industry", ind);
      const [list, st, subList, inds, hist] = await Promise.all([
        api.get(`/catalog?${params.toString()}`),
        api.get("/catalog/embeddings/status"),
        api.get("/subcontractors"),
        api.get("/catalog/industries"),
        api.get("/catalog/history"),
      ]);
      setItems(list);
      setStatus(st);
      setSubs(Object.fromEntries(subList.map((s) => [s.id, s.name])));
      setIndustries(inds);
      setHistory(hist);
    } catch (e) {
      setError(String(e.message || e));
    }
  }, []);

  useEffect(() => {
    if (!loading && canAdmin) load();
  }, [loading, canAdmin, load]);

  async function act(key, fn) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await load(q, industry);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  async function onUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    await act("upload", () => api.upload("/catalog/upload?replace=false&skip_invalid=true", file));
    e.target.value = "";
  }

  if (loading) return <main className="container" />;
  if (user && !canAdmin)
    return (
      <main className="container narrow">
        <div className="panel">
          <div className="empty">Admin only. Catalog management requires an admin account.</div>
        </div>
      </main>
    );

  return (
    <main className="container">
      <div className="eyebrow">Supplier rate sheet</div>
      <h1 className="page-title">Catalog</h1>

      <div className="statbar">
        <Stat k="Items" v={items?.length ?? "—"} />
        <Stat k="Industries" v={industries.length || "—"} />
        <Stat
          k="Embedded"
          v={status ? `${status.embedded_items}/${status.total_items}` : "—"}
        />
        <Stat k="Provider" v={status?.provider ?? "—"} />
        <div className="actions">
          <label className="btn" style={{ cursor: "pointer" }}>
            ⬆ Upload sheet
            <input type="file" accept=".csv,.xlsx" hidden onChange={onUpload} />
          </label>
          <button
            className="btn"
            disabled={busy === "export"}
            onClick={() => act("export", () => api.download("/catalog/export", "catalog.xlsx"))}
            title="Download the catalog as an Excel sheet"
          >
            ⬇ Export Excel
          </button>
          <button
            className="btn"
            disabled={busy === "embed"}
            onClick={() => act("embed", () => api.post("/catalog/embeddings/build"))}
            title="Generate embeddings for any items missing one"
          >
            {busy === "embed" ? "Embedding…" : "⚙ Build embeddings"}
          </button>
          <button
            className="btn"
            disabled={busy === "reembed"}
            onClick={() =>
              confirm("Re-embed every item with the current provider?") &&
              act("reembed", () => api.post("/catalog/embeddings/build?force=true"))
            }
            title="Re-embed ALL items (use after switching embedding provider or editing classification)"
          >
            {busy === "reembed" ? "Re-embedding…" : "↻ Re-embed all"}
          </button>
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            + New item
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      {adding && (
        <ItemForm
          title="New catalog item"
          initial={BLANK}
          submitLabel="Create"
          industries={industries}
          onCancel={() => setAdding(false)}
          onSubmit={(data) =>
            act("create", async () => {
              await api.post("/catalog/item", data);
              setAdding(false);
            })
          }
        />
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Items</h2>
          <div className="row">
            <select
              className="input"
              style={{ width: 170 }}
              value={industry}
              onChange={(e) => {
                setIndustry(e.target.value);
                load(q, e.target.value);
              }}
            >
              <option value="">All industries</option>
              {industries.map((i) => (
                <option key={i} value={i}>{i}</option>
              ))}
            </select>
            <input
              className="input"
              style={{ width: 240 }}
              placeholder="Search code / desc / brand / supplier…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load(q, industry)}
            />
            <button className="btn btn-sm" onClick={() => load(q, industry)}>
              Search
            </button>
          </div>
        </div>

        {!items && <div className="empty">Loading…</div>}
        {items && items.length === 0 && (
          <div className="empty">No items. Upload a rate sheet or add one above.</div>
        )}
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
                <th>Sub</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) =>
                editing === it.id ? (
                  <tr key={it.id}>
                    <td colSpan={8} style={{ padding: 0 }}>
                      <ItemForm
                        title={`Edit ${it.item_code}`}
                        initial={it}
                        submitLabel="Save"
                        embedded
                        industries={industries}
                        onCancel={() => setEditing(null)}
                        onSubmit={(data) =>
                          act("edit", async () => {
                            await api.patch(`/catalog/${it.id}`, data);
                            setEditing(null);
                          })
                        }
                      />
                    </td>
                  </tr>
                ) : (
                  <tr key={it.id}>
                    <td>
                      <strong>{it.item_code}</strong>
                      {it.link && (
                        <>
                          {" "}
                          <a href={it.link} target="_blank" rel="noreferrer" title={it.link}>
                            🔗
                          </a>
                        </>
                      )}
                      {it.model_number && (
                        <div className="muted" style={{ fontSize: 11 }}>{it.model_number}</div>
                      )}
                    </td>
                    <td dir="auto">
                      {it.description_en}
                      {it.description_ar && (
                        <div className="muted" style={{ fontSize: 12 }} dir="auto">
                          {it.description_ar}
                        </div>
                      )}
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
                      {it.category && (
                        <div className="muted" style={{ fontSize: 11 }}>{it.category}</div>
                      )}
                    </td>
                    <td>
                      {it.unit || <span className="muted">—</span>}
                      {it.count_unit && (
                        <span className="muted"> / {it.count_unit}</span>
                      )}
                    </td>
                    <td className="num">{money(it.unit_cost)}</td>
                    <td>
                      {it.brand}
                      {it.supplier && (
                        <div className="muted" style={{ fontSize: 11 }}>{it.supplier}</div>
                      )}
                    </td>
                    <td>
                      {it.subcontractor_id ? (
                        <span className="badge badge-gray">{subs[it.subcontractor_id] || "sub"}</span>
                      ) : (
                        <span className="muted" style={{ fontSize: 12 }}>own</span>
                      )}
                    </td>
                    <td className="cell-actions">
                      <button className="btn btn-sm" onClick={() => setEditing(it.id)}>
                        Edit
                      </button>
                      <button
                        className="btn btn-sm btn-danger-ghost"
                        onClick={() =>
                          confirm(`Delete ${it.item_code}?`) &&
                          act(`del-${it.id}`, () => api.del(`/catalog/item/${it.id}`))
                        }
                      >
                        Delete
                      </button>
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

export function ItemHistory({ history }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>History</h2>
        <span className="tag">edits & deletions</span>
      </div>
      {!history && <div className="empty">Loading…</div>}
      {history && history.length === 0 && (
        <div className="empty">No changes recorded yet.</div>
      )}
      {history && history.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>When</th>
              <th>Action</th>
              <th>Code</th>
              <th>Item</th>
              <th>Change</th>
              <th>By</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id}>
                <td className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                  {new Date(h.created_at).toLocaleString()}
                </td>
                <td>
                  <span className={`badge ${h.action === "deleted" ? "badge-red" : "badge-amber"}`}>
                    {h.action}
                  </span>
                </td>
                <td><strong>{h.item_code}</strong></td>
                <td dir="auto">{h.item_description || <span className="muted">—</span>}</td>
                <td dir="auto" style={{ fontSize: 12 }}>
                  {h.details || <span className="muted">—</span>}
                </td>
                <td className="muted" style={{ fontSize: 12 }}>{h.username || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
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
    <form
      onSubmit={submit}
      className={embedded ? "" : "panel"}
      style={embedded ? { padding: 14, background: "var(--surface-2)" } : { padding: 16 }}
    >
      <div className="eyebrow" style={{ marginBottom: 8 }}>
        {title}
      </div>

      <div className="form-section-label">Identification</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        <Field label="Item code">
          <input
            className="input"
            value={f.item_code || "— assigned on save —"}
            disabled
            title="Generated automatically by the system"
          />
        </Field>
        <Field label="Measure unit">
          <input className="input" value={f.unit || ""} onChange={set("unit")} placeholder="m, m², kg, L…" />
        </Field>
        <Field label="Count unit">
          <input className="input" value={f.count_unit || ""} onChange={set("count_unit")} placeholder="each, pcs, set, box…" />
        </Field>
        <Field label="Model / part no.">
          <input className="input" value={f.model_number || ""} onChange={set("model_number")} />
        </Field>
        <Field label="Brand">
          <input className="input" value={f.brand || ""} onChange={set("brand")} />
        </Field>
      </div>

      <div className="form-section-label">Classification</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        <Field label="Industry / trade">
          <input
            className="input"
            list="catalog-industries"
            value={f.industry || ""}
            onChange={set("industry")}
            placeholder="Electrical, Plumbing…"
          />
          <datalist id="catalog-industries">
            {industries.map((i) => (
              <option key={i} value={i} />
            ))}
          </datalist>
        </Field>
        <Field label="Category">
          <input className="input" value={f.category || ""} onChange={set("category")} placeholder="Cables, Valves…" />
        </Field>
        <Field label="Supplier / vendor">
          <input className="input" value={f.supplier || ""} onChange={set("supplier")} />
        </Field>
        <Field label="Unit cost">
          <input className="input" type="number" step="0.01" value={f.unit_cost} onChange={set("unit_cost")} />
        </Field>
      </div>

      <div className="form-section-label">Descriptions</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
        <Field label="Description (EN)">
          <input className="input" value={f.description_en || ""} onChange={set("description_en")} />
        </Field>
        <Field label="Description (AR)">
          <input className="input" dir="auto" value={f.description_ar || ""} onChange={set("description_ar")} />
        </Field>
      </div>

      <div className="form-section-label">References</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <Field label="Link (product / datasheet / spec URL)">
          <input
            className="input"
            type="url"
            value={f.link || ""}
            onChange={set("link")}
            placeholder="https://…"
          />
        </Field>
        <Field label="Notes / specifications">
          <input className="input" dir="auto" value={f.notes || ""} onChange={set("notes")} />
        </Field>
      </div>

      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn btn-primary btn-sm" type="submit">
          {submitLabel}
        </button>
        <button className="btn btn-sm btn-ghost" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function Field({ label, children }) {
  return (
    <div className="field" style={{ marginTop: 0 }}>
      <label>{label}</label>
      {children}
    </div>
  );
}

function Stat({ k, v }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}

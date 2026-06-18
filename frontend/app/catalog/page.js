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

export default function CatalogPage() {
  const { user, loading } = useAuth();
  const [items, setItems] = useState(null);
  const [status, setStatus] = useState(null);
  const [subs, setSubs] = useState({});
  const [q, setQ] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(
    async (query = "") => {
      try {
        const [list, st, subList] = await Promise.all([
          api.get(`/catalog?limit=200${query ? `&q=${encodeURIComponent(query)}` : ""}`),
          api.get("/catalog/embeddings/status"),
          api.get("/subcontractors"),
        ]);
        setItems(list);
        setStatus(st);
        setSubs(Object.fromEntries(subList.map((s) => [s.id, s.name])));
      } catch (e) {
        setError(String(e.message || e));
      }
    },
    []
  );

  useEffect(() => {
    if (!loading && user?.role === "admin") load();
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

  async function onUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    await act("upload", () => api.upload("/catalog/upload?replace=false&skip_invalid=true", file));
    e.target.value = "";
  }

  if (loading) return <main className="container" />;
  if (user && user.role !== "admin")
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
            title="Re-embed ALL items (use after switching embedding provider)"
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
            <input
              className="input"
              style={{ width: 240 }}
              placeholder="Search code / AR / EN…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load(q)}
            />
            <button className="btn btn-sm" onClick={() => load(q)}>
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
                <th>Unit</th>
                <th className="num">Material</th>
                <th className="num">Labour</th>
                <th className="num">Markup %</th>
                <th>Brand</th>
                <th>Subcontractor</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) =>
                editing === it.id ? (
                  <tr key={it.id}>
                    <td colSpan={9} style={{ padding: 0 }}>
                      <ItemForm
                        title={`Edit ${it.item_code}`}
                        initial={it}
                        submitLabel="Save"
                        embedded
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
                    </td>
                    <td dir="auto">
                      {it.description_en}
                      {it.description_ar && (
                        <div className="muted" style={{ fontSize: 12 }} dir="auto">
                          {it.description_ar}
                        </div>
                      )}
                    </td>
                    <td>{it.unit}</td>
                    <td className="num">{money(it.material_cost)}</td>
                    <td className="num">{money(it.labour_cost)}</td>
                    <td className="num">{it.markup}</td>
                    <td>{it.brand}</td>
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
    <form
      onSubmit={submit}
      className={embedded ? "" : "panel"}
      style={embedded ? { padding: 14, background: "var(--surface-2)" } : { padding: 16 }}
    >
      <div className="eyebrow" style={{ marginBottom: 8 }}>
        {title}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        <Field label="Item code">
          <input className="input" value={f.item_code} onChange={set("item_code")} required />
        </Field>
        <Field label="Unit">
          <input className="input" value={f.unit || ""} onChange={set("unit")} />
        </Field>
        <Field label="Brand">
          <input className="input" value={f.brand || ""} onChange={set("brand")} />
        </Field>
        <Field label="Markup %">
          <input className="input" type="number" value={f.markup} onChange={set("markup")} />
        </Field>
        <Field label="Description (EN)">
          <input className="input" value={f.description_en || ""} onChange={set("description_en")} />
        </Field>
        <Field label="Description (AR)">
          <input className="input" dir="auto" value={f.description_ar || ""} onChange={set("description_ar")} />
        </Field>
        <Field label="Material cost">
          <input className="input" type="number" value={f.material_cost} onChange={set("material_cost")} />
        </Field>
        <Field label="Labour cost">
          <input className="input" type="number" value={f.labour_cost} onChange={set("labour_cost")} />
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

"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, money } from "../../../lib/api";

export default function ReviewPage() {
  const { rfpId } = useParams();
  const [doc, setDoc] = useState(null);
  const [groups, setGroups] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    try {
      const [d, g] = await Promise.all([
        api.get(`/rfps/${rfpId}`),
        api.get(`/matching/rfp/${rfpId}`),
      ]);
      setDoc(d.document);
      setGroups(g);
    } catch (e) {
      setError(String(e));
    }
  }, [rfpId]);

  useEffect(() => {
    load();
  }, [load]);

  const allLines = (groups || []).flatMap((g) => g.boq_lines);
  const total = allLines.reduce((s, l) => s + Number(l.line_total || 0), 0);
  const flagged = allLines.filter((l) => l.needs_review && !l.approved).length;
  const approved = allLines.filter((l) => l.approved).length;

  async function action(key, fn) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="container">
      <Link href="/" className="crumb">
        ← All RFPs
      </Link>
      <h1 className="page-title">
        Review BoQ{" "}
        <span className="muted" style={{ fontWeight: 500 }}>
          {doc ? `· ${doc.filename}` : `· RFP ${rfpId}`}
        </span>
      </h1>

      <div className="statbar">
        <Stat k="Scope lines" v={groups?.length ?? "—"} />
        <Stat k="BoQ lines" v={allLines.length} />
        <Stat k="Flagged" v={flagged} cls={flagged ? "badge-amber" : "badge-green"} />
        <Stat k="Approved" v={`${approved}/${allLines.length}`} />
        <Stat k="Total" v={money(total)} />
        <div className="actions">
          <button
            className="btn"
            disabled={busy === "rerun"}
            onClick={() => action("rerun", () => api.post(`/matching/run/${rfpId}`))}
          >
            {busy === "rerun" ? "Matching…" : "↻ Re-run"}
          </button>
          <button
            className="btn"
            disabled={busy === "approveall" || allLines.length === 0}
            onClick={() =>
              action("approveall", () => api.post(`/boq-lines/approve-all?rfp_id=${rfpId}`))
            }
          >
            ✓ Approve all
          </button>
          <button
            className={`btn ${approved > 0 ? "btn-success" : ""}`}
            disabled={busy === "export"}
            onClick={() =>
              action("export", () =>
                api.download(
                  `/output/rfp/${rfpId}/boq.xlsx?include_unapproved=true`,
                  `BoQ_${rfpId}.xlsx`
                )
              )
            }
            title="Download the BoQ as Excel (works even if nothing is matched yet)"
          >
            {busy === "export" ? "Exporting…" : "⬇ Export"}
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      {groups && groups.length === 0 && (
        <div className="panel">
          <div className="empty">
            No scope lines matched yet. Run matching from the RFP workspace.
          </div>
        </div>
      )}

      {groups && <SectionedGroups groups={groups} onChange={load} setError={setError} />}
    </main>
  );
}

function SectionedGroups({ groups, onChange, setError }) {
  // Group scope lines by their section (from AI analysis). Flat uploads have
  // section_no 0 / no title → render without section headers.
  const map = new Map();
  for (const g of groups) {
    const no = g.scope_line.section_no ?? 0;
    if (!map.has(no))
      map.set(no, { no, title: g.scope_line.section_title || null, items: [] });
    map.get(no).items.push(g);
  }
  const sections = [...map.values()].sort((a, b) => a.no - b.no);
  const flat = sections.length === 1 && !sections[0].title;

  if (flat)
    return sections[0].items.map((g) => (
      <ScopeGroup key={g.scope_line.id} group={g} onChange={onChange} setError={setError} />
    ));

  return sections.map((s) => {
    const total = s.items
      .flatMap((g) => g.boq_lines)
      .reduce((sum, l) => sum + Number(l.line_total || 0), 0);
    return (
      <div key={s.no} style={{ marginBottom: 22 }}>
        <div className="section-head">
          <div className="row" style={{ gap: 10 }}>
            <span className="section-no">{s.no}</span>
            <span style={{ fontWeight: 700 }}>{s.title || "Section"}</span>
            <span className="tag">{s.items.length} items</span>
          </div>
          <div className="nums" style={{ fontWeight: 700 }}>
            {money(total)}
          </div>
        </div>
        {s.items.map((g) => (
          <ScopeGroup key={g.scope_line.id} group={g} onChange={onChange} setError={setError} />
        ))}
      </div>
    );
  });
}

function ScopeGroup({ group, onChange, setError }) {
  const s = group.scope_line;
  const subtotal = group.boq_lines.reduce((sum, l) => sum + Number(l.line_total || 0), 0);
  const [adding, setAdding] = useState(false);

  return (
    <section className="scope">
      <div className="scope-head">
        <div>
          <div className="eyebrow">
            Scope #{s.line_no} · {s.quantity ?? "—"} {s.unit || ""}
          </div>
          <div className="desc" dir="auto">
            {s.description}
          </div>
        </div>
        <div style={{ textAlign: "right", whiteSpace: "nowrap" }}>
          <div className="eyebrow">Subtotal</div>
          <div className="nums" style={{ fontWeight: 700, fontSize: 15 }}>
            {money(subtotal)}
          </div>
        </div>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Catalog item</th>
            <th className="num">Qty</th>
            <th className="num">Unit price</th>
            <th className="num">Total</th>
            <th>Conf.</th>
            <th>Brand / comments</th>
            <th style={{ textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {group.boq_lines.length === 0 && (
            <tr>
              <td colSpan={7}>
                <span className="muted">No proposed items.</span>
              </td>
            </tr>
          )}
          {group.boq_lines.map((bl) => (
            <BoqRow key={bl.id} bl={bl} onChange={onChange} setError={setError} />
          ))}
        </tbody>
      </table>

      <div className="scope-foot">
        {adding ? (
          <AddItem
            rfpLineId={s.id}
            onDone={() => {
              setAdding(false);
              onChange();
            }}
            onCancel={() => setAdding(false)}
            setError={setError}
          />
        ) : (
          <button className="btn btn-sm btn-ghost" onClick={() => setAdding(true)}>
            + Add item
          </button>
        )}
      </div>
    </section>
  );
}

function BoqRow({ bl, onChange, setError }) {
  const matched = bl.catalog_item_id != null;
  const [qty, setQty] = useState(bl.quantity);
  const [price, setPrice] = useState(bl.unit_price);
  const [brand, setBrand] = useState(bl.brand || "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setQty(bl.quantity);
    setPrice(bl.unit_price);
    setBrand(bl.brand || "");
  }, [bl.quantity, bl.unit_price, bl.brand]);

  const dirty =
    Number(qty) !== Number(bl.quantity) ||
    Number(price) !== Number(bl.unit_price) ||
    brand !== (bl.brand || "");

  async function call(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const flag = bl.needs_review && !bl.approved;
  const rowCls = bl.approved ? "row-approved" : flag ? "row-flagged" : "";
  const pct = Math.round((bl.confidence || 0) * 100);
  const badgeCls = flag ? "badge-red" : pct >= 80 ? "badge-green" : "badge-amber";

  return (
    <tr className={rowCls}>
      <td dir="auto">
        {matched ? (
          <>
            <strong>{bl.item_code}</strong>
            {bl.subcontractor && (
              <span className="badge badge-gray" style={{ marginLeft: 6 }}>
                {bl.subcontractor}
              </span>
            )}
            <div className="muted" style={{ fontSize: 12 }}>
              {bl.description_en}
            </div>
            {bl.description_ar && (
              <div style={{ fontSize: 12, color: "var(--text-subtle)" }} dir="auto">
                {bl.description_ar}
              </div>
            )}
          </>
        ) : (
          <div>
            <span className="badge badge-red">no match</span>
            {bl.notes && (
              <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                {bl.notes}
              </div>
            )}
          </div>
        )}
      </td>
      <td className="num">
        <input
          className="input num"
          type="number"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          disabled={!matched}
        />
        <div className="tag" style={{ marginTop: 2 }}>
          {bl.unit}
        </div>
      </td>
      <td className="num">
        <input
          className="input num"
          type="number"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          disabled={!matched}
        />
      </td>
      <td className="num" style={{ fontWeight: 700 }}>
        {money(bl.line_total)}
      </td>
      <td>
        <span className={`badge ${badgeCls}`}>{pct}%</span>
      </td>
      <td>
        <input
          className="input"
          value={brand}
          placeholder="brand…"
          onChange={(e) => setBrand(e.target.value)}
        />
      </td>
      <td className="cell-actions">
        {dirty && (
          <button
            className="btn btn-sm btn-primary"
            disabled={busy}
            onClick={() =>
              call(() =>
                api.patch(`/boq-lines/${bl.id}`, {
                  quantity: Number(qty),
                  unit_price: Number(price),
                  brand,
                })
              )
            }
          >
            Save
          </button>
        )}
        <button
          className={`btn btn-sm ${bl.approved ? "btn-approved" : "btn-approve"}`}
          disabled={busy}
          onClick={() =>
            call(() => api.patch(`/boq-lines/${bl.id}`, { approved: !bl.approved }))
          }
        >
          {bl.approved ? "✓ Approved" : "Approve"}
        </button>
        <button
          className="btn btn-sm btn-danger-ghost"
          disabled={busy}
          onClick={() => call(() => api.del(`/boq-lines/${bl.id}`))}
        >
          Delete
        </button>
      </td>
    </tr>
  );
}

function AddItem({ rfpLineId, onDone, onCancel, setError }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [picked, setPicked] = useState(null);
  const [qty, setQty] = useState(1);
  const [busy, setBusy] = useState(false);

  async function search() {
    setError(null);
    try {
      setHits(await api.get(`/catalog?q=${encodeURIComponent(q)}&limit=8`));
    } catch (e) {
      setError(String(e));
    }
  }

  async function add() {
    if (!picked) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/boq-lines", {
        rfp_line_id: rfpLineId,
        catalog_item_id: picked.id,
        quantity: Number(qty),
      });
      onDone();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="picker">
      <div className="row">
        <input
          className="input"
          style={{ flex: 1 }}
          placeholder="Search catalog (code / AR / EN)…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          autoFocus
        />
        <button className="btn btn-sm" onClick={search}>
          Search
        </button>
        <button className="btn btn-sm btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {hits.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {hits.map((h) => (
            <label key={h.id} className="hit">
              <input
                type="radio"
                name={`pick-${rfpLineId}`}
                checked={picked?.id === h.id}
                onChange={() => setPicked(h)}
              />
              <span dir="auto">
                <strong>{h.item_code}</strong> · {h.description_en}
                {h.description_ar ? ` / ${h.description_ar}` : ""}
              </span>
            </label>
          ))}
          {picked && (
            <div className="row" style={{ marginTop: 8 }}>
              <span className="tag">Qty</span>
              <input
                className="input num"
                type="number"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
              />
              <button className="btn btn-sm btn-primary" disabled={busy} onClick={add}>
                Add {picked.item_code}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ k, v, cls }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v">{cls ? <span className={`badge ${cls}`}>{v}</span> : v}</div>
    </div>
  );
}

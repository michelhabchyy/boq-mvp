export const STATUSES = [
  { key: "lead", label: "Lead", color: "#64748b" },
  { key: "bidding", label: "Bidding", color: "#0e6e6e" },
  { key: "shortlisted", label: "Shortlisted", color: "#2563eb" },
  { key: "awarded", label: "Awarded", color: "#2fb573" },
  { key: "in_progress", label: "In progress", color: "#b45309" },
  { key: "completed", label: "Completed", color: "#15803d" },
  { key: "lost", label: "Lost", color: "#b3261e" },
];
export const LABEL = Object.fromEntries(STATUSES.map((s) => [s.key, s.label]));
export const COLOR = Object.fromEntries(STATUSES.map((s) => [s.key, s.color]));
export const ORDER = ["lead", "bidding", "shortlisted", "awarded", "in_progress", "completed"];

export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString() : "");
export const fmtWhen = (d) => (d ? new Date(d).toLocaleString() : "");
export const money = (n, cur = "SAR") =>
  n == null || n === "" ? "—" : `${cur} ${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function progress(status) {
  if (status === "lost") return { pct: 100, color: COLOR.lost };
  const i = ORDER.indexOf(status);
  return { pct: ((i + 1) / ORDER.length) * 100, color: COLOR[status] };
}

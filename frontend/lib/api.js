// Fetch wrapper around the FastAPI backend, with JWT auth.
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "boq_token";

export function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
}
function setToken(t) {
  if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, t);
}
function clearToken() {
  if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
}

// When the OWNER "opens" a company, we store it here and send X-Company-Id so
// the backend treats the owner as that company's admin (impersonation).
const COMPANY_KEY = "boq_company";
export function getActingCompany() {
  if (typeof window === "undefined") return null;
  const v = localStorage.getItem(COMPANY_KEY);
  return v ? JSON.parse(v) : null;
}
export function setActingCompany(company) {
  if (typeof window !== "undefined")
    localStorage.setItem(COMPANY_KEY, JSON.stringify(company));
}
export function clearActingCompany() {
  if (typeof window !== "undefined") localStorage.removeItem(COMPANY_KEY);
}

function authHeaders() {
  const t = getToken();
  const h = t ? { Authorization: `Bearer ${t}` } : {};
  const co = getActingCompany();
  if (co) h["X-Company-Id"] = String(co.id);
  return h;
}

async function handle(res) {
  if (res.status === 401) {
    // Token missing/expired — bounce to login (unless we're already there).
    clearToken();
    if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
      location.href = "/login";
    }
    throw new Error("Not authenticated");
  }
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  base: BASE,
  get: (path) => fetch(`${BASE}${path}`, { headers: authHeaders() }).then(handle),
  post: (path, body) =>
    fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: body == null ? undefined : JSON.stringify(body),
    }).then(handle),
  patch: (path, body) =>
    fetch(`${BASE}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    }).then(handle),
  del: (path) =>
    fetch(`${BASE}${path}`, { method: "DELETE", headers: authHeaders() }).then(handle),
  upload: (path, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}${path}`, {
      method: "POST",
      headers: authHeaders(),
      body: fd,
    }).then(handle);
  },
  // Multipart with extra fields/files (the page builds the FormData).
  uploadForm: (path, formData) =>
    fetch(`${BASE}${path}`, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    }).then(handle),

  // Download a binary file (e.g. .xlsx) and trigger a browser save.
  async download(path, fallbackName = "download") {
    const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
    if (!res.ok) {
      let detail;
      try {
        detail = (await res.json()).detail;
      } catch {
        detail = res.statusText;
      }
      throw new Error(typeof detail === "string" ? detail : "Download failed");
    }
    let name = fallbackName;
    const cd = res.headers.get("Content-Disposition");
    const m = cd && cd.match(/filename="?([^"]+)"?/);
    if (m) name = m[1];
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  // Fetch a file (with auth) and open it in a new tab for preview.
  async openInNewTab(path) {
    const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
    if (!res.ok) {
      let detail;
      try {
        detail = (await res.json()).detail;
      } catch {
        detail = res.statusText;
      }
      throw new Error(typeof detail === "string" ? detail : "Could not open file");
    }
    const url = URL.createObjectURL(await res.blob());
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  // --- auth helpers ---
  async login(username, password, otp) {
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, otp: otp || undefined }),
    });
    const data = await handle(res);
    if (data.mfa_required) return { mfaRequired: true };
    setToken(data.access_token);
    return { user: data.user };
  },
  logout() {
    clearToken();
    clearActingCompany();
    if (typeof window !== "undefined") location.href = "/login";
  },
};

export const money = (n) =>
  (Number(n) || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

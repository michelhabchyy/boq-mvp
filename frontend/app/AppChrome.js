"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  getToken,
  getActingCompany,
  setActingCompany as persistActingCompany,
  clearActingCompany,
} from "../lib/api";

const AuthContext = createContext({ user: null, loading: true });
export const useAuth = () => useContext(AuthContext);

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AppChrome({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(null);
  const isLogin = pathname?.startsWith("/login");

  useEffect(() => {
    if (isLogin) {
      setLoading(false);
      return;
    }
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setActing(getActingCompany());
    api
      .get("/auth/me")
      .then((u) => {
        setUser(u);
        setLoading(false);
        // Owner with no company selected belongs in the platform area.
        const ownerArea =
          pathname?.startsWith("/dashboard") ||
          pathname?.startsWith("/companies") ||
          pathname?.startsWith("/plans");
        if (u.role === "owner" && !getActingCompany() && !ownerArea) {
          router.replace("/dashboard");
        } else if (u.role === "subcontractor" && !pathname?.startsWith("/my-items")) {
          router.replace("/my-items");
        }
      })
      .catch(() => {});
  }, [pathname, isLogin, router]);

  function enterCompany(company) {
    persistActingCompany(company);
    setActing(company);
    router.push("/");
  }
  function exitCompany() {
    clearActingCompany();
    setActing(null);
    router.push("/dashboard");
  }

  // "Admin context" = a real company admin, OR the owner acting on a company.
  const canAdmin =
    user?.role === "admin" || (user?.role === "owner" && !!acting);

  const ctx = { user, loading, acting, enterCompany, exitCompany, canAdmin };

  if (isLogin) {
    return (
      <AuthContext.Provider value={{ ...ctx, loading: false }}>
        {children}
      </AuthContext.Provider>
    );
  }

  return (
    <AuthContext.Provider value={ctx}>
      <TopBar user={user} pathname={pathname} acting={acting} />
      {acting && user?.role === "owner" && (
        <div className="actbanner">
          <span>
            Viewing as <strong>{acting.name}</strong> <span className="muted">(owner)</span>
          </span>
          <button className="btn btn-sm" onClick={exitCompany}>
            ← Exit to owner
          </button>
        </div>
      )}
      {children}
    </AuthContext.Provider>
  );
}

const fmtTok = (n) => {
  n = Number(n) || 0;
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + "M";
  if (n >= 1_000) return Math.round(n / 1_000) + "K";
  return String(n);
};

// Live chip in the top bar: the current user's own token spend this week, with
// the company's remaining weekly allowance. Polls so it stays "live".
function UsageChip({ routeKey }) {
  const [u, setU] = useState(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    const fetchIt = () =>
      api
        .get("/usage/me")
        .then((d) => aliveRef.current && setU(d))
        .catch(() => {});
    fetchIt();
    const id = setInterval(fetchIt, 12000);
    const onFocus = () => fetchIt();
    window.addEventListener("focus", onFocus);
    return () => {
      aliveRef.current = false;
      clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, [routeKey]);

  if (!u) return null;
  const limit = u.company_weekly_limit || 0;
  const used = u.company_weekly_used || 0;
  const pct = limit ? Math.round((used / limit) * 100) : 0;
  const level = limit && used >= limit ? "over" : pct >= 80 ? "warn" : "";

  return (
    <Link
      href="/usage"
      className={`usagechip ${level}`}
      title={
        `You spent ${(u.tokens_this_week || 0).toLocaleString()} tokens this week ` +
        `(${(u.tokens_all_time || 0).toLocaleString()} all-time). ` +
        `Company: ${used.toLocaleString()} / ${limit.toLocaleString()} this week (${pct}%).`
      }
    >
      <span className="dot" />
      <span>{fmtTok(u.tokens_this_week)}</span>
      <span className="muted">you · {pct}% co</span>
    </Link>
  );
}

function TopBar({ user, pathname, acting }) {
  const role = user?.role;
  const isOwner = role === "owner";
  const isAdmin = role === "admin";
  const isSub = role === "subcontractor";
  const ownerActing = isOwner && !!acting;
  // Owner acting on a company gets the admin menu; idle owner gets the platform menu.
  const adminMenu = isAdmin || ownerActing;

  const nav = [
    { href: "/dashboard", label: "Dashboard", show: isOwner && !ownerActing },
    { href: "/companies", label: "Companies", show: isOwner && !ownerActing },
    { href: "/plans", label: "Plans", show: isOwner && !ownerActing },
    { href: "/overview", label: "Dashboard", show: role === "reviewer" || adminMenu },
    { href: "/", label: "RFPs", show: role === "reviewer" || adminMenu },
    { href: "/catalog", label: "Catalog", show: adminMenu },
    { href: "/subcontractors", label: "Subcontractors", show: adminMenu },
    { href: "/users", label: "Users", show: adminMenu },
    { href: "/usage", label: "Usage", show: role === "reviewer" || adminMenu },
    { href: "/my-items", label: "My Items", show: isSub },
  ].filter((n) => n.show);

  // A company context exists (own company, or owner impersonating one) iff the
  // usage endpoints will resolve — only then show the live token chip.
  const inCompany = role === "admin" || role === "reviewer" || ownerActing;

  const active = (href) =>
    href === "/" ? pathname === "/" : pathname?.startsWith(href);

  return (
    <header className="topbar">
      <Link className="brand" href={isOwner && !ownerActing ? "/dashboard" : "/"} style={{ color: "#fff" }}>
        <span className="mark" />
        BoQ Automation
      </Link>
      <nav className="nav">
        {nav.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            style={active(n.href) ? { color: "#fff", background: "rgba(255,255,255,.12)" } : undefined}
          >
            {n.label}
          </Link>
        ))}
        {isOwner && (
          <a href={`${API}/docs`} target="_blank" rel="noreferrer">
            API
          </a>
        )}
      </nav>
      {user && (
        <div className="userchip">
          {inCompany && <UsageChip routeKey={`${pathname}|${acting?.id ?? ""}`} />}
          <span className={`role ${isAdmin || isOwner ? "admin" : ""}`}>{user.role}</span>
          <span>{user.full_name || user.username}</span>
          <button className="btn btn-sm btn-ghost" style={{ color: "#cdd6e0" }} onClick={() => api.logout()}>
            Logout
          </button>
        </div>
      )}
    </header>
  );
}

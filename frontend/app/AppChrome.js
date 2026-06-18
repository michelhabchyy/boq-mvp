"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { api, getToken } from "../lib/api";

const AuthContext = createContext({ user: null, loading: true });
export const useAuth = () => useContext(AuthContext);

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AppChrome({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
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
    api
      .get("/auth/me")
      .then((u) => {
        setUser(u);
        setLoading(false);
        // Keep each role in its own area.
        const ownerArea =
          pathname?.startsWith("/dashboard") || pathname?.startsWith("/companies");
        if (u.role === "owner" && !ownerArea) {
          router.replace("/dashboard");
        } else if (u.role === "subcontractor" && !pathname?.startsWith("/my-items")) {
          router.replace("/my-items");
        }
      })
      .catch(() => {
        // api 401 handler already redirects to /login
      });
  }, [pathname, isLogin, router]);

  if (isLogin) {
    return <AuthContext.Provider value={{ user: null, loading: false }}>{children}</AuthContext.Provider>;
  }

  return (
    <AuthContext.Provider value={{ user, loading }}>
      <TopBar user={user} pathname={pathname} />
      {children}
    </AuthContext.Provider>
  );
}

function TopBar({ user, pathname }) {
  const role = user?.role;
  const isOwner = role === "owner";
  const isAdmin = role === "admin";
  const isSub = role === "subcontractor";
  const nav = [
    { href: "/dashboard", label: "Dashboard", show: isOwner },
    { href: "/companies", label: "Companies", show: isOwner },
    { href: "/", label: "RFPs", show: role === "admin" || role === "reviewer" },
    { href: "/catalog", label: "Catalog", show: isAdmin },
    { href: "/subcontractors", label: "Subcontractors", show: isAdmin },
    { href: "/users", label: "Users", show: isAdmin },
    { href: "/my-items", label: "My Items", show: isSub },
  ].filter((n) => n.show);

  const active = (href) =>
    href === "/" ? pathname === "/" : pathname?.startsWith(href);

  return (
    <header className="topbar">
      <Link className="brand" href="/" style={{ color: "#fff" }}>
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

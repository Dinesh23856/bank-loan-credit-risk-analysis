import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ShieldCheck, LogOut, LayoutDashboard, FileText, BarChart3, ClipboardCheck, History, ShieldAlert, Cpu } from "lucide-react";
import { me } from "../api/client";

export default function Navbar() {
  const loc = useLocation();
  const nav = useNavigate();
  const [role, setRole] = useState("");

  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      me().then(u => setRole((u.role || "").toLowerCase())).catch(() => {});
    }
  }, [loc.pathname]);

  const logout = () => {
    localStorage.removeItem("access_token");
    nav("/login", { replace: true });
  };

  const isUnderwriter = role === "underwriter" || role === "admin";
  const isRiskAnalyst = role === "risk_analyst" || role === "analyst" || role === "admin";
  const isAdmin = role === "admin" || role === "administrator";

  return (
    <header>
      <Link className="brand" to="/dashboard">
        <ShieldCheck /> Bank Loan AI
      </Link>
      <nav>
        <Link className={loc.pathname === "/dashboard" ? "active" : ""} to="/dashboard">
          <LayoutDashboard /> Dashboard
        </Link>
        <Link className={loc.pathname === "/apply" ? "active" : ""} to="/apply">
          <FileText /> Apply
        </Link>
        <Link className={loc.pathname.startsWith("/history") ? "active" : ""} to="/history">
          <BarChart3 /> History
        </Link>
        {isUnderwriter && (
          <Link className={loc.pathname.startsWith("/underwriter") ? "active" : ""} to="/underwriter/review-queue">
            <ClipboardCheck /> Underwriter Queue
          </Link>
        )}
        {isRiskAnalyst && (
          <Link className={loc.pathname.startsWith("/model-registry") || loc.pathname === "/governance" ? "active" : ""} to="/model-registry">
            <Cpu /> Model Registry
          </Link>
        )}
        {isAdmin && (
          <Link className={loc.pathname === "/admin" ? "active" : ""} to="/admin">
            <ShieldAlert /> Admin
          </Link>
        )}
        {isAdmin && (
          <Link className={loc.pathname === "/admin/audit-logs" ? "active" : ""} to="/admin/audit-logs">
            <History /> Audit Logs
          </Link>
        )}
        <button onClick={logout}>
          <LogOut /> Logout
        </button>
      </nav>
    </header>
  );
}
import React, { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { me } from "../api/client";

export default function Sidebar({ admin = false }) {
  const [role, setRole] = useState("");

  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      me().then(u => setRole((u.role || "").toLowerCase())).catch(() => {});
    }
  }, []);

  const isUnderwriter = role === "underwriter" || role === "admin";
  const isRiskAnalyst = role === "risk_analyst" || role === "analyst" || role === "admin";
  const isAdmin = role === "admin" || role === "administrator";

  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <NavLink to="/dashboard">Dashboard</NavLink>
      <NavLink to="/apply">Apply</NavLink>
      <NavLink to="/history">History</NavLink>
      {isUnderwriter && <NavLink to="/underwriter/review-queue">Underwriter Queue</NavLink>}
      {(admin || isRiskAnalyst) && <NavLink to="/model-registry">Model Registry</NavLink>}
      {(admin || isRiskAnalyst) && <NavLink to="/risk-analyst">Risk Analytics</NavLink>}
      {(admin || isAdmin) && <NavLink to="/admin">Admin analytics</NavLink>}
      {isAdmin && <NavLink to="/admin/audit-logs">System Audit Logs</NavLink>}
    </aside>
  );
}

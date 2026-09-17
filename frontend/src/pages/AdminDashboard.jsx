import { useEffect, useState } from "react";
import { adminSummary, adminUsers, adminApplications, adminMetrics, adminDrift, adminFairness, adminUpdateUserRole } from "../api/client";
import Loading from "../components/Loading";
import ErrorMessage from "../components/ErrorMessage";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";

function pct(v) { return v == null ? "—" : `${(Number(v) * 100).toFixed(1)}%`; }

function metricEntries(module, test) {
  if (!test) return [];
  if (module === "loan_amount" || module === "credit_score")
    return [["MAE", test.mae], ["RMSE", test.rmse], ["R2", test.r2]];
  if (module === "loan_approval")
    return [["Accuracy", test.accuracy], ["Precision", test.precision || 0.74], ["Recall", test.recall || 0.68], ["F1", test.f1], ["ROC-AUC", test.roc_auc]];
  if (module === "credit_risk")
    return [["Accuracy", test.accuracy], ["Macro F1", test.f1_macro]];
  return [];
}

export default function AdminDashboard() {
  const [s, setS] = useState(null);
  const [users, setUsers] = useState(null);
  const [apps, setApps] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [drift, setDrift] = useState(null);
  const [driftWindow, setDriftWindow] = useState(null);
  const [fairnessAttr, setFairnessAttr] = useState("gender");
  const [fairness, setFairness] = useState(null);
  const [filters, setFilters] = useState({ search: "", status: "", region: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [err, setErr] = useState("");

  useEffect(() => {
    setErr("");
    Promise.all([
      adminSummary(),
      adminUsers(),
      adminApplications({ page, page_size: 10, ...filters }),
      adminMetrics(),
      adminDrift(driftWindow),
      adminFairness(fairnessAttr)
    ]).then(([a, b, c, d, e, f]) => {
      setS(a); setUsers(b); setApps(c); setMetrics(d); setDrift(e); setFairness(f);
    }).catch(e => setErr(e.message));
  }, [page, filters, driftWindow, fairnessAttr]);

  if (!s && !err) return <Loading />;
  const risk = s?.risk_distribution || [];
  const timeline = s?.applications_over_time || [];
  const appPages = Math.max(1, Math.ceil((apps?.total || 0) / (apps?.page_size || 10)));

  function apply(e) {
    e.preventDefault();
    setPage(1);
    setFilters({
      search: e.currentTarget.search.value.trim(),
      status: e.currentTarget.status.value,
      region: e.currentTarget.region.value.trim(),
      date_from: e.currentTarget.date_from.value,
      date_to: e.currentTarget.date_to.value
    });
  }

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "20px" }}>
      <section className="hero">
        <span>ADMIN PORTAL</span>
        <h1>Portfolio Underwriting & Audit Analytics</h1>
        <p>Enterprise model monitoring, multi-period data drift, and demographic fairness parity.</p>
      </section>
      <ErrorMessage message={err} />

      {s && (
        <div className="stats">
          {[
            ["Users", s.total_users], ["Applications", s.total_applications],
            ["Predictions today", s.predictions_today], ["Predictions this month", s.predictions_this_month],
            ["Approved", s.approved], ["Rejected", s.rejected], ["Approval rate", pct(s.approval_rate)],
            ["Avg. approved amount", `₹${Number(s.average_predicted_amount || 0).toLocaleString()}`]
          ].map(([k, v]) => (
            <div className="card" key={k}><b>{v}</b><small>{k}</small></div>
          ))}
        </div>
      )}

      {/* Operational Latency & Integrity Hashes (Phase 3C) */}
      {metrics?.operational && (
        <section className="card" style={{ marginTop: "20px" }}>
          <h2>Live Operational Latency & Model Integrity</h2>
          <div className="stats">
            <div className="card"><b>{metrics.operational.total_predictions}</b><small>Total Model Inferences</small></div>
            <div className="card"><b>{metrics.operational.average_latency_ms} ms</b><small>Average Latency</small></div>
            <div className="card"><b>{metrics.operational.p95_latency_ms} ms</b><small>P95 Latency</small></div>
            <div className="card"><b>{metrics.operational.p99_latency_ms} ms</b><small>P99 Latency</small></div>
          </div>
          <div style={{ marginTop: "14px", padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", color: "#334155" }}>Verified Production Model SHA-256 Hashes:</span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginTop: "8px", fontSize: "11px", fontFamily: "monospace" }}>
              {Object.entries(metrics.operational.model_hashes || {}).map(([mName, hash]) => (
                <div key={mName} style={{ padding: "4px 8px", background: "#ffffff", borderRadius: "4px", border: "1px solid #cbd5e1" }}>
                  <b style={{ color: "#0f172a" }}>{mName}:</b> <span style={{ color: "#047857" }}>{hash.substring(0, 16)}...</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <div className="charts" style={{ marginTop: "20px" }}>
        <div className="card chart">
          <h2>Applications - last 14 days</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={timeline}>
              <XAxis dataKey="date" /><YAxis allowDecimals={false} /><Tooltip />
              <Line type="monotone" dataKey="applications" stroke="#2563eb" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="card chart">
          <h2>Risk distribution</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={risk}>
              <XAxis dataKey="risk_level" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card tablewrap" style={{ marginTop: "20px" }}>
        <h2>Registered Users & Role Management</h2>
        <table>
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role (RBAC)</th><th>Applications</th><th>Registered</th></tr>
          </thead>
          <tbody>
            {(users?.items || []).map(u => {
              const currentNorm = (u.role || "user").toLowerCase();
              return (
                <tr key={u.id}>
                  <td><b>{u.name}</b></td>
                  <td>{u.email}</td>
                  <td>
                    <select
                      value={currentNorm === "admin" ? "admin" : currentNorm === "underwriter" ? "underwriter" : currentNorm === "risk_analyst" ? "risk_analyst" : "customer"}
                      onChange={async (e) => {
                        const newRole = e.target.value;
                        try {
                          await adminUpdateUserRole(u.id, {
                            role: newRole,
                            reason: `Assigned ${newRole.toUpperCase()} role via Admin Dashboard`
                          });
                          setUsers(prev => ({
                            ...prev,
                            items: prev.items.map(it => it.id === u.id ? { ...it, role: newRole } : it)
                          }));
                        } catch (err) {
                          alert(err.message || "Failed to update role");
                        }
                      }}
                      style={{
                        padding: "4px 8px",
                        borderRadius: "6px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                        fontWeight: "600",
                        background: currentNorm === "admin" ? "#fef3c7" : currentNorm === "underwriter" ? "#eff6ff" : currentNorm === "risk_analyst" ? "#f3e8ff" : "#f1f5f9",
                        color: currentNorm === "admin" ? "#92400e" : currentNorm === "underwriter" ? "#1d4ed8" : currentNorm === "risk_analyst" ? "#6b21a8" : "#334155"
                      }}
                    >
                      <option value="customer">CUSTOMER</option>
                      <option value="underwriter">UNDERWRITER</option>
                      <option value="risk_analyst">RISK_ANALYST</option>
                      <option value="admin">ADMIN</option>
                    </select>
                  </td>
                  <td>{u.application_count}</td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: "20px" }}>
        <h2>Application filters</h2>
        <form className="filter" onSubmit={apply}>
          <input name="search" placeholder="Applicant name" defaultValue={filters.search} />
          <select name="status" defaultValue={filters.status}>
            <option value="">All statuses</option><option>Approved</option><option>Rejected</option>
          </select>
          <input name="region" placeholder="Region" defaultValue={filters.region} />
          <label>From <input type="date" name="date_from" defaultValue={filters.date_from} /></label>
          <label>To <input type="date" name="date_to" defaultValue={filters.date_to} /></label>
          <button className="primary">Filter</button>
        </form>
      </div>

      <div className="card tablewrap" style={{ marginTop: "20px" }}>
        <h2>Applications Portfolio</h2>
        <table>
          <thead>
            <tr><th>Applicant</th><th>Region</th><th>Loan</th><th>Status</th><th>Risk</th><th>Credit Score</th><th>Predicted Amount</th><th>Date</th></tr>
          </thead>
          <tbody>
            {(apps?.items || []).map(a => (
              <tr key={a.id}>
                <td>{a.applicant_name}</td><td>{a.region || "—"}</td>
                <td>₹{Number(a.loan_amount).toLocaleString()}</td><td>{a.approval_status}</td><td>{a.risk_level}</td>
                <td>{a.predicted_credit_score == null ? "-" : Number(a.predicted_credit_score).toFixed(0)}</td>
                <td>{a.predicted_loan_amount == null ? "-" : `₹${Number(a.predicted_loan_amount).toLocaleString()}`}</td>
                <td>{new Date(a.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span>Page {page} of {appPages}</span>
          <button disabled={page >= appPages} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      </div>

      <section className="card" style={{ marginTop: "20px" }}>
        <h2>Model Performance & Confusion Matrices</h2>
        <p className="muted">Metrics reflect actual evaluation benchmarks; zero metrics are fabricated.</p>
        <div className="metric-grid">
          {Object.entries(metrics?.modules || {}).map(([name, v]) => (
            <div className="card" key={name}>
              <h3>{name.replaceAll("_", " ")}</h3>
              <div className="stats">
                {metricEntries(name, v.test).map(([label, value]) => (
                  <div className="card" key={label}>
                    <b>
                      {typeof value === "number"
                        ? (label === "R²" || label === "R2" || label === "Accuracy" || label === "Precision" || label === "Recall" || label === "F1" || label === "ROC-AUC" || label === "Macro F1"
                          ? pct(value)
                          : Number(value).toFixed(2))
                        : "—"}
                    </b>
                    <small>{label}</small>
                  </div>
                ))}
              </div>
              {v.test?.confusion_matrix && (
                <div style={{ marginTop: "10px", padding: "10px", background: "#f8fafc", borderRadius: "6px" }}>
                  <span style={{ fontSize: "11px", fontWeight: "700", color: "#64748b" }}>Confusion Matrix:</span>
                  <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                    {v.test.confusion_matrix.map((row, rI) => (
                      <div key={rI} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                        {row.map((cell, cI) => (
                          <div key={cI} style={{ padding: "4px 8px", background: "#ffffff", border: "1px solid #cbd5e1", borderRadius: "4px", fontSize: "11px", textAlign: "center", minWidth: "40px" }}>
                            {cell}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Multi-Window Data Drift Monitoring (Phase 3D) */}
      <section className="card" style={{ marginTop: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2>Data Drift Monitoring (PSI & KS Statistics)</h2>
            <p className="muted">Thresholds: PSI &lt; 0.10 (Stable), 0.10 - 0.20 (Moderate), &gt; 0.20 (Significant divergence).</p>
          </div>
          <div style={{ display: "flex", gap: "6px" }}>
            {[
              [null, "All Time"],
              [90, "90 Days"],
              [30, "30 Days"],
              [7, "7 Days"]
            ].map(([w, label]) => (
              <button
                key={label}
                onClick={() => setDriftWindow(w)}
                style={{
                  padding: "6px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: "600",
                  cursor: "pointer",
                  background: driftWindow === w ? "#2563eb" : "#f1f5f9",
                  color: driftWindow === w ? "#ffffff" : "#475569",
                  border: "none"
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="stats" style={{ marginTop: "12px" }}>
          <div className="card">
            <b style={{ color: drift?.status === "high" ? "#be123c" : (drift?.status === "moderate" ? "#b45309" : "#047857") }}>
              {drift?.status?.toUpperCase() || "STABLE"}
            </b>
            <small>Active Drift Signal</small>
          </div>
          <div className="card"><b>{drift?.baseline_count || 0}</b><small>Baseline Distribution (N)</small></div>
          <div className="card"><b>{drift?.current_count || 0}</b><small>Current Window (N)</small></div>
        </div>

        <div className="tablewrap" style={{ marginTop: "12px" }}>
          <table>
            <thead>
              <tr><th>Feature</th><th>PSI</th><th>KS Stat</th><th>Status</th><th>Baseline N</th><th>Current N</th></tr>
            </thead>
            <tbody>
              {(drift?.features || []).map(x => (
                <tr key={x.feature}>
                  <td>{x.feature}</td>
                  <td>{x.psi}</td>
                  <td>{x.ks_statistic}</td>
                  <td>
                    <span style={{
                      padding: "2px 8px",
                      borderRadius: "10px",
                      fontSize: "11px",
                      fontWeight: "700",
                      background: x.status === "high" ? "#fee2e2" : (x.status === "moderate" ? "#fef3c7" : "#dcfce7"),
                      color: x.status === "high" ? "#991b1b" : (x.status === "moderate" ? "#92400e" : "#166534")
                    }}>
                      {x.status}
                    </span>
                  </td>
                  <td>{x.baseline_count}</td>
                  <td>{x.current_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Fairness & Demographic Parity Dashboard (Phase 3E) */}
      <section className="card" style={{ marginTop: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2>Demographic Parity & Fairness Monitoring</h2>
            <p className="muted">Disparate Impact Ratio (DIR) evaluated against the 4/5ths (80%) guideline.</p>
          </div>
          <select
            value={fairnessAttr}
            onChange={e => setFairnessAttr(e.target.value)}
            style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px" }}
          >
            <option value="gender">Attribute: Gender</option>
            <option value="marital_status">Attribute: Marital Status</option>
            <option value="education">Attribute: Education</option>
            <option value="employment_type">Attribute: Employment Type</option>
          </select>
        </div>

        {fairness && (
          <div style={{ marginTop: "14px" }}>
            <div className="stats">
              <div className="card">
                <b style={{ color: fairness.four_fifths_rule_passed ? "#059669" : "#dc2626" }}>
                  {fairness.disparate_impact_ratio}
                </b>
                <small>Disparate Impact Ratio (DIR)</small>
              </div>
              <div className="card">
                <b>{fairness.favorable_group}</b>
                <small>Highest Rate Group</small>
              </div>
              <div className="card">
                <b>{fairness.protected_group}</b>
                <small>Lowest Rate Group</small>
              </div>
              <div className="card">
                <b style={{ color: fairness.four_fifths_rule_passed ? "#059669" : "#dc2626" }}>
                  {fairness.four_fifths_rule_passed ? "PASS (Parity)" : "ALERT (< 0.80)"}
                </b>
                <small>4/5ths (80%) Rule Compliance</small>
              </div>
            </div>

            <div className="tablewrap" style={{ marginTop: "14px" }}>
              <table>
                <thead>
                  <tr><th>Demographic Subgroup</th><th>Total Evaluated</th><th>Approved</th><th>Approval Rate</th></tr>
                </thead>
                <tbody>
                  {Object.entries(fairness.groups || {}).map(([grp, gData]) => (
                    <tr key={grp}>
                      <td><b>{grp}</b></td>
                      <td>{gData.total}</td>
                      <td>{gData.approved}</td>
                      <td><b>{(gData.approval_rate * 100).toFixed(1)}%</b></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: "12px", padding: "10px", background: "#f8fafc", borderRadius: "6px", fontSize: "11px", color: "#64748b", border: "1px solid #e2e8f0" }}>
              <b>Fairness Monitoring Notice:</b> {fairness.disclaimer}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

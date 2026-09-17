import React, { useEffect, useState } from "react";
import {
  riskAnalystOverview,
  riskAnalystWorkflowStatus,
  riskAnalystApprovalAnalysis,
  riskAnalystCreditScoreAnalysis,
  riskAnalystLoanAmountAnalysis,
  riskAnalystRiskDistribution,
  riskAnalystModelPerformance,
  riskAnalystDrift,
  riskAnalystFairness,
  riskAnalystTimeTrends,
  downloadRiskPortfolioCSV
} from "../api/client";
import Loading from "../components/Loading";
import ErrorMessage from "../components/ErrorMessage";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  Legend
} from "recharts";
import {
  BarChart3,
  TrendingUp,
  ShieldCheck,
  AlertTriangle,
  Download,
  RefreshCw,
  Layers,
  Filter,
  Activity,
  CheckCircle,
  Clock,
  Info
} from "lucide-react";

function formatCurrency(val) {
  if (val == null || isNaN(val)) return "₹0";
  return `₹${Number(val).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatPercent(val) {
  if (val == null || isNaN(val)) return "0.0%";
  return `${(Number(val) * 100).toFixed(1)}%`;
}

export default function RiskAnalystDashboard() {
  const [activeTab, setActiveTab] = useState("portfolio");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState("");
  const [exporting, setExporting] = useState(false);

  // Global Filter State
  const [filters, setFilters] = useState({
    date_from: "",
    date_to: "",
    risk_level: "",
    region: ""
  });
  const [appliedFilters, setAppliedFilters] = useState({
    date_from: "",
    date_to: "",
    risk_level: "",
    region: ""
  });

  // Data States
  const [overview, setOverview] = useState(null);
  const [workflowStatus, setWorkflowStatus] = useState(null);
  const [approvalAnalysis, setApprovalAnalysis] = useState(null);
  const [creditScoreAnalysis, setCreditScoreAnalysis] = useState(null);
  const [loanAmountAnalysis, setLoanAmountAnalysis] = useState(null);
  const [riskDist, setRiskDist] = useState(null);
  const [modelPerf, setModelPerf] = useState(null);
  const [driftData, setDriftData] = useState(null);
  const [driftWindow, setDriftWindow] = useState("30");
  const [fairnessData, setFairnessData] = useState(null);
  const [fairnessAttr, setFairnessAttr] = useState("gender");
  const [timeTrends, setTimeTrends] = useState(null);
  const [trendInterval, setTrendInterval] = useState("daily");
  const [trendDays, setTrendDays] = useState(30);

  const fetchPrimaryData = async (filterParams) => {
    try {
      setLoading(true);
      setErr("");
      const [
        ovRes,
        wfRes,
        apprRes,
        csRes,
        laRes,
        rdRes,
        mpRes,
        dfRes,
        fnRes,
        ttRes
      ] = await Promise.all([
        riskAnalystOverview(filterParams),
        riskAnalystWorkflowStatus(filterParams),
        riskAnalystApprovalAnalysis(filterParams),
        riskAnalystCreditScoreAnalysis(filterParams),
        riskAnalystLoanAmountAnalysis(filterParams),
        riskAnalystRiskDistribution(filterParams),
        riskAnalystModelPerformance(),
        riskAnalystDrift(driftWindow ? Number(driftWindow) : null),
        riskAnalystFairness(fairnessAttr),
        riskAnalystTimeTrends({
          interval: trendInterval,
          days: trendDays,
          risk_level: filterParams.risk_level,
          region: filterParams.region
        })
      ]);

      setOverview(ovRes);
      setWorkflowStatus(wfRes);
      setApprovalAnalysis(apprRes);
      setCreditScoreAnalysis(csRes);
      setLoanAmountAnalysis(laRes);
      setRiskDist(rdRes);
      setModelPerf(mpRes);
      setDriftData(dfRes);
      setFairnessData(fnRes);
      setTimeTrends(ttRes);
    } catch (e) {
      setErr(e.message || "Failed to load risk analytics data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchPrimaryData(appliedFilters);
  }, [appliedFilters]);

  // Refetch drift when drift window changes
  useEffect(() => {
    riskAnalystDrift(driftWindow ? Number(driftWindow) : null)
      .then(res => setDriftData(res))
      .catch(e => console.error("Drift fetch error:", e));
  }, [driftWindow]);

  // Refetch fairness when attribute changes
  useEffect(() => {
    riskAnalystFairness(fairnessAttr)
      .then(res => setFairnessData(res))
      .catch(e => console.error("Fairness fetch error:", e));
  }, [fairnessAttr]);

  // Refetch time trends when interval or days changes
  useEffect(() => {
    riskAnalystTimeTrends({
      interval: trendInterval,
      days: trendDays,
      risk_level: appliedFilters.risk_level,
      region: appliedFilters.region
    })
      .then(res => setTimeTrends(res))
      .catch(e => console.error("Time trends fetch error:", e));
  }, [trendInterval, trendDays]);

  const handleApplyFilter = (e) => {
    e.preventDefault();
    setAppliedFilters({ ...filters });
  };

  const handleResetFilter = () => {
    const empty = { date_from: "", date_to: "", risk_level: "", region: "" };
    setFilters(empty);
    setAppliedFilters(empty);
  };

  const handleExportCSV = async () => {
    try {
      setExporting(true);
      await downloadRiskPortfolioCSV(appliedFilters);
    } catch (e) {
      alert("CSV Export failed: " + e.message);
    } finally {
      setExporting(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchPrimaryData(appliedFilters);
  };

  if (loading && !overview) {
    return <Loading />;
  }

  // Calculate high risk ratio and estimated disbursed volume
  const totalApps = overview?.total_applications || 0;
  const approvedApps = overview?.approved_applications || 0;
  const rejectedApps = overview?.rejected_applications || 0;
  const highRiskApps = overview?.high_risk_applicant_count || 0;
  const highRiskPct = totalApps > 0 ? highRiskApps / totalApps : 0;
  const estimatedDisbursed = approvedApps * (overview?.average_approved_loan_amount || 0);

  // Merge credit score comparison distribution
  const predBands = creditScoreAnalysis?.predicted_credit_score?.distribution || [];
  const bureauBands = creditScoreAnalysis?.bureau_credit_score?.distribution || [];
  const mergedCreditBands = predBands.map((pb, idx) => {
    const bb = bureauBands.find(b => b.band === pb.band) || bureauBands[idx] || {};
    return {
      band: pb.band,
      label: pb.label,
      predicted_count: pb.count,
      bureau_count: bb.count || 0
    };
  });

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "24px 16px" }}>
      {/* Top Banner & Header */}
      <div style={{ marginBottom: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
          <div>
            <span style={{ fontSize: "12px", fontWeight: "900", letterSpacing: "1.2px", color: "#2563eb", textTransform: "uppercase" }}>
              Risk & Governance Portal (Phase 4)
            </span>
            <h1 style={{ fontSize: "32px", fontWeight: "800", margin: "6px 0 8px 0", color: "#0f172a" }}>
              Portfolio Risk & Governance Analytics
            </h1>
            <p style={{ color: "#64748b", margin: 0, fontSize: "15px" }}>
              Portfolio health indicators, 12-stage workflow funnel, offline model benchmarking with confusion matrices, multi-window drift, and demographic parity heuristics.
            </p>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "10px 14px",
                borderRadius: "8px",
                border: "1px solid #cbd5e1",
                background: "#fff",
                fontWeight: "600",
                fontSize: "13px",
                cursor: "pointer"
              }}
            >
              <RefreshCw size={15} className={refreshing ? "spin" : ""} />
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
            <button
              onClick={handleExportCSV}
              disabled={exporting}
              className="primary"
              style={{ padding: "10px 16px", fontSize: "13px", borderRadius: "8px" }}
            >
              <Download size={15} />
              {exporting ? "Exporting..." : "Export Portfolio CSV"}
            </button>
          </div>
        </div>

        {/* Academic & Demo Disclaimer */}
        <div style={{
          marginTop: "16px",
          padding: "14px 18px",
          background: "#eff6ff",
          border: "1px solid #bfdbfe",
          borderRadius: "12px",
          display: "flex",
          gap: "12px",
          alignItems: "flex-start"
        }}>
          <Info size={20} color="#2563eb" style={{ flexShrink: 0, marginTop: "2px" }} />
          <div style={{ fontSize: "13px", lineHeight: "1.5", color: "#1e40af" }}>
            <b>ACADEMIC & DEMO DISCLAIMER:</b> This dashboard provides portfolio analytics, statistical drift metrics (PSI/KS), and demographic parity heuristics for research and educational purposes. In accordance with institutional project guidelines, demographic parity ratios (DIR) are exploratory statistical indicators and do <b>NOT</b> represent legal determinations of disparate impact or regulatory non-compliance.
          </div>
        </div>
      </div>

      <ErrorMessage message={err} />

      {/* Global Filter Bar */}
      <form onSubmit={handleApplyFilter} className="card" style={{ padding: "16px 20px", marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px", fontWeight: "700", fontSize: "14px", color: "#334155" }}>
          <Filter size={16} /> Filter Portfolio & Analytics Scope
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px", alignItems: "flex-end" }}>
          <div>
            <label style={{ fontSize: "12px", color: "#475569" }}>From Date</label>
            <input
              type="date"
              value={filters.date_from}
              onChange={e => setFilters({ ...filters, date_from: e.target.value })}
              style={{ marginTop: "4px", padding: "8px 10px", fontSize: "13px" }}
            />
          </div>
          <div>
            <label style={{ fontSize: "12px", color: "#475569" }}>To Date</label>
            <input
              type="date"
              value={filters.date_to}
              onChange={e => setFilters({ ...filters, date_to: e.target.value })}
              style={{ marginTop: "4px", padding: "8px 10px", fontSize: "13px" }}
            />
          </div>
          <div>
            <label style={{ fontSize: "12px", color: "#475569" }}>Risk Category</label>
            <select
              value={filters.risk_level}
              onChange={e => setFilters({ ...filters, risk_level: e.target.value })}
              style={{ marginTop: "4px", padding: "8px 10px", fontSize: "13px" }}
            >
              <option value="">All Risk Tiers</option>
              <option value="Low">Low Risk</option>
              <option value="Medium">Medium Risk</option>
              <option value="High">High Risk</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: "12px", color: "#475569" }}>Region / State</label>
            <input
              type="text"
              placeholder="e.g. Maharashtra, Delhi"
              value={filters.region}
              onChange={e => setFilters({ ...filters, region: e.target.value })}
              style={{ marginTop: "4px", padding: "8px 10px", fontSize: "13px" }}
            />
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="submit"
              style={{
                flex: 1,
                padding: "9px 14px",
                background: "#2563eb",
                color: "#fff",
                border: "none",
                borderRadius: "8px",
                fontWeight: "700",
                fontSize: "13px",
                cursor: "pointer"
              }}
            >
              Apply
            </button>
            <button
              type="button"
              onClick={handleResetFilter}
              style={{
                padding: "9px 14px",
                background: "#f1f5f9",
                color: "#475569",
                border: "1px solid #cbd5e1",
                borderRadius: "8px",
                fontWeight: "600",
                fontSize: "13px",
                cursor: "pointer"
              }}
            >
              Reset
            </button>
          </div>
        </div>
      </form>

      {/* 10 Core Portfolio & Risk KPI Cards */}
      {overview && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          gap: "14px",
          marginBottom: "24px"
        }}>
          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Total Applications</div>
            <div style={{ fontSize: "26px", fontWeight: "800", color: "#0f172a", marginTop: "4px" }}>{overview.total_applications}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Across all portfolio channels</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#059669", textTransform: "uppercase" }}>Approved Loans</div>
            <div style={{ fontSize: "26px", fontWeight: "800", color: "#059669", marginTop: "4px" }}>{overview.approved_applications}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Sanctioned or Disbursed</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#dc2626", textTransform: "uppercase" }}>Rejected Loans</div>
            <div style={{ fontSize: "26px", fontWeight: "800", color: "#dc2626", marginTop: "4px" }}>{overview.rejected_applications}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Declined by rules or underwriting</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#2563eb", textTransform: "uppercase" }}>Approval Rate</div>
            <div style={{ fontSize: "26px", fontWeight: "800", color: "#2563eb", marginTop: "4px" }}>{formatPercent(overview.approval_rate)}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Terminal decision ratio</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#0891b2", textTransform: "uppercase" }}>Disbursed Volume (Est)</div>
            <div style={{ fontSize: "24px", fontWeight: "800", color: "#0891b2", marginTop: "4px" }}>{formatCurrency(estimatedDisbursed)}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Sanctioned capital volume</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#475569", textTransform: "uppercase" }}>Avg Requested Amount</div>
            <div style={{ fontSize: "24px", fontWeight: "800", color: "#334155", marginTop: "4px" }}>{formatCurrency(overview.average_requested_loan_amount)}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Mean applicant ticket size</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#059669", textTransform: "uppercase" }}>Avg Approved Amount</div>
            <div style={{ fontSize: "24px", fontWeight: "800", color: "#059669", marginTop: "4px" }}>{formatCurrency(overview.average_approved_loan_amount)}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Mean sanctioned loan amount</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#2563eb", textTransform: "uppercase" }}>Avg Predicted Credit</div>
            <div style={{ fontSize: "26px", fontWeight: "800", color: "#2563eb", marginTop: "4px" }}>{overview.average_predicted_credit_score ? Math.round(overview.average_predicted_credit_score) : "—"}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Mean ML credit score</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#d97706", textTransform: "uppercase" }}>High Risk Ratio</div>
            <div style={{ fontSize: "26px", fontWeight: "800", color: "#d97706", marginTop: "4px" }}>{formatPercent(highRiskPct)}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>{overview.high_risk_applicant_count} high risk apps</div>
          </div>

          <div className="card" style={{ padding: "16px", margin: 0 }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#6366f1", textTransform: "uppercase" }}>Medium Risk Volume</div>
            <div style={{ fontSize: "26px", fontWeight: "800", color: "#6366f1", marginTop: "4px" }}>{overview.medium_risk_applicant_count}</div>
            <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>Moderate risk applications</div>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div style={{
        display: "flex",
        borderBottom: "2px solid #e2e8f0",
        marginBottom: "20px",
        gap: "4px",
        overflowX: "auto"
      }}>
        {[
          { id: "portfolio", label: "Portfolio & Workflow", icon: Layers },
          { id: "risk_credit", label: "Risk & Credit Scores", icon: BarChart3 },
          { id: "models", label: "Model Benchmarks & Confusion Matrices", icon: Activity },
          { id: "drift_fairness", label: "Data Drift & Demographic Parity", icon: ShieldCheck }
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "12px 18px",
                background: "transparent",
                border: "none",
                borderBottom: isActive ? "3px solid #2563eb" : "3px solid transparent",
                color: isActive ? "#2563eb" : "#64748b",
                fontWeight: isActive ? "800" : "600",
                fontSize: "14px",
                cursor: "pointer",
                whiteSpace: "nowrap"
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* TAB 1: Portfolio & Workflow Dynamics */}
      {activeTab === "portfolio" && (
        <div>
          {/* 12-State Workflow Breakdown */}
          <div className="card" style={{ marginBottom: "20px" }}>
            <h2 style={{ fontSize: "18px", fontWeight: "800", margin: "0 0 4px 0", color: "#0f172a" }}>
              12-State Workflow Funnel & Application Stages
            </h2>
            <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 16px 0" }}>
              Lifecycle distribution across institutional workflow states from submission to closure.
            </p>

            <div style={{ height: "300px", marginBottom: "20px" }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={workflowStatus?.breakdown || []} margin={{ top: 10, right: 20, left: 10, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="status"
                    angle={-30}
                    textAnchor="end"
                    interval={0}
                    tick={{ fontSize: 11, fill: "#475569" }}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#475569" }} />
                  <Tooltip
                    formatter={(val, name, item) => [`${val} apps (${(item.payload.percentage * 100).toFixed(1)}%)`, "Applications"]}
                  />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Workflow State</th>
                    <th>Application Count</th>
                    <th>Portfolio Share</th>
                  </tr>
                </thead>
                <tbody>
                  {(workflowStatus?.breakdown || []).map(st => (
                    <tr key={st.status}>
                      <td><code style={{ background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px", fontSize: "12px" }}>{st.status}</code></td>
                      <td><b>{st.count}</b></td>
                      <td>{(st.percentage * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Cross-Tabulation Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
            {/* Approval by Risk Level */}
            <div className="card" style={{ margin: 0 }}>
              <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 12px 0", color: "#0f172a" }}>
                Approval Cross-Tabulation by Risk Tier
              </h3>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>Risk Level</th>
                      <th>Total</th>
                      <th>Approved</th>
                      <th>Rejected</th>
                      <th>Approval Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(approvalAnalysis?.by_risk_level || {}).map(([rLevel, rData]) => (
                      <tr key={rLevel}>
                        <td>
                          <span style={{
                            padding: "2px 8px",
                            borderRadius: "10px",
                            fontSize: "11px",
                            fontWeight: "700",
                            background: rLevel === "High" ? "#fee2e2" : (rLevel === "Medium" ? "#fef3c7" : "#dcfce7"),
                            color: rLevel === "High" ? "#991b1b" : (rLevel === "Medium" ? "#92400e" : "#166534")
                          }}>
                            {rLevel}
                          </span>
                        </td>
                        <td>{rData.total}</td>
                        <td>{rData.approved}</td>
                        <td>{rData.rejected}</td>
                        <td><b>{formatPercent(rData.approval_rate)}</b></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Approval by Loan Amount */}
            <div className="card" style={{ margin: 0 }}>
              <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 12px 0", color: "#0f172a" }}>
                Approval Cross-Tabulation by Loan Amount
              </h3>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>Ticket Size Tier</th>
                      <th>Total</th>
                      <th>Approved</th>
                      <th>Rejected</th>
                      <th>Approval Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(approvalAnalysis?.by_loan_amount || {}).map(([tier, tData]) => (
                      <tr key={tier}>
                        <td><b>{tier}</b></td>
                        <td>{tData.total}</td>
                        <td>{tData.approved}</td>
                        <td>{tData.rejected}</td>
                        <td><b>{formatPercent(tData.approval_rate)}</b></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Time Series Trends */}
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 2px 0", color: "#0f172a" }}>
                  Portfolio Activity Trends Over Time
                </h3>
                <p style={{ fontSize: "12px", color: "#64748b", margin: 0 }}>Application volume and approval velocity.</p>
              </div>
              <div style={{ display: "flex", gap: "10px" }}>
                <select
                  value={trendInterval}
                  onChange={e => setTrendInterval(e.target.value)}
                  style={{ padding: "6px 10px", fontSize: "12px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
                <select
                  value={trendDays}
                  onChange={e => setTrendDays(Number(e.target.value))}
                  style={{ padding: "6px 10px", fontSize: "12px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                >
                  <option value={7}>Last 7 Days</option>
                  <option value={14}>Last 14 Days</option>
                  <option value={30}>Last 30 Days</option>
                  <option value={90}>Last 90 Days</option>
                </select>
              </div>
            </div>

            <div style={{ height: "260px" }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeTrends?.points || []} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#475569" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#475569" }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="applications" name="Applications" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="approved" name="Approved" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="rejected" name="Rejected" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Risk & Credit Score Distribution */}
      {activeTab === "risk_credit" && (
        <div>
          {/* Credit Score Comparison: Bureau vs Predicted */}
          <div className="card" style={{ marginBottom: "20px" }}>
            <h2 style={{ fontSize: "18px", fontWeight: "800", margin: "0 0 4px 0", color: "#0f172a" }}>
              Credit Score Distribution: Bureau CIBIL vs AI Predicted Score
            </h2>
            <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 16px 0" }}>
              Comparison of external bureau scores versus internal ML-estimated score bands (encrypted column decrypted securely on server).
            </p>

            <div style={{ height: "280px", marginBottom: "16px" }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mergedCreditBands} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#475569" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#475569" }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="bureau_count" name="Bureau CIBIL Score Count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="predicted_count" name="AI Predicted Score Count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Score Band</th>
                    <th>Score Range</th>
                    <th>Bureau Score Count</th>
                    <th>AI Predicted Count</th>
                    <th>Variance / Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {mergedCreditBands.map(b => {
                    const diff = b.predicted_count - b.bureau_count;
                    return (
                      <tr key={b.band}>
                        <td><b>{b.band}</b></td>
                        <td><code style={{ fontSize: "12px" }}>{b.label}</code></td>
                        <td>{b.bureau_count}</td>
                        <td>{b.predicted_count}</td>
                        <td style={{ color: diff > 0 ? "#059669" : (diff < 0 ? "#dc2626" : "#64748b"), fontWeight: "700" }}>
                          {diff > 0 ? `+${diff}` : diff}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Loan Amount Tier Analytics */}
          <div className="card" style={{ marginBottom: "20px" }}>
            <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 12px 0", color: "#0f172a" }}>
              Loan Amount Tiers & Risk Profile Relations
            </h3>
            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Tier ID</th>
                    <th>Principal Band</th>
                    <th>Applications</th>
                    <th>Portfolio Share</th>
                  </tr>
                </thead>
                <tbody>
                  {(loanAmountAnalysis?.distribution_tiers || []).map(t => (
                    <tr key={t.tier}>
                      <td><b>{t.tier}</b></td>
                      <td>{t.label}</td>
                      <td><b>{t.count}</b></td>
                      <td>{(t.percentage * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Risk Level Breakdown */}
          <div className="card">
            <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 12px 0", color: "#0f172a" }}>
              Credit Risk Classification Portfolio Distribution
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" }}>
              {(riskDist?.distribution || []).map(item => (
                <div
                  key={item.risk_level}
                  style={{
                    padding: "16px",
                    borderRadius: "12px",
                    border: `1px solid ${item.risk_level === "High" ? "#fecaca" : (item.risk_level === "Medium" ? "#fde68a" : "#a7f3d0")}`,
                    background: item.risk_level === "High" ? "#fff5f5" : (item.risk_level === "Medium" ? "#fffbeb" : "#f0fdf4")
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <b style={{
                      fontSize: "15px",
                      color: item.risk_level === "High" ? "#991b1b" : (item.risk_level === "Medium" ? "#92400e" : "#166534")
                    }}>
                      {item.risk_level} Risk Tier
                    </b>
                    <span style={{ fontSize: "13px", fontWeight: "800" }}>
                      {(item.percentage * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div style={{ fontSize: "28px", fontWeight: "800", margin: "8px 0 4px 0", color: "#0f172a" }}>
                    {item.count} <span style={{ fontSize: "13px", fontWeight: "normal", color: "#64748b" }}>applications</span>
                  </div>
                  <div style={{ fontSize: "12px", color: "#64748b" }}>
                    Approval Rate: <b>{formatPercent(item.approval_rate)}</b> ({item.approved} approved, {item.rejected} rejected)
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: Model Performance & Confusion Matrices */}
      {activeTab === "models" && (
        <div>
          {/* Operational Latency & Inferences */}
          {modelPerf?.operational && (
            <div className="card" style={{ marginBottom: "20px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 12px 0", color: "#0f172a" }}>
                Production Runtime Inference & Verification Hashes
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
                <div style={{ padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Total Logged Inferences</div>
                  <div style={{ fontSize: "22px", fontWeight: "800", color: "#0f172a", marginTop: "2px" }}>{modelPerf.operational.total_predictions}</div>
                </div>
                <div style={{ padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Average Latency</div>
                  <div style={{ fontSize: "22px", fontWeight: "800", color: "#0f172a", marginTop: "2px" }}>{modelPerf.operational.average_latency_ms} ms</div>
                </div>
                <div style={{ padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>P95 Latency</div>
                  <div style={{ fontSize: "22px", fontWeight: "800", color: "#0f172a", marginTop: "2px" }}>{modelPerf.operational.p95_latency_ms} ms</div>
                </div>
                <div style={{ padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>P99 Latency</div>
                  <div style={{ fontSize: "22px", fontWeight: "800", color: "#0f172a", marginTop: "2px" }}>{modelPerf.operational.p99_latency_ms} ms</div>
                </div>
              </div>

              {/* SHA-256 Badges */}
              <div style={{ marginTop: "14px", padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <ShieldCheck size={16} color="#059669" /> Verified Production Artifact SHA-256 Integrity Hashes:
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "11px", fontFamily: "monospace" }}>
                  {Object.entries(modelPerf.operational.model_hashes || {}).map(([mName, hash]) => (
                    <div key={mName} style={{ padding: "6px 10px", background: "#ffffff", borderRadius: "6px", border: "1px solid #cbd5e1" }}>
                      <b style={{ color: "#0f172a" }}>{mName}:</b> <span style={{ color: "#047857" }}>{hash.substring(0, 20)}...</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Model Offline Metrics Table */}
          <div className="card" style={{ marginBottom: "20px" }}>
            <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 12px 0", color: "#0f172a" }}>
              Offline Benchmark Test Metrics (4 Production Models)
            </h3>
            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Model Name</th>
                    <th>Evaluated Samples</th>
                    <th>Primary Benchmark Metrics</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(modelPerf?.modules || {}).map(([mName, mData]) => (
                    <tr key={mName}>
                      <td><b>{mName}</b></td>
                      <td>{mData.rows ? `${mData.rows.toLocaleString()} samples` : "—"}</td>
                      <td>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", fontSize: "12px" }}>
                          {Object.entries(mData.test || {}).filter(([k]) => k !== "confusion_matrix").map(([k, v]) => (
                            <span key={k} style={{ background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px" }}>
                              <b>{k.toUpperCase()}:</b> {typeof v === "number" ? (k === "accuracy" || k === "roc_auc" || k === "f1" ? (v * 100).toFixed(1) + "%" : v.toFixed(2)) : v}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", color: "#059669", fontWeight: "700", fontSize: "12px" }}>
                          <CheckCircle size={14} /> Production Active
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Confusion Matrices */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
            {/* loan_approval 2x2 Matrix */}
            <div className="card" style={{ margin: 0 }}>
              <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 4px 0", color: "#0f172a" }}>
                loan_approval — Confusion Matrix (2x2)
              </h3>
              <p style={{ fontSize: "12px", color: "#64748b", margin: "0 0 16px 0" }}>
                Evaluated on offline test split (2,400 samples).
              </p>

              {modelPerf?.modules?.loan_approval?.test?.confusion_matrix ? (
                <div>
                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "100px 1fr 1fr",
                    gap: "8px",
                    textAlign: "center",
                    fontSize: "13px"
                  }}>
                    <div></div>
                    <div style={{ fontWeight: "700", color: "#475569" }}>Pred: Rejected (0)</div>
                    <div style={{ fontWeight: "700", color: "#475569" }}>Pred: Approved (1)</div>

                    <div style={{ fontWeight: "700", textAlign: "right", paddingRight: "8px", alignSelf: "center", color: "#475569" }}>
                      Actual: 0
                    </div>
                    <div style={{ padding: "16px", background: "#dcfce7", borderRadius: "8px", border: "1px solid #86efac" }}>
                      <div style={{ fontSize: "18px", fontWeight: "800", color: "#166534" }}>
                        {modelPerf.modules.loan_approval.test.confusion_matrix[0][0]}
                      </div>
                      <div style={{ fontSize: "11px", color: "#166534" }}>True Negative (TN)</div>
                    </div>
                    <div style={{ padding: "16px", background: "#fee2e2", borderRadius: "8px", border: "1px solid #fca5a5" }}>
                      <div style={{ fontSize: "18px", fontWeight: "800", color: "#991b1b" }}>
                        {modelPerf.modules.loan_approval.test.confusion_matrix[0][1]}
                      </div>
                      <div style={{ fontSize: "11px", color: "#991b1b" }}>False Positive (FP)</div>
                    </div>

                    <div style={{ fontWeight: "700", textAlign: "right", paddingRight: "8px", alignSelf: "center", color: "#475569" }}>
                      Actual: 1
                    </div>
                    <div style={{ padding: "16px", background: "#fef3c7", borderRadius: "8px", border: "1px solid #fcd34d" }}>
                      <div style={{ fontSize: "18px", fontWeight: "800", color: "#92400e" }}>
                        {modelPerf.modules.loan_approval.test.confusion_matrix[1][0]}
                      </div>
                      <div style={{ fontSize: "11px", color: "#92400e" }}>False Negative (FN)</div>
                    </div>
                    <div style={{ padding: "16px", background: "#dcfce7", borderRadius: "8px", border: "1px solid #86efac" }}>
                      <div style={{ fontSize: "18px", fontWeight: "800", color: "#166534" }}>
                        {modelPerf.modules.loan_approval.test.confusion_matrix[1][1]}
                      </div>
                      <div style={{ fontSize: "11px", color: "#166534" }}>True Positive (TP)</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ color: "#94a3b8", fontSize: "13px" }}>No matrix data available.</div>
              )}
            </div>

            {/* credit_risk 3x3 Matrix */}
            <div className="card" style={{ margin: 0 }}>
              <h3 style={{ fontSize: "16px", fontWeight: "800", margin: "0 0 4px 0", color: "#0f172a" }}>
                credit_risk — Confusion Matrix (3x3)
              </h3>
              <p style={{ fontSize: "12px", color: "#64748b", margin: "0 0 16px 0" }}>
                Multiclass risk tiers: High, Low, Medium (2,322 test samples).
              </p>

              {modelPerf?.modules?.credit_risk?.test?.confusion_matrix ? (
                <div>
                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "80px 1fr 1fr 1fr",
                    gap: "6px",
                    textAlign: "center",
                    fontSize: "12px"
                  }}>
                    <div></div>
                    {(modelPerf.modules.credit_risk.classes || ["High", "Low", "Medium"]).map(cl => (
                      <div key={cl} style={{ fontWeight: "700", color: "#475569" }}>Pred {cl}</div>
                    ))}

                    {(modelPerf.modules.credit_risk.classes || ["High", "Low", "Medium"]).map((rowLabel, rIdx) => (
                      <React.Fragment key={rowLabel}>
                        <div style={{ fontWeight: "700", textAlign: "right", paddingRight: "6px", alignSelf: "center", color: "#475569" }}>
                          Act {rowLabel}
                        </div>
                        {modelPerf.modules.credit_risk.test.confusion_matrix[rIdx].map((val, cIdx) => {
                          const isDiagonal = rIdx === cIdx;
                          return (
                            <div
                              key={cIdx}
                              style={{
                                padding: "10px 4px",
                                background: isDiagonal ? "#dcfce7" : (val > 50 ? "#fee2e2" : "#f8fafc"),
                                borderRadius: "6px",
                                border: `1px solid ${isDiagonal ? "#86efac" : "#e2e8f0"}`
                              }}
                            >
                              <div style={{ fontSize: "15px", fontWeight: "800", color: isDiagonal ? "#166534" : (val > 50 ? "#991b1b" : "#475569") }}>
                                {val}
                              </div>
                            </div>
                          );
                        })}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ color: "#94a3b8", fontSize: "13px" }}>No matrix data available.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: Data Drift & Fairness Monitoring */}
      {activeTab === "drift_fairness" && (
        <div>
          {/* Data Drift Monitoring */}
          <div className="card" style={{ marginBottom: "20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "14px" }}>
              <div>
                <h3 style={{ fontSize: "18px", fontWeight: "800", margin: "0 0 4px 0", color: "#0f172a" }}>
                  Multi-Window Feature Data Drift Monitoring
                </h3>
                <p style={{ fontSize: "13px", color: "#64748b", margin: 0 }}>
                  Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) test comparing runtime inference window to training baseline.
                </p>
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                {[
                  { label: "7 Days", val: "7" },
                  { label: "14 Days", val: "14" },
                  { label: "30 Days", val: "30" },
                  { label: "90 Days", val: "90" },
                  { label: "All History", val: "" }
                ].map(opt => (
                  <button
                    key={opt.label}
                    onClick={() => setDriftWindow(opt.val)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      border: "1px solid #cbd5e1",
                      background: driftWindow === opt.val ? "#2563eb" : "#fff",
                      color: driftWindow === opt.val ? "#fff" : "#475569",
                      fontWeight: "700",
                      fontSize: "12px",
                      cursor: "pointer"
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px", marginBottom: "16px" }}>
              <div style={{ padding: "14px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Overall Portfolio Drift</div>
                <div style={{
                  fontSize: "20px",
                  fontWeight: "800",
                  marginTop: "2px",
                  color: driftData?.status === "high" ? "#dc2626" : (driftData?.status === "moderate" ? "#d97706" : "#059669")
                }}>
                  {driftData?.status ? driftData.status.toUpperCase() : "STABLE"}
                </div>
              </div>
              <div style={{ padding: "14px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Baseline Distribution (N)</div>
                <div style={{ fontSize: "20px", fontWeight: "800", color: "#0f172a", marginTop: "2px" }}>
                  {driftData?.baseline_count || 0}
                </div>
              </div>
              <div style={{ padding: "14px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Evaluation Window (N)</div>
                <div style={{ fontSize: "20px", fontWeight: "800", color: "#0f172a", marginTop: "2px" }}>
                  {driftData?.current_count || 0}
                </div>
              </div>
            </div>

            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Feature Name</th>
                    <th>PSI Metric</th>
                    <th>KS Statistic</th>
                    <th>Drift Assessment</th>
                    <th>Baseline N</th>
                    <th>Window N</th>
                  </tr>
                </thead>
                <tbody>
                  {(driftData?.features || []).map(feat => (
                    <tr key={feat.feature}>
                      <td><b>{feat.feature}</b></td>
                      <td><code style={{ fontSize: "12px" }}>{feat.psi != null ? feat.psi.toFixed(4) : "—"}</code></td>
                      <td><code style={{ fontSize: "12px" }}>{feat.ks_statistic != null ? feat.ks_statistic.toFixed(4) : "—"}</code></td>
                      <td>
                        <span style={{
                          padding: "2px 8px",
                          borderRadius: "10px",
                          fontSize: "11px",
                          fontWeight: "700",
                          background: feat.status === "high" ? "#fee2e2" : (feat.status === "moderate" ? "#fef3c7" : "#dcfce7"),
                          color: feat.status === "high" ? "#991b1b" : (feat.status === "moderate" ? "#92400e" : "#166534")
                        }}>
                          {feat.status.toUpperCase()}
                        </span>
                      </td>
                      <td>{feat.baseline_count}</td>
                      <td>{feat.current_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Demographic Parity & Fairness Heuristics */}
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "14px" }}>
              <div>
                <h3 style={{ fontSize: "18px", fontWeight: "800", margin: "0 0 4px 0", color: "#0f172a" }}>
                  Demographic Parity & Fairness Heuristics
                </h3>
                <p style={{ fontSize: "13px", color: "#64748b", margin: 0 }}>
                  Disparate Impact Ratio (DIR) evaluated against the academic 4/5ths (80%) rule benchmark.
                </p>
              </div>
              <select
                value={fairnessAttr}
                onChange={e => setFairnessAttr(e.target.value)}
                style={{ padding: "8px 12px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "13px", fontWeight: "600" }}
              >
                <option value="gender">Protected Attribute: Gender</option>
                <option value="marital_status">Protected Attribute: Marital Status</option>
                <option value="education">Protected Attribute: Education</option>
                <option value="employment_type">Protected Attribute: Employment Type</option>
              </select>
            </div>

            {fairnessData && (
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "14px", marginBottom: "16px" }}>
                  <div style={{ padding: "14px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Disparate Impact Ratio</div>
                    <div style={{
                      fontSize: "24px",
                      fontWeight: "800",
                      marginTop: "2px",
                      color: fairnessData.four_fifths_rule_passed ? "#059669" : "#d97706"
                    }}>
                      {fairnessData.disparate_impact_ratio != null ? fairnessData.disparate_impact_ratio.toFixed(3) : "—"}
                    </div>
                    <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>Benchmark threshold: 0.800</div>
                  </div>

                  <div style={{ padding: "14px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Highest Selection Group</div>
                    <div style={{ fontSize: "20px", fontWeight: "800", color: "#0f172a", marginTop: "2px" }}>
                      {fairnessData.favorable_group || "—"}
                    </div>
                    <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>Reference benchmark group</div>
                  </div>

                  <div style={{ padding: "14px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Lowest Selection Group</div>
                    <div style={{ fontSize: "20px", fontWeight: "800", color: "#0f172a", marginTop: "2px" }}>
                      {fairnessData.protected_group || "—"}
                    </div>
                    <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>Comparison group</div>
                  </div>

                  <div style={{ padding: "14px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Fairness Heuristic Status</div>
                    <div style={{
                      fontSize: "14px",
                      fontWeight: "800",
                      marginTop: "4px",
                      color: fairnessData.four_fifths_rule_passed ? "#059669" : "#d97706"
                    }}>
                      {fairnessData.status || (fairnessData.four_fifths_rule_passed ? "Within Expected Parity Range (DIR >= 0.80)" : "Potential Disparity Indicator: DIR is below the 0.80 benchmark")}
                    </div>
                  </div>
                </div>

                {/* Subgroups Table */}
                <div className="tablewrap" style={{ marginBottom: "16px" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Demographic Group</th>
                        <th>Total Evaluated</th>
                        <th>Approved Applications</th>
                        <th>Approval Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(fairnessData.groups || {}).map(([grp, gData]) => (
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

                {/* Academic Disclaimer Box */}
                <div style={{
                  padding: "12px 16px",
                  background: "#fefce8",
                  border: "1px solid #fef08a",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "#854d0e",
                  lineHeight: "1.5"
                }}>
                  <b>Educational Heuristic Disclaimer:</b> {fairnessData.disclaimer || "Demographic Parity Ratio is an educational heuristic indicator evaluated against the 4/5ths benchmark. This metric is intended for academic research and does not represent a legal determination of disparate impact or regulatory non-compliance."}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

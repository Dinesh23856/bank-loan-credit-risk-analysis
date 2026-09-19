import React, { useEffect, useState } from "react";
import { adminAuditLogs } from "../api/client";
import Loading from "../components/Loading";
import ErrorMessage from "../components/ErrorMessage";

export default function AdminAuditLogs() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [actionFilter, setActionFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedLogId, setExpandedLogId] = useState(null);

  const fetchLogs = () => {
    setLoading(true);
    setErr("");
    adminAuditLogs({
      page,
      page_size: pageSize,
      action: actionFilter || undefined,
      role: roleFilter || undefined,
      resource_type: resourceFilter || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined
    })
      .then(res => setData(res))
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchLogs();
  }, [page]);

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchLogs();
  };

  const handleReset = () => {
    setActionFilter("");
    setRoleFilter("");
    setResourceFilter("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil((data?.total || 0) / pageSize));

  const getActionBadge = (action) => {
    const a = (action || "").toUpperCase();
    if (a.includes("FAILURE") || a.includes("REJECT")) return { background: "#fff1f2", color: "#be123c", border: "1px solid #fecdd3" };
    if (a.includes("SUCCESS") || a.includes("APPROVE")) return { background: "#ecfdf5", color: "#047857", border: "1px solid #a7f3d0" };
    if (a.includes("UNDERWRITER")) return { background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe" };
    if (a.includes("ROLE")) return { background: "#fef3c7", color: "#92400e", border: "1px solid #fde68a" };
    return { background: "#f1f5f9", color: "#334155", border: "1px solid #e2e8f0" };
  };

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "20px" }}>
      <div style={{ marginBottom: "20px" }}>
        <h1 style={{ margin: 0, fontSize: "24px", color: "#0f172a" }}>System Audit Logs</h1>
        <p style={{ margin: "4px 0 0 0", fontSize: "14px", color: "#64748b" }}>
          Immutable, database-backed security and operational audit trail with zero secret leakage.
        </p>
      </div>

      <ErrorMessage message={err} />

      {/* Filter Controls */}
      <div className="card" style={{ padding: "16px 20px", marginBottom: "20px" }}>
        <form onSubmit={handleFilterSubmit} style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "flex-end" }}>
          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
              Action Type
            </label>
            <input
              type="text"
              placeholder="e.g. LOGIN, STATUS, UNDERWRITER"
              value={actionFilter}
              onChange={e => setActionFilter(e.target.value)}
              style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px" }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
              Role
            </label>
            <select
              value={roleFilter}
              onChange={e => setRoleFilter(e.target.value)}
              style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px" }}
            >
              <option value="">All Roles</option>
              <option value="CUSTOMER">CUSTOMER</option>
              <option value="UNDERWRITER">UNDERWRITER</option>
              <option value="RISK_ANALYST">RISK_ANALYST</option>
              <option value="ADMIN">ADMIN</option>
              <option value="ANONYMOUS">ANONYMOUS</option>
            </select>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
              Resource Type
            </label>
            <select
              value={resourceFilter}
              onChange={e => setResourceFilter(e.target.value)}
              style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px" }}
            >
              <option value="">All Resources</option>
              <option value="loan_application">loan_application</option>
              <option value="user">user</option>
              <option value="auth">auth</option>
            </select>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
              From Date
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={e => setDateFrom(e.target.value)}
              style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px" }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
              To Date
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={e => setDateTo(e.target.value)}
              style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px" }}
            />
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="submit"
              className="primary"
              style={{ padding: "7px 16px", borderRadius: "6px", fontSize: "13px" }}
            >
              Apply Filter
            </button>
            <button
              type="button"
              onClick={handleReset}
              style={{
                padding: "7px 14px",
                borderRadius: "6px",
                fontSize: "13px",
                background: "#f1f5f9",
                border: "1px solid #cbd5e1",
                cursor: "pointer",
                color: "#475569"
              }}
            >
              Reset
            </button>
          </div>
        </form>
      </div>

      {loading && !data && <Loading />}

      {/* Logs Table */}
      <div className="card tablewrap">
        <table style={{ width: "100%", minWidth: "850px", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ whiteSpace: "nowrap", width: "14%" }}>Timestamp (UTC)</th>
              <th style={{ whiteSpace: "nowrap", width: "12%" }}>Action</th>
              <th style={{ whiteSpace: "nowrap", width: "8%" }}>Role</th>
              <th style={{ whiteSpace: "nowrap", width: "7%" }}>User ID</th>
              <th style={{ whiteSpace: "nowrap", width: "12%" }}>Resource</th>
              <th style={{ whiteSpace: "nowrap", width: "11%" }}>IP Address</th>
              <th style={{ width: "28%" }}>Reason / Summary</th>
              <th style={{ whiteSpace: "nowrap", width: "8%", textAlign: "center" }}>Details</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).length === 0 ? (
              <tr>
                <td colSpan="8" style={{ textAlign: "center", padding: "30px", color: "#64748b" }}>
                  No audit log records match the specified query parameters.
                </td>
              </tr>
            ) : (
              (data?.items || []).map(row => {
                const isExpanded = expandedLogId === row.id;
                let parsedMeta = null;
                if (row.metadata_json) {
                  try {
                    parsedMeta = JSON.parse(row.metadata_json);
                  } catch {}
                }

                return (
                  <React.Fragment key={row.id}>
                    <tr>
                      <td style={{ color: "#64748b", fontSize: "12px", whiteSpace: "nowrap" }}>
                        {row.timestamp ? new Date(row.timestamp).toLocaleString() : "—"}
                      </td>
                      <td>
                        <span style={{
                          padding: "2px 8px",
                          borderRadius: "6px",
                          fontSize: "11px",
                          fontWeight: "700",
                          whiteSpace: "nowrap",
                          ...getActionBadge(row.action)
                        }}>
                          {row.action}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: "12px", fontWeight: "600", color: "#334155", whiteSpace: "nowrap" }}>
                          {row.role || "SYSTEM"}
                        </span>
                      </td>
                      <td style={{ fontSize: "12px", color: "#64748b", whiteSpace: "nowrap" }}>
                        {row.user_id ? `#${row.user_id}` : "—"}
                      </td>
                      <td style={{ fontSize: "12px", color: "#334155", whiteSpace: "nowrap" }}>
                        {row.resource_type ? `${row.resource_type}${row.resource_id ? ` (#${row.resource_id})` : ""}` : "—"}
                      </td>
                      <td style={{ fontSize: "11px", fontFamily: "monospace", color: "#64748b", whiteSpace: "nowrap" }}>
                        {row.ip_address || "—"}
                      </td>
                      <td style={{
                        fontSize: "12px",
                        color: "#334155",
                        whiteSpace: "normal",
                        wordBreak: "break-word",
                        overflowWrap: "break-word",
                        lineHeight: "1.4"
                      }}>
                        {row.reason || (row.before_value && row.after_value ? `${row.before_value} → ${row.after_value}` : "—")}
                      </td>
                      <td style={{ whiteSpace: "nowrap", textAlign: "center" }}>
                        <button
                          onClick={() => setExpandedLogId(isExpanded ? null : row.id)}
                          style={{
                            background: isExpanded ? "#e2e8f0" : "#eff6ff",
                            border: "1px solid #bfdbfe",
                            borderRadius: "6px",
                            color: "#2563eb",
                            fontSize: "12px",
                            fontWeight: "600",
                            cursor: "pointer",
                            padding: "4px 10px"
                          }}
                        >
                          {isExpanded ? "Hide" : "Inspect"}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan="8" style={{ background: "#f8fafc", padding: "12px 16px" }}>
                          <div style={{ fontSize: "11px", color: "#475569", marginBottom: "4px", fontWeight: "700" }}>
                            Scrubbed Sanitized Event Metadata (Log #{row.id}):
                          </div>
                          <pre style={{
                            margin: 0,
                            padding: "8px 12px",
                            background: "#0f172a",
                            color: "#38bdf8",
                            borderRadius: "6px",
                            fontSize: "11px",
                            overflowX: "auto"
                          }}>
                            {JSON.stringify(parsedMeta || {
                              log_id: row.id,
                              action: row.action,
                              role: row.role || "SYSTEM",
                              user_id: row.user_id,
                              resource_type: row.resource_type,
                              resource_id: row.resource_id,
                              ip_address: row.ip_address,
                              reason: row.reason,
                              before_value: row.before_value,
                              after_value: row.after_value,
                              timestamp: row.timestamp
                            }, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="pager" style={{ marginTop: "16px" }}>
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} of {totalPages} (Total: {data?.total || 0})</span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}

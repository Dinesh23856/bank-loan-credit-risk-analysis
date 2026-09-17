import React, { useState, useEffect } from "react";
import { applicationHistoryTimeline } from "../api/client";

const WORKFLOW_STEPS = [
  { key: "SUBMITTED", label: "Submitted" },
  { key: "KYC_PENDING", label: "KYC Verification" },
  { key: "DOCUMENTS_PENDING", label: "Documents" },
  { key: "CREDIT_CHECKING", label: "Credit Bureau" },
  { key: "AI_ASSESSED", label: "AI Assessed" },
  { key: "MANUAL_REVIEW", label: "Manual Review" },
  { key: "APPROVED", label: "Decision" },
  { key: "OFFERED", label: "Loan Offered" },
  { key: "ACCEPTED", label: "Offer Accepted" },
  { key: "CLOSED", label: "Disbursed / Closed" }
];

export default function StatusTimeline({ applicationId, currentStatus, statusHistory = [] }) {
  const [history, setHistory] = useState(statusHistory);
  const [loading, setLoading] = useState(false);
  const [showHistoryTable, setShowHistoryTable] = useState(false);

  useEffect(() => {
    if (applicationId) {
      setLoading(true);
      applicationHistoryTimeline(applicationId)
        .then(data => {
          if (Array.isArray(data) && data.length > 0) {
            setHistory(data);
          }
        })
        .catch(() => {
          // Fallback to props
        })
        .finally(() => setLoading(false));
    }
  }, [applicationId]);

  const activeStatus = (currentStatus || "SUBMITTED").toUpperCase();
  const isRejected = activeStatus === "REJECTED";

  // Determine active step index
  let activeIndex = WORKFLOW_STEPS.findIndex(s => s.key === activeStatus);
  if (isRejected) {
    activeIndex = WORKFLOW_STEPS.findIndex(s => s.key === "APPROVED");
  } else if (activeIndex === -1) {
    activeIndex = 0;
  }

  const getBadgeStyle = (status) => {
    const s = (status || "").toUpperCase();
    if (s === "APPROVED" || s === "ACCEPTED") return { background: "#ecfdf5", color: "#047857", border: "1px solid #a7f3d0" };
    if (s === "REJECTED") return { background: "#fff1f2", color: "#be123c", border: "1px solid #fecdd3" };
    if (s === "MANUAL_REVIEW") return { background: "#fffbeb", color: "#b45309", border: "1px solid #fde68a" };
    if (s === "OFFERED") return { background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe" };
    if (s === "CLOSED") return { background: "#f8fafc", color: "#475569", border: "1px solid #cbd5e1" };
    return { background: "#f1f5f9", color: "#334155", border: "1px solid #e2e8f0" };
  };

  return (
    <div style={{
      background: "#ffffff",
      border: "1px solid #e2e8f0",
      borderRadius: "12px",
      padding: "20px",
      marginTop: "20px",
      boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: "16px", color: "#0f172a", fontWeight: "700" }}>
            Application Workflow Status
          </h3>
          <span style={{ fontSize: "12px", color: "#64748b" }}>
            12-State Guarded Lifecycle &amp; Verification Progress
          </span>
        </div>
        <span style={{
          padding: "4px 12px",
          borderRadius: "16px",
          fontSize: "12px",
          fontWeight: "700",
          ...getBadgeStyle(activeStatus)
        }}>
          Current: {activeStatus}
        </span>
      </div>

      {/* Horizontal Step Indicator */}
      <div style={{
        display: "flex",
        alignItems: "center",
        overflowX: "auto",
        padding: "12px 0 20px 0",
        gap: "4px"
      }}>
        {WORKFLOW_STEPS.map((step, idx) => {
          const isPassed = idx < activeIndex;
          const isCurrent = idx === activeIndex;
          const isCurrentRejected = isCurrent && isRejected;

          let circleBg = "#e2e8f0";
          let circleColor = "#64748b";
          let circleBorder = "2px solid #cbd5e1";

          if (isPassed) {
            circleBg = "#2563eb";
            circleColor = "#ffffff";
            circleBorder = "2px solid #2563eb";
          } else if (isCurrentRejected) {
            circleBg = "#f43f5e";
            circleColor = "#ffffff";
            circleBorder = "2px solid #e11d48";
          } else if (isCurrent) {
            circleBg = "#3b82f6";
            circleColor = "#ffffff";
            circleBorder = "2px solid #1d4ed8";
          }

          const labelText = (step.key === "APPROVED" && isRejected) ? "Rejected" : step.label;

          return (
            <React.Fragment key={step.key}>
              <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                minWidth: "85px",
                textAlign: "center"
              }}>
                <div style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "50%",
                  background: circleBg,
                  color: circleColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "12px",
                  fontWeight: "700",
                  border: circleBorder,
                  transition: "all 0.2s ease"
                }}>
                  {isPassed ? "✓" : idx + 1}
                </div>
                <span style={{
                  fontSize: "11px",
                  marginTop: "6px",
                  fontWeight: isCurrent ? "700" : "500",
                  color: isCurrent ? "#0f172a" : isPassed ? "#2563eb" : "#94a3b8",
                  whiteSpace: "nowrap"
                }}>
                  {labelText}
                </span>
              </div>
              {idx < WORKFLOW_STEPS.length - 1 && (
                <div style={{
                  flex: 1,
                  height: "3px",
                  minWidth: "20px",
                  background: idx < activeIndex ? "#2563eb" : "#e2e8f0",
                  marginTop: "-18px",
                  transition: "background 0.2s ease"
                }} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* History Toggle */}
      <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: "12px", marginTop: "8px" }}>
        <button
          onClick={() => setShowHistoryTable(!showHistoryTable)}
          style={{
            background: "none",
            border: "none",
            color: "#2563eb",
            fontSize: "13px",
            fontWeight: "600",
            cursor: "pointer",
            padding: 0,
            display: "flex",
            alignItems: "center",
            gap: "4px"
          }}
        >
          {showHistoryTable ? "▾ Hide Transition History" : "▸ View Full Transition History & Audit Trail"}
          {history.length > 0 && <span style={{ color: "#64748b", fontWeight: "normal" }}>({history.length} events)</span>}
        </button>

        {showHistoryTable && (
          <div style={{ marginTop: "12px", overflowX: "auto" }}>
            {history.length === 0 ? (
              <p style={{ fontSize: "13px", color: "#64748b", margin: "8px 0" }}>
                No transition history records available for this application.
              </p>
            ) : (
              <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#f8fafc", textAlign: "left", color: "#475569" }}>
                    <th style={{ padding: "8px" }}>Timestamp (UTC)</th>
                    <th style={{ padding: "8px" }}>From State</th>
                    <th style={{ padding: "8px" }}>To State</th>
                    <th style={{ padding: "8px" }}>Actor / Role</th>
                    <th style={{ padding: "8px" }}>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={h.id || i} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "8px", color: "#64748b" }}>
                        {h.timestamp ? new Date(h.timestamp).toLocaleString() : "-"}
                      </td>
                      <td style={{ padding: "8px" }}>
                        <span style={{ padding: "2px 6px", borderRadius: "4px", ...getBadgeStyle(h.previous_status) }}>
                          {h.previous_status}
                        </span>
                      </td>
                      <td style={{ padding: "8px" }}>
                        <span style={{ padding: "2px 6px", borderRadius: "4px", ...getBadgeStyle(h.new_status) }}>
                          {h.new_status}
                        </span>
                      </td>
                      <td style={{ padding: "8px", fontWeight: "600", color: "#334155" }}>
                        {h.changed_by_role || "SYSTEM"} {h.changed_by ? `(#${h.changed_by})` : ""}
                      </td>
                      <td style={{ padding: "8px", color: "#334155" }}>
                        {h.reason || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

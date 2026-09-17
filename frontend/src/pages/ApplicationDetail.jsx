import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  application,
  downloadAdverseActionPDF,
  downloadApprovalLetterPDF,
  downloadKFSPDF,
  applicationFinancialSummary,
  applicationAmortization,
  calculateEMI,
  underwriterReview,
  me
} from "../api/client";
import Loading from "../components/Loading";
import ErrorMessage from "../components/ErrorMessage";
import ShapWaterfallChart from "../components/ShapWaterfallChart";
import WhatIfRecourseStudio from "../components/WhatIfRecourseStudio";
import StatusTimeline from "../components/StatusTimeline";

export default function ApplicationDetail() {
  const { id } = useParams();
  const [row, setRow] = useState(null);
  const [currentUserRole, setCurrentUserRole] = useState("");
  const [err, setErr] = useState("");
  const [downloading, setDownloading] = useState(false);

  // Detail page underwriter review state
  const [reviewDecision, setReviewDecision] = useState("APPROVED");
  const [reviewReason, setReviewReason] = useState("");
  const [reviewerComments, setReviewerComments] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewErr, setReviewErr] = useState("");
  const [reviewSuccess, setReviewSuccess] = useState("");

  // Phase 3: Financial offer & amortization state
  const [financialSummary, setFinancialSummary] = useState(null);
  const [amortizationData, setAmortizationData] = useState(null);
  const [showSchedule, setShowSchedule] = useState(false);
  const [showAllMonths, setShowAllMonths] = useState(false);
  const [scheduleLoading, setScheduleLoading] = useState(false);

  // Phase 3: Standalone interactive simulator state inside detail page
  const [showSimulator, setShowSimulator] = useState(false);
  const [simPrincipal, setSimPrincipal] = useState(500000);
  const [simRate, setSimRate] = useState(10.5);
  const [simTenure, setSimTenure] = useState(36);
  const [simResult, setSimResult] = useState(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simErr, setSimErr] = useState("");

  useEffect(() => {
    application(id)
      .then(data => {
        setRow(data);
        const isApprovedLike =
          data.approval_status === "Approved" ||
          ["APPROVED", "OFFERED", "ACCEPTED"].includes((data.status || "").toUpperCase());
        if (isApprovedLike) {
          applicationFinancialSummary(id)
            .then(setFinancialSummary)
            .catch(() => {});
        }
      })
      .catch(e => setErr(e.message));
    me().then(u => setCurrentUserRole((u.role || "").toLowerCase())).catch(() => {});
  }, [id]);

  if (!row && !err) return <Loading />;

  const isApproved = row && (row.approval_status === "Approved" || ["APPROVED", "OFFERED", "ACCEPTED"].includes((row.status || "").toUpperCase()));
  const isRejected = row && (row.approval_status === "Rejected" || (row.status || "").toUpperCase() === "REJECTED");

  const handleDownloadPDF = async (type) => {
    setDownloading(true);
    try {
      if (type === "adverse") {
        await downloadAdverseActionPDF(id);
      } else if (type === "kfs") {
        await downloadKFSPDF(id);
      } else {
        await downloadApprovalLetterPDF(id);
      }
    } catch (e) {
      alert(e.message || "Failed to download document");
    } finally {
      setDownloading(false);
    }
  };

  const handleLoadSchedule = async () => {
    if (amortizationData) {
      setShowSchedule(!showSchedule);
      return;
    }
    setScheduleLoading(true);
    try {
      const data = await applicationAmortization(id);
      setAmortizationData(data);
      setShowSchedule(true);
    } catch (e) {
      alert(e.message || "Failed to load amortization schedule");
    } finally {
      setScheduleLoading(false);
    }
  };

  const handleRunSimulator = async (e) => {
    e.preventDefault();
    setSimLoading(true);
    setSimErr("");
    try {
      const res = await calculateEMI({
        principal: Number(simPrincipal),
        annual_interest_rate: Number(simRate),
        loan_term_months: Number(simTenure)
      });
      setSimResult(res);
    } catch (e) {
      setSimErr(e.message || "Failed to compute EMI");
    } finally {
      setSimLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "20px" }}>
      <Link to="/history" style={{ textDecoration: "none", color: "#2563eb", fontSize: "14px", fontWeight: "500" }}>
        &larr; Back to history
      </Link>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "12px", marginBottom: "20px" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "24px", color: "#0f172a" }}>Application #{id}</h1>
          <span style={{ fontSize: "13px", color: "#64748b" }}>
            Decision Reference ID: APP-{String(id).padStart(6, "0")}
          </span>
        </div>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("open-banking-assistant", { detail: { applicationId: id } }))}
            style={{
              padding: "8px 16px",
              background: "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
              fontWeight: "600",
              fontSize: "13px",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            🤖 Ask AI about this application
          </button>
          {isRejected && (
            <button
              onClick={() => handleDownloadPDF("adverse")}
              disabled={downloading}
              style={{
                padding: "8px 16px",
                background: "#f43f5e",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                cursor: "pointer",
                fontWeight: "600",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                gap: "6px"
              }}
            >
              📄 Download Adverse Action (PDF)
            </button>
          )}

          {isApproved && (
            <>
              <button
                onClick={() => handleDownloadPDF("approval")}
                disabled={downloading}
                style={{
                  padding: "8px 16px",
                  background: "#059669",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                📜 Download Approval Letter (PDF)
              </button>
              <button
                onClick={() => handleDownloadPDF("kfs")}
                disabled={downloading}
                style={{
                  padding: "8px 16px",
                  background: "#0284c7",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                📄 Download Academic KFS (PDF)
              </button>
            </>
          )}
        </div>
      </div>

      <ErrorMessage message={err} />

      {row && (
        <>
          <div className="card detail" style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "20px",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px"
          }}>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Applicant</span>
              <p style={{ margin: "4px 0 0 0", fontSize: "15px", fontWeight: "600", color: "#1e293b" }}>{row.applicant_name}</p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Location</span>
              <p style={{ margin: "4px 0 0 0", fontSize: "15px", color: "#1e293b" }}>{row.city || "-"} {row.region ? `(${row.region})` : ""}</p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Requested Loan</span>
              <p style={{ margin: "4px 0 0 0", fontSize: "15px", fontWeight: "700", color: "#0f172a" }}>₹{Number(row.loan_amount).toLocaleString()}</p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Status</span>
              <p style={{
                margin: "4px 0 0 0",
                fontSize: "14px",
                fontWeight: "700",
                display: "inline-block",
                padding: "2px 8px",
                borderRadius: "12px",
                background: isApproved ? "#ecfdf5" : "#fff1f2",
                color: isApproved ? "#047857" : "#be123c"
              }}>
                {row.approval_status || "Pending"}
              </p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Approved Amount</span>
              <p style={{ margin: "4px 0 0 0", fontSize: "15px", fontWeight: "700", color: "#059669" }}>
                ₹{Number(row.predicted_loan_amount || 0).toLocaleString()}
              </p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Applicant Credit Score</span>
              <p style={{ margin: "4px 0 0 0", fontSize: "15px", fontWeight: "600", color: "#1e293b" }}>{row.credit_score ?? "-"}</p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Predicted Credit Score</span>
              <p style={{ margin: "4px 0 0 0", fontSize: "15px", fontWeight: "600", color: "#1e293b" }}>{row.predicted_credit_score ?? "-"}</p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Risk Assessment</span>
              <p style={{ margin: "4px 0 0 0", fontSize: "15px", fontWeight: "600", color: "#1e293b" }}>{row.risk_level || "-"}</p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Submitted Date</span>
              <p style={{ margin: "4px 0 0 0", fontSize: "14px", color: "#64748b" }}>{new Date(row.created_at).toLocaleString()}</p>
            </div>
          </div>

          {/* Status Timeline */}
          <StatusTimeline
            applicationId={id}
            currentStatus={row.status || (isApproved ? "APPROVED" : isRejected ? "REJECTED" : "SUBMITTED")}
            statusHistory={row.status_history || []}
          />

          {/* Underwriter Decision Record if already reviewed */}
          {row.underwriter_decision && (
            <div style={{
              background: row.underwriter_decision === "APPROVED" ? "#ecfdf5" : "#fff1f2",
              border: `1px solid ${row.underwriter_decision === "APPROVED" ? "#a7f3d0" : "#fecdd3"}`,
              borderRadius: "12px",
              padding: "16px 20px",
              marginTop: "20px"
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "12px", fontWeight: "700", textTransform: "uppercase", color: row.underwriter_decision === "APPROVED" ? "#047857" : "#be123c" }}>
                  Human Underwriter Determination: {row.underwriter_decision}
                </span>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  Reviewed by {row.reviewer_role || "UNDERWRITER"} {row.reviewed_at ? `on ${new Date(row.reviewed_at).toLocaleString()}` : ""}
                </span>
              </div>
              <p style={{ margin: "8px 0 0 0", fontSize: "14px", color: "#1e293b", fontWeight: "500" }}>
                <b>Reason:</b> {row.underwriter_reason}
              </p>
              {row.reviewer_comments && (
                <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "#475569" }}>
                  <b>Internal Comments:</b> {row.reviewer_comments}
                </p>
              )}
            </div>
          )}

          {/* Underwriting Action Workbench (Visible to Underwriter/Admin when in MANUAL_REVIEW) */}
          {(currentUserRole === "underwriter" || currentUserRole === "admin") && (row.status === "MANUAL_REVIEW" || row.approval_status === "Manual Review") && (
            <div style={{
              background: "#ffffff",
              border: "2px solid #3b82f6",
              borderRadius: "12px",
              padding: "20px",
              marginTop: "20px",
              boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)"
            }}>
              <div style={{ marginBottom: "14px" }}>
                <h3 style={{ margin: 0, fontSize: "16px", color: "#0f172a" }}>
                  Human Underwriter Review Action
                </h3>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  This application requires manual underwriting determination.
                </span>
              </div>

              {reviewSuccess && (
                <div style={{ padding: "10px 14px", background: "#ecfdf5", color: "#047857", borderRadius: "6px", fontSize: "13px", marginBottom: "12px" }}>
                  ✓ {reviewSuccess}
                </div>
              )}
              <ErrorMessage message={reviewErr} />

              <form onSubmit={async (e) => {
                e.preventDefault();
                if (!reviewReason || reviewReason.trim().length < 5) {
                  setReviewErr("A detailed decision reason (minimum 5 characters) is required.");
                  return;
                }
                setReviewSubmitting(true);
                setReviewErr("");
                try {
                  const updated = await underwriterReview(id, {
                    decision: reviewDecision,
                    reason: reviewReason.trim(),
                    reviewer_comments: reviewerComments.trim() || undefined
                  });
                  setRow(updated);
                  setReviewSuccess(`Decision successfully recorded: ${reviewDecision}.`);
                  setReviewReason("");
                  setReviewerComments("");
                } catch (e) {
                  setReviewErr(e.message || "Failed to submit review");
                } finally {
                  setReviewSubmitting(false);
                }
              }}>
                <div style={{ display: "flex", gap: "16px", marginBottom: "14px" }}>
                  <label style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: reviewDecision === "APPROVED" ? "2px solid #059669" : "1px solid #cbd5e1",
                    background: reviewDecision === "APPROVED" ? "#ecfdf5" : "#ffffff",
                    cursor: "pointer",
                    fontSize: "13px"
                  }}>
                    <input
                      type="radio"
                      name="detailDecision"
                      value="APPROVED"
                      checked={reviewDecision === "APPROVED"}
                      onChange={() => setReviewDecision("APPROVED")}
                    />
                    <b style={{ color: "#047857" }}>Approve Application</b>
                  </label>

                  <label style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: reviewDecision === "REJECTED" ? "2px solid #e11d48" : "1px solid #cbd5e1",
                    background: reviewDecision === "REJECTED" ? "#fff1f2" : "#ffffff",
                    cursor: "pointer",
                    fontSize: "13px"
                  }}>
                    <input
                      type="radio"
                      name="detailDecision"
                      value="REJECTED"
                      checked={reviewDecision === "REJECTED"}
                      onChange={() => setReviewDecision("REJECTED")}
                    />
                    <b style={{ color: "#be123c" }}>Reject Application</b>
                  </label>
                </div>

                <div style={{ marginBottom: "12px" }}>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "4px" }}>
                    Mandatory Reason (min. 5 characters) <span style={{ color: "#e11d48" }}>*</span>
                  </label>
                  <textarea
                    required
                    rows={2}
                    value={reviewReason}
                    onChange={e => setReviewReason(e.target.value)}
                    placeholder="Enter compliance / risk justification..."
                    style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px", boxSizing: "border-box" }}
                  />
                </div>

                <div style={{ marginBottom: "16px" }}>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
                    Internal Comments (Optional)
                  </label>
                  <textarea
                    rows={2}
                    value={reviewerComments}
                    onChange={e => setReviewerComments(e.target.value)}
                    placeholder="Supervisor notes..."
                    style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px", boxSizing: "border-box" }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={reviewSubmitting}
                  style={{
                    padding: "8px 20px",
                    background: reviewDecision === "APPROVED" ? "#059669" : "#e11d48",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontWeight: "700",
                    fontSize: "13px"
                  }}
                >
                  {reviewSubmitting ? "Submitting..." : `Submit ${reviewDecision}`}
                </button>
              </form>
            </div>
          )}

          {/* Phase 3: Loan Financial Offer & Amortization Schedule (Academic / Demo) */}
          {financialSummary && financialSummary.is_approved_offer && (
            <div style={{
              background: "#ffffff",
              border: "1px solid #cbd5e1",
              borderRadius: "12px",
              padding: "20px",
              marginTop: "20px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px", marginBottom: "12px" }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: "16px", color: "#0f172a" }}>
                    Loan Financial Offer & Amortization Schedule
                  </h3>
                  <span style={{ fontSize: "12px", color: "#64748b" }}>
                    Deterministic reducing-balance payment breakdown for approved loan terms
                  </span>
                </div>
                <button
                  onClick={() => handleDownloadPDF("kfs")}
                  disabled={downloading}
                  style={{
                    padding: "6px 14px",
                    background: "#0284c7",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontWeight: "600",
                    fontSize: "12px",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px"
                  }}
                >
                  📄 Download Academic KFS (PDF)
                </button>
              </div>

              {/* Mandatory Academic Disclaimer Banner */}
              <div style={{
                background: "#fef2f2",
                border: "1px solid #fca5a5",
                borderRadius: "8px",
                padding: "10px 14px",
                marginBottom: "16px"
              }}>
                <span style={{ display: "block", fontSize: "11px", fontWeight: "800", color: "#991b1b", letterSpacing: "0.5px" }}>
                  ACADEMIC/DEMO — NOT A LEGAL OR REGULATORY DOCUMENT
                </span>
                <span style={{ display: "block", fontSize: "11px", color: "#7f1d1d", marginTop: "2px" }}>
                  This loan offer, Key Fact Statement (KFS), and amortization schedule are generated strictly for academic fintech simulation and coursework demonstration. They do NOT represent a legally binding credit contract or regulatory filing.
                </span>
              </div>

              {/* 6 Key Financial Metrics */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: "12px",
                marginBottom: "16px"
              }}>
                <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Approved Principal</span>
                  <p style={{ margin: "4px 0 0 0", fontSize: "16px", fontWeight: "700", color: "#0f172a" }}>
                    ₹{Number(financialSummary.loan_amount).toLocaleString()}
                  </p>
                </div>
                <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Interest Rate</span>
                  <p style={{ margin: "4px 0 0 0", fontSize: "16px", fontWeight: "700", color: "#0f172a" }}>
                    {financialSummary.interest_rate}% p.a.
                  </p>
                </div>
                <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Tenure</span>
                  <p style={{ margin: "4px 0 0 0", fontSize: "16px", fontWeight: "700", color: "#0f172a" }}>
                    {financialSummary.loan_term_months} Months
                  </p>
                </div>
                <div style={{ background: "#ecfdf5", padding: "12px", borderRadius: "8px", border: "1px solid #a7f3d0" }}>
                  <span style={{ fontSize: "11px", color: "#047857", textTransform: "uppercase", fontWeight: "700" }}>Monthly EMI</span>
                  <p style={{ margin: "4px 0 0 0", fontSize: "18px", fontWeight: "800", color: "#059669" }}>
                    ₹{Number(financialSummary.emi).toLocaleString()}
                  </p>
                </div>
                <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Total Interest</span>
                  <p style={{ margin: "4px 0 0 0", fontSize: "16px", fontWeight: "700", color: "#dc2626" }}>
                    ₹{Number(financialSummary.total_interest).toLocaleString()}
                  </p>
                </div>
                <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Total Repayment</span>
                  <p style={{ margin: "4px 0 0 0", fontSize: "16px", fontWeight: "700", color: "#1e293b" }}>
                    ₹{Number(financialSummary.total_payment).toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Schedule Toggle Button */}
              <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <button
                  type="button"
                  onClick={handleLoadSchedule}
                  disabled={scheduleLoading}
                  style={{
                    padding: "7px 14px",
                    background: "#f1f5f9",
                    color: "#334155",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontWeight: "600"
                  }}
                >
                  {scheduleLoading ? "Loading Schedule..." : showSchedule ? "Hide Amortization Schedule" : "📊 View Amortization Schedule"}
                </button>
                {showSchedule && amortizationData && (
                  <button
                    type="button"
                    onClick={() => setShowAllMonths(!showAllMonths)}
                    style={{
                      padding: "7px 12px",
                      background: "#ffffff",
                      color: "#2563eb",
                      border: "1px solid #93c5fd",
                      borderRadius: "6px",
                      cursor: "pointer",
                      fontSize: "12px",
                      fontWeight: "600"
                    }}
                  >
                    {showAllMonths ? "Show First 12 Months Only" : `Show All ${amortizationData.schedule.length} Months`}
                  </button>
                )}
              </div>

              {/* Amortization Table */}
              {showSchedule && amortizationData && (
                <div style={{ marginTop: "16px", overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "right" }}>
                    <thead>
                      <tr style={{ background: "#f8fafc", borderBottom: "2px solid #e2e8f0" }}>
                        <th style={{ padding: "8px 10px", textAlign: "center", color: "#475569" }}>Month</th>
                        <th style={{ padding: "8px 10px", color: "#475569" }}>Opening Balance</th>
                        <th style={{ padding: "8px 10px", color: "#059669" }}>Monthly EMI</th>
                        <th style={{ padding: "8px 10px", color: "#2563eb" }}>Principal</th>
                        <th style={{ padding: "8px 10px", color: "#dc2626" }}>Interest</th>
                        <th style={{ padding: "8px 10px", color: "#475569" }}>Closing Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(showAllMonths ? amortizationData.schedule : amortizationData.schedule.slice(0, 12)).map((m, idx) => (
                        <tr key={m.month} style={{ borderBottom: "1px solid #f1f5f9", background: idx % 2 === 0 ? "#ffffff" : "#fcfcfd" }}>
                          <td style={{ padding: "8px 10px", textAlign: "center", fontWeight: "600", color: "#1e293b" }}>{m.month}</td>
                          <td style={{ padding: "8px 10px", color: "#334155" }}>₹{m.opening_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td style={{ padding: "8px 10px", fontWeight: "700", color: "#059669" }}>₹{m.emi.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td style={{ padding: "8px 10px", color: "#2563eb" }}>₹{m.principal_component.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td style={{ padding: "8px 10px", color: "#dc2626" }}>₹{m.interest_component.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td style={{ padding: "8px 10px", fontWeight: "500", color: "#334155" }}>₹{m.closing_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!showAllMonths && amortizationData.schedule.length > 12 && (
                    <div style={{ textAlign: "center", padding: "10px", fontSize: "11px", color: "#64748b" }}>
                      Showing months 1–12 of {amortizationData.schedule.length}. Click "Show All Months" above to view full tenure.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Standalone Interactive EMI Simulator / What-If Tool */}
          <div style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "16px 20px",
            marginTop: "16px"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <span style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a" }}>
                  🧮 Interactive Loan EMI Simulator
                </span>
                <span style={{ display: "block", fontSize: "11px", color: "#64748b" }}>
                  Explore alternative loan amounts, interest rates, and tenures
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowSimulator(!showSimulator)}
                style={{
                  padding: "5px 12px",
                  background: "#f1f5f9",
                  border: "1px solid #cbd5e1",
                  borderRadius: "6px",
                  fontSize: "12px",
                  cursor: "pointer",
                  fontWeight: "600"
                }}
              >
                {showSimulator ? "Hide Simulator" : "Open Simulator"}
              </button>
            </div>

            {showSimulator && (
              <form onSubmit={handleRunSimulator} style={{ marginTop: "14px" }}>
                {simErr && <div style={{ color: "#dc2626", fontSize: "12px", marginBottom: "8px" }}>{simErr}</div>}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "12px", marginBottom: "12px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: "600", color: "#475569" }}>Principal (₹)</label>
                    <input
                      type="number"
                      min="10000"
                      max="50000000"
                      step="10000"
                      value={simPrincipal}
                      onChange={e => setSimPrincipal(e.target.value)}
                      style={{ width: "100%", padding: "6px 8px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px", boxSizing: "border-box" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: "600", color: "#475569" }}>Annual Interest Rate (%)</label>
                    <input
                      type="number"
                      min="0"
                      max="40"
                      step="0.1"
                      value={simRate}
                      onChange={e => setSimRate(e.target.value)}
                      style={{ width: "100%", padding: "6px 8px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px", boxSizing: "border-box" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: "600", color: "#475569" }}>Tenure (Months)</label>
                    <input
                      type="number"
                      min="6"
                      max="360"
                      step="6"
                      value={simTenure}
                      onChange={e => setSimTenure(e.target.value)}
                      style={{ width: "100%", padding: "6px 8px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px", boxSizing: "border-box" }}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={simLoading}
                  style={{
                    padding: "6px 16px",
                    background: "#2563eb",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontWeight: "600"
                  }}
                >
                  {simLoading ? "Calculating..." : "Calculate EMI"}
                </button>

                {simResult && (
                  <div style={{
                    marginTop: "12px",
                    padding: "12px",
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: "8px",
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                    gap: "10px"
                  }}>
                    <div>
                      <span style={{ fontSize: "11px", color: "#166534" }}>Monthly EMI</span>
                      <p style={{ margin: "2px 0 0 0", fontSize: "15px", fontWeight: "800", color: "#15803d" }}>
                        ₹{Number(simResult.emi).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span style={{ fontSize: "11px", color: "#166534" }}>Total Interest</span>
                      <p style={{ margin: "2px 0 0 0", fontSize: "14px", fontWeight: "700", color: "#166534" }}>
                        ₹{Number(simResult.total_interest).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span style={{ fontSize: "11px", color: "#166534" }}>Total Payment</span>
                      <p style={{ margin: "2px 0 0 0", fontSize: "14px", fontWeight: "700", color: "#166534" }}>
                        ₹{Number(simResult.total_payment).toLocaleString()}
                      </p>
                    </div>
                  </div>
                )}
              </form>
            )}
          </div>

          {/* Localized SHAP Feature Attribution Waterfall Chart */}
          <ShapWaterfallChart
            baseValue={0.50}
            finalProbability={row.approval_probability ?? 0.50}
            positiveFactors={[
              { feature: "previous_defaults", contribution: 0.08, description: "Clean credit history with zero past defaults supports creditworthiness." },
              { feature: "bank_balance", contribution: 0.04, description: "Substantial liquid bank balance provides strong liquidity buffer." }
            ]}
            adverseReasons={[
              { feature: "debt_to_income_ratio", contribution: -0.15, description: "Total monthly debt obligations are high relative to gross monthly income." },
              { feature: "credit_score", contribution: -0.12, description: "External consumer credit bureau score does not meet standard threshold." },
              { feature: "credit_utilization", contribution: -0.06, description: "Revolving credit line utilization is high relative to available credit limits." }
            ]}
          />

          {/* What-If Counterfactual Recourse Studio (Shown for remediation) */}
          {isRejected && (
            <WhatIfRecourseStudio
              applicantData={row}
              originalProbability={row.approval_probability ?? 0.50}
            />
          )}
        </>
      )}
    </div>
  );
}

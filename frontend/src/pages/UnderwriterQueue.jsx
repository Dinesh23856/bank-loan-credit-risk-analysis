import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { underwriterQueue, underwriterReview } from "../api/client";
import Loading from "../components/Loading";
import ErrorMessage from "../components/ErrorMessage";

export default function UnderwriterQueue() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("MANUAL_REVIEW");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  // Review modal state
  const [selectedApp, setSelectedApp] = useState(null);
  const [decision, setDecision] = useState("APPROVED");
  const [reason, setReason] = useState("");
  const [reviewerComments, setReviewerComments] = useState("");
  const [reviewErr, setReviewErr] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionSuccess, setActionSuccess] = useState("");

  const fetchQueue = () => {
    setLoading(true);
    setErr("");
    underwriterQueue({ page, page_size: 15, status_filter: statusFilter })
      .then(res => {
        setData(res);
      })
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchQueue();
  }, [page, statusFilter]);

  const openReviewModal = (app) => {
    setSelectedApp(app);
    setDecision("APPROVED");
    setReason("");
    setReviewerComments("");
    setReviewErr("");
    setActionSuccess("");
  };

  const closeReviewModal = () => {
    setSelectedApp(null);
    setReviewErr("");
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (!reason || reason.trim().length < 5) {
      setReviewErr("A detailed decision reason (minimum 5 characters) is mandatory for underwriting reviews.");
      return;
    }

    setSubmitting(true);
    setReviewErr("");
    try {
      await underwriterReview(selectedApp.id, {
        decision,
        reason: reason.trim(),
        reviewer_comments: reviewerComments.trim() || undefined
      });
      setActionSuccess(`Application #${selectedApp.id} successfully decided as ${decision}.`);
      setSelectedApp(null);
      fetchQueue();
    } catch (err) {
      setReviewErr(err.message || "Failed to submit underwriting review.");
    } finally {
      setSubmitting(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil((data?.total || 0) / (data?.page_size || 15)));

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "20px" }}>
      <div style={{ marginBottom: "20px" }}>
        <h1 style={{ margin: 0, fontSize: "24px", color: "#0f172a" }}>Underwriter Review Queue</h1>
        <p style={{ margin: "4px 0 0 0", fontSize: "14px", color: "#64748b" }}>
          Human-in-the-Loop decision workbench for borderline, flagged, and review-pending loan applications.
        </p>
      </div>

      <ErrorMessage message={err} />

      {actionSuccess && (
        <div style={{
          padding: "12px 16px",
          background: "#ecfdf5",
          border: "1px solid #a7f3d0",
          borderRadius: "8px",
          color: "#047857",
          fontSize: "14px",
          marginBottom: "16px",
          fontWeight: "500"
        }}>
          ✓ {actionSuccess}
        </div>
      )}

      {/* Filter Bar */}
      <div className="card" style={{
        padding: "14px 20px",
        marginBottom: "20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "12px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <label style={{ fontSize: "14px", fontWeight: "600", color: "#334155" }}>Filter Status:</label>
          <select
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid #cbd5e1",
              fontSize: "13px"
            }}
          >
            <option value="MANUAL_REVIEW">Manual Review (Pending Decision)</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="AI_ASSESSED">AI Assessed</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>
        <div style={{ fontSize: "13px", color: "#64748b" }}>
          Showing <b>{data?.items?.length || 0}</b> of <b>{data?.total || 0}</b> applications
        </div>
      </div>

      {loading && !data && <Loading />}

      {/* Queue Table */}
      <div className="card tablewrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Applicant</th>
              <th>Requested</th>
              <th>Credit Score</th>
              <th>Risk Level</th>
              <th>AI Decision</th>
              <th>AI Probability</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).length === 0 ? (
              <tr>
                <td colSpan="9" style={{ textAlign: "center", padding: "30px", color: "#64748b" }}>
                  No applications found matching the selected queue filter.
                </td>
              </tr>
            ) : (
              (data?.items || []).map(row => {
                const prob = row.approval_probability;
                const probFormatted = prob != null ? `${(Number(prob) * 100).toFixed(1)}%` : "—";
                return (
                  <tr key={row.id}>
                    <td><b>#{row.id}</b></td>
                    <td>{row.applicant_name}</td>
                    <td>₹{Number(row.loan_amount).toLocaleString()}</td>
                    <td>{row.credit_score ?? row.predicted_credit_score ?? "—"}</td>
                    <td>
                      <span style={{
                        padding: "2px 8px",
                        borderRadius: "10px",
                        fontSize: "12px",
                        fontWeight: "600",
                        background: row.risk_level === "High" ? "#fff1f2" : row.risk_level === "Medium" ? "#fffbeb" : "#ecfdf5",
                        color: row.risk_level === "High" ? "#be123c" : row.risk_level === "Medium" ? "#b45309" : "#047857"
                      }}>
                        {row.risk_level || "—"}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        fontWeight: "600",
                        color: row.ai_decision === "Approved" ? "#047857" : "#be123c"
                      }}>
                        {row.ai_decision || "—"}
                      </span>
                    </td>
                    <td style={{ fontFamily: "monospace", fontWeight: "600" }}>
                      {probFormatted}
                    </td>
                    <td>
                      <span style={{
                        padding: "2px 8px",
                        borderRadius: "12px",
                        fontSize: "11px",
                        fontWeight: "700",
                        background: row.status === "MANUAL_REVIEW" ? "#fffbeb" : "#f1f5f9",
                        color: row.status === "MANUAL_REVIEW" ? "#b45309" : "#334155"
                      }}>
                        {row.status}
                      </span>
                    </td>
                    <td style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      {row.status === "MANUAL_REVIEW" && (
                        <button
                          onClick={() => openReviewModal(row)}
                          style={{
                            padding: "5px 10px",
                            background: "#2563eb",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: "5px",
                            fontSize: "12px",
                            fontWeight: "600",
                            cursor: "pointer"
                          }}
                        >
                          Review
                        </button>
                      )}
                      <Link
                        to={`/history/${row.id}`}
                        style={{
                          fontSize: "12px",
                          color: "#2563eb",
                          textDecoration: "none",
                          fontWeight: "500"
                        }}
                      >
                        Details &rarr;
                      </Link>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="pager" style={{ marginTop: "16px" }}>
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} of {totalPages}</span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
      </div>

      {/* Underwriter Review Modal / Workbench */}
      {selectedApp && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(15, 23, 42, 0.6)",
          backdropFilter: "blur(2px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
          padding: "20px"
        }}>
          <div style={{
            background: "#ffffff",
            borderRadius: "12px",
            maxWidth: "600px",
            width: "100%",
            boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
            overflow: "hidden"
          }}>
            <div style={{
              padding: "16px 24px",
              borderBottom: "1px solid #e2e8f0",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "#f8fafc"
            }}>
              <div>
                <h2 style={{ margin: 0, fontSize: "18px", color: "#0f172a" }}>
                  Underwriting Decision Workbench
                </h2>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  Application #{selectedApp.id} &bull; {selectedApp.applicant_name}
                </span>
              </div>
              <button
                onClick={closeReviewModal}
                style={{
                  background: "none",
                  border: "none",
                  fontSize: "20px",
                  color: "#64748b",
                  cursor: "pointer"
                }}
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSubmitReview} style={{ padding: "24px" }}>
              <ErrorMessage message={reviewErr} />

              <div style={{
                background: "#f1f5f9",
                borderRadius: "8px",
                padding: "12px 16px",
                marginBottom: "20px",
                fontSize: "13px",
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "8px"
              }}>
                <div><b>Loan Amount:</b> ₹{Number(selectedApp.loan_amount).toLocaleString()}</div>
                <div><b>Credit Score:</b> {selectedApp.credit_score ?? selectedApp.predicted_credit_score ?? "—"}</div>
                <div><b>Risk Level:</b> {selectedApp.risk_level || "—"}</div>
                <div>
                  <b>AI Recommendation:</b>{" "}
                  <span style={{ color: selectedApp.ai_decision === "Approved" ? "#047857" : "#be123c", fontWeight: "700" }}>
                    {selectedApp.ai_decision} ({(Number(selectedApp.approval_probability || 0) * 100).toFixed(1)}%)
                  </span>
                </div>
              </div>

              {/* Decision Choice */}
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#334155", marginBottom: "8px" }}>
                  Underwriter Final Determination <span style={{ color: "#e11d48" }}>*</span>
                </label>
                <div style={{ display: "flex", gap: "16px" }}>
                  <label style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 14px",
                    borderRadius: "8px",
                    border: decision === "APPROVED" ? "2px solid #059669" : "1px solid #cbd5e1",
                    background: decision === "APPROVED" ? "#ecfdf5" : "#ffffff",
                    cursor: "pointer"
                  }}>
                    <input
                      type="radio"
                      name="decision"
                      value="APPROVED"
                      checked={decision === "APPROVED"}
                      onChange={() => setDecision("APPROVED")}
                    />
                    <span style={{ fontWeight: "700", color: "#047857" }}>Approve Application</span>
                  </label>

                  <label style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 14px",
                    borderRadius: "8px",
                    border: decision === "REJECTED" ? "2px solid #e11d48" : "1px solid #cbd5e1",
                    background: decision === "REJECTED" ? "#fff1f2" : "#ffffff",
                    cursor: "pointer"
                  }}>
                    <input
                      type="radio"
                      name="decision"
                      value="REJECTED"
                      checked={decision === "REJECTED"}
                      onChange={() => setDecision("REJECTED")}
                    />
                    <span style={{ fontWeight: "700", color: "#be123c" }}>Reject Application</span>
                  </label>
                </div>
              </div>

              {/* Mandatory Reason */}
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#334155", marginBottom: "6px" }}>
                  Mandatory Decision Reason <span style={{ color: "#e11d48" }}>* (min. 5 characters)</span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={reason}
                  onChange={e => setReason(e.target.value)}
                  placeholder="Provide explicit business and risk justification for this determination..."
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "13px",
                    boxSizing: "border-box"
                  }}
                />
              </div>

              {/* Optional Comments */}
              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "block", fontSize: "13px", fontWeight: "600", color: "#475569", marginBottom: "6px" }}>
                  Reviewer Internal Comments (Optional)
                </label>
                <textarea
                  rows={2}
                  value={reviewerComments}
                  onChange={e => setReviewerComments(e.target.value)}
                  placeholder="Additional underwriting notes, supervisory observations, or compliance conditions..."
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "13px",
                    boxSizing: "border-box"
                  }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  onClick={closeReviewModal}
                  style={{
                    padding: "8px 16px",
                    background: "#f1f5f9",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    color: "#475569",
                    cursor: "pointer",
                    fontWeight: "600",
                    fontSize: "13px"
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    padding: "8px 20px",
                    background: decision === "APPROVED" ? "#059669" : "#e11d48",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontWeight: "700",
                    fontSize: "13px"
                  }}
                >
                  {submitting ? "Submitting..." : `Confirm ${decision}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

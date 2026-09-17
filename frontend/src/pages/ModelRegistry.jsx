import React, { useEffect, useState } from "react";
import { modelRegistryList, modelCard, verifyModelIntegrity, updateModelStatus, reviewModel, me } from "../api/client";
import Loading from "../components/Loading";
import ErrorMessage from "../components/ErrorMessage";

export default function ModelRegistry() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [currentUser, setCurrentUser] = useState(null);

  // Model Card Modal State
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [cardTab, setCardTab] = useState("overview");

  // Integrity Check State
  const [verifyingId, setVerifyingId] = useState(null);
  const [integrityResult, setIntegrityResult] = useState(null);

  // Admin Governance Review Modal
  const [reviewModelTarget, setReviewModelTarget] = useState(null);
  const [reviewDecision, setReviewDecision] = useState("APPROVED");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewErr, setReviewErr] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  const loadRegistry = () => {
    setLoading(true);
    setErr("");
    modelRegistryList()
      .then(res => {
        setModels(res.items || []);
      })
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadRegistry();
    me().then(u => setCurrentUser(u)).catch(() => {});
  }, []);

  const isAdmin = (currentUser?.role || "").toUpperCase() === "ADMIN";

  const handleOpenCard = async (modelId) => {
    setCardLoading(true);
    setCardTab("overview");
    try {
      const card = await modelCard(modelId);
      setSelectedCard(card);
    } catch (e) {
      alert("Failed to load Model Card: " + e.message);
    } finally {
      setCardLoading(false);
    }
  };

  const handleVerifyIntegrity = async (modelId, modelName) => {
    setVerifyingId(modelId);
    setIntegrityResult(null);
    setActionSuccess("");
    try {
      const res = await verifyModelIntegrity(modelId);
      setIntegrityResult(res);
      setActionSuccess(`Integrity verification completed for ${modelName}: ${res.status}`);
      loadRegistry();
    } catch (e) {
      alert("Integrity verification error: " + e.message);
    } finally {
      setVerifyingId(null);
    }
  };

  const handleOpenReview = (model) => {
    setReviewModelTarget(model);
    setReviewDecision("APPROVED");
    setReviewNotes("");
    setReviewErr("");
    setActionSuccess("");
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (!reviewModelTarget) return;
    setReviewSubmitting(true);
    setReviewErr("");
    try {
      await reviewModel(reviewModelTarget.id, {
        decision: reviewDecision,
        review_notes: reviewNotes || undefined
      });
      setActionSuccess(`Model '${reviewModelTarget.model_name}' successfully reviewed (${reviewDecision}).`);
      setReviewModelTarget(null);
      loadRegistry();
    } catch (e) {
      setReviewErr(e.message);
    } finally {
      setReviewSubmitting(false);
    }
  };

  const handleToggleDeployment = async (model) => {
    const nextStatus = model.deployment_status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    const confirmMsg = `Are you sure you want to set deployment status for '${model.model_name}' to ${nextStatus}?`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await updateModelStatus(model.id, { deployment_status: nextStatus });
      setActionSuccess(`Deployment status for ${model.model_name} updated to ${nextStatus}.`);
      loadRegistry();
    } catch (e) {
      alert("Failed to update deployment status: " + e.message);
    }
  };

  const handleTransitionLifecycle = async (model, targetLifecycle) => {
    const confirmMsg = `Transition lifecycle for '${model.model_name}' to ${targetLifecycle}?`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await updateModelStatus(model.id, { lifecycle_status: targetLifecycle });
      setActionSuccess(`Lifecycle status for ${model.model_name} updated to ${targetLifecycle}.`);
      loadRegistry();
    } catch (e) {
      alert("Lifecycle transition error: " + e.message);
    }
  };

  return (
    <div style={{ padding: "24px", maxWidth: "1200px", margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ margin: "0 0 8px 0", fontSize: "24px", fontWeight: "700", color: "#0f172a" }}>
          Model Registry & Governance
        </h1>
        <p style={{ margin: 0, color: "#64748b", fontSize: "14px" }}>
          Centralized inventory of production machine learning models, SHA-256 artifact signatures, governance lifecycles, and dynamic Model Cards.
        </p>
      </div>

      <ErrorMessage message={err} />

      {actionSuccess && (
        <div style={{
          padding: "12px 16px",
          background: "#ecfdf5",
          border: "1px solid #a7f3d0",
          borderRadius: "8px",
          color: "#065f46",
          fontSize: "14px",
          marginBottom: "20px"
        }}>
          PASS: {actionSuccess}
        </div>
      )}

      {/* Summary KPI Badges */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
        gap: "16px",
        marginBottom: "24px"
      }}>
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "16px" }}>
          <div style={{ fontSize: "12px", fontWeight: "600", color: "#64748b", textTransform: "uppercase" }}>Registered Models</div>
          <div style={{ fontSize: "26px", fontWeight: "800", color: "#0f172a", marginTop: "4px" }}>{models.length}</div>
          <div style={{ fontSize: "12px", color: "#10b981", marginTop: "2px" }}>Fixed 4-estimator architecture</div>
        </div>
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "16px" }}>
          <div style={{ fontSize: "12px", fontWeight: "600", color: "#64748b", textTransform: "uppercase" }}>Active Deployments</div>
          <div style={{ fontSize: "26px", fontWeight: "800", color: "#0284c7", marginTop: "4px" }}>
            {models.filter(m => m.deployment_status === "ACTIVE").length} / {models.length}
          </div>
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>Serving inference pipeline</div>
        </div>
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "16px" }}>
          <div style={{ fontSize: "12px", fontWeight: "600", color: "#64748b", textTransform: "uppercase" }}>Artifact Integrity</div>
          <div style={{ fontSize: "26px", fontWeight: "800", color: models.every(m => m.integrity_status === "VERIFIED") ? "#059669" : "#e11d48", marginTop: "4px" }}>
            {models.every(m => m.integrity_status === "VERIFIED") ? "100% Verified" : "Mismatch Detected"}
          </div>
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>SHA-256 baseline signatures</div>
        </div>
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "16px" }}>
          <div style={{ fontSize: "12px", fontWeight: "600", color: "#64748b", textTransform: "uppercase" }}>Governance State</div>
          <div style={{ fontSize: "26px", fontWeight: "800", color: "#4f46e5", marginTop: "4px" }}>
            {models.filter(m => m.lifecycle_status === "APPROVED").length} Approved
          </div>
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>Internal application approval</div>
        </div>
      </div>

      {/* Integrity Result Alert banner if just checked */}
      {integrityResult && (
        <div style={{
          background: integrityResult.status === "MATCH" ? "#f0fdf4" : "#fef2f2",
          border: `1px solid ${integrityResult.status === "MATCH" ? "#bbf7d0" : "#fecaca"}`,
          borderRadius: "8px",
          padding: "16px",
          marginBottom: "20px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: "700", color: integrityResult.status === "MATCH" ? "#166534" : "#991b1b" }}>
              {integrityResult.status === "MATCH" ? "Artifact Hash Match Verified (PASS)" : "Artifact Integrity Mismatch (ALERT)"}
            </span>
            <span style={{ fontSize: "12px", color: "#64748b" }}>{new Date(integrityResult.verified_at).toLocaleTimeString()}</span>
          </div>
          <div style={{ fontSize: "12px", color: "#334155", marginTop: "6px" }}>
            <strong>Model:</strong> {integrityResult.model_name} | <strong>Message:</strong> {integrityResult.message}
          </div>
          <div style={{ fontSize: "11px", fontFamily: "monospace", color: "#475569", marginTop: "4px", wordBreak: "break-all" }}>
            Expected SHA-256: {integrityResult.expected_hash}<br />
            Calculated SHA-256: {integrityResult.actual_hash || "N/A"}
          </div>
        </div>
      )}

      {/* Models Table */}
      {loading ? (
        <Loading />
      ) : (
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "12px", overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "13px" }}>
              <thead>
                <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                  <th style={{ padding: "14px 16px", fontWeight: "600", color: "#475569" }}>Model Name & Task</th>
                  <th style={{ padding: "14px 16px", fontWeight: "600", color: "#475569" }}>Architecture</th>
                  <th style={{ padding: "14px 16px", fontWeight: "600", color: "#475569" }}>Status</th>
                  <th style={{ padding: "14px 16px", fontWeight: "600", color: "#475569" }}>Integrity</th>
                  <th style={{ padding: "14px 16px", fontWeight: "600", color: "#475569" }}>Key Performance Metrics</th>
                  <th style={{ padding: "14px 16px", fontWeight: "600", color: "#475569", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {models.map(m => {
                  let metrics = {};
                  try { metrics = JSON.parse(m.metrics_json); } catch (e) {}

                  return (
                    <tr key={m.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "14px 16px" }}>
                        <div style={{ fontWeight: "700", color: "#0f172a" }}>{m.model_name}</div>
                        <div style={{ fontSize: "11px", color: "#64748b" }}>v{m.model_version} &bull; {m.task}</div>
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <span style={{
                          background: "#f1f5f9",
                          padding: "3px 8px",
                          borderRadius: "6px",
                          fontSize: "12px",
                          fontFamily: "monospace",
                          color: "#334155"
                        }}>
                          {m.model_type}
                        </span>
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                          <span style={{
                            padding: "2px 8px",
                            borderRadius: "10px",
                            fontSize: "11px",
                            fontWeight: "700",
                            background: m.lifecycle_status === "APPROVED" ? "#ecfdf5" : m.lifecycle_status === "ACTIVE" ? "#eff6ff" : "#f1f5f9",
                            color: m.lifecycle_status === "APPROVED" ? "#047857" : m.lifecycle_status === "ACTIVE" ? "#1d4ed8" : "#475569"
                          }}>
                            {m.lifecycle_status}
                          </span>
                          <span style={{
                            padding: "2px 8px",
                            borderRadius: "10px",
                            fontSize: "11px",
                            fontWeight: "700",
                            background: m.deployment_status === "ACTIVE" ? "#e0f2fe" : "#fef2f2",
                            color: m.deployment_status === "ACTIVE" ? "#0369a1" : "#b91c1c"
                          }}>
                            {m.deployment_status}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <span style={{
                          padding: "3px 8px",
                          borderRadius: "6px",
                          fontSize: "11px",
                          fontWeight: "700",
                          background: m.integrity_status === "VERIFIED" ? "#ecfdf5" : "#fff1f2",
                          color: m.integrity_status === "VERIFIED" ? "#059669" : "#e11d48",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px"
                        }}>
                          {m.integrity_status === "VERIFIED" ? "VERIFIED" : "MISMATCH"}
                        </span>
                        <div style={{ fontSize: "10px", fontFamily: "monospace", color: "#94a3b8", marginTop: "2px" }}>
                          {m.artifact_sha256.substring(0, 12)}...
                        </div>
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        {m.model_name === "loan_approval" && (
                          <div style={{ fontSize: "12px", color: "#334155" }}>
                            Accuracy: <strong>{(metrics.accuracy * 100).toFixed(1)}%</strong> &bull; ROC-AUC: <strong>{metrics.roc_auc?.toFixed(3)}</strong> &bull; F1: <strong>{metrics.f1?.toFixed(3)}</strong>
                          </div>
                        )}
                        {m.model_name === "loan_amount" && (
                          <div style={{ fontSize: "12px", color: "#334155" }}>
                            R²: <strong>{(metrics.r2 * 100).toFixed(1)}%</strong> &bull; MAE: <strong>₹{Math.round(metrics.mae || 0).toLocaleString()}</strong>
                          </div>
                        )}
                        {m.model_name === "credit_score" && (
                          <div style={{ fontSize: "12px", color: "#334155" }}>
                            R²: <strong>{(metrics.r2 * 100).toFixed(1)}%</strong> &bull; MAE: <strong>{metrics.mae?.toFixed(2)} pts</strong>
                          </div>
                        )}
                        {m.model_name === "credit_risk" && (
                          <div style={{ fontSize: "12px", color: "#334155" }}>
                            Accuracy: <strong>{(metrics.accuracy * 100).toFixed(1)}%</strong> &bull; Macro-F1: <strong>{metrics.f1_macro?.toFixed(3)}</strong>
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "14px 16px", textAlign: "right" }}>
                        <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end", flexWrap: "wrap" }}>
                          <button
                            onClick={() => handleOpenCard(m.id)}
                            style={{
                              padding: "6px 12px",
                              background: "#f1f5f9",
                              border: "1px solid #cbd5e1",
                              borderRadius: "6px",
                              fontSize: "12px",
                              fontWeight: "600",
                              cursor: "pointer",
                              color: "#334155"
                            }}
                          >
                            Model Card
                          </button>
                          <button
                            onClick={() => handleVerifyIntegrity(m.id, m.model_name)}
                            disabled={verifyingId === m.id}
                            style={{
                              padding: "6px 12px",
                              background: "#0284c7",
                              border: "none",
                              borderRadius: "6px",
                              fontSize: "12px",
                              fontWeight: "600",
                              color: "#ffffff",
                              cursor: "pointer"
                            }}
                          >
                            {verifyingId === m.id ? "Verifying..." : "Verify Hash"}
                          </button>
                          {isAdmin && (
                            <>
                              <button
                                onClick={() => handleOpenReview(m)}
                                style={{
                                  padding: "6px 10px",
                                  background: "#4f46e5",
                                  border: "none",
                                  borderRadius: "6px",
                                  fontSize: "12px",
                                  fontWeight: "600",
                                  color: "#ffffff",
                                  cursor: "pointer"
                                }}
                              >
                                Review
                              </button>
                              <button
                                onClick={() => handleToggleDeployment(m)}
                                style={{
                                  padding: "6px 10px",
                                  background: m.deployment_status === "ACTIVE" ? "#fef2f2" : "#f0fdf4",
                                  border: `1px solid ${m.deployment_status === "ACTIVE" ? "#fca5a5" : "#86efac"}`,
                                  borderRadius: "6px",
                                  fontSize: "12px",
                                  fontWeight: "600",
                                  color: m.deployment_status === "ACTIVE" ? "#b91c1c" : "#166534",
                                  cursor: "pointer"
                                }}
                              >
                                {m.deployment_status === "ACTIVE" ? "Deactivate" : "Activate"}
                              </button>
                              {m.lifecycle_status !== "RETIRED" && (
                                <button
                                  onClick={() => handleTransitionLifecycle(m, "RETIRED")}
                                  style={{
                                    padding: "6px 8px",
                                    background: "#f8fafc",
                                    border: "1px solid #e2e8f0",
                                    borderRadius: "6px",
                                    fontSize: "11px",
                                    color: "#64748b",
                                    cursor: "pointer"
                                  }}
                                >
                                  Retire
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Model Card Modal */}
      {selectedCard && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(15, 23, 42, 0.6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 9999,
          padding: "20px"
        }}>
          <div style={{
            background: "#ffffff",
            borderRadius: "16px",
            width: "100%",
            maxWidth: "800px",
            maxHeight: "90vh",
            display: "flex",
            flexDirection: "column",
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
            overflow: "hidden"
          }}>
            {/* Modal Header */}
            <div style={{
              padding: "20px 24px",
              borderBottom: "1px solid #e2e8f0",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "#f8fafc"
            }}>
              <div>
                <h2 style={{ margin: 0, fontSize: "18px", fontWeight: "700", color: "#0f172a" }}>
                  Model Card: {selectedCard.model_name}
                </h2>
                <p style={{ margin: "2px 0 0 0", fontSize: "12px", color: "#64748b" }}>
                  Version {selectedCard.model_version} &bull; {selectedCard.task} &bull; {selectedCard.model_type}
                </p>
              </div>
              <button
                onClick={() => setSelectedCard(null)}
                style={{
                  background: "transparent",
                  border: "none",
                  fontSize: "20px",
                  cursor: "pointer",
                  color: "#64748b",
                  padding: "4px 8px"
                }}
              >
                &times;
              </button>
            </div>

            {/* Modal Navigation Tabs */}
            <div style={{ display: "flex", borderBottom: "1px solid #e2e8f0", padding: "0 24px", background: "#ffffff" }}>
              {["overview", "features", "metrics", "governance"].map(tab => (
                <button
                  key={tab}
                  onClick={() => setCardTab(tab)}
                  style={{
                    padding: "12px 16px",
                    background: "transparent",
                    border: "none",
                    borderBottom: cardTab === tab ? "2px solid #0284c7" : "2px solid transparent",
                    color: cardTab === tab ? "#0284c7" : "#64748b",
                    fontWeight: cardTab === tab ? "700" : "500",
                    fontSize: "13px",
                    cursor: "pointer",
                    textTransform: "capitalize"
                  }}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Modal Body Content */}
            <div style={{ padding: "24px", overflowY: "auto", fontSize: "13px", lineHeight: "1.6", color: "#334155" }}>
              {cardTab === "overview" && (
                <div>
                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Primary Purpose</h3>
                  <p style={{ margin: "0 0 16px 0" }}>{selectedCard.purpose || "Not available."}</p>

                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Intended Use</h3>
                  <p style={{ margin: "0 0 16px 0" }}>{selectedCard.intended_use || "Not available."}</p>

                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Out of Scope / Prohibited Uses</h3>
                  <p style={{ margin: "0 0 16px 0", color: "#b91c1c" }}>{selectedCard.out_of_scope_use}</p>

                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Limitations & Caveats</h3>
                  <p style={{ margin: "0 0 16px 0" }}>{selectedCard.limitations || "None documented."}</p>

                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Known Risks & Mitigation</h3>
                  <p style={{ margin: "0 0 16px 0" }}>{selectedCard.known_risks || "None documented."}</p>
                </div>
              )}

              {cardTab === "features" && (
                <div>
                  <div style={{ marginBottom: "16px" }}>
                    <strong>Target Variable:</strong> <span style={{ fontFamily: "monospace", background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px" }}>{selectedCard.target_variable}</span>
                  </div>
                  <div style={{ marginBottom: "16px" }}>
                    <strong>Total Features:</strong> {selectedCard.feature_count}
                  </div>
                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Input Feature Schema</h3>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", maxHeight: "250px", overflowY: "auto", padding: "8px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    {selectedCard.input_features.map((feat, idx) => (
                      <span key={idx} style={{
                        background: "#ffffff",
                        border: "1px solid #cbd5e1",
                        borderRadius: "4px",
                        padding: "2px 8px",
                        fontSize: "11px",
                        fontFamily: "monospace"
                      }}>
                        {feat}
                      </span>
                    ))}
                  </div>

                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginTop: "16px", marginBottom: "8px" }}>Explainability Scope</h3>
                  <p style={{ margin: 0 }}>{selectedCard.explainability?.method} - {selectedCard.explainability?.scope}</p>
                </div>
              )}

              {cardTab === "metrics" && (
                <div>
                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Training Data Reference</h3>
                  <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0", marginBottom: "16px" }}>
                    <div><strong>Dataset:</strong> {selectedCard.dataset?.reference}</div>
                    <div style={{ fontSize: "11px", fontFamily: "monospace", color: "#64748b", marginTop: "4px", wordBreak: "break-all" }}>
                      SHA-256: {selectedCard.dataset?.sha256}
                    </div>
                  </div>

                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Evaluation Metrics</h3>
                  <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    <pre style={{ margin: 0, fontSize: "12px", fontFamily: "monospace" }}>
                      {JSON.stringify(selectedCard.evaluation_metrics, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {cardTab === "governance" && (
                <div>
                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Artifact Signature</h3>
                  <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0", marginBottom: "16px" }}>
                    <div><strong>Artifact Path:</strong> {selectedCard.artifact?.path}</div>
                    <div style={{ fontSize: "11px", fontFamily: "monospace", color: "#0f172a", marginTop: "4px", wordBreak: "break-all" }}>
                      <strong>SHA-256:</strong> {selectedCard.artifact?.sha256}
                    </div>
                    <div style={{ marginTop: "6px" }}>
                      <strong>Integrity Status:</strong> <span style={{ color: selectedCard.artifact?.integrity_status === "VERIFIED" ? "#059669" : "#e11d48", fontWeight: "700" }}>{selectedCard.artifact?.integrity_status}</span>
                    </div>
                  </div>

                  <h3 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a", marginBottom: "8px" }}>Governance & Review State</h3>
                  <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0", marginBottom: "16px" }}>
                    <div><strong>Lifecycle Status:</strong> {selectedCard.governance?.lifecycle_status}</div>
                    <div><strong>Deployment Status:</strong> {selectedCard.governance?.deployment_status}</div>
                    {selectedCard.governance?.reviewed_at && (
                      <div style={{ marginTop: "4px" }}>
                        <strong>Last Reviewed:</strong> {new Date(selectedCard.governance.reviewed_at).toLocaleString()}
                        {selectedCard.governance.review_notes && <div><strong>Notes:</strong> {selectedCard.governance.review_notes}</div>}
                      </div>
                    )}
                  </div>

                  <div style={{ padding: "12px", background: "#fef3c7", border: "1px solid #fde68a", borderRadius: "8px", fontSize: "11px", color: "#92400e" }}>
                    <strong>Disclaimer:</strong> {selectedCard.regulatory_disclaimer}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div style={{
              padding: "16px 24px",
              borderTop: "1px solid #e2e8f0",
              background: "#f8fafc",
              display: "flex",
              justifyContent: "flex-end"
            }}>
              <button
                onClick={() => setSelectedCard(null)}
                style={{
                  padding: "8px 16px",
                  background: "#0f172a",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  fontWeight: "600",
                  cursor: "pointer",
                  fontSize: "13px"
                }}
              >
                Close Model Card
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Admin Governance Review Modal */}
      {reviewModelTarget && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(15, 23, 42, 0.6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 9999,
          padding: "20px"
        }}>
          <div style={{
            background: "#ffffff",
            borderRadius: "16px",
            width: "100%",
            maxWidth: "500px",
            padding: "24px",
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)"
          }}>
            <h2 style={{ margin: "0 0 6px 0", fontSize: "18px", fontWeight: "700", color: "#0f172a" }}>
              Administrative Governance Review
            </h2>
            <p style={{ margin: "0 0 16px 0", fontSize: "13px", color: "#64748b" }}>
              Model: <strong>{reviewModelTarget.model_name}</strong> (v{reviewModelTarget.model_version})
            </p>

            <ErrorMessage message={reviewErr} />

            <form onSubmit={handleSubmitReview}>
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
                  Review Decision
                </label>
                <select
                  value={reviewDecision}
                  onChange={e => setReviewDecision(e.target.value)}
                  style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px" }}
                >
                  <option value="APPROVED">APPROVED (Authorized for active deployment)</option>
                  <option value="REJECTED">REJECTED (Retire and deactivate model)</option>
                </select>
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
                  Governance Review Notes
                </label>
                <textarea
                  rows={3}
                  value={reviewNotes}
                  onChange={e => setReviewNotes(e.target.value)}
                  placeholder="Document validation criteria, evaluation context, or sign-off remarks..."
                  style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px", boxSizing: "border-box" }}
                />
              </div>

              <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  onClick={() => setReviewModelTarget(null)}
                  style={{
                    padding: "8px 16px",
                    background: "#f1f5f9",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    fontWeight: "600",
                    fontSize: "13px",
                    cursor: "pointer",
                    color: "#475569"
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={reviewSubmitting}
                  style={{
                    padding: "8px 16px",
                    background: reviewDecision === "APPROVED" ? "#059669" : "#e11d48",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    fontWeight: "700",
                    fontSize: "13px",
                    cursor: "pointer"
                  }}
                >
                  {reviewSubmitting ? "Submitting..." : `Confirm ${reviewDecision}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

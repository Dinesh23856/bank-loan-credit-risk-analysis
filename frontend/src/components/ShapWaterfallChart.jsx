import React from "react";

export default function ShapWaterfallChart({
  baseValue = 0.50,
  finalProbability = 0.50,
  positiveFactors = [],
  adverseReasons = []
}) {
  const factors = [
    ...positiveFactors.map(f => ({ ...f, type: "positive" })),
    ...adverseReasons.map(f => ({ ...f, type: "negative" }))
  ].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));

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
          <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "600", color: "#0f172a" }}>
            Localized Decision Explainability (TreeSHAP)
          </h3>
          <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#64748b" }}>
            Feature attributions derived from the production Random Forest underwriting model.
          </p>
        </div>
        <div style={{ display: "flex", gap: "12px", fontSize: "12px" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "#059669" }}>
            <span style={{ width: "10px", height: "10px", backgroundColor: "#10b981", borderRadius: "2px" }}></span>
            Positive (+Approval)
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "#e11d48" }}>
            <span style={{ width: "10px", height: "10px", backgroundColor: "#f43f5e", borderRadius: "2px" }}></span>
            Negative (-Approval)
          </span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px" }}>
        <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
          <span style={{ fontSize: "12px", color: "#64748b" }}>Model Base Rate (E[f(x)])</span>
          <div style={{ fontSize: "20px", fontWeight: "700", color: "#334155" }}>
            {(baseValue * 100).toFixed(1)}%
          </div>
        </div>
        <div style={{ background: finalProbability >= 0.5 ? "#ecfdf5" : "#fff1f2", padding: "12px", borderRadius: "8px", border: `1px solid ${finalProbability >= 0.5 ? "#a7f3d0" : "#fecdd3"}` }}>
          <span style={{ fontSize: "12px", color: finalProbability >= 0.5 ? "#065f46" : "#9f1239" }}>Final Predicted Probability</span>
          <div style={{ fontSize: "20px", fontWeight: "700", color: finalProbability >= 0.5 ? "#047857" : "#be123c" }}>
            {(finalProbability * 100).toFixed(1)}% ({finalProbability >= 0.5 ? "Approved" : "Rejected"})
          </div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {factors.length === 0 ? (
          <p style={{ fontSize: "13px", color: "#64748b", textAlign: "center", margin: "20px 0" }}>
            No localized SHAP explanations available for this record.
          </p>
        ) : (
          factors.map((item, idx) => {
            const isPos = item.type === "positive";
            const absVal = Math.abs(item.contribution);
            const widthPct = Math.min(100, Math.max(8, absVal * 300));
            const formattedName = (item.feature || "Feature").replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());

            return (
              <div key={idx} style={{
                display: "flex",
                flexDirection: "column",
                padding: "8px 12px",
                borderRadius: "6px",
                background: "#f8fafc",
                border: "1px solid #edf2f7"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontSize: "13px", fontWeight: "600", color: "#1e293b" }}>
                    {formattedName}
                  </span>
                  <span style={{
                    fontSize: "12px",
                    fontWeight: "700",
                    color: isPos ? "#059669" : "#e11d48"
                  }}>
                    {isPos ? "+" : ""}{(item.contribution * 100).toFixed(2)}% impact
                  </span>
                </div>

                <div style={{
                  height: "8px",
                  width: "100%",
                  backgroundColor: "#e2e8f0",
                  borderRadius: "4px",
                  overflow: "hidden",
                  position: "relative"
                }}>
                  <div style={{
                    height: "100%",
                    width: `${widthPct}%`,
                    backgroundColor: isPos ? "#10b981" : "#f43f5e",
                    borderRadius: "4px"
                  }} />
                </div>

                {item.description && (
                  <span style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                    {item.description}
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>

      <div style={{ marginTop: "16px", padding: "10px", background: "#f1f5f9", borderRadius: "6px", fontSize: "11px", color: "#64748b" }}>
        <b>Notice:</b> Factors represent localized TreeSHAP additive feature attributions for this specific applicant against the model baseline distribution.
      </div>
    </div>
  );
}

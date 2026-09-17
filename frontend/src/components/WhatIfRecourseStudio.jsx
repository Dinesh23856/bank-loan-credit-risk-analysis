import React, { useState, useEffect, useRef } from "react";
import { counterfactual } from "../api/client";

export default function WhatIfRecourseStudio({
  applicantData,
  originalProbability = 0.20,
  onSimulateSuccess
}) {
  const [loanAmount, setLoanAmount] = useState(applicantData?.requested_loan_amount || applicantData?.loan_amount || 500000);
  const [loanTerm, setLoanTerm] = useState(applicantData?.loan_term || applicantData?.loan_term_months || 36);
  const [collateralValue, setCollateralValue] = useState(applicantData?.collateral_value || 0);
  const [savings, setSavings] = useState(applicantData?.savings || 50000);
  const [dti, setDti] = useState(applicantData?.debt_to_income_ratio || 0.45);

  const [loading, setLoading] = useState(false);
  const [simResult, setSimResult] = useState(null);
  const [error, setError] = useState("");

  const debounceTimer = useRef(null);

  useEffect(() => {
    if (!applicantData) return;

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    debounceTimer.current = setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const payload = {
          applicant_data: {
            applicant_name: applicantData.applicant_name || "Applicant",
            city: applicantData.city || "",
            region: applicantData.region || "",
            age: Number(applicantData.age || 35),
            dependents: Number(applicantData.dependents || 0),
            gender: applicantData.gender || "Male",
            marital_status: applicantData.marital_status || "Single",
            education: applicantData.education || "Graduate",
            employment_type: applicantData.employment_type || "Salaried",
            annual_income: Number(applicantData.annual_income || 600000),
            debt_to_income_ratio: Number(dti),
            savings: Number(savings),
            bank_balance: Number(applicantData.bank_balance || 50000),
            assets: Number(applicantData.assets || 100000),
            credit_history: applicantData.credit_history || "Average",
            previous_loans: Number(applicantData.previous_loans || 1),
            previous_defaults: Number(applicantData.previous_defaults || 0),
            payment_history: Number(applicantData.payment_history || 85),
            credit_utilization: Number(applicantData.credit_utilization || 0.4),
            credit_score: Number(applicantData.credit_score || 650),
            loan_type: applicantData.loan_type || "Personal",
            requested_loan_amount: Number(loanAmount),
            loan_term: Number(loanTerm),
            collateral_value: Number(collateralValue),
            interest_rate: Number(applicantData.interest_rate || 10.5)
          },
          requested_loan_amount: Number(loanAmount),
          loan_term: Number(loanTerm),
          collateral_value: Number(collateralValue),
          savings: Number(savings),
          debt_to_income_ratio: Number(dti)
        };

        const res = await counterfactual(payload);
        setSimResult(res);
        if (onSimulateSuccess) onSimulateSuccess(res);
      } catch (err) {
        setError(err.message || "Simulation failed");
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [loanAmount, loanTerm, collateralValue, savings, dti, applicantData]);

  const origPct = (originalProbability * 100).toFixed(1);
  const simPct = simResult ? (simResult.approval_probability * 100).toFixed(1) : origPct;
  const isApproved = simResult && simResult.estimated_decision === "Approved";

  return (
    <div style={{
      background: "#ffffff",
      border: "1px solid #e2e8f0",
      borderRadius: "12px",
      padding: "24px",
      marginTop: "24px",
      boxShadow: "0 2px 4px rgba(0,0,0,0.04)"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
        <div>
          <div style={{ display: "inline-block", background: "#fef3c7", color: "#92400e", fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "12px", marginBottom: "6px" }}>
            RECOURSE SIMULATOR
          </div>
          <h3 style={{ margin: 0, fontSize: "18px", fontWeight: "700", color: "#0f172a" }}>
            What-If Counterfactual Recourse Studio
          </h3>
          <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "#64748b" }}>
            Explore mutable financial adjustments to identify actionable paths toward credit approval.
          </p>
        </div>

        {/* Comparison Header */}
        <div style={{ display: "flex", gap: "12px", textAlign: "right" }}>
          <div style={{ padding: "8px 12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", color: "#64748b", display: "block" }}>Original Probability</span>
            <span style={{ fontSize: "16px", fontWeight: "700", color: "#64748b" }}>{origPct}%</span>
          </div>
          <div style={{ padding: "8px 12px", background: isApproved ? "#ecfdf5" : "#fff1f2", borderRadius: "8px", border: `1px solid ${isApproved ? "#a7f3d0" : "#fecdd3"}` }}>
            <span style={{ fontSize: "11px", color: isApproved ? "#047857" : "#be123c", display: "block" }}>
              Simulated Probability {loading && "..."}
            </span>
            <span style={{ fontSize: "18px", fontWeight: "800", color: isApproved ? "#059669" : "#e11d48" }}>
              {simPct}%
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ padding: "10px", background: "#fef2f2", color: "#991b1b", borderRadius: "6px", fontSize: "12px", marginBottom: "16px" }}>
          {error}
        </div>
      )}

      {/* Simulator Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginTop: "16px" }}>
        {/* Left Column: Mutable Financial Sliders */}
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <h4 style={{ margin: 0, fontSize: "13px", fontWeight: "600", color: "#334155", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Adjustable Financial Parameters
          </h4>

          {/* Requested Loan Amount */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
              <label style={{ fontWeight: "600", color: "#1e293b" }}>Requested Loan Amount</label>
              <span style={{ fontWeight: "700", color: "#0f172a" }}>₹{Number(loanAmount).toLocaleString()}</span>
            </div>
            <input
              type="range"
              min="25000"
              max="2000000"
              step="10000"
              value={loanAmount}
              onChange={e => setLoanAmount(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#2563eb" }}
            />
          </div>

          {/* Loan Term */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
              <label style={{ fontWeight: "600", color: "#1e293b" }}>Loan Term (Months)</label>
              <span style={{ fontWeight: "700", color: "#0f172a" }}>{loanTerm} Months</span>
            </div>
            <input
              type="range"
              min="12"
              max="120"
              step="6"
              value={loanTerm}
              onChange={e => setLoanTerm(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#2563eb" }}
            />
          </div>

          {/* Additional Collateral */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
              <label style={{ fontWeight: "600", color: "#1e293b" }}>Pledged Collateral Valuation</label>
              <span style={{ fontWeight: "700", color: "#0f172a" }}>₹{Number(collateralValue).toLocaleString()}</span>
            </div>
            <input
              type="range"
              min="0"
              max="3000000"
              step="50000"
              value={collateralValue}
              onChange={e => setCollateralValue(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#2563eb" }}
            />
          </div>

          {/* Dedicated Savings / Down Payment */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
              <label style={{ fontWeight: "600", color: "#1e293b" }}>Dedicated Savings / Reserve</label>
              <span style={{ fontWeight: "700", color: "#0f172a" }}>₹{Number(savings).toLocaleString()}</span>
            </div>
            <input
              type="range"
              min="10000"
              max="1000000"
              step="10000"
              value={savings}
              onChange={e => setSavings(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#2563eb" }}
            />
          </div>

          {/* Debt to Income Ratio */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
              <label style={{ fontWeight: "600", color: "#1e293b" }}>Target Debt-to-Income (DTI)</label>
              <span style={{ fontWeight: "700", color: "#0f172a" }}>{(dti * 100).toFixed(1)}%</span>
            </div>
            <input
              type="range"
              min="0.10"
              max="0.80"
              step="0.02"
              value={dti}
              onChange={e => setDti(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#2563eb" }}
            />
          </div>
        </div>

        {/* Right Column: Protected Attributes (Locked) & Simulation Result */}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <h4 style={{ margin: "0 0 8px 0", fontSize: "13px", fontWeight: "600", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Locked Demographic Attributes (Protected)
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
              {[
                { label: "Gender", val: applicantData?.gender || "Male" },
                { label: "Age", val: `${applicantData?.age || 35} Yrs` },
                { label: "Marital Status", val: applicantData?.marital_status || "Single" },
                { label: "Education", val: applicantData?.education || "Graduate" },
              ].map((item, i) => (
                <div key={i} style={{ padding: "8px 10px", background: "#f1f5f9", borderRadius: "6px", border: "1px dashed #cbd5e1" }}>
                  <div style={{ fontSize: "10px", color: "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                    <span>🔒</span> {item.label}
                  </div>
                  <div style={{ fontSize: "12px", fontWeight: "600", color: "#334155", marginTop: "2px" }}>
                    {item.val}
                  </div>
                </div>
              ))}
            </div>
            <p style={{ fontSize: "11px", color: "#94a3b8", marginTop: "6px", fontStyle: "italic" }}>
              Protected demographic variables cannot be modified for recourse purposes in compliance with fair lending principles.
            </p>
          </div>

          {/* Simulation Status Card */}
          <div style={{
            padding: "14px",
            borderRadius: "8px",
            background: isApproved ? "#f0fdf4" : "#fef2f2",
            border: `1px solid ${isApproved ? "#bbf7d0" : "#fecaca"}`,
            marginTop: "14px"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "12px", fontWeight: "600", color: isApproved ? "#166534" : "#991b1b" }}>
                Simulation Outcome:
              </span>
              <span style={{
                fontSize: "12px",
                fontWeight: "700",
                padding: "3px 10px",
                borderRadius: "12px",
                background: isApproved ? "#15803d" : "#dc2626",
                color: "#ffffff"
              }}>
                {isApproved ? "Likely Approved" : "Remains Rejected"}
              </span>
            </div>
            <div style={{ fontSize: "12px", color: isApproved ? "#15803d" : "#7f1d1d", marginTop: "6px" }}>
              {isApproved
                ? "Simulated model probability meets the approval threshold. Applying these financial adjustments would significantly strengthen this application."
                : "Additional adjustments (e.g. lowering loan amount or reducing total debt-to-income ratio) are still needed to cross the approval threshold."}
            </div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: "16px", padding: "10px", background: "#f8fafc", borderRadius: "6px", fontSize: "11px", color: "#64748b", border: "1px solid #e2e8f0" }}>
        <b>Notice:</b> This counterfactual scenario is an indicative simulation based on statistical underwriting models. It does not constitute a formal loan offer or guarantee of credit approval.
      </div>
    </div>
  );
}

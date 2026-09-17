const API_URL = import.meta.env.VITE_API_URL;
if (import.meta.env.PROD && !API_URL) throw new Error("VITE_API_URL is required in production.");
const base = (API_URL || "http://localhost:8000").replace(/\/$/, "");

export async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeout ?? 15000);
  const token = localStorage.getItem("access_token");
  try {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${base}${path}`, { ...options, headers, signal: controller.signal, credentials: "include" });
    let body = null;
    try { body = await res.json(); } catch {}
    if (!res.ok) {
      if (res.status === 401) localStorage.removeItem("access_token");
      throw new Error(body?.detail || body?.message || `Request failed (${res.status})`);
    }
    return body;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    if (e instanceof TypeError) throw new Error("Unable to reach the server. Check your connection.");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const login = data => api("/auth/login", { method: "POST", body: JSON.stringify(data) });
export const register = data => api("/auth/register", { method: "POST", body: JSON.stringify(data) });
export const logout = () => api("/auth/logout", { method: "POST" });
export const refreshToken = () => api("/auth/refresh", { method: "POST" });
export const me = () => api("/auth/me");
export const submitLoan = data => api("/predict/loan", { method: "POST", body: JSON.stringify(data) });
export const counterfactual = data => api("/predict/counterfactual", { method: "POST", body: JSON.stringify(data) });
export const applications = ({ page = 1, page_size = 20 } = {}) => api(`/applications?page=${page}&page_size=${page_size}`);
export const application = id => api(`/applications/${encodeURIComponent(id)}`);
export const adminSummary = () => api("/admin/summary");
export const adminUsers = ({ page = 1, page_size = 20 } = {}) => api(`/admin/users?page=${page}&page_size=${page_size}`);
export const adminApplications = ({ page = 1, page_size = 20, search = "", status = "", region = "", date_from = "", date_to = "" } = {}) => {
  const q = new URLSearchParams({ page, page_size });
  if (search) q.set("search", search);
  if (status) q.set("status", status);
  if (region) q.set("region", region);
  if (date_from) q.set("date_from", date_from);
  if (date_to) q.set("date_to", date_to);
  return api(`/admin/applications?${q}`);
};
export const adminMetrics = () => api("/admin/metrics");
export const adminDrift = (windowDays) => api(windowDays ? `/admin/drift?window_days=${windowDays}` : "/admin/drift");
export const adminFairness = (attribute = "gender") => api(`/admin/fairness?attribute=${encodeURIComponent(attribute)}`);

export const evaluateRisk = data => api("/predict/risk", { method: "POST", body: JSON.stringify(data) });
export const processApplicationAsync = id => api(`/applications/${encodeURIComponent(id)}/process`, { method: "POST" });
export const getTask = taskId => api(`/tasks/${encodeURIComponent(taskId)}`);

export async function downloadPDF(path, filename) {
  const token = localStorage.getItem("access_token");
  let res = await fetch(`${base}${path}`, {
    method: "GET",
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  });
  if (!res.ok) {
    // Fallback to POST if server prefers POST
    res = await fetch(`${base}${path}`, {
      method: "POST",
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) }
    });
  }
  if (!res.ok) throw new Error("Failed to generate PDF document.");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export const downloadAdverseActionPDF = id => downloadPDF(`/applications/${encodeURIComponent(id)}/adverse-action.pdf`, `adverse_action_notice_${id}.pdf`);
export const downloadApprovalLetterPDF = id => downloadPDF(`/applications/${encodeURIComponent(id)}/approval-letter.pdf`, `loan_approval_commitment_${id}.pdf`);
export const downloadKFSPDF = id => downloadPDF(`/applications/${encodeURIComponent(id)}/kfs/pdf`, `kfs_loan_summary_${id}.pdf`);


export const chatSend = data => api("/chat", { method: "POST", body: JSON.stringify(data) });
export const chatConversations = () => api("/chat/conversations");
export const chatConversation = id => api(`/chat/conversations/${encodeURIComponent(id)}`);
export const chatDeleteConversation = id => api(`/chat/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });

export const underwriterQueue = ({ page = 1, page_size = 20, status_filter = "" } = {}) => {
  const q = new URLSearchParams({ page, page_size });
  if (status_filter) q.set("status_filter", status_filter);
  return api(`/underwriter/queue?${q}`);
};
export const underwriterApplication = id => api(`/underwriter/applications/${encodeURIComponent(id)}`);
export const underwriterReview = (id, data) => api(`/underwriter/applications/${encodeURIComponent(id)}/review`, { method: "POST", body: JSON.stringify(data) });
export const applicationHistoryTimeline = id => api(`/applications/${encodeURIComponent(id)}/history`);
export const transitionApplication = (id, data) => api(`/applications/${encodeURIComponent(id)}/transition`, { method: "POST", body: JSON.stringify(data) });
export const adminAuditLogs = ({ page = 1, page_size = 50, user_id, role, action, resource_type, date_from, date_to } = {}) => {
  const q = new URLSearchParams({ page, page_size });
  if (user_id != null && user_id !== "") q.set("user_id", user_id);
  if (role) q.set("role", role);
  if (action) q.set("action", action);
  if (resource_type) q.set("resource_type", resource_type);
  if (date_from) q.set("date_from", date_from);
  if (date_to) q.set("date_to", date_to);
  return api(`/admin/audit-logs?${q}`);
};
export const adminUpdateUserRole = (userId, data) => api(`/admin/users/${encodeURIComponent(userId)}/role`, { method: "PUT", body: JSON.stringify(data) });

export const modelRegistryList = ({ lifecycle_status = "", deployment_status = "" } = {}) => {
  const q = new URLSearchParams();
  if (lifecycle_status) q.set("lifecycle_status", lifecycle_status);
  if (deployment_status) q.set("deployment_status", deployment_status);
  const qs = q.toString();
  return api(`/models${qs ? `?${qs}` : ""}`);
};
export const modelRegistryDetail = id => api(`/models/${encodeURIComponent(id)}`);
export const modelCard = id => api(`/models/${encodeURIComponent(id)}/card`);
export const verifyModelIntegrity = id => api(`/models/${encodeURIComponent(id)}/verify-integrity`, { method: "POST" });
export const updateModelStatus = (id, data) => api(`/models/${encodeURIComponent(id)}/status`, { method: "PUT", body: JSON.stringify(data) });
export const reviewModel = (id, data) => api(`/models/${encodeURIComponent(id)}/review`, { method: "POST", body: JSON.stringify(data) });

// Phase 3: Financial Calculations & Academic KFS
export const calculateEMI = data => api("/financial/calculate-emi", { method: "POST", body: JSON.stringify(data) });
export const applicationFinancialSummary = id => api(`/applications/${encodeURIComponent(id)}/financial-summary`);
export const applicationAmortization = id => api(`/applications/${encodeURIComponent(id)}/amortization`);
export const applicationKFS = id => api(`/applications/${encodeURIComponent(id)}/kfs`);

// Phase 4: Risk Analyst & Executive Analytics
export const riskAnalystOverview = (params = {}) => {
  const q = new URLSearchParams();
  if (params.date_from) q.set("date_from", params.date_from);
  if (params.date_to) q.set("date_to", params.date_to);
  if (params.risk_level) q.set("risk_level", params.risk_level);
  if (params.region) q.set("region", params.region);
  const qs = q.toString();
  return api(`/risk-analyst/overview${qs ? `?${qs}` : ""}`);
};

export const riskAnalystWorkflowStatus = (params = {}) => {
  const q = new URLSearchParams();
  if (params.date_from) q.set("date_from", params.date_from);
  if (params.date_to) q.set("date_to", params.date_to);
  if (params.risk_level) q.set("risk_level", params.risk_level);
  if (params.region) q.set("region", params.region);
  const qs = q.toString();
  return api(`/risk-analyst/workflow-status${qs ? `?${qs}` : ""}`);
};

export const riskAnalystApprovalAnalysis = (params = {}) => {
  const q = new URLSearchParams();
  if (params.date_from) q.set("date_from", params.date_from);
  if (params.date_to) q.set("date_to", params.date_to);
  if (params.risk_level) q.set("risk_level", params.risk_level);
  if (params.region) q.set("region", params.region);
  const qs = q.toString();
  return api(`/risk-analyst/approval-analysis${qs ? `?${qs}` : ""}`);
};

export const riskAnalystCreditScoreAnalysis = (params = {}) => {
  const q = new URLSearchParams();
  if (params.date_from) q.set("date_from", params.date_from);
  if (params.date_to) q.set("date_to", params.date_to);
  if (params.risk_level) q.set("risk_level", params.risk_level);
  if (params.region) q.set("region", params.region);
  const qs = q.toString();
  return api(`/risk-analyst/credit-score-analysis${qs ? `?${qs}` : ""}`);
};

export const riskAnalystLoanAmountAnalysis = (params = {}) => {
  const q = new URLSearchParams();
  if (params.date_from) q.set("date_from", params.date_from);
  if (params.date_to) q.set("date_to", params.date_to);
  if (params.risk_level) q.set("risk_level", params.risk_level);
  if (params.region) q.set("region", params.region);
  const qs = q.toString();
  return api(`/risk-analyst/loan-amount-analysis${qs ? `?${qs}` : ""}`);
};

export const riskAnalystRiskDistribution = (params = {}) => {
  const q = new URLSearchParams();
  if (params.date_from) q.set("date_from", params.date_from);
  if (params.date_to) q.set("date_to", params.date_to);
  if (params.risk_level) q.set("risk_level", params.risk_level);
  if (params.region) q.set("region", params.region);
  const qs = q.toString();
  return api(`/risk-analyst/risk-distribution${qs ? `?${qs}` : ""}`);
};

export const riskAnalystModelPerformance = () => api("/risk-analyst/model-performance");

export const riskAnalystDrift = (windowDays) => api(windowDays ? `/risk-analyst/drift?window_days=${windowDays}` : "/risk-analyst/drift");

export const riskAnalystFairness = (attribute = "gender") => api(`/risk-analyst/fairness?attribute=${encodeURIComponent(attribute)}`);

export const riskAnalystTimeTrends = ({ interval = "daily", days = 30, risk_level = "", region = "" } = {}) => {
  const q = new URLSearchParams({ interval, days });
  if (risk_level) q.set("risk_level", risk_level);
  if (region) q.set("region", region);
  return api(`/risk-analyst/time-trends?${q}`);
};

export const downloadRiskPortfolioCSV = async (params = {}) => {
  const q = new URLSearchParams();
  if (params.date_from) q.set("date_from", params.date_from);
  if (params.date_to) q.set("date_to", params.date_to);
  if (params.risk_level) q.set("risk_level", params.risk_level);
  if (params.region) q.set("region", params.region);
  const qs = q.toString();
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${base}/risk-analyst/export-csv${qs ? `?${qs}` : ""}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  });
  if (!res.ok) throw new Error("Failed to export risk portfolio CSV.");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `risk_portfolio_export_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};



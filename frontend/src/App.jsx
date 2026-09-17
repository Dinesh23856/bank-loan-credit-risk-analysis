import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminRoute from "./components/AdminRoute";
import UnderwriterRoute from "./components/UnderwriterRoute";
import RiskAnalystRoute from "./components/RiskAnalystRoute";
import BankingChatModal from "./components/BankingChatModal";
import Login from "./pages/Login";
import Register from "./pages/Register";
import UserDashboard from "./pages/UserDashboard";
import LoanApplication from "./pages/LoanApplication";
import ApplicationHistory from "./pages/ApplicationHistory";
import ApplicationDetail from "./pages/ApplicationDetail";
import AdminDashboard from "./pages/AdminDashboard";
import AdminAuditLogs from "./pages/AdminAuditLogs";
import UnderwriterQueue from "./pages/UnderwriterQueue";
import ModelRegistry from "./pages/ModelRegistry";
import RiskAnalystDashboard from "./pages/RiskAnalystDashboard";
import "./styles.css";

function ProtectedLayout() {
  return (
    <ProtectedRoute>
      <Navbar />
      <div className="shell">
        <Sidebar />
        <main><Outlet /></main>
      </div>
      <BankingChatModal />
    </ProtectedRoute>
  );
}

function UnderwriterLayout() {
  return (
    <UnderwriterRoute>
      <Navbar />
      <div className="shell">
        <Sidebar />
        <main><Outlet /></main>
      </div>
      <BankingChatModal />
    </UnderwriterRoute>
  );
}

function AdminLayout() {
  return (
    <AdminRoute>
      <Navbar />
      <div className="shell">
        <Sidebar admin />
        <main><Outlet /></main>
      </div>
      <BankingChatModal />
    </AdminRoute>
  );
}

function RiskAnalystLayout() {
  return (
    <RiskAnalystRoute>
      <Navbar />
      <div className="shell">
        <Sidebar admin />
        <main><Outlet /></main>
      </div>
      <BankingChatModal />
    </RiskAnalystRoute>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Customer / Authenticated User Routes */}
        <Route element={<ProtectedLayout />}>
          <Route path="/dashboard" element={<UserDashboard />} />
          <Route path="/apply" element={<LoanApplication />} />
          <Route path="/history" element={<ApplicationHistory />} />
          <Route path="/history/:id" element={<ApplicationDetail />} />
        </Route>

        {/* Underwriter Workflow Routes */}
        <Route element={<UnderwriterLayout />}>
          <Route path="/underwriter/review-queue" element={<UnderwriterQueue />} />
          <Route path="/underwriter/queue" element={<UnderwriterQueue />} />
        </Route>

        {/* Risk Analyst & Governance Routes */}
        <Route element={<RiskAnalystLayout />}>
          <Route path="/risk-analyst" element={<RiskAnalystDashboard />} />
          <Route path="/risk-analyst/dashboard" element={<RiskAnalystDashboard />} />
          <Route path="/model-registry" element={<ModelRegistry />} />
          <Route path="/governance" element={<ModelRegistry />} />
        </Route>

        {/* Admin Portal & Audit Routes */}
        <Route element={<AdminLayout />}>
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/audit-logs" element={<AdminAuditLogs />} />
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
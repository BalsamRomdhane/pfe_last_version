import React, { useContext, useEffect } from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { UserProvider, UserContext } from './context/UserContext';
import { NotificationProvider } from './context/NotificationContext';

// ── Components ────────────────────────────────────────────────────────────────
import Login       from './components/Login';
import Dashboard   from './components/Dashboard.jsx';
import Users       from './components/Users';
import Departments from './components/Departments';
import Normes      from './components/Normes';
import Documents   from './components/Documents';
import Validations from './components/Validations';
import System      from './components/System';
import ResetPassword from './components/ResetPassword';

// ── Pages ─────────────────────────────────────────────────────────────────────
import TrainingDataset      from './pages/TrainingDataset';
import MLDashboard          from './pages/MLDashboard';
import DocumentAnalysis     from './pages/DocumentAnalysis';
import SemanticSearch       from './pages/SemanticSearch';
import EvidenceIntelligence from './pages/EvidenceIntelligence';
import DatasetQuality       from './pages/DatasetQuality';
import AIInsights           from './pages/AIInsights';
import MLOps                from './pages/MLOps';
import ComplianceDashboard  from './pages/ComplianceDashboard';
import DocumentSecurity     from './pages/DocumentSecurity';

// ── Guards ────────────────────────────────────────────────────────────────────
function LoadingScreen() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-slate-700 border-t-brand-500" />
        <span className="text-sm font-medium text-slate-400">Loading…</span>
      </div>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading } = useContext(UserContext);
  if (loading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RoleProtectedRoute({ children, roles }) {
  const { user, loading } = useContext(UserContext);
  if (loading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  const normalizedRole = user.role || '';
  if (!roles.includes(normalizedRole)) return <Navigate to="/dashboard" replace />;
  return children;
}

function OptionalPage({ Component, roles }) {
  if (roles) return <RoleProtectedRoute roles={roles}><Component /></RoleProtectedRoute>;
  return <ProtectedRoute><Component /></ProtectedRoute>;
}

function AdminRedirect() {
  useEffect(() => {
    const apiBase  = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
    const adminUrl = apiBase.replace(/\/api\/?$/, '/admin/');
    window.location.href = adminUrl;
  }, []);
  return null;
}

// ── App root ──────────────────────────────────────────────────────────────────
function App() {
  return (
    <UserProvider>
      <NotificationProvider>
        <AppContent />
      </NotificationProvider>
    </UserProvider>
  );
}

function AppContent() {
  const { user, loading } = useContext(UserContext);

  return (
    <Router>
      <Routes>
        {/* Public */}
        <Route path="/login" element={loading ? <LoadingScreen /> : (!user ? <Login /> : <Navigate to="/dashboard" replace />)} />
        <Route path="/reset-password" element={<ResetPassword />} />

        {/* All roles */}
        <Route path="/dashboard"  element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/documents"  element={<ProtectedRoute><Documents /></ProtectedRoute>} />
        <Route path="/system"     element={<ProtectedRoute><System /></ProtectedRoute>} />

        <Route path="/validations" element={
          <RoleProtectedRoute roles={['ADMIN','TEAMLEAD','EMPLOYEE']}>
            <Validations />
          </RoleProtectedRoute>
        } />

        {/* Admin + TeamLead */}
        <Route path="/normes" element={
          <RoleProtectedRoute roles={['ADMIN','TEAMLEAD']}><Normes /></RoleProtectedRoute>
        } />
        <Route path="/document-analysis" element={
          <RoleProtectedRoute roles={['ADMIN','TEAMLEAD']}><DocumentAnalysis /></RoleProtectedRoute>
        } />
        <Route path="/evidence-intelligence" element={
          <RoleProtectedRoute roles={['ADMIN','TEAMLEAD']}><EvidenceIntelligence /></RoleProtectedRoute>
        } />
        <Route path="/semantic-search" element={
          <RoleProtectedRoute roles={['ADMIN','TEAMLEAD']}><SemanticSearch /></RoleProtectedRoute>
        } />
        <Route path="/compliance-dashboard" element={
          <OptionalPage Component={ComplianceDashboard} roles={['ADMIN','TEAMLEAD']} />
        } />
        <Route path="/ai-insights" element={
          <OptionalPage Component={AIInsights} roles={['ADMIN','TEAMLEAD']} />
        } />
        <Route path="/document-security" element={
          <OptionalPage Component={DocumentSecurity} roles={['ADMIN','TEAMLEAD']} />
        } />

        {/* Admin only */}
        <Route path="/users" element={
          <RoleProtectedRoute roles={['ADMIN']}><Users /></RoleProtectedRoute>
        } />
        <Route path="/departments" element={
          <RoleProtectedRoute roles={['ADMIN']}><Departments /></RoleProtectedRoute>
        } />
        <Route path="/training-dataset" element={
          <RoleProtectedRoute roles={['ADMIN']}><TrainingDataset /></RoleProtectedRoute>
        } />
        <Route path="/dataset-quality" element={
          <OptionalPage Component={DatasetQuality} roles={['ADMIN']} />
        } />
        <Route path="/ml-dashboard" element={
          <RoleProtectedRoute roles={['ADMIN']}><MLDashboard /></RoleProtectedRoute>
        } />
        <Route path="/admin/mlops" element={
          <OptionalPage Component={MLOps} roles={['ADMIN']} />
        } />

        {/* Django admin redirect */}
        <Route path="/admin/*" element={<AdminRedirect />} />

        {/* Root */}
        <Route path="/" element={
          loading ? <LoadingScreen /> : <Navigate to={user ? '/dashboard' : '/login'} replace />
        } />

        {/* 404 */}
        <Route path="*" element={
          loading ? <LoadingScreen /> : (user ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />)
        } />
      </Routes>
    </Router>
  );
}

export default App;

import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import Layout from './components/layout/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import QueuePage from './pages/QueuePage';
import CheckReviewPage from './pages/CheckReviewPage';
import AdminPage from './pages/AdminPage';
import ReportsPage from './pages/ReportsPage';
import FraudTrendsPage from './pages/FraudTrendsPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/queue" element={<QueuePage />} />
                <Route path="/queue/:queueId" element={<QueuePage />} />
                <Route path="/review/:itemId" element={<CheckReviewPage />} />
                <Route path="/admin/*" element={<AdminPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/fraud/trends" element={<FraudTrendsPage />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;

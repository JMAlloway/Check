import { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import { authApi } from './services/api';
import Layout from './components/layout/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import QueuePage from './pages/QueuePage';
import CheckReviewPage from './pages/CheckReviewPage';
import AdminPage from './pages/AdminPage';
import ReportsPage from './pages/ReportsPage';
import FraudTrendsPage from './pages/FraudTrendsPage';
import HelpPage from './pages/HelpPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

/**
 * Session restoration on page refresh.
 *
 * Since access tokens are stored in memory only (not localStorage),
 * they're lost on page refresh. The refresh token is in an httpOnly cookie,
 * so we can use it to get a new access token automatically.
 */
function useSessionRestore() {
  const { user, accessToken, setAccessToken, logout } = useAuthStore();
  const [isRestoring, setIsRestoring] = useState(false);
  const [hasAttemptedRestore, setHasAttemptedRestore] = useState(false);

  useEffect(() => {
    // Only attempt restore if:
    // 1. We have user info (was logged in before refresh)
    // 2. No access token (was lost on refresh since it's memory-only)
    // 3. Haven't already tried to restore
    if (user && !accessToken && !hasAttemptedRestore) {
      setIsRestoring(true);
      setHasAttemptedRestore(true);

      authApi.refreshSession()
        .then((response) => {
          setAccessToken(response.access_token);
        })
        .catch(() => {
          // Refresh failed (cookie expired or invalid), logout user
          logout();
        })
        .finally(() => {
          setIsRestoring(false);
        });
    }
  }, [user, accessToken, hasAttemptedRestore, setAccessToken, logout]);

  return isRestoring;
}

function App() {
  const isRestoring = useSessionRestore();

  // Show loading state while restoring session
  if (isRestoring) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-bank-navy mx-auto"></div>
          <p className="mt-4 text-gray-600">Restoring session...</p>
        </div>
      </div>
    );
  }

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
                <Route path="/help" element={<HelpPage />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;

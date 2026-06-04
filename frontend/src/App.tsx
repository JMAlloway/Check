import { Suspense, lazy, useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import { authApi } from './services/api';
import ErrorBoundary from './components/ErrorBoundary';
import Layout from './components/layout/Layout';
// LoginPage stays eager so the unauthenticated entry point paints immediately.
import LoginPage from './pages/LoginPage';

// Route-based code splitting: each authenticated page (and its heavy deps such
// as recharts) loads in its own chunk on first navigation, keeping the initial
// bundle small.
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const QueuePage = lazy(() => import('./pages/QueuePage'));
const ApprovalsPage = lazy(() => import('./pages/ApprovalsPage'));
const CheckReviewPage = lazy(() => import('./pages/CheckReviewPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const AutomationPage = lazy(() => import('./pages/AutomationPage'));
const FraudTrendsPage = lazy(() => import('./pages/FraudTrendsPage'));
const ArchivePage = lazy(() => import('./pages/ArchivePage'));
const HelpPage = lazy(() => import('./pages/HelpPage'));
const OperationsHubPage = lazy(() => import('./pages/OperationsHubPage'));
const SecurityIncidentsPage = lazy(() => import('./pages/SecurityIncidentsPage'));
const ContextConnectorsPage = lazy(() => import('./pages/ContextConnectorsPage'));
const CommitBatchesPage = lazy(() => import('./pages/CommitBatchesPage'));
const AuditDrillDownPage = lazy(() => import('./pages/AuditDrillDownPage'));
const FraudEventsPage = lazy(() => import('./pages/FraudEventsPage'));

function RouteFallback() {
  return (
    <div className="flex items-center justify-center py-24" role="status" aria-label="Loading">
      <div className="h-10 w-10 animate-spin rounded-full border-b-2 border-bank-navy"></div>
    </div>
  );
}

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
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Suspense fallback={<RouteFallback />}>
                  <Routes>
                    <Route path="/" element={<Navigate to="/dashboard" replace />} />
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/queue" element={<QueuePage />} />
                    <Route path="/queue/:queueId" element={<QueuePage />} />
                    <Route path="/approvals" element={<ApprovalsPage />} />
                    <Route path="/review/:itemId" element={<CheckReviewPage />} />
                    <Route path="/admin/*" element={<AdminPage />} />
                    <Route path="/reports" element={<ReportsPage />} />
                    <Route path="/automation" element={<AutomationPage />} />
                    <Route path="/archive" element={<ArchivePage />} />
                    <Route path="/fraud/trends" element={<FraudTrendsPage />} />
                    <Route path="/fraud/events" element={<FraudEventsPage />} />
                    <Route path="/operations" element={<OperationsHubPage />} />
                    <Route path="/security/incidents" element={<SecurityIncidentsPage />} />
                    <Route path="/connectors/item-context" element={<ContextConnectorsPage />} />
                    <Route path="/connectors/commit" element={<CommitBatchesPage />} />
                    <Route path="/audit/drill-down" element={<AuditDrillDownPage />} />
                    <Route path="/help" element={<HelpPage />} />
                  </Routes>
                </Suspense>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </ErrorBoundary>
  );
}

export default App;

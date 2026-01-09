import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore, getCsrfToken } from '../stores/authStore';

const API_BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : 'http://localhost:8000/api/v1';

// Extract API origin for resolving relative image URLs
// API_BASE_URL is like "http://localhost:8000/api/v1", we need just "http://localhost:8000"
const API_ORIGIN = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Resolve an image URL from the backend.
 * Backend returns relative paths like "/api/v1/images/secure/{token}"
 * We need to prepend the API origin so the browser fetches from the correct server.
 */
export function resolveImageUrl(url: string | undefined): string | undefined {
  if (!url) return undefined;

  // If it's already an absolute URL, return as-is
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }

  // Prepend API origin to relative URLs
  return `${API_ORIGIN}${url}`;
}

/**
 * API Client - Security-hardened for bank-grade auth
 *
 * SECURITY NOTES:
 * - Access token: Sent in Authorization header (from memory, not localStorage)
 * - Refresh token: Sent automatically via httpOnly cookie (withCredentials: true)
 * - CSRF protection: X-CSRF-Token header sent for auth endpoints
 */
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // CRITICAL: Send cookies with requests
});

// Track if we're currently refreshing to prevent multiple refresh attempts
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

// Request interceptor - add auth token and CSRF token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const { accessToken } = useAuthStore.getState();
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }

    // Add CSRF token for auth endpoints (cookie-based operations)
    if (config.url?.includes('/auth/')) {
      const csrfToken = getCsrfToken();
      if (csrfToken && config.headers) {
        config.headers['X-CSRF-Token'] = csrfToken;
      }
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle 401 with cookie-based refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      // Check if we have a user (indicating we were logged in)
      const { user, logout, setAccessToken } = useAuthStore.getState();

      if (!user) {
        // Never logged in, just reject
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Wait for the refresh to complete
        return new Promise((resolve) => {
          subscribeTokenRefresh((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Refresh using httpOnly cookie (no body needed)
        // The refresh token is automatically sent via the cookie
        const response = await api.post('/auth/refresh', {});

        const { access_token } = response.data;

        // Update access token in memory
        setAccessToken(access_token);

        // Notify subscribers and retry original request
        onTokenRefreshed(access_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;

        return api(originalRequest);
      } catch {
        // Refresh failed, logout user
        logout();
        refreshSubscribers = [];
        // Redirect to login (handled by auth guard in router)
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: async (username: string, password: string) => {
    // Login sets refresh token in httpOnly cookie automatically
    const response = await api.post('/auth/login', { username, password });
    return response.data;
  },

  logout: async () => {
    // Logout reads refresh token from httpOnly cookie
    // No need to pass it in body anymore
    const response = await api.post('/auth/logout', {});
    return response.data;
  },

  getCurrentUser: async (token?: string) => {
    const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
    const response = await api.get('/auth/me', { headers });
    return response.data;
  },

  // Attempt to restore session using httpOnly cookie
  // Called on app init when user info exists but access token is missing
  refreshSession: async () => {
    const response = await api.post('/auth/refresh', {});
    return response.data;
  },
};

// Check API
export const checkApi = {
  getItems: async (params: {
    page?: number;
    page_size?: number;
    status?: string[];
    risk_level?: string[];
    queue_id?: string;
    assigned_to?: string;
    has_ai_flags?: boolean;
    sla_breached?: boolean;
    date_from?: string;
    date_to?: string;
  }) => {
    const response = await api.get('/checks', { params });
    return response.data;
  },

  getMyQueue: async (page = 1, pageSize = 20) => {
    const response = await api.get('/checks/my-queue', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  getItem: async (itemId: string) => {
    const response = await api.get(`/checks/${itemId}`);
    return response.data;
  },

  getHistory: async (itemId: string, limit = 10) => {
    const response = await api.get(`/checks/${itemId}/history`, {
      params: { limit },
    });
    return response.data;
  },

  assignItem: async (
    itemId: string,
    data: { reviewer_id?: string; approver_id?: string; queue_id?: string }
  ) => {
    const response = await api.post(`/checks/${itemId}/assign`, null, { params: data });
    return response.data;
  },

  updateStatus: async (itemId: string, status: string) => {
    const response = await api.post(`/checks/${itemId}/status`, null, {
      params: { status },
    });
    return response.data;
  },

  syncItems: async (amountMin = 5000) => {
    const response = await api.post('/checks/sync', null, {
      params: { amount_min: amountMin },
    });
    return response.data;
  },
};

// Decision API
export const decisionApi = {
  getReasonCodes: async (category?: string, decisionType?: string) => {
    const response = await api.get('/decisions/reason-codes', {
      params: { category, decision_type: decisionType },
    });
    return response.data;
  },

  createDecision: async (data: {
    check_item_id: string;
    decision_type: string;
    action: string;
    reason_code_ids?: string[];
    notes?: string;
    ai_assisted?: boolean;
  }) => {
    const response = await api.post('/decisions', data);
    return response.data;
  },

  approveDualControl: async (data: {
    decision_id: string;
    approve: boolean;
    notes?: string;
  }) => {
    const response = await api.post('/decisions/dual-control', data);
    return response.data;
  },

  getDecisionHistory: async (itemId: string) => {
    const response = await api.get(`/decisions/${itemId}/history`);
    return response.data;
  },
};

// Queue API
export const queueApi = {
  getQueues: async (includeInactive = false) => {
    const response = await api.get('/queues', {
      params: { include_inactive: includeInactive },
    });
    return response.data;
  },

  getQueue: async (queueId: string) => {
    const response = await api.get(`/queues/${queueId}`);
    return response.data;
  },

  getQueueStats: async (queueId: string) => {
    const response = await api.get(`/queues/${queueId}/stats`);
    return response.data;
  },
};

// Reports API
export const reportsApi = {
  getDashboard: async () => {
    const response = await api.get('/reports/dashboard');
    return response.data;
  },

  getThroughput: async (days = 7) => {
    const response = await api.get('/reports/throughput', { params: { days } });
    return response.data;
  },

  getDecisionReport: async (days = 30) => {
    const response = await api.get('/reports/decisions', { params: { days } });
    return response.data;
  },

  getReviewerPerformance: async (days = 30) => {
    const response = await api.get('/reports/reviewer-performance', { params: { days } });
    return response.data;
  },
};

// Image API
export const imageApi = {
  logZoom: async (imageId: string, zoomLevel: number, viewId?: string) => {
    const response = await api.post(`/images/${imageId}/zoom`, null, {
      params: { zoom_level: zoomLevel, view_id: viewId },
    });
    return response.data;
  },
};

// Audit API
export const auditApi = {
  getItemAuditTrail: async (itemId: string, limit = 100) => {
    const response = await api.get(`/audit/items/${itemId}`, { params: { limit } });
    return response.data;
  },

  generatePacket: async (data: {
    check_item_id: string;
    include_images?: boolean;
    include_history?: boolean;
    format?: string;
  }) => {
    const response = await api.post('/audit/packet', data);
    return response.data;
  },

  downloadPacket: async (downloadUrl: string, filename: string) => {
    // Download PDF and trigger browser download
    const response = await api.get(downloadUrl, {
      responseType: 'blob',
    });

    // Create blob URL and trigger download
    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};

// Fraud Intelligence API
export const fraudApi = {
  // Fraud Events
  createEvent: async (data: {
    check_item_id?: string;
    case_id?: string;
    event_date: string;
    amount: number;
    fraud_type: string;
    channel: string;
    confidence: number;
    narrative_private?: string;
    narrative_shareable?: string;
    sharing_level: number;
  }) => {
    const response = await api.post('/fraud/fraud-events', data);
    return response.data;
  },

  getEvents: async (params: {
    page?: number;
    page_size?: number;
    status?: string;
    fraud_type?: string;
    check_item_id?: string;
  }) => {
    const response = await api.get('/fraud/fraud-events', { params });
    return response.data;
  },

  getEvent: async (eventId: string) => {
    const response = await api.get(`/fraud/fraud-events/${eventId}`);
    return response.data;
  },

  updateEvent: async (eventId: string, data: Record<string, unknown>) => {
    const response = await api.patch(`/fraud/fraud-events/${eventId}`, data);
    return response.data;
  },

  submitEvent: async (eventId: string, data: {
    sharing_level?: number;
    confirm_no_pii?: boolean;
  }) => {
    const response = await api.post(`/fraud/fraud-events/${eventId}/submit`, data);
    return response.data;
  },

  withdrawEvent: async (eventId: string, reason: string) => {
    const response = await api.post(`/fraud/fraud-events/${eventId}/withdraw`, { reason });
    return response.data;
  },

  // Network Alerts
  getNetworkAlerts: async (checkItemId: string) => {
    const response = await api.get('/fraud/network-alerts', {
      params: { check_item_id: checkItemId },
    });
    return response.data;
  },

  dismissAlert: async (alertId: string, reason?: string) => {
    const response = await api.post(`/fraud/network-alerts/${alertId}/dismiss`, { reason });
    return response.data;
  },

  // Network Trends
  getNetworkTrends: async (range: string = '6m', granularity: string = 'month') => {
    const response = await api.get('/fraud/network-trends', {
      params: { range, granularity },
    });
    return response.data;
  },

  // Config
  getConfig: async () => {
    const response = await api.get('/fraud/config');
    return response.data;
  },

  updateConfig: async (data: Record<string, unknown>) => {
    const response = await api.patch('/fraud/config', data);
    return response.data;
  },

  // PII Check
  checkPII: async (text: string, strict: boolean = false) => {
    const response = await api.post('/fraud/check-pii', { text, strict });
    return response.data;
  },
};

// User Management API
export const userApi = {
  getUsers: async (params: {
    page?: number;
    page_size?: number;
    is_active?: boolean;
    search?: string;
  }) => {
    const response = await api.get('/users', { params });
    return response.data;
  },

  getUser: async (userId: string) => {
    const response = await api.get(`/users/${userId}`);
    return response.data;
  },

  createUser: async (data: {
    email: string;
    username: string;
    full_name: string;
    password: string;
    department?: string;
    branch?: string;
    employee_id?: string;
    is_active?: boolean;
    role_ids?: string[];
  }) => {
    const response = await api.post('/users', data);
    return response.data;
  },

  updateUser: async (userId: string, data: {
    email?: string;
    full_name?: string;
    department?: string;
    branch?: string;
    is_active?: boolean;
    role_ids?: string[];
  }) => {
    const response = await api.patch(`/users/${userId}`, data);
    return response.data;
  },

  getRoles: async () => {
    const response = await api.get('/users/roles/');
    return response.data;
  },

  createRole: async (data: {
    name: string;
    description?: string;
    permission_ids?: string[];
  }) => {
    const response = await api.post('/users/roles/', data);
    return response.data;
  },

  getPermissions: async () => {
    const response = await api.get('/users/permissions/');
    return response.data;
  },
};

// Queue Management API (extended)
export const queueAdminApi = {
  ...queueApi,

  createQueue: async (data: {
    name: string;
    description?: string;
    queue_type?: string;
    sla_hours?: number;
    warning_threshold_minutes?: number;
    routing_criteria?: Record<string, unknown>;
    allowed_role_ids?: string[];
    allowed_user_ids?: string[];
  }) => {
    const response = await api.post('/queues', data);
    return response.data;
  },

  updateQueue: async (queueId: string, data: {
    name?: string;
    description?: string;
    queue_type?: string;
    is_active?: boolean;
    sla_hours?: number;
    display_order?: number;
  }) => {
    const response = await api.patch(`/queues/${queueId}`, data);
    return response.data;
  },

  getAssignments: async (queueId: string) => {
    const response = await api.get(`/queues/${queueId}/assignments`);
    return response.data;
  },

  createAssignment: async (queueId: string, data: {
    user_id: string;
    can_review?: boolean;
    can_approve?: boolean;
    max_concurrent_items?: number;
  }) => {
    const response = await api.post(`/queues/${queueId}/assignments`, data);
    return response.data;
  },
};

// Policy Management API
export const policyApi = {
  getPolicies: async (status?: string) => {
    const response = await api.get('/policies', { params: { status_filter: status } });
    return response.data;
  },

  getPolicy: async (policyId: string) => {
    const response = await api.get(`/policies/${policyId}`);
    return response.data;
  },

  createPolicy: async (data: {
    name: string;
    description?: string;
    applies_to_account_types?: string[];
    applies_to_branches?: string[];
    applies_to_markets?: string[];
    initial_version?: {
      effective_date: string;
      expiry_date?: string;
      change_notes?: string;
      rules: Array<{
        name: string;
        description?: string;
        rule_type: string;
        priority: number;
        is_enabled: boolean;
        conditions: Array<{ field: string; operator: string; value: unknown }>;
        actions: Array<{ type: string; params?: Record<string, unknown> }>;
        amount_threshold?: number;
        risk_level_threshold?: string;
      }>;
    };
  }) => {
    const response = await api.post('/policies', data);
    return response.data;
  },

  createVersion: async (policyId: string, data: {
    effective_date: string;
    expiry_date?: string;
    change_notes?: string;
    rules: Array<{
      name: string;
      description?: string;
      rule_type: string;
      priority: number;
      is_enabled: boolean;
      conditions: Array<{ field: string; operator: string; value: unknown }>;
      actions: Array<{ type: string; params?: Record<string, unknown> }>;
      amount_threshold?: number;
      risk_level_threshold?: string;
    }>;
  }) => {
    const response = await api.post(`/policies/${policyId}/versions`, data);
    return response.data;
  },

  activatePolicy: async (policyId: string, versionId?: string) => {
    const response = await api.post(`/policies/${policyId}/activate`, null, {
      params: versionId ? { version_id: versionId } : undefined,
    });
    return response.data;
  },
};

// Audit Log API (extended)
export const auditLogApi = {
  ...auditApi,

  searchLogs: async (params: {
    page?: number;
    page_size?: number;
    action?: string;
    resource_type?: string;
    resource_id?: string;
    user_id?: string;
    date_from?: string;
    date_to?: string;
  }) => {
    const response = await api.get('/audit/logs', { params });
    return response.data;
  },

  getUserActivity: async (userId: string, params: {
    date_from?: string;
    date_to?: string;
    limit?: number;
  }) => {
    const response = await api.get(`/audit/users/${userId}`, { params });
    return response.data;
  },

  getItemViews: async (itemId: string) => {
    const response = await api.get(`/audit/items/${itemId}/views`);
    return response.data;
  },
};

// System API - Demo mode and system status
export const systemApi = {
  getStatus: async () => {
    const response = await api.get('/system/status');
    return response.data;
  },

  getDemoMode: async () => {
    const response = await api.get('/system/demo-mode');
    return response.data;
  },

  getDemoCredentials: async () => {
    const response = await api.get('/system/demo/credentials');
    return response.data;
  },

  seedDemoData: async (count = 60, resetExisting = false) => {
    const response = await api.post('/system/demo/seed', {
      count,
      reset_existing: resetExisting,
    });
    return response.data;
  },

  resetDemoData: async () => {
    const response = await api.post('/system/demo/reset');
    return response.data;
  },
};

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '../stores/authStore';

const API_BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const { accessToken } = useAuthStore.getState();
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle 401
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      const { refreshToken, logout } = useAuthStore.getState();

      if (refreshToken) {
        try {
          const response = await api.post('/auth/refresh', {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token } = response.data;
          const { user, setAuth } = useAuthStore.getState();

          if (user) {
            setAuth(user, access_token, refresh_token);

            // Retry original request
            const originalRequest = error.config;
            if (originalRequest && originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${access_token}`;
              return api(originalRequest);
            }
          }
        } catch {
          logout();
        }
      } else {
        logout();
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: async (username: string, password: string) => {
    const response = await api.post('/auth/login', { username, password });
    return response.data;
  },

  logout: async (refreshToken: string) => {
    const response = await api.post('/auth/logout', { refresh_token: refreshToken });
    return response.data;
  },

  getCurrentUser: async (token?: string) => {
    const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
    const response = await api.get('/auth/me', { headers });
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

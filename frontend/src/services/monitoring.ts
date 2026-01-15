/**
 * Frontend Monitoring Service
 *
 * Provides client-side monitoring for:
 * - JavaScript errors and React component errors
 * - Performance metrics (Core Web Vitals)
 * - Security-relevant events (auth failures, API errors)
 * - User session health
 *
 * All events are sent to the backend for aggregation and alerting.
 * No third-party services required (bank compliance friendly).
 */

import { api } from './api';

// Types
interface ErrorEvent {
  type: 'error';
  message: string;
  stack?: string;
  componentStack?: string;
  url: string;
  userAgent: string;
  timestamp: string;
  sessionId: string;
  userId?: string;
  metadata?: Record<string, unknown>;
}

interface PerformanceEvent {
  type: 'performance';
  metric: string;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  url: string;
  timestamp: string;
  sessionId: string;
}

interface SecurityEvent {
  type: 'security';
  eventType: string;
  severity: 'info' | 'warning' | 'error';
  details: Record<string, unknown>;
  url: string;
  timestamp: string;
  sessionId: string;
  userId?: string;
}

type MonitoringEvent = ErrorEvent | PerformanceEvent | SecurityEvent;

// Generate a session ID for correlating events
const getSessionId = (): string => {
  let sessionId = sessionStorage.getItem('monitoring_session_id');
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    sessionStorage.setItem('monitoring_session_id', sessionId);
  }
  return sessionId;
};

// Event queue for batching
let eventQueue: MonitoringEvent[] = [];
let flushTimer: NodeJS.Timeout | null = null;
const FLUSH_INTERVAL = 5000; // 5 seconds
const MAX_QUEUE_SIZE = 20;

/**
 * Flush queued events to the backend
 */
const flushEvents = async (): Promise<void> => {
  if (eventQueue.length === 0) return;

  const events = [...eventQueue];
  eventQueue = [];

  try {
    // Send to backend monitoring endpoint
    await api.post('/monitoring/events', { events });
  } catch (error) {
    // If sending fails, re-queue events (with limit to prevent memory issues)
    if (eventQueue.length < MAX_QUEUE_SIZE * 2) {
      eventQueue = [...events, ...eventQueue].slice(0, MAX_QUEUE_SIZE * 2);
    }
    console.warn('[Monitoring] Failed to send events:', error);
  }
};

/**
 * Queue an event for sending
 */
const queueEvent = (event: MonitoringEvent): void => {
  eventQueue.push(event);

  // Flush immediately if queue is full
  if (eventQueue.length >= MAX_QUEUE_SIZE) {
    flushEvents();
  }

  // Set up periodic flush
  if (!flushTimer) {
    flushTimer = setInterval(flushEvents, FLUSH_INTERVAL);
  }
};

/**
 * Get current user ID from auth store (if available)
 */
const getCurrentUserId = (): string | undefined => {
  try {
    // Dynamic import to avoid circular dependencies
    const authState = JSON.parse(localStorage.getItem('auth-storage') || '{}');
    return authState?.state?.user?.id;
  } catch {
    return undefined;
  }
};

// ============================================================================
// Error Tracking
// ============================================================================

/**
 * Track a JavaScript error
 */
export const trackError = (
  error: Error,
  metadata?: Record<string, unknown>
): void => {
  const event: ErrorEvent = {
    type: 'error',
    message: error.message,
    stack: error.stack,
    url: window.location.href,
    userAgent: navigator.userAgent,
    timestamp: new Date().toISOString(),
    sessionId: getSessionId(),
    userId: getCurrentUserId(),
    metadata,
  };

  queueEvent(event);

  // Also log to console in development
  if (import.meta.env.DEV) {
    console.error('[Monitoring] Error tracked:', error, metadata);
  }
};

/**
 * Track a React component error (from error boundary)
 */
export const trackComponentError = (
  error: Error,
  componentStack: string,
  componentName?: string
): void => {
  const event: ErrorEvent = {
    type: 'error',
    message: error.message,
    stack: error.stack,
    componentStack,
    url: window.location.href,
    userAgent: navigator.userAgent,
    timestamp: new Date().toISOString(),
    sessionId: getSessionId(),
    userId: getCurrentUserId(),
    metadata: { componentName },
  };

  queueEvent(event);
};

/**
 * Global error handler for uncaught errors
 */
export const setupGlobalErrorHandler = (): void => {
  // Uncaught errors
  window.onerror = (message, source, lineno, colno, error) => {
    trackError(error || new Error(String(message)), {
      source,
      lineno,
      colno,
      type: 'uncaught',
    });
    return false; // Let the error propagate
  };

  // Unhandled promise rejections
  window.onunhandledrejection = (event) => {
    const error = event.reason instanceof Error
      ? event.reason
      : new Error(String(event.reason));

    trackError(error, { type: 'unhandled_rejection' });
  };
};

// ============================================================================
// Performance Monitoring (Core Web Vitals)
// ============================================================================

type MetricRating = 'good' | 'needs-improvement' | 'poor';

interface WebVitalMetric {
  name: string;
  value: number;
  rating: MetricRating;
}

/**
 * Get rating for a metric based on Core Web Vitals thresholds
 */
const getMetricRating = (name: string, value: number): MetricRating => {
  const thresholds: Record<string, [number, number]> = {
    // [good, poor] thresholds - anything in between is "needs improvement"
    LCP: [2500, 4000],      // Largest Contentful Paint (ms)
    FID: [100, 300],        // First Input Delay (ms)
    CLS: [0.1, 0.25],       // Cumulative Layout Shift (score)
    FCP: [1800, 3000],      // First Contentful Paint (ms)
    TTFB: [800, 1800],      // Time to First Byte (ms)
    INP: [200, 500],        // Interaction to Next Paint (ms)
  };

  const [good, poor] = thresholds[name] || [1000, 3000];

  if (value <= good) return 'good';
  if (value >= poor) return 'poor';
  return 'needs-improvement';
};

/**
 * Track a performance metric
 */
export const trackPerformanceMetric = (
  name: string,
  value: number
): void => {
  const rating = getMetricRating(name, value);

  const event: PerformanceEvent = {
    type: 'performance',
    metric: name,
    value: Math.round(value),
    rating,
    url: window.location.href,
    timestamp: new Date().toISOString(),
    sessionId: getSessionId(),
  };

  queueEvent(event);

  // Log poor metrics in development
  if (import.meta.env.DEV && rating === 'poor') {
    console.warn(`[Monitoring] Poor ${name}:`, value);
  }
};

/**
 * Setup Core Web Vitals monitoring using Performance Observer
 */
export const setupPerformanceMonitoring = (): void => {
  // First Contentful Paint
  try {
    const paintObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.name === 'first-contentful-paint') {
          trackPerformanceMetric('FCP', entry.startTime);
        }
      }
    });
    paintObserver.observe({ type: 'paint', buffered: true });
  } catch (e) {
    console.warn('[Monitoring] Paint observer not supported');
  }

  // Largest Contentful Paint
  try {
    const lcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const lastEntry = entries[entries.length - 1];
      if (lastEntry) {
        trackPerformanceMetric('LCP', lastEntry.startTime);
      }
    });
    lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
  } catch (e) {
    console.warn('[Monitoring] LCP observer not supported');
  }

  // First Input Delay
  try {
    const fidObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        // @ts-expect-error processingStart is available on PerformanceEventTiming
        const fid = entry.processingStart - entry.startTime;
        trackPerformanceMetric('FID', fid);
      }
    });
    fidObserver.observe({ type: 'first-input', buffered: true });
  } catch (e) {
    console.warn('[Monitoring] FID observer not supported');
  }

  // Cumulative Layout Shift
  try {
    let clsValue = 0;
    const clsObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        // @ts-expect-error value is available on layout-shift entries
        if (!entry.hadRecentInput) {
          // @ts-expect-error value is available on layout-shift entries
          clsValue += entry.value;
        }
      }
    });
    clsObserver.observe({ type: 'layout-shift', buffered: true });

    // Report CLS when page is hidden
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden' && clsValue > 0) {
        trackPerformanceMetric('CLS', clsValue);
      }
    });
  } catch (e) {
    console.warn('[Monitoring] CLS observer not supported');
  }

  // Time to First Byte (from navigation timing)
  try {
    const navObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'navigation') {
          // @ts-expect-error responseStart is available on PerformanceNavigationTiming
          trackPerformanceMetric('TTFB', entry.responseStart);
        }
      }
    });
    navObserver.observe({ type: 'navigation', buffered: true });
  } catch (e) {
    console.warn('[Monitoring] Navigation observer not supported');
  }
};

// ============================================================================
// Security Event Tracking
// ============================================================================

/**
 * Track a security-relevant event
 */
export const trackSecurityEvent = (
  eventType: string,
  severity: 'info' | 'warning' | 'error',
  details: Record<string, unknown> = {}
): void => {
  const event: SecurityEvent = {
    type: 'security',
    eventType,
    severity,
    details,
    url: window.location.href,
    timestamp: new Date().toISOString(),
    sessionId: getSessionId(),
    userId: getCurrentUserId(),
  };

  queueEvent(event);
};

/**
 * Track authentication events
 */
export const trackAuthEvent = {
  loginSuccess: (userId: string) => {
    trackSecurityEvent('auth.login_success', 'info', { userId });
  },

  loginFailure: (username: string, reason: string) => {
    trackSecurityEvent('auth.login_failure', 'warning', { username, reason });
  },

  logout: () => {
    trackSecurityEvent('auth.logout', 'info', {});
  },

  sessionExpired: () => {
    trackSecurityEvent('auth.session_expired', 'warning', {});
  },

  tokenRefreshFailed: () => {
    trackSecurityEvent('auth.token_refresh_failed', 'warning', {});
  },
};

/**
 * Track API errors
 */
export const trackApiError = (
  endpoint: string,
  status: number,
  error?: string
): void => {
  const severity = status >= 500 ? 'error' : 'warning';
  trackSecurityEvent('api.error', severity, {
    endpoint,
    status,
    error,
  });
};

/**
 * Track suspicious activity
 */
export const trackSuspiciousActivity = (
  activity: string,
  details: Record<string, unknown> = {}
): void => {
  trackSecurityEvent('suspicious_activity', 'warning', {
    activity,
    ...details,
  });
};

// ============================================================================
// Initialization
// ============================================================================

/**
 * Initialize all frontend monitoring
 */
export const initializeMonitoring = (): void => {
  setupGlobalErrorHandler();
  setupPerformanceMonitoring();

  // Flush events before page unload
  window.addEventListener('beforeunload', () => {
    // Use sendBeacon for reliable delivery
    if (eventQueue.length > 0 && navigator.sendBeacon) {
      navigator.sendBeacon(
        '/api/v1/monitoring/events',
        JSON.stringify({ events: eventQueue })
      );
    }
  });

  // Flush events when page becomes hidden
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      flushEvents();
    }
  });

  console.log('[Monitoring] Frontend monitoring initialized');
};

// Export for use in React Error Boundary
export { getSessionId };

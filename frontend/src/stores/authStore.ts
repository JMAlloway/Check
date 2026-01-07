import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User } from '../types';

/**
 * Auth Store - Security-hardened token storage
 *
 * SECURITY NOTES:
 * - Access token: Stored in memory ONLY (not persisted to localStorage)
 * - Refresh token: Stored in httpOnly cookie by backend (not accessible to JS)
 * - CSRF token: Read from cookie and sent in header for cookie-based requests
 *
 * This protects against XSS attacks - even if malicious JS runs, it cannot
 * steal the refresh token (httpOnly) and the access token is lost on page reload.
 */

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, accessToken: string) => void;
  setAccessToken: (accessToken: string) => void;
  logout: () => void;
  hasPermission: (resource: string, action: string) => boolean;
  hasRole: (roleName: string) => boolean;
}

// Helper to get CSRF token from cookie
export function getCsrfToken(): string | null {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : null;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,

      setAuth: (user, accessToken) => {
        set({
          user,
          accessToken,
          isAuthenticated: true,
        });
      },

      setAccessToken: (accessToken) => {
        set({ accessToken });
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
        });
      },

      hasPermission: (resource, action) => {
        const { user } = get();
        if (!user) return false;
        if (user.is_superuser) return true;
        return user.permissions.includes(`${resource}:${action}`);
      },

      hasRole: (roleName) => {
        const { user } = get();
        if (!user) return false;
        if (user.is_superuser) return true;
        return user.roles.some((r) => r.name === roleName);
      },
    }),
    {
      name: 'auth-storage',
      // SECURITY: Only persist user info for UI display, NOT tokens
      // Access token stays in memory only (lost on refresh, re-obtained via refresh token cookie)
      // Refresh token is in httpOnly cookie (not accessible to JS at all)
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        // accessToken is intentionally NOT persisted
      }),
    }
  )
);

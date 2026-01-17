import { create } from 'zustand';
import { systemApi } from '../services/api';

interface DemoModeStatus {
  enabled: boolean;
  environment: string;
  safety_checks_passed: boolean;
  demo_data_count: number;
  features: {
    synthetic_checks: boolean;
    mock_ai_analysis: boolean;
    demo_images: boolean;
    guided_tour: boolean;
    sample_workflows: boolean;
  };
  notices: string[];
}

interface DemoCredential {
  username: string;
  password: string;
  role: string;
  description: string;
}

interface DemoState {
  // Status
  status: DemoModeStatus | null;
  credentials: DemoCredential[];
  isLoading: boolean;
  error: string | null;
  lastFetched: Date | null;

  // Actions
  fetchDemoStatus: () => Promise<void>;
  fetchCredentials: () => Promise<void>;
  clearError: () => void;

  // Computed
  isDemoMode: () => boolean;
}

export const useDemoStore = create<DemoState>((set, get) => ({
  // Initial state
  status: null,
  credentials: [],
  isLoading: false,
  error: null,
  lastFetched: null,

  // Fetch demo mode status
  fetchDemoStatus: async () => {
    // Skip if recently fetched (within 5 minutes)
    const lastFetched = get().lastFetched;
    if (lastFetched && Date.now() - lastFetched.getTime() < 5 * 60 * 1000) {
      return;
    }

    set({ isLoading: true, error: null });
    try {
      const status = await systemApi.getDemoMode();
      set({
        status,
        isLoading: false,
        lastFetched: new Date(),
      });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to fetch demo status',
      });
    }
  },

  // Fetch demo credentials (only when demo mode is enabled)
  fetchCredentials: async () => {
    const status = get().status;
    if (!status?.enabled) {
      return;
    }

    set({ isLoading: true, error: null });
    try {
      const response = await systemApi.getDemoCredentials();
      set({
        credentials: response.credentials || [],
        isLoading: false,
      });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to fetch credentials',
      });
    }
  },

  // Clear error
  clearError: () => set({ error: null }),

  // Check if demo mode is enabled
  isDemoMode: () => {
    const status = get().status;
    return status?.enabled ?? false;
  },
}));

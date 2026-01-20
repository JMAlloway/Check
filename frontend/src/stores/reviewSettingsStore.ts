import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ReviewSettings {
  autoAdvance: boolean;
  setAutoAdvance: (enabled: boolean) => void;
}

export const useReviewSettings = create<ReviewSettings>()(
  persist(
    (set) => ({
      autoAdvance: true, // Default to enabled for efficiency
      setAutoAdvance: (enabled: boolean) => set({ autoAdvance: enabled }),
    }),
    {
      name: 'review-settings',
    }
  )
);

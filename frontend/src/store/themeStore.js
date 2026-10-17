import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/** 明暗主题：'light' | 'dark'，持久化到 localStorage */
export const useThemeStore = create(
  persist(
    (set) => ({
      mode: 'light',
      toggle: () => set((s) => ({ mode: s.mode === 'light' ? 'dark' : 'light' })),
      setMode: (mode) => set({ mode }),
    }),
    { name: 'poke-theme-store', partialize: (s) => ({ mode: s.mode }) },
  ),
)

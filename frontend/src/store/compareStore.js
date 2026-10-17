import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/** 对比暂存：最多 3 只，刷新后保留 */
export const useCompareStore = create(
  persist(
    (set) => ({
      ids: [],
      toggle: (id) =>
        set((s) => ({
          ids: s.ids.includes(id)
            ? s.ids.filter((x) => x !== id)
            : [...s.ids, id].slice(-3),
        })),
      remove: (id) => set((s) => ({ ids: s.ids.filter((x) => x !== id) })),
      clear: () => set({ ids: [] }),
    }),
    { name: 'poke-compare-store', partialize: (s) => ({ ids: s.ids }) },
  ),
)

export const COMPARE_MAX = 3

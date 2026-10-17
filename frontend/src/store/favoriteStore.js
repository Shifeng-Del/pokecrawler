import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/** 收藏：localStorage 持久化，ids 为数组（Set 不能直接 JSON 序列化） */
export const useFavoriteStore = create(
  persist(
    (set) => ({
      ids: [],
      toggle: (id) =>
        set((s) => ({
          ids: s.ids.includes(id)
            ? s.ids.filter((x) => x !== id)
            : [...s.ids, id],
        })),
      remove: (id) => set((s) => ({ ids: s.ids.filter((x) => x !== id) })),
      clear: () => set({ ids: [] }),
    }),
    { name: 'poke-favorite-store', partialize: (s) => ({ ids: s.ids }) },
  ),
)

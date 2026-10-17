import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const DEFAULT_FILTERS = {
  q: '',
  types: [],
  typeAny: [],
  ability: undefined,
  minTotal: undefined,
  maxTotal: undefined,
  // P2 物种档案分类（值均为英文 slug；genus 为英文原文如 Seed Pokémon）
  genus: undefined,
  eggGroup: undefined,
  habitat: undefined,
  color: undefined,
  shape: undefined,
  growthRate: undefined,
  sort: 'id',
  order: 'asc',
  favOnly: false,
}

export const useFilterStore = create(
  persist(
    (set) => ({
      filters: { ...DEFAULT_FILTERS },
      setFilters: (patch) => set((s) => ({ filters: { ...s.filters, ...patch } })),
      resetFilters: () => set({ filters: { ...DEFAULT_FILTERS } }),
      pendingType: null,
      setPendingType: (t) => set({ pendingType: t }),
      takePendingType: () => {
        const value = useFilterStore.getState().pendingType
        if (value) set({ pendingType: null })
        return value
      },
      // 全局搜索面板选中某只宝可梦后，跳到列表页并自动打开它的抽屉
      pendingDetailId: null,
      setPendingDetailId: (id) => set({ pendingDetailId: id }),
      takePendingDetailId: () => {
        const value = useFilterStore.getState().pendingDetailId
        if (value) set({ pendingDetailId: null })
        return value
      },
    }),
    {
      name: 'poke-filter-store',
      partialize: (s) => ({ filters: s.filters }),
    },
  ),
)

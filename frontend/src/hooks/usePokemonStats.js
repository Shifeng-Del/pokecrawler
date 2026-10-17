import { useQuery } from '@tanstack/react-query'
import * as api from '@/api/stats'

export const useOverview = () =>
  useQuery({ queryKey: ['stats', 'overview'], queryFn: api.getOverview, staleTime: 30_000 })

export const useTypeDistribution = (metric = 'count') =>
  useQuery({
    queryKey: ['stats', 'type-dist', metric],
    queryFn: () => api.getTypeDistribution(metric),
    staleTime: 60_000,
  })

export const useTypeMatrix = () =>
  useQuery({ queryKey: ['stats', 'type-matrix'], queryFn: api.getTypeMatrix, staleTime: 60_000 })

export const useAbilityTop = (limit = 20) =>
  useQuery({
    queryKey: ['stats', 'ability-top', limit],
    queryFn: () => api.getAbilityTop(limit),
    staleTime: 60_000,
  })

export const useHeightWeight = (mode = 'scatter', type = '') =>
  useQuery({
    queryKey: ['stats', 'hw', mode, type],
    queryFn: () => api.getHeightWeight(mode, type),
    staleTime: 60_000,
  })

export const useRanking = (metric = 'stat_total', limit = 20) =>
  useQuery({
    queryKey: ['stats', 'ranking', metric, limit],
    queryFn: () => api.getRanking(metric, limit),
    staleTime: 60_000,
  })

export const useRadar = (ids = []) =>
  useQuery({
    queryKey: ['stats', 'radar', ids],
    queryFn: () => api.getRadar(ids),
    staleTime: 60_000,
  })

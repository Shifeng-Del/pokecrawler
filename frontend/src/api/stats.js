import client from './client'

export const getOverview = async () => (await client.get('/stats/overview')).data
export const getTypeDistribution = async (metric = 'count') =>
  (await client.get(`/stats/type-distribution?metric=${metric}`)).data
export const getTypeMatrix = async () => (await client.get('/stats/type-matrix')).data
export const getAbilityTop = async (limit = 20) =>
  (await client.get(`/stats/ability-top?limit=${limit}`)).data
export const getHeightWeight = async (mode = 'scatter', type = '') =>
  (await client.get(`/stats/height-weight?mode=${mode}${type ? `&type=${type}` : ''}`)).data
export const getRanking = async (metric = 'stat_total', limit = 20, order = 'desc') =>
  (await client.get(`/stats/ranking?metric=${metric}&limit=${limit}&order=${order}`)).data
export const getRadar = async (ids = []) =>
  (await client.get(`/stats/radar${ids.length ? `?ids=${ids.join(',')}` : ''}`)).data
export const getTypeRadar = async () => (await client.get('/stats/type-radar')).data
export const getCrawlTrend = async () => (await client.get('/stats/crawl-trend')).data

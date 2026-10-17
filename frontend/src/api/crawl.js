import client from './client'

export async function triggerCrawl(payload) {
  const { data } = await client.post('/crawl/trigger', payload)
  return data
}

export async function listJobs(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') search.set(k, v)
  })
  const { data } = await client.get(`/crawl/jobs?${search.toString()}`)
  return data
}

export const getJob = async (id) => (await client.get(`/crawl/jobs/${id}`)).data
export const cancelJob = async (id) => (await client.post(`/crawl/jobs/${id}/cancel`)).data
export const deleteJob = async (id) => (await client.delete(`/crawl/jobs/${id}`)).data

export const getScheduler = async () => (await client.get('/crawl/scheduler')).data
export const runSchedulerNow = async (id) => (await client.post(`/crawl/scheduler/${id}/run-now`)).data
export const pauseScheduler = async (id) => (await client.post(`/crawl/scheduler/${id}/pause`)).data
export const resumeScheduler = async (id) => (await client.post(`/crawl/scheduler/${id}/resume`)).data

export const getRobots = async () => (await client.get('/crawl/robots')).data
export const getFetchers = async () => (await client.get('/crawl/fetchers')).data

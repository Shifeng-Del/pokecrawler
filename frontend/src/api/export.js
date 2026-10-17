import client from './client'
import { buildQuery } from './pokemon'

/** 导出下载：走 blob，避免跨域与中文文件名问题 */
export async function downloadExport(filters = {}, format = 'csv') {
  const query = buildQuery({ ...filters, page: undefined, page_size: undefined })
  const { data } = await client.get(`/export?format=${format}&${query}`, {
    responseType: 'blob',
  })
  const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
  const url = URL.createObjectURL(new Blob([data], { type: 'application/octet-stream' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `pokemon_${stamp}.${format}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const exportUrl = (filters = {}, format = 'csv') =>
  `/api/v1/export?format=${format}&${buildQuery(filters)}`

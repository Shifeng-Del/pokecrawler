import { useQuery } from '@tanstack/react-query'
import { getJob } from '@/api/crawl'

const TERMINAL = ['success', 'failed', 'cancelled']

/** 任务进度：终态自动停止轮询 */
export function useCrawlJob(jobId) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => getJob(jobId),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status || TERMINAL.includes(status)) return false
      return 1000
    },
    staleTime: 0,
  })
}

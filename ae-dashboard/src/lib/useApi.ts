import { useState, useEffect, useCallback } from 'react'
import { api } from './api'

// 通用数据获取 hook
function useApiData<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): { data: T | null; loading: boolean; error: string | null; refetch: () => void } {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetcher()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}

// 系统统计
export function useStats() {
  return useApiData(() => api.getStats())
}

// 系统资源
export function useResources() {
  return useApiData(() => api.getResources())
}

// 效果列表
export function useEffects(category?: string) {
  return useApiData(() => api.getEffects(category), [category])
}

// 风格模板
export function useStyles() {
  return useApiData(() => api.getStyles())
}

// 项目列表
export function useProjects(status?: string) {
  return useApiData(() => api.getProjects({ status }), [status])
}

// 历史记录
export function useHistory(limit = 50) {
  return useApiData(() => api.getHistory({ limit }), [limit])
}

// 任务列表
export function useTasks(status?: string) {
  return useApiData(() => api.getTasks({ status }), [status])
}

// 木偶风格列表
export function usePuppetStyles() {
  return useApiData(() => api.getPuppetStyles())
}

// 质量评估指标
export function useQualityMetrics() {
  return useApiData(() => api.getQualityMetrics())
}

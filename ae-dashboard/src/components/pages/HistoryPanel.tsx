import React, { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/components/ui/Toast'
import { useAppStore, HistoryItem, fallbackHistory } from '@/store/useAppStore'
import { api } from '@/lib/api'
import {
  Clock, CheckCircle2, XCircle, Loader2, ArrowRight, RefreshCw,
  Filter, Search, Download, AlertCircle, ChevronLeft, ChevronRight, Trash2,
} from 'lucide-react'

type ResultFilter = 'all' | 'success' | 'failure' | 'pending'
type TimeRange = 'today' | '7days' | '30days' | 'all'

const resultConfig: Record<HistoryItem['result'], { icon: React.ComponentType<{ className?: string }>; color: string; bg: string }> = {
  success: { icon: CheckCircle2, color: 'text-green-500', bg: 'bg-green-50' },
  failure: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-50' },
  pending: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-50' },
}

const resultFilters: { value: ResultFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'success', label: '成功' },
  { value: 'failure', label: '失败' },
  { value: 'pending', label: '进行中' },
]

const timeRangeOptions: { value: TimeRange; label: string }[] = [
  { value: 'today', label: '今天' },
  { value: '7days', label: '最近 7 天' },
  { value: '30days', label: '最近 30 天' },
  { value: 'all', label: '全部' },
]

const PAGE_SIZE = 20

// 将后端返回的历史记录字段安全转为前端 HistoryItem
function adaptHistory(h: Record<string, unknown>): HistoryItem {
  const toStr = (v: unknown, fallback = ''): string =>
    typeof v === 'string' ? v : v == null ? fallback : String(v)
  const toTimestamp = (v: unknown): string => {
    if (typeof v === 'number' && Number.isFinite(v)) {
      const d = new Date(v * 1000)
      const yyyy = d.getFullYear()
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      const hh = String(d.getHours()).padStart(2, '0')
      const mi = String(d.getMinutes()).padStart(2, '0')
      return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
    }
    if (typeof v === 'string' && v.length > 0) return v
    return ''
  }
  return {
    id: toStr(h.id),
    action: toStr(h.action, '未知操作'),
    timestamp: toTimestamp(h.timestamp),
    result: (h.result as HistoryItem['result']) || 'success',
    details: toStr(h.details),
    projectId: h.projectId as string | undefined,
    params: h.params as Record<string, unknown> | undefined,
  }
}

// 将 timestamp 字符串解析为 Date 用于时间范围筛选
function parseHistoryDate(timestamp: string): Date | null {
  if (!timestamp) return null
  // 支持 "YYYY-MM-DD HH:mm" 与 ISO 格式
  const d = new Date(timestamp.replace(' ', 'T'))
  return isNaN(d.getTime()) ? null : d
}

export function HistoryPanel() {
  const { showToast } = useToast()
  const { clearHistory, setHistory } = useAppStore()

  // 本组件独立维护历史列表（以 API 拉取为准）
  const [history, setLocalHistory] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [usingFallback, setUsingFallback] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  // 客户端筛选
  const [resultFilter, setResultFilter] = useState<ResultFilter>('all')
  const [timeRange, setTimeRange] = useState<TimeRange>('all')
  const [searchTerm, setSearchTerm] = useState('')

  // UI 状态
  const [clearConfirm, setClearConfirm] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const loadHistory = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    setError(null)
    try {
      const params: { limit: number; offset: number; result?: string } = {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }
      // 服务端按结果过滤（result 参数与后端一致）
      if (resultFilter !== 'all') params.result = resultFilter
      const resp = await api.getHistory(params) as {
        history?: HistoryItem[] | Record<string, unknown>[]
        total?: number
      }
      const rawList = resp?.history ?? []
      const adapted = rawList.map(h => adaptHistory(h as Record<string, unknown>))
      setLocalHistory(adapted)
      setHistory(adapted) // 同步到 store
      setTotal(typeof resp?.total === 'number' ? resp.total : adapted.length)
      setUsingFallback(false)
    } catch (err) {
      console.error('[HistoryPanel] 加载历史失败:', err)
      const msg = err instanceof Error ? err.message : '网络错误'
      setError(msg)
      setLocalHistory(fallbackHistory)
      setHistory(fallbackHistory)
      setTotal(fallbackHistory.length)
      setUsingFallback(true)
      showToast('后端不可用，已加载示例数据', 'warning')
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [page, resultFilter, setHistory, showToast])

  useEffect(() => {
    loadHistory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, resultFilter])

  // 客户端二次筛选：时间范围 + 搜索词
  const filteredHistory = history.filter(item => {
    // 时间范围筛选
    if (timeRange !== 'all' && item.timestamp) {
      const itemDate = parseHistoryDate(item.timestamp)
      if (itemDate) {
        const now = new Date()
        const start = new Date(now)
        if (timeRange === 'today') {
          start.setHours(0, 0, 0, 0)
        } else if (timeRange === '7days') {
          start.setDate(now.getDate() - 7)
        } else if (timeRange === '30days') {
          start.setDate(now.getDate() - 30)
        }
        if (itemDate < start) return false
      }
    }
    // 搜索词筛选（action / details）
    if (searchTerm) {
      const term = searchTerm.toLowerCase()
      if (
        !item.action.toLowerCase().includes(term) &&
        !item.details.toLowerCase().includes(term)
      ) {
        return false
      }
    }
    return true
  })

  const handleRefresh = () => loadHistory()

  const handleResultFilterChange = (f: ResultFilter) => {
    setResultFilter(f)
    setPage(1) // 服务端筛选切换时回到第 1 页
  }

  const handleRetry = async (id: string) => {
    const item = history.find(h => h.id === id)
    if (!item) return
    // 先乐观更新本地状态
    setLocalHistory(prev => prev.map(h =>
      h.id === id ? { ...h, result: 'pending' } : h
    ))
    showToast(`正在重试: ${item.action}...`, 'info')
    try {
      // 调用后端添加一条重试记录
      await api.addHistory({
        action: `重试: ${item.action}`,
        result: 'success',
        details: item.details,
        projectId: item.projectId,
      })
      // 重试成功后刷新列表
      setTimeout(() => {
        setLocalHistory(prev => prev.map(h =>
          h.id === id ? { ...h, result: 'success' } : h
        ))
        showToast(`重试成功: ${item.action}`, 'success')
      }, 800)
    } catch (err) {
      console.error('[HistoryPanel] 重试失败:', err)
      // 失败回滚状态
      setLocalHistory(prev => prev.map(h =>
        h.id === id ? { ...h, result: 'failure' } : h
      ))
      showToast('重试失败，请稍后再试', 'error')
    }
  }

  const handleClear = async () => {
    if (!clearConfirm) {
      setClearConfirm(true)
      setTimeout(() => setClearConfirm(false), 3000)
      return
    }
    setClearConfirm(false)
    try {
      await api.clearHistory()
      clearHistory()
      setLocalHistory([])
      setTotal(0)
      showToast('已清空操作历史', 'success')
    } catch (err) {
      console.error('[HistoryPanel] 清空历史失败:', err)
      // 后端不可用时仅清空本地
      clearHistory()
      setLocalHistory([])
      setTotal(0)
      showToast('后端不可用，仅清空本地历史', 'warning')
    }
  }

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(history, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `history-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
    showToast('历史记录已导出', 'success')
  }

  // ===== 加载骨架 =====
  if (loading && history.length === 0) {
    return (
      <div className="p-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">操作历史</h3>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 p-4 animate-pulse">
                  <div className="w-10 h-10 rounded-full bg-secondary" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-secondary rounded w-1/3" />
                    <div className="h-3 bg-secondary rounded w-2/3" />
                  </div>
                  <div className="h-4 bg-secondary rounded w-20" />
                </div>
              ))}
            </div>
            <div className="flex items-center justify-center gap-2 mt-6 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">正在加载历史记录...</span>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // ===== 错误状态（且未降级到 fallback） =====
  if (error && !usingFallback && history.length === 0) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center">
            <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-500" />
            <p className="font-semibold mb-1">加载历史记录失败</p>
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button variant="outline" size="sm" className="gap-1" onClick={handleRefresh}>
              <RefreshCw className="w-3 h-3" />
              重试
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-6">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary" />
            <h3 className="font-semibold">操作历史</h3>
            <Badge variant="secondary">{filteredHistory.length} 条记录</Badge>
            {usingFallback && (
              <Badge className="bg-yellow-100 text-yellow-700">示例数据</Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-1" onClick={handleRefresh} disabled={loading}>
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              刷新
            </Button>
            {history.length > 0 && (
              <>
                <Button variant="outline" size="sm" className="gap-1" onClick={handleExport}>
                  <Download className="w-3 h-3" />
                  导出
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className={`gap-1 ${clearConfirm ? 'bg-red-50 text-red-600 border-red-300' : ''}`}
                  onClick={handleClear}
                >
                  {clearConfirm ? (
                    <>
                      <Trash2 className="w-3 h-3" />
                      确认清空?
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3 h-3" />
                      清空
                    </>
                  )}
                </Button>
              </>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {/* 搜索栏 + 时间范围 + 结果筛选 */}
          <div className="flex flex-col gap-3 mb-4">
            <div className="flex items-center gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="搜索历史记录..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="flex gap-1">
                {timeRangeOptions.map(t => (
                  <button
                    key={t.value}
                    onClick={() => setTimeRange(t.value)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                      timeRange === t.value
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-secondary hover:bg-secondary/80 text-muted-foreground'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-1">
              {resultFilters.map(f => (
                <button
                  key={f.value}
                  onClick={() => handleResultFilterChange(f.value)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    resultFilter === f.value
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary hover:bg-secondary/80 text-muted-foreground'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {filteredHistory.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Filter className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>{searchTerm || timeRange !== 'all' ? '未找到匹配的记录' : '暂无操作记录'}</p>
            </div>
          ) : (
            <div className="space-y-0">
              {filteredHistory.map((item) => {
                const cfg = resultConfig[item.result] || resultConfig.success
                const Icon = cfg.icon
                return (
                  <div key={item.id} className={`border-b last:border-b-0`}>
                    <div
                      className="flex items-center gap-4 p-4 hover:bg-secondary/30 cursor-pointer"
                      onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                    >
                      <div className={`w-10 h-10 rounded-full ${cfg.bg} flex items-center justify-center flex-shrink-0`}>
                        <Icon className={`w-5 h-5 ${cfg.color} ${item.result === 'pending' ? 'animate-spin' : ''}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{item.action}</span>
                          {item.result === 'success' && (
                            <ArrowRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground truncate">{item.details}</p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className="text-sm">{item.timestamp}</p>
                        {item.result === 'failure' && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleRetry(item.id) }}
                            className="mt-1 text-xs text-primary hover:text-primary/80 flex items-center gap-1 ml-auto"
                          >
                            <RefreshCw className="w-3 h-3" />
                            重试
                          </button>
                        )}
                      </div>
                    </div>
                    {/* 展开详情 */}
                    {expandedId === item.id && (
                      <div className="px-4 pb-4 pl-18 ml-14">
                        <div className="p-3 rounded-lg bg-secondary/50 space-y-2">
                          <div className="flex gap-4 text-sm">
                            <span className="text-muted-foreground">记录ID:</span>
                            <span className="font-mono">{item.id}</span>
                          </div>
                          {item.projectId && (
                            <div className="flex gap-4 text-sm">
                              <span className="text-muted-foreground">关联项目:</span>
                              <span className="font-mono">{item.projectId}</span>
                            </div>
                          )}
                          {item.params && (
                            <div className="text-sm">
                              <span className="text-muted-foreground">参数:</span>
                              <pre className="mt-1 p-2 rounded bg-gray-900 text-gray-100 text-xs overflow-x-auto">
                                {JSON.stringify(item.params, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* 分页 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 mt-6 pt-4 border-t">
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                disabled={page <= 1 || loading}
                onClick={() => setPage(p => Math.max(1, p - 1))}
              >
                <ChevronLeft className="w-4 h-4" />
                上一页
              </Button>
              <span className="text-sm text-muted-foreground">
                第 {page} / {totalPages} 页（共 {total} 条）
              </span>
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                disabled={page >= totalPages || loading}
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              >
                下一页
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

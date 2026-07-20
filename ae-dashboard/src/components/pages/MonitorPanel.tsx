import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Activity, Cpu, HardDrive, MemoryStick, AlertTriangle,
  RefreshCw, Play, Pause, Search,
} from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/Toast'

// ============================================================
// 类型定义 - 对齐后端响应结构
// ============================================================

interface ResourceSnapshot {
  timestamp: number
  available: boolean
  reason?: string
  cpu_percent?: number
  cpu_per_core?: number[]
  cpu_count?: number
  memory?: {
    total_mb: number
    used_mb: number
    available_mb: number
    percent: number
  }
  disk?: {
    total_gb: number
    used_gb: number
    free_gb: number
    percent: number
  }
  gpu?: GpuInfo[]
  gpu_available?: boolean
}

interface GpuInfo {
  index: number
  name: string
  gpu_percent: number
  memory_percent: number
  memory_used_mb: number
  memory_total_mb: number
}

interface Thresholds {
  cpu_percent?: number
  memory_percent?: number
  disk_percent?: number
}

interface SystemResourcesResponse {
  success: boolean
  snapshot: ResourceSnapshot
  thresholds: Thresholds
}

interface HistoryResponse {
  success: boolean
  sample_count: number
  limit: number
  history: ResourceSnapshot[]
  stats?: Record<string, unknown>
  recent_alerts?: Array<{
    timestamp: number
    metric: string
    value: number
    threshold: number
    severity: 'critical' | 'warning'
    message: string
  }>
}

interface RenderProgressInfo {
  current_frame: number
  total_frames: number
  percent: number
  elapsed_seconds: number
  estimated_remaining_seconds: number
  frames_per_second: number
  current_layer: string
  status: string
  current_phase?: string | null
}

interface RenderProgressResponse {
  success: boolean
  job_id: string
  source: string
  progress: RenderProgressInfo
}

// ============================================================
// 常量配置
// ============================================================

const REFRESH_INTERVAL_MS = 5000
const HISTORY_LIMIT = 100
// 阈值告警门槛（与后端默认阈值对齐）
const CPU_ALERT_THRESHOLD = 80
const MEMORY_ALERT_THRESHOLD = 85

type MetricKey = 'cpu' | 'memory' | 'disk' | 'gpu'

interface MetricCardConfig {
  key: MetricKey
  icon: typeof Cpu
  label: string
  color: string
  bg: string
  bar: string
}

const METRIC_CARDS: MetricCardConfig[] = [
  { key: 'cpu', icon: Cpu, label: 'CPU 使用率', color: 'text-blue-500', bg: 'bg-blue-500/10', bar: 'bg-blue-500' },
  { key: 'memory', icon: MemoryStick, label: '内存使用率', color: 'text-purple-500', bg: 'bg-purple-500/10', bar: 'bg-purple-500' },
  { key: 'disk', icon: HardDrive, label: '磁盘使用率', color: 'text-amber-500', bg: 'bg-amber-500/10', bar: 'bg-amber-500' },
  { key: 'gpu', icon: Activity, label: 'GPU 使用率', color: 'text-green-500', bg: 'bg-green-500/10', bar: 'bg-green-500' },
]

// ============================================================
// 主组件
// ============================================================

export function MonitorPanel() {
  const { showToast } = useToast()

  // 资源快照与历史
  const [snapshot, setSnapshot] = useState<ResourceSnapshot | null>(null)
  const [history, setHistory] = useState<ResourceSnapshot[]>([])
  const [thresholds, setThresholds] = useState<Thresholds>({})

  // 自动刷新
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [loading, setLoading] = useState(false)

  // 渲染进度查询
  const [jobIdInput, setJobIdInput] = useState('')
  const [renderProgress, setRenderProgress] = useState<RenderProgressResponse | null>(null)
  const [renderLoading, setRenderLoading] = useState(false)
  const [renderError, setRenderError] = useState<string | null>(null)

  // 保持最新 job_id 引用，供轮询使用
  const activeJobIdRef = useRef<string | null>(null)

  // ---------- 数据拉取 ----------
  const fetchResources = useCallback(async () => {
    try {
      const res = await api.getSystemResources()
      const data = res as SystemResourcesResponse
      setSnapshot(data.snapshot)
      setThresholds(data.thresholds || {})
    } catch {
      // 静默失败，避免自动刷新时刷屏
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const res = await api.getSystemResourcesHistory({ limit: HISTORY_LIMIT })
      const data = res as HistoryResponse
      setHistory(data.history || [])
    } catch {
      // 静默失败
    }
  }, [])

  const refreshAll = useCallback(async (showIndicator = false) => {
    if (showIndicator) setLoading(true)
    await Promise.all([fetchResources(), fetchHistory()])
    if (showIndicator) setLoading(false)
  }, [fetchResources, fetchHistory])

  const fetchRenderProgress = useCallback(async (jobId: string) => {
    setRenderLoading(true)
    setRenderError(null)
    try {
      const res = await api.getRenderProgress(jobId)
      setRenderProgress(res as RenderProgressResponse)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '查询失败'
      setRenderError(msg)
      setRenderProgress(null)
    } finally {
      setRenderLoading(false)
    }
  }, [])

  // ---------- 自动刷新 ----------
  useEffect(() => {
    // 首次立即拉取
    refreshAll(true)
  }, [refreshAll])

  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(() => {
      fetchResources()
      fetchHistory()
      // 若有活跃渲染任务，且未完成/失败，则轮询进度
      const activeJob = activeJobIdRef.current
      if (activeJob) {
        api.getRenderProgress(activeJob)
          .then((res) => {
            const data = res as RenderProgressResponse
            setRenderProgress(data)
            const st = data.progress?.status
            if (st === 'completed' || st === 'failed') {
              activeJobIdRef.current = null
            }
          })
          .catch(() => {
            // 静默
          })
      }
    }, REFRESH_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [autoRefresh, fetchResources, fetchHistory])

  // ---------- 渲染进度查询 ----------
  const handleQueryProgress = () => {
    const id = jobIdInput.trim()
    if (!id) {
      showToast('请输入渲染任务 ID', 'warning')
      return
    }
    activeJobIdRef.current = id
    fetchRenderProgress(id)
  }

  const handleStopPolling = () => {
    activeJobIdRef.current = null
    showToast('已停止轮询该任务进度', 'info')
  }

  // ---------- 派生数据 ----------
  const cpuPercent = snapshot?.cpu_percent ?? 0
  const memoryPercent = snapshot?.memory?.percent ?? 0
  const diskPercent = snapshot?.disk?.percent ?? 0
  const gpuPercent = snapshot?.gpu?.[0]?.gpu_percent ?? 0

  // 阈值告警（优先用后端返回的阈值，回退到默认值）
  const cpuThreshold = thresholds.cpu_percent ?? CPU_ALERT_THRESHOLD
  const memoryThreshold = thresholds.memory_percent ?? MEMORY_ALERT_THRESHOLD

  const alerts: Array<{ metric: string; value: number; threshold: number }> = []
  if (cpuPercent > cpuThreshold) {
    alerts.push({ metric: 'CPU', value: cpuPercent, threshold: cpuThreshold })
  }
  if (memoryPercent > memoryThreshold) {
    alerts.push({ metric: '内存', value: memoryPercent, threshold: memoryThreshold })
  }

  const metricValueMap: Record<MetricKey, number> = {
    cpu: cpuPercent,
    memory: memoryPercent,
    disk: diskPercent,
    gpu: gpuPercent,
  }

  const metricDetailMap: Record<MetricKey, string> = {
    cpu: snapshot?.cpu_count ? `${snapshot.cpu_count} 核` : '',
    memory: snapshot?.memory ? `${formatMb(snapshot.memory.used_mb)} / ${formatMb(snapshot.memory.total_mb)}` : '',
    disk: snapshot?.disk ? `${formatGb(snapshot.disk.used_gb)} / ${formatGb(snapshot.disk.total_gb)}` : '',
    gpu: snapshot?.gpu?.[0]?.name || (snapshot?.gpu_available ? '已就绪' : '不可用'),
  }

  // 最近 5 分钟历史（按时间戳过滤）
  const fiveMinAgo = Date.now() / 1000 - 300
  const recentHistory = history.filter((s) => s.timestamp >= fiveMinAgo)
  const cpuSeries = recentHistory.map((s) => s.cpu_percent ?? 0)
  const memorySeries = recentHistory.map((s) => s.memory?.percent ?? 0)

  return (
    <div className="p-6 space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">系统监控</h3>
          <p className="text-sm text-muted-foreground">实时监控 CPU / 内存 / 磁盘 / GPU 与渲染进度</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={autoRefresh ? 'default' : 'outline'}
            size="sm"
            onClick={() => setAutoRefresh((v) => !v)}
            title={autoRefresh ? '暂停自动刷新' : '开启自动刷新'}
          >
            {autoRefresh ? <Pause className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
            {autoRefresh ? '自动刷新中' : '已暂停'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refreshAll(true)}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>
      </div>

      {/* 阈值告警条 */}
      {alerts.length > 0 && (
        <Card className="p-4 border-red-300 bg-red-50">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-red-700">资源告警</p>
              <div className="mt-1 space-y-1">
                {alerts.map((a, i) => (
                  <p key={i} className="text-sm text-red-600">
                    {a.metric} 使用率 {a.value.toFixed(1)}% 已超过阈值 {a.threshold}%，请关注系统负载
                  </p>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* 资源不可用提示 */}
      {snapshot && !snapshot.available && (
        <Card className="p-4 border-amber-300 bg-amber-50">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />
            <p className="text-sm text-amber-700">
              资源监控不可用：{snapshot.reason || '未知原因'}
            </p>
          </div>
        </Card>
      )}

      {/* 4 个资源指标卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {METRIC_CARDS.map((card) => {
          const value = metricValueMap[card.key]
          const detail = metricDetailMap[card.key]
          return (
            <Card key={card.key} className="p-5">
              <div className="flex items-start justify-between">
                <div className={`w-10 h-10 rounded-lg ${card.bg} flex items-center justify-center`}>
                  <card.icon className={`w-5 h-5 ${card.color}`} />
                </div>
                <span className={`text-xs font-medium ${card.color}`}>
                  {value > (card.key === 'cpu' ? CPU_ALERT_THRESHOLD : card.key === 'memory' ? MEMORY_ALERT_THRESHOLD : 100)
                    ? '告警'
                    : '正常'}
                </span>
              </div>
              <div className="mt-4">
                <p className="text-2xl font-bold">
                  {value.toFixed(1)}
                  <span className="text-sm font-normal text-muted-foreground ml-1">%</span>
                </p>
                <p className="text-sm text-muted-foreground mt-1">{card.label}</p>
                {detail && (
                  <p className="text-xs text-muted-foreground mt-1 truncate">{detail}</p>
                )}
              </div>
              {/* 进度条 */}
              <div className="mt-3 w-full h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className={`h-full ${card.bar} transition-all duration-500 rounded-full`}
                  style={{ width: `${Math.min(value, 100)}%` }}
                />
              </div>
            </Card>
          )
        })}
      </div>

      {/* 历史趋势图 + 渲染进度 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CPU / 内存 历史趋势图 */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-semibold">历史趋势（最近 5 分钟）</h4>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm bg-blue-500" />
                <span className="text-muted-foreground">CPU</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm bg-purple-500" />
                <span className="text-muted-foreground">内存</span>
              </span>
            </div>
          </div>
          <TrendChart
            cpuSeries={cpuSeries}
            memorySeries={memorySeries}
            emptyHint="暂无历史采样数据"
          />
          <p className="text-xs text-muted-foreground mt-2">
            采样点：{recentHistory.length} 条
          </p>
        </Card>

        {/* 渲染任务进度 */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-semibold">渲染任务进度</h4>
            {activeJobIdRef.current && autoRefresh && (
              <Badge variant="secondary">轮询中</Badge>
            )}
          </div>

          {/* job_id 输入 */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="输入渲染任务 ID..."
                value={jobIdInput}
                onChange={(e) => setJobIdInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleQueryProgress()
                }}
                className="pl-9"
              />
            </div>
            <Button size="sm" onClick={handleQueryProgress} disabled={renderLoading}>
              {renderLoading ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Search className="w-4 h-4 mr-1" />}
              查询
            </Button>
            {activeJobIdRef.current && (
              <Button variant="outline" size="sm" onClick={handleStopPolling}>
                停止轮询
              </Button>
            )}
          </div>

          {/* 渲染进度展示 */}
          <div className="mt-4">
            {renderError && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-600">
                查询失败：{renderError}
              </div>
            )}
            {!renderProgress && !renderError && !renderLoading && (
              <div className="text-center py-8 text-muted-foreground">
                <Activity className="w-10 h-10 mx-auto mb-2 opacity-40" />
                <p className="text-sm">输入任务 ID 查询渲染进度</p>
              </div>
            )}
            {renderProgress && (
              <RenderProgressView data={renderProgress} />
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

// ============================================================
// 子组件：历史趋势折线图（纯 SVG）
// ============================================================

interface TrendChartProps {
  cpuSeries: number[]
  memorySeries: number[]
  emptyHint?: string
}

function TrendChart({ cpuSeries, memorySeries, emptyHint }: TrendChartProps) {
  const width = 480
  const height = 160
  const padding = { top: 10, right: 10, bottom: 20, left: 32 }
  const innerWidth = width - padding.left - padding.right
  const innerHeight = height - padding.top - padding.bottom

  const maxPoints = Math.max(cpuSeries.length, memorySeries.length)
  if (maxPoints < 2) {
    return (
      <div className="flex items-center justify-center text-sm text-muted-foreground" style={{ height }}>
        {emptyHint || '数据不足'}
      </div>
    )
  }

  const toPoints = (series: number[]) => {
    if (series.length < 2) return ''
    const step = innerWidth / (series.length - 1)
    return series
      .map((v, i) => {
        const x = padding.left + i * step
        const y = padding.top + innerHeight - (Math.min(v, 100) / 100) * innerHeight
        return `${x.toFixed(2)},${y.toFixed(2)}`
      })
      .join(' ')
  }

  const cpuPoints = toPoints(cpuSeries)
  const memoryPoints = toPoints(memorySeries)
  const yTicks = [0, 25, 50, 75, 100]

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      preserveAspectRatio="none"
      role="img"
      aria-label="CPU 与内存历史趋势"
    >
      {/* Y 轴刻度线 */}
      {yTicks.map((tick) => {
        const y = padding.top + innerHeight - (tick / 100) * innerHeight
        return (
          <g key={tick}>
            <line
              x1={padding.left}
              y1={y}
              x2={width - padding.right}
              y2={y}
              stroke="currentColor"
              strokeOpacity={0.1}
              strokeWidth={1}
            />
            <text
              x={padding.left - 6}
              y={y + 3}
              textAnchor="end"
              fontSize={9}
              fill="currentColor"
              fillOpacity={0.5}
            >
              {tick}
            </text>
          </g>
        )
      })}

      {/* CPU 折线 */}
      <polyline
        points={cpuPoints}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* 内存折线 */}
      <polyline
        points={memoryPoints}
        fill="none"
        stroke="#a855f7"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {/* X 轴 */}
      <line
        x1={padding.left}
        y1={height - padding.bottom}
        x2={width - padding.right}
        y2={height - padding.bottom}
        stroke="currentColor"
        strokeOpacity={0.2}
        strokeWidth={1}
      />
    </svg>
  )
}

// ============================================================
// 子组件：渲染进度视图
// ============================================================

function RenderProgressView({ data }: { data: RenderProgressResponse }) {
  const { progress } = data
  const percent = Math.min(Math.max(progress.percent, 0), 100)
  const status = progress.status || 'idle'

  const statusBadge = (() => {
    switch (status) {
      case 'rendering':
        return <Badge variant="default">渲染中</Badge>
      case 'completed':
        return <Badge variant="success">已完成</Badge>
      case 'failed':
        return <Badge variant="destructive">失败</Badge>
      case 'idle':
        return <Badge variant="secondary">等待中</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  })()

  const isRunning = status === 'rendering'

  return (
    <div className="space-y-3">
      {/* 顶部：job_id + 状态 */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-muted-foreground flex-shrink-0">任务</span>
          <span className="text-sm font-mono truncate" title={data.job_id}>{data.job_id}</span>
        </div>
        {statusBadge}
      </div>

      {/* 进度条 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-sm font-medium">{percent.toFixed(1)}%</span>
          <span className="text-xs text-muted-foreground">
            {isRunning && progress.frames_per_second > 0
              ? `${progress.frames_per_second.toFixed(2)} fps`
              : ''}
          </span>
        </div>
        <div className="w-full h-3 bg-secondary rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 rounded-full ${
              status === 'failed' ? 'bg-red-500' : status === 'completed' ? 'bg-green-500' : 'bg-blue-500'
            }`}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* 帧信息 */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="bg-secondary/30 rounded-lg p-3">
          <p className="text-xs text-muted-foreground">当前帧 / 总帧数</p>
          <p className="font-mono mt-0.5">
            {progress.current_frame} / {progress.total_frames}
          </p>
        </div>
        <div className="bg-secondary/30 rounded-lg p-3">
          <p className="text-xs text-muted-foreground">已耗时 / 预计剩余</p>
          <p className="font-mono mt-0.5">
            {formatDuration(progress.elapsed_seconds)} / {formatDuration(progress.estimated_remaining_seconds)}
          </p>
        </div>
      </div>

      {/* 当前图层 / 阶段 */}
      {(progress.current_layer || progress.current_phase) && (
        <div className="text-xs text-muted-foreground">
          {progress.current_layer && <span>图层：{progress.current_layer}</span>}
          {progress.current_layer && progress.current_phase && <span className="mx-2">·</span>}
          {progress.current_phase && <span>阶段：{progress.current_phase}</span>}
        </div>
      )}

      {/* 数据来源 */}
      <div className="text-xs text-muted-foreground">
        数据来源：
        <span className="font-mono">{data.source}</span>
      </div>
    </div>
  )
}

// ============================================================
// 工具函数
// ============================================================

function formatMb(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${mb.toFixed(0)} MB`
}

function formatGb(gb: number): string {
  if (gb >= 1024) return `${(gb / 1024).toFixed(1)} TB`
  return `${gb.toFixed(1)} GB`
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return '0s'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

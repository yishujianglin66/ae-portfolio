import { useState, useEffect, useRef, useCallback } from 'react'
import { Play, RotateCcw, Download, CheckCircle2, XCircle, Loader2, Film, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

// ============================================================================
//  Types
// ============================================================================

interface StageStatus {
  stage_id: string
  label: string
  status: 'pending' | 'running' | 'passed' | 'failed' | 'skipped'
  elapsed_s?: number
  error?: string
}

interface FlagshipRun {
  run_id: string
  status: 'idle' | 'running' | 'completed' | 'failed'
  stages: StageStatus[]
  created_at?: string
  final_mp4_url?: string
}

const STAGE_LABELS: Record<string, string> = {
  S0_health: 'S0 健康检查',
  S1_assets: 'S1 素材规范化',
  S2_beat: 'S2 节拍分析',
  S3_ae: 'S3 AE 合成',
  S4_premiere: 'S4 PR 粗剪',
  S5_davinci: 'S5 DaVinci 调色',
  S6_export: 'S6 AME 导出',
  S7_qg: 'S7 质量门',
}

const API_BASE = '/api/v1/flagship'

// ============================================================================
//  Component
// ============================================================================

export function FlagshipPipeline() {
  const [run, setRun] = useState<FlagshipRun | null>(null)
  const [isExecuting, setIsExecuting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const getToken = () => localStorage.getItem('ae_token') || ''

  const apiRequest = useCallback(async (path: string, options?: RequestInit) => {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`,
        ...(options?.headers || {}),
      },
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || `HTTP ${res.status}`)
    }
    return res.json()
  }, [])

  // WebSocket 连接（带降级轮询）
  const connectWs = useCallback((runId: string) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${API_BASE}/ws/${runId}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setRun(data)
        } catch { /* ignore parse errors */ }
      }

      ws.onclose = () => {
        // 降级：5s 轮询
        startPolling(runId)
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch {
      startPolling(runId)
    }
  }, [])

  const startPolling = useCallback((runId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const data = await apiRequest(`/${runId}/status`)
        setRun(data)
        if (data.status === 'completed' || data.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current)
          setIsExecuting(false)
        }
      } catch { /* ignore */ }
    }, 5000)
  }, [apiRequest])

  // 执行旗舰管线
  const handleExecute = async () => {
    setIsExecuting(true)
    setError(null)
    setVideoUrl(null)
    try {
      const data = await apiRequest('/execute', { method: 'POST' })
      setRun(data)
      if (data.run_id) {
        connectWs(data.run_id)
      }
    } catch (e: any) {
      setError(e.message || '执行失败')
      setIsExecuting(false)
    }
  }

  // Resume
  const handleResume = async () => {
    if (!run?.run_id) return
    setIsExecuting(true)
    setError(null)
    try {
      const data = await apiRequest(`/${run.run_id}/resume`, { method: 'POST' })
      setRun(data)
    } catch (e: any) {
      setError(e.message || 'Resume 失败')
      setIsExecuting(false)
    }
  }

  // 下载产物
  const handleDownload = async (stage: string) => {
    if (!run?.run_id) return
    try {
      const res = await fetch(`${API_BASE}/${run.run_id}/download/${stage}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
      })
      if (res.ok) {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${stage}_output`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch { /* ignore */ }
  }

  // 清理
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // 检测完成 → 设置视频预览
  useEffect(() => {
    if (run?.status === 'completed' && run.run_id) {
      setVideoUrl(`${API_BASE}/${run.run_id}/download/S6_export`)
      setIsExecuting(false)
    }
    if (run?.status === 'failed') {
      setIsExecuting(false)
    }
  }, [run?.status, run?.run_id])

  const stages: StageStatus[] = run?.stages || Object.entries(STAGE_LABELS).map(([id, label]) => ({
    stage_id: id,
    label,
    status: 'pending' as const,
    elapsed_s: undefined,
    error: undefined,
  }))

  const progress = stages.filter(s => s.status === 'passed' || s.status === 'failed').length
  const progressPct = Math.round((progress / stages.length) * 100)

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Film className="w-6 h-6 text-primary" />
            旗舰管线
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            S0→S7 全链路跨软件自动化（AE / PR / DaVinci / AME）
          </p>
        </div>
        <div className="flex gap-2">
          {run?.status === 'failed' && (
            <button
              onClick={handleResume}
              disabled={isExecuting}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" />
              Resume
            </button>
          )}
          <button
            onClick={handleExecute}
            disabled={isExecuting}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {isExecuting ? '执行中...' : 'Execute'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>进度</span>
          <span>{progressPct}%</span>
        </div>
        <div className="h-2 bg-secondary rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              run?.status === 'failed' ? 'bg-destructive' : 'bg-primary'
            )}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Stage Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {stages.map((stage) => (
          <div
            key={stage.stage_id}
            className={cn(
              'p-4 rounded-xl border transition-colors',
              stage.status === 'running' && 'border-primary bg-primary/5',
              stage.status === 'passed' && 'border-green-500/50 bg-green-500/5',
              stage.status === 'failed' && 'border-destructive/50 bg-destructive/5',
              stage.status === 'pending' && 'border-border',
            )}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-muted-foreground">{stage.stage_id}</span>
              {stage.status === 'running' && <Loader2 className="w-4 h-4 animate-spin text-primary" />}
              {stage.status === 'passed' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
              {stage.status === 'failed' && <XCircle className="w-4 h-4 text-destructive" />}
            </div>
            <p className="text-sm font-medium">{stage.label || STAGE_LABELS[stage.stage_id]}</p>
            {stage.elapsed_s != null && (
              <p className="text-xs text-muted-foreground mt-1">{stage.elapsed_s.toFixed(1)}s</p>
            )}
            {stage.error && (
              <p className="text-xs text-destructive mt-1 line-clamp-2">{stage.error}</p>
            )}
            {stage.status === 'passed' && (
              <button
                onClick={() => handleDownload(stage.stage_id)}
                className="mt-2 flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <Download className="w-3 h-3" />
                下载产物
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Video Preview */}
      {videoUrl && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium">最终产物预览</h3>
          <video
            src={videoUrl}
            controls
            className="w-full max-w-2xl rounded-xl border"
          />
        </div>
      )}
    </div>
  )
}

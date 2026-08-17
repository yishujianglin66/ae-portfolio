/**
 * EvolutionPanel - 自进化闭环观测面板 (P2)
 *
 * 数据源: GET /api/v1/evolution/{summary,decisions,cost,knowledge}
 * 展示: 分数趋势 / 版本决策统计 / 成本观测 / 知识沉淀
 */
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { TrendingUp, GitCommit, Coins, Brain, RefreshCw, Loader2 } from 'lucide-react'

interface ScorePoint {
  run_id: string
  scope: string
  score: number
  timestamp: number
}

interface Summary {
  score_trend: ScorePoint[]
  decisions: { total: number; accept: number; rollback: number; rollback_rate: number }
  cost: { total_tokens: number; total_cost_usd: number; evolution_cycles: number }
  versions: { version_id: string; scope: string; status: string; created_at: number }[]
  knowledge: Record<string, unknown>
  avg_score: number
}

interface Decision {
  scope?: string
  decision?: string
  score?: number
  best_score?: number
  version_id?: string
  reason?: string
  timestamp?: number
}

interface Lesson {
  scope?: string
  decision?: string
  lesson?: string
  score?: number
  timestamp?: number
}

function fmtTime(ts: unknown): string {
  const n = Number(ts || 0)
  if (!n) return '-'
  const d = new Date(n > 1e12 ? n : n * 1000)
  return isNaN(d.getTime()) ? '-' : d.toLocaleString('zh-CN', { hour12: false })
}

function ScoreTrendChart({ points }: { points: ScorePoint[] }) {
  if (!points.length) {
    return <p className="text-sm text-muted-foreground">暂无评测数据</p>
  }
  const w = 560
  const h = 120
  const max = Math.max(...points.map(p => p.score), 100)
  const min = Math.min(...points.map(p => p.score), 0)
  const span = Math.max(max - min, 1)
  const step = points.length > 1 ? w / (points.length - 1) : 0
  const pts = points
    .map((p, i) => `${(i * step).toFixed(1)},${(h - ((p.score - min) / span) * h).toFixed(1)}`)
    .join(' ')
  return (
    <div>
      <svg width={w} height={h + 20} className="overflow-visible">
        <polyline points={pts} fill="none" stroke="hsl(var(--primary))" strokeWidth={2} />
        {points.map((p, i) => (
          <circle
            key={p.run_id + i}
            cx={i * step}
            cy={h - ((p.score - min) / span) * h}
            r={3}
            fill="hsl(var(--primary))"
          >
            <title>{`${p.scope} | ${p.score.toFixed(1)} | ${fmtTime(p.timestamp)}`}</title>
          </circle>
        ))}
      </svg>
      <div className="flex justify-between text-xs text-muted-foreground mt-1">
        <span>最早</span>
        <span>最近 {points.length} 次评测</span>
      </div>
    </div>
  )
}

export function EvolutionPanel() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, d, k] = await Promise.all([
        api.getEvolutionSummary(),
        api.getEvolutionDecisions({ limit: 30 }),
        api.getEvolutionKnowledge(15),
      ])
      setSummary(s as Summary)
      setDecisions(((d as { decisions?: Decision[] }).decisions || []).slice().reverse())
      setLessons(((k as { lessons?: Lesson[] }).lessons || []).slice().reverse())
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const stats = [
    {
      icon: TrendingUp,
      label: '平均评分',
      value: summary ? summary.avg_score.toFixed(1) : '-',
      sub: summary ? `最近 ${summary.score_trend.length} 次评测` : '',
    },
    {
      icon: GitCommit,
      label: '版本决策',
      value: summary ? `${summary.decisions.accept} / ${summary.decisions.rollback}` : '-',
      sub: summary ? `accept / rollback（回退率 ${(summary.decisions.rollback_rate * 100).toFixed(1)}%）` : '',
    },
    {
      icon: Coins,
      label: '累计成本',
      value: summary ? `${summary.cost.total_tokens.toLocaleString()} tokens` : '-',
      sub: summary ? `$${summary.cost.total_cost_usd.toFixed(4)} / ${summary.cost.evolution_cycles} 轮进化` : '',
    },
    {
      icon: Brain,
      label: '知识沉淀',
      value: String(lessons.length || 0),
      sub: '条进化经验',
    },
  ]

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          自进化闭环：评测 → Optimizer 提案 → 版本决策 → 知识沉淀（文件即真相）
        </p>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 text-sm"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          刷新
        </button>
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {/* 概览卡片 */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map((s) => (
          <Card key={s.label} className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs">
              <s.icon className="w-4 h-4" />
              {s.label}
            </div>
            <p className="text-2xl font-bold mt-2">{s.value}</p>
            <p className="text-xs text-muted-foreground mt-1">{s.sub}</p>
          </Card>
        ))}
      </div>

      {/* 分数趋势 */}
      <Card className="p-4">
        <h3 className="text-sm font-medium mb-3">评测分数趋势</h3>
        <ScoreTrendChart points={summary?.score_trend || []} />
      </Card>

      <div className="grid grid-cols-2 gap-4">
        {/* 版本决策 */}
        <Card className="p-4">
          <h3 className="text-sm font-medium mb-3">最近版本决策</h3>
          {decisions.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无决策记录</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {decisions.map((d, i) => (
                <div key={i} className="flex items-start gap-2 text-sm border-b pb-2">
                  <Badge
                    variant={d.decision === 'accept' ? 'default' : 'secondary'}
                    className={d.decision === 'accept' ? '' : 'bg-destructive/20 text-destructive'}
                  >
                    {d.decision || '-'}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs">
                      <span className="font-medium">{d.scope || '-'}</span>
                      {' · '}score {(Number(d.score) || 0).toFixed(1)} / best {(Number(d.best_score) || 0).toFixed(1)}
                      {' · '}
                      {d.version_id || '-'}
                    </p>
                    {d.reason && (
                      <p className="text-xs text-muted-foreground truncate" title={d.reason}>
                        {d.reason}
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">{fmtTime(d.timestamp)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* 知识沉淀 */}
        <Card className="p-4">
          <h3 className="text-sm font-medium mb-3">进化知识沉淀</h3>
          {lessons.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无知识条目</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {lessons.map((l, i) => (
                <div key={i} className="text-sm border-b pb-2">
                  <p className="text-xs">
                    <Badge variant="outline">{l.scope || '-'}</Badge>
                    <span className="ml-2 text-muted-foreground">{l.decision || '-'}</span>
                    <span className="ml-2 text-muted-foreground">{fmtTime(l.timestamp)}</span>
                  </p>
                  <p className="text-xs mt-1">{l.lesson || `score ${(Number(l.score) || 0).toFixed(1)}`}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* 版本列表 */}
      <Card className="p-4">
        <h3 className="text-sm font-medium mb-3">版本档案（最近 20 个）</h3>
        {!summary?.versions?.length ? (
          <p className="text-sm text-muted-foreground">暂无版本</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground border-b">
                <th className="py-2">版本</th>
                <th className="py-2">作用域</th>
                <th className="py-2">状态</th>
                <th className="py-2">创建时间</th>
              </tr>
            </thead>
            <tbody>
              {summary.versions.map((v) => (
                <tr key={v.version_id} className="border-b last:border-0">
                  <td className="py-2 font-mono text-xs">{v.version_id}</td>
                  <td className="py-2">{v.scope || '-'}</td>
                  <td className="py-2">
                    <Badge variant={v.status === 'active' ? 'default' : 'secondary'}>{v.status}</Badge>
                  </td>
                  <td className="py-2 text-xs text-muted-foreground">{fmtTime(v.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

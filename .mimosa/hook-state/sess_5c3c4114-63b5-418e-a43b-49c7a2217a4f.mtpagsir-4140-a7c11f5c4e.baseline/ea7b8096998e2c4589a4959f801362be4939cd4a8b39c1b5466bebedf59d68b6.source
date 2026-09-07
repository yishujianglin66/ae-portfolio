import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useAppStore } from '@/store/useAppStore'
import { mockEffects, mockStyleTemplates } from '@/data/mockData'
import { api } from '@/lib/api'
import { Sparkles, Clock, CheckCircle2, XCircle, Loader2, Play, ArrowRight } from 'lucide-react'

interface DashboardProps {
  onNavigate?: (page: string) => void
}

export function Dashboard({ onNavigate }: DashboardProps = {}) {
  const { projects, history } = useAppStore()
  // 资源统计数量：默认回退到 mock 数据长度，API 成功后覆盖
  const [effectsCount, setEffectsCount] = useState(mockEffects.length)
  const [stylesCount, setStylesCount] = useState(mockStyleTemplates.length)

  // 组件挂载时调用 API 获取效果/风格数量
  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const res: any = await api.getEffects()
        const list: any[] = Array.isArray(res) ? res
          : Array.isArray(res?.items) ? res.items
          : Array.isArray(res?.data) ? res.data
          : Array.isArray(res?.effects) ? res.effects
          : []
        if (mounted) setEffectsCount(list.length)
      } catch {
        // API 失败时回退到 mockEffects.length
      }
      try {
        const res: any = await api.getStyles()
        const list: any[] = Array.isArray(res) ? res
          : Array.isArray(res?.items) ? res.items
          : Array.isArray(res?.data) ? res.data
          : Array.isArray(res?.styles) ? res.styles
          : []
        if (mounted) setStylesCount(list.length)
      } catch {
        // API 失败时回退到 mockStyleTemplates.length
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  const completedProjects = projects.filter(p => p.status === 'completed').length
  const processingProjects = projects.filter(p => p.status === 'processing').length
  const failedProjects = projects.filter(p => p.status === 'failed').length
  const totalExecuted = completedProjects + failedProjects
  const successRate = totalExecuted > 0 ? ((completedProjects / totalExecuted) * 100).toFixed(0) : '0'

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-4 gap-4">
        <Card className="cursor-pointer hover:shadow-lg transition-shadow" onClick={() => onNavigate?.('projects')}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">项目总数</p>
                <p className="text-2xl font-bold mt-1">{projects.length}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-shadow" onClick={() => onNavigate?.('projects')}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">已完成</p>
                <p className="text-2xl font-bold mt-1">{completedProjects}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-shadow" onClick={() => onNavigate?.('projects')}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">执行中</p>
                <p className="text-2xl font-bold mt-1">{processingProjects}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">成功率</p>
                <p className="text-2xl font-bold mt-1">{successRate}%</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                <Clock className="w-5 h-5 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">最近操作</h3>
                <Button variant="ghost" size="sm" onClick={() => onNavigate?.('history')}>查看全部</Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {history.slice(0, 5).map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-secondary/50 cursor-pointer"
                    onClick={() => onNavigate?.('history')}
                  >
                    <div className="flex-shrink-0">
                      {item.result === 'success' && <CheckCircle2 className="w-5 h-5 text-green-500" />}
                      {item.result === 'failure' && <XCircle className="w-5 h-5 text-red-500" />}
                      {item.result === 'pending' && <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{item.action}</p>
                      <p className="text-xs text-muted-foreground">{item.details}</p>
                    </div>
                    <span className="text-xs text-muted-foreground">{item.timestamp}</span>
                  </div>
                ))}
                {history.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    暂无操作记录
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">快速操作</h3>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <Button variant="outline" className="justify-start gap-2" onClick={() => onNavigate?.('effects')}>
                  <Sparkles className="w-4 h-4" />
                  添加效果
                </Button>
                <Button variant="outline" className="justify-start gap-2" onClick={() => onNavigate?.('execute')}>
                  <Play className="w-4 h-4" />
                  执行命令
                </Button>
                <Button variant="outline" className="justify-start gap-2" onClick={() => onNavigate?.('styles')}>
                  <ArrowRight className="w-4 h-4" />
                  风格模板
                </Button>
                <Button variant="outline" className="justify-start gap-2" onClick={() => onNavigate?.('projects')}>
                  <Clock className="w-4 h-4" />
                  项目管理
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="mt-4">
            <CardHeader>
              <h3 className="font-semibold">资源统计</h3>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div
                  className="flex items-center justify-between cursor-pointer hover:bg-secondary/30 p-2 rounded-lg"
                  onClick={() => onNavigate?.('effects')}
                >
                  <span className="text-sm text-muted-foreground">效果数量</span>
                  <Badge variant="secondary">{effectsCount}</Badge>
                </div>
                <div
                  className="flex items-center justify-between cursor-pointer hover:bg-secondary/30 p-2 rounded-lg"
                  onClick={() => onNavigate?.('styles')}
                >
                  <span className="text-sm text-muted-foreground">风格模板</span>
                  <Badge variant="secondary">{stylesCount}</Badge>
                </div>
                <div
                  className="flex items-center justify-between cursor-pointer hover:bg-secondary/30 p-2 rounded-lg"
                  onClick={() => onNavigate?.('projects')}
                >
                  <span className="text-sm text-muted-foreground">项目数量</span>
                  <Badge variant="secondary">{projects.length}</Badge>
                </div>
                <div
                  className="flex items-center justify-between cursor-pointer hover:bg-secondary/30 p-2 rounded-lg"
                  onClick={() => onNavigate?.('history')}
                >
                  <span className="text-sm text-muted-foreground">历史记录</span>
                  <Badge variant="secondary">{history.length}</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

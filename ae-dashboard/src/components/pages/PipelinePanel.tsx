import { useState } from 'react'
import { Activity, CheckCircle2, Circle, ArrowRight, Cpu, Film, Music, Eye, Wand2, Server } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PipelineStage {
  id: string
  name: string
  nameEn: string
  icon: React.ElementType
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  duration?: number
  detail?: string
  agents?: string[]
}

interface MCPServerStatus {
  name: string
  status: 'online' | 'offline' | 'error' | 'unknown'
  tools: number
  latency?: number
  lastCheck?: string
}

const PIPELINE_STAGES: PipelineStage[] = [
  { id: 'plan', name: '任务规划', nameEn: 'Planning', icon: Wand2, status: 'pending', agents: ['PlannerAgent'] },
  { id: 'material', name: '素材搜集', nameEn: 'Material', icon: Film, status: 'pending', agents: ['MaterialAgent'] },
  { id: 'vision', name: '视觉分析', nameEn: 'Vision', icon: Eye, status: 'pending', agents: ['VisionAgent'] },
  { id: 'audio', name: '音频处理', nameEn: 'Audio', icon: Music, status: 'pending', agents: ['AudioAgent'] },
  { id: 'compose', name: '合成渲染', nameEn: 'Compose', icon: Cpu, status: 'pending', agents: ['ComposerAgent'] },
  { id: 'style', name: '风格守护', nameEn: 'Style Guard', icon: Activity, status: 'pending', agents: ['StyleAgent'] },
  { id: 'enhance', name: '质量增强', nameEn: 'Enhance', icon: Cpu, status: 'pending', agents: ['EnhancerAgent'] },
  { id: 'color', name: '调色', nameEn: 'Color Grade', icon: Activity, status: 'pending', agents: ['ColoristAgent'] },
  { id: 'quality', name: '质检', nameEn: 'QA', icon: CheckCircle2, status: 'pending', agents: ['QualityAgent'] },
  { id: 'publish', name: '发布', nameEn: 'Publish', icon: Server, status: 'pending', agents: ['PublishAgent'] },
]

const MCP_SERVERS: MCPServerStatus[] = [
  { name: 'AfterEffectsMCP', status: 'unknown', tools: 25 },
  { name: 'AdobeMCP', status: 'unknown', tools: 15 },
  { name: 'PremiereProMCP', status: 'unknown', tools: 12 },
  { name: 'AdobeBridgeMCP', status: 'unknown', tools: 8 },
  { name: 'DaVinciResolveMCP', status: 'unknown', tools: 30 },
  { name: 'AEToolsMCP', status: 'unknown', tools: 10 },
  { name: 'ComfyUIMCP', status: 'unknown', tools: 6 },
  { name: 'filesystem', status: 'unknown', tools: 5 },
]

const AGENT_STATUS = [
  { name: 'PlannerAgent', desc: '任务规划', status: 'ready', tasks_completed: 47 },
  { name: 'MaterialAgent', desc: '素材搜集', status: 'ready', tasks_completed: 123 },
  { name: 'VisionAgent', desc: '视觉分析', status: 'ready', tasks_completed: 89 },
  { name: 'AudioAgent', desc: '音频处理', status: 'ready', tasks_completed: 56 },
  { name: 'ComposerAgent', desc: '合成渲染', status: 'ready', tasks_completed: 34 },
  { name: 'EnhancerAgent', desc: '质量增强', status: 'ready', tasks_completed: 22 },
  { name: 'ColoristAgent', desc: '调色', status: 'ready', tasks_completed: 41 },
  { name: 'MaskAgent', desc: '智能遮罩', status: 'ready', tasks_completed: 18 },
  { name: 'QualityAgent', desc: '质检', status: 'new', tasks_completed: 0 },
  { name: 'StyleAgent', desc: '风格守护', status: 'new', tasks_completed: 0 },
  { name: 'PublishAgent', desc: '多平台发布', status: 'new', tasks_completed: 0 },
]

export function PipelinePanel() {
  const [stages, setStages] = useState<PipelineStage[]>(PIPELINE_STAGES)
  const [mcpServers, setMcpServers] = useState<MCPServerStatus[]>(MCP_SERVERS)
  const [isRunning, setIsRunning] = useState(false)
  const [activeView, setActiveView] = useState<'pipeline' | 'agents' | 'mcp'>('pipeline')

  // 模拟管线运行
  const runPipeline = () => {
    setIsRunning(true)
    setStages(prev => prev.map(s => ({ ...s, status: 'pending' as const })))

    const runStage = (index: number) => {
      if (index >= stages.length) {
        setIsRunning(false)
        return
      }

      setStages(prev => prev.map((s, i) =>
        i === index ? { ...s, status: 'running' as const } : s
      ))

      const duration = 1000 + Math.random() * 2000
      setTimeout(() => {
        setStages(prev => prev.map((s, i) =>
          i === index ? { ...s, status: 'completed' as const, duration: Math.round(duration / 100) / 10 } : s
        ))
        runStage(index + 1)
      }, duration)
    }

    runStage(0)
  }

  return (
    <div className="p-6 space-y-6">
      {/* 视图切换 */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setActiveView('pipeline')}
          className={cn(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            activeView === 'pipeline' ? 'bg-primary text-primary-foreground' : 'bg-secondary hover:bg-secondary/80'
          )}
        >
          管线可视化
        </button>
        <button
          onClick={() => setActiveView('agents')}
          className={cn(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            activeView === 'agents' ? 'bg-primary text-primary-foreground' : 'bg-secondary hover:bg-secondary/80'
          )}
        >
          智能体矩阵 (11)
        </button>
        <button
          onClick={() => setActiveView('mcp')}
          className={cn(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            activeView === 'mcp' ? 'bg-primary text-primary-foreground' : 'bg-secondary hover:bg-secondary/80'
          )}
        >
          MCP Server 状态 (8)
        </button>
      </div>

      {/* 管线可视化 */}
      {activeView === 'pipeline' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">多智能体制作管线</h2>
            <button
              onClick={runPipeline}
              disabled={isRunning}
              className={cn(
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                isRunning ? 'bg-secondary text-muted-foreground cursor-not-allowed' : 'bg-primary text-primary-foreground hover:bg-primary/90'
              )}
            >
              {isRunning ? '运行中...' : '模拟运行'}
            </button>
          </div>

          {/* 流水线 */}
          <div className="grid grid-cols-5 gap-3">
            {stages.map((stage, i) => (
              <div key={stage.id} className="relative">
                <div className={cn(
                  'rounded-xl border-2 p-4 transition-all',
                  stage.status === 'completed' ? 'border-green-500 bg-green-500/10' :
                  stage.status === 'running' ? 'border-blue-500 bg-blue-500/10 animate-pulse' :
                  stage.status === 'failed' ? 'border-red-500 bg-red-500/10' :
                  'border-border bg-secondary/50'
                )}>
                  <div className="flex items-center gap-2 mb-2">
                    <stage.icon className={cn(
                      'w-5 h-5',
                      stage.status === 'completed' ? 'text-green-500' :
                      stage.status === 'running' ? 'text-blue-500' :
                      'text-muted-foreground'
                    )} />
                    {stage.status === 'completed' && <CheckCircle2 className="w-4 h-4 text-green-500 ml-auto" />}
                    {stage.status === 'running' && <Circle className="w-4 h-4 text-blue-500 ml-auto animate-pulse" />}
                    {stage.status === 'pending' && <Circle className="w-4 h-4 text-muted-foreground ml-auto" />}
                  </div>
                  <p className="text-sm font-medium">{stage.name}</p>
                  <p className="text-xs text-muted-foreground">{stage.nameEn}</p>
                  {stage.duration && (
                    <p className="text-xs text-green-500 mt-1">{stage.duration}s</p>
                  )}
                  {stage.agents && (
                    <p className="text-xs text-muted-foreground mt-1">{stage.agents[0]}</p>
                  )}
                </div>
                {i < stages.length - 1 && (
                  <ArrowRight className="absolute -right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground hidden lg:block" />
                )}
              </div>
            ))}
          </div>

          {/* 统计 */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs text-muted-foreground">总阶段</p>
              <p className="text-2xl font-bold">{stages.length}</p>
            </div>
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs text-muted-foreground">已完成</p>
              <p className="text-2xl font-bold text-green-500">{stages.filter(s => s.status === 'completed').length}</p>
            </div>
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs text-muted-foreground">总耗时</p>
              <p className="text-2xl font-bold">
                {stages.reduce((sum, s) => sum + (s.duration || 0), 0).toFixed(1)}s
              </p>
            </div>
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs text-muted-foreground">智能体</p>
              <p className="text-2xl font-bold">11</p>
            </div>
          </div>
        </div>
      )}

      {/* 智能体矩阵 */}
      {activeView === 'agents' && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">智能体矩阵 — 11 Agents</h2>
          <div className="grid grid-cols-3 gap-4">
            {AGENT_STATUS.map(agent => (
              <div key={agent.name} className="bg-secondary/50 rounded-xl p-4 border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{agent.name}</span>
                  <span className={cn(
                    'px-2 py-0.5 rounded-full text-xs',
                    agent.status === 'ready' ? 'bg-green-500/20 text-green-500' :
                    agent.status === 'new' ? 'bg-blue-500/20 text-blue-500' :
                    'bg-yellow-500/20 text-yellow-500'
                  )}>
                    {agent.status === 'ready' ? '就绪' : agent.status === 'new' ? 'NEW' : '忙碌'}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{agent.desc}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  已完成任务: <span className="text-foreground font-medium">{agent.tasks_completed}</span>
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MCP Server 状态 */}
      {activeView === 'mcp' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">MCP Server 状态监控</h2>
            <button
              onClick={() => setMcpServers(prev => prev.map(s => ({
                ...s,
                status: Math.random() > 0.3 ? 'online' : 'offline',
                latency: Math.round(Math.random() * 100 + 10),
                lastCheck: new Date().toLocaleTimeString(),
              })))}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-secondary hover:bg-secondary/80"
            >
              刷新状态
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {mcpServers.map(server => (
              <div key={server.name} className="bg-secondary/50 rounded-xl p-4 border">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium">{server.name}</span>
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      'w-2.5 h-2.5 rounded-full',
                      server.status === 'online' ? 'bg-green-500' :
                      server.status === 'offline' ? 'bg-red-500' :
                      server.status === 'error' ? 'bg-yellow-500' :
                      'bg-gray-500'
                    )} />
                    <span className="text-xs text-muted-foreground">
                      {server.status === 'online' ? '在线' :
                       server.status === 'offline' ? '离线' :
                       server.status === 'error' ? '异常' : '未知'}
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <p className="text-muted-foreground">工具数</p>
                    <p className="font-medium">{server.tools}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">延迟</p>
                    <p className="font-medium">{server.latency ? `${server.latency}ms` : '-'}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">最后检查</p>
                    <p className="font-medium">{server.lastCheck || '-'}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* 汇总 */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs text-muted-foreground">总 Server</p>
              <p className="text-2xl font-bold">{mcpServers.length}</p>
            </div>
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs text-muted-foreground">在线</p>
              <p className="text-2xl font-bold text-green-500">{mcpServers.filter(s => s.status === 'online').length}</p>
            </div>
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs text-muted-foreground">总工具</p>
              <p className="text-2xl font-bold">{mcpServers.reduce((sum, s) => sum + s.tools, 0)}</p>
            </div>
            <div className="bg-secondary/50 rounded-xl p-4">
              <p className="text-xs text-muted-foreground">平均延迟</p>
              <p className="text-2xl font-bold">
                {mcpServers.filter(s => s.latency).length > 0
                  ? Math.round(mcpServers.filter(s => s.latency).reduce((sum, s) => sum + (s.latency || 0), 0) / mcpServers.filter(s => s.latency).length)
                  : 0}ms
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

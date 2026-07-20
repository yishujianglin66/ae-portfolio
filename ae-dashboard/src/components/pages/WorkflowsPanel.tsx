import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { Play, CheckCircle, AlertCircle, Loader2, ArrowRight } from 'lucide-react'

interface WorkflowStep {
  step_id: string
  name: string
  tool: string
  operation: string
  depends_on: string[]
}

interface WorkflowDetail {
  workflow_name: string
  step_count: number
  steps: WorkflowStep[]
}

interface StepResult {
  success: boolean
  tool_name: string
  operation: string
  output_path: string | null
  output_data: Record<string, unknown>
  error: string
  duration_ms: number
  mode_used: string
}

interface WorkflowResult {
  workflow_name: string
  status: string
  total_duration_ms: number
  output_files: string[]
  error: string
  summary: string
  steps: StepResult[]
}

const WORKFLOW_DESCRIPTIONS: Record<string, string> = {
  enhance_quality: '使用Topaz Video AI进行视频超分辨率增强',
  delivery_pipeline: 'AE渲染 → Topaz增强 → FFmpeg编码',
  full_production: 'Silhouette抠像 → AE合成 → DaVinci调色 → FFmpeg输出',
}

export function WorkflowsPanel() {
  const [workflows, setWorkflows] = useState<WorkflowDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState<string | null>(null)
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null)
  const [result, setResult] = useState<WorkflowResult | null>(null)
  const [inputPath, setInputPath] = useState('input.mp4')
  const [outputPath, setOutputPath] = useState('output.mp4')
  const [mode, setMode] = useState('simulate')

  useEffect(() => {
    loadWorkflows()
  }, [])

  async function loadWorkflows() {
    setLoading(true)
    try {
      const data = await api.getToolchainWorkflows() as {
        total: number
        workflows: string[]
        details: WorkflowDetail[]
      }
      setWorkflows(data.details)
    } catch (err) {
      console.error('Failed to load workflows:', err)
    } finally {
      setLoading(false)
    }
  }

  async function executeWorkflow(name: string) {
    setExecuting(name)
    setResult(null)
    try {
      const data = await api.executeWorkflow({
        workflow_name: name,
        input_path: inputPath,
        output_path: outputPath,
        mode,
      }) as WorkflowResult
      setResult(data)
    } catch (err: unknown) {
      setResult({
        workflow_name: name,
        status: 'error',
        total_duration_ms: 0,
        output_files: [],
        error: err instanceof Error ? err.message : String(err),
        summary: '执行失败',
        steps: [],
      })
    } finally {
      setExecuting(null)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* 工作流列表 */}
      <div>
        <h2 className="text-lg font-semibold mb-3">工作流预设</h2>
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">加载中...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {workflows.map(wf => (
              <div
                key={wf.workflow_name}
                className={`bg-card rounded-lg border p-4 cursor-pointer transition-colors ${
                  selectedWorkflow === wf.workflow_name ? 'border-primary ring-1 ring-primary' : 'hover:border-primary/50'
                }`}
                onClick={() => setSelectedWorkflow(wf.workflow_name)}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold">{wf.workflow_name}</h3>
                  <span className="text-xs bg-secondary px-2 py-0.5 rounded">
                    {wf.step_count} 步
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  {WORKFLOW_DESCRIPTIONS[wf.workflow_name] || '自定义工作流'}
                </p>
                {/* 工作流步骤可视化 */}
                <div className="flex items-center gap-1 flex-wrap">
                  {wf.steps.map((step, i) => (
                    <div key={step.step_id} className="flex items-center gap-1">
                      <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                        {step.tool.split('_')[0].substring(0, 4)}
                      </span>
                      {i < wf.steps.length - 1 && (
                        <ArrowRight className="w-3 h-3 text-muted-foreground" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 执行配置 */}
      {selectedWorkflow && (
        <div className="bg-card rounded-lg border p-4 space-y-4">
          <h2 className="text-lg font-semibold">执行配置</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground block mb-1">输入文件</label>
              <input
                type="text"
                value={inputPath}
                onChange={e => setInputPath(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-secondary rounded-md border-0 focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground block mb-1">输出文件</label>
              <input
                type="text"
                value={outputPath}
                onChange={e => setOutputPath(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-secondary rounded-md border-0 focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div>
              <label className="text-sm text-muted-foreground block mb-1">执行模式</label>
              <select
                value={mode}
                onChange={e => setMode(e.target.value)}
                className="px-3 py-2 text-sm bg-secondary rounded-md border-0 focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="auto">自动</option>
                <option value="simulate">模拟</option>
                <option value="real">真实</option>
              </select>
            </div>
            <div className="flex-1" />
            <button
              onClick={() => executeWorkflow(selectedWorkflow)}
              disabled={!!executing}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
            >
              {executing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  执行中...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  执行工作流
                </>
              )}
            </button>
          </div>

          {/* 步骤详情 */}
          {workflows.find(w => w.workflow_name === selectedWorkflow) && (
            <div className="mt-4">
              <h3 className="text-sm font-medium mb-2">工作流步骤</h3>
              <div className="space-y-2">
                {workflows.find(w => w.workflow_name === selectedWorkflow)!.steps.map((step, i) => (
                  <div key={step.step_id} className="flex items-center gap-3 bg-secondary/50 rounded-md px-3 py-2">
                    <span className="text-xs font-mono bg-secondary px-1.5 py-0.5 rounded">
                      {i + 1}
                    </span>
                    <span className="text-sm font-medium">{step.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {step.tool}.{step.operation}
                    </span>
                    {step.depends_on.length > 0 && (
                      <span className="text-xs text-muted-foreground ml-auto">
                        依赖: {step.depends_on.join(', ')}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 执行结果 */}
      {result && (
        <div className={`bg-card rounded-lg border p-4 space-y-3 ${
          result.status === 'success' ? 'border-green-500/20' : 'border-red-500/20'
        }`}>
          <div className="flex items-center gap-2">
            {result.status === 'success' ? (
              <CheckCircle className="w-5 h-5 text-green-500" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-500" />
            )}
            <h2 className="text-lg font-semibold">执行结果</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-muted-foreground">工作流</p>
              <p className="text-sm font-medium">{result.workflow_name}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">状态</p>
              <p className={`text-sm font-medium ${
                result.status === 'success' ? 'text-green-500' : 'text-red-500'
              }`}>{result.status}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">耗时</p>
              <p className="text-sm font-medium">{result.total_duration_ms.toFixed(1)}ms</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">输出文件</p>
              <p className="text-sm font-medium">{result.output_files.length}</p>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">{result.summary}</p>

          {/* 步骤结果 */}
          {result.steps.length > 0 && (
            <div className="space-y-2 mt-3">
              <h3 className="text-sm font-medium">步骤详情</h3>
              {result.steps.map((step, i) => (
                <div key={i} className="flex items-center gap-3 bg-secondary/50 rounded-md px-3 py-2">
                  {step.success ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-red-500" />
                  )}
                  <span className="text-sm font-medium">{step.tool_name}.{step.operation}</span>
                  <span className="text-xs text-muted-foreground">
                    {step.duration_ms.toFixed(1)}ms
                  </span>
                  <span className="text-xs bg-secondary px-2 py-0.5 rounded ml-auto">
                    {step.mode_used}
                  </span>
                </div>
              ))}
            </div>
          )}

          {result.error && (
            <div className="bg-red-500/10 text-red-500 text-sm rounded-md p-3">
              {result.error}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
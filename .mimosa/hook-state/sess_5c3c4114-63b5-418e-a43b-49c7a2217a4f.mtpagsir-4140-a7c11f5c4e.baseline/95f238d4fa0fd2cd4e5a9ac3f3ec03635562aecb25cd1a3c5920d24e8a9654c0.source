import { useState } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { useToast } from '@/components/ui/Toast'
import { useAppStore } from '@/store/useAppStore'
import { mockEffects, mockStyleTemplates, intentTypes } from '@/data/mockData'
import { api } from '@/lib/api'
import { PreviewModal } from './PreviewModal'
import { Play, Sparkles, Zap, Clock, CheckCircle2, Loader2, XCircle, Terminal, ChevronDown, ChevronUp, Eye, Send, Trash2, Layers, Crosshair, Brush } from 'lucide-react'

// 简单的 NLU 解析模拟
function parseCommand(input: string): Record<string, string> {
  const params: Record<string, string> = {}

  // 效果名
  const effectMatch = input.match(/(发光|辉光|模糊|阴影|描边|光晕|变形|色彩校正)/)
  if (effectMatch) params['效果'] = effectMatch[1]

  // 颜色
  const colorMatch = input.match(/(红色|蓝色|绿色|黄色|紫色|青色|白色|黑色|橙色)/)
  if (colorMatch) params['颜色'] = colorMatch[1]

  // 强度
  const intensityMatch = input.match(/强度[为是]?(\d+)/) || input.match(/(\d+)%/)
  if (intensityMatch) params['强度'] = intensityMatch[1]

  // 图层
  const layerMatch = input.match(/(选中|文字|图片|视频|背景)图层?/)
  if (layerMatch) params['图层'] = layerMatch[1]

  // 风格
  const styleMatch = input.match(/(电影感|赛博朋克|复古|极简|梦幻)/)
  if (styleMatch) params['风格'] = styleMatch[1]

  // 意图
  if (input.includes('加') || input.includes('添加') || input.includes('应用')) params['意图'] = '添加效果'
  else if (input.includes('动画') || input.includes('关键帧')) params['意图'] = '创建动画'
  else if (input.includes('风格')) params['意图'] = '应用风格'
  else if (input.includes('渲染') || input.includes('输出')) params['意图'] = '渲染输出'
  else params['意图'] = '自动检测'

  return params
}

// 将后端 AI Planner 返回结构适配为前端统一的 Record<string, string>
function adaptAiPlanResult(raw: any): Record<string, string> {
  const params: Record<string, string> = {}
  if (!raw || typeof raw !== 'object') return params
  // 1) 优先取 params 字段（对象或数组）
  const candidate: any = raw.params ?? raw.parameters ?? raw.parsed_params ?? raw.result ?? raw
  if (Array.isArray(candidate)) {
    // [{name, value}, ...] 或 [{key, value}, ...]
    candidate.forEach((p: any) => {
      if (!p || typeof p !== 'object') return
      const k = String(p.name ?? p.key ?? p.label ?? '')
      const v = p.value ?? p.default ?? p.content
      if (k) params[k] = String(v ?? '')
    })
  } else if (candidate && typeof candidate === 'object') {
    Object.entries(candidate).forEach(([k, v]) => {
      if (v !== null && v !== undefined) params[k] = String(v)
    })
  }
  // 2) intent / 意图 单独处理
  if (raw.intent && !params['意图']) params['意图'] = String(raw.intent)
  if (raw.intent_type && !params['意图']) params['意图'] = String(raw.intent_type)
  return params
}

// 异步调用后端 AI Planner API 增强解析；失败时回退到本地 parseCommand
async function parseCommandEnhanced(
  input: string,
  localFallback: Record<string, string>
): Promise<Record<string, string>> {
  try {
    // api.request 在 api.ts 中为 private，使用类型断言绕过访问限制以避免修改 api.ts
    const requestFn = (api as unknown as {
      request: <T>(path: string, options?: RequestInit) => Promise<T>
    }).request
    const res: any = await requestFn('/ai/plan', {
      method: 'POST',
      body: JSON.stringify({ input }),
    })
    const adapted = adaptAiPlanResult(res)
    // 后端无有效字段时回退
    if (Object.keys(adapted).length === 0) {
      return localFallback
    }
    return adapted
  } catch {
    // API 失败回退到本地 parseCommand
    return localFallback
  }
}

const silhouetteModes = [
  { value: 'real', label: '真实', desc: '自动启动Silhouette.exe执行真实渲染输出' },
  { value: 'auto', label: '自动', desc: '优先真实模式，失败回退模拟模式' },
  { value: 'simulate', label: '模拟', desc: '使用模拟器执行（无需安装Silhouette）' },
]

const PRESET_COMMAND_MAP: Record<string, string> = {
  standard_keying: '对选中图层执行标准Roto抠像',
  hair_keying: '对选中图层执行毛发抠像',
  hard_edge_keying: '对选中图层执行硬边Roto抠像',
  soft_edge_keying: '对选中图层执行柔边Roto抠像',
  multi_shape_keying: '对选中图层执行多形状分解抠像',
  ai_assisted_keying: '对选中图层执行AI辅助抠像',
  planar_track: '对选中图层执行平面跟踪',
  high_precision_track: '对选中图层执行高精度跟踪',
  fast_track: '对选中图层执行快速跟踪',
  point_track: '对选中图层执行点跟踪',
  stabilize: '对选中图层执行稳定化',
  camera_solve: '对选中图层执行摄像机解算',
  clone_repair: '对选中图层执行克隆修复',
  smart_repair: '对选中图层执行智能修复',
  wire_removal: '对选中图层执行威亚去除',
  digital_makeup: '对选中图层执行数字化妆',
  sequence_repair: '对选中图层执行序列帧修复',
  object_removal: '对选中图层执行物体擦除',
}

const silhouettePresets = [
  { id: 'standard_keying', name: '标准抠像', category: 'roto', icon: 'mask' },
  { id: 'hair_keying', name: '毛发抠像', category: 'roto', icon: 'mask' },
  { id: 'hard_edge_keying', name: '硬边抠像', category: 'roto', icon: 'mask' },
  { id: 'soft_edge_keying', name: '柔边抠像', category: 'roto', icon: 'mask' },
  { id: 'multi_shape_keying', name: '多形状抠像', category: 'roto', icon: 'mask' },
  { id: 'ai_assisted_keying', name: 'AI辅助抠像', category: 'roto', icon: 'mask' },
  { id: 'planar_track', name: '平面跟踪', category: 'track', icon: 'track' },
  { id: 'high_precision_track', name: '高精度跟踪', category: 'track', icon: 'track' },
  { id: 'fast_track', name: '快速跟踪', category: 'track', icon: 'track' },
  { id: 'point_track', name: '点跟踪', category: 'track', icon: 'track' },
  { id: 'stabilize', name: '稳定化', category: 'track', icon: 'track' },
  { id: 'camera_solve', name: '摄像机解算', category: 'track', icon: 'track' },
  { id: 'clone_repair', name: '克隆修复', category: 'paint', icon: 'paint' },
  { id: 'smart_repair', name: '智能修复', category: 'paint', icon: 'paint' },
  { id: 'wire_removal', name: '去威亚', category: 'paint', icon: 'paint' },
  { id: 'digital_makeup', name: '数字化妆', category: 'paint', icon: 'paint' },
  { id: 'sequence_repair', name: '序列修复', category: 'paint', icon: 'paint' },
  { id: 'object_removal', name: '物体擦除', category: 'paint', icon: 'paint' },
]

const silhouettePresetCategories = [
  { key: 'roto', label: 'Roto 抠像', count: 6 },
  { key: 'track', label: '跟踪', count: 6 },
  { key: 'paint', label: 'Paint 修复', count: 6 },
]

export function ExecutePanel() {
  const { showToast } = useToast()
  const { addExecutionLog, updateExecutionLog, executionLogs, settings } = useAppStore()
  const [inputText, setInputText] = useState('')
  const [selectedIntent, setSelectedIntent] = useState<string | null>(null)
  const [executionStatus, setExecutionStatus] = useState<'idle' | 'processing' | 'success' | 'failed'>('idle')
  const [logs, setLogs] = useState<string[]>([])
  const [showLogs, setShowLogs] = useState(true)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [silhouetteMode, setSilhouetteMode] = useState('real')
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null)
  const [presetCategory, setPresetCategory] = useState<string>('roto')

  const execute = () => {
    if (!inputText.trim()) {
      showToast('请输入命令内容', 'warning')
      return
    }

    // 1) 先调用本地 parseCommand 快速显示预览
    const localParsed = parseCommand(inputText)
    const intent = selectedIntent || localParsed['意图'] || '自动检测'

    setExecutionStatus('processing')
    setShowLogs(true)
    setLogs(['[开始] 解析输入...', `输入: "${inputText}"`])

    const logId = addExecutionLog({
      command: inputText,
      intent,
      result: 'pending',
      logs: [],
      parsedParams: localParsed,
    })

    const steps = [
      { delay: 500, log: `[NLU] 识别意图: ${intent}` },
      { delay: 1000, log: `[解析] 提取参数: ${Object.entries(localParsed).map(([k, v]) => `${k}=${v}`).join(', ') || '无'}` },
      { delay: 1500, log: `[生成] 构建AE命令序列...` },
      { delay: 2000, log: `[连接] AE MCP Listener...` },
      { delay: 2200, log: settings.aeConnected ? `[发送] 命令已发送` : `[警告] AE未连接，使用模拟模式` },
      { delay: 2800, log: `[执行] ${localParsed['效果'] ? `应用${localParsed['效果']}效果` : '执行命令'}...` },
      { delay: 3500, log: `[完成] 执行成功` },
    ]

    steps.forEach((step, index) => {
      setTimeout(() => {
        setLogs(prev => [...prev, step.log])
        if (index === steps.length - 1) {
          setExecutionStatus('success')
          if (logId) {
            updateExecutionLog(logId, { result: 'success', logs: [...logs, step.log] })
          }
          showToast('命令执行成功', 'success')
        }
      }, step.delay)
    })

    // 2) 异步调用后端 AI Planner API 增强解析结果
    parseCommandEnhanced(inputText, localParsed).then((enhanced) => {
      // 仅当后端返回了与本地不同的解析结果时才更新
      const changed = Object.keys(enhanced).some(
        (k) => enhanced[k] !== localParsed[k]
      ) || Object.keys(enhanced).length !== Object.keys(localParsed).length
      if (!changed) return
      setLogs(prev => [
        ...prev,
        `[AI] 后端 AI Planner 已增强解析: ${Object.entries(enhanced).map(([k, v]) => `${k}=${v}`).join(', ') || '无'}`,
      ])
      if (logId) {
        updateExecutionLog(logId, { parsedParams: enhanced })
      }
    })
  }

  const handlePreview = () => {
    if (!inputText.trim()) {
      showToast('请输入命令内容', 'warning')
      return
    }
    setPreviewOpen(true)
  }

  const handleClear = () => {
    setInputText('')
    setSelectedIntent(null)
    setExecutionStatus('idle')
    setLogs([])
    showToast('已清空输入', 'info')
  }

  const handleQuickCommand = (text: string) => {
    setInputText(text)
  }

  const handleRerun = (cmd: string) => {
    setInputText(cmd)
    setTimeout(() => execute(), 100)
  }

  return (
    <div className="p-6 space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Play className="w-5 h-5 text-primary" />
            <h3 className="font-semibold">命令执行中心</h3>
            {executionStatus !== 'idle' && (
              <Badge className={`${
                executionStatus === 'processing' ? 'bg-blue-100 text-blue-600' :
                executionStatus === 'success' ? 'bg-green-100 text-green-600' :
                'bg-red-100 text-red-600'
              } flex items-center gap-1`}>
                {executionStatus === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                {executionStatus === 'success' && <CheckCircle2 className="w-3 h-3" />}
                {executionStatus === 'failed' && <XCircle className="w-3 h-3" />}
                {executionStatus === 'processing' ? '执行中' : executionStatus === 'success' ? '成功' : '失败'}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-6">
          <div className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) execute()
                }}
                placeholder="输入自然语言命令，如：给选中图层加蓝色发光效果..."
                className="text-lg py-4 flex-1"
              />
              {inputText && (
                <Button variant="outline" size="lg" onClick={handleClear}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              {intentTypes.map((intent) => (
                <button
                  key={intent.type}
                  onClick={() => setSelectedIntent(selectedIntent === intent.type ? null : intent.type)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                    selectedIntent === intent.type
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary hover:bg-secondary/80'
                  }`}
                >
                  <Sparkles className="w-4 h-4" />
                  {intent.label}
                </button>
              ))}
            </div>

            <div className="flex gap-4">
              <Button
                size="lg"
                className="flex-1 gap-2"
                onClick={execute}
                disabled={executionStatus === 'processing'}
              >
                {executionStatus === 'processing' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
                {executionStatus === 'processing' ? '执行中...' : '执行命令'}
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="gap-2"
                onClick={handlePreview}
              >
                <Eye className="w-5 h-5" />
                预览效果
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">提示: Ctrl+Enter 快速执行</p>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">常用效果</h3>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              {mockEffects.map((effect) => (
                <button
                  key={effect.id}
                  onClick={() => handleQuickCommand(`给选中图层加${effect.name}效果`)}
                  className="p-3 rounded-lg border hover:border-primary hover:bg-primary/5 transition-colors text-left"
                >
                  <p className="font-medium">{effect.name}</p>
                  <p className="text-xs text-muted-foreground">{effect.category}</p>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">快速风格</h3>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-2">
              {mockStyleTemplates.map((style) => (
                <button
                  key={style.id}
                  onClick={() => handleQuickCommand(`应用${style.name}风格`)}
                  className="p-3 rounded-lg border hover:border-primary hover:bg-primary/5 transition-colors flex items-center gap-3"
                >
                  <div className="w-10 h-10 rounded-lg overflow-hidden flex-shrink-0">
                    <img src={style.thumbnail} alt={style.name} className="w-full h-full object-cover" />
                  </div>
                  <div className="text-left">
                    <p className="font-medium">{style.name}</p>
                    <p className="text-xs text-muted-foreground">{style.effects.join(' + ')}</p>
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            <h3 className="font-semibold">Silhouette 预设库</h3>
            <Badge variant="outline">{silhouettePresets.length} 个预设</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-xs text-muted-foreground mr-2">执行模式:</span>
              {silhouetteModes.map((mode) => (
                <button
                  key={mode.value}
                  onClick={() => setSilhouetteMode(mode.value)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    silhouetteMode === mode.value
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary hover:bg-secondary/80'
                  }`}
                  title={mode.desc}
                >
                  {mode.label}模式
                </button>
              ))}
            </div>

            <div className="flex gap-2 border-b">
              {silhouettePresetCategories.map((cat) => (
                <button
                  key={cat.key}
                  onClick={() => setPresetCategory(cat.key)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                    presetCategory === cat.key
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {cat.label}
                  <span className="ml-1 text-xs opacity-60">({cat.count})</span>
                </button>
              ))}
            </div>
            
            <div className="grid grid-cols-3 gap-2">
              {silhouettePresets
                .filter(p => p.category === presetCategory)
                .map((preset) => {
                  const Icon = preset.icon === 'mask' ? Layers : preset.icon === 'track' ? Crosshair : Brush
                  const handlePresetClick = () => {
                    const isSelected = selectedPreset === preset.id
                    setSelectedPreset(isSelected ? null : preset.id)
                    if (!isSelected) {
                      setInputText(PRESET_COMMAND_MAP[preset.id] || '')
                    }
                  }
                  return (
                    <button
                      key={preset.id}
                      onClick={handlePresetClick}
                      className={`p-3 rounded-lg border transition-all text-center ${
                        selectedPreset === preset.id
                          ? 'border-primary bg-primary/10 scale-[1.02]'
                          : 'hover:border-primary hover:bg-primary/5'
                      }`}
                    >
                      <Icon className={`w-5 h-5 mx-auto mb-1 ${selectedPreset === preset.id ? 'text-primary' : ''}`} />
                      <p className="text-xs font-medium">{preset.name}</p>
                    </button>
                  )
                })}
            </div>

            {selectedPreset && (
              <div className="p-3 bg-secondary/50 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    已选择: {silhouettePresets.find(p => p.id === selectedPreset)?.name}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    模式: {silhouetteModes.find(m => m.value === silhouetteMode)?.label}
                  </span>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setShowLogs(!showLogs)}
        >
          <div className="flex items-center gap-2">
            <Terminal className="w-5 h-5 text-primary" />
            <h3 className="font-semibold">执行日志</h3>
            {logs.length > 0 && <Badge variant="secondary">{logs.length} 行</Badge>}
          </div>
          {showLogs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </CardHeader>
        {showLogs && (
          <CardContent>
            <div className="bg-gray-900 text-gray-100 rounded-lg p-4 font-mono text-sm h-48 overflow-y-auto">
              {logs.length === 0 ? (
                <div className="text-gray-500 flex items-center justify-center h-full">
                  等待执行命令...
                </div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="flex items-start gap-2 mb-1">
                    <span className="text-gray-500">{String(index + 1).padStart(2, '0')}</span>
                    <span className={log.includes('[完成]') ? 'text-green-400' : log.includes('[错误]') || log.includes('[警告]') ? 'text-yellow-400' : 'text-gray-300'}>
                      {log}
                    </span>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        )}
      </Card>

      {executionLogs.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">执行历史</h3>
              <Badge variant="secondary">{executionLogs.length} 条</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {executionLogs.slice(0, 10).map((item) => (
                <div key={item.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-secondary/50">
                  {item.result === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                  ) : item.result === 'pending' ? (
                    <Loader2 className="w-4 h-4 text-blue-500 animate-spin flex-shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                  )}
                  <span className="text-sm font-medium flex-1 truncate">{item.command}</span>
                  {item.parsedParams && Object.keys(item.parsedParams).length > 0 && (
                    <div className="hidden md:flex gap-1">
                      {Object.entries(item.parsedParams).slice(0, 3).map(([k, v]) => (
                        <Badge key={k} variant="secondary" className="text-xs">{k}: {String(v)}</Badge>
                      ))}
                    </div>
                  )}
                  <span className="text-xs text-muted-foreground flex-shrink-0">{item.timestamp}</span>
                  <button
                    onClick={() => handleRerun(item.command)}
                    className="text-xs text-primary hover:text-primary/80 flex-shrink-0"
                  >
                    重跑
                  </button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 预览弹窗 */}
      <PreviewModal
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        type="command"
        commandText={inputText}
        parsedParams={parseCommand(inputText)}
      />
    </div>
  )
}

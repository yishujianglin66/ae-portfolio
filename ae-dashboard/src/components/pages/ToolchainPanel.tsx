import { useState, useEffect, useMemo } from 'react'
import { api } from '@/lib/api'
import { useDebounce } from '@/lib/utils'
import { Cpu, CheckCircle, XCircle, RefreshCw, Search, ChevronDown, ChevronRight } from 'lucide-react'

interface ToolInfo {
  name: string
  category: string
  status: string
  description: string
  executable_path: string
  capabilities: string[]
  metadata: Record<string, unknown>
}

interface EngineList {
  total: number
  engines: ToolInfo[]
}

interface CategoryList {
  categories: string[]
  counts: Record<string, number>
}

const CATEGORY_LABELS: Record<string, string> = {
  engine: '软件引擎',
  script: 'AE脚本',
  mcp_tool: 'MCP工具',
  python_tool: 'Python工具',
}

const ENGINE_ICONS: Record<string, string> = {
  after_effects: 'AE',
  after_effects_2025: 'AE25',
  premiere_pro: 'PR',
  photoshop: 'PS',
  illustrator: 'AI',
  media_encoder: 'ME',
  topaz_video_ai: 'Topaz',
  blender: 'Blender',
  ffmpeg: 'FFmpeg',
  davinci_resolve: 'DaVinci',
  silhouette: 'Silhouette',
}

interface ToolchainPanelProps {
  onRefresh?: () => Promise<void>
}

export function ToolchainPanel(_props: ToolchainPanelProps = {}) {
  const [engines, setEngines] = useState<ToolInfo[]>([])
  const [categories, setCategories] = useState<CategoryList | null>(null)
  const [activeCategory, setActiveCategory] = useState<string>('engine')
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearchQuery = useDebounce(searchQuery, 200)
  const [expandedTool, setExpandedTool] = useState<string | null>(null)
  const [totalTools, setTotalTools] = useState(0)

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    loadToolsByCategory(activeCategory)
  }, [activeCategory])

  async function loadData() {
    setLoading(true)
    try {
      const [enginesData, catData] = await Promise.all([
        api.getToolchainEngines() as Promise<EngineList>,
        api.getToolchainCategories() as Promise<CategoryList>,
      ])
      setEngines(enginesData.engines)
      setCategories(catData)
    } catch (err) {
      console.error('Failed to load toolchain data:', err)
    } finally {
      setLoading(false)
    }
  }

  async function loadToolsByCategory(category: string) {
    try {
      const data = await api.getToolchainTools(category) as { total: number; tools: ToolInfo[] }
      setTools(data.tools)
      setTotalTools(data.total)
    } catch (err) {
      console.error('Failed to load tools:', err)
    }
  }

  const filteredTools = useMemo(() => tools.filter(t =>
    t.name.toLowerCase().includes(debouncedSearchQuery.toLowerCase()) ||
    t.description.toLowerCase().includes(debouncedSearchQuery.toLowerCase())
  ), [tools, debouncedSearchQuery])

  const availableEngines = engines.filter(e => e.status === 'available').length

  return (
    <div className="p-6 space-y-6">
      {/* 引擎状态概览 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-card rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">软件引擎</p>
              <p className="text-2xl font-bold">{engines.length}</p>
            </div>
          </div>
        </div>

        <div className="bg-card rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">可用引擎</p>
              <p className="text-2xl font-bold">{availableEngines}</p>
            </div>
          </div>
        </div>

        <div className="bg-card rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
              <XCircle className="w-5 h-5 text-orange-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">不可用</p>
              <p className="text-2xl font-bold">{engines.length - availableEngines}</p>
            </div>
          </div>
        </div>

        <div className="bg-card rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <RefreshCw className="w-5 h-5 text-purple-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">工具总数</p>
              <p className="text-2xl font-bold">{totalTools || (categories ? Object.values(categories.counts).reduce((a, b) => a + b, 0) : 0)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 引擎卡片 */}
      <div>
        <h2 className="text-lg font-semibold mb-3">软件引擎</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {engines.map(engine => {
            const icon = ENGINE_ICONS[engine.name] || '?'
            const isAvailable = engine.status === 'available'
            return (
              <div
                key={engine.name}
                className={`bg-card rounded-lg border p-3 transition-colors ${
                  isAvailable ? 'border-green-500/20' : 'border-red-500/20'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                    isAvailable ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'
                  }`}>
                    {icon}
                  </span>
                  <span className="text-sm font-medium truncate flex-1">{engine.description}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${isAvailable ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-xs text-muted-foreground">
                    {isAvailable ? '可用' : '不可用'}
                  </span>
                </div>
                {engine.capabilities.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {engine.capabilities.slice(0, 3).map(cap => (
                      <span key={cap} className="text-[10px] bg-secondary px-1.5 py-0.5 rounded">
                        {cap}
                      </span>
                    ))}
                    {engine.capabilities.length > 3 && (
                      <span className="text-[10px] text-muted-foreground">
                        +{engine.capabilities.length - 3}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* 工具列表 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">工具列表</h2>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="搜索工具..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-sm bg-secondary rounded-md border-0 focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <button
              onClick={loadData}
              className="p-1.5 rounded-md hover:bg-secondary"
              title="刷新"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 分类标签 */}
        <div className="flex gap-2 mb-3">
          {categories && categories.categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1 text-sm rounded-full transition-colors ${
                activeCategory === cat
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:text-foreground'
              }`}
            >
              {CATEGORY_LABELS[cat] || cat} ({categories.counts[cat] || 0})
            </button>
          ))}
        </div>

        {/* 工具表格 */}
        <div className="bg-card rounded-lg border">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">加载中...</div>
          ) : (
            <div className="divide-y">
              {filteredTools.map(tool => (
                <div key={tool.name}>
                  <button
                    onClick={() => setExpandedTool(expandedTool === tool.name ? null : tool.name)}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-secondary/50 transition-colors text-left"
                  >
                    {expandedTool === tool.name ? (
                      <ChevronDown className="w-4 h-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    )}
                    <span className={`w-2 h-2 rounded-full ${
                      tool.status === 'available' ? 'bg-green-500' : 'bg-red-500'
                    }`} />
                    <span className="text-sm font-medium flex-1">{tool.name}</span>
                    <span className="text-xs text-muted-foreground">{tool.description}</span>
                    {tool.capabilities.length > 0 && (
                      <span className="text-xs bg-secondary px-2 py-0.5 rounded">
                        {tool.capabilities.length} 个能力
                      </span>
                    )}
                  </button>
                  {expandedTool === tool.name && (
                    <div className="px-4 pb-3 pl-11 space-y-2">
                      <div className="text-xs text-muted-foreground">
                        <span className="font-medium">路径:</span>{' '}
                        <code className="bg-secondary px-1 rounded">{tool.executable_path || 'N/A'}</code>
                      </div>
                      {tool.capabilities.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {tool.capabilities.map(cap => (
                            <span key={cap} className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                              {cap}
                            </span>
                          ))}
                        </div>
                      )}
                      {Object.keys(tool.metadata).length > 0 && (
                        <div className="text-xs text-muted-foreground">
                          <span className="font-medium">元数据:</span>{' '}
                          {Object.entries(tool.metadata).map(([k, v]) => (
                            <span key={k} className="mr-3">
                              {k}={String(v)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              {filteredTools.length === 0 && (
                <div className="p-6 text-center text-muted-foreground text-sm">
                  没有找到匹配的工具
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useAppStore, Project, fallbackProjects } from '@/store/useAppStore'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { ProjectDetailDrawer } from './ProjectDetailDrawer'
import { RenderProgressModal } from './RenderProgressModal'
import { ProjectEditModal } from './ProjectEditModal'
import {
  Folder, Clock, Layers, Play, Edit, Trash2, Eye, Plus,
  RefreshCw, Loader2, AlertCircle, ChevronLeft, ChevronRight, Film, Monitor,
} from 'lucide-react'

type StatusFilter = 'all' | 'draft' | 'processing' | 'completed' | 'failed'

const statusConfig: Record<Project['status'], { label: string; color: string }> = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-600' },
  processing: { label: '执行中', color: 'bg-blue-100 text-blue-600' },
  completed: { label: '已完成', color: 'bg-green-100 text-green-600' },
  failed: { label: '失败', color: 'bg-red-100 text-red-600' },
}

const statusFilters: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'draft', label: '草稿' },
  { value: 'processing', label: '执行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
]

const PAGE_SIZE = 9

const formatDuration = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// 将后端响应的任意字段安全转为 Project（处理 timestamp/数值差异）
function adaptProject(p: Record<string, unknown>): Project {
  const toStr = (v: unknown, fallback = ''): string =>
    typeof v === 'string' ? v : v == null ? fallback : String(v)
  const toNum = (v: unknown, fallback = 0): number =>
    (typeof v === 'number' && Number.isFinite(v)) ? v : fallback
  const toDateString = (v: unknown): string => {
    if (typeof v === 'number' && Number.isFinite(v)) {
      return new Date(v * 1000).toISOString().split('T')[0]
    }
    if (typeof v === 'string' && v.length > 0) return v.split('T')[0]
    return new Date().toISOString().split('T')[0]
  }
  return {
    id: toStr(p.id),
    name: toStr(p.name, '未命名项目'),
    description: p.description as string | undefined,
    status: (p.status as Project['status']) || 'draft',
    createdAt: toDateString(p.createdAt),
    updatedAt: toDateString(p.updatedAt),
    duration: toNum(p.duration),
    sceneCount: toNum(p.sceneCount),
    width: toNum(p.width, 1920),
    height: toNum(p.height, 1080),
    frameRate: toNum(p.frameRate, 30),
    scenes: (p.scenes as Project['scenes']) || [],
    appliedEffects: (p.appliedEffects as Project['appliedEffects']) || [],
    renderOutput: p.renderOutput as string | undefined,
  }
}

export function ProjectsPanel() {
  const { showToast } = useToast()
  const { deleteProject, setProjects } = useAppStore()

  // 本组件独立维护的列表状态：以 API 拉取为准
  const [projects, setLocalProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [usingFallback, setUsingFallback] = useState(false)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  // 弹窗状态
  const [detailProject, setDetailProject] = useState<Project | null>(null)
  const [renderProject, setRenderProject] = useState<Project | null>(null)
  const [editProject, setEditProject] = useState<Project | null>(null)
  const [editMode, setEditMode] = useState<'edit' | 'create'>('edit')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const loadProjects = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    setError(null)
    try {
      const params: { page: number; page_size: number; status?: string } = {
        page,
        page_size: PAGE_SIZE,
      }
      if (statusFilter !== 'all') params.status = statusFilter
      const resp = await api.getProjects(params) as {
        projects?: Project[] | Record<string, unknown>[]
        total?: number
      }
      const rawList = resp?.projects ?? []
      const adapted = rawList.map((p) =>
        adaptProject(p as Record<string, unknown>)
      )
      setLocalProjects(adapted)
      // 同步到 store，便于其他页面（Dashboard 等）共享
      setProjects(adapted)
      setTotal(typeof resp?.total === 'number' ? resp.total : adapted.length)
      setUsingFallback(false)
    } catch (err) {
      console.error('[ProjectsPanel] 加载项目失败:', err)
      const msg = err instanceof Error ? err.message : '网络错误'
      setError(msg)
      // 降级到 fallback 数据
      setLocalProjects(fallbackProjects)
      setProjects(fallbackProjects)
      setTotal(fallbackProjects.length)
      setUsingFallback(true)
      showToast('后端不可用，已加载示例数据', 'warning')
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [page, statusFilter, setProjects, showToast])

  useEffect(() => {
    loadProjects()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter])

  const handleRefresh = () => {
    loadProjects()
  }

  const handleFilterChange = (filter: StatusFilter) => {
    setStatusFilter(filter)
    setPage(1) // 切换筛选时回到第 1 页
  }

  const handleCreate = () => {
    setEditProject(null)
    setEditMode('create')
  }

  const handleView = (project: Project) => {
    setDetailProject(project)
  }

  const handleEdit = (project: Project) => {
    setEditProject(project)
    setEditMode('edit')
    setDetailProject(null)
  }

  const handleRender = (project: Project) => {
    setRenderProject(project)
    setDetailProject(null)
  }

  const handleDelete = async (project: Project) => {
    if (deleteConfirm !== project.id) {
      setDeleteConfirm(project.id)
      setTimeout(() => setDeleteConfirm(null), 3000)
      return
    }
    // 二次确认后执行删除
    setDeleteConfirm(null)
    // 先尝试调用后端 API
    try {
      await api.deleteProject(project.id)
      showToast(`已删除项目: ${project.name}`, 'success')
      // 同步移除本地 store（deleteProject 会写入历史记录）
      deleteProject(project.id)
      // 重新加载当前页
      loadProjects()
    } catch (err) {
      console.error('[ProjectsPanel] 删除项目失败:', err)
      // API 失败时仍移除本地（保持 UI 一致），并提示
      deleteProject(project.id)
      setLocalProjects(prev => prev.filter(p => p.id !== project.id))
      showToast('后端不可用，仅本地删除', 'warning')
    }
  }

  // ===== 加载骨架 =====
  if (loading && projects.length === 0) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold">项目管理</h3>
          <Button className="gap-2" disabled>
            <Plus className="w-4 h-4" />
            创建新项目
          </Button>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="pb-3">
                <div className="h-5 bg-secondary rounded w-2/3" />
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="h-4 bg-secondary rounded w-1/2" />
                  <div className="h-4 bg-secondary rounded w-3/4" />
                  <div className="h-4 bg-secondary rounded w-2/3" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="flex items-center justify-center gap-2 mt-6 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">正在加载项目...</span>
        </div>
      </div>
    )
  }

  // ===== 错误状态（且未降级到 fallback） =====
  if (error && !usingFallback && projects.length === 0) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold">项目管理</h3>
          <Button className="gap-2" onClick={handleCreate}>
            <Plus className="w-4 h-4" />
            创建新项目
          </Button>
        </div>
        <Card>
          <CardContent className="p-8 text-center">
            <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-500" />
            <p className="font-semibold mb-1">加载项目失败</p>
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <div className="flex items-center justify-center gap-2">
              <Button variant="outline" size="sm" className="gap-1" onClick={handleRefresh}>
                <RefreshCw className="w-3 h-3" />
                重试
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">项目管理</h3>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-1" onClick={handleRefresh} disabled={loading}>
            {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            刷新
          </Button>
          <Button className="gap-2" onClick={handleCreate}>
            <Plus className="w-4 h-4" />
            创建新项目
          </Button>
        </div>
      </div>

      {/* 状态筛选 + 降级提示 */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex gap-1">
          {statusFilters.map(f => (
            <button
              key={f.value}
              onClick={() => handleFilterChange(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                statusFilter === f.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary hover:bg-secondary/80 text-muted-foreground'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        {usingFallback && (
          <Badge className="bg-yellow-100 text-yellow-700">
            示例数据（后端不可用）
          </Badge>
        )}
        {!usingFallback && (
          <span className="text-xs text-muted-foreground">
            共 {total} 个项目
          </span>
        )}
      </div>

      {projects.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            <Folder className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>暂无项目，点击右上角创建新项目</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {projects.map((project) => (
            <Card key={project.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <Folder className="w-5 h-5 text-primary flex-shrink-0" />
                    <h4 className="font-semibold truncate" title={project.name}>{project.name}</h4>
                  </div>
                  <Badge className={statusConfig[project.status].color}>
                    {statusConfig[project.status].label}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 mb-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="w-4 h-4" />
                    <span>时长: {formatDuration(project.duration)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Layers className="w-4 h-4" />
                    <span>{project.sceneCount} 个场景</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Monitor className="w-4 h-4" />
                    <span>{project.width}×{project.height}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Film className="w-4 h-4" />
                    <span>{project.frameRate} fps</span>
                  </div>
                  {project.appliedEffects.length > 0 && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span className="w-4 h-4 text-primary">✦</span>
                      <span>{project.appliedEffects.length} 个效果</span>
                    </div>
                  )}
                  {project.renderOutput && (
                    <div className="flex items-center gap-2 text-sm text-green-600">
                      <span className="w-4 h-4">▶</span>
                      <span className="truncate" title={project.renderOutput}>已渲染</span>
                    </div>
                  )}
                  <div className="text-xs text-muted-foreground">
                    创建于 {project.createdAt}
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="flex-1 gap-1" onClick={() => handleView(project)}>
                    <Eye className="w-3 h-3" />
                    查看
                  </Button>
                  <Button variant="outline" size="sm" className="gap-1" onClick={() => handleEdit(project)}>
                    <Edit className="w-3 h-3" />
                  </Button>
                  {project.status !== 'processing' && (
                    <Button variant="outline" size="sm" className="gap-1" onClick={() => handleRender(project)}>
                      <Play className="w-3 h-3" />
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className={`gap-1 ${deleteConfirm === project.id ? 'bg-red-50 text-red-600 border-red-300' : ''}`}
                    onClick={() => handleDelete(project)}
                  >
                    <Trash2 className="w-3 h-3" />
                    {deleteConfirm === project.id ? '?' : ''}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* 项目统计 */}
      <Card className="mt-6">
        <CardHeader>
          <h3 className="font-semibold">项目统计</h3>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4">
            {Object.entries(statusConfig).map(([key, config]) => {
              // 统计当前列表内的项目状态分布
              const count = projects.filter(p => p.status === key).length
              return (
                <div key={key} className="text-center">
                  <p className="text-2xl font-bold">{count}</p>
                  <p className={`text-sm ${config.color.replace('bg-', 'text-')}`}>{config.label}</p>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-6">
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
            第 {page} / {totalPages} 页
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

      {/* 详情抽屉 */}
      <ProjectDetailDrawer
        project={detailProject}
        open={!!detailProject}
        onClose={() => setDetailProject(null)}
        onEdit={handleEdit}
        onRender={handleRender}
      />

      {/* 渲染弹窗 */}
      <RenderProgressModal
        project={renderProject}
        open={!!renderProject}
        onClose={() => setRenderProject(null)}
      />

      {/* 编辑/创建弹窗 */}
      <ProjectEditModal
        project={editProject}
        open={!!editProject || editMode === 'create'}
        onClose={() => { setEditProject(null); setEditMode('edit') }}
        mode={editMode}
      />
    </div>
  )
}

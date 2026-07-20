import { Drawer } from '@/components/ui/Drawer'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useAppStore, Project } from '@/store/useAppStore'
import { useToast } from '@/components/ui/Toast'
import {
  Clock, Layers, Film, Monitor, Edit, Trash2, Play,
  CheckCircle2, XCircle, Folder, Calendar, Sparkles, FileVideo,
  Copy
} from 'lucide-react'

interface ProjectDetailDrawerProps {
  project: Project | null
  open: boolean
  onClose: () => void
  onEdit: (project: Project) => void
  onRender: (project: Project) => void
}

const statusConfig = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-600' },
  processing: { label: '执行中', color: 'bg-blue-100 text-blue-600' },
  completed: { label: '已完成', color: 'bg-green-100 text-green-600' },
  failed: { label: '失败', color: 'bg-red-100 text-red-600' },
}

const formatDuration = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function ProjectDetailDrawer({ project, open, onClose, onEdit, onRender }: ProjectDetailDrawerProps) {
  const { deleteProject, history } = useAppStore()
  const { showToast } = useToast()

  if (!project) return null

  const projectHistory = history.filter(h => h.projectId === project.id)

  const handleDelete = () => {
    deleteProject(project.id)
    showToast(`已删除项目: ${project.name}`, 'success')
    onClose()
  }

  const handleCopyPath = () => {
    if (project.renderOutput) {
      navigator.clipboard.writeText(project.renderOutput).then(() => {
        showToast('路径已复制到剪贴板', 'success')
      })
    }
  }

  const handleOpenFolder = () => {
    showToast('请在文件资源管理器中打开输出目录查看文件', 'info')
  }

  const getOutputDir = () => {
    if (!project.renderOutput) return ''
    const parts = project.renderOutput.split('/')
    parts.pop()
    return parts.join('/')
  }

  return (
    <Drawer open={open} onClose={onClose} title={project.name} width="640px">
      <div className="space-y-6">
        {/* 基本信息 */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Folder className="w-5 h-5 text-primary" />
              <h3 className="text-xl font-semibold">{project.name}</h3>
              <Badge className={statusConfig[project.status].color}>
                {statusConfig[project.status].label}
              </Badge>
            </div>
            {project.description && (
              <p className="text-muted-foreground">{project.description}</p>
            )}
          </div>
        </div>

        {/* 参数信息 */}
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
            <Clock className="w-5 h-5 text-primary" />
            <div>
              <p className="text-xs text-muted-foreground">总时长</p>
              <p className="font-semibold">{formatDuration(project.duration)}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
            <Layers className="w-5 h-5 text-primary" />
            <div>
              <p className="text-xs text-muted-foreground">场景数</p>
              <p className="font-semibold">{project.sceneCount} 个</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
            <Monitor className="w-5 h-5 text-primary" />
            <div>
              <p className="text-xs text-muted-foreground">合成尺寸</p>
              <p className="font-semibold">{project.width} × {project.height}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
            <Film className="w-5 h-5 text-primary" />
            <div>
              <p className="text-xs text-muted-foreground">帧率</p>
              <p className="font-semibold">{project.frameRate} fps</p>
            </div>
          </div>
        </div>

        {/* 时间信息 */}
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-1">
            <Calendar className="w-4 h-4" />
            创建于 {project.createdAt}
          </div>
          <div className="flex items-center gap-1">
            <Calendar className="w-4 h-4" />
            更新于 {project.updatedAt}
          </div>
        </div>

        {/* 场景列表 */}
        {project.scenes.length > 0 && (
          <div>
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <Layers className="w-4 h-4" />
              场景列表
            </h4>
            <div className="space-y-2">
              {project.scenes.map((scene, index) => (
                <div key={scene.id} className="flex items-center gap-3 p-3 rounded-lg border hover:bg-secondary/30 transition-colors">
                  <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center">
                    {index + 1}
                  </span>
                  <div className="flex-1">
                    <p className="font-medium text-sm">{scene.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDuration(scene.duration)} · {scene.layerCount} 个图层
                      {scene.effects.length > 0 && ` · ${scene.effects.length} 个效果`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 已应用效果 */}
        {project.appliedEffects.length > 0 && (
          <div>
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              已应用效果 ({project.appliedEffects.length})
            </h4>
            <div className="space-y-2">
              {project.appliedEffects.map((effect) => (
                <div key={effect.id} className="p-3 rounded-lg border">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">{effect.name}</span>
                    <Badge variant="secondary" className="text-xs">{effect.category}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {effect.params.map(p => (
                      <span key={p.name}>{p.name}: {p.value}{p.unit}</span>
                    ))}
                    {effect.blendMode && <span>混合: {effect.blendMode}</span>}
                    {effect.opacity !== undefined && <span>不透明度: {effect.opacity}%</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 渲染输出 */}
        {project.renderOutput && (
          <div>
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <FileVideo className="w-4 h-4" />
              渲染输出
            </h4>
            <div className="p-4 rounded-lg bg-green-50 border border-green-200">
              <div className="flex items-center gap-3 mb-3">
                <FileVideo className="w-6 h-6 text-green-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-green-700">
                    {project.renderOutput.split('/').pop()}
                  </p>
                  <p className="text-xs font-mono text-green-600 break-all">
                    {getOutputDir()}
                  </p>
                </div>
                <button
                  onClick={handleCopyPath}
                  className="p-2 rounded-lg hover:bg-green-100 transition-colors flex-shrink-0"
                  title="复制完整路径"
                >
                  <Copy className="w-4 h-4 text-green-600" />
                </button>
              </div>
              <div className="flex items-center justify-between text-xs text-green-600 pt-3 border-t border-green-200">
                <span>{project.width}×{project.height}</span>
                <span>{project.frameRate} fps</span>
                <span>{formatDuration(project.duration)}</span>
              </div>
              <div className="flex gap-2 mt-3">
                <Button variant="outline" size="sm" className="flex-1 gap-1 text-green-700 border-green-300 hover:bg-green-100" onClick={handleOpenFolder}>
                  <Folder className="w-3 h-3" />
                  打开文件夹
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* 操作历史 */}
        {projectHistory.length > 0 && (
          <div>
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4" />
              操作历史
            </h4>
            <div className="space-y-1">
              {projectHistory.slice(0, 10).map(h => (
                <div key={h.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-secondary/30 text-sm">
                  {h.result === 'success' && <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />}
                  {h.result === 'failure' && <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />}
                  {h.result === 'pending' && <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />}
                  <span className="flex-1 truncate">{h.action}</span>
                  <span className="text-xs text-muted-foreground">{h.timestamp}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-3 pt-4 border-t">
          <Button variant="outline" className="flex-1 gap-2" onClick={() => onEdit(project)}>
            <Edit className="w-4 h-4" />
            编辑
          </Button>
          {project.status !== 'processing' && (
            <Button className="flex-1 gap-2" onClick={() => onRender(project)}>
              <Play className="w-4 h-4" />
              渲染
            </Button>
          )}
          <Button variant="outline" className="gap-2 text-red-600 hover:text-red-600 hover:bg-red-50" onClick={handleDelete}>
            <Trash2 className="w-4 h-4" />
            删除
          </Button>
        </div>
      </div>
    </Drawer>
  )
}

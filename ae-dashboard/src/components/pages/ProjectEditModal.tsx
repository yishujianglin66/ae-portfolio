import { useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Project, useAppStore } from '@/store/useAppStore'
import { useToast } from '@/components/ui/Toast'
import { Save, Plus } from 'lucide-react'

interface ProjectEditModalProps {
  project: Project | null
  open: boolean
  onClose: () => void
  mode: 'edit' | 'create'
}

const sizePresets = [
  { label: '1920 × 1080 (Full HD)', width: 1920, height: 1080 },
  { label: '1080 × 1920 (竖屏)', width: 1080, height: 1920 },
  { label: '3840 × 2160 (4K)', width: 3840, height: 2160 },
  { label: '1080 × 1080 (方形)', width: 1080, height: 1080 },
]

const frameRateOptions = [24, 25, 30, 50, 60]

export function ProjectEditModal({ project, open, onClose, mode }: ProjectEditModalProps) {
  const { addProject, updateProject } = useAppStore()
  const { showToast } = useToast()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [width, setWidth] = useState(1920)
  const [height, setHeight] = useState(1080)
  const [duration, setDuration] = useState(60)
  const [frameRate, setFrameRate] = useState(30)
  const [sceneCount, setSceneCount] = useState(3)

  useEffect(() => {
    if (open) {
      if (project && mode === 'edit') {
        setName(project.name)
        setDescription(project.description || '')
        setWidth(project.width)
        setHeight(project.height)
        setDuration(project.duration)
        setFrameRate(project.frameRate)
        setSceneCount(project.sceneCount)
      } else {
        setName('')
        setDescription('')
        setWidth(1920)
        setHeight(1080)
        setDuration(60)
        setFrameRate(30)
        setSceneCount(3)
      }
    }
  }, [open, project, mode])

  const handleSave = () => {
    if (!name.trim()) {
      showToast('请输入项目名称', 'warning')
      return
    }

    if (mode === 'create') {
      addProject({
        name,
        description,
        status: 'draft',
        duration,
        sceneCount,
        width,
        height,
        frameRate,
        scenes: Array.from({ length: sceneCount }, (_, i) => ({
          id: `s${Date.now()}_${i}`,
          name: `场景 ${i + 1}`,
          duration: Math.floor(duration / sceneCount),
          layerCount: 0,
          effects: [],
        })),
        appliedEffects: [],
      })
      showToast(`项目「${name}」创建成功`, 'success')
    } else if (project) {
      updateProject(project.id, {
        name,
        description,
        width,
        height,
        duration,
        frameRate,
        sceneCount,
      })
      showToast(`项目「${name}」已更新`, 'success')
    }
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={mode === 'create' ? '创建新项目' : `编辑 - ${project?.name}`}
      maxWidth="560px"
    >
      <div className="space-y-5">
        {/* 项目名称 */}
        <div>
          <label className="text-sm font-medium mb-2 block">项目名称 <span className="text-red-500">*</span></label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="输入项目名称"
          />
        </div>

        {/* 项目描述 */}
        <div>
          <label className="text-sm font-medium mb-2 block">项目描述</label>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="可选，简要描述项目内容"
          />
        </div>

        {/* 合成尺寸 */}
        <div>
          <label className="text-sm font-medium mb-2 block">合成尺寸</label>
          <div className="grid grid-cols-2 gap-2">
            {sizePresets.map(preset => (
              <button
                key={preset.label}
                onClick={() => { setWidth(preset.width); setHeight(preset.height) }}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  width === preset.width && height === preset.height
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <p className="text-sm font-medium">{preset.width} × {preset.height}</p>
                <p className="text-xs text-muted-foreground">{preset.label.split(' ')[2]}</p>
              </button>
            ))}
          </div>
        </div>

        {/* 帧率 */}
        <div>
          <label className="text-sm font-medium mb-2 block">帧率</label>
          <div className="flex gap-2">
            {frameRateOptions.map(fps => (
              <button
                key={fps}
                onClick={() => setFrameRate(fps)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  frameRate === fps
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary hover:bg-secondary/80'
                }`}
              >
                {fps} fps
              </button>
            ))}
          </div>
        </div>

        {/* 时长 + 场景数 */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium mb-2 block">总时长 (秒)</label>
            <Input
              type="number"
              value={duration}
              onChange={(e) => setDuration(Math.max(1, parseInt(e.target.value) || 0))}
              min={1}
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block">场景数量</label>
            <Input
              type="number"
              value={sceneCount}
              onChange={(e) => setSceneCount(Math.max(1, parseInt(e.target.value) || 0))}
              min={1}
            />
          </div>
        </div>

        {/* 按钮 */}
        <div className="flex gap-3 pt-4 border-t">
          <Button variant="outline" className="flex-1" onClick={onClose}>取消</Button>
          <Button className="flex-1 gap-2" onClick={handleSave}>
            {mode === 'create' ? (
              <>
                <Plus className="w-4 h-4" />
                创建项目
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                保存修改
              </>
            )}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

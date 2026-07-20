import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useToast } from '@/components/ui/Toast'
import { useAppStore, AppliedEffect } from '@/store/useAppStore'
import { mockEffects, mockStyleTemplates } from '@/data/mockData'
import { CheckCircle2, Eye, Sparkles, Play } from 'lucide-react'

type PreviewType = 'effect' | 'style' | 'command'

interface PreviewModalProps {
  open: boolean
  onClose: () => void
  type: PreviewType
  // 效果预览
  effectName?: string
  effectParams?: { name: string; value: number; unit: string }[]
  // 风格预览
  styleId?: string
  styleIntensity?: number
  // 命令预览
  commandText?: string
  parsedParams?: Record<string, unknown>
}

export function PreviewModal({
  open, onClose, type,
  effectName, effectParams,
  styleId, styleIntensity,
  commandText, parsedParams,
}: PreviewModalProps) {
  const { showToast } = useToast()
  const { applyEffectToProject, projects } = useAppStore()

  const effect = mockEffects.find(e => e.name === effectName)
  const style = mockStyleTemplates.find(s => s.id === styleId)
  const activeProject = projects.find(p => p.status === 'processing' || p.status === 'draft')

  const handleApplyEffect = () => {
    if (!effectName || !effectParams) return
    const appliedEffect: AppliedEffect = {
      id: Date.now().toString(),
      name: effectName,
      category: effect?.category || '通用',
      params: effectParams.map(p => ({ ...p, min: 0, max: 100 })),
      appliedAt: new Date().toISOString(),
    }
    applyEffectToProject(activeProject?.id || null, appliedEffect)
    showToast(`已将「${effectName}」应用到${activeProject ? `项目「${activeProject.name}」` : '当前图层'}`, 'success')
    onClose()
  }

  const handleApplyStyle = () => {
    if (!style) return
    showToast(`已将「${style.name}」风格应用到${activeProject ? `项目「${activeProject.name}」` : '当前项目'}`, 'success')
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="预览" maxWidth="640px">
      <div className="space-y-4">
        {/* 效果预览 */}
        {type === 'effect' && effectName && (
          <>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-primary" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">{effectName}</h3>
                {effect && <Badge variant="secondary">{effect.category}</Badge>}
              </div>
            </div>

            {/* 效果参数 */}
            {effectParams && effectParams.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">参数</h4>
                <div className="grid grid-cols-2 gap-3">
                  {effectParams.map(param => (
                    <div key={param.name} className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
                      <span className="text-sm text-muted-foreground">{param.name}</span>
                      <span className="font-semibold">{param.value}{param.unit}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 预览区域 - 模拟效果 */}
            <div>
              <h4 className="text-sm font-semibold mb-2">效果预览</h4>
              <div className="rounded-lg overflow-hidden border bg-gray-900 aspect-video flex items-center justify-center relative">
                <div className="text-center">
                  <div
                    className="inline-block transition-all"
                    style={{
                      filter: effectName?.includes('发光') || effectName?.includes('辉光')
                        ? `drop-shadow(0 0 ${effectParams?.find(p => p.name === '半径')?.value || 20}px rgba(0, 150, 255, 0.8))`
                        : effectName?.includes('模糊')
                        ? `blur(${(effectParams?.find(p => p.name === '半径')?.value || 5) * 0.3}px)`
                        : 'none'
                    }}
                  >
                    <p className="text-white text-2xl font-bold">预览文本</p>
                  </div>
                  <p className="text-gray-500 text-xs mt-2">效果预览模拟</p>
                </div>
              </div>
            </div>

            <div className="flex gap-3 pt-4 border-t">
              <Button variant="outline" className="flex-1" onClick={onClose}>取消</Button>
              <Button className="flex-1 gap-2" onClick={handleApplyEffect}>
                <CheckCircle2 className="w-4 h-4" />
                应用到{activeProject ? '项目' : '图层'}
              </Button>
            </div>
          </>
        )}

        {/* 风格预览 */}
        {type === 'style' && style && (
          <>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg overflow-hidden">
                <img src={style.thumbnail} alt={style.name} className="w-full h-full object-cover" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">{style.name}</h3>
                <Badge variant="secondary">强度: {((styleIntensity || 0.5) * 100).toFixed(0)}%</Badge>
              </div>
            </div>

            <div className="rounded-lg overflow-hidden border">
              <img src={style.thumbnail} alt={style.name} className="w-full" />
            </div>

            <div>
              <h4 className="text-sm font-semibold mb-2">风格描述</h4>
              <p className="text-sm text-muted-foreground">{style.description}</p>
            </div>

            <div>
              <h4 className="text-sm font-semibold mb-2">包含效果</h4>
              <div className="flex flex-wrap gap-2">
                {style.effects.map(eff => (
                  <Badge key={eff} variant="secondary" className="flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    {eff}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="flex gap-3 pt-4 border-t">
              <Button variant="outline" className="flex-1" onClick={onClose}>取消</Button>
              <Button className="flex-1 gap-2" onClick={handleApplyStyle}>
                <CheckCircle2 className="w-4 h-4" />
                应用到{activeProject ? '项目' : '当前'}
              </Button>
            </div>
          </>
        )}

        {/* 命令预览 */}
        {type === 'command' && commandText && (
          <>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                <Play className="w-6 h-6 text-primary" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">命令解析预览</h3>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold mb-2">输入命令</h4>
              <div className="p-3 rounded-lg bg-secondary/50 font-mono text-sm">
                {commandText}
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold mb-2">解析结果</h4>
              <div className="space-y-2">
                {parsedParams && Object.entries(parsedParams).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between p-2 rounded-lg border">
                    <span className="text-sm text-muted-foreground">{key}</span>
                    <span className="font-mono text-sm font-semibold">{String(value)}</span>
                  </div>
                ))}
                {(!parsedParams || Object.keys(parsedParams).length === 0) && (
                  <p className="text-sm text-muted-foreground">未解析到参数</p>
                )}
              </div>
            </div>

            <div className="flex gap-3 pt-4 border-t">
              <Button variant="outline" className="flex-1" onClick={onClose}>取消</Button>
              <Button className="flex-1 gap-2" onClick={() => { showToast('请点击「执行命令」按钮执行', 'info'); onClose() }}>
                <Eye className="w-4 h-4" />
                确认执行
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}

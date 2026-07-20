import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Slider } from '@/components/ui/Slider'
import { useToast } from '@/components/ui/Toast'
import { mockStyleTemplates, mockEffects, type StyleTemplate } from '@/data/mockData'
import { api } from '@/lib/api'
import { Palette, Heart, Sparkles, CheckCircle2, Eye, Sliders, Loader2 } from 'lucide-react'

// 将后端 API 返回的数据适配为前端 StyleTemplate 类型
function adaptStyle(raw: any): StyleTemplate {
  const id = String(raw.id ?? raw.style_id ?? raw.key ?? '')
  const name = String(raw.name ?? raw.label ?? raw.display_name ?? '未命名风格')
  const description = String(raw.description ?? raw.desc ?? raw.summary ?? '')
  const thumbnail = String(raw.thumbnail ?? raw.image ?? raw.preview_url ?? '')
  // effects 适配：支持 string[] 或 [{name: ...}]
  const rawEffects: any[] = Array.isArray(raw.effects) ? raw.effects
    : Array.isArray(raw.effect_list) ? raw.effect_list
    : []
  const effects: string[] = rawEffects.map((e: any) =>
    typeof e === 'string' ? e : String(e.name ?? e.label ?? e.id ?? '')
  )
  const intensity = typeof raw.intensity === 'number' ? raw.intensity
    : typeof raw.strength === 'number' ? raw.strength
    : 0.5
  return { id, name, description, thumbnail, effects, intensity }
}

export function StylesPanel() {
  const { showToast } = useToast()
  const [styles, setStyles] = useState<StyleTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedStyle, setSelectedStyle] = useState<StyleTemplate | null>(null)
  const [intensity, setIntensity] = useState(0.5)
  const [favorites, setFavorites] = useState<Set<string>>(new Set())
  const [showCustomize, setShowCustomize] = useState(false)
  const [enabledEffects, setEnabledEffects] = useState<Record<string, boolean>>({})

  // 组件挂载时调用 API 获取风格列表
  useEffect(() => {
    let mounted = true
    const loadStyles = async () => {
      setLoading(true)
      try {
        const res: any = await api.getStyles()
        // 兼容多种返回结构
        const list: any[] = Array.isArray(res) ? res
          : Array.isArray(res?.items) ? res.items
          : Array.isArray(res?.data) ? res.data
          : Array.isArray(res?.styles) ? res.styles
          : []
        if (!mounted) return
        if (list.length === 0) {
          setStyles(mockStyleTemplates)
          showToast('API 返回空数据，已回退到本地风格库', 'info')
        } else {
          setStyles(list.map(adaptStyle))
        }
      } catch (err) {
        if (!mounted) return
        setStyles(mockStyleTemplates)
        showToast(`风格列表加载失败，已使用本地数据: ${(err as Error).message}`, 'error')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    loadStyles()
    return () => { mounted = false }
  }, [])

  // 数据加载完成后默认选中第一个风格
  useEffect(() => {
    if (!selectedStyle && styles.length > 0) {
      const first = styles[0]
      setSelectedStyle(first)
      setIntensity(first.intensity)
      const enabled: Record<string, boolean> = {}
      first.effects.forEach(e => { enabled[e] = true })
      setEnabledEffects(enabled)
    }
  }, [styles, selectedStyle])

  const getEffectNames = (effectIds: string[]) => {
    return effectIds.map(id => {
      const effect = mockEffects.find(e => e.name === id)
      return effect ? effect.name : id
    })
  }

  const handleSelectStyle = (style: StyleTemplate) => {
    setSelectedStyle(style)
    setIntensity(style.intensity)
    setShowCustomize(false)
    const enabled: Record<string, boolean> = {}
    style.effects.forEach(e => { enabled[e] = true })
    setEnabledEffects(enabled)
  }

  const handleApply = () => {
    if (!selectedStyle) return
    showToast(`已将「${selectedStyle.name}」风格应用到当前项目`, 'success')
  }

  const handlePreview = () => {
    if (!selectedStyle) return
    showToast(`正在预览「${selectedStyle.name}」风格...`, 'info')
    setTimeout(() => showToast('预览完成', 'success'), 800)
  }

  const handleToggleFavorite = (styleId: string, styleName: string) => {
    setFavorites(prev => {
      const next = new Set(prev)
      if (next.has(styleId)) {
        next.delete(styleId)
        showToast(`已取消收藏「${styleName}」`, 'info')
      } else {
        next.add(styleId)
        showToast(`已收藏「${styleName}」`, 'success')
      }
      return next
    })
  }

  const handleCreateNew = () => {
    showToast('新建风格模板功能开发中...', 'info')
  }

  const handleToggleEffect = (effectName: string) => {
    setEnabledEffects(prev => ({ ...prev, [effectName]: !prev[effectName] }))
  }

  // 加载中状态
  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <span className="text-sm">正在加载风格模板...</span>
        </div>
      </div>
    )
  }

  // 无数据兜底
  if (!selectedStyle) {
    return (
      <div className="p-6 flex items-center justify-center h-64 text-muted-foreground text-sm">
        暂无风格模板数据
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold">风格模板</h3>
          <Badge variant="secondary">{styles.length} 个模板</Badge>
        </div>
        <Button variant="outline" className="gap-2" onClick={handleCreateNew}>
          <Palette className="w-4 h-4" />
          创建新风格
        </Button>
      </div>

      <div className="grid grid-cols-5 gap-4">
        {styles.map((style) => (
          <Card
            key={style.id}
            onClick={() => handleSelectStyle(style)}
            className={`cursor-pointer transition-all hover:shadow-lg ${
              selectedStyle.id === style.id ? 'ring-2 ring-primary' : ''
            }`}
          >
            <CardContent className="p-4">
              <div className="aspect-square rounded-lg overflow-hidden mb-3">
                <img
                  src={style.thumbnail}
                  alt={style.name}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="flex items-center justify-between mb-1">
                <h4 className="font-medium">{style.name}</h4>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleToggleFavorite(style.id, style.name)
                  }}
                  className={`p-1 hover:bg-secondary rounded ${favorites.has(style.id) ? 'text-red-500' : 'text-muted-foreground'}`}
                >
                  <Heart className="w-4 h-4" fill={favorites.has(style.id) ? 'currentColor' : 'none'} />
                </button>
              </div>
              <p className="text-xs text-muted-foreground line-clamp-2">{style.description}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {style.effects.map((effect) => (
                  <Badge key={effect} variant="secondary" className="text-xs">
                    {effect}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="mt-6">
        <CardContent className="p-6">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="aspect-video rounded-lg overflow-hidden mb-4">
                <img
                  src={selectedStyle.thumbnail}
                  alt={selectedStyle.name}
                  className="w-full h-full object-cover"
                />
              </div>
              <h3 className="text-xl font-semibold mb-2">{selectedStyle.name}</h3>
              <p className="text-muted-foreground">{selectedStyle.description}</p>
            </div>

            <div className="space-y-6">
              <div>
                <h4 className="font-medium mb-2">效果强度</h4>
                <div className="flex items-center gap-4">
                  <Slider
                    value={intensity}
                    onChange={setIntensity}
                    min={0}
                    max={1}
                    step={0.1}
                    className="flex-1"
                  />
                  <span className="text-sm font-medium w-12">{(intensity * 100).toFixed(0)}%</span>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium">包含效果</h4>
                  <Button variant="ghost" size="sm" onClick={() => setShowCustomize(!showCustomize)}>
                    <Sliders className="w-3 h-3 mr-1" />
                    {showCustomize ? '完成' : '自定义'}
                  </Button>
                </div>
                <div className="space-y-2">
                  {getEffectNames(selectedStyle.effects).map((effect) => (
                    <div
                      key={effect}
                      onClick={() => showCustomize && handleToggleEffect(effect)}
                      className={`flex items-center gap-2 p-2 rounded-lg transition-colors ${
                        showCustomize ? 'cursor-pointer hover:bg-secondary' : ''
                      } ${enabledEffects[effect] === false ? 'bg-secondary/30 opacity-50' : 'bg-secondary/50'}`}
                    >
                      <Sparkles className="w-4 h-4 text-primary" />
                      <span className="text-sm">{effect}</span>
                      {showCustomize && (
                        <span className="ml-auto text-xs">
                          {enabledEffects[effect] !== false ? '已启用' : '已禁用'}
                        </span>
                      )}
                      {!showCustomize && <CheckCircle2 className="w-4 h-4 text-green-500 ml-auto" />}
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex gap-3">
                <Button className="flex-1 gap-2" onClick={handleApply}>
                  <CheckCircle2 className="w-4 h-4" />
                  应用到项目
                </Button>
                <Button variant="outline" className="gap-2" onClick={handlePreview}>
                  <Eye className="w-4 h-4" />
                  预览
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

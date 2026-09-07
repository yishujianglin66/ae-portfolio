import React, { useState, useMemo, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { Slider } from '@/components/ui/Slider'
import { useToast } from '@/components/ui/Toast'
import { mockEffects, type Effect } from '@/data/mockData'
import { api } from '@/lib/api'
import { Sparkles, CircleDot, Zap, Search, Plus, Settings, Wind, Layers, Eye, Check, CheckCircle2, Loader2 } from 'lucide-react'
import { useDebounce } from '@/lib/utils'

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Sparkles,
  Wind,
  CircleDot,
  Zap,
  Layers,
}

// 将后端 API 返回的数据适配为前端 Effect 类型
function adaptEffect(raw: any): Effect {
  // 兼容多种字段命名（name/label, params/parameters 等）
  const id = String(raw.id ?? raw.effect_id ?? raw.key ?? '')
  const name = String(raw.name ?? raw.label ?? raw.display_name ?? '未命名效果')
  const category = String(raw.category ?? raw.group ?? raw.type ?? '通用')
  const icon = String(raw.icon ?? 'Sparkles')
  // 参数适配：支持 { name, value, min, max, unit } 或 { key, default, range: [min, max] } 等结构
  const rawParams: any[] = Array.isArray(raw.params) ? raw.params
    : Array.isArray(raw.parameters) ? raw.parameters
    : Array.isArray(raw.props) ? raw.props
    : []
  const params = rawParams.map((p: any) => ({
    name: String(p.name ?? p.key ?? p.label ?? '参数'),
    value: typeof p.value === 'number' ? p.value : (typeof p.default === 'number' ? p.default : 0),
    min: typeof p.min === 'number' ? p.min : (Array.isArray(p.range) ? p.range[0] : 0),
    max: typeof p.max === 'number' ? p.max : (Array.isArray(p.range) ? p.range[1] : 100),
    unit: String(p.unit ?? p.suffix ?? ''),
  }))
  return { id, name, category, icon, params }
}

export function EffectsPanel() {
  const { showToast } = useToast()
  const [searchTerm, setSearchTerm] = useState('')
  const debouncedSearchTerm = useDebounce(searchTerm, 200)
  const [effects, setEffects] = useState<Effect[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedEffect, setSelectedEffect] = useState<Effect | null>(null)
  const [params, setParams] = useState<Effect['params']>([])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [favorites, setFavorites] = useState<Set<string>>(new Set())
  const [appliedEffects, setAppliedEffects] = useState<{ name: string; params: Record<string, number> }[]>([])

  // 组件挂载时调用 API 获取效果列表
  useEffect(() => {
    let mounted = true
    const loadEffects = async () => {
      setLoading(true)
      try {
        const res: any = await api.getEffects()
        // 兼容多种返回结构：数组 / { items: [...] } / { data: [...] } / { effects: [...] }
        const list: any[] = Array.isArray(res) ? res
          : Array.isArray(res?.items) ? res.items
          : Array.isArray(res?.data) ? res.data
          : Array.isArray(res?.effects) ? res.effects
          : []
        if (!mounted) return
        if (list.length === 0) {
          // API 返回空列表，回退到 mock
          setEffects(mockEffects)
          showToast('API 返回空数据，已回退到本地效果库', 'info')
        } else {
          const adapted = list.map(adaptEffect)
          setEffects(adapted)
        }
      } catch (err) {
        if (!mounted) return
        // API 失败，回退到 mockEffects 数据
        setEffects(mockEffects)
        showToast(`效果列表加载失败，已使用本地数据: ${(err as Error).message}`, 'error')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    loadEffects()
    return () => { mounted = false }
  }, [])

  // 数据加载完成后设置默认选中第一个效果
  useEffect(() => {
    if (!selectedEffect && effects.length > 0) {
      const first = effects[0]
      setSelectedEffect(first)
      setParams(first.params)
    }
  }, [effects, selectedEffect])

  const filteredEffects = useMemo(() => effects.filter(effect =>
    effect.name.toLowerCase().includes(debouncedSearchTerm.toLowerCase()) ||
    effect.category.toLowerCase().includes(debouncedSearchTerm.toLowerCase())
  ), [debouncedSearchTerm, effects])

  const handleParamChange = (paramName: string, value: number) => {
    setParams(prev => prev.map(p => p.name === paramName ? { ...p, value } : p))
  }

  const handleEffectSelect = (effect: Effect) => {
    setSelectedEffect(effect)
    setParams(effect.params)
    setShowAdvanced(false)
  }

  const handleAddEffect = () => {
    if (!selectedEffect) return
    showToast(`已选择效果: ${selectedEffect.name}`, 'info')
  }

  const handleApplyToLayer = () => {
    if (!selectedEffect) return
    const paramObj: Record<string, number> = {}
    params.forEach(p => { paramObj[p.name] = p.value })
    setAppliedEffects(prev => [...prev, { name: selectedEffect.name, params: paramObj }])
    showToast(`已将「${selectedEffect.name}」应用到选中图层`, 'success')
  }

  const handlePreview = () => {
    if (!selectedEffect) return
    showToast(`正在预览「${selectedEffect.name}」效果...`, 'info')
    setTimeout(() => {
      showToast(`预览完成，参数已生效`, 'success')
    }, 800)
  }

  const handleToggleFavorite = (effectName: string) => {
    setFavorites(prev => {
      const next = new Set(prev)
      if (next.has(effectName)) {
        next.delete(effectName)
        showToast(`已取消收藏「${effectName}」`, 'info')
      } else {
        next.add(effectName)
        showToast(`已收藏「${effectName}」`, 'success')
      }
      return next
    })
  }

  const handleResetParams = () => {
    if (!selectedEffect) return
    setParams(selectedEffect.params)
    showToast('参数已重置为默认值', 'info')
  }

  // 加载中状态
  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <span className="text-sm">正在加载效果列表...</span>
        </div>
      </div>
    )
  }

  // 无数据兜底
  if (!selectedEffect) {
    return (
      <div className="p-6 flex items-center justify-center h-64 text-muted-foreground text-sm">
        暂无效果数据
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="搜索效果..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 w-64"
          />
        </div>
        <div className="flex gap-2">
          {appliedEffects.length > 0 && (
            <Badge variant="secondary" className="flex items-center gap-1">
              <Check className="w-3 h-3" />
              已应用 {appliedEffects.length} 个效果
            </Badge>
          )}
          <Button className="gap-2" onClick={handleAddEffect}>
            <Plus className="w-4 h-4" />
            添加效果
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-6">
        <div className="col-span-1">
          <Card>
            <CardContent className="p-4">
              <h3 className="font-semibold mb-4">效果列表</h3>
              <div className="space-y-2">
                {filteredEffects.map((effect) => (
                  <div
                    key={effect.id}
                    onClick={() => handleEffectSelect(effect)}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg transition-colors cursor-pointer ${
                      selectedEffect.id === effect.id
                        ? 'bg-primary text-primary-foreground'
                        : 'hover:bg-secondary'
                    }`}
                  >
                    {iconMap[effect.icon] && React.createElement(iconMap[effect.icon], { className: 'w-5 h-5' })}
                    <div className="text-left flex-1">
                      <p className="text-sm font-medium">{effect.name}</p>
                      <p className="text-xs opacity-70">{effect.category}</p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleToggleFavorite(effect.name)
                      }}
                      className={`p-1 rounded hover:bg-black/10 ${favorites.has(effect.name) ? 'text-yellow-400' : 'opacity-50'}`}
                    >
                      <svg className="w-4 h-4" fill={favorites.has(effect.name) ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                      </svg>
                    </button>
                  </div>
                ))}
                {filteredEffects.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    未找到匹配的效果
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="col-span-3">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  {iconMap[selectedEffect.icon] && React.createElement(iconMap[selectedEffect.icon], { className: 'w-8 h-8 text-primary' })}
                  <div>
                    <h3 className="text-xl font-semibold">{selectedEffect.name}</h3>
                    <Badge variant="secondary">{selectedEffect.category}</Badge>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleResetParams}>
                    重置参数
                  </Button>
                  <Button variant="outline" className="gap-2" onClick={() => setShowAdvanced(!showAdvanced)}>
                    <Settings className="w-4 h-4" />
                    {showAdvanced ? '收起' : '高级设置'}
                  </Button>
                </div>
              </div>

              <div className="space-y-6">
                {params.map((param) => (
                  <div key={param.name}>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium">{param.name}</label>
                      <span className="text-sm text-muted-foreground">
                        {param.value}{param.unit}
                      </span>
                    </div>
                    <Slider
                      value={param.value}
                      onChange={(value) => handleParamChange(param.name, value)}
                      min={param.min}
                      max={param.max}
                      step={param.unit === '' && param.max <= 10 ? 0.1 : 1}
                    />
                  </div>
                ))}

                {showAdvanced && (
                  <div className="border-t pt-4 space-y-4">
                    <h4 className="text-sm font-semibold text-muted-foreground">高级参数</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-sm font-medium mb-2 block">混合模式</label>
                        <select className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm">
                          <option>正常</option>
                          <option>叠加</option>
                          <option>滤色</option>
                          <option>柔光</option>
                          <option>强光</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-sm font-medium mb-2 block">不透明度</label>
                        <div className="flex items-center gap-3">
                          <Slider value={100} onChange={() => {}} min={0} max={100} step={1} className="flex-1" />
                          <span className="text-sm w-12">100%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-8">
                <Button className="flex-1 gap-2" onClick={handleApplyToLayer}>
                  <Check className="w-4 h-4" />
                  应用到图层
                </Button>
                <Button variant="outline" className="gap-2" onClick={handlePreview}>
                  <Eye className="w-4 h-4" />
                  预览效果
                </Button>
              </div>

              {appliedEffects.length > 0 && (
                <div className="mt-6 border-t pt-4">
                  <h4 className="text-sm font-semibold mb-3">已应用效果列表</h4>
                  <div className="space-y-2">
                    {appliedEffects.map((applied, index) => (
                      <div key={index} className="flex items-center gap-3 p-2 rounded-lg bg-secondary/50">
                        <CheckCircle2 className="w-4 h-4 text-green-500" />
                        <span className="text-sm font-medium">{applied.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {Object.entries(applied.params).map(([k, v]) => `${k}: ${v}`).join(', ')}
                        </span>
                        <button
                          onClick={() => {
                            setAppliedEffects(prev => prev.filter((_, i) => i !== index))
                            showToast(`已移除「${applied.name}」`, 'info')
                          }}
                          className="ml-auto text-xs text-red-500 hover:text-red-700"
                        >
                          移除
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { Zap, Play, Download, Sparkles, Eye, Settings2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

interface StyleAnalysis {
  color_palette: string
  color_temperature: string
  contrast: string
  pace: string
  bpm?: number
  transitions: string[]
  effects: string[]
  camera_movements: string[]
  text_style?: {
    font: string
    color: string
    position: string
    animation: string
  }
  audio_mood: string
  mood_keywords: string[]
}

interface ToolStep {
  tool: string
  action: string
  params: Record<string, unknown>
  input: string
  output: string
}

export function StyleCopyPanel() {
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [style, setStyle] = useState<StyleAnalysis | null>(null)
  const [steps, setSteps] = useState<ToolStep[]>([])
  const [resultVideo, setResultVideo] = useState('')
  const [currentStep, setCurrentStep] = useState(0)

  const handleAnalyze = async () => {
    if (!input.trim()) return
    setIsLoading(true)
    
    try {
      const response = await fetch('/api/style-copy/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: input.trim() })
      })
      const data = await response.json()
      
      if (data.success && data.style) {
        setStyle(data.style)
      }
    } catch (error) {
      console.error('分析失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!input.trim()) return
    setIsLoading(true)
    setCurrentStep(0)
    
    try {
      const response = await fetch('/api/style-copy/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: input.trim() })
      })
      const data = await response.json()
      
      if (data.success && data.data) {
        setStyle(data.data.style)
        setSteps(data.data.tool_sequence || [])
        
        if (data.data.output_path) {
          setResultVideo(data.data.output_path)
        }
      }
    } catch (error) {
      console.error('生成失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">视频风格智能复制</h1>
        <p className="text-muted-foreground">输入视频链接或描述风格，自动分析并生成风格化视频</p>
      </div>

      <Card className="mb-6">
        <CardContent className="p-6">
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="输入视频链接（YouTube/Bilibili/抖音）或描述风格（如：赛博朋克风格，高对比度）"
                className="h-12 text-base"
              />
            </div>
            <Button
              onClick={handleAnalyze}
              disabled={!input.trim() || isLoading}
              className="h-12 px-6"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              分析风格
            </Button>
            <Button
              onClick={handleGenerate}
              disabled={!input.trim() || isLoading}
              className="h-12 px-6 bg-primary hover:bg-primary/90"
            >
              <Play className="w-4 h-4 mr-2" />
              {isLoading ? '处理中...' : '一键生成'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary mr-3" />
          <span className="text-lg font-medium">正在处理，请稍候...</span>
        </div>
      )}

      {style && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5" />
                <span className="text-lg font-bold">风格分析结果</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-secondary/50 rounded-lg p-3">
                  <p className="text-sm text-muted-foreground">色板</p>
                  <p className="font-medium">{style.color_palette}</p>
                </div>
                <div className="bg-secondary/50 rounded-lg p-3">
                  <p className="text-sm text-muted-foreground">色温</p>
                  <Badge variant="outline">{style.color_temperature}</Badge>
                </div>
                <div className="bg-secondary/50 rounded-lg p-3">
                  <p className="text-sm text-muted-foreground">对比度</p>
                  <Badge variant="outline">{style.contrast}</Badge>
                </div>
                <div className="bg-secondary/50 rounded-lg p-3">
                  <p className="text-sm text-muted-foreground">节奏</p>
                  <Badge variant="outline">{style.pace}</Badge>
                </div>
              </div>

              {style.bpm && (
                <div className="bg-secondary/50 rounded-lg p-3">
                  <p className="text-sm text-muted-foreground">BPM</p>
                  <p className="text-2xl font-bold">{style.bpm}</p>
                </div>
              )}

              <div>
                <p className="text-sm text-muted-foreground mb-2">转场类型</p>
                <div className="flex flex-wrap gap-2">
                  {style.transitions.map((t, i) => (
                    <Badge key={i} variant="secondary">{t}</Badge>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-sm text-muted-foreground mb-2">特效</p>
                <div className="flex flex-wrap gap-2">
                  {style.effects.map((e, i) => (
                    <Badge key={i} variant="secondary">{e}</Badge>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-sm text-muted-foreground mb-2">运镜</p>
                <div className="flex flex-wrap gap-2">
                  {style.camera_movements.map((c, i) => (
                    <Badge key={i} variant="secondary">{c}</Badge>
                  ))}
                </div>
              </div>

              {style.text_style && (
                <div className="bg-secondary/50 rounded-lg p-3">
                  <p className="text-sm text-muted-foreground mb-2">字幕风格</p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <span className="text-muted-foreground">字体:</span>
                    <span>{style.text_style.font}</span>
                    <span className="text-muted-foreground">颜色:</span>
                    <span>{style.text_style.color}</span>
                    <span className="text-muted-foreground">位置:</span>
                    <span>{style.text_style.position}</span>
                    <span className="text-muted-foreground">动画:</span>
                    <span>{style.text_style.animation}</span>
                  </div>
                </div>
              )}

              <div>
                <p className="text-sm text-muted-foreground mb-2">情绪关键词</p>
                <div className="flex flex-wrap gap-2">
                  {style.mood_keywords.map((k, i) => (
                    <Badge key={i}>{k}</Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Settings2 className="w-5 h-5" />
                <span className="text-lg font-bold">工具调用序列</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {steps.length > 0 ? (
                steps.map((step, index) => (
                  <div
                    key={index}
                    className={cn(
                      'p-4 rounded-lg border transition-all',
                      index < currentStep ? 'bg-success/10 border-success' : '',
                      index === currentStep ? 'bg-primary/10 border-primary' : '',
                      index > currentStep ? 'bg-secondary/30 border-secondary' : ''
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-sm font-medium">
                          {index + 1}
                        </span>
                        <span className="font-medium">{step.tool}</span>
                        <Badge variant="outline">{step.action}</Badge>
                      </div>
                      {index < currentStep && (
                        <span className="text-green-600 text-sm">✓ 完成</span>
                      )}
                      {index === currentStep && (
                        <span className="text-primary text-sm">处理中...</span>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      <p>输入: {step.input}</p>
                      <p>输出: {step.output}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Zap className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>点击"一键生成"查看工具调用序列</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {resultVideo && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Eye className="w-5 h-5" />
              <span className="text-lg font-bold">输出结果</span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="bg-black rounded-lg overflow-hidden">
              <video
                src={resultVideo}
                controls
                className="w-full max-h-96"
              />
            </div>
            <div className="mt-4 flex gap-2">
              <Button variant="outline">
                <Download className="w-4 h-4 mr-2" />
                下载视频
              </Button>
              <Button>
                <Zap className="w-4 h-4 mr-2" />
                再次生成
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
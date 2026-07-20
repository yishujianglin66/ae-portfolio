import { useState, useEffect, useRef } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Project, useAppStore } from '@/store/useAppStore'
import { useToast } from '@/components/ui/Toast'
import {
  Play, CheckCircle2, XCircle, Loader2, FileVideo, Folder,
  RefreshCw, Download, Copy, Settings, FileJson, Pause
} from 'lucide-react'

interface RenderProgressModalProps {
  project: Project | null
  open: boolean
  onClose: () => void
}

type RenderStatus = 'idle' | 'rendering' | 'success' | 'failed'
type OutputFormat = 'mp4' | 'mov' | 'avi' | 'json'

export function RenderProgressModal({ project, open, onClose }: RenderProgressModalProps) {
  const { updateProject, addHistory, settings } = useAppStore()
  const { showToast } = useToast()
  const [status, setStatus] = useState<RenderStatus>('idle')
  const [progress, setProgress] = useState(0)
  const [logs, setLogs] = useState<string[]>([])
  const [outputPath, setOutputPath] = useState<string | null>(null)
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('mp4')
  const [fileName, setFileName] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [fileSize, setFileSize] = useState<string>('')
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const renderIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (open && project) {
      setStatus('idle')
      setProgress(0)
      setLogs([])
      setOutputPath(project.renderOutput || null)
      setFileName(`${project.name.replace(/\s/g, '_')}_${Date.now().toString().slice(-6)}`)
      setOutputFormat(settings.renderOutputFormat as OutputFormat || 'mp4')
      const dir = settings.autoCreateSubfolder
        ? `${settings.renderOutputDir}/${project.name.replace(/\s/g, '_')}`
        : settings.renderOutputDir
      setOutputDir(dir)
      setShowSettings(false)
      setDownloadUrl(null)
      setFileSize('')
      setVideoUrl(null)
      setIsPlaying(false)
    }
  }, [open, project?.id, settings.renderOutputDir, settings.renderOutputFormat, settings.autoCreateSubfolder])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const generateRenderData = () => {
    if (!project) return null
    const fullPath = `${outputDir}/${fileName}.${outputFormat}`
    const totalFrames = Math.ceil(project.duration * project.frameRate)
    const estimatedSize = Math.round(totalFrames * project.width * project.height * 0.1 / 1024 / 1024)
    return {
      projectName: project.name,
      projectId: project.id,
      renderTime: new Date().toISOString(),
      outputPath: fullPath,
      outputDir: outputDir,
      fileSize: `${estimatedSize} MB (预估)`,
      settings: {
        width: project.width,
        height: project.height,
        frameRate: project.frameRate,
        duration: project.duration,
        format: outputFormat,
        totalFrames: totalFrames,
      },
      scenes: project.scenes.map(s => ({
        name: s.name,
        duration: s.duration,
        layerCount: s.layerCount,
        effectCount: s.effects.length,
      })),
      effects: project.appliedEffects.map(e => ({
        name: e.name,
        category: e.category,
        params: e.params,
      })),
      outputFile: `${fileName}.${outputFormat}`,
    }
  }

  const triggerDownload = (data: object, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    setDownloadUrl(url)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const generatePreviewVideo = async (): Promise<string> => {
    if (!project) return ''

    const canvas = document.createElement('canvas')
    const width = Math.min(project.width, 640)
    const height = Math.min(project.height, 360)
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')!

    const stream = canvas.captureStream(30)
    const mimeTypes = [
      'video/webm;codecs=vp9',
      'video/webm;codecs=vp8',
      'video/webm',
    ]
    let mimeType = ''
    for (const type of mimeTypes) {
      if (MediaRecorder.isTypeSupported(type)) {
        mimeType = type
        break
      }
    }

    const recorder = new MediaRecorder(stream, { mimeType: mimeType || 'video/webm' })
    const chunks: BlobPart[] = []

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }

    return new Promise((resolve) => {
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: mimeType || 'video/webm' })
        const url = URL.createObjectURL(blob)
        resolve(url)
      }

      recorder.start()

      const duration = Math.min(project.duration, 5)
      const totalFrames = duration * 30
      let frame = 0

      const drawFrame = () => {
        if (frame >= totalFrames) {
          recorder.stop()
          return
        }

        const progress = frame / totalFrames
        const time = (frame / 30).toFixed(2)

        ctx.fillStyle = '#0f172a'
        ctx.fillRect(0, 0, width, height)

        const gradient = ctx.createLinearGradient(0, 0, width, height)
        gradient.addColorStop(0, '#1e40af')
        gradient.addColorStop(0.5, '#7c3aed')
        gradient.addColorStop(1, '#db2777')
        ctx.fillStyle = gradient
        ctx.globalAlpha = 0.3
        ctx.fillRect(0, 0, width, height)
        ctx.globalAlpha = 1

        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 24px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText(project.name, width / 2, height / 2 - 40)

        const barWidth = width * 0.6
        const barHeight = 8
        const barX = (width - barWidth) / 2
        const barY = height / 2

        ctx.fillStyle = 'rgba(255,255,255,0.2)'
        ctx.fillRect(barX, barY, barWidth, barHeight)

        ctx.fillStyle = '#22c55e'
        ctx.fillRect(barX, barY, barWidth * progress, barHeight)

        ctx.fillStyle = 'rgba(255,255,255,0.8)'
        ctx.font = '14px monospace'
        ctx.fillText(`${time}s / ${duration.toFixed(2)}s`, width / 2, height / 2 + 30)

        ctx.fillStyle = 'rgba(255,255,255,0.5)'
        ctx.font = '12px sans-serif'
        ctx.fillText(`${project.width}×${project.height} · ${project.frameRate}fps`, width / 2, height - 20)

        if (project.appliedEffects.length > 0) {
          ctx.fillStyle = '#fbbf24'
          ctx.font = 'bold 12px sans-serif'
          ctx.textAlign = 'left'
          ctx.fillText(`✨ ${project.appliedEffects.length} 个效果`, 20, 30)
          ctx.textAlign = 'center'
        }

        frame++
        requestAnimationFrame(drawFrame)
      }

      drawFrame()
    })
  }

  const startRender = () => {
    if (!project) return

    setStatus('rendering')
    setProgress(0)
    setLogs([])
    setOutputPath(null)
    setDownloadUrl(null)
    setFileSize('')

    const totalFrames = Math.ceil(project.duration * project.frameRate)
    const renderData = generateRenderData()
    const fullPath = `${outputDir}/${fileName}.${outputFormat}`
    const estimatedSize = Math.round(totalFrames * project.width * project.height * 0.1 / 1024 / 1024)

    const renderSteps = [
      { progress: 3, log: `[初始化] 准备渲染项目: ${project.name}` },
      { progress: 6, log: `[检查] 合成尺寸: ${project.width}×${project.height}, 帧率: ${project.frameRate}fps` },
      { progress: 9, log: `[检查] 总时长: ${project.duration}秒 (${totalFrames}帧)` },
      { progress: 12, log: `[检查] 输出目录: ${outputDir}` },
      { progress: 15, log: `[检查] 输出文件: ${fileName}.${outputFormat}` },
      { progress: 18, log: `[场景] 共 ${project.sceneCount} 个场景` },
      { progress: 25, log: `[渲染] 场景 1/${project.sceneCount}: ${project.scenes[0]?.name || '场景1'}...` },
      { progress: 40, log: `[渲染] 场景 2/${project.sceneCount}: ${project.scenes[1]?.name || '场景2'}...` },
      { progress: 55, log: `[渲染] 场景 3/${project.sceneCount}: ${project.scenes[2]?.name || '场景3'}...` },
      { progress: 70, log: `[效果] 处理已应用效果 (${project.appliedEffects.length}个)...` },
      { progress: 80, log: `[编码] ${outputFormat.toUpperCase()} 编码中...` },
      { progress: 88, log: `[音频] 混音处理...` },
      { progress: 94, log: `[合成] 最终合成...` },
      { progress: 97, log: `[写入] 正在写入文件到磁盘...` },
      { progress: 100, log: `[完成] 渲染成功! 输出: ${fullPath}` },
    ]

    let stepIndex = 0
    renderIntervalRef.current = setInterval(() => {
      if (stepIndex < renderSteps.length) {
        const step = renderSteps[stepIndex]
        setProgress(step.progress)
        setLogs(prev => [...prev, step.log])
        stepIndex++
      } else {
        if (renderIntervalRef.current) clearInterval(renderIntervalRef.current)

        setOutputPath(fullPath)
        setFileSize(`${estimatedSize} MB`)
        setStatus('success')

        generatePreviewVideo().then(url => {
          setVideoUrl(url)
        })

        if (renderData) {
          triggerDownload(renderData, `${fileName}_metadata.json`)
        }

        updateProject(project.id, {
          status: 'completed',
          renderOutput: fullPath,
        })
        addHistory({
          action: `渲染项目: ${project.name}`,
          result: 'success',
          details: `输出: ${fullPath} (${project.width}×${project.height}, ${project.frameRate}fps, ~${estimatedSize}MB)`,
          projectId: project.id,
          params: { format: outputFormat, fileName, duration: project.duration, outputDir, fileSize: estimatedSize },
        })
        showToast(`项目「${project.name}」渲染完成`, 'success')
      }
    }, 400)
  }

  const handleCopyPath = () => {
    if (outputPath) {
      navigator.clipboard.writeText(outputPath).then(() => {
        showToast('路径已复制到剪贴板', 'success')
      })
    }
  }

  const handleDownloadVideo = () => {
    if (videoUrl) {
      const a = document.createElement('a')
      a.href = videoUrl
      a.download = `${fileName}.webm`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      showToast('视频已开始下载', 'success')
    } else {
      showToast('视频生成中，请稍候...', 'info')
    }
  }

  const handleDownloadMetadata = () => {
    const data = generateRenderData()
    if (data) {
      triggerDownload(data, `${fileName}_metadata.json`)
      showToast('元数据已下载', 'success')
    }
  }

  const handleTogglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  const handleOpenFolder = () => {
    showToast(`请在文件资源管理器中打开: ${outputDir}`, 'info')
  }

  const handleClose = () => {
    if (status === 'rendering') {
      showToast('渲染进行中，请等待完成', 'warning')
      return
    }
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
    }
    if (videoUrl) {
      URL.revokeObjectURL(videoUrl)
    }
    onClose()
  }

  if (!project) return null

  const formats: OutputFormat[] = ['mp4', 'mov', 'avi', 'json']

  return (
    <Modal open={open} onClose={handleClose} title={`渲染 - ${project.name}`} maxWidth="640px">
      <div className="space-y-6">
        {/* 项目信息 */}
        <div className="flex items-center gap-3 p-4 rounded-lg bg-secondary/50">
          <Folder className="w-8 h-8 text-primary" />
          <div>
            <p className="font-semibold">{project.name}</p>
            <p className="text-sm text-muted-foreground">
              {project.width}×{project.height} · {project.frameRate}fps · {project.duration}秒 · {project.sceneCount}场景
            </p>
          </div>
        </div>

        {/* 渲染设置（可展开） */}
        {status === 'idle' && (
          <div className="space-y-3">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <Settings className="w-4 h-4" />
              渲染设置
              <span className="text-xs">({showSettings ? '收起' : '展开'})</span>
            </button>

            {showSettings && (
              <div className="p-4 rounded-lg border space-y-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">输出目录</label>
                  <div className="flex items-center gap-2 p-2 rounded-md bg-secondary/50 text-sm">
                    <Folder className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    <span className="font-mono truncate">{outputDir}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    在设置中可修改默认输出目录
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium mb-2 block">输出文件名</label>
                  <Input
                    value={fileName}
                    onChange={(e) => setFileName(e.target.value)}
                    placeholder="输入文件名"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-2 block">输出格式</label>
                  <div className="flex gap-2">
                    {formats.map(fmt => (
                      <button
                        key={fmt}
                        onClick={() => setOutputFormat(fmt)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                          outputFormat === fmt
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-secondary hover:bg-secondary/80'
                        }`}
                      >
                        {fmt.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    * 浏览器环境下将下载元数据 JSON 文件，视频需在 AE 中真实渲染
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 状态：待开始 */}
        {status === 'idle' && (
          <div className="text-center py-6">
            <Play className="w-12 h-12 mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground mb-6">点击下方按钮开始渲染</p>
            <Button size="lg" className="gap-2" onClick={startRender}>
              <Play className="w-5 h-5" />
              开始渲染
            </Button>
          </div>
        )}

        {/* 状态：渲染中 */}
        {status === 'rendering' && (
          <div>
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                  <span className="font-medium">渲染中...</span>
                </div>
                <span className="text-2xl font-bold text-blue-500">{progress}%</span>
              </div>
              <div className="w-full h-3 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all duration-300 rounded-full"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            <div className="bg-gray-900 text-gray-100 rounded-lg p-4 font-mono text-sm h-48 overflow-y-auto">
              {logs.map((log, index) => (
                <div key={index} className="flex items-start gap-2 mb-1">
                  <span className="text-gray-500">{String(index + 1).padStart(2, '0')}</span>
                  <span className={log.includes('[完成]') ? 'text-green-400' : log.includes('[错误]') ? 'text-red-400' : 'text-gray-300'}>
                    {log}
                  </span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        )}

        {/* 状态：成功 */}
        {status === 'success' && (
          <div className="text-center py-2">
            <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-500" />
            <h3 className="text-xl font-semibold mb-2">渲染完成</h3>
            <p className="text-muted-foreground mb-4">项目已成功渲染输出</p>

            {/* 视频预览 */}
            {videoUrl ? (
              <div className="mb-6">
                <div className="relative rounded-lg overflow-hidden bg-black group">
                  <video
                    ref={videoRef}
                    src={videoUrl}
                    className="w-full max-h-64 object-contain"
                    loop
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    onClick={handleTogglePlay}
                  />
                  <div className={`absolute inset-0 flex items-center justify-center bg-black/30 transition-opacity ${isPlaying ? 'opacity-0 group-hover:opacity-100' : 'opacity-100'}`}>
                    <button
                      onClick={handleTogglePlay}
                      className="w-16 h-16 rounded-full bg-white/20 backdrop-blur flex items-center justify-center hover:bg-white/30 transition-colors"
                    >
                      {isPlaying ? (
                        <Pause className="w-8 h-8 text-white" />
                      ) : (
                        <Play className="w-8 h-8 text-white ml-1" />
                      )}
                    </button>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-2">点击视频播放/暂停 · 预览视频为示例效果</p>
              </div>
            ) : (
              <div className="mb-6 p-8 rounded-lg bg-secondary/50">
                <Loader2 className="w-8 h-8 mx-auto mb-2 text-primary animate-spin" />
                <p className="text-sm text-muted-foreground">正在生成预览视频...</p>
              </div>
            )}

            {outputPath && (
              <div className="p-4 rounded-lg bg-green-50 border border-green-200 mb-6 text-left">
                <div className="flex items-center gap-3 mb-3">
                  <FileVideo className="w-8 h-8 text-green-600 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-green-700">输出文件</p>
                    <p className="text-sm font-mono text-green-600 break-all">{fileName}.{outputFormat}</p>
                  </div>
                  <button
                    onClick={handleCopyPath}
                    className="p-2 rounded-lg hover:bg-green-100 transition-colors flex-shrink-0"
                    title="复制完整路径"
                  >
                    <Copy className="w-4 h-4 text-green-600" />
                  </button>
                </div>

                <div className="space-y-2 pt-3 border-t border-green-200">
                  <div className="flex items-center gap-2 text-sm">
                    <Folder className="w-4 h-4 text-green-600 flex-shrink-0" />
                    <span className="text-green-700">保存位置:</span>
                    <span className="font-mono text-green-600 break-all flex-1">{outputDir}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-green-600 pt-2 border-t border-green-200">
                    <span>{project.width}×{project.height}</span>
                    <span>{project.frameRate} fps</span>
                    <span>{project.duration}秒</span>
                    <span>{outputFormat.toUpperCase()}</span>
                    <span>{fileSize}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-3 justify-center">
              <Button className="gap-2" onClick={handleDownloadVideo} disabled={!videoUrl}>
                <Download className="w-4 h-4" />
                下载视频
              </Button>
              <Button variant="outline" className="gap-2" onClick={handleOpenFolder}>
                <Folder className="w-4 h-4" />
                打开文件夹
              </Button>
              <Button variant="outline" className="gap-2" onClick={handleDownloadMetadata}>
                <FileJson className="w-4 h-4" />
                下载元数据
              </Button>
              <Button variant="outline" className="gap-2" onClick={() => {
                setStatus('idle')
                setProgress(0)
                setLogs([])
                setVideoUrl(null)
              }}>
                <RefreshCw className="w-4 h-4" />
                重新渲染
              </Button>
              <Button variant="outline" onClick={handleClose}>
                完成
              </Button>
            </div>
          </div>
        )}

        {/* 状态：失败 */}
        {status === 'failed' && (
          <div className="text-center py-4">
            <XCircle className="w-16 h-16 mx-auto mb-4 text-red-500" />
            <h3 className="text-xl font-semibold mb-2">渲染失败</h3>
            <div className="flex gap-3 justify-center mt-6">
              <Button className="gap-2" onClick={startRender}>
                <RefreshCw className="w-4 h-4" />
                重新渲染
              </Button>
              <Button variant="outline" onClick={handleClose}>关闭</Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

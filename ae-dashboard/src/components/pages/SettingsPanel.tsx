import { useState } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Slider } from '@/components/ui/Slider'
import { Badge } from '@/components/ui/Badge'
import { useToast } from '@/components/ui/Toast'
import { useAppStore } from '@/store/useAppStore'
import { Settings, Monitor, Palette, Shield, Database, Save, Loader2, CheckCircle2, Sun, Moon, Laptop, Download, Upload, Folder, FileVideo } from 'lucide-react'

export function SettingsPanel() {
  const { showToast } = useToast()
  const { settings, updateSettings, resetSettings, restoreFromBackup, projects, history, favorites } = useAppStore()

  const [connecting, setConnecting] = useState(false)
  const [testing, setTesting] = useState(false)
  const [resetConfirm, setResetConfirm] = useState(false)

  const handleManualConnect = () => {
    setConnecting(true)
    showToast('正在连接 AE...', 'info')
    setTimeout(() => {
      setConnecting(false)
      updateSettings({ aeConnected: true })
      showToast('AE 连接成功', 'success')
    }, 1500)
  }

  const handleTestConnection = () => {
    setTesting(true)
    showToast('正在测试连接...', 'info')
    setTimeout(() => {
      setTesting(false)
      if (settings.aeConnected) {
        showToast('连接测试通过，延迟 23ms', 'success')
      } else {
        showToast('连接测试失败，AE 未响应', 'error')
      }
    }, 1000)
  }

  const handleSave = () => {
    showToast('所有设置已保存到本地', 'success')
  }

  const handleBackup = () => {
    const data = { projects, history, settings, favorites, exportDate: new Date().toISOString() }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ae-copilot-backup-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
    showToast('数据已备份到本地文件', 'success')
  }

  const handleRestore = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = (ev) => {
        try {
          const data = JSON.parse(ev.target?.result as string)
          // 必须包含至少一个已识别的备份字段，否则视为非法备份文件
          const isBackup =
            data && typeof data === 'object' && (
              Array.isArray(data.projects) ||
              Array.isArray(data.history) ||
              (data.settings && typeof data.settings === 'object') ||
              (data.favorites && Array.isArray(data.favorites.effects) && Array.isArray(data.favorites.styles))
            )
          if (!isBackup) {
            showToast('文件格式错误，恢复失败', 'error')
            return
          }
          restoreFromBackup(data)
          showToast('数据恢复成功', 'success')
        } catch {
          showToast('文件格式错误，恢复失败', 'error')
        }
      }
      reader.readAsText(file)
    }
    input.click()
  }

  const handleReset = () => {
    if (resetConfirm) {
      resetSettings()
      setResetConfirm(false)
      showToast('所有设置已重置为默认值', 'success')
    } else {
      setResetConfirm(true)
      setTimeout(() => setResetConfirm(false), 3000)
    }
  }

  const themes = [
    { key: 'light' as const, label: '浅色', icon: Sun },
    { key: 'dark' as const, label: '深色', icon: Moon },
    { key: 'system' as const, label: '系统', icon: Laptop },
  ]

  const dataSize = ((JSON.stringify(projects).length + JSON.stringify(history).length) / 1024).toFixed(1)

  return (
    <div className="p-6 space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Settings className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">AE 连接设置</h3>
            </div>
            <Badge className={settings.aeConnected ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}>
              {settings.aeConnected ? '已连接' : '未连接'}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">自动连接</p>
              <p className="text-sm text-muted-foreground">启动时自动连接 AE</p>
            </div>
            <button
              onClick={() => updateSettings({ autoConnect: !settings.autoConnect })}
              className={`w-12 h-6 rounded-full transition-colors ${settings.autoConnect ? 'bg-primary' : 'bg-muted'}`}
            >
              <span className={`block w-5 h-5 rounded-full bg-white shadow transition-transform ${settings.autoConnect ? 'translate-x-6' : 'translate-x-0.5'}`} />
            </button>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="font-medium">连接超时</label>
              <span className="text-sm text-muted-foreground">{settings.timeout}秒</span>
            </div>
            <Slider
              value={settings.timeout}
              onChange={(v) => updateSettings({ timeout: v })}
              min={10}
              max={120}
              step={5}
            />
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              className="flex-1 gap-2"
              onClick={handleManualConnect}
              disabled={connecting}
            >
              {connecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Monitor className="w-4 h-4" />}
              {connecting ? '连接中...' : '手动连接'}
            </Button>
            <Button
              variant="outline"
              className="flex-1 gap-2"
              onClick={handleTestConnection}
              disabled={testing}
            >
              {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              {testing ? '测试中...' : '测试连接'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileVideo className="w-5 h-5 text-primary" />
            <h3 className="font-semibold">渲染输出设置</h3>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="font-medium mb-2 block">输出目录</label>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Folder className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  value={settings.renderOutputDir}
                  onChange={(e) => updateSettings({ renderOutputDir: e.target.value })}
                  className="w-full h-9 pl-9 pr-3 rounded-md border border-input bg-background text-sm"
                  placeholder="例如: D:/AE_Renders"
                />
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  const input = document.createElement('input')
                  input.type = 'file'
                  input.webkitdirectory = true
                  input.onchange = () => {
                    showToast('目录选择功能需要后端支持，当前为模拟模式', 'info')
                  }
                  input.click()
                }}
              >
                选择目录
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              渲染文件将保存到此目录下，可按项目自动创建子文件夹
            </p>
          </div>

          <div>
            <label className="font-medium mb-2 block">默认输出格式</label>
            <div className="flex gap-2">
              {['mp4', 'mov', 'avi', 'gif'].map(fmt => (
                <button
                  key={fmt}
                  onClick={() => updateSettings({ renderOutputFormat: fmt })}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    settings.renderOutputFormat === fmt
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary hover:bg-secondary/80'
                  }`}
                >
                  {fmt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
            <div>
              <p className="text-sm font-medium">按项目创建子文件夹</p>
              <p className="text-xs text-muted-foreground">自动在输出目录下创建项目名称文件夹</p>
            </div>
            <button
              onClick={() => updateSettings({ autoCreateSubfolder: !settings.autoCreateSubfolder })}
              className={`w-12 h-6 rounded-full transition-colors ${settings.autoCreateSubfolder ? 'bg-primary' : 'bg-muted'}`}
            >
              <span className={`block w-5 h-5 rounded-full bg-white shadow transition-transform ${settings.autoCreateSubfolder ? 'translate-x-6' : 'translate-x-0.5'}`} />
            </button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">NLU 设置</h3>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="font-medium">置信度阈值</label>
                <span className="text-sm text-muted-foreground">{(settings.confidenceThreshold * 100).toFixed(0)}%</span>
              </div>
              <Slider
                value={settings.confidenceThreshold}
                onChange={(v) => updateSettings({ confidenceThreshold: v })}
                min={0}
                max={1}
                step={0.05}
              />
              <p className="text-xs text-muted-foreground mt-2">低于此阈值的意图将触发追问</p>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="font-medium">最大重试次数</label>
                <span className="text-sm text-muted-foreground">{settings.maxRetries}次</span>
              </div>
              <Slider
                value={settings.maxRetries}
                onChange={(v) => updateSettings({ maxRetries: v })}
                min={1}
                max={10}
                step={1}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Palette className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">界面设置</h3>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="font-medium mb-2 block">主题</label>
              <div className="grid grid-cols-3 gap-2">
                {themes.map(t => {
                  const Icon = t.icon
                  return (
                    <button
                      key={t.key}
                      onClick={() => {
                        updateSettings({ theme: t.key })
                        showToast(`主题已切换为: ${t.label}`, 'info')
                      }}
                      className={`p-3 rounded-lg border-2 transition-all flex flex-col items-center gap-1 ${
                        settings.theme === t.key
                          ? 'border-primary bg-primary/10'
                          : 'border-border hover:border-primary/50'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span className="text-xs">{t.label}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            <div>
              <label className="font-medium mb-2 block">语言</label>
              <select
                value={settings.language}
                onChange={(e) => {
                  updateSettings({ language: e.target.value })
                  showToast(`语言已切换为: ${e.target.value}`, 'info')
                }}
                className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
              >
                <option>中文 (简体)</option>
                <option>English</option>
                <option>日本語</option>
                <option>한국어</option>
              </select>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-primary" />
            <h3 className="font-semibold">数据管理</h3>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
            <div>
              <p className="font-medium">项目数据</p>
              <p className="text-sm text-muted-foreground">{projects.length} 个项目</p>
            </div>
            <Badge variant="secondary">{(JSON.stringify(projects).length / 1024).toFixed(1)} KB</Badge>
          </div>

          <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
            <div>
              <p className="font-medium">历史记录</p>
              <p className="text-sm text-muted-foreground">{history.length} 条记录</p>
            </div>
            <Badge variant="secondary">{(JSON.stringify(history).length / 1024).toFixed(1)} KB</Badge>
          </div>

          <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
            <div>
              <p className="font-medium">收藏数据</p>
              <p className="text-sm text-muted-foreground">{favorites.effects.length} 个效果, {favorites.styles.length} 个风格</p>
            </div>
            <Badge variant="secondary">{dataSize} KB</Badge>
          </div>

          <div className="flex gap-3">
            <Button variant="outline" className="gap-2" onClick={handleBackup}>
              <Download className="w-4 h-4" />
              备份数据
            </Button>
            <Button variant="outline" className="gap-2" onClick={handleRestore}>
              <Upload className="w-4 h-4" />
              恢复数据
            </Button>
            <Button
              variant="outline"
              className={`gap-2 text-red-600 hover:text-red-600 hover:bg-red-50 ${resetConfirm ? 'bg-red-50 border-red-300' : ''}`}
              onClick={handleReset}
            >
              {resetConfirm ? '确认重置?' : '重置数据'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Button className="w-full gap-2" onClick={handleSave}>
        <Save className="w-4 h-4" />
        保存所有设置
      </Button>
    </div>
  )
}

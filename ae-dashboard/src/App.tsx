import { useState, useEffect, useCallback } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { Dashboard } from '@/components/pages/Dashboard'
import { EffectsPanel } from '@/components/pages/EffectsPanel'
import { StylesPanel } from '@/components/pages/StylesPanel'
import { ProjectsPanel } from '@/components/pages/ProjectsPanel'
import { HistoryPanel } from '@/components/pages/HistoryPanel'
import { ExecutePanel } from '@/components/pages/ExecutePanel'
import { SettingsPanel } from '@/components/pages/SettingsPanel'
import { LoginPage } from '@/components/pages/LoginPage'
import { MonitorPanel } from '@/components/pages/MonitorPanel'
import { UsersPanel } from '@/components/pages/UsersPanel'
import { ToolchainPanel } from '@/components/pages/ToolchainPanel'
import { WorkflowsPanel } from '@/components/pages/WorkflowsPanel'
import { StyleCopyPanel } from '@/components/pages/StyleCopyPanel'
import { useAppStore } from '@/store/useAppStore'
import { useAuthStore } from '@/store/useAuthStore'
import { useToast } from '@/components/ui/Toast'
import { Loader2, RefreshCw } from 'lucide-react'

type PageKey = 'dashboard' | 'effects' | 'styles' | 'projects' | 'history' | 'execute' | 'settings' | 'monitor' | 'users' | 'toolchain' | 'workflows' | 'style-copy'

const titles: Record<PageKey, string> = {
  dashboard: '控制台',
  effects: '效果库',
  styles: '风格模板',
  projects: '项目管理',
  history: '操作历史',
  execute: '执行中心',
  settings: '设置',
  monitor: '监控中心',
  users: '用户管理',
  toolchain: '工具链',
  workflows: '工作流',
  'style-copy': '风格复制',
}

function App() {
  const [activeTab, setActiveTab] = useState<PageKey>('dashboard')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const syncFromBackend = useAppStore(s => s.syncFromBackend)
  const { isAuthenticated, fetchUser } = useAuthStore()
  const { showToast } = useToast()

  const handleRefresh = useCallback(async (showIndicator = true) => {
    if (isRefreshing) return
    if (showIndicator) setIsRefreshing(true)
    try {
      await syncFromBackend()
      if (showIndicator) {
        showToast('数据已刷新', 'success')
      }
    } catch {
      if (showIndicator) {
        showToast('刷新失败，请稍后重试', 'error')
      }
    } finally {
      if (showIndicator) setIsRefreshing(false)
    }
  }, [isRefreshing, syncFromBackend, showToast])

  useEffect(() => {
    const token = localStorage.getItem('ae_token')
    if (token) {
      fetchUser()
    }
  }, [fetchUser])

  useEffect(() => {
    syncFromBackend()
  }, [syncFromBackend])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'F5' || (e.ctrlKey && e.key === 'r') || (e.metaKey && e.key === 'r')) {
        e.preventDefault()
        handleRefresh()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleRefresh])

  const renderPage = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard onNavigate={(page) => setActiveTab(page as PageKey)} />
      case 'effects':
        return <EffectsPanel />
      case 'styles':
        return <StylesPanel />
      case 'projects':
        return <ProjectsPanel />
      case 'history':
        return <HistoryPanel />
      case 'execute':
        return <ExecutePanel />
      case 'settings':
        return <SettingsPanel />
      case 'monitor':
        return <MonitorPanel />
      case 'users':
        return <UsersPanel />
      case 'toolchain':
        return <ToolchainPanel onRefresh={() => handleRefresh(false)} />
      case 'workflows':
        return <WorkflowsPanel />
      case 'style-copy':
        return <StyleCopyPanel />
    }
  }

  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={() => setActiveTab('dashboard')} />
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar activeTab={activeTab} onTabChange={(tab) => setActiveTab(tab as PageKey)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title={titles[activeTab]}
          onNavigate={(p) => setActiveTab(p as PageKey)}
          rightAction={
            <button
              onClick={() => handleRefresh()}
              className={`p-2 rounded-lg hover:bg-secondary transition-colors ${isRefreshing ? 'text-primary' : ''}`}
              title="刷新数据 (F5)"
            >
              {isRefreshing ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <RefreshCw className="w-5 h-5" />
              )}
            </button>
          }
        />
        <main className="flex-1 overflow-y-auto">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}

export default App

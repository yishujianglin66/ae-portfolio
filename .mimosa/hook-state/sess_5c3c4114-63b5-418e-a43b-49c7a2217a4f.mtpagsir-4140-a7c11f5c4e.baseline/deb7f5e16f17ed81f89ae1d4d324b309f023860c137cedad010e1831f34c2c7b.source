import { Layers, Sparkles, Palette, Clock, Folder, Settings, Play, Wand2, Activity, Users, Wrench, GitBranch, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/store/useAuthStore'

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

const menuItems = [
  { id: 'dashboard', icon: Layers, label: '控制台' },
  { id: 'effects', icon: Sparkles, label: '效果库' },
  { id: 'styles', icon: Palette, label: '风格模板' },
  { id: 'projects', icon: Folder, label: '项目管理' },
  { id: 'style-copy', icon: Zap, label: '风格复制' },
  { id: 'toolchain', icon: Wrench, label: '工具链' },
  { id: 'workflows', icon: GitBranch, label: '工作流' },
  { id: 'history', icon: Clock, label: '操作历史' },
  { id: 'execute', icon: Play, label: '执行中心' },
]

const systemItems = [
  { id: 'monitor', icon: Activity, label: '监控中心' },
  { id: 'users', icon: Users, label: '用户管理', roles: ['admin'] },
  { id: 'settings', icon: Settings, label: '设置' },
]

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  const { user, isAuthenticated } = useAuthStore()

  const filteredSystemItems = systemItems.filter(item => {
    if (!item.roles) return true
    if (!user) return false
    return item.roles.includes(user.role)
  })

  return (
    <aside className="w-64 bg-secondary/50 border-r h-screen flex flex-col">
      <div className="p-4 border-b">
        <div className="flex items-center gap-2">
          <Wand2 className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-lg font-bold">AE Copilot</h1>
            <p className="text-xs text-muted-foreground">v2.0</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <p className="text-xs font-medium text-muted-foreground px-3 py-2">工作区</p>
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={cn(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              activeTab === item.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
            )}
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </button>
        ))}

        {isAuthenticated && (
          <>
            <p className="text-xs font-medium text-muted-foreground px-3 py-2 mt-4">系统</p>
            {filteredSystemItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  activeTab === item.id
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                )}
              >
                <item.icon className="w-5 h-5" />
                {item.label}
              </button>
            ))}
          </>
        )}
      </nav>

      <div className="p-4 border-t space-y-3">
        {isAuthenticated && user ? (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-sm font-medium text-primary">
              {user.username[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user.username}</p>
              <p className="text-xs text-muted-foreground truncate">
                {user.role === 'admin' ? '管理员' : user.role === 'operator' ? '操作员' : '查看者'}
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-primary/10 rounded-lg p-3">
            <p className="text-xs text-muted-foreground">连接状态</p>
            <div className="flex items-center gap-2 mt-1">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-sm font-medium">AE 已连接</span>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}

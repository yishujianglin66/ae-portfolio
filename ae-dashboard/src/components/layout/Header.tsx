import { useState, ReactNode } from 'react'
import { Search, Bell, User, LogOut, Settings, ChevronDown } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { useAuthStore } from '@/store/useAuthStore'

interface HeaderProps {
  title: string
  onNavigate?: (page: string) => void
  rightAction?: ReactNode
}

export function Header({ title, onNavigate, rightAction }: HeaderProps) {
  const { user, isAuthenticated, logout } = useAuthStore()
  const [showMenu, setShowMenu] = useState(false)

  const handleLogout = async () => {
    await logout()
    setShowMenu(false)
    window.location.reload()
  }

  return (
    <header className="h-16 border-b flex items-center justify-between px-6">
      <h2 className="text-xl font-semibold">{title}</h2>

      <div className="flex items-center gap-4">
        {rightAction && <div className="flex items-center gap-2">{rightAction}</div>}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="搜索效果、风格..."
            className="pl-9 w-64"
          />
        </div>

        <button className="relative p-2 rounded-lg hover:bg-secondary transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-destructive rounded-full" />
        </button>

        {isAuthenticated && user ? (
          <div className="relative pl-4 border-l">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="flex items-center gap-2 p-1 rounded-lg hover:bg-secondary transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-sm font-medium text-primary">
                {user.username[0].toUpperCase()}
              </div>
              <div className="text-left">
                <p className="text-sm font-medium leading-tight">{user.username}</p>
                <p className="text-xs text-muted-foreground">
                  {user.role === 'admin' ? '管理员' : user.role === 'operator' ? '操作员' : '查看者'}
                </p>
              </div>
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            </button>

            {showMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
                <div className="absolute right-0 top-full mt-2 w-56 bg-card border rounded-xl shadow-xl overflow-hidden z-50">
                  <div className="p-3 border-b bg-secondary/30">
                    <p className="text-sm font-medium">{user.username}</p>
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                  </div>
                  <div className="p-1">
                    <button
                      onClick={() => { onNavigate?.('settings'); setShowMenu(false) }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg hover:bg-secondary transition-colors text-left"
                    >
                      <Settings className="w-4 h-4 text-muted-foreground" />
                      设置
                    </button>
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg hover:bg-secondary transition-colors text-left text-destructive"
                    >
                      <LogOut className="w-4 h-4" />
                      退出登录
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 pl-4 border-l">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
              <User className="w-4 h-4 text-primary" />
            </div>
            <span className="text-sm font-medium">访客</span>
          </div>
        )}
      </div>
    </header>
  )
}

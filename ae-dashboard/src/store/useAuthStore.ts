import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '@/lib/api'

export interface AuthUser {
  user_id: string
  username: string
  email: string
  role: 'admin' | 'operator' | 'viewer'
  permissions: string[]
  is_active: boolean
  created_at: string
}

interface AuthStore {
  user: AuthUser | null
  isAuthenticated: boolean
  loading: boolean
  error: string | null

  login: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  fetchUser: () => Promise<void>
  changePassword: (oldPassword: string, newPassword: string) => Promise<boolean>
  clearError: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      loading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ loading: true, error: null })
        try {
          const res: any = await api.login(username, password)
          if (res.user) {
            set({ user: res.user, isAuthenticated: true, loading: false })
            return true
          }
          set({ loading: false, error: '登录失败' })
          return false
        } catch (e: any) {
          set({ loading: false, error: e.message || '登录失败' })
          return false
        }
      },

      logout: async () => {
        set({ loading: true })
        try {
          await api.logout()
        } catch {
        } finally {
          set({ user: null, isAuthenticated: false, loading: false })
        }
      },

      fetchUser: async () => {
        try {
          const user: any = await api.getMe()
          set({ user, isAuthenticated: true })
        } catch {
          set({ user: null, isAuthenticated: false })
        }
      },

      changePassword: async (oldPassword: string, newPassword: string) => {
        set({ loading: true, error: null })
        try {
          await api.changePassword(oldPassword, newPassword)
          set({ loading: false })
          return true
        } catch (e: any) {
          set({ loading: false, error: e.message || '修改密码失败' })
          return false
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'ae-auth-storage',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)

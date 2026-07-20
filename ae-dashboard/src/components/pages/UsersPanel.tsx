import { useState, useEffect } from 'react'
import { Plus, Trash2, Edit, Shield, Mail, User } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/useAuthStore'

interface UserItem {
  user_id: string
  username: string
  email: string
  role: 'admin' | 'operator' | 'viewer'
  is_active: boolean
  created_at: string
  last_login_at?: string
}

const roleLabels: Record<string, string> = {
  admin: '管理员',
  operator: '操作员',
  viewer: '查看者',
}

const roleColors: Record<string, string> = {
  admin: 'bg-red-500',
  operator: 'bg-blue-500',
  viewer: 'bg-green-500',
}

export function UsersPanel() {
  const { user: currentUser } = useAuthStore()
  const [users, setUsers] = useState<UserItem[]>([])
  const [loading, setLoading] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingUser, setEditingUser] = useState<UserItem | null>(null)
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    role: 'viewer' as 'admin' | 'operator' | 'viewer',
  })

  const loadUsers = async () => {
    setLoading(true)
    try {
      const res: any = await api.getUsers({ page_size: 50 })
      setUsers(res.users || [])
    } catch {
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  const handleAdd = () => {
    setEditingUser(null)
    setFormData({ username: '', email: '', password: '', role: 'viewer' })
    setShowAddModal(true)
  }

  const handleEdit = (u: UserItem) => {
    setEditingUser(u)
    setFormData({ username: u.username, email: u.email, password: '', role: u.role })
    setShowAddModal(true)
  }

  const handleDelete = async (u: UserItem) => {
    if (!confirm(`确定删除用户 "${u.username}" 吗？`)) return
    try {
      await api.deleteUser(u.user_id)
      await loadUsers()
    } catch (e: any) {
      alert(e.message || '删除失败')
    }
  }

  const handleSubmit = async () => {
    try {
      if (editingUser) {
        const data: Record<string, unknown> = { email: formData.email, role: formData.role }
        if (formData.password) data.password = formData.password
        await api.updateUser(editingUser.user_id, data)
      } else {
        await api.createUser({
          username: formData.username,
          email: formData.email,
          password: formData.password,
          role: formData.role,
        })
      }
      setShowAddModal(false)
      await loadUsers()
    } catch (e: any) {
      alert(e.message || '操作失败')
    }
  }

  const isAdmin = currentUser?.role === 'admin'

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">用户管理</h3>
          <p className="text-sm text-muted-foreground">
            {isAdmin ? '管理系统用户和权限角色' : '查看系统用户列表'}
          </p>
        </div>
        {isAdmin && (
          <Button onClick={handleAdd}>
            <Plus className="w-4 h-4 mr-2" />
            新增用户
          </Button>
        )}
      </div>

      <Card className="p-0 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-secondary/30">
              <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">用户名</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">邮箱</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">角色</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">状态</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">创建时间</th>
              {isAdmin && <th className="text-right px-4 py-3 text-sm font-medium text-muted-foreground">操作</th>}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id} className="border-b hover:bg-secondary/20 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                      <User className="w-4 h-4 text-primary" />
                    </div>
                    <span className="font-medium">{u.username}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <Mail className="w-3 h-3" />
                    {u.email}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Shield className={`w-4 h-4 ${u.role === 'admin' ? 'text-red-500' : u.role === 'operator' ? 'text-blue-500' : 'text-green-500'}`} />
                    <Badge variant="outline">{roleLabels[u.role]}</Badge>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1.5 text-sm ${u.is_active ? 'text-green-500' : 'text-muted-foreground'}`}>
                    <span className={`w-2 h-2 rounded-full ${u.is_active ? 'bg-green-500' : 'bg-muted-foreground'}`} />
                    {u.is_active ? '活跃' : '禁用'}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  {new Date(u.created_at).toLocaleDateString('zh-CN')}
                </td>
                {isAdmin && (
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => handleEdit(u)} disabled={u.username === 'admin'}>
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(u)} disabled={u.username === 'admin'}>
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="text-center py-8 text-sm text-muted-foreground">加载中...</div>}
      </Card>

      <Modal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        title={editingUser ? '编辑用户' : '新增用户'}
      >
        <div className="space-y-4 py-2">
          {!editingUser && (
            <div className="space-y-2">
              <label className="text-sm font-medium">用户名</label>
              <Input
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                placeholder="输入用户名"
              />
            </div>
          )}
          <div className="space-y-2">
            <label className="text-sm font-medium">邮箱</label>
            <Input
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="user@example.com"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">
              密码 {editingUser && <span className="text-muted-foreground font-normal">(留空则不修改)</span>}
            </label>
            <Input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              placeholder="••••••••"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">角色</label>
            <div className="grid grid-cols-3 gap-2">
              {(['admin', 'operator', 'viewer'] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setFormData({ ...formData, role: r })}
                  className={`p-3 rounded-lg border text-sm transition-colors ${
                    formData.role === r
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'hover:bg-secondary'
                  }`}
                >
                  <div className="flex items-center justify-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${roleColors[r]}`} />
                    {roleLabels[r]}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="outline" onClick={() => setShowAddModal(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={!formData.email || (!editingUser && !formData.username)}>
            {editingUser ? '保存' : '创建'}
          </Button>
        </div>
      </Modal>
    </div>
  )
}

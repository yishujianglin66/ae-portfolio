import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '@/lib/api'

// ===== 类型定义 =====
export interface EffectParam {
  name: string
  value: number
  min: number
  max: number
  unit: string
}

export interface AppliedEffect {
  id: string
  name: string
  category: string
  params: EffectParam[]
  blendMode?: string
  opacity?: number
  appliedAt: string
}

export interface Scene {
  id: string
  name: string
  duration: number
  layerCount: number
  effects: AppliedEffect[]
}

export interface Project {
  id: string
  name: string
  description?: string
  status: 'draft' | 'processing' | 'completed' | 'failed'
  createdAt: string
  updatedAt: string
  duration: number
  sceneCount: number
  width: number
  height: number
  frameRate: number
  scenes: Scene[]
  appliedEffects: AppliedEffect[]
  renderOutput?: string
}

export interface HistoryItem {
  id: string
  action: string
  timestamp: string
  result: 'success' | 'failure' | 'pending'
  details: string
  projectId?: string
  params?: Record<string, unknown>
}

export interface AppSettings {
  autoConnect: boolean
  timeout: number
  confidenceThreshold: number
  maxRetries: number
  theme: 'light' | 'dark' | 'system'
  language: string
  aeConnected: boolean
  renderOutputDir: string
  renderOutputFormat: string
  autoCreateSubfolder: boolean
}

export interface ExecutionLog {
  id: string
  command: string
  intent: string | null
  result: 'success' | 'failure' | 'pending'
  timestamp: string
  logs: string[]
  parsedParams?: Record<string, unknown>
}

// ===== Store 定义 =====
interface AppStore {
  // 数据
  projects: Project[]
  history: HistoryItem[]
  executionLogs: ExecutionLog[]
  settings: AppSettings
  favorites: { effects: string[]; styles: string[] }

  // Project 操作
  addProject: (project: Omit<Project, 'id' | 'createdAt' | 'updatedAt'>) => string
  updateProject: (id: string, updates: Partial<Project>) => void
  deleteProject: (id: string) => void
  getProject: (id: string) => Project | undefined
  setProjects: (projects: Project[]) => void

  // History 操作
  addHistory: (item: Omit<HistoryItem, 'id' | 'timestamp'>) => void
  updateHistory: (id: string, updates: Partial<HistoryItem>) => void
  clearHistory: () => void
  setHistory: (history: HistoryItem[]) => void

  // Execution 操作
  addExecutionLog: (log: Omit<ExecutionLog, 'id' | 'timestamp'>) => string
  updateExecutionLog: (id: string, updates: Partial<ExecutionLog>) => void

  // Settings 操作
  updateSettings: (updates: Partial<AppSettings>) => void
  resetSettings: () => void

  // 备份/恢复
  restoreFromBackup: (data: {
    projects?: Project[]
    history?: HistoryItem[]
    settings?: Partial<AppSettings>
    favorites?: { effects: string[]; styles: string[] }
  }) => void

  // Favorites 操作
  toggleEffectFavorite: (name: string) => void
  toggleStyleFavorite: (id: string) => void

  // 应用效果到项目
  applyEffectToProject: (projectId: string | null, effect: AppliedEffect) => void

  // 后端同步
  backendConnected: boolean
  syncFromBackend: () => Promise<void>
  syncProjects: () => Promise<void>
  syncHistory: () => Promise<void>
  submitPuppetTask: (params: {
    input_video: string
    output_dir: string
    style: string
    auto_detect: boolean
    quality: string
    mode: string
  }) => Promise<string | null>
}

const defaultSettings: AppSettings = {
  autoConnect: true,
  timeout: 30,
  confidenceThreshold: 0.7,
  maxRetries: 3,
  theme: 'light',
  language: '中文 (简体)',
  aeConnected: false,
  renderOutputDir: 'D:/AE_Renders',
  renderOutputFormat: 'mp4',
  autoCreateSubfolder: true,
}

const today = () => new Date().toISOString().split('T')[0]
const timeStr = () => {
  const d = new Date()
  return `${today()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
const genId = () => Date.now().toString() + Math.random().toString(36).slice(2, 6)

// 时间戳规范化：后端 createdAt / updatedAt / timestamp 可能是 Unix 秒（number），
// 也可能是已格式化的字符串。统一转为 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:mm' 字符串。
const normalizeDate = (raw: unknown): string => {
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    const d = new Date(raw * 1000)
    return d.toISOString().split('T')[0]
  }
  if (typeof raw === 'string' && raw.length > 0) return raw.split('T')[0]
  return today()
}

const normalizeTimestamp = (raw: unknown): string => {
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    const d = new Date(raw * 1000)
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mi = String(d.getMinutes()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
  }
  if (typeof raw === 'string' && raw.length > 0) return raw
  return timeStr()
}

// 兜底 mock 数据：后端不可用时降级使用，保证页面不空白
export const fallbackProjects: Project[] = [
  {
    id: 'p1',
    name: '产品宣传片',
    description: '2026夏季新品发布宣传视频',
    status: 'completed',
    createdAt: '2026-07-08',
    updatedAt: '2026-07-09',
    duration: 180,
    sceneCount: 5,
    width: 1920,
    height: 1080,
    frameRate: 30,
    scenes: [
      { id: 's1', name: '开场动画', duration: 15, layerCount: 8, effects: [] },
      { id: 's2', name: '产品展示', duration: 60, layerCount: 12, effects: [] },
      { id: 's3', name: '功能演示', duration: 45, layerCount: 6, effects: [] },
      { id: 's4', name: '用户场景', duration: 30, layerCount: 10, effects: [] },
      { id: 's5', name: '结尾Logo', duration: 30, layerCount: 4, effects: [] },
    ],
    appliedEffects: [],
    renderOutput: 'D:/renders/product_promo_20260709.mp4',
  },
  {
    id: 'p2',
    name: '抖音短视频',
    description: '15秒竖屏短视频',
    status: 'processing',
    createdAt: '2026-07-09',
    updatedAt: '2026-07-09',
    duration: 15,
    sceneCount: 3,
    width: 1080,
    height: 1920,
    frameRate: 30,
    scenes: [
      { id: 's1', name: '开头', duration: 3, layerCount: 5, effects: [] },
      { id: 's2', name: '主体', duration: 9, layerCount: 8, effects: [] },
      { id: 's3', name: '结尾', duration: 3, layerCount: 3, effects: [] },
    ],
    appliedEffects: [],
  },
  {
    id: 'p3',
    name: '婚礼集锦',
    description: '婚礼全程精彩集锦',
    status: 'draft',
    createdAt: '2026-07-07',
    updatedAt: '2026-07-08',
    duration: 600,
    sceneCount: 12,
    width: 1920,
    height: 1080,
    frameRate: 25,
    scenes: [],
    appliedEffects: [],
  },
  {
    id: 'p4',
    name: '品牌广告',
    description: '30秒电视广告',
    status: 'completed',
    createdAt: '2026-07-06',
    updatedAt: '2026-07-08',
    duration: 90,
    sceneCount: 4,
    width: 1920,
    height: 1080,
    frameRate: 30,
    scenes: [
      { id: 's1', name: '品牌展示', duration: 15, layerCount: 6, effects: [] },
      { id: 's2', name: '产品特写', duration: 30, layerCount: 10, effects: [] },
      { id: 's3', name: '使用场景', duration: 30, layerCount: 8, effects: [] },
      { id: 's4', name: 'Logo结尾', duration: 15, layerCount: 4, effects: [] },
    ],
    appliedEffects: [],
    renderOutput: 'D:/renders/brand_ad_20260708.mp4',
  },
  {
    id: 'p5',
    name: '教程视频',
    description: 'AE基础教程',
    status: 'failed',
    createdAt: '2026-07-05',
    updatedAt: '2026-07-07',
    duration: 300,
    sceneCount: 8,
    width: 1920,
    height: 1080,
    frameRate: 30,
    scenes: [],
    appliedEffects: [],
  },
]

const initialHistory: HistoryItem[] = [
  { id: 'h1', action: '添加发光效果', timestamp: '2026-07-09 10:30', result: 'success', details: '图层: layer_001, 参数: 半径20px', projectId: 'p1' },
  { id: 'h2', action: '应用电影感风格', timestamp: '2026-07-09 10:25', result: 'success', details: '效果: 发光+模糊+渐变', projectId: 'p1' },
  { id: 'h3', action: '生成节拍动画', timestamp: '2026-07-09 10:20', result: 'pending', details: 'BPM: 120, 图层: layer_001', projectId: 'p2' },
  { id: 'h4', action: '创建合成', timestamp: '2026-07-09 10:15', result: 'success', details: '尺寸: 1920x1080, 时长: 15s', projectId: 'p2' },
  { id: 'h5', action: '渲染输出', timestamp: '2026-07-09 10:10', result: 'failure', details: '文件不存在: video.mp4', projectId: 'p5' },
]

// 兜底 mock 数据：后端不可用时降级使用
export const fallbackHistory: HistoryItem[] = initialHistory

export const useAppStore = create<AppStore>()(
  persist(
    (set, get) => ({
      // 初始为空数组，由各 Panel 在 mount 时通过 API 拉取；
      // 后端不可用时由 Panel 主动降级到 fallback 数据。
      projects: [],
      history: [],
      executionLogs: [],
      settings: defaultSettings,
      favorites: { effects: [], styles: [] },

      // ===== Project 操作 =====
      addProject: (project) => {
        const id = genId()
        const newProject: Project = {
          ...project,
          id,
          createdAt: today(),
          updatedAt: today(),
        }
        set(state => ({ projects: [newProject, ...state.projects] }))
        get().addHistory({
          action: '创建项目',
          result: 'success',
          details: `项目: ${project.name}`,
          projectId: id,
        })
        return id
      },

      updateProject: (id, updates) => {
        set(state => ({
          projects: state.projects.map(p =>
            p.id === id ? { ...p, ...updates, updatedAt: today() } : p
          )
        }))
      },

      deleteProject: (id) => {
        const project = get().getProject(id)
        set(state => ({ projects: state.projects.filter(p => p.id !== id) }))
        if (project) {
          get().addHistory({
            action: '删除项目',
            result: 'success',
            details: `项目: ${project.name}`,
          })
        }
      },

      getProject: (id) => get().projects.find(p => p.id === id),

      setProjects: (projects) => set({ projects }),

      // ===== History 操作 =====
      addHistory: (item) => {
        const newItem: HistoryItem = {
          ...item,
          id: genId(),
          timestamp: timeStr(),
        }
        set(state => ({ history: [newItem, ...state.history] }))
      },

      updateHistory: (id, updates) => {
        set(state => ({
          history: state.history.map(h => h.id === id ? { ...h, ...updates } : h)
        }))
      },

      clearHistory: () => set({ history: [] }),

      setHistory: (history) => set({ history }),

      // ===== Execution 操作 =====
      addExecutionLog: (log) => {
        const id = genId()
        const newLog: ExecutionLog = {
          ...log,
          id,
          timestamp: timeStr(),
        }
        set(state => ({ executionLogs: [newLog, ...state.executionLogs].slice(0, 50) }))
        // 同时写入历史
        get().addHistory({
          action: `执行命令: ${log.command}`,
          result: log.result,
          details: `意图: ${log.intent || '自动检测'}`,
        })
        return id
      },

      updateExecutionLog: (id, updates) => {
        set(state => ({
          executionLogs: state.executionLogs.map(l => l.id === id ? { ...l, ...updates } : l)
        }))
      },

      // ===== Settings 操作 =====
      updateSettings: (updates) => {
        set(state => ({ settings: { ...state.settings, ...updates } }))
      },

      resetSettings: () => set({ settings: defaultSettings }),

      // 备份/恢复：只覆盖传入的字段，未提供的字段保持现状
      restoreFromBackup: (data) => {
        set(state => {
          const next: Partial<typeof state> = {}
          if (Array.isArray(data.projects)) next.projects = data.projects
          if (Array.isArray(data.history)) next.history = data.history.slice(0, 100)
          if (data.settings && typeof data.settings === 'object') {
            next.settings = { ...state.settings, ...data.settings }
          }
          if (data.favorites && Array.isArray(data.favorites.effects) && Array.isArray(data.favorites.styles)) {
            next.favorites = data.favorites
          }
          return next
        })
      },

      // ===== Favorites 操作 =====
      toggleEffectFavorite: (name) => {
        set(state => {
          const effects = state.favorites.effects
          return {
            favorites: {
              ...state.favorites,
              effects: effects.includes(name)
                ? effects.filter(e => e !== name)
                : [...effects, name]
            }
          }
        })
      },

      toggleStyleFavorite: (id) => {
        set(state => {
          const styles = state.favorites.styles
          return {
            favorites: {
              ...state.favorites,
              styles: styles.includes(id)
                ? styles.filter(s => s !== id)
                : [...styles, id]
            }
          }
        })
      },

      // ===== 应用效果到项目 =====
      applyEffectToProject: (projectId, effect) => {
        if (!projectId) {
          // 没有指定项目，只记录历史
          get().addHistory({
            action: `应用效果: ${effect.name}`,
            result: 'success',
            details: effect.params.map(p => `${p.name}=${p.value}${p.unit}`).join(', '),
          })
          return
        }
        set(state => ({
          projects: state.projects.map(p =>
            p.id === projectId
              ? { ...p, appliedEffects: [...p.appliedEffects, effect], updatedAt: today() }
              : p
          )
        }))
        get().addHistory({
          action: `应用效果: ${effect.name}`,
          result: 'success',
          details: effect.params.map(p => `${p.name}=${p.value}${p.unit}`).join(', '),
          projectId,
        })
      },

      // ===== 后端同步 =====
      backendConnected: false,

      syncFromBackend: async () => {
        try {
          await api.getHealth()
          set({ backendConnected: true })
          await Promise.all([
            get().syncProjects(),
            get().syncHistory(),
          ])
        } catch {
          set({ backendConnected: false })
        }
      },

      syncProjects: async () => {
        try {
          const resp = await api.getProjects({ page: 1, page_size: 100 }) as {
            projects?: Array<Record<string, unknown>>
          }
          const list = resp?.projects
          if (Array.isArray(list) && list.length > 0) {
            const projects: Project[] = list.map((p: Record<string, unknown>) => ({
              id: String(p.id ?? ''),
              name: String(p.name ?? '未命名项目'),
              description: p.description as string | undefined,
              status: (p.status as Project['status']) || 'draft',
              createdAt: normalizeDate(p.createdAt),
              updatedAt: normalizeDate(p.updatedAt),
              duration: Number(p.duration ?? 0),
              sceneCount: Number(p.sceneCount ?? 0),
              width: Number(p.width ?? 1920),
              height: Number(p.height ?? 1080),
              frameRate: Number(p.frameRate ?? 30),
              scenes: (p.scenes as Scene[]) || [],
              appliedEffects: (p.appliedEffects as AppliedEffect[]) || [],
              renderOutput: p.renderOutput as string | undefined,
            }))
            set({ projects })
          }
        } catch {
          // 后端不可用，保持现有数据（由 Panel 自行决定是否降级到 fallback）
        }
      },

      syncHistory: async () => {
        try {
          const resp = await api.getHistory({ limit: 100 }) as {
            history?: Array<Record<string, unknown>>
          }
          const list = resp?.history
          if (Array.isArray(list) && list.length > 0) {
            const history: HistoryItem[] = list.map((h: Record<string, unknown>) => ({
              id: String(h.id ?? ''),
              action: String(h.action ?? ''),
              timestamp: normalizeTimestamp(h.timestamp),
              result: (h.result as HistoryItem['result']) || 'success',
              details: String(h.details ?? ''),
              projectId: h.projectId as string | undefined,
              params: h.params as Record<string, unknown> | undefined,
            }))
            set({ history })
          }
        } catch {
          // 后端不可用，保持现有数据
        }
      },

      submitPuppetTask: async (params) => {
        try {
          const resp = await api.submitPuppetStyle(params) as Record<string, unknown>
          const taskId = resp.task_id as string

          get().addHistory({
            action: `提交木偶风格化任务`,
            result: 'pending',
            details: `风格: ${params.style}, 任务ID: ${taskId}`,
          })

          return taskId
        } catch {
          get().addHistory({
            action: `提交木偶风格化任务失败`,
            result: 'failure',
            details: `风格: ${params.style}`,
          })
          return null
        }
      },
    }),
    {
      name: 'ae-copilot-storage',
      // 只持久化部分数据
      partialize: (state) => ({
        projects: state.projects,
        history: state.history.slice(0, 100),
        executionLogs: state.executionLogs.slice(0, 20),
        settings: state.settings,
        favorites: state.favorites,
      }),
    }
  )
)

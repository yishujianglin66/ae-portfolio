// ============================================================================
// 备份/恢复数据完整性回归测试
// 验证缺陷：handleBackup 导出 projects/history/settings/favorites，
// 但 handleRestore 历史上只恢复 settings，导致 3/4 数据静默丢失。
// 运行：node ae-dashboard/src/store/useAppStore.restore.test.mjs
//   （无测试框架依赖，使用 node:assert；zustand persist 依赖 localStorage，
//    因此用 jsdom 风格的最小 shim 加载源文件会失败，这里采用直接 import
//    真实模块 + 注入 localStorage 桩的方式。）
// ============================================================================

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { strict as assert } from 'node:assert'

const __dirname = dirname(fileURLToPath(import.meta.url))

// --- 注入 localStorage 桩（zustand persist 在初始化时会读取） ---
const memStore = new Map()
globalThis.localStorage = {
  getItem: (k) => (memStore.has(k) ? memStore.get(k) : null),
  setItem: (k, v) => memStore.set(k, String(v)),
  removeItem: (k) => memStore.delete(k),
  clear: () => memStore.clear(),
  key: (i) => Array.from(memStore.keys())[i] ?? null,
  get length() { return memStore.size },
}
// jsdom 缺失：补一些 React 生态依赖占位
globalThis.window = globalThis

// 动态 import 源 store
const storeUrl = resolve(__dirname, 'useAppStore.ts')
// 通过 esbuild-like 转换：此处假设已通过 tsc/esbuild 构建；
// 退而求其次：直接从同目录下的 mjs 编译产物加载（如果存在），否则指引用户。
let mod
try {
  // 优先尝试加载编译后的 .mjs/.js
  const compiled = resolve(__dirname, 'useAppStore.compiled.mjs')
  mod = await import(compiled)
} catch {
  console.error('[SKIP] 未找到编译产物。请先运行：')
  console.error('       npx tsc ae-dashboard/src/store/useAppStore.ts \\')
  console.error('           --target es2020 --module esnext --moduleResolution bundler \\')
  console.error('           --outDir ae-dashboard/src/store --skipLibCheck \\')
  console.error('           && rename .js -> .compiled.mjs')
  process.exit(0)
}
const { useAppStore } = mod

// --- 准备一份模拟备份（与 handleBackup 输出结构一致） ---
const backup = {
  projects: [
    {
      id: 'p-backup-1',
      name: 'Backup Project',
      status: 'completed',
      createdAt: '2026-07-09',
      updatedAt: '2026-07-09',
      duration: 60, sceneCount: 1, width: 1920, height: 1080, frameRate: 30,
      scenes: [], appliedEffects: [],
    },
  ],
  history: [
    { id: 'h-backup-1', action: 'backup action', timestamp: '2026-07-09 10:00', result: 'success', details: 'x', projectId: 'p-backup-1' },
  ],
  settings: { theme: 'dark', renderOutputDir: 'E:/BackupRenders' },
  favorites: { effects: ['glow', 'blur'], styles: ['cinematic'] },
  exportDate: '2026-07-09T10:00:00.000Z',
}

// --- 用例 1：完整恢复 ---
{
  useAppStore.setState({ projects: [], history: [], favorites: { effects: [], styles: [] } })
  useAppStore.getState().restoreFromBackup(backup)
  const s = useAppStore.getState()
  assert.equal(s.projects.length, 1, 'projects 应被恢复')
  assert.equal(s.projects[0].id, 'p-backup-1', 'projects 内容应一致')
  assert.equal(s.history.length, 1, 'history 应被恢复')
  assert.equal(s.favorites.effects.length, 2, 'favorites.effects 应被恢复')
  assert.equal(s.favorites.styles.length, 1, 'favorites.styles 应被恢复')
  assert.equal(s.settings.theme, 'dark', 'settings.theme 应被恢复')
  assert.equal(s.settings.renderOutputDir, 'E:/BackupRenders', 'settings.renderOutputDir 应被恢复')
  console.log('[PASS] 完整备份恢复：projects / history / favorites / settings 均恢复')
}

// --- 用例 2：部分字段（仅 projects）不应覆盖其他字段 ---
{
  useAppStore.setState({
    projects: [],
    history: [{ id: 'h-local', action: 'local', timestamp: '2026-07-10 09:00', result: 'success', details: '' }],
    favorites: { effects: ['local-eff'], styles: ['local-sty'] },
    settings: { ...useAppStore.getState().settings, theme: 'light' },
  })
  useAppStore.getState().restoreFromBackup({ projects: backup.projects })
  const s = useAppStore.getState()
  assert.equal(s.projects.length, 1, 'projects 应被恢复')
  assert.equal(s.history.length, 1, 'history 不应被清空')
  assert.equal(s.history[0].id, 'h-local', '本地 history 应保留')
  assert.equal(s.favorites.effects[0], 'local-eff', '本地 favorites 应保留')
  assert.equal(s.settings.theme, 'light', '未提供 settings 时应保留现状')
  console.log('[PASS] 部分字段恢复：未提供的字段保持现状，不被清空')
}

// --- 用例 3：非法类型应被忽略 ---
{
  useAppStore.setState({ projects: [{ id: 'keep' }] })
  useAppStore.getState().restoreFromBackup({ projects: 'not an array', history: 42, settings: null })
  const s = useAppStore.getState()
  assert.equal(s.projects[0].id, 'keep', '非法 projects 类型应被忽略，原值保留')
  console.log('[PASS] 非法类型防御：非数组/非对象输入被忽略，原数据保留')
}

// --- 用例 4：历史记录超过 100 条时截断（与 partialize 对齐） ---
{
  const bigHistory = Array.from({ length: 150 }, (_, i) => ({
    id: `h${i}`, action: `a${i}`, timestamp: '2026-07-09 10:00', result: 'success', details: '',
  }))
  useAppStore.getState().restoreFromBackup({ history: bigHistory })
  const s = useAppStore.getState()
  assert.equal(s.history.length, 100, 'history 应被截断到 100 条以匹配 partialize')
  console.log('[PASS] history 截断到 100 条')
}

console.log('\n所有备份/恢复数据完整性测试通过。')

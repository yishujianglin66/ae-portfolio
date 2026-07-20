/**
 * API 客户端 - 与 FastAPI 后端对接
 */

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const TOKEN_KEY = 'ae_token'
const REFRESH_KEY = 'ae_refresh_token'

class ApiClient {
  private base: string
  private token: string | null = null

  constructor(base: string) {
    this.base = base
    this.token = localStorage.getItem(TOKEN_KEY)
  }

  setToken(token: string | null, refreshToken?: string) {
    this.token = token
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
    if (refreshToken !== undefined) {
      if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken)
      else localStorage.removeItem(REFRESH_KEY)
    }
  }

  getToken(): string | null {
    return this.token
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_KEY)
  }

  private getAuthHeader(): Record<string, string> {
    return this.token ? { 'Authorization': `Bearer ${this.token}` } : {}
  }

  private async request<T>(
    path: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.base}${path}`
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
        ...options?.headers,
      },
      ...options,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || error.message || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // ===== 系统 =====
  async getHealth() {
    return this.request('/health')
  }

  async getStats() {
    return this.request('/stats')
  }

  async getResources() {
    return this.request('/resources')
  }

  // ===== 系统资源监控（CPU/内存/磁盘/GPU + 渲染进度）=====
  async getSystemResources() {
    return this.request('/system/resources')
  }

  async getSystemResourcesHistory(params?: { limit?: number }) {
    const query = new URLSearchParams()
    if (params?.limit) query.set('limit', String(params.limit))
    const q = query.toString()
    return this.request(`/system/resources/history${q ? '?' + q : ''}`)
  }

  async getRenderProgress(jobId: string) {
    return this.request(`/render/progress/${encodeURIComponent(jobId)}`)
  }

  // ===== 任务 =====
  async submitTask(data: {
    task_type: string
    input_path?: string
    output_path?: string
    config?: Record<string, unknown>
    priority?: number
  }) {
    return this.request('/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getTasks(params?: {
    status?: string
    page?: number
    page_size?: number
  }) {
    const query = new URLSearchParams()
    if (params?.status) query.set('status', params.status)
    if (params?.page) query.set('page', String(params.page))
    if (params?.page_size) query.set('page_size', String(params.page_size))
    const q = query.toString()
    return this.request(`/tasks${q ? '?' + q : ''}`)
  }

  async getTask(taskId: string) {
    return this.request(`/tasks/${taskId}`)
  }

  async cancelTask(taskId: string) {
    return this.request(`/tasks/${taskId}/cancel`, { method: 'POST' })
  }

  async waitTask(taskId: string, timeout = 60) {
    return this.request(`/tasks/${taskId}/wait?timeout=${timeout}`, {
      method: 'POST',
    })
  }

  // ===== 效果库 =====
  async getEffects(category?: string) {
    const q = category ? `?category=${encodeURIComponent(category)}` : ''
    return this.request(`/effects${q}`)
  }

  async getEffectCategories() {
    return this.request('/effects/categories')
  }

  // ===== 风格模板 =====
  async getStyles() {
    return this.request('/styles')
  }

  async getStyle(styleId: string) {
    return this.request(`/styles/${styleId}`)
  }

  // ===== 项目 =====
  async getProjects(params?: { status?: string; page?: number; page_size?: number }) {
    const query = new URLSearchParams()
    if (params?.status) query.set('status', params.status)
    if (params?.page) query.set('page', String(params.page))
    if (params?.page_size) query.set('page_size', String(params.page_size))
    const q = query.toString()
    return this.request(`/projects${q ? '?' + q : ''}`)
  }

  async createProject(data: Record<string, unknown>) {
    return this.request('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getProject(projectId: string) {
    return this.request(`/projects/${projectId}`)
  }

  async updateProject(projectId: string, data: Record<string, unknown>) {
    return this.request(`/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteProject(projectId: string) {
    return this.request(`/projects/${projectId}`, { method: 'DELETE' })
  }

  // ===== 历史记录 =====
  async getHistory(params?: { limit?: number; offset?: number; result?: string }) {
    const query = new URLSearchParams()
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.offset) query.set('offset', String(params.offset))
    if (params?.result) query.set('result', params.result)
    const q = query.toString()
    return this.request(`/history${q ? '?' + q : ''}`)
  }

  async addHistory(data: { action: string; result?: string; details?: string; projectId?: string }) {
    return this.request('/history', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async clearHistory() {
    return this.request('/history', { method: 'DELETE' })
  }

  // ===== 木偶风格化 =====
  async getPuppetStyles() {
    return this.request('/puppet/styles')
  }

  async submitPuppetStyle(data: {
    input_video: string
    output_dir: string
    style: string
    auto_detect: boolean
    quality: string
    mode: string
  }) {
    return this.request('/puppet/style', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // ===== 质量评估 =====
  async getQualityMetrics() {
    return this.request('/quality/metrics')
  }

  async submitQualityAssess(data: {
    reference_video: string
    test_video: string
    metrics: string[]
    mode: string
  }) {
    return this.request('/quality/assess', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // ===== 工作流 =====
  async submitPuppetWorkflow(params: {
    input_video: string
    output_dir: string
    style?: string
    auto_detect?: boolean
    quality?: string
    mode?: string
    priority?: number
  }) {
    const query = new URLSearchParams()
    query.set('input_video', params.input_video)
    query.set('output_dir', params.output_dir)
    if (params.style) query.set('style', params.style)
    if (params.auto_detect !== undefined) query.set('auto_detect', String(params.auto_detect))
    if (params.quality) query.set('quality', params.quality)
    if (params.mode) query.set('mode', params.mode)
    if (params.priority) query.set('priority', String(params.priority))
    return this.request(`/workflow/puppet?${query.toString()}`, { method: 'POST' })
  }

  async getWorkflowStatus(taskId: string) {
    return this.request(`/workflow/${taskId}`)
  }

  // ===== 参数优化 =====
  async optimizeParameters(context: Record<string, unknown>, useFeedback = true, mode = 'auto') {
    const query = new URLSearchParams()
    query.set('use_feedback', String(useFeedback))
    query.set('mode', mode)
    return this.request(`/optimize/parameters?${query.toString()}`, {
      method: 'POST',
      body: JSON.stringify(context),
    })
  }

  // ===== 批量处理 =====
  async submitBatch(data: {
    tasks: Array<Record<string, unknown>>
    batch_name?: string
    priority?: number
  }) {
    return this.request('/batch', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // ===== 认证 =====
  async login(username: string, password: string) {
    const res: any = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    if (res.access_token) {
      this.setToken(res.access_token, res.refresh_token)
    }
    return res
  }

  async logout() {
    try {
      await this.request('/auth/logout', { method: 'POST' })
    } finally {
      this.setToken(null)
      localStorage.removeItem(REFRESH_KEY)
    }
  }

  async refreshToken() {
    const refresh = this.getRefreshToken()
    if (!refresh) throw new Error('No refresh token')
    const res: any = await this.request('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (res.access_token) {
      this.setToken(res.access_token, res.refresh_token)
    }
    return res
  }

  async getMe() {
    return this.request('/auth/me')
  }

  async changePassword(oldPassword: string, newPassword: string) {
    return this.request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    })
  }

  async getAuditLog(params?: { page?: number; page_size?: number; action?: string }) {
    const query = new URLSearchParams()
    if (params?.page) query.set('page', String(params.page))
    if (params?.page_size) query.set('page_size', String(params.page_size))
    if (params?.action) query.set('action', params.action)
    const q = query.toString()
    return this.request(`/auth/audit-log${q ? '?' + q : ''}`)
  }

  // ===== 用户管理 =====
  async getUsers(params?: { page?: number; page_size?: number; role?: string }) {
    const query = new URLSearchParams()
    if (params?.page) query.set('page', String(params.page))
    if (params?.page_size) query.set('page_size', String(params.page_size))
    if (params?.role) query.set('role', params.role)
    const q = query.toString()
    return this.request(`/users${q ? '?' + q : ''}`)
  }

  async createUser(data: { username: string; email: string; password: string; role: string }) {
    return this.request('/users', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateUser(userId: string, data: Record<string, unknown>) {
    return this.request(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteUser(userId: string) {
    return this.request(`/users/${userId}`, { method: 'DELETE' })
  }

  // ===== 监控指标 =====
  async getMetricsSummary() {
    return this.request('/metrics/summary')
  }

  // ===== 告警 =====
  async getActiveAlerts() {
    return this.request('/alerts/active')
  }

  async getAlertHistory(params?: { page?: number; page_size?: number }) {
    const query = new URLSearchParams()
    if (params?.page) query.set('page', String(params.page))
    if (params?.page_size) query.set('page_size', String(params.page_size))
    const q = query.toString()
    return this.request(`/alerts/history${q ? '?' + q : ''}`)
  }

  // ===== 工具链 =====
  async getToolchainTools(category?: string) {
    const q = category ? `?category=${encodeURIComponent(category)}` : ''
    return this.request(`/toolchain/tools${q}`)
  }

  async getToolchainTool(toolName: string) {
    return this.request(`/toolchain/tools/${encodeURIComponent(toolName)}`)
  }

  async getToolchainCategories() {
    return this.request('/toolchain/tools/categories')
  }

  async getToolchainEngines() {
    return this.request('/toolchain/tools/engines')
  }

  async executeTool(data: {
    tool_name: string
    operation: string
    params?: Record<string, unknown>
    mode?: string
  }) {
    return this.request('/toolchain/tools/execute', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getToolchainWorkflows() {
    return this.request('/toolchain/workflows')
  }

  async getToolchainWorkflowDetail(workflowName: string) {
    return this.request(`/toolchain/workflows/${encodeURIComponent(workflowName)}`)
  }

  async executeWorkflow(data: {
    workflow_name: string
    input_path: string
    output_path: string
    mode?: string
  }) {
    return this.request('/toolchain/workflows/execute', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getToolchainStatus() {
    return this.request('/toolchain/status')
  }

  async quickRender(projectPath: string, compName: string, outputPath: string, mode = 'auto') {
    const query = new URLSearchParams()
    query.set('project_path', projectPath)
    query.set('comp_name', compName)
    query.set('output_path', outputPath)
    query.set('mode', mode)
    return this.request(`/toolchain/quick/render?${query.toString()}`, { method: 'POST' })
  }

  async quickEnhance(inputPath: string, outputPath: string, model = 'proteus', scale = 2.0, mode = 'auto') {
    const query = new URLSearchParams()
    query.set('input_path', inputPath)
    query.set('output_path', outputPath)
    query.set('model', model)
    query.set('scale', String(scale))
    query.set('mode', mode)
    return this.request(`/toolchain/quick/enhance?${query.toString()}`, { method: 'POST' })
  }

  async quickEncode(inputPath: string, outputPath: string, codec = 'h264', mode = 'auto') {
    const query = new URLSearchParams()
    query.set('input_path', inputPath)
    query.set('output_path', outputPath)
    query.set('codec', codec)
    query.set('mode', mode)
    return this.request(`/toolchain/quick/encode?${query.toString()}`, { method: 'POST' })
  }

  // ===== WebSocket =====
  connectWebSocket(onMessage: (data: unknown) => void): WebSocket {
    const wsUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws/progress`
    const ws = new WebSocket(wsUrl)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch {
        // ignore parse errors
      }
    }

    return ws
  }
}

export const api = new ApiClient(API_BASE)

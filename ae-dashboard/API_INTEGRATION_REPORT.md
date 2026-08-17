# AE Dashboard 前端真实 API 治理报告

> 执行时间：2026-08-14 ｜ 执行方式：真实构建 + 真实 API 调用（非纸面推理）
> 范围：`ae-dashboard`（React18 + TS + Vite5 + Zustand5）↔ 后端 FastAPI（`web/api_server.py`）
> 环境：Node v22.22.3 / npm 10.9.8 / Python 3.11（fastapi 0.136.3 / uvicorn 0.48.0）

---

## 1. 结论速览

| 项 | 结果 | 证据 |
|---|---|---|
| 前端真实构建 | ✅ 成功（改动前后均通过） | `tsc && vite build`，1538 modules，产物见 §2 |
| Mock 使用全貌 | ✅ 已盘点 | 5 个页面组件 + 1 个 store 兜底，见 §3 |
| 后端入口定位 | ✅ 已确认 | `web/api_server.py`，`/health` + `/api/v1/health`，端口 8000，见 §4 |
| 第一条真实调用 | ✅ 已打通并留证 | `/health` 200 + 登录→stats→effects 全链路 + vite 代理链路，见 §5 |
| 前端接入真实 API | ✅ 已落地并重新构建通过 | Dashboard 健康状态指示器，见 §6 |

**一句话结论**：PHASE10 审计的"大量 mock 回退"是**有意的降级策略而非纯假数据**——前端 `src/lib/api.ts` 已有 60+ 真实端点封装、store 已有 `syncFromBackend` 真实同步，mock 仅在**后端不可用/未登录(401)** 时兜底。本次治理已把 Dashboard 第一条无鉴权真实调用（`/api/v1/health`）落地为可见 UI，并完整打通 浏览器→vite 代理→FastAPI 链路。

---

## 2. 构建验证（真实执行）

### 2.1 依赖与命令
- `ae-dashboard/package.json`：`build = tsc && vite build`；依赖 react 18.2 / zustand 5.0 / tailwindcss 3.4 / lucide-react 等。
- `node_modules` 已存在（无需 `npm install`），直接执行 `npm run build`。

### 2.2 改动前首次构建输出（末尾）
```
> ae-dashboard@0.1.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 1538 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.47 kB │ gzip:   0.31 kB
dist/assets/index-f0wtcgEd.css   31.91 kB │ gzip:   6.25 kB
dist/assets/index-ISXEcpdD.js   382.84 kB │ gzip: 106.37 kB
✓ built in 21.17s
```
✅ **构建成功**（TypeScript 类型检查 `tsc` + Vite 打包均通过，无报错）。

### 2.3 改动后重新构建输出（末尾）
```
dist/assets/index-BoqrlSjS.js   383.56 kB │ gzip: 106.54 kB
✓ built in 22.02s
```
✅ 新 bundle hash（`BoqrlSjS`），健康指示器代码已进入产物；经 grep 确认 bundle 含 `'/api/v1'`、`'/health'`、`'getHealth'`。

---

## 3. Mock 使用全貌盘点（真实 grep）

### 3.1 引用 mock 的组件/页面（`grep mockData|Mock|mock ae-dashboard/src`）

| 文件 | 引用内容 | 性质 |
|---|---|---|
| `src/components/pages/Dashboard.tsx` | `mockEffects` / `mockStyleTemplates`（初始计数） | 兜底：`api.getEffects()/getStyles()` 失败时回退长度 |
| `src/components/pages/EffectsPanel.tsx` | `mockEffects`（L70-71, L79-80） | 兜底：API 返回空/失败时 setEffects(mockEffects) |
| `src/components/pages/StylesPanel.tsx` | `mockStyleTemplates` / `mockEffects`（L55, L62, L86） | 兜底 + 效果名→详情查找 |
| `src/components/pages/ExecutePanel.tsx` | `mockEffects` / `mockStyleTemplates` / `intentTypes`（L348, L371） | 下拉选项数据（静态枚举，非数据回退） |
| `src/components/pages/PreviewModal.tsx` | `mockEffects` / `mockStyleTemplates`（L35-36） | 参数名查找（按 name/id 取参数定义） |
| `src/store/useAppStore.ts` | `fallbackProjects`（L190）/ `fallbackHistory`（L294） | 后端不可用时 store 初始数据；`isDegraded` 标记降级（Header 提示条） |

### 3.2 mockData.ts 定义的假数据（`src/data/mockData.ts`）
- `mockEffects`：5 个效果（发光/模糊/粒子/噪波/渐变，含参数定义）——**与后端真实数据同构**（后端 `/api/v1/effects` 返回 8 个，含同样的 ADBE Glo2/Blur/Particular/Noise/Ramp）。
- `mockStyleTemplates`：5 个风格模板（电影感/赛博朋克/极简/复古/梦幻，thumbnail 指向 trae-api 占位图）。
- `mockProjects`：5 个假项目；`mockHistory`：5 条假历史；`intentTypes`：6 个命令意图枚举。

### 3.3 现有 API 封装情况（`grep fetch\(|axios|/api/`）
- **`src/lib/api.ts`（557 行）——已是完整真实 API client**：`API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'`；`fetch` 封装 + 30s 超时 + 401 自动 refresh token 重试；60+ 端点（health/stats/effects/styles/projects/history/tasks/puppet/quality/toolchain/evolution/auth/users/alerts/websocket 等）；token 仅存内存、refresh token 存 sessionStorage（安全设计）。
- **`src/lib/useApi.ts`**：通用 `useApiData` hook + 8 个业务 hook（useStats/useResources/useEffects/useStyles/useProjects/useHistory/useTasks/usePuppetStyles）。
- **`src/store/useAppStore.ts`**：`syncFromBackend()` 挂载时真实调用 `api.getHealth()` → `backendConnected=true, isDegraded=false`，再并行 `syncProjects()`（`api.getProjects`）与 `syncHistory()`（`api.getHistory`）；失败置 `isDegraded=true`。`App.tsx` L56/L79 挂载时调用；`Header.tsx` 按 `isDegraded` 显示降级横幅。
- **直连 fetch 页面**：`FlagshipPipeline.tsx`（`/api/v1/flagship`）、`StyleCopyPanel.tsx`（`/api/style-copy/analyze|run`）、`EvolutionPanel.tsx`（注释声明 `/api/v1/evolution/*`）。
- **未用 axios**（全部原生 fetch）。

> 结论：mock 是**降级兜底**，触发条件为①后端进程未启动（网络失败）②未登录（受保护端点 401）③后端返回空列表。真实数据链路已存在但未登录状态下被 mock 遮盖——这正是本次治理用**无鉴权 `/health`** 立起真实调用证据的原因。

---

## 4. 后端入口定位（真实 grep）

`grep FastAPI\(` 全库命中 10 处，主入口：

| 文件 | 行 | app 定义 | 端口 | 说明 |
|---|---|---|---|---|
| **`web/api_server.py`** | L416 | `FastAPI(title="AE Knowledge Vault API", version="1.0.0")` | `API_PORT` 默认 **8000**（L2136） | **前端对齐的真实后端**（api.ts WebSocket 注释明确指向它）；`/health`(L546) 与 `/api/v1/health`(L566，前端 API_BASE 别名) 双端点；vite.config 代理亦指向 8000 |
| `web/integrator_api.py` | L653 | `FastAPI(` | — | 集成器 API |
| `puppet-automation/src/api/main.py` | L656 | `FastAPI(` | — | puppet-automation 自带 API（也有 `/api/v1/health`） |
| 其余 7 处 | — | 测试/工具脚本 | — | 非服务入口 |

**健康检查端点**：
- `GET /health`（L546，无需鉴权）→ `HealthResponse{status, version, timestamp, uptime, services}`
- `GET /api/v1/health`（L566，别名，与前端 `API_BASE=/api/v1` 对齐）
- 可选模块（toolchain_api / ai_chat_api / style_copy）缺失时优雅降级（ImportError 捕获 + WARNING 日志），核心健康检查不受影响。

启动方式（已验证）：`py -3.11 -m uvicorn api_server:app --host 127.0.0.1 --port 8000`（工作目录 `web/`）。

---

## 5. 真实 API 调用证据

### 5.1 直接健康检查（真实响应）
```
$ Invoke-RestMethod http://127.0.0.1:8000/health
{
    "status":  "healthy",
    "version":  "1.0.0",
    "timestamp":  1786641068.5666435,
    "uptime":  7.59504246711731,
    "services":  { "api":  "healthy", "auth":  "healthy" }
}
```

### 5.2 前端实际请求路径 `/api/v1/health`（真实响应，200）
```
$ Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
{ "status": "healthy", "version": "1.0.0", ..., "services": { "api": "healthy", "auth": "healthy" } }
```

### 5.3 鉴权全链路（登录→token→真实数据）
```
1) POST /api/v1/auth/login  {username: admin, ...}
   → login OK, token_type=Bearer, access_token_len=520

2) GET /api/v1/stats  (Authorization: Bearer <token>)
   → { "tasks": {}, "workers": 0, "uptime": 26.6, "memory_usage": 97.9, "cpu_usage": 61.9 }

3) GET /api/v1/effects  (Authorization: Bearer <token>)
   → { "effects": [8 个真实效果: ADBE Glo2/Blur/Particular/Noise/Ramp/Drop Shadow/Color Balance/Motion Tile],
       "total": 8, "categories": [视觉效果/特效/扭曲/生成效果/颜色校正/透视] }
```
> 注：控制台中文乱码仅为 PowerShell GBK 显示问题，响应本体为 UTF-8 JSON（前端 `res.effects` 分支可正确解析）。未带 token 时 `/api/v1/stats`、`/api/v1/effects` 返回 **401**——即 mock 回退的真实触发条件。

### 5.4 端到端链路（浏览器侧，经 vite proxy）
vite.config.ts 已配置 `/api`、`/health`、`/ws` → `localhost:8000` 代理。实测（vite dev :5174 运行中）：
```
$ curl http://localhost:5174/api/v1/health
{"status":"healthy","version":"1.0.0","timestamp":1786641195.12742,
 "uptime":134.1907353401184,"services":{"api":"healthy","auth":"healthy"}}
HTTP_CODE=200
```
✅ 浏览器 → vite dev(5174) → 代理 → FastAPI(8000) 全链路 200。

---

## 6. 前端接入真实 API（本次改动）

### 6.1 修改文件：`ae-dashboard/src/components/pages/Dashboard.tsx`
在"资源统计"卡片顶部新增**后端服务状态**指示器，调用 `api.getHealth()`（→ `GET /api/v1/health`，无需鉴权，只读、零破坏风险）：

- 新增 state：`backendHealth`（status/version/services）、`healthLoading`
- 新增 `useEffect`：挂载时 `api.getHealth()`，成功渲染绿标"已连接 v{version}"并展示 `services: api:healthy · auth:healthy`，失败渲染红标"未连接"，加载中灰标"检测中…"
- UI 行：`后端服务状态` 标签 + 状态 Badge + services 明细行

### 6.2 重新构建验证（真实执行）
```
> tsc && vite build
✓ 1538 modules transformed.
dist/assets/index-BoqrlSjS.js   383.56 kB │ gzip: 106.54 kB
✓ built in 22.02s
```
✅ 编译通过；产物含 `getHealth` / `/api/v1` / `/health`（grep 实证）。

---

## 7. 下一步建议

1. **登录态治理**：Dashboard/EffectsPanel/StylesPanel 的受保护端点（`/effects`、`/styles`、`/projects`）在未登录时必然 401→mock。建议在 App.tsx 挂载时若 `backendConnected` 则引导登录（LoginPage 已有），登录成功后 `syncFromBackend` 立即刷新，把"真实数据+mock 兜底"切换为"真实数据为主"。
2. **API 形状对齐**：后端 `/api/v1/effects` 返回 `{effects, total, categories}`（含 `name_en/description`），前端 `Effect` 接口无 name_en/description——建议扩展类型后去掉 mockData 中同名效果。
3. **生产部署代理**：dev 由 vite proxy 转发；生产 build 后需由反向代理（nginx/Caddy）将 `/api`、`/ws`、`/health` 转发到 8000，或配置 `VITE_API_BASE` 指向完整后端地址（注意 CORS：`AE_VAULT_CORS_ORIGINS` 需含生产域名）。
4. **mockData.ts 收敛**：`mockProjects/mockHistory` 已被 `fallbackProjects/fallbackHistory` 取代（store 兜底），可清理；`ExecutePanel` 的意图枚举建议移到常量文件并逐步由 `/api/v1/compose` 等真实端点替换。
5. **可选模块补齐**：后端缺 `toolchain_api`/`ai_chat_api`（仅 WARNING 降级），如需工具链/聊天面板真实数据需安装对应模块（`puppet-automation/src` 有实现）。

---

## 附：关键路径速查
- 前端 API client：`ae-dashboard/src/lib/api.ts`（60+ 端点，`VITE_API_BASE` 可配）
- 前端 hooks：`ae-dashboard/src/lib/useApi.ts`
- 前端 store 同步：`ae-dashboard/src/store/useAppStore.ts`（`syncFromBackend`）
- 后端入口：`web/api_server.py`（`/health` L546、`/api/v1/health` L566、端口 8000 L2136）
- 后端备选入口：`puppet-automation/src/api/main.py`
- vite 代理：`ae-dashboard/vite.config.ts`（/api、/ws、/health → localhost:8000）

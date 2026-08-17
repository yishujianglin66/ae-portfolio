# OpenBiliClaw 集成计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 OpenBiliClaw（跨平台 AI 内容发现 Agent）部署到本机，并接入 DSH Web UI，实现边用 DSH 干活边刷个性化推荐。

**Architecture:** OpenBiliClaw 后端（Python + SQLite）本地运行在 8420 端口 → DSH 插件通过 HTTP + WebSocket 连接后端 → DSH Web UI 右侧第四栏展示推荐/内容库/对话/画像面板 + 注册 22 个 Agent Bridge 工具。

**Tech Stack:** Python 3.12, SQLite, Node.js, DeepSeek Harness v0.1, Chrome 浏览器插件

---

## 前置条件

- [x] Node.js v22 已安装
- [x] Python 3.12 已安装
- [x] DSH Web UI 已部署（http://127.0.0.1:3080）
- [ ] OpenBiliClaw 后端未安装
- [ ] DSH 插件未安装

---

### Task 1: 安装 OpenBiliClaw 后端

**Files:**
- 安装目录: `C:\Users\Administrator\Desktop\OpenBiliClaw\`（建议）

- [ ] **Step 1: 克隆仓库**

```powershell
cd C:\Users\Administrator\Desktop
git clone https://github.com/whiteguo233/OpenBiliClaw.git
```

- [ ] **Step 2: 创建虚拟环境并安装依赖**

```powershell
cd C:\Users\Administrator\Desktop\OpenBiliClaw
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

- [ ] **Step 3: 下载向量模型（bge-m3）**

精简版首次启动自动下载，或手动：
```powershell
# 模型约 1.1GB，需联网
# 也可下载 -with-embedding 完整版安装包跳过此步
```

- [ ] **Step 4: 启动后端验证**

```powershell
python -m openbiliclaw.server
# 访问 http://127.0.0.1:8420/web 确认 Web UI 可打开
```

- [ ] **Step 5: 开启 Agent Bridge v2**

```powershell
python -m openbiliclaw.integrations.openclaw.cli start
# 确认 bridge CLI 可调用
```

- [ ] **Step 6: 安装 Chrome 浏览器插件**

从 Chrome 应用商店安装，或从 Latest Release 下载 zip 手动安装。插件负责平台登录会话和 Cookie 同步。

---

### Task 2: 安装 DSH 插件

**Files:**
- 插件目录: `~/.dsh/profiles/web/node_modules/@openbiliclaw/dsh-plugin/`
- 配置文件: `~/.dsh/profiles/web/cordis.patch.yml`

- [ ] **Step 1: 克隆 DSH 插件仓库**

```powershell
cd C:\Users\Administrator\Desktop
git clone https://github.com/whiteguo233/dsh-openbiliclaw.git
```

- [ ] **Step 2: 复制到 DSH profile 的 node_modules**

```powershell
$dest = "$env:USERPROFILE\.dsh\profiles\web\node_modules\@openbiliclaw\dsh-plugin"
New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
Copy-Item -Recurse -Force "C:\Users\Administrator\Desktop\dsh-openbiliclaw\*" $dest
```

- [ ] **Step 3: 注册到 cordis.patch.yml**

在 `~/.dsh/profiles/web/cordis.patch.yml` 末尾追加：

```yaml
    - id: openbiliclaw
      name: '@openbiliclaw/dsh-plugin'
      config:
        workdir: 'C:\Users\Administrator\Desktop\OpenBiliClaw'
```

注意缩进对齐现有 `- insert:` 块内的条目。

- [ ] **Step 4: 重启 DSH**

```powershell
# 停止现有 DSH 进程
# 重新启动
Set-Location C:\Users\Administrator
& "C:\Users\Administrator\AppData\Roaming\npm\dsh.cmd" --profile web
```

- [ ] **Step 5: 验证 DSH 第四栏**

浏览器访问 http://127.0.0.1:3080，右侧应出现第四栏（推荐/内容库/对话/画像/设置）。

---

### Task 3: 配置与初始化

**Files:**
- 后端配置: `C:\Users\Administrator\Desktop\OpenBiliClaw\config.toml`
- DSH 面板设置: DSH Web UI → 第四栏 → 设置

- [ ] **Step 1: 配置 LLM Provider**

编辑 `config.toml`，设置你的 DeepSeek API Key：

```toml
[llm]
provider = "deepseek"
api_key = "sk-xxxxxxxx"
model = "deepseek-chat"
```

- [ ] **Step 2: 连接内容源**

在 DSH 第四栏 → 设置 → 通用，确认连接地址为 `http://127.0.0.1:8420/api`。

在 Chrome 插件中登录 B 站（默认初始化来源），或选择小红书/抖音/YouTube 等。

- [ ] **Step 3: 初始化画像**

首次使用时，OpenBiliClaw 会基于你的浏览历史构建五层灵魂画像（事件→偏好→觉察→洞察→灵魂）。可以通过对话调教来校准。

---

### Task 4: 与 AE-Knowledge-Vault 项目联动

**Files:**
- 知识库: `c:\Users\Administrator\Desktop\AE-Knowledge-Vault\10-风格化剪辑知识库\`
- 素材搜索: `c:\Users\Administrator\Desktop\AE-Knowledge-Vault\13-素材获取与搜索\`

- [ ] **Step 1: 用 OpenBiliClaw 发现素材灵感**

在 DSH 第四栏刷推荐时，关注 B 站/小红书上的 AE 教程、剪辑技巧、特效案例。收藏有价值的内容。

- [ ] **Step 2: Agent 闭环**

DSH Agent 可通过 22 个 `openbiliclaw_*` 工具读取推荐、回答探测、保存内容。例如：
- 让 Agent 搜索"AE 粒子特效教程"相关的推荐内容
- Agent 代答兴趣探测，自动完善画像
- 收藏的内容可导出为素材参考清单

- [ ] **Step 3: 知识库反哺**

将 OpenBiliClaw 发现的高质量教程/案例整理后纳入 `10-风格化剪辑知识库` 或 `11-大师知识库`，形成「发现→学习→沉淀」闭环。

---

## 预期效果

```
┌───────────────────────────── DSH Web GUI ─────────────────────────────
│  左边栏     │   会话区        │  详情栏    │  ┌─ OpenBiliClaw 面板 ─┐ │
│ (DSH 自带)  │  (DSH 自带)     │ (DSH 自带) │  │ ✨ 推荐 / 内容库     │ │
│             │                 │           │  │ / 对话 / 画像 / 设置  │ │
└─────────────────────────────┬─────────────────────────────────────────┘
│ HTTP + WebSocket (http://127.0.0.1:8420)
┌─────────────────────────────▼─────────────────────────────────────────┐
│         OpenBiliClaw 后端 (Python + SQLite + bge-m3 向量模型)          │
───────────────────────────────────────────────────────────────────────┘
```

- 左边和 Agent 聊 AE 剪辑需求，右边刷 B 站/小红书推荐的 AE 教程
- 22 个 Agent 工具让 DSH Agent 也能操作推荐系统
- 100% 本地运行，数据不上传

---

## 风险与注意事项

| 风险 | 缓解措施 |
|------|----------|
| bge-m3 模型下载慢（1.1GB） | 用 -with-embedding 完整版安装包，或夜间下载 |
| Python 依赖冲突 | 严格使用 .venv 虚拟环境 |
| DSH 第四栏不显示 | 确认 DSH 版本支持 aside 列（v0.1.0-rc.6 已原生支持） |
| Agent Bridge v2 CLI 调用失败 | 确认 `.venv/Scripts/python.exe` 路径正确 |
| Chrome 插件与后端版本不匹配 | 从同一 Release 版本下载 |

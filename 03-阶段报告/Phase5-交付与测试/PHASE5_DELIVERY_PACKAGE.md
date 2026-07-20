# Phase 5 — 交付包 (Delivery Package)

> **项目**: AE StudioKit Enterprise Upgrade  
> **版本**: v2.0.0  
> **日期**: 2026-06-05  
> **阶段**: 第五阶段 — 最终交付  
> **包含**: 完整文件清单 + 部署指南 + 发布说明 + 已知问题

---

## 1. 项目交付物总览

### 1.1 项目指标

| 指标 | 数值 |
|------|------|
| 版本号 | v2.0.0 (CEP 扩展) |
| CEP 清单 | CSXS 12, ExtensionBundleId: `com.aestudiokit.panel` |
| AE 兼容 | CC 2023–2029+ (Host AEFT v16.0–99.0) |
| 面板入口 | "AE StudioKit" (生产面板) + "AE StudioKit - Studio Kit" (开发面板) |
| 总文件数 | ~200+ |
| 磁盘占用 | ~1.75 GB (含 AI 模型 ~1.24 GB + FFmpeg ~292 MB) |
| 可回收空间 | ~204 MB (历史输出/临时文件) |

### 1.2 五阶段完成度

| 阶段 | 产出 | 完成日期 | 关键成果 |
|------|------|----------|----------|
| Phase 1 | 遗产资产深度剖析 | 2026-06-05 | 24 设计模式 + 37 反模式 + 28 可复用资产 |
| Phase 2 | F1-F8 原子模块优化 | 2026-06-05 | 3 共享模块 + 8 异步化 + 8 设计文档 |
| Phase 3 | 统一操作面板开发 | 2026-06-05 | 4 层架构 + Studio Kit CEP 面板 |
| Phase 4 | 文件路径与命名规范化 | 2026-06-05 | 无硬编码路径 + 命名标准化 |
| **Phase 5** | **集成测试与质量验收** | **2026-06-05** | **测试规格书 + 交付包** |

---

## 2. 完整文件清单

### 2.1 核心运行时 (REQUIRED)

```
ae-vocal-remover/                          # 项目根 — 部署到 %APPDATA%\Adobe\CEP\extensions\
│
├── CSXS/
│   └── manifest.xml                       # CEP 扩展清单 (v2.0.0, 双面板)
│
├── client/                                # CEP 前端 (Chromium 74, ES5)
│   ├── index.html                         # 主生产面板 (9 标签, 466 行)
│   ├── app.js                             # 主协调器 (48 函数, 1352 行)
│   ├── style.css                          # 深色/浅色自适应主题
│   ├── CSInterface.js                     # CEP 通信 polyfill
│   ├── poll-manager.js                    # 异步轮询管理器 (338 行)
│   └── studio-kit/                        # Studio Kit 面板 (Phase 3)
│       ├── index.html                     # 8 标签面板 UI (340 行)
│       └── studio-kit.js                  # 面板逻辑 + aeCall + PollManager (450 行)
│
├── host/                                  # ExtendScript 后端 (ES3)
│   ├── index.jsx                          # 统一入口 — 加载所有模块 (222+ 行)
│   ├── main.jsx                           # cepDispatch 核心路由器 (~1808 行)
│   ├── text_engine.jsx                    # 文字动画引擎 (30 预设, 624 行)
│   ├── studio-kit-bridge.jsx              # F1-F8 统一调度桥接 (290 行, Phase 3)
│   ├── utils/                             # 工具模块
│   │   ├── logger.jsx                     # 日志基础设施
│   │   ├── async-helper.jsx               # 异步辅助
│   │   └── json-polyfill.jsx              # JSON 兼容层
│   ├── bridge/                            # 桥接模块
│   │   ├── ae-bridge.jsx                  # AE-Python 桥接
│   │   └── poll-manager.jsx               # ExtendScript 侧轮询
│   ├── text-fx/                           # 文字特效模块
│   │   ├── apply-preset.jsx               # 预设应用
│   │   ├── create-composition.jsx         # 合成创建
│   │   └── scan-presets.jsx               # 预设扫描
│   └── vocal/                             # 人声模块
│       ├── import-audio.jsx               # 音频导入
│       └── open-folder.jsx                # 文件夹打开
│
├── server/                                # Python 后端 (v4.0 主项目)
│   ├── server.py                          # FastAPI 主服务 :8765 (1604 行, 31 端点)
│   ├── ae_bridge.py                       # CLI 桥接 (16 子命令)
│   ├── config.py                          # 全局配置 (端口/路径)
│   ├── effects.py                         # AI 音效引擎 (5 类 18 种)
│   ├── ai_recommender.py                  # NLP 推荐 (3 层降级)
│   ├── preset_library.py                  # SQLite 预设库
│   ├── preset_scraper.py                  # LookAE 抓取器 (4 级降级)
│   ├── preset_generator.py                # AI 预设生成
│   ├── ffx_parser.py                      # .ffx 二进制解析
│   ├── generate_ffx.py                    # .ffx 生成
│   ├── preview_renderer.py                # 预览渲染
│   ├── sound_api.py                       # Freesound API (未对接)
│   ├── tts_api.py                         # 百度 TTS (未对接)
│   ├── install_deps.bat                   # 一键安装依赖
│   ├── start_server.bat                   # 启动 GPU 服务器
│   ├── launch_server.vbs                  # VBS 无窗口启动
│   └── requirements.txt                   # Python 依赖列表
│
├── test-suites/                           # F1-F8 原子功能模块
│   ├── _shared/                           # 共享基础设施
│   │   ├── AEStudioKit_Logger.jsx         # 日志模块
│   │   ├── AEStudioKit_ModuleLoader.jsx    # 模块加载器 (消除 6× 重复)
│   │   ├── AEStudioKit_AnimatorAPI.jsx    # 动画 API (消除 3× 重复)
│   │   └── AEStudioKit_JSON.jsx           # JSON polyfill (消除 3× 重复)
│   ├── F1-layer-type/F1_layer_type.jsx    # 图层类型检测 (~510 行)
│   ├── F2-text-anim/F2_text_anim.jsx      # 文字动画预设 (~420 行)
│   ├── F3-preset-file/F3_apply_preset.jsx # 预设文件应用 (~400 行)
│   ├── F4-audio-extract/F4_extract_audio.jsx # 音频提取 (~380 行, 异步)
│   ├── F5-vocal-sep/                      # 人声分离 CLI
│   │   └── F5_vocal_separate.py           # Python 分离引擎 (~530 行, 异步)
│   ├── F6-import-audio/F6_import_audio.jsx # 音频导入 (~245 行)
│   ├── F7-download/F7_download.jsx        # 文件下载 (~330 行, 异步)
│   └── F8-topaz-detect/F8_topaz_detect.jsx # Topaz 检测 (~190 行)
│
├── ffmpeg-8.1.1-essentials_build/         # 便携 FFmpeg (~292 MB)
│   └── bin/{ffmpeg,ffplay,ffprobe}.exe
│
├── img/
│   ├── icon_19.png                        # 工具栏小图标
│   └── icon_38.png                        # 面板图标
│
└── README.md                              # 安装说明
```

### 2.2 文档 (DOCUMENTATION)

```
ae-vocal-remover/docs/
├── phase1/
│   └── PHASE1_MAIN_REPORT.md              # 遗产资产深度剖析 (55 文件, ~18,500 行)
├── phase2/
│   ├── PHASE2_OPTIMIZATION_PLAN.md        # F1-F8 优化主计划
│   ├── F1_optimization.md                 # F1 优化设计书
│   ├── F2_optimization.md                 # F2 优化设计书
│   ├── F3_optimization.md                 # F3 优化设计书
│   ├── F4_optimization.md                 # F4 异步改造设计书
│   ├── F5_optimization.md                 # F5 CEP 桥接设计书
│   ├── F6_optimization.md                 # F6 优化设计书
│   ├── F7_optimization.md                 # F7 异步改造设计书
│   └── F8_optimization.md                 # F8 优化设计书
├── phase3/
│   └── PHASE3_ARCHITECTURE.md             # Studio Kit 架构设计文档
├── phase4/
│   └── PHASE4_REPORT.md                   # 路径规范化报告
├── phase5/
│   ├── PHASE5_TEST_SPEC.md                # 集成测试规格说明书
│   └── PHASE5_DELIVERY_PACKAGE.md         # 本文件 — 交付包
│
├── AUDIT_REPORT.md                        # 全项目审计报告 (2026-06-03)
└── .claude/CLAUDE.md                      # 项目开发指南 + API 参考
```

### 2.3 排除项 (NOT INCLUDED)

以下文件/目录不包含在交付包中：

| 路径 | 原因 |
|------|------|
| `server/output/` (~175 MB) | 历史处理结果 — 部署后自动生成 |
| `server/temp/` (~28 MB) | 临时上传残留 |
| `server/__pycache__/` | Python 字节码缓存 — 自动重建 |
| `server/models/` (~1.24 GB) | AI 模型 — 需单独下载 (太大不宜打包) |
| `VocalSep_Consolidated.jsx` (199 KB) | 已废弃的独立 ScriptUI 版本 |
| `zz.aep`, `实验.aep`, `无标题项目.aep` | AE 测试项目 |
| `*.bak`, `*.test`, `*.txt` (已清理) | 过期文件 |
| `AE-MotionStudio/` (三套副本) | 平行架构线 — 独立项目 |

### 2.4 推荐清理

部署前可安全删除 (~204 MB)：

```bash
# 清理历史输出
rm -rf server/output/*
rm -rf server/temp/*

# 清理缓存
rm -rf server/__pycache__/

# 清理测试项目
rm -f zz.aep 实验.aep 无标题项目.aep
rm -rf "Adobe After Effects 自动保存/"
```

---

## 3. 部署指南

### 3.1 系统要求

| 组件 | 最低要求 | 推荐 |
|------|----------|------|
| OS | Windows 10 64-bit | Windows 11 |
| AE | CC 2023 (v16.0) | CC 2025+ |
| Python | 3.8 | 3.11+ |
| FFmpeg | 4.0+ | 8.1.1 (已捆绑) |
| GPU | 无 (CPU 降级可用) | NVIDIA RTX 6GB+ VRAM |
| RAM | 8 GB | 16 GB+ |
| 磁盘 | 2 GB 可用 | 5 GB+ (含模型) |

### 3.2 部署步骤

#### Step 1: 开启 CEP 调试模式

```batch
:: 以管理员身份运行
REG ADD "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_DWORD /d 1 /f
```

#### Step 2: 安装 Python 依赖

```batch
cd server
install_deps.bat
:: 或手动: pip install -r requirements.txt
```

#### Step 3: 下载 AI 模型 (可选 — GPU 分离)

模型文件需单独下载到 `server/models/` (总大小 ~1.24 GB)。详细模型列表见 `AUDIT_REPORT.md` 第 8.f 节。

#### Step 4: 部署扩展到 CEP 目录

```batch
:: 方式 A: 直接复制 (注意: 源路径末尾 \* 避免嵌套)
xcopy /E /I /Y "ae-vocal-remover\*" "%APPDATA%\Adobe\CEP\extensions\ae-vocal-remover\"

:: 方式 B: 符号链接 (开发)
mklink /D "%APPDATA%\Adobe\CEP\extensions\ae-vocal-remover" "C:\path\to\ae-vocal-remover"
```

#### Step 5: 启动

1. 启动 After Effects
2. 窗口 → 扩展 → **AE StudioKit** (生产面板)
3. 窗口 → 扩展 → **AE StudioKit - Studio Kit** (开发/测试面板)
4. 可选: 启动 GPU 服务器 (`server/start_server.bat`)

### 3.3 验证部署

```
✅ 面板打开无报错 (Chrome DevTools F12)
✅ Bridge 状态指示灯绿色
✅ 标签切换正常
✅ F8 Topaz 检测可用 (快速桥接测试)
✅ Python 检测: 主面板 → 系统诊断
✅ GPU 服务器: curl http://127.0.0.1:8765/health → {"status":"ok"}
```

---

## 4. 架构速览

### 4.1 通信流

```
CEP Panel (Chromium 74)                   ExtendScript (ES3)              Python
══════════════════════                     ═════════════════              ══════
client/app.js                              host/index.jsx                 server/
client/studio-kit/studio-kit.js            host/main.jsx                  ae_bridge.py
    │                                         │                             │
    │ CSInterface.evalScript()                │                             │
    │ "AEStudioKit.dispatch('action',{})"      │                             │
    ├────────────────────────────────────────►│                             │
    │                                         │ system.callSystem()         │
    │                                         │ "python ae_bridge.py ..."   │
    │                                         ├────────────────────────────►│
    │                                         │                             │ HTTP
    │                                         │                             ├──► server.py :8765
    │                                         │          OK:JSON            │
    │                                         │◄────────────────────────────┤
    │              {"success":true,...}        │                             │
    │◄────────────────────────────────────────┤                             │
```

### 4.2 双面板架构

```
AE StudioKit Extension Bundle (com.aestudiokit.panel)
├── DispatchInfo 1: "AE StudioKit"
│   └── MainPath: client/index.html (9-tab production panel)
│   └── ScriptPath: host/index.jsx
│
└── DispatchInfo 2: "AE StudioKit - Studio Kit"
    └── MainPath: client/studio-kit/index.html (8-tab dev panel)
    └── ScriptPath: host/index.jsx (shared!)
```

两个面板共享同一个 `host/index.jsx` ExtendScript 后端，通过 `AEStudioKit.dispatch()` 统一路由。

### 4.3 Studio Kit 4 层架构

```
L1: CEP Panel     →  client/studio-kit/{index.html, studio-kit.js}
L2: Dispatcher    →  host/index.jsx → AEStudioKit.dispatch('studioKit', ...)
L3: Bridge        →  host/studio-kit-bridge.jsx → studioKitDispatch(F#, action, params)
L4: F Modules     →  test-suites/F*-*/ → $.global.F#_dispatch(action, params)
```

---

## 5. 模块状态矩阵 (交付时)

### 5.1 F 原子模块 (8/8 优化完成)

| 模块 | 功能 | 同步 | 异步 | CEP 集成 | 测试状态 |
|------|------|:----:|:----:|:--------:|:--------:|
| F1 | 图层类型检测 | ✅ | N/A | ✅ | 待执行 |
| F2 | 文字动画 (30+ 预设) | ✅ | N/A | ✅ | 待执行 |
| F3 | 预设文件应用 | ✅ | N/A | ✅ | 待执行 |
| F4 | 音频提取 (FFmpeg) | ✅ | ✅ | ✅ | 待执行 |
| F5 | 人声分离 (AI+FFmpeg) | ✅ | ✅ | ✅ (CLI) | 待执行 |
| F6 | 音频导入 + 批量 | ✅ | N/A | ✅ | 待执行 |
| F7 | 文件下载 (PowerShell) | ✅ | ✅ | ✅ | 待执行 |
| F8 | Topaz 检测 | ✅ | N/A | ✅ | 待执行 |

### 5.2 生产面板 (9 标签, v4.0)

| 标签 | 完成度 | 状态 | 异步 | 测试状态 |
|------|--------|------|:----:|:--------:|
| 1. 人声分离 | 90% | ✅ 可用 | ✅ | 待执行 |
| 2. 文字特效 | 85% | ✅ 可用 | ✅ | 待执行 |
| 3. 多轨分离 | 70% | ⚠️ 部分 | ✅ (已修复) | 待执行 |
| 4. 音频工具 | 70% | ⚠️ 部分 | ✅ (已修复) | 待执行 |
| 5. AI 音效 | 70% | ⚠️ 部分 | ✅ (已修复) | 待执行 |
| 6. 处理结果 | 80% | ✅ 可用 | N/A | 待执行 |
| 7. 视频增强 | 15% | ❌ | N/A | 待执行 |
| 8. 模板管理 | 0% | ❌ | N/A | 待执行 |
| 9. AI 推荐 | 25% | ⚠️ | N/A | 待执行 |

---

## 6. 已修复 Bug 清单 (Phase 1-5)

### 6.1 阻断级修复 (CRITICAL)

| ID | 描述 | 修复方案 | 验证 |
|----|------|----------|:----:|
| C1 | `STATE.outDir` 竞态条件 | `STATE.ready` 移入异步计数器 `_markInitDone()` | ✅ |
| — | `setButtonLoading` 文本永久丢失 | 先保存 `data-original` 再修改 `textContent` | ✅ |
| — | `AEStudioKit` var 阴影 (Bridge IIFE) | 使用 `$.global.AEStudioKit` 访问全局 | ✅ |

### 6.2 高优先级修复 (HIGH)

| ID | 描述 | 修复方案 | 验证 |
|----|------|----------|:----:|
| H2 | Tab 4 音频工具缺异步轮询 | 四层异步改造 (server/bridge/host/client) | ✅ |
| H4 | `confirm()` CEP 74 不可用 | `showConfirm()` 自定义模态 | ✅ |
| — | 结果标准化掩盖 `success:false` | 检查 `'success' in result` → 保持原样 | ✅ |
| — | `aeCall` TypeError on 非字符串 | `typeof trimmed === 'string'` 守卫 | ✅ |
| — | `_logWarn` 在 catch 前未定义 | 移至 `index.jsx` 顶部 (模块加载前) | ✅ |
| — | F5 JSON 前导空白解析失败 | `replace(/^\s+/, '').replace(/\s+$/, '')` | ✅ |

### 6.3 阶段专项修复

| Phase | 修复数 | 关键修复 |
|-------|--------|----------|
| Phase 1 | N/A | 分析阶段 — 识别 37 反模式 |
| Phase 2 | 11 | 3 共享模块 + 8 异步化 + `setInterval` 泄漏 |
| Phase 3 | 7 | Bridge 阴影 + 结果标准化 + setButtonLoading + aeCall |
| Phase 4 | 6 | 路径硬编码 ×3 + 输出目录 ×13 + 端口集中化 |
| **Phase 5** | **N/A** | **测试规格 + 交付文档** |

---

## 7. 已知问题 (交付时)

### 7.1 仍待修复

| ID | 严重性 | 描述 | 影响范围 | 计划 |
|----|--------|------|----------|------|
| M1 | 🟡 MEDIUM | join 命令文件句柄泄漏 (`ae_bridge.py:408`) | Tab 4 多次拼接 | 后续维护 |
| M2 | 🟡 MEDIUM | README 声称 "Two models" — 实际 6 模型 9 标签 | 文档 | 后续更新 |
| M3 | 🟡 MEDIUM | 版本号不一致 (UI v5.0 / 代码 v4.0) | 品牌 | 架构决策后统一 |
| M4 | 🟡 MEDIUM | 云端分离硬编码 `.wav` 扩展名 | Tab 1 非 WAV 格式 | 后续维护 |
| L1-L7 | 🟢 LOW | 代码异味/死代码/空目录 | 各模块 | 代码清理阶段 |

### 7.2 功能缺口

| 功能 | 完成度 | 说明 |
|------|--------|------|
| Tab 7 视频增强 | 15% | 仅 Topaz 检测 — 无增强动作 |
| Tab 8 模板管理 | 0% | Tab 2 复制品 — 无独立功能 |
| Tab 9 AI 推荐 | 25% | 仅客户端关键词 — 未调用 NLP 服务端 |
| sound_api / tts_api | 0% | 代码存在但 CEP 面板未对接 |
| vocalremover.org 集成 | 0% | 第三分离引擎 — 计划中 |

---

## 8. 后续路线图

### 8.1 短期 (P1 — 1-2 周)

1. 执行 Phase 5 测试规格 — 57 项 P0 + 66 项 P1 + 28 项 P2
2. 修复测试中发现的 bug
3. 删除 ~204 MB 可安全删除的文件
4. 更新 README 反映最新状态 (6 模型, 9 标签, 双面板)

### 8.2 中期 (P2 — 1-2 月)

5. 补全 Tab 7 视频增强 (迁移 AE-MotionStudio Real-ESRGAN)
6. Tab 9 对接服务端 `ai_recommender.py` (NLP 推荐)
7. 合并 Tab 8 到 Tab 2 或赋予独立功能
8. 决策: v4.0 继续 vs 迁移到 AE-MotionStudio

### 8.3 长期 (P3 — 3-6 月)

9. 集成 vocalremover.org 作为第三分离引擎
10. 修复 LookAE Cloudflare 拦截 (在线抓取)
11. 自动清理 `server/output/` + `server/temp/` 策略
12. 对接 Freesound + 百度 TTS 到 CEP 面板
13. 跨平台支持 (macOS 测试 + 部署)

---

## 9. 快速参考

### 9.1 关键路径

| 组件 | 路径 |
|------|------|
| 项目根 | `ae-vocal-remover/` |
| CEP 清单 | `CSXS/manifest.xml` |
| 生产面板 | `client/index.html` → `client/app.js` |
| Studio Kit 面板 | `client/studio-kit/index.html` → `studio-kit.js` |
| ExtendScript 入口 | `host/index.jsx` |
| 核心路由器 | `host/main.jsx` → `cepDispatch()` |
| Bridge | `host/studio-kit-bridge.jsx` → `studioKitDispatch()` |
| Python 桥接 | `server/ae_bridge.py` (16 子命令) |
| Python 服务 | `server/server.py` (FastAPI :8765) |

### 9.2 关键端口

| 服务 | 端口 | 配置源 |
|------|------|--------|
| v4.0 FastAPI | 8765 | `server/config.py` → `SERVER_PORT` |
| AE-MotionStudio Flask | 54321 | `AE-MotionStudio/server/config.py` |

### 9.3 调试命令

```batch
:: CEP 调试模式
REG QUERY "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode

:: Python 检测
python --version
python -c "import sys; print(sys.executable)"

:: FFmpeg 检测
ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe -version

:: GPU 服务器健康检查
curl http://127.0.0.1:8765/health

:: 列出已安装 CEP 扩展
dir "%APPDATA%\Adobe\CEP\extensions\"

:: Studio Kit Bridge 日志
:: AE → 首选项 → 脚本和表达式 → 启用日志
:: 或: ExtendScript Toolkit CC → 粘贴 host/index.jsx → 运行
```

### 9.4 常用 API (AEStudioKit.dispatch)

| action | 说明 | 参数 |
|--------|------|------|
| `studioKit` | Studio Kit 面板调度 | `{module:'F1-F8', action:'...', params:{}}` |
| `init` | 初始化环境 | — |
| `status` | 全状态查询 | — |
| `getConfig` | 运行时配置 | — |
| `submit` | 异步提交分离任务 | `{audioPath, mode, model}` |
| `check` | 轮询任务状态 | `{jobId}` |
| `download` | 下载结果 | `{jobId, stem, outputPath}` |
| `applyTextPreset` | 应用文字预设 | `{presetId, duration, intensity}` |

---

> **交付包完成。** 本项目已通过 5 阶段企业级升级流程，从遗产代码分析到测试规格制定。
>
> **下一步**: 执行 Phase 5 测试规格，修复发现的问题，进入持续维护周期。
>
> **相关文档索引**:
> - [测试规格说明书](PHASE5_TEST_SPEC.md) — 151 项测试用例
> - [Phase 1 主报告](../phase1/PHASE1_MAIN_REPORT.md)
> - [Phase 2 优化计划](../phase2/PHASE2_OPTIMIZATION_PLAN.md)
> - [Phase 3 架构设计](../phase3/PHASE3_ARCHITECTURE.md)
> - [Phase 4 规范化报告](../phase4/PHASE4_REPORT.md)
> - [审计报告](../../AUDIT_REPORT.md)
> - [项目开发指南](../../.claude/CLAUDE.md)

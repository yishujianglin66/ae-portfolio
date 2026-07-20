# AE-Knowledge-Vault 多软件集成环境部署指南 v2.0

> 适用版本：ae_agent_pipeline.py v2.0 | 更新日期：2026-07-14
> 项目根目录：`c:\Users\Administrator\Desktop\AE-Knowledge-Vault\`

本指南覆盖 AE-Knowledge-Vault v2.0 已集成的全部软件的安装与部署，包括 Adobe 全家桶（AE/PR/PS/AME）、DaVinci Resolve、Silhouette 2026、Topaz Video AI、Blender、FFmpeg 以及 RunwayML/Pika 云端 API。

---

## 一、系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10 22H2 (x64) | Windows 11 23H2+ (x64) |
| Python | 3.10 | 3.11.x（生产）/ 3.12（开发预研） |
| CPU | 8 核 x86_64 | 16 核以上 |
| 内存 | 16 GB | 32 GB 或更高 |
| GPU | NVIDIA 8 GB VRAM | NVIDIA 16 GB VRAM（CUDA 12.x） |
| 磁盘空间 | 60 GB（含全部软件） | 200 GB SSD（含素材缓存） |

---

## 二、Adobe 全家桶部署

### 2.1 Adobe After Effects 2026（主合成引擎）

| 属性 | 说明 |
|------|------|
| 版本要求 | 26.x（2026 版） |
| 安装位置 | `D:\AE\Adobe After Effects 2026\` |
| 可执行文件 | `Support Files\AfterFX.exe` |
| 角色定位 | 主合成引擎，ExtendScript 桥接宿主，MCP 命令执行端 |

**环境变量配置**：

- `core/config.py` 默认路径：`C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe`
- 实际安装于 D 盘时，需在 `config.json` 或环境变量中覆盖：
  ```json
  { "ae": { "install_path": "D:\\AE\\Adobe After Effects 2026\\Support Files\\AfterFX.exe" } }
  ```
- 环境变量覆盖：`AEKV_AE_INSTALL_PATH=D:\AE\Adobe After Effects 2026\Support Files\AfterFX.exe`

**验证方法**：

```powershell
# 检查可执行文件存在
Test-Path "D:\AE\Adobe After Effects 2026\Support Files\AfterFX.exe"

# 命令行启动 AE（无界面）
& "D:\AE\Adobe After Effects 2026\Support Files\AfterFX.exe" -r "ae_mcp_bg_listener.jsx"
```

### 2.2 Adobe Premiere Pro 2026（剪辑）

| 属性 | 说明 |
|------|------|
| 版本要求 | 26.x（2026 版） |
| 安装位置 | 与 AE 同目录策略，默认 `C:\Program Files\Adobe\Adobe Premiere Pro 2026\` |
| 角色定位 | 时间线剪辑、转场、音频同步、多机位组装 |

**集成方式**：通过 `adobe_suite_integration.py` 的 `PremiereConfig` 调用，支持 `timeline_assemble`、`add_transitions`、`audio_sync`、`multi_cam` 四种操作类型。

**验证方法**：

```powershell
Test-Path "C:\Program Files\Adobe\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe"
```

### 2.3 Adobe Photoshop 2026（图像处理）

| 属性 | 说明 |
|------|------|
| 版本要求 | 27.x（2026 版） |
| 安装位置 | 默认 `C:\Program Files\Adobe\Adobe Photoshop 2026\` |
| 角色定位 | 材质纹理生成（木质/陶瓷/布偶）、帧处理、遮罩绘制、批量导出 |

**集成方式**：通过 `PhotoshopConfig` 调用，支持 `texture_gen`、`frame_process`、`matte_paint`、`batch_export` 四种操作。木偶视频化场景中负责生成木质/陶瓷/布偶材质纹理。

**验证方法**：

```powershell
Test-Path "C:\Program Files\Adobe\Adobe Photoshop 2026\Photoshop.exe"
```

### 2.4 Adobe Media Encoder 2026（批量渲染）

| 属性 | 说明 |
|------|------|
| 版本要求 | 26.x（2026 版） |
| 安装位置 | 默认 `C:\Program Files\Adobe\Adobe Media Encoder 2026\` |
| 角色定位 | 批量渲染、格式转换、监视文件夹自动化输出 |

**验证方法**：

```powershell
Test-Path "C:\Program Files\Adobe\Adobe Media Encoder 2026\Adobe Media Encoder.exe"
```

---

## 三、DaVinci Resolve 部署（调色）

| 属性 | 说明 |
|------|------|
| 版本要求 | Resolve 19.x 或 Studio 版 |
| 安装位置 | `D:\DaVinci Resolve\` |
| 可执行文件 | `Resolve.exe` |
| 角色定位 | 专业调色（节点式调色流程）、LUT 应用、批量调色 |

**环境变量配置**：

- `davinci_resolve_integration.py` 默认路径：`D:\DaVinci Resolve`
- 环境变量覆盖：`RESOLVE_HOME=D:\DaVinci Resolve`
- 支持的调色节点类型：`primary`、`secondary`、`qualifier`、`power_window`、`lut`、`vignette`、`blur`、`mixer`

**输出格式支持**：mp4、mov、prores422hq、prores422、prores4444、dnxhr（mxf）、dpx、exr

**验证方法**：

```powershell
Test-Path "D:\DaVinci Resolve\Resolve.exe"

# 检查 Python API 模块（DaVinciResolveScript）
python -c "import DaVinciResolveScript; print('Resolve API 可用')"
```

---

## 四、Silhouette 2026 部署（遮罩抠像）

| 属性 | 说明 |
|------|------|
| 版本要求 | 2026.0.2（发布日期 2026-06-15） |
| 安装位置 | `C:\Program Files\BorisFX\Silhouette 2026.0\` |
| 安装大小 | 11.28 GB |
| 可执行文件 | `Silhouette.exe` |
| 内置 Python | `resources\python\python.exe` |
| 角色定位 | 遮罩抠像、AI Roto 2.0、AI Paint 2.0、平面跟踪、画面修复 |

**环境变量配置**：

- `core/config.py` 默认配置：
  ```python
  "silhouette": {
      "install_path": r"C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe",
      "python_path": r"C:\Program Files\BorisFX\Silhouette 2026.0\resources\python\python.exe",
      "output_dir": "./silhouette_output",
      "max_retries": 3,
      "retry_delay_ms": 3000,
      "timeout_ms": 120000
  }
  ```
- 支持的最大分辨率：12K（2026 版提升 50%）
- GPU 显存利用：最高 16 GB

**验证方法**：

```powershell
Test-Path "C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe"

# 检查内置 Python
Test-Path "C:\Program Files\BorisFX\Silhouette 2026.0\resources\python\python.exe"
```

---

## 五、Topaz Video AI 部署（视频增强）

| 属性 | 说明 |
|------|------|
| 版本要求 | 4.x |
| 安装位置 | `C:\Program Files\Topaz Labs LLC\Topaz Video AI\`（任务指定 `D:\Topaz Video AI\`） |
| CLI 工具 | `topazcli.exe` 或 `Topaz Video AI.exe --cli` |
| 角色定位 | 视频超分辨率放大、帧率插值补帧、AI 降噪、智能锐化、防抖稳定化 |

**环境变量配置**：

- 默认路径：`C:\Program Files\Topaz Labs LLC\Topaz Video AI`
- 环境变量覆盖：`TOPAZ_HOME=D:\Topaz Video AI`
- 输出目录：`AE_WORK_DIR\topaz_output`（默认 `D:\AE-Work\topaz_output`）

**支持功能与预设**：

| 功能 | 说明 |
|------|------|
| `upscale` | 超分辨率放大（2x / 4x） |
| `interpolate` | 帧率插值补帧（24fps → 60fps） |
| `denoise` | AI 降噪 |
| `sharpen` | 智能锐化 |
| `stabilize` | 视频防抖稳定化 |

**验证方法**：

```powershell
# 检查 CLI 工具
Test-Path "D:\Topaz Video AI\topazcli.exe"

# 命令行验证（如使用默认路径）
& "C:\Program Files\Topaz Labs LLC\Topaz Video AI\topazcli.exe" --help
```

---

## 六、Blender 部署（3D 建模渲染）

| 属性 | 说明 |
|------|------|
| 版本要求 | 4.2 LTS 或更高 |
| 安装位置 | `C:\Program Files\Blender Foundation\Blender 4.2\` |
| 可执行文件 | `blender.exe` / `blender-launcher.exe` |
| 角色定位 | 3D 场景生成、材质纹理、灯光布置、关键帧动画、Python 自动化渲染 |

**环境变量配置**：

- 默认路径：`C:\Program Files\Blender Foundation\Blender 4.2`
- 环境变量覆盖：`BLENDER_HOME=C:\Program Files\Blender Foundation\Blender 4.2`
- 输出目录：`AE_WORK_DIR\blender_output`（默认 `D:\AE-Work\blender_output`）

**渲染引擎支持**：

| 引擎 | 说明 |
|------|------|
| `eevee` | 实时渲染引擎（默认，速度快） |
| `cycles` | 物理光线追踪引擎（高质量，支持 GPU） |
| `workbench` | 工作台预览渲染 |

**集成方式**：通过 `blender --python script.py` 命令行执行 Python 脚本，支持 `scene_generation`、`material_setup`、`lighting_setup`、`animation`、`rendering` 五种操作。

**验证方法**：

```powershell
Test-Path "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"

# 验证 Python API
& "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" --python-expr "import bpy; print(bpy.app.version_string)"
```

---

## 七、FFmpeg 部署（命令行工具）

| 属性 | 说明 |
|------|------|
| 版本要求 | 6.x 或更高 |
| 安装位置 | `D:\ffmpeg\bin\` |
| 可执行文件 | `ffmpeg.exe`、`ffprobe.exe`、`ffplay.exe` |
| 角色定位 | 素材预处理、格式转换、视频帧提取、流媒体处理 |

**环境变量配置**：

```powershell
# 将 FFmpeg 加入系统 PATH
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";D:\ffmpeg\bin", "User")
```

或在 `.env` 中配置代理后通过 `ffmpeg-python` 库调用（`media_preprocessor.py` 模块）。

**验证方法**：

```powershell
# 检查可执行文件
Test-Path "D:\ffmpeg\bin\ffmpeg.exe"

# 验证版本
ffmpeg -version

# 验证 ffprobe
ffprobe -version
```

---

## 八、RunwayML / Pika 云端 API 部署

### 8.1 RunwayML API

| 属性 | 说明 |
|------|------|
| 模型 | Gen-2 / Gen-3 Alpha |
| API 端点 | `https://api.runwayml.com/v1` |
| 认证方式 | Bearer Token（`RUNWAY_API_KEY`） |
| 角色定位 | AI 文生视频、图生视频 |

**环境变量配置**：

```bash
# .env 文件
RUNWAY_API_KEY=your_runway_api_key_here
```

**支持生成类型**：`text_to_video`、`image_to_video`

### 8.2 Pika API

| 属性 | 说明 |
|------|------|
| 模型 | Pika 1.0 |
| API 端点 | `https://api.pika.art/v1` |
| 认证方式 | Bearer Token（`PIKA_API_KEY`） |
| 角色定位 | AI 文生视频、图生视频、视频延伸 |

**环境变量配置**：

```bash
# .env 文件
PIKA_API_KEY=your_pika_api_key_here
```

**支持生成类型**：`text_to_video`、`image_to_video`、`video_extend`（Pika 专属）

### 8.3 通用配置

- 支持宽高比：`16:9`、`9:16`、`1:1`、`4:5`
- 默认输出目录：`AE_WORK_DIR\ai_video_output`（`D:\AE-Work\ai_video_output`）
- 执行模式：`real`（真实 API 调用）、`simulate`（模拟）、`auto`（自动降级）

**验证方法**：

```python
# Python 验证 API Key 已配置
import os
print("RunwayML:", "已配置" if os.environ.get("RUNWAY_API_KEY") else "未配置")
print("Pika:", "已配置" if os.environ.get("PIKA_API_KEY") else "未配置")
```

---

## 九、Python 环境与依赖

### 9.1 Python 版本

- **生产环境**：Python 3.11.x（比 3.10 快 25%，生态稳定）
- **开发预研**：Python 3.12
- 最低要求：Python 3.10（`pyproject.toml` 中 `requires-python = ">=3.10"`）

### 9.2 依赖安装

```bash
# 安装核心依赖
pip install -e .

# 安装全部可选依赖（推荐）
pip install -e ".[all]"

# 分组安装
pip install -e ".[audio,vision,video,ai,download,web]"
```

### 9.3 核心依赖清单

| 分组 | 包 | 用途 |
|------|-----|------|
| 核心 | `numpy>=1.24,<2.0` | 数值计算基础 |
| 核心 | `Pillow>=10.0` | 图像处理 |
| 核心 | `pydantic>=2.0` | 数据验证 |
| audio | `librosa>=0.10` | 音频分析（BPM/节拍/情绪） |
| audio | `soundfile>=0.12` | 音频 I/O |
| vision | `opencv-python>=4.8` | 视频帧提取/CV 处理 |
| vision | `scenedetect[opencv]>=0.6.4` | 场景分割检测 |
| video | `ffmpeg-python>=0.2` | FFmpeg Python 封装 |
| video | `moviepy>=1.0` | 视频编辑 |
| ai | `openai>=1.0` | LLM 网关（OpenAI 兼容） |
| ai | `scikit-learn>=1.3` | 机器学习 |
| download | `yt-dlp>=2024.0` | 视频素材下载 |
| download | `requests>=2.31` | HTTP 请求 |
| web | `fastapi>=0.104` | Web Dashboard |
| web | `uvicorn[standard]>=0.24` | ASGI 服务器 |
| web | `websockets>=12.0` | WebSocket 通信 |

### 9.4 额外依赖（按需安装）

| 包 | 用途 | 对应模块 |
|-----|------|---------|
| `mediapipe` | 手势/姿态/面部跟踪 | `mediapipe_integration.py` |
| `torch` + `transformers` | CLIP 语义搜索 | `13-素材获取与搜索/03-AI语义搜索/` |
| `DaVinciResolveScript` | DaVinci Resolve API | `davinci_resolve_integration.py` |

---

## 十、.env 配置文件说明

项目根目录提供 `.env.example` 模板，复制为 `.env` 后填入实际值。`.env` 已在 `.gitignore` 中，不会被提交。

### 10.1 配置项分类

| 分类 | 关键变量 | 说明 |
|------|---------|------|
| 环境配置 | `AEK_ENVIRONMENT` | `development` / `test` / `production` |
| 路径配置 | `AEK_VIDEO_LIBRARY` | 视频素材库路径（可选，覆盖默认） |
| 路径配置 | `AEK_AUDIO_LIBRARY` | 音频素材库路径 |
| 路径配置 | `AEK_BGM_LIBRARY` | BGM 素材库路径 |
| 路径配置 | `AEK_DOWNLOAD_TEMP` | 临时下载目录 |
| 平台凭证 | `DOUYIN_COOKIE` / `DOUYIN_COOKIE_PATH` | 抖音素材下载 |
| 平台凭证 | `BILIBILI_COOKIE` | Bilibili 素材下载 |
| 平台凭证 | `YOUTUBE_API_KEY` | YouTube API |
| 平台凭证 | `PEXELS_API_KEY` / `PIXABAY_API_KEY` | 免费素材 API |
| 平台凭证 | `JAMENDO_CLIENT_ID` | Jamendo 音乐 API |
| AI 视频 | `RUNWAY_API_KEY` | RunwayML API |
| AI 视频 | `PIKA_API_KEY` | Pika API |
| MCP 安全 | `MCP_BRIDGE_SECRET` | MCP Bridge HMAC-SHA256 签名密钥 |
| LLM 网关 | `AEKV_LLM_BASE_URL` | OmniRoute / OpenAI 兼容端点 |
| LLM 网关 | `AEKV_LLM_API_KEY` | LLM API Key |
| LLM 网关 | `AEKV_LLM_MODEL` | 默认模型（`auto` 自动路由） |
| 代理 | `HTTP_PROXY` / `HTTPS_PROXY` | 网络代理（可选） |

### 10.2 MCP Bridge 密钥生成

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 十一、core/config.py 配置加载机制

`core/config.py` 实现了 `ConfigManager` 类，遵循 12-Factor App 配置原则，支持分层覆盖与类型安全。

### 11.1 配置来源优先级（从低到高）

1. **默认配置**（代码中 `_register_default_config()` 定义）
2. **项目配置文件** `./config.json`
3. **用户配置文件** `~/.ae-knowledge-vault/config.json`
4. **环境变量**（`AEKV_*` 前缀，自动转换为点路径，如 `AEKV_AE_INSTALL_PATH` → `ae.install_path`）
5. **命令行参数**

### 11.2 核心配置段

| 配置段 | 关键字段 | 说明 |
|--------|---------|------|
| `output` | `default_dir`、`tmp_dir` | 输出与临时目录 |
| `ae` | `install_path`、`script_dir`、`max_retries`、`timeout_ms` | AE 安装路径与执行参数 |
| `silhouette` | `install_path`、`python_path`、`timeout_ms` | Silhouette 安装与执行参数 |
| `server` | `host`、`port`、`debug` | Web 服务配置 |
| `pipeline` | `max_concurrent_tasks`、`default_frame_rate`、`enable_silhouette_fallback` | 工作流配置 |
| `media_library` | `video_dir`、`audio_dir`、`image_dir`、`cache_size_gb` | 素材库配置 |
| `mcp_bridge` | `bridge_dir`、`timeout_seconds`、`signature_enabled`、`secret` | MCP Bridge 配置 |
| `model` | `nlu_model`、`api_key`、`base_url`、`default_model`、`routing` | LLM 网关配置 |
| `memory` | `enabled`、`db_path`、`min_confidence` | 持久化记忆系统 |

### 11.3 配置访问 API

```python
from core.config import get_config, get_str, get_int, get_bool, get_list

# 点路径访问
ae_path = get_str("ae.install_path")
timeout = get_int("ae.timeout_ms", 60000)
silhouette_fallback = get_bool("pipeline.enable_silhouette_fallback")

# 依赖检查
from core.config import check_dependencies
deps = check_dependencies()
# 返回: {"ae_installed": True, "silhouette_installed": True, ...}
```

### 11.4 热重载

```python
from core.config import config_manager
config_manager.reload()  # 运行时重新加载配置
```

---

## 十二、MCP 桥接部署

AE-Knowledge-Vault 通过 ExtendScript 桥接实现 Python ↔ AE 通信，采用文件轮询机制。

### 12.1 桥接组件

| 文件 | 作用 |
|------|------|
| `ae_mcp_bridge_v26.jsx` | AE 2026 专用桥接脚本（含 JSON polyfill、命令分发、HMAC 签名验证） |
| `ae_mcp_bg_listener.jsx` | 后台无 UI 监听器，通过 `AfterFX.exe -r` 启动 |

### 12.2 桥接目录

默认桥接目录：`C:/Users/Administrator/Documents/ae-mcp-bridge/`

文件结构：
```
ae-mcp-bridge/
├── ae_command.json    # Python → AE 命令文件
├── ae_mcp_result.json # AE → Python 结果文件
```

### 12.3 部署步骤

1. **创建桥接目录**：
   ```powershell
   New-Item -ItemType Directory -Force -Path "C:\Users\Administrator\Documents\ae-mcp-bridge"
   ```

2. **启动后台监听器**：
   ```powershell
   & "D:\AE\Adobe After Effects 2026\Support Files\AfterFX.exe" -r "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ae_mcp_bg_listener.jsx"
   ```

3. **配置签名验证（可选）**：
   - 在 `.env` 中设置 `MCP_BRIDGE_SECRET`
   - 在 `ae_mcp_bg_listener.jsx` 中设置 `SIGNATURE_ENABLED = true`

### 12.4 桥接配置（core/config.py）

```python
"mcp_bridge": {
    "bridge_dir": "./ae-mcp-bridge",
    "timeout_seconds": 300,
    "poll_interval_seconds": 1.0,
    "signature_enabled": False,
    "secret": ""
}
```

监听器默认轮询间隔：500ms（`CHECK_INTERVAL = 500`）

### 12.5 验证方法

```powershell
# 检查桥接目录与文件
Test-Path "C:\Users\Administrator\Documents\ae-mcp-bridge\ae_command.json"

# 检查 AE 进程是否在运行
Get-Process "AfterFX" -ErrorAction SilentlyContinue
```

---

## 十三、目录结构说明

```
c:\Users\Administrator\Desktop\AE-Knowledge-Vault\
├── ae_agent_pipeline.py          # v2.0 主管线（五层架构）
├── ae_mcp_bridge_v26.jsx         # AE 2026 MCP 桥接脚本
├── ae_mcp_bg_listener.jsx        # AE 后台监听器（无 UI）
├── topaz_integration.py          # Topaz Video AI 集成
├── davinci_resolve_integration.py# DaVinci Resolve 调色集成
├── blender_3d_integration.py     # Blender 3D 集成
├── ai_video_generator.py         # RunwayML/Pika AI 视频生成
├── adobe_suite_integration.py    # Adobe 全家桶集成（PS/PR/ME）
├── mediapipe_integration.py      # MediaPipe 人物识别
├── audio_analyzer_librosa.py     # Librosa 音频分析
├── media_preprocessor.py         # FFmpeg 素材预处理
├── core/
│   ├── config.py                 # ConfigManager 配置管理
│   ├── event_bus.py              # 事件总线
│   ├── state_machine.py          # 状态机
│   ├── observability.py          # 可观测性
│   ├── workflow_orchestrator.py  # 工作流编排器
│   ├── llm_gateway.py            # LLM 网关（OmniRoute 兼容）
│   └── memory_store.py           # 持久化记忆系统
├── config/                       # 配置文件目录
├── 08-安装与部署/                # 本目录
├── 10-风格化剪辑知识库/          # 软件功能完全指南
├── 13-素材获取与搜索/            # 素材下载与 AI 语义搜索
├── 14-Silhouette知识库/          # Silhouette 专项知识库
├── .env.example                  # 环境变量模板
├── .env                          # 环境变量（不入库）
├── pyproject.toml                # Python 项目配置
└── config.json                   # 项目配置文件（可选）
```

---

## 十四、快速验证清单

部署完成后，按以下清单逐项验证：

### 14.1 基础环境

- [ ] Python 3.11 已安装：`python --version`
- [ ] 核心依赖已安装：`pip install -e ".[all]"`
- [ ] `.env` 文件已创建：`Test-Path .env`
- [ ] `config.json` 配置正确（如覆盖了默认路径）

### 14.2 Adobe 全家桶

- [ ] AE 2026 可启动：`Test-Path "D:\AE\Adobe After Effects 2026\Support Files\AfterFX.exe"`
- [ ] PR 2026 已安装
- [ ] PS 2026 已安装
- [ ] AME 2026 已安装

### 14.3 专业软件

- [ ] DaVinci Resolve 可启动：`Test-Path "D:\DaVinci Resolve\Resolve.exe"`
- [ ] Silhouette 2026.0.2 已安装（11.28 GB）
- [ ] Topaz Video AI CLI 可用：`Test-Path "D:\Topaz Video AI\topazcli.exe"`
- [ ] Blender 可启动且 Python API 可用
- [ ] FFmpeg 已加入 PATH：`ffmpeg -version`

### 14.4 云端 API

- [ ] `RUNWAY_API_KEY` 已配置
- [ ] `PIKA_API_KEY` 已配置

### 14.5 MCP 桥接

- [ ] 桥接目录已创建：`Test-Path "C:\Users\Administrator\Documents\ae-mcp-bridge"`
- [ ] AE 后台监听器可启动
- [ ] Python → AE 命令可往返

### 14.6 集成验证

```python
# 运行依赖检查
from core.config import check_dependencies
deps = check_dependencies()
for k, v in deps.items():
    print(f"  {'✓' if v else '✗'} {k}")

# 启动主管线验证
from ae_agent_pipeline import AEAgentPipeline
pipeline = AEAgentPipeline()
print("Pipeline 初始化成功")
```

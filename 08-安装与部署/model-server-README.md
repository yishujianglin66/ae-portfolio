# AI 模型与外部 API 说明 v2.0

> 适用版本：ae_agent_pipeline.py v2.0 | 更新日期：2026-07-14
> 项目根目录：`c:\Users\Administrator\Desktop\AE-Knowledge-Vault\`

本文档说明 AE-Knowledge-Vault v2.0 集成的全部本地模型、云端 API、Python AI 库及 Adobe 集成接口的模型与资源路径配置。

---

## 一、本地模型

### 1.1 Topaz Video AI 模型

Topaz Video AI 通过 CLI（`topazcli.exe`）调用内置 AI 模型完成视频增强，模型随软件安装，无需单独下载。

**安装路径**：`C:\Program Files\Topaz Labs LLC\Topaz Video AI\`（或 `D:\Topaz Video AI\`，通过 `TOPAZ_HOME` 环境变量覆盖）

**集成模块**：`topaz_integration.py`（`TopazEnhancer` 类）

#### 核心模型与适用场景

| 模型 | 适用场景 | 说明 |
|------|---------|------|
| **Proteus** | 通用视频增强（默认） | 综合超分+降噪+锐化，适合大多数素材；代码默认模型 |
| **Artemis** | 高质量视频超分 | 适合低分辨率老视频/压缩损失严重的素材，细节恢复强 |
| **Gaia** | 高清/CG 素材超分 | 适合已较清晰的 CG/动画素材，2x/4x 放大保真度高 |
| **Theia** | 细节增强 | 适合纹理细节丰富的实拍素材 |
| **Protex** | 极限超分（8x） | 适合极端放大需求，需较高 GPU 算力 |
| **Iris** | 人脸增强 | 专注人脸区域修复与增强，适合人物特写镜头 |
| **Nyx** | 降噪专用 | 适合高 ISO 暗光素材，强力降噪保留细节 |
| **AHD** | 去隔行 | 适合老式隔行扫描素材（DV/广播录像） |
| **Chronos** | 帧插值补帧 | 24fps → 60fps 补帧，运动补偿 |
| **Stabilizer** | 防抖稳定化 | 画面抖动修正 |
| **Denoise** | 通用降噪 | 轻度降噪模型 |
| **Sharpen** | 智能锐化 | 细节边缘增强 |

#### 帧插值模型（补帧专用）

| 模型 | 质量 | 速度 | 说明 |
|------|------|------|------|
| RIFE v4 | 高 | 中 | 主流帧插值模型，运动补偿效果好 |
| DAIN v3 | 最高 | 慢 | 质量最佳但速度慢，适合精细处理 |
| CAIN v2 | 中 | 快 | 速度优先，适合快速预览 |
| Real-ESRGAN | 高 | 中 | 兼顾超分与补帧 |

#### 代码中的模型配置

```python
# topaz_integration.py
AVAILABLE_MODELS = [
    "proteus", "artemis", "gaia", "theia", "ahd",
    "chronos", "stabilizer", "denoise", "sharpen"
]

# TopazConfig 默认模型
@dataclass
class TopazConfig:
    model: str = "proteus"      # 默认使用 Proteus
    scale: float = 1.0           # 缩放倍数
    fps: int = 0                 # 补帧目标帧率（0=不补帧）
    denoise: float = 0.0         # 降噪强度（0.0-1.0）
    sharpen: float = 0.0         # 锐化强度（0.0-1.0）
```

#### 预设配置

| 预设名 | 模型 | 缩放 | 降噪 | 锐化 | 适用场景 |
|--------|------|------|------|------|---------|
| `default` | proteus | 1.0 | 0.3 | 0.2 | 均衡配置，轻度增强 |
| `quality_2x` | proteus | 2.0 | 0.5 | 0.3 | 2 倍超分，高质量 |
| `denoise_strong` | nyx | 1.0 | 0.8 | 0.1 | 强力降噪 |
| `upscale_4x` | gaia | 4.0 | 0.2 | 0.2 | 4 倍超分（CG/高清素材） |

---

### 1.2 Silhouette 2026 fx API

Silhouette 2026 提供内置的 Python fx API，用于遮罩抠像、AI Roto、AI Paint、跟踪等操作。

**关键约束**：fx API **必须在 Silhouette 内部 Script Editor 中运行**，不可从外部 Python 环境直接导入。外部集成通过 `silhouette_executor.py` 调用 Silhouette 的命令行接口执行脚本。

#### fx API 核心模块

```python
# 以下代码仅在 Silhouette 内部 Script Editor 中可用
from fx import *

# 访问当前项目与节点
project = activeProject()
session = activeSession()
node = activeNode()

# AI Roto 2.0（2026 新功能）
ai_roto = node.property("aiRoto")
ai_roto.setValue("model", "transformer_v2")   # transformer_v2 / mask_rcnn / fast
ai_roto.setValue("multiObject", True)
ai_roto.setValue("maxObjects", 20)
ai_roto.setValue("smallObjectBoost", True)

# AI Paint 2.0（扩散模型）
ai_paint = node.property("aiPaint")
ai_paint.setValue("mode", "diffusion")
ai_paint.setValue("textureSynthesis", True)
ai_paint.setValue("temporalCoherence", True)
```

#### 2026 版 AI 模型架构

| 功能 | 模型架构 | 精度 | 速度 |
|------|---------|------|------|
| AI Roto 2.0 | Transformer + CNN 混合 | IoU 0.92 | 0.8s/帧 |
| AI Paint 2.0 | Diffusion 扩散模型 | 帧间一致性 +40% | - |
| AI 边缘细化 | U-Net++ | - | - |

#### 外部集成方式

```python
# ae_agent_pipeline.py 中的 Silhouette 执行器
from silhouette_executor import SilhouetteExecutor

# 通过命令行调用 Silhouette 执行内部脚本
executor = SilhouetteExecutor()
result = executor.execute_task(
    task_type="roto",
    input_path="input.mp4",
    output_dir="./silhouette_output"
)
```

**配置路径**（`core/config.py`）：
```python
"silhouette": {
    "install_path": r"C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe",
    "python_path": r"C:\Program Files\BorisFX\Silhouette 2026.0\resources\python\python.exe",
    "output_dir": "./silhouette_output",
    "timeout_ms": 120000
}
```

---

## 二、云端 API

### 2.1 RunwayML API

RunwayML 提供 Gen-2 / Gen-3 Alpha 视频生成模型，通过 REST API 调用。

**集成模块**：`ai_video_generator.py`（`AIVideoGenerator` 类）

| 属性 | 说明 |
|------|------|
| API 端点 | `https://api.runwayml.com/v1` |
| 认证方式 | Bearer Token |
| 环境变量 | `RUNWAY_API_KEY` |
| 模型 | Gen-2 / Gen-3 Alpha |
| 计费 | 按生成时长计费（credits 制），不同分辨率/时长消耗不同 credits |

#### 认证方式

```python
import requests

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}
```

#### 核心端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/generate/text-to-video` | POST | 文生视频 |
| `/generate/image-to-video` | POST | 图生视频 |
| `/jobs/{job_id}` | GET | 查询任务状态 |
| `/jobs/{job_id}/download` | GET | 下载生成结果 |

#### 请求示例

```python
# 文生视频
payload = {
    'prompt': 'A wooden puppet theater stage, cinematic lighting',
    'duration': 4,           # 秒
    'resolution': '1080p',
    'model': 'gen-3'         # Gen-3 Alpha
}
response = requests.post(
    'https://api.runwayml.com/v1/generate/text-to-video',
    headers=headers,
    json=payload
)
```

#### 支持参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `prompt` | str | 文本提示词 |
| `negative_prompt` | str | 负面提示词 |
| `duration` | float | 视频时长（秒，默认 4.0） |
| `fps` | int | 帧率（默认 24） |
| `width` / `height` | int | 分辨率（默认 1024x576） |
| `aspect_ratio` | str | 宽高比：`16:9` / `9:16` / `1:1` / `4:5` |
| `motion_bucket` | int | 运动强度（1-255，默认 127） |
| `seed` | int | 随机种子（-1=随机） |

---

### 2.2 Pika API

Pika 提供 Pika 1.0 视频生成模型，支持视频延伸功能。

**集成模块**：`ai_video_generator.py`（`AIVideoGenerator` 类）

| 属性 | 说明 |
|------|------|
| API 端点 | `https://api.pika.art/v1` |
| 认证方式 | Bearer Token |
| 环境变量 | `PIKA_API_KEY` |
| 模型 | Pika 1.0 |

#### 核心端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/generate/text-to-video` | POST | 文生视频 |
| `/generate/image-to-video` | POST | 图生视频 |
| `/generate/video-extend` | POST | 视频延伸（Pika 专属） |
| `/tasks/{task_id}` | GET | 查询任务状态 |

#### 生成类型

| 类型 | 说明 | RunwayML | Pika |
|------|------|---------|------|
| `text_to_video` | 文生视频 | ✓ | ✓ |
| `image_to_video` | 图生视频 | ✓ | ✓ |
| `video_extend` | 视频延伸 | ✗ | ✓（专属） |

---

### 2.3 云端 API 通用配置

```python
# ai_video_generator.py
RUNWAY_API_KEY = os.environ.get("RUNWAY_API_KEY", "")
PIKA_API_KEY = os.environ.get("PIKA_API_KEY", "")

RUNWAY_API_BASE = "https://api.runwayml.com/v1"
PIKA_API_BASE = "https://api.pika.art/v1"

# 执行模式
# - real: 真实 API 调用（需要 API Key）
# - simulate: 模拟执行（用于测试）
# - auto: 优先 real，失败降级为 simulate
```

#### 预设风格

| 提供商 | 预设名 | 风格说明 |
|--------|--------|---------|
| runway | `cinematic` | 电影级风格，胶片质感，浅景深 |
| runway | `anime` | 动漫风格，吉卜力风格，鲜艳色彩 |
| pika | `cinematic` | 电影级风格 |
| pika | `anime` | 动漫风格 |

---

## 三、Python AI 库

### 3.1 Librosa（音频分析）

| 属性 | 说明 |
|------|------|
| 包名 | `librosa>=0.10` |
| 依赖分组 | `audio` |
| 集成模块 | `audio_analyzer_librosa.py`（`LibrosaAudioAnalyzer` 类） |
| 用途 | BPM 检测、节拍网格、强拍位置、频谱分析、情绪识别 |

#### 核心能力

| 功能 | 说明 |
|------|------|
| 节奏分析 | BPM 检测、节拍网格、强拍位置、速度曲线 |
| 结构分割 | 段落边界检测、段落类型分类 |
| 能量分析 | RMS 曲线、峰值爆发点、动态范围 |
| 频谱分析 | 6 频段分解、频谱质心/通量/rolloff、色度 |
| 情绪识别 | Valence-Arousal 值、调式判断（大小调） |

#### 使用示例

```python
from audio_analyzer_librosa import LibrosaAudioAnalyzer

analyzer = LibrosaAudioAnalyzer(enable_cache=False)
result = analyzer.analyze("music.mp3")
# result 包含: bpm, beats, downbeats, rms, spectral_centroid, mood, key...
```

---

### 3.2 MediaPipe（手势/姿态/面部跟踪）

| 属性 | 说明 |
|------|------|
| 包名 | `mediapipe` |
| 集成模块 | `mediapipe_integration.py`（`MediaPipeIntegrator` 类） |
| 用途 | 人物检测、姿态估计、面部跟踪、手势识别 |

#### 配置参数

```python
from mediapipe_integration import MediaPipeIntegrator, MediaPipeConfig

integrator = MediaPipeIntegrator(
    MediaPipeConfig(
        mode="auto",              # auto / real / simulate
        detect_pose=True,         # 姿态估计
        detect_face=True,         # 面部跟踪
        detect_hands=False,       # 手势识别
        confidence_threshold=0.5, # 置信度阈值
        max_num_persons=1,        # 最大检测人数
        sample_interval=5,        # 采样间隔（帧）
    )
)
```

#### 应用场景

- **木偶风格化**：`PuppetAutoProcessor` 依赖 MediaPipe 检测人物姿态，驱动木偶化效果
- **片段分析**：感知层（Layer 1）提取人物运动特征

---

### 3.3 CLIP（语义搜索）

| 属性 | 说明 |
|------|------|
| 包名 | `torch` + `transformers`（CLIP 模型） |
| 集成路径 | `13-素材获取与搜索/03-AI语义搜索/` |
| 用途 | 语义搜索、向量索引、智能素材匹配 |

#### 核心模块

| 文件 | 作用 |
|------|------|
| `clip_indexer.py` | 视频帧向量化索引构建 |
| `clip_searcher.py` | 语义搜索查询 |
| `frame_extractor.py` | 视频帧提取（配合 OpenCV） |
| `hybrid_retriever.py` | 混合检索（语义+关键词） |
| `vector_store.py` | 向量存储 |
| `smart_matcher.py` | 智能匹配器 |
| `smart_ranker.py` | 智能排序器 |

#### 工作流程

```
视频素材 → frame_extractor 提取关键帧 → clip_indexer 生成向量 → vector_store 存储
                                                                    ↓
用户查询 → clip_searcher 语义检索 → smart_ranker 排序 → hybrid_retriever 混合召回 → 匹配结果
```

---

### 3.4 OpenCV（视频帧提取）

| 属性 | 说明 |
|------|------|
| 包名 | `opencv-python>=4.8` |
| 依赖分组 | `vision` |
| 用途 | 视频帧提取、CV 处理、光流分析、场景检测 |

#### 核心能力

| 功能 | 说明 |
|------|------|
| 视频帧提取 | 按间隔/时间点提取帧 |
| 光流分析 | Horn-Schunck / Lucas-Kanade 运动估计 |
| 场景检测 | 配合 `scenedetect` 实现场景分割 |
| 色彩分析 | 颜色空间转换、主色板提取 |
| 构图分析 | 三分法、对称性、景深判断 |

#### 集成模块

- `scene_detector.py`：场景分割检测（配合 `scenedetect[opencv]`）
- `13-素材获取与搜索/03-AI语义搜索/frame_extractor.py`：帧提取

---

## 四、Adobe 集成

### 4.1 AE ExtendScript 桥接

AE 集成**无需独立模型**，通过 ExtendScript 桥接实现 Python ↔ AE 通信。

**桥接组件**：

| 文件 | 作用 |
|------|------|
| `ae_mcp_bridge_v26.jsx` | AE 2026 专用桥接脚本（JSON polyfill + 命令分发 + HMAC 签名） |
| `ae_mcp_bg_listener.jsx` | 后台无 UI 监听器 |

**通信机制**：文件轮询（Python 写入 `ae_command.json` → AE 监听器读取并执行 → 结果写入 `ae_mcp_result.json`）

**桥接目录**：`C:/Users/Administrator/Documents/ae-mcp-bridge/`

**轮询间隔**：500ms

**签名验证**：可选 HMAC-SHA256（通过 `MCP_BRIDGE_SECRET` 配置）

---

### 4.2 DaVinci Resolve 脚本 API

DaVinci Resolve 提供官方 Python API（`DaVinciResolveScript` 模块）用于调色自动化。

**集成模块**：`davinci_resolve_integration.py`（`DavinciColorist` 类）

| 属性 | 说明 |
|------|------|
| API 模块 | `DaVinciResolveScript`（随 Resolve 安装） |
| 安装路径 | `D:\DaVinci Resolve\` |
| 环境变量 | `RESOLVE_HOME` |
| 角色定位 | 节点式调色、LUT 应用、批量调色、.drx 预设导出 |

#### 调色节点类型

| 节点类型 | 说明 |
|---------|------|
| `primary` | 一级调色（lift/gamma/gain/saturation/contrast） |
| `secondary` | 二级调色 |
| `qualifier` | 限定器（色相/亮度/饱和度抠像） |
| `power_window` | Power Window 遮罩 |
| `lut` | LUT 应用 |
| `vignette` | 暗角 |
| `blur` | 模糊 |
| `mixer` | 混合器 |

#### 配置示例

```python
from davinci_resolve_integration import DavinciColorist, create_config_from_preset

colorist = DavinciColorist()
config = create_config_from_preset("cinematic")
result = colorist.color_grade(
    input_path="input.mp4",
    output_path="graded.mp4",
    config=config
)
```

---

## 五、模型/资源路径配置

### 5.1 core/config.py 配置段

`core/config.py` 的 `ConfigManager` 统一管理所有模型与资源路径：

```python
# 模型配置段（LLM 网关）
"model": {
    "nlu_model": "local",          # local=纯正则, llm=LLM增强, hybrid=混合
    "max_tokens": 4096,
    "temperature": 0.7,
    "api_key": "",                 # AEKV_LLM_API_KEY 或 OPENAI_API_KEY
    "base_url": "",                # OmniRoute 或 OpenAI 兼容端点
    "default_model": "auto",       # auto 让网关自动路由
    "timeout_seconds": 30,
    "max_retries": 3,
    "enable_compression": True,    # Caveman token 压缩
    "enable_fallback": True,       # Provider 降级
    "fallback_providers": [],      # 降级 Provider 列表
    "routing": {                   # 任务→模型路由表
        "intent_classification": "auto",
        "scene_description": "auto",
        "effect_planning": "auto",
        "quality_review": "auto",
        "feedback_analysis": "auto",
        "general": "auto",
    }
}

# 记忆系统配置段
"memory": {
    "enabled": True,
    "db_path": "",                 # 空=默认 ~/.ae-knowledge-vault/memory.db
    "min_confidence": 0.3,         # 经验推荐最低置信度
}

# 素材库配置段
"media_library": {
    "video_dir": "./video素材库",
    "audio_dir": "./音频素材库",
    "image_dir": "./图片素材库",
    "cache_enabled": True,
    "cache_size_gb": 10
}

# MCP Bridge 配置段
"mcp_bridge": {
    "bridge_dir": "./ae-mcp-bridge",
    "timeout_seconds": 300,
    "poll_interval_seconds": 1.0,
    "signature_enabled": False,
    "secret": ""
}
```

### 5.2 环境变量与路径映射

| 环境变量 | 配置路径 | 说明 |
|---------|---------|------|
| `TOPAZ_HOME` | topaz_integration.py | Topaz Video AI 安装路径 |
| `BLENDER_HOME` | blender_3d_integration.py | Blender 安装路径 |
| `RESOLVE_HOME` | davinci_resolve_integration.py | DaVinci Resolve 安装路径 |
| `AE_WORK_DIR` | 多模块共享 | 输出根目录（默认 `D:\AE-Work`） |
| `RUNWAY_API_KEY` | ai_video_generator.py | RunwayML API Key |
| `PIKA_API_KEY` | ai_video_generator.py | Pika API Key |
| `AEKV_LLM_BASE_URL` | core/config.py → model.base_url | LLM 网关端点 |
| `AEKV_LLM_API_KEY` | core/config.py → model.api_key | LLM API Key |
| `MCP_BRIDGE_SECRET` | core/config.py → mcp_bridge.secret | MCP Bridge 签名密钥 |

### 5.3 输出目录结构

```
D:\AE-Work\                          # AE_WORK_DIR 根目录
├── topaz_output\                    # Topaz Video AI 增强输出
├── blender_output\                  # Blender 渲染输出
├── ai_video_output\                 # RunwayML/Pika AI 视频输出
└── silhouette_output\               # Silhouette 抠像输出
```

### 5.4 依赖检查

```python
from core.config import check_dependencies

deps = check_dependencies()
# 返回:
# {
#   "ae_installed": True,
#   "silhouette_installed": True,
#   "output_dir_writable": True,
#   "tmp_dir_writable": True,
#   "bridge_dir_writable": True
# }
```

### 5.5 LLM 网关配置（可选）

LLM 网关用于意图理解增强（`nlu_model=llm` 或 `hybrid` 模式），支持 OmniRoute 或任意 OpenAI 兼容端点：

```bash
# .env 配置
AEKV_LLM_BASE_URL=http://localhost:5273/v1    # OmniRoute 网关
AEKV_LLM_API_KEY=your-api-key
AEKV_LLM_MODEL=auto                            # auto 让网关自动路由

# 降级 Provider（JSON 格式）
AEKV_LLM_FALLBACKS=[{"base_url":"https://api.deepseek.com/v1","api_key":"sk-xxx"}]
```

未配置 LLM 网关时，系统自动降级为 `nlu_model=local`（纯正则模式），不影响核心功能。

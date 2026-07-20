# Phase 7 - 素材获取与集成系统架构设计 v2.0

> 📅 日期: 2026-07-06
> 📋 目标: 构建完整的素材搜索、下载、分析、匹配、导入AE的一体化工作流

---

## 一、实战演练经验教训总结

### 1.1 本次测试的成功经验

#### ✅ 最佳实践：`executeAtomScript`
- **最可靠**：这是白名单内最强大的命令
- **最灵活**：可以直接运行任意 ExtendScript
- **最快**：不需要多个往返过程

#### ✅ ExtendScript 避坑指南
1. **路径**：必须用正斜杠 `/`，不能用反斜杠
2. **特性**：不能用 ES6+ 特性（如 `toISOString()`）
3. **调试**：用 `alert()` 或写入文件调试

#### ✅ Python脚本桥接模式
- 使用 `--json-input` 参数实现标准输入输出通信
- 所有Python模块统一接口模式，便于MCP调用
- 子进程调用方式隔离了依赖环境问题

### 1.2 发现的问题与解决方案

| 问题 | 解决方案 | 状态 |
|------|---------|------|
| `importFootage` 命令有时失败 | 使用 `executeAtomScript` 直接实现完整导入 | ✅ 已修复 |
| 路径反斜杠转义问题 | 使用正斜杠或正确转义的反斜杠 | ✅ 已修复 |
| 合成不存在时的处理 | 先检查，不存在则自动创建 | ✅ 已修复 |
| 音频分析能力缺失 | 集成librosa库实现BPM/情绪/曲风分析 | ✅ 已新增 |
| 智能BGM匹配缺失 | 基于音频特征的相似度匹配算法 | ✅ 已新增 |
| 多平台搜索能力不足 | 集成yt-dlp搜索功能，支持抖音/B站/YouTube | ✅ 已新增 |
| 抖音搜索式下载缺失 | 实现关键词搜索+批量下载 | ✅ 已新增 |

---

## 二、完整架构设计

### 2.1 系统模块划分

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AE MCP 完整素材工作流 v2.0                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│  │  用户提示词  │────▶│  素材搜索器  │────▶│  下载管理器  │            │
│  │  (MCP工具)   │     │  (MediaSearch)│     │(MediaFetcher)│            │
│  │              │     │  + AudioAnalyzer│   │+ DouyinDownloader│         │
│  └──────────────┘     └───────┬────────┘     └──────┬────────┘            │
│                               │                    │                     │
│  ┌──────────────┐     ┌───────▼────────┐            │                     │
│  │  AE 导入器   │◀────│  音频分析器   │◀───────────┘                     │
│  │ (AEImporter) │     │(AudioAnalyzer)│                                 │
│  └──────────────┘     └──────────────┘                                 │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    MediaManager (统一调度)                        │   │
│  │  complete_workflow() / find_and_download_bgm()                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        素材管理系统架构                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   入口层         │    │   业务逻辑层     │    │   工具链层       │ │
│  │                 │    │                 │    │                 │ │
│  │ • media-manager │    │ • media-fetcher │    │ • yt-dlp        │ │
│  │ • media-mcp-tools│   │ • douyin-       │    │ • FFmpeg        │ │
│  │                 │    │   downloader    │    │ • FFprobe       │ │
│  └────────┬────────┘    │ • media-search  │    │ • librosa       │ │
│           │             │ • audio-analyzer│    │ • scipy         │ │
│           │             │ • ffmpeg-toolkit│    │                 │ │
│           │             └────────┬────────┘    └─────────────────┘ │
│           │                      │                                │
│           ▼                      ▼                                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      数据存储层                              │   │
│  │                                                             │   │
│  │  D:\AE-Work\                                                │   │
│  │  ├── 视频素材库/     # 视频文件                              │   │
│  │  ├── 音频素材库/                                            │   │
│  │  │   ├── BGM/       # 背景音乐                              │   │
│  │  │   └── 音效/      # 音效素材                              │   │
│  │  ├── 图片素材库/     # 图片文件                              │   │
│  │  ├── 成品库/        # 渲染输出                              │   │
│  │  ├── 下载临时/      # 下载缓存                              │   │
│  │  ├── 日志与报告/    # 运行日志                              │   │
│  │  └── cookies/       # 平台登录凭证                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 核心工具链

| 工具 | 用途 | GitHub ⭐ | 状态 |
|------|------|----------|------|
| **yt-dlp** | 视频/音频下载 (支持 1000+ 网站) | 62k+ | ✅ 已集成 |
| **FFmpeg** | 格式转换、剪辑、提取 | 40k+ | ✅ 已集成 |
| **librosa** | 音频分析（BPM/情绪/曲风） | 10k+ | ✅ 已集成 |
| **scipy** | 科学计算支持 | 15k+ | ✅ 已集成 |

---

## 三、功能规划

### 3.1 Phase 7 第一阶段（已实现）

1. **`download-media` MCP 工具**
   - 从 URL 下载视频/音频
   - 自动选择最佳质量
   - 支持平台：抖音、B站、YouTube 等

2. **`import-media-to-ae` MCP 工具**
   - 下载 + 导入一体化
   - 支持音频、视频、图片
   - 自动添加到合成

3. **修复现有 `importFootage` 工具**
   - 解决路径转义问题
   - 使用 `executeAtomScript` 实现

### 3.2 Phase 7 第二阶段（已实现）

1. **`search-media` MCP 工具**
   - 本地素材库搜索
   - 在线平台搜索（抖音/B站/YouTube/快手）
   - 支持关键词、情绪、BPM多维度搜索

2. **`extract-audio` MCP 工具**
   - 从视频提取音频
   - 支持 MP3/WAV/M4A/FLAC 格式

3. **`clip-media` MCP 工具**
   - 截取视频/音频片段
   - 精确到毫秒级

4. **`analyze-audio` MCP 工具**
   - 分析音频特征（BPM/情绪/曲风/音调）
   - 生成节拍映射

5. **`find-bgm` MCP 工具**
   - 智能匹配背景音乐
   - 基于时长、情绪、BPM匹配

6. **`get-media-info` MCP 工具**
   - 获取媒体文件详细信息

7. **`library-stats` MCP 工具**
   - 获取素材库统计信息

---

## 四、模块详细说明

### 4.1 MediaFetcher (`media-fetcher.py`)

**功能**：跨平台视频/音频下载器

**支持平台**：抖音/TikTok、Bilibili、YouTube、快手

**核心方法**：
- `download_video(url, audio_only, quality)` - 下载视频/音频
- `download_bgm(url)` - 仅下载音频
- `download_batch(urls)` - 批量下载
- `get_video_info(url)` - 获取视频元信息

### 4.2 DouyinDownloader (`douyin-downloader.py`)

**功能**：抖音专用下载工具

**核心方法**：
- `download_video(url)` - 无水印下载
- `download_bgm(url)` - 提取背景音乐
- `search_and_download(keyword)` - 搜索式下载
- `download_user_videos(user_url)` - 批量下载用户视频
- `download_trending_videos(count)` - 下载热门视频
- `batch_extract_audio()` - 批量提取音频
- `auto_manage_cookies()` - Cookie自动管理

### 4.3 FFmpegToolkit (`ffmpeg-toolkit.py`)

**功能**：音频提取与片段截取

**核心方法**：
- `extract_audio(input, format)` - 提取音频
- `extract_video_segment(input, start, duration)` - 截取视频片段
- `extract_audio_segment(input, start, duration)` - 截取音频片段
- `get_media_info(input)` - 获取媒体信息
- `convert_video_format(input, output)` - 转换格式

### 4.4 AudioAnalyzer (`audio-analyzer.py`)

**功能**：智能音频分析引擎

**分析维度**：
- 🎵 **BPM/节拍**: 精确检测节拍速度和节拍位置
- 🎹 **音调**: 调性(C/D/E等)和调式(major/minor)
- 🎭 **情绪**: excited/calm/happy/sad/epic/mysterious
- 🎸 **曲风**: rock/pop/electronic/classical/jazz/epic/ambient
- 📊 **声学特征**: 能量、响度、频谱重心、零交叉率

**核心方法**：
- `analyze_audio(path)` - 完整音频分析
- `generate_beat_map(path)` - 生成节拍映射
- `find_best_bgm_match(features, dir)` - 智能BGM匹配

### 4.5 MediaSearchEngine (`media-search.py`)

**功能**：素材搜索与智能匹配

**核心方法**：
- `scan_library()` - 扫描素材库
- `search_by_keyword(keyword)` - 关键词搜索
- `search_by_mood(mood)` - 情绪搜索
- `search_by_bpm(bpm)` - BPM搜索
- `search_online(query, platform)` - 在线平台搜索
- `find_bgm_for_video(duration, mood, bpm)` - 智能BGM匹配
- `get_library_stats()` - 素材库统计

### 4.6 MediaManager (`media-manager.py`)

**功能**：综合管理主入口，统一调度所有模块

**核心方法**：
- `complete_workflow(url, clip_start, clip_duration, extract_audio, analyze)` - 完整工作流
- `find_and_download_bgm(mood, duration, bpm)` - 智能BGM查找与下载

---

## 五、MCP 工具设计

### 5.1 工具清单

| 工具名称 | 功能描述 | 参数 |
|---------|---------|------|
| `search-media` | 搜索本地或在线素材 | query, type, platform, mood, bpm, minDuration, maxDuration, maxResults |
| `download-media` | 下载视频/音频 | url, type, outputDir, quality |
| `extract-audio` | 从视频提取音频 | inputFile, outputFile, format, bitrate |
| `clip-media` | 截取视频/音频片段 | inputFile, startTime, duration, outputFile, type |
| `analyze-audio` | 分析音频特征 | audioPath |
| `find-bgm` | 智能匹配BGM | videoDuration, mood, bpm, maxResults |
| `get-media-info` | 获取媒体信息 | filePath |
| `library-stats` | 获取素材库统计 | 无 |

### 5.2 工具调用示例

```typescript
// 搜索素材
server.tool("search-media", "搜索素材", {
  query: z.string(),
  platform: z.enum(["youtube", "bilibili", "douyin", "local"]).optional(),
  mood: z.string().optional(),
  bpm: z.number().optional()
})

// 分析音频
server.tool("analyze-audio", "分析音频", {
  audioPath: z.string()
})

// 匹配BGM
server.tool("find-bgm", "匹配BGM", {
  videoDuration: z.number(),
  mood: z.string().optional(),
  bpm: z.number().optional()
})
```

---

## 六、路径处理

### 6.1 统一路径处理规则

1. **Windows路径**：统一转换为正斜杠 `/`
2. **路径转义**：确保安全传递给ExtendScript
3. **相对路径**：自动转换为绝对路径

### 6.2 ExtendScript安全路径

```typescript
// 将 Windows 路径转换为 ExtendScript 安全路径
function toExtendScriptPath(winPath) {
    return winPath.replace(/\\/g, "/");
}
```

---

## 七、知识架构整合

### 7.1 与现有知识体系的关联

| 知识领域 | 关联模块 | 用途 |
|---------|---------|------|
| 节拍-关键帧映射 | AudioAnalyzer | BPM检测用于精确关键帧对齐 |
| 音画匹配引擎 | AudioAnalyzer + MediaSearchEngine | 智能BGM匹配 |
| 音乐结构分析 | AudioAnalyzer | 段落检测和结构分析 |
| 风格化剪辑 | MediaSearchEngine | 情绪/BPM匹配素材 |

### 7.2 知识流动路径

```
用户需求 → 素材搜索 → 下载 → 音频分析 → BGM匹配 → AE导入 → 剪辑制作
              ↓           ↓           ↓           ↓
         关键词/情绪   多平台支持   BPM/情绪/曲风   智能推荐
```

---

## 八、部署清单

### 8.1 依赖安装

```bash
# 核心工具
pip install yt-dlp

# 音频分析
pip install librosa scipy numpy

# FFmpeg (需要单独安装并添加到PATH)
# 下载地址: https://ffmpeg.org/download.html
```

### 8.2 配置文件

路径：`config/media-config.json`

```json
{
  "directories": {
    "video_library": "D:/AE-Work/视频素材库",
    "bgm_library": "D:/AE-Work/音频素材库/BGM"
  },
  "tools": {
    "yt_dlp": "yt-dlp",
    "ffmpeg": "ffmpeg"
  },
  "platforms": {
    "douyin": {
      "cookie_path": "D:/AE-Work/cookies/douyin_cookies.txt"
    }
  },
  "audio": {
    "default_sample_rate": 44100,
    "default_bitrate": "192k"
  }
}
```

---

## 九、路线图

| 阶段 | 状态 | 完成时间 |
|------|------|---------|
| Phase7.1 - 基础下载功能 | ✅ | 已完成 |
| Phase7.2 - FFmpeg集成 | ✅ | 已完成 |
| Phase7.3 - 音频分析完善 | ✅ | 已完成 |
| Phase7.4 - 搜索功能集成 | ✅ | 已完成 |
| Phase7.5 - MCP工具封装 | ✅ | 已完成 |
| Phase7.6 - 综合管理入口 | ✅ | 已完成 |
| Phase7.7 - 性能优化 | 🔄 | 进行中 |
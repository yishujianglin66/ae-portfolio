# Phase7 - 媒体处理与AE集成完全指南 🎬

> ✅ **完成日期**：2026-07-06  
> 🎯 **目标**：提供从素材搜索→下载→剪辑→导入AE的完整工作流

---

## 📋 快速开始总览

已集成到 `after-effects-mcp` 项目中的完整工具链：

| 阶段 | 功能 | 工具名 | 依赖 |
|------|------|--------|------|
| 1️⃣ | 素材下载 | `download-media` | yt-dlp |
| 2️⃣ | 音频提取 | `extract-audio` | FFmpeg |
| 3️⃣ | 视频裁剪 | `clip-media` | FFmpeg |
| 4️⃣ | 信息查询 | `get-media-info` | FFprobe |
| 5️⃣ | 可靠导入 | `import-footage-reliable` | AE |
| 6️⃣ | 下载+导入一体化 | `import-media-to-ae` | yt-dlp + AE |

---

## 🔧 依赖安装

### 1. yt-dlp (必需，用于下载)
```
Windows推荐下载：https://github.com/yt-dlp/yt-dlp/releases
下载 yt-dlp.exe，放入 PATH 中的文件夹，如 C:\Windows\
```

验证：
```powershell
yt-dlp --version
```

### 2. FFmpeg (必需，用于剪辑和格式转换)
```
Windows推荐下载：https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
解压后，把 bin 目录添加到 PATH 环境变量
```

验证：
```powershell
ffmpeg -version
ffprobe -version
```

---

## 📖 完整工作流演示

### 工作流 1：抖音/视频→下载→裁剪→导入AE
```
1. download-media [抖音URL]
   ↓ (得到 video.mp4)
2. clip-media video.mp4 00:00:05 00:00:10
   ↓ (得到 video_clip.mp4，从第5秒开始，取10秒)
3. import-media-to-ae video_clip.mp4 [compName]
   ↓ (完成！素材已在AE中)
```

### 工作流 2：提取BGM
```
1. extract-audio video.mp4 mp3
   ↓ (得到 video_audio.mp3)
2. import-footage-reliable video_audio.mp3 [compName]
```

### 工作流 3：快速下载+导入
```
1. import-media-to-ae [URL] [compName]
   ✅ 一步到位！
```

---

## 🎯 详细使用说明

### 1. download-media - 下载媒体
参数：
- `url`: 媒体URL（抖音、B站、YouTube等1000+网站）
- `type`: `video`|`audio`（默认 video）
- `outputDir`: 自定义输出目录（可选）
- `quality`: `best`|`720p`|`1080p`（默认 best）

示例：
```
download-media https://www.bilibili.com/video/... video 720p
```

### 2. clip-media - 裁剪片段
参数：
- `filePath`: 源文件路径
- `startTime`: 起始时间，格式 `00:00:00` 或 `00:00`
- `duration`: 持续时长
- `outputPath`: 输出路径（可选）

示例：
```
clip-media video.mp4 00:00:05 00:00:10
# 从第5秒开始，取10秒
```

### 3. extract-audio - 提取BGM
参数：
- `filePath`: 视频文件路径
- `format`: `mp3`|`wav`|`m4a`（默认 mp3）
- `outputPath`: 输出路径（可选）

示例：
```
extract-audio video.mp4 mp3
```

### 4. import-media-to-ae - 一体化工作流
参数：
- `url`: 媒体URL
- `compName`: 目标合成名称（可选）
- 其他参数同 `download-media`

示例：
```
import-media-to-ae https://... "我的BGM素材"
```

---

## 📁 项目文件

### 主要文件位置
- **AE MCP 项目**：`c:\Users\Administrator\Desktop\after-effects-mcp-main\`
  - **源代码**：`src/index.ts`
  - **已构建**：`build/index.js`
- **知识仓库**：`c:\Users\Administrator\Desktop\AE-Knowledge-Vault\`
  - **Phase7相关**：`phase7-media-tools\`
  - **文档**：`03-阶段报告/Phase7-素材获取与集成/`

### 构建和运行
```powershell
cd c:\Users\Administrator\Desktop\after-effects-mcp-main
npm run build
# 然后在您的MCP客户端配置 build/index.js 作为MCP服务器
```

---

## 📋 本次开发回顾

### ✅ 已完成的工作
1. **Phase7 基础工具集成**
   - `download-media` - yt-dlp下载
   - `import-media-to-ae` - 下载+导入一体化
   - `import-footage-reliable` - 可靠导入（修复路径问题）

2. **Phase7.2 FFmpeg 工具集**
   - `clip-media` - 视频/音频裁剪
   - `extract-audio` - 音频提取（BGM）
   - `get-media-info` - 媒体信息查询

3. **架构优化**
   - 移除独立文件，直接集成到 `index.ts`
   - 避免模块化问题
   - 使用已有验证过的 `importFootage` 脚本

### 📝 经验与教训
1. **路径处理**：ExtendScript 必须使用正斜杠 `/`
2. **工具选择**：`executeAtomScript` 最灵活可靠
3. **模块化**：项目规模小，直接内联更好
4. **外部依赖**：yt-dlp 和 FFmpeg 都是成熟工具，整合容易

---

## 🎉 总结

现在你拥有了一个**完整的媒体工作流**！从任意网站下载素材→裁剪→提取BGM→导入AE，一气呵成！🚀

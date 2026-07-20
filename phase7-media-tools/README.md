# Phase7 - 素材获取与管理系统 🎬

## 📦 安装步骤

### 1️⃣ 安装 yt-dlp
从 GitHub 下载并安装：https://github.com/yt-dlp/yt-dlp/releases

确保 yt-dlp 在系统 PATH 中：
```bash
yt-dlp --version
```

### 2️⃣ 将 Phase7 工具集成到你的 MCP 服务器

在你的 MCP 服务器中，导入并使用 Phase7 工具：
```javascript
import './phase7-media-tools/phase7-mcp-tools';
```

---

## 🚀 使用指南

### 工具 1: `import-media-to-ae` - 一体化导入
从 URL 直接下载并导入 AE！

**示例**：
```
import-media-to-ae 
  url: "https://www.bilibili.com/video/BV1xx..."
  type: video
  compName: "我的项目"
```

### 工具 2: `download-media` - 仅下载
只下载文件，不导入 AE。

### 工具 3: `import-footage-reliable` - 可靠版本地导入
修复了路径转义问题的本地素材导入。

---

## 🔧 核心模块

| 模块 | 用途 |
|------|------|
| `PathUtils` | 路径处理，Windows → ExtendScript 安全 |
| `MediaDownloader` | yt-dlp 下载管理器 |
| `AEImporter` | 生成 AE 导入脚本 |

---

## 📝 经验教训

1. **路径必须使用正斜杠**，否则 ExtendScript 会转义失败
2. **使用 executeAtomScript** 而不是单独的命令，更可靠
3. **不要在 ExtendScript 中使用 ES6+ 特性**（如 toISOString）

---

## 📚 相关资源

- 项目主文档：查看 `03-阶段报告/Phase7-素材获取与集成/`
- 测试套件：`05-测试套件/`

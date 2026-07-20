# 🚀 Phase7 - 快速开始指南

## ✅ 当前状态
- ✅ yt-dlp 已安装并验证可用
- ✅ Phase7 核心模块已创建
- ✅ 快速测试通过

---

## 📦 使用方法（两种方式）

---

### 方式 1: 独立使用（推荐，最简单）

#### 下载文件
```bash
cd phase7-media-tools
node standalone-downloader.js <URL> [video|audio]
```

**示例**：
```bash
node standalone-downloader.js "https://www.bilibili.com/video/BV1xx..." video
```

下载完成后，会自动生成 `Phase7_Import_Downloaded.jsx`，在 AE 中运行即可导入！

---

### 方式 2: 集成到 MCP 服务器

将 `phase7-mcp-tools.ts` 导入到你的 MCP 服务器主文件中。

---

## 📂 项目结构

```
phase7-media-tools/
├── README.md                  # 完整文档
├── QUICKSTART.md              # 本文件
├── quick-test.js              # 快速测试脚本
├── standalone-downloader.js   # 独立下载工具
├── index.js                   # 主入口
├── path-utils.js              # 路径处理工具
├── media-downloader.js        # yt-dlp 下载器
├── ae-importer.js             # AE 导入工具
└── phase7-mcp-tools.ts        # MCP 工具定义
```

---

## 🎯 下一步

1. 先运行 `05-测试套件/Phase7_Test_Import.jsx` 在 AE 中测试导入
2. 尝试使用 `standalone-downloader.js` 下载你需要的素材
3. 然后将 `phase7-mcp-tools.ts` 集成到你的完整 MCP 工作流中

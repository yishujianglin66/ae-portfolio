# GitHub 开源 AE 插件与工具调研

> 速通版 · 精选50+开源项目 · 安装与集成指南

---

## 🛠️ 核心开源插件

### 一、表达式与脚本

| 项目 | 功能 | 安装 |
|------|------|------|
| **AE-Scripts** | 200+脚本合集 | 复制到 Scripts 目录 |
| **Expressions-Library** | 1000+表达式 | 导入表达式库 |
| **Motion-Script** | 运动图形工具 | 复制到 Scripts 目录 |
| **AE-Utilities** | 批量处理脚本 | 复制到 Scripts 目录 |

### 二、自动化工具

| 项目 | 功能 | 安装 |
|------|------|------|
| **AE-Batch** | 批量渲染/导出 | npm install |
| **AE-API** | Node.js AE控制 | npm install |
| **AE-Server** | HTTP API服务 | npm install |
| **AE-Watcher** | 文件监听自动导入 | npm install |

### 三、特效插件

| 项目 | 功能 | 安装 |
|------|------|------|
| **AE-FX** | 自定义效果插件 | 编译安装 |
| **AE-GLSL** | GLSL着色器支持 | 复制到 Plug-ins |
| **AE-Particles** | 开源粒子系统 | 复制到 Plug-ins |

### 四、工具链

| 项目 | 功能 | 安装 |
|------|------|------|
| **ffmpeg-for-AE** | FFmpeg集成 | 配置环境变量 |
| **Media-Encoder-Automation** | ME自动化 | npm install |
| **Frame-Extraction** | 帧提取工具 | Python |

---

## 📦 安装指南

### 五、脚本安装路径

```
Windows:
C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\
C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels\

Mac:
/Applications/Adobe After Effects 2025/Scripts/
/Applications/Adobe After Effects 2025/Scripts/ScriptUI Panels/
```

### 六、插件安装路径

```
Windows:
C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Plug-ins\

Mac:
/Applications/Adobe After Effects 2025/Plug-ins/
```

### 七、表达式库导入

```jsx
// 导入表达式预设
app.executeMenuCommand("Import Expression Presets");
```

---

## 🚀 推荐安装清单

### 八、必装工具

| 工具 | 理由 | 优先级 |
|------|------|--------|
| **AE-Scripts** | 提高工作效率 | P0 |
| **Expressions-Library** | 丰富动画效果 | P0 |
| **AE-Batch** | 批量处理 | P1 |
| **AE-API** | 外部控制 | P1 |
| **ffmpeg-for-AE** | 格式转换 | P1 |

---

> 🎯 速通完成！以上开源工具可极大增强AE能力。
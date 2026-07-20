# AE MCP Server

Adobe After Effects MCP Server - 通过文件桥接与 AE 通信的 MCP 服务

## 架构

```
MCP Client (Trae IDE) → stdio → MCP Server → 文件桥接 → AE JSX 监听脚本
```

- **MCP Server**: Node.js + TypeScript + @modelcontextprotocol/sdk
- **传输方式**: stdio（与 Trae IDE MCP 兼容）
- **通信协议**: 文件桥接（JSON 文件轮询）

## 桥接目录

默认桥接目录: `C:\Users\Administrator\Documents\ae-mcp-bridge\`

- `command.json` - 写入命令
- `result.json` - 读取结果
- `bridge.log` - 日志
- `temp/args.json` - 脚本参数临时文件

通信机制:
- 轮询间隔: 200ms
- 超时时间: 8000ms
- 原子写入: 先写 .tmp 再 rename

## 项目结构

```
ae-mcp-server/
├── src/
│   ├── index.ts          # MCP Server 入口，注册所有工具
│   ├── bridge.ts         # 文件桥接通信逻辑
│   └── tools/            # 每个工具一个文件
│       ├── _base.ts      # 工具基类和工厂函数
│       ├── create-composition.ts
│       ├── add-text-layer.ts
│       ├── add-shape-layer.ts
│       ├── add-adjustment-layer.ts
│       ├── set-blend-mode.ts
│       ├── set-track-matte.ts
│       ├── add-effect-with-keyframes.ts
│       ├── batch-add-effects.ts
│       ├── import-footage.ts
│       ├── run-jsx-script.ts
│       ├── get-project-info.ts
│       └── list-compositions.ts
├── scripts/              # AE JSX 脚本（需复制到 AE 脚本目录）
│   ├── _lib/             # 公共库文件
│   ├── bridge_listener.jsx  # AE 端监听脚本（主入口）
│   ├── createComposition.jsx
│   ├── addTextLayer.jsx
│   ├── addShapeLayer.jsx
│   ├── addAdjustmentLayer.jsx
│   ├── setBlendMode.jsx
│   ├── setTrackMatte.jsx
│   ├── addEffectWithKeyframes.jsx
│   ├── batchAddEffects.jsx
│   ├── importFootage.jsx
│   ├── executeAtomScript.jsx
│   ├── analyzeProject.jsx
│   └── listCompositions.jsx
├── package.json
├── tsconfig.json
└── README.md
```

## 安装与构建

```bash
cd ae-mcp-server
npm install
npm run build
```

## 启动方式

### 1. 启动 AE 监听脚本

1. 打开 Adobe After Effects
2. 将 `scripts/` 目录下的所有文件复制到 AE 脚本目录:
   - `C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ae-mcp-bridge\`
3. 在 AE 中: 文件 → 脚本 → 运行脚本文件
4. 选择 `bridge_listener.jsx`
5. 点击确定启动监听（监听在后台运行）

### 2. 启动 MCP Server

```bash
node dist/index.js
```

或使用 npm:

```bash
npm start
```

### 3. 在 Trae IDE 中配置 MCP Server

在 Trae IDE 的 MCP 配置中添加:

```json
{
  "mcpServers": {
    "after-effects": {
      "command": "node",
      "args": ["C:\\path\\to\\ae-mcp-server\\dist\\index.js"]
    }
  }
}
```

## 工具列表

共 12 个核心工具:

| 工具名称 | 描述 |
|---------|------|
| `create-composition` | 创建新的 After Effects 合成 |
| `add-text-layer` | 在合成中添加文字图层 |
| `add-shape-layer` | 在合成中添加形状图层（矩形/椭圆/星形/多边形） |
| `add-adjustment-layer` | 在合成中添加调整图层 |
| `set-blend-mode` | 设置图层的混合模式 |
| `set-track-matte` | 设置图层的轨道遮罩类型 |
| `add-effect-with-keyframes` | 向图层添加效果并设置关键帧动画 |
| `batch-add-effects` | 批量向图层添加多个效果 |
| `import-footage` | 导入素材文件到项目，可选添加到指定合成 |
| `run-jsx-script` | 执行任意 JSX 脚本（有安全限制） |
| `get-project-info` | 获取当前打开项目的详细信息 |
| `list-compositions` | 列出项目中所有合成的基本信息 |

## 工具详情

### create-composition

创建新的 After Effects 合成。

**参数:**
- `name` (string, 必填): 合成名称
- `width` (number, 默认 1920): 合成宽度（像素）
- `height` (number, 默认 1080): 合成高度（像素）
- `duration` (number, 默认 10): 合成持续时间（秒）
- `frameRate` (number, 默认 30): 帧速率（fps）
- `pixelAspect` (number, 默认 1): 像素宽高比

### add-text-layer

在合成中添加文字图层。

**参数:**
- `compName` (string, 必填): 目标合成名称
- `text` (string, 必填): 文字内容
- `name` (string, 可选): 图层名称
- `fontSize` (number, 可选): 字体大小，默认 72
- `fillColor` (number[3], 可选): 填充颜色 [r, g, b]，范围 0-1，默认白色
- `fontFamily` (string, 可选): 字体名称，默认 Arial
- `justification` (enum, 可选): 对齐方式 (left/center/right)，默认 center
- `position` (number[2], 可选): 位置 [x, y]，默认居中

### add-shape-layer

在合成中添加形状图层。

**参数:**
- `compName` (string, 必填): 目标合成名称
- `shapeType` (enum, 必填): 形状类型 (rectangle/ellipse/star/polygon)
- `name` (string, 可选): 图层名称
- `position` (number[2], 可选): 位置 [x, y]，默认居中
- `size` (number[2], 可选): 尺寸 [宽, 高]，默认合成的 50%
- `fillColor` (number[3], 可选): 填充颜色 [r, g, b]，范围 0-1
- `strokeColor` (number[3], 可选): 描边颜色 [r, g, b]，范围 0-1
- `strokeWidth` (number, 可选): 描边宽度，默认 0（无描边）

### add-adjustment-layer

在合成中添加调整图层。

**参数:**
- `compName` (string, 必填): 目标合成名称
- `name` (string, 可选): 调整图层名称，默认 "Adjustment Layer"
- `position` (number, 可选): 插入位置索引（1-based），默认最顶层

### set-blend-mode

设置图层的混合模式。

**参数:**
- `compName` (string, 必填): 目标合成名称
- `layerIndex` (number, 必填): 图层索引（1-based）
- `blendMode` (enum, 必填): 混合模式
  - NONE, DISSOLVE, MULTIPLY, SCREEN, OVERLAY
  - SOFT_LIGHT, HARD_LIGHT, ADD, COLOR_DODGE, COLOR_BURN
  - DARKEN, LIGHTEN, DIFFERENCE, EXCLUSION, HUE
  - SATURATION, COLOR, LUMINOSITY

### set-track-matte

设置图层的轨道遮罩类型。

**参数:**
- `compName` (string, 必填): 目标合成名称
- `layerIndex` (number, 必填): 图层索引（1-based）
- `matteType` (enum, 必填): 轨道遮罩类型
  - NO_TRACK_MATTE
  - ALPHA_TRACK_MATTE
  - ALPHA_INVERTED_TRACK_MATTE
  - LUMA_TRACK_MATTE
  - LUMA_INVERTED_TRACK_MATTE

### add-effect-with-keyframes

向图层添加效果并设置关键帧动画。

**参数:**
- `compName` (string, 必填): 目标合成名称
- `layerIndex` (number, 必填): 图层索引（1-based）
- `effectMatchName` (string, 必填): 效果匹配名称（如 ADBE Gaussian Blur 2）
- `settings` (object, 可选): 效果初始参数设置 {propertyName: value}
- `keyframes` (array, 可选): 关键帧数组
  - `propertyName` (string): 效果属性名称
  - `time` (number): 关键帧时间（秒）
  - `value` (any): 关键帧值
  - `easingType` (enum, 可选): 缓动类型 (linear/hold/easeIn/easeOut/easeInOut/bezier)

### batch-add-effects

批量向图层添加多个效果。

**参数:**
- `compName` (string, 必填): 目标合成名称
- `layerIndex` (number, 必填): 图层索引（1-based）
- `effects` (array, 必填): 要添加的效果数组
  - `effectMatchName` (string): 效果匹配名称
  - `settings` (object, 可选): 效果参数设置

### import-footage

导入素材文件到项目，可选添加到指定合成。

**参数:**
- `filePath` (string, 必填): 素材文件的完整路径
- `asSequence` (boolean, 可选): 是否作为序列导入，默认 false
- `compName` (string, 可选): 目标合成名称（指定后素材会添加到该合成）
- `position` (number, 可选): 添加到合成时的位置索引（1-based）

### run-jsx-script

执行任意 JSX 脚本（有安全限制）。

**安全限制:**
- 禁止系统命令调用 (system.callSystem)
- 禁止外部 JSX 文件执行 ($.evalFile)
- 禁止动态函数创建 (new Function)
- 禁止外部程序启动 (.execute)
- 脚本大小限制: 1MB

**参数:**
- `scriptContent` (string, 必填): 要执行的 JSX 脚本内容
- `scriptName` (string, 可选): 脚本名称，用于日志标识
- `dryRun` (boolean, 可选): 干运行模式，仅检查语法不执行，默认 false
- `timeout` (number, 可选): 超时时间（毫秒），默认 10000

### get-project-info

获取当前打开项目的详细信息，包括所有合成、图层、效果统计。

**参数:** 无

**返回:**
- 项目名称和路径
- 合成总数和图层总数
- 所有合成的详细信息（图层、效果、关键帧等）
- 效果分类统计（内置/插件）
- 使用的技术栈分析

### list-compositions

列出项目中所有合成的基本信息。

**参数:** 无

**返回:**
- 合成列表：名称、尺寸、时长、帧率、图层数等

## 开发

### 目录结构说明

- `src/`: TypeScript 源代码
- `dist/`: 编译输出（构建后生成）
- `scripts/`: AE JSX 脚本文件
  - `_lib/`: 公共库（参数加载、响应构建、工具函数）
  - `bridge_listener.jsx`: AE 端主监听脚本

### 新增工具

1. 在 `src/tools/` 下创建新工具文件
2. 使用 `createTool` 工厂函数创建工具定义
3. 在 `src/tools/index.ts` 中导出
4. 在 `scripts/` 下创建对应的 JSX 脚本
5. 在 `bridge_listener.jsx` 中会自动按名称调用

### 自定义桥接目录

设置环境变量或修改 `src/bridge.ts` 中的默认路径。

## 技术栈

- Node.js 18+
- TypeScript 5+
- @modelcontextprotocol/sdk
- zod (参数验证)
- stdio 传输模式

## 许可证

MIT

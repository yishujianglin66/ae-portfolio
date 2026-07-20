---
title: AE扩展脚本深度集成手册
date: 2026-07-14
related_docs:
  - "[[AE扩展脚本完全知识库]] - 扩展脚本完全知识库（含 BeatEdit 等插件解析，本文聚焦深度集成）"
tags:
  - AE扩展脚本
  - 深度集成
  - MCP桥接
  - 原子参数编译
  - 自动化
---

# AE扩展脚本深度集成手册

> [!abstract] 文档摘要
> 本手册整合了AE-Knowledge-Vault项目中所有扩展脚本资源，建立了知识库→工具→API→执行的完整集成链路。涵盖74个JSX脚本、22个MCP工具、14个编译器模板，以及与四大核心扩展（BeatEdit、Motion Tools Pro、MotionSpice、Motion Studio）的深度集成方案。

---

## 第一章 集成架构总览

### 1.1 四层集成模型

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AE扩展脚本深度集成架构                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 第一层：知识层（Knowledge Layer）                             │   │
│  │ ├── AE扩展脚本完全知识库.md                                   │   │
│  │ ├── AE ExtendScript API 原子级映射手册.md                     │   │
│  │ ├── MCP→AE效果操作桥接规范.md                                 │   │
│  │ ├── 原子参数编译器规范.md                                     │   │
│  │ └── 参数-效果原子级映射库.md                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 第二层：工具层（Tool Layer）                                  │   │
│  │ ├── BeatEdit（节拍检测与卡点动画）                            │   │
│  │ ├── Motion Tools Pro（运动工具集）                            │   │
│  │ ├── MotionSpice（MG动画预设库）                              │   │
│  │ ├── Motion Studio（运动工作室）                              │   │
│  │ └── ScriptUI Panels（74个脚本面板）                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 第三层：桥接层（Bridge Layer）                                │   │
│  │ ├── ae_mcp_bridge_v26.jsx（核心桥接脚本）                    │   │
│  │ ├── MCP Server（Node.js服务端）                              │   │
│  │ ├── ae_command.json（命令文件）                              │   │
│  │ ├── ae_mcp_result.json（结果文件）                           │   │
│  │ └── 22个allowedScripts（白名单脚本）                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 第四层：执行层（Execution Layer）                             │   │
│  │ ├── ExtendScript引擎（JSX执行）                               │   │
│  │ ├── AE DOM对象模型                                           │   │
│  │ ├── 效果属性操作（matchName→property→setValue）              │   │
│  │ └── 关键帧/表达式/遮罩/插件控制                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 数据流路径

```
用户请求 → 知识库检索 → 参数生成 → 编译器编译 → MCP调用 → Bridge执行 → AE操作 → 结果返回
```

---

## 第二章 知识层集成

### 2.1 核心知识文档

| 文档 | 位置 | 字数 | 核心内容 |
|------|------|------|----------|
| AE扩展脚本完全知识库 | [AE扩展脚本完全知识库.md](AE扩展脚本完全知识库.md) | 15,000+ | 四大扩展深度解析、协同工作流、实战案例 |
| AE ExtendScript API原子级映射手册 | [AE ExtendScript API 原子级映射手册.md](AE%20ExtendScript%20API%20原子级映射手册.md) | 20,000+ | 60个效果matchName、DOM映射、脚本模板 |
| MCP→AE效果操作桥接规范 | [MCP→AE效果操作桥接规范.md](MCP→AE效果操作桥接规范.md) | 12,000+ | 通信协议、22个工具Schema、错误码定义 |
| 原子参数编译器规范 | [原子参数编译器规范.md](原子参数编译器规范.md) | 18,000+ | 三阶段编译、11种IR节点、14个代码模板 |
| 参数-效果原子级映射库 | [参数-效果原子级映射库.md](参数-效果原子级映射库.md) | 25,000+ | 600+参数项、效果→属性映射 |

### 2.2 知识检索接口

```python
class AEKnowledgeIntegrator:
    """AE扩展脚本知识检索接口"""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.kb_path = self.vault_path / "10-风格化剪辑知识库"
        self.scripts_path = self.vault_path / "AE-Scripts"

    def search_effect_matchname(self, effect_name: str) -> dict:
        """搜索效果的matchName"""
        # 查询 AE ExtendScript API 原子级映射手册
        pass

    def get_script_template(self, operation: str) -> str:
        """获取脚本模板"""
        # 查询 原子参数编译器规范
        pass

    def get_mcp_tool_schema(self, tool_name: str) -> dict:
        """获取MCP工具Schema"""
        # 查询 MCP→AE效果操作桥接规范
        pass
```

---

## 第三章 工具层集成

### 3.1 四大核心扩展

#### 3.1.1 BeatEdit（节拍检测与卡点动画）

**安装路径**：
```
C:\Program Files (x86)\Common Files\Adobe\CEP\extensions\beatedit_Ae_2_2_005
```

**核心功能**：
- 精准节拍检测（支持多种音乐类型）
- 自动生成卡点标记
- 智能关键帧映射
- 批量动画应用

**MCP集成接口**：
```json
{
  "tool": "beatedit_analyze",
  "params": {
    "audio_layer": "Audio Layer Name",
    "sensitivity": 0.8,
    "min_bpm": 60,
    "max_bpm": 180
  },
  "returns": {
    "beats": [0.5, 1.0, 1.5, 2.0],
    "bpm": 120,
    "time_signature": "4/4"
  }
}
```

**脚本调用示例**：
```javascript
// BeatEdit 节拍检测调用
function analyzeBeats(comp, audioLayer) {
    var beats = [];
    var audioPath = audioLayer.source.file.fsName;

    // 调用BeatEdit的节拍检测工具
    var payloadPath = "C:\\Program Files (x86)\\Common Files\\Adobe\\CEP\\extensions\\beatedit_Ae_2_2_005\\payloads\\ibtWin.exe";
    var cmd = '"' + payloadPath + '" --input "' + audioPath + '" --output "beat_data.json"';

    system.callSystem(cmd);

    // 解析结果
    var resultFile = new File(comp.path + "/beat_data.json");
    if (resultFile.exists) {
        resultFile.open("r");
        var data = JSON.parse(resultFile.read());
        beats = data.beats;
        resultFile.close();
    }

    return beats;
}
```

#### 3.1.2 Motion Tools Pro（运动工具集）

**安装路径**：
```
D:\AE_Plugins\Motion Tools Pro\motion tools pro\jsx\
```

**核心功能**：
- 图层分布与排列
- 文字分割动画
- 路径动画工具
- IK骨骼系统

**脚本文件**：
- `distribution-apply.jsx` - 图层分布
- `textsplit-apply.jsx` - 文字分割
- `limbScripts.jsx` - IK骨骼
- `path_test.jsx` - 路径测试

**MCP集成接口**：
```json
{
  "tool": "motion_tools_distribute",
  "params": {
    "layers": ["Layer 1", "Layer 2", "Layer 3"],
    "mode": "grid",
    "columns": 3,
    "spacing": 100
  }
}
```

#### 3.1.3 MotionSpice（MG动画预设库）

**安装路径**：
```
D:\AE_Plugins\MotionSpice\MotionSpice\jsx\
```

**核心功能**：
- 30+种动画预设
- 一键应用效果
- 批量渲染支持

**脚本分类**：
- `finishing/` - 后期效果（FadeIn、FadeOut、Glow等）
- `core.jsx` - 核心功能
- `autorender.jsx` - 自动渲染

**预设列表**：
| 预设名称 | 功能 | 快捷键 |
|---------|------|--------|
| FadeIn | 淡入 | Ctrl+Shift+F1 |
| FadeOut | 淡出 | Ctrl+Shift+F2 |
| Glow | 发光 | Ctrl+Shift+G |
| Drift | 漂移 | Ctrl+Shift+D |
| FlickerIn | 闪烁进入 | Ctrl+Shift+F3 |

#### 3.1.4 Motion Studio（运动工作室）

**安装路径**：
```
D:\AE_Plugins\Motion Studio\
```

**核心功能**：
- 高级运动控制
- 缓动曲线编辑
- 时间重映射

### 3.2 ScriptUI Panels脚本库

**位置**：`AE-Scripts/ScriptUI Panels/`

**脚本清单（74个）**：

| 类别 | 脚本数 | 代表脚本 |
|------|--------|----------|
| 基础动画 | 12 | FadeIn.jsx、FadeOut.jsx、Drift.jsx |
| 效果添加 | 8 | AddGlow.jsx、AddFill.jsx、AddHueSaturation.jsx |
| 变换操作 | 10 | ScaleHalf.jsx、Rotate45.jsx、FlipHorizontal.jsx |
| 时间操作 | 6 | TimeRemapLoop.jsx、SmartPrecompose.jsx |
| 项目管理 | 5 | CleanupProject.jsx、SequenceLayers.jsx |
| 工具脚本 | 33 | util.jsx、core.jsx、main.jsx |

---

## 第四章 桥接层集成

### 4.1 MCP Bridge核心架构

**核心文件**：[ae_mcp_bridge_v26.jsx](../ae_mcp_bridge_v26.jsx)

**通信流程**：
```
1. MCP Server → ae_command.json（写入命令）
2. Bridge Panel → 轮询 ae_command.json（250ms间隔）
3. Bridge → 验证 allowedScripts 白名单
4. Bridge → evalScript() 执行 JSX
5. JSX → 写入 ae_mcp_result.json
6. MCP Server → 读取结果返回
```

### 4.2 22个MCP工具清单

| # | 脚本名称 | MCP工具名 | 功能 |
|---|---------|-----------|------|
| 1 | createComposition.jsx | create-composition | 创建合成 |
| 2 | getProjectDetails.jsx | get-project-details | 获取项目详情 |
| 3 | listCompositions.jsx | list-compositions | 列出合成 |
| 4 | createTextLayer.jsx | create-text-layer | 创建文字层 |
| 5 | createShapeLayer.jsx | create-shape-layer | 创建形状层 |
| 6 | createSolidLayer.jsx | create-solid-layer | 创建纯色层 |
| 7 | createCamera.jsx | create-camera | 创建摄像机 |
| 8 | createNullObject.jsx | create-null-object | 创建空对象 |
| 9 | duplicateLayer.jsx | duplicate-layer | 复制图层 |
| 10 | deleteLayer.jsx | delete-layer | 删除图层 |
| 11 | setLayerKeyframe.jsx | setLayerKeyframe | 设置关键帧 |
| 12 | setLayerExpression.jsx | setLayerExpression | 设置表达式 |
| 13 | setLayerProperties.jsx | setLayerProperties | 设置属性 |
| 14 | batchSetLayerProperties.jsx | batchSetLayerProperties | 批量设置属性 |
| 15 | getLayerInfo.jsx | getLayerInfo | 获取图层信息 |
| 16 | setLayerMask.jsx | setLayerMask | 设置遮罩 |
| 17 | runScript.jsx | run-script | 执行脚本 |
| 18 | getHelp.jsx | get-help | 获取帮助 |
| 19 | getResults.jsx | get-results | 获取结果 |
| 20 | createAdjustmentLayer.jsx | create-adjustment-layer | 创建调整层 |
| 21 | toggle3DLayer.jsx | toggle-3d-layer | 切换3D层 |
| 22 | setBlendMode.jsx | set-blend-mode | 设置混合模式 |

### 4.3 扩展MCP工具设计

#### 4.3.1 效果操作工具（14个新增）

```json
[
  {
    "name": "add_effect",
    "description": "添加效果到图层",
    "inputSchema": {
      "layer": "string",
      "effect_matchname": "string",
      "properties": "object"
    }
  },
  {
    "name": "set_effect_property",
    "description": "设置效果属性",
    "inputSchema": {
      "layer": "string",
      "effect_index": "number",
      "property_name": "string",
      "value": "any"
    }
  },
  {
    "name": "add_keyframe_to_effect",
    "description": "添加效果关键帧",
    "inputSchema": {
      "layer": "string",
      "effect_index": "number",
      "property_name": "string",
      "time": "number",
      "value": "any",
      "easing": "string"
    }
  }
]
```

#### 4.3.2 BeatEdit集成工具（4个新增）

```json
[
  {
    "name": "beatedit_analyze",
    "description": "分析音频节拍"
  },
  {
    "name": "beatedit_create_markers",
    "description": "创建节拍标记"
  },
  {
    "name": "beatedit_apply_animation",
    "description": "应用节拍动画"
  },
  {
    "name": "beatedit_sync_keyframes",
    "description": "同步关键帧到节拍"
  }
]
```

---

## 第五章 执行层集成

### 5.1 ExtendScript执行环境

**ES3语法规范**：
- 使用 `var` 而非 `let/const`
- 无箭头函数
- 无模板字符串
- 无 `Promise/async/await`

**示例代码**：
```javascript
// ES3兼容代码
(function() {
    var comp = app.project.activeItem;
    if (!(comp instanceof CompItem)) {
        alert("请先打开一个合成");
        return;
    }

    var layer = comp.selectedLayers[0];
    if (!layer) {
        alert("请先选择一个图层");
        return;
    }

    // 添加效果
    var effect = layer.Effects.addProperty("ADBE Glo2");
    effect.property(1).setValue(0.5);  // Glow Threshold
    effect.property(2).setValue(1.0);  // Glow Radius
    effect.property(3).setValue([1, 0.8, 0]);  // Color RGB
})();
```

### 5.2 效果matchName映射表

| 效果名称 | matchName | 属性数 |
|---------|-----------|--------|
| Glow | ADBE Glo2 | 5 |
| Gaussian Blur | ADBE Gaussian Blur | 1 |
| Hue/Saturation | ADBE HUE SATURATION | 5 |
| Levels | ADBE Easy Levels2 | 6 |
| Curves | ADBE CurvesCustom | 2 |
| Fast Blur | ADBE Camera Lens Blur | 8 |
| Motion Blur | ADBE Motion Blur | 0 |
| Drop Shadow | ADBE Drop Shadow | 6 |
| Fill | ADBE Fill | 2 |
| Noise | ADBE Noise | 3 |

### 5.3 关键帧缓动映射

```javascript
// 缓动类型到KeyframeEase映射
var EASING_MAP = {
    "linear": [new KeyframeEase(0, 33), new KeyframeEase(0, 33)],
    "easeIn": [new KeyframeEase(0.5, 33), new KeyframeEase(0, 33)],
    "easeOut": [new KeyframeEase(0, 33), new KeyframeEase(0.5, 33)],
    "easeInOut": [new KeyframeEase(0.5, 33), new KeyframeEase(0.5, 33)],
    "bezier_0.2_0.8": [new KeyframeEase(0.2, 75), new KeyframeEase(0.8, 75)]
};
```

---

## 第六章 集成测试规范

### 6.1 测试套件

**测试文件**：[MCP_FullTestSuite.jsx](../05-测试套件/MCP_FullTestSuite.jsx)

**测试覆盖**：
- 22个MCP工具功能测试
- 效果添加与属性设置测试
- 关键帧缓动测试
- 错误处理测试

### 6.2 验证流程

```powershell
# 1. 启动MCP Server
cd puppet-automation
py -3.11 api_server.py

# 2. 运行测试套件
cd AE-Scripts/ScriptUI Panels
# 在AE中运行 MCP_FullTestSuite.jsx

# 3. 检查结果
# 查看 ae_mcp_result.json
```

---

## 第七章 快速参考

### 7.1 常用脚本模板

#### 创建合成
```javascript
app.beginUndoGroup("Create Composition");
var comp = app.project.items.addComp(
    "My Comp",  // 名称
    1920,       // 宽度
    1080,       // 高度
    1,          // 像素比
    30,         // 帧率
    10          // 时长（秒）
);
app.endUndoGroup();
```

#### 添加效果
```javascript
app.beginUndoGroup("Add Glow");
var layer = comp.selectedLayers[0];
var effect = layer.Effects.addProperty("ADBE Glo2");
effect.property(1).setValue(0.5);
app.endUndoGroup();
```

#### 设置关键帧
```javascript
app.beginUndoGroup("Add Keyframe");
var prop = layer.property("Transform").property("Position");
prop.setValueAtTime(0, [960, 540]);
prop.setValueAtTime(1, [1920, 540]);

var easeIn = new KeyframeEase(0.5, 33);
var easeOut = new KeyframeEase(0.5, 33);
prop.setTemporalEaseAtKey(1, [easeIn, easeIn], [easeOut, easeOut]);
app.endUndoGroup();
```

### 7.2 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 脚本不执行 | 未在白名单 | 添加到 allowedScripts |
| 属性设置失败 | matchName错误 | 查询映射手册 |
| 关键帧错误 | 维度不匹配 | 检查属性维度 |
| 编码错误 | 中文路径 | 使用英文路径 |

---

> 返回 → [[🏠-AE知识中心]]
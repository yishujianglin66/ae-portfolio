---
title: MCP→AE效果操作桥接规范
date: 2026-07-05
tags:
  - MCP
  - 桥接
  - 协议
  - 效果操作
  - 自动化
---
# MCP→AE效果操作桥接规范

> [!abstract] 文档摘要
> 本文档规范了MCP Server与After Effects之间的桥接通信协议，涵盖现有架构分析、MCP工具扩展规范、Bridge通信协议升级和端到端效果操作调用链。从命令文件格式到结果文件格式，从错误码定义到超时重试策略，提供了完整的桥接层技术规范，是"知识编译→AE执行"传输层的基础协议文档。

> [!tip] 使用指南
> - MCP开发者：从第一章开始，理解现有架构后按第二章扩展新工具
> - Bridge面板开发者：重点关注第三章通信协议扩展
> - 自动化引擎集成者：第四章的端到端调用链是核心参考
> - 故障排查：第三章的错误码定义和超时重试策略

---

## 第一章 现有MCP架构分析

### 1.1 通信流程概述

After Effects MCP项目的核心通信架构采用"命令文件轮询"模式，整个数据流如下：

```
┌──────────────┐     写命令      ┌──────────────────┐    轮询读取     ┌───────────────────┐
│  Node.js     │ ──────────────→ │  ae_command.json │ ──────────────→ │  AE Bridge 面板   │
│  MCP Server  │                 │  (命令文件)       │                 │  (CEP/ScriptUI)    │
└──────┬───────┘                 └──────────────────┘                 └────────┬──────────┘
       │                                                                        │
       │                        ┌──────────────────┐                            │ evalScript()
       │    读取结果             │  ae_mcp_result   │ ←──────── 写结果 ────────── │
       │ ←───────────────────── │  .json (结果文件) │                             │
       │                        └──────────────────┘                             │
       │                                                                        ▼
       │                                                              ┌──────────────────┐
       │                                                              │  ExtendScript     │
       │                                                              │  (JSX 执行引擎)   │
       │                                                              └──────────────────┘
```

**详细步骤分解**：

1. **MCP Server接收请求**：AI助手（如Claude、Cursor）通过MCP协议发送工具调用请求
2. **命令写入**：Node.js MCP Server将命令参数序列化为JSON，写入`ae_command.json`文件
3. **Bridge轮询**：AE Bridge面板以固定间隔（默认250ms）轮询`ae_command.json`文件
4. **命令解析**：Bridge读取命令，验证allowedScripts白名单，解析参数
5. **ExtendScript执行**：通过`evalScript()`调用对应的JSX脚本
6. **结果写入**：JSX执行完毕，将返回值序列化为JSON写入`ae_mcp_result.json`
7. **结果读取**：MCP Server读取结果文件，提取返回数据，响应给调用方

### 1.2 22个allowedScripts清单

现有MCP Server定义了以下22个允许执行的脚本（白名单机制确保安全性）：

| # | 脚本名称 | MCP工具名 | 功能说明 |
|---|---------|-----------|---------|
| 1 | createComposition.jsx | create-composition | 创建新合成 |
| 2 | getProjectDetails.jsx | get-project-details | 获取项目详情 |
| 3 | listCompositions.jsx | list-compositions | 列出所有合成 |
| 4 | createTextLayer.jsx | create-text-layer | 创建文字图层 |
| 5 | createShapeLayer.jsx | create-shape-layer | 创建形状图层 |
| 6 | createSolidLayer.jsx | create-solid-layer | 创建纯色图层 |
| 7 | createCamera.jsx | create-camera | 创建摄像机图层 |
| 8 | createNullObject.jsx | create-null-object | 创建空对象图层 |
| 9 | duplicateLayer.jsx | duplicate-layer | 复制图层 |
| 10 | deleteLayer.jsx | delete-layer | 删除图层 |
| 11 | setLayerKeyframe.jsx | setLayerKeyframe | 设置图层关键帧 |
| 12 | setLayerExpression.jsx | setLayerExpression | 设置图层表达式 |
| 13 | setLayerProperties.jsx | setLayerProperties | 设置图层属性 |
| 14 | batchSetLayerProperties.jsx | batchSetLayerProperties | 批量设置图层属性 |
| 15 | getLayerInfo.jsx | getLayerInfo | 获取图层信息 |
| 16 | setLayerMask.jsx | setLayerMask | 设置图层遮罩 |
| 17 | runScript.jsx | run-script | 执行自定义脚本 |
| 18 | getHelp.jsx | get-help | 获取帮助信息 |
| 19 | getResults.jsx | get-results | 获取执行结果 |
| 20 | createAdjustmentLayer.jsx | create-adjustment-layer | 创建调整图层 |
| 21 | toggle3DLayer.jsx | toggle-3d-layer | 切换3D图层模式 |
| 22 | setBlendMode.jsx | set-blend-mode | 设置混合模式 |

### 1.3 每个脚本的参数Schema和返回Schema

#### 1.3.1 createComposition.jsx

**参数Schema**：
```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string", "default": "Comp 1" },
    "width": { "type": "number", "default": 1920 },
    "height": { "type": "number", "default": 1080 },
    "frameRate": { "type": "number", "default": 30 },
    "duration": { "type": "number", "default": 10 },
    "bgColor": { "type": "array", "items": { "type": "number" }, "default": [0, 0, 0] }
  },
  "required": []
}
```

**返回Schema**：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "compositionName": { "type": "string" },
    "width": { "type": "number" },
    "height": { "type": "number" },
    "frameRate": { "type": "number" },
    "duration": { "type": "number" }
  }
}
```

#### 1.3.2 createTextLayer.jsx

**参数Schema**：
```json
{
  "type": "object",
  "properties": {
    "compName": { "type": "string" },
    "text": { "type": "string" },
    "fontSize": { "type": "number", "default": 72 },
    "fontFamily": { "type": "string", "default": "Arial" },
    "fillColor": { "type": "array", "items": { "type": "number" }, "default": [255, 255, 255] },
    "position": { "type": "array", "items": { "type": "number" }, "default": [960, 540] }
  },
  "required": ["compName", "text"]
}
```

**返回Schema**：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "layerName": { "type": "string" },
    "layerIndex": { "type": "number" }
  }
}
```

#### 1.3.3 createShapeLayer.jsx

**参数Schema**：
```json
{
  "type": "object",
  "properties": {
    "compName": { "type": "string" },
    "shapeType": { "type": "string", "enum": ["rectangle", "ellipse", "polygon", "star"] },
    "fillColor": { "type": "array", "items": { "type": "number" } },
    "strokeColor": { "type": "array", "items": { "type": "number" } },
    "strokeWidth": { "type": "number", "default": 0 },
    "size": { "type": "array", "items": { "type": "number" } },
    "position": { "type": "array", "items": { "type": "number" } }
  },
  "required": ["compName", "shapeType"]
}
```

**返回Schema**：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "layerName": { "type": "string" },
    "layerIndex": { "type": "number" }
  }
}
```

#### 1.3.4 setLayerKeyframe.jsx

**参数Schema**：
```json
{
  "type": "object",
  "properties": {
    "compName": { "type": "string" },
    "layerIndex": { "type": "number" },
    "propertyPath": { "type": "string", "description": "如 'transform.position'" },
    "keyframeTime": { "type": "number" },
    "keyframeValue": { "type": "array", "items": { "type": "number" } },
    "easingType": { "type": "string", "enum": ["linear", "easeIn", "easeOut", "easeInOut", "bezier"] }
  },
  "required": ["compName", "layerIndex", "propertyPath", "keyframeTime", "keyframeValue"]
}
```

**返回Schema**：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "keyframeIndex": { "type": "number" },
    "propertyPath": { "type": "string" }
  }
}
```

#### 1.3.5 setLayerExpression.jsx

**参数Schema**：
```json
{
  "type": "object",
  "properties": {
    "compName": { "type": "string" },
    "layerIndex": { "type": "number" },
    "propertyPath": { "type": "string" },
    "expression": { "type": "string" }
  },
  "required": ["compName", "layerIndex", "propertyPath", "expression"]
}
```

**返回Schema**：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "propertyPath": { "type": "string" },
    "expressionApplied": { "type": "boolean" }
  }
}
```

#### 1.3.6 setLayerProperties.jsx

**参数Schema**：
```json
{
  "type": "object",
  "properties": {
    "compName": { "type": "string" },
    "layerIndex": { "type": "number" },
    "properties": {
      "type": "object",
      "properties": {
        "position": { "type": "array", "items": { "type": "number" } },
        "scale": { "type": "array", "items": { "type": "number" } },
        "rotation": { "type": "number" },
        "opacity": { "type": "number" },
        "blendMode": { "type": "string" },
        "threeDLayer": { "type": "boolean" },
        "trackMatteType": { "type": "string" },
        "enabled": { "type": "boolean" }
      }
    }
  },
  "required": ["compName", "layerIndex"]
}
```

**返回Schema**：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "updatedProperties": { "type": "array", "items": { "type": "string" } }
  }
}
```

#### 1.3.7 getLayerInfo.jsx

**参数Schema**：
```json
{
  "type": "object",
  "properties": {
    "compName": { "type": "string" },
    "layerIndex": { "type": "number" }
  },
  "required": ["compName", "layerIndex"]
}
```

**返回Schema**：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "layerName": { "type": "string" },
    "layerType": { "type": "string" },
    "position": { "type": "array", "items": { "type": "number" } },
    "scale": { "type": "array", "items": { "type": "number" } },
    "rotation": { "type": "number" },
    "opacity": { "type": "number" },
    "is3D": { "type": "boolean" },
    "blendMode": { "type": "string" },
    "effects": { "type": "array", "items": { "type": "object" } }
  }
}
```

#### 1.3.8 setLayerMask.jsx

**参数Schema**：
```json
{
  "type": "object",
  "properties": {
    "compName": { "type": "string" },
    "layerIndex": { "type": "number" },
    "maskMode": { "type": "string", "enum": ["add", "subtract", "intersect", "difference"] },
    "maskFeather": { "type": "array", "items": { "type": "number" }, "default": [0, 0] },
    "maskExpansion": { "type": "number", "default": 0 },
    "maskOpacity": { "type": "number", "default": 100 },
    "vertices": { "type": "array", "items": { "type": "object" } }
  },
  "required": ["compName", "layerIndex"]
}
```

**返回Schema**：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "maskIndex": { "type": "number" }
  }
}
```

#### 1.3.9 其余脚本Schema汇总

其余脚本（createSolidLayer、createCamera、createNullObject、duplicateLayer、deleteLayer、batchSetLayerProperties、createAdjustmentLayer、toggle3DLayer、setBlendMode、runScript、getHelp、getResults、getProjectDetails、listCompositions）遵循相同的模式：

```json
{
  "参数Schema通用结构": {
    "compName": "目标合成名（必填）",
    "layerIndex": "目标图层索引（操作图层时必填）",
    "...": "各脚本特有参数"
  },
  "返回Schema通用结构": {
    "success": "boolean，操作是否成功",
    "errorCode": "string，失败时的错误码",
    "errorMessage": "string，失败时的错误描述",
    "...": "各脚本特有返回值"
  }
}
```

**runScript特殊说明**：

`runScript.jsx` 是最灵活的工具，可以执行任意ExtendScript代码，其参数Schema：

```json
{
  "type": "object",
  "properties": {
    "scriptContent": {
      "type": "string",
      "description": "要执行的ExtendScript代码"
    }
  },
  "required": ["scriptContent"]
}
```

返回Schema：
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "output": { "type": "string", "description": "脚本输出（通过$.writeln或返回值）" },
    "error": { "type": "string", "description": "错误信息（如有）" }
  }
}
```

### 1.4 性能特征

| 性能指标 | 当前值 | 说明 |
|---------|--------|------|
| 轮询间隔 | 250ms | Bridge面板检查命令文件的频率 |
| 命令超时 | 5000ms | MCP Server等待结果的最长时间 |
| 文件写入延迟 | <10ms | Node.js写入JSON文件耗时 |
| 文件读取延迟 | <10ms | Bridge读取JSON文件耗时 |
| ExtendScript执行延迟 | 50-2000ms | 取决于脚本复杂度 |
| 端到端延迟 | 300-5260ms | 从MCP调用到返回结果的完整时间 |
| 并发支持 | 不支持 | 同一时间只能处理一个命令 |

**性能瓶颈分析**：

```
用户发起请求 (0ms)
  │
  ├── MCP Server写命令文件 (+5ms)
  │
  ├── 等待Bridge轮询 (0~250ms, 平均125ms)
  │
  ├── Bridge读取+解析命令 (+5ms)
  │
  ├── evalScript()执行JSX (50~2000ms)
  │
  ├── Bridge写结果文件 (+5ms)
  │
  ├── MCP Server读结果文件 (+5ms)
  │
  └── 返回结果给用户

最佳情况: ~70ms
典型情况: ~200-500ms
最差情况: ~5260ms (超时)
```

---

## 第二章 MCP工具扩展规范

### 2.1 扩展工具总览

为支持完整的效果操作能力，需要新增以下14个MCP工具，补充现有22个工具的不足：

| # | 新工具名 | 对应JSX | 功能 | 参数 |
|---|---------|---------|------|------|
| 1 | add-effect-with-keyframes | addEffectWithKeyframes.jsx | 添加效果+关键帧 | effectMatchName, settings, keyframes[] |
| 2 | set-keyframe-easing | setKeyframeEasing.jsx | 设置关键帧缓动 | propertyPath, keyIndex, easingType, easeIn, easeOut |
| 3 | batch-add-effects | batchAddEffects.jsx | 批量添加效果 | effects[] |
| 4 | set-blend-mode | setBlendMode.jsx | 设置混合模式 | layerIndex, blendMode |
| 5 | set-track-matte | setTrackMatte.jsx | 设置轨道遮罩 | layerIndex, matteType |
| 6 | set-parent-layer | setParentLayer.jsx | 设置父子关系 | layerIndex, parentIndex |
| 7 | add-adjustment-layer | addAdjustmentLayer.jsx | 创建调整层 | name, position |
| 8 | add-precomp | addPrecomp.jsx | 创建预合成 | name, layerIndices[] |
| 9 | import-footage | importFootage.jsx | 导入素材 | filePath |
| 10 | set-motion-blur | setMotionBlur.jsx | 设置运动模糊 | layerIndex, enabled, shutterAngle |
| 11 | add-mask-with-shape | addMaskWithShape.jsx | 添加遮罩 | layerIndex, vertices[], feather, mode |
| 12 | execute-atom-script | executeAtomScript.jsx | 执行原子参数编译后的脚本 | scriptContent |
| 13 | get-effect-properties | getEffectProperties.jsx | 获取效果所有属性 | layerIndex, effectIndex |
| 14 | set-effect-keyframes | setEffectKeyframes.jsx | 设置效果属性关键帧 | layerIndex, effectIndex, propName, keyframes[] |

### 2.2 工具1：add-effect-with-keyframes

#### 2.2.1 完整参数Schema

```json
{
  "name": "add-effect-with-keyframes",
  "description": "向指定图层添加效果并设置关键帧动画",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": {
        "type": "string",
        "description": "目标合成名称"
      },
      "layerIndex": {
        "type": "number",
        "description": "目标图层索引（1-based）"
      },
      "effectMatchName": {
        "type": "string",
        "description": "效果的matchName，如 'ADBE Gaussian Blur 2'、'ADBE Glo2'"
      },
      "settings": {
        "type": "object",
        "description": "效果的初始参数设置",
        "additionalProperties": {
          "oneOf": [
            { "type": "number" },
            { "type": "string" },
            { "type": "array", "items": { "type": "number" } }
          ]
        }
      },
      "keyframes": {
        "type": "array",
        "description": "关键帧列表",
        "items": {
          "type": "object",
          "properties": {
            "propertyName": {
              "type": "string",
              "description": "效果内的属性名，如 'Blurriness'"
            },
            "time": {
              "type": "number",
              "description": "关键帧时间（秒）"
            },
            "value": {
              "oneOf": [
                { "type": "number" },
                { "type": "array", "items": { "type": "number" } }
              ],
              "description": "关键帧值"
            },
            "easingType": {
              "type": "string",
              "enum": ["linear", "easeIn", "easeOut", "easeInOut", "bezier"],
              "default": "linear"
            }
          },
          "required": ["propertyName", "time", "value"]
        }
      }
    },
    "required": ["compName", "layerIndex", "effectMatchName"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "effectIndex": { "type": "number" },
      "effectName": { "type": "string" },
      "keyframesAdded": { "type": "number" }
    }
  }
}
```

#### 2.2.2 JSX脚本框架代码

```javascript
// addEffectWithKeyframes.jsx
(function() {
  // 从命令参数中获取数据
  var params = __commandParams__; // Bridge注入的参数对象

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101: 没有活动合成" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102: 图层索引无效" });
  }

  app.beginUndoGroup("Add Effect With Keyframes");

  try {
    // 添加效果
    var effect = layer.Effects.addProperty(params.effectMatchName);
    var effectIndex = effect.propertyIndex;

    // 设置初始参数
    if (params.settings) {
      for (var propName in params.settings) {
        if (params.settings.hasOwnProperty(propName)) {
          var prop = effect.property(propName);
          if (prop && prop.canSetExpression === false || prop.canSetValue) {
            var val = params.settings[propName];
            if (prop.propertyValueType === PropertyValueType.COLOR) {
              prop.setValue(val);
            } else if (prop.propertyValueType === PropertyValueType.TwoD ||
                       prop.propertyValueType === PropertyValueType.ThreeD) {
              prop.setValue(val);
            } else {
              prop.setValue(val);
            }
          }
        }
      }
    }

    // 添加关键帧
    var keyframesAdded = 0;
    if (params.keyframes && params.keyframes.length > 0) {
      for (var i = 0; i < params.keyframes.length; i++) {
        var kf = params.keyframes[i];
        var prop = effect.property(kf.propertyName);
        if (prop) {
          var timeObj = kf.time;
          var valueObj = kf.value;

          // 添加关键帧
          if (prop.canSetValue) {
            prop.setValueAtTime(timeObj, valueObj);
            keyframesAdded++;

            // 设置缓动
            if (kf.easingType && kf.easingType !== "linear") {
              var kfIndex = prop.nearestKeyIndex(timeObj);
              var keyInInterp, keyOutInterp;

              switch (kf.easingType) {
                case "easeIn":
                  keyInInterp = KeyframeInterpolationType.BEZIER;
                  keyOutInterp = KeyframeInterpolationType.LINEAR;
                  break;
                case "easeOut":
                  keyInInterp = KeyframeInterpolationType.LINEAR;
                  keyOutInterp = KeyframeInterpolationType.BEZIER;
                  break;
                case "easeInOut":
                  keyInInterp = KeyframeInterpolationType.BEZIER;
                  keyOutInterp = KeyframeInterpolationType.BEZIER;
                  break;
                default:
                  keyInInterp = KeyframeInterpolationType.LINEAR;
                  keyOutInterp = KeyframeInterpolationType.LINEAR;
              }

              prop.setInterpolationTypeAtKey(kfIndex, keyInInterp, keyOutInterp);
            }
          }
        }
      }
    }

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      effectIndex: effectIndex,
      effectName: effect.name,
      keyframesAdded: keyframesAdded
    });

  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({
      success: false,
      error: "E200: " + e.toString()
    });
  }
})();
```

#### 2.2.3 MCP注册代码片段

```typescript
// 在 src/index.ts 中注册工具
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    // ... 现有工具 ...
    {
      name: "add-effect-with-keyframes",
      description: "向指定图层添加效果并设置关键帧动画。effectMatchName示例：'ADBE Gaussian Blur 2'(高斯模糊)、'ADBE Glo2'(发光)、'ADBE Lens Blur'(镜头模糊)",
      inputSchema: {
        type: "object",
        properties: {
          compName: { type: "string", description: "目标合成名称" },
          layerIndex: { type: "number", description: "目标图层索引（1-based）" },
          effectMatchName: { type: "string", description: "效果的matchName" },
          settings: { type: "object", description: "效果的初始参数设置" },
          keyframes: {
            type: "array",
            items: {
              type: "object",
              properties: {
                propertyName: { type: "string" },
                time: { type: "number" },
                value: { type: "number" },
                easingType: { type: "string", enum: ["linear", "easeIn", "easeOut", "easeInOut"] }
              },
              required: ["propertyName", "time", "value"]
            }
          }
        },
        required: ["compName", "layerIndex", "effectMatchName"]
      }
    }
  ]
}));
```

### 2.3 工具2：set-keyframe-easing

#### 2.3.1 完整参数Schema

```json
{
  "name": "set-keyframe-easing",
  "description": "设置指定关键帧的缓动曲线类型和缓动参数",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string", "description": "目标合成名称" },
      "layerIndex": { "type": "number", "description": "目标图层索引" },
      "propertyPath": {
        "type": "string",
        "description": "属性路径，如 'transform.position' 或 'effect(\"Gaussian Blur\")(1)'"
      },
      "keyIndex": { "type": "number", "description": "关键帧索引（1-based）" },
      "easingType": {
        "type": "string",
        "enum": ["linear", "easeIn", "easeOut", "easeInOut", "bezier", "hold"],
        "description": "缓动类型"
      },
      "easeIn": {
        "type": "object",
        "description": "入缓动参数（贝塞尔控制点）",
        "properties": {
          "speed": { "type": "number", "default": 0 },
          "influence": { "type": "number", "default": 33 }
        }
      },
      "easeOut": {
        "type": "object",
        "description": "出缓动参数（贝塞尔控制点）",
        "properties": {
          "speed": { "type": "number", "default": 0 },
          "influence": { "type": "number", "default": 33 }
        }
      }
    },
    "required": ["compName", "layerIndex", "propertyPath", "keyIndex", "easingType"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "propertyPath": { "type": "string" },
      "keyIndex": { "type": "number" },
      "appliedEasing": { "type": "string" }
    }
  }
}
```

#### 2.3.2 JSX脚本框架代码

```javascript
// setKeyframeEasing.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  app.beginUndoGroup("Set Keyframe Easing");

  try {
    // 解析属性路径
    var prop = layer;
    var pathParts = params.propertyPath.split(".");
    for (var i = 0; i < pathParts.length; i++) {
      prop = prop.property(pathParts[i]);
      if (!prop) {
        return JSON.stringify({ success: false, error: "E103: 属性路径无效" });
      }
    }

    var keyIndex = params.keyIndex;
    if (keyIndex < 1 || keyIndex > prop.numKeys) {
      return JSON.stringify({ success: false, error: "E104: 关键帧索引超出范围" });
    }

    var inInterp, outInterp;

    switch (params.easingType) {
      case "linear":
        inInterp = KeyframeInterpolationType.LINEAR;
        outInterp = KeyframeInterpolationType.LINEAR;
        break;
      case "easeIn":
        inInterp = KeyframeInterpolationType.BEZIER;
        outInterp = KeyframeInterpolationType.LINEAR;
        break;
      case "easeOut":
        inInterp = KeyframeInterpolationType.LINEAR;
        outInterp = KeyframeInterpolationType.BEZIER;
        break;
      case "easeInOut":
        inInterp = KeyframeInterpolationType.BEZIER;
        outInterp = KeyframeInterpolationType.BEZIER;
        break;
      case "hold":
        inInterp = KeyframeInterpolationType.HOLD;
        outInterp = KeyframeInterpolationType.HOLD;
        break;
      case "bezier":
        inInterp = KeyframeInterpolationType.BEZIER;
        outInterp = KeyframeInterpolationType.BEZIER;
        break;
      default:
        inInterp = KeyframeInterpolationType.LINEAR;
        outInterp = KeyframeInterpolationType.LINEAR;
    }

    prop.setInterpolationTypeAtKey(keyIndex, inInterp, outInterp);

    // 设置贝塞尔缓动参数
    if (params.easingType === "bezier" || params.easingType === "easeIn" ||
        params.easingType === "easeOut" || params.easingType === "easeInOut") {

      var easeInObj = params.easeIn || { speed: 0, influence: 33 };
      var easeOutObj = params.easeOut || { speed: 0, influence: 33 };

      if (prop.propertyValueType === PropertyValueType.TwoD) {
        var inEase = [
          new KeyframeEase(easeInObj.speed, easeInObj.influence),
          new KeyframeEase(easeInObj.speed, easeInObj.influence)
        ];
        var outEase = [
          new KeyframeEase(easeOutObj.speed, easeOutObj.influence),
          new KeyframeEase(easeOutObj.speed, easeOutObj.influence)
        ];
        prop.setTemporalEaseAtKey(keyIndex, inEase, outEase);
      } else if (prop.propertyValueType === PropertyValueType.ThreeD) {
        var inEase3 = [
          new KeyframeEase(easeInObj.speed, easeInObj.influence),
          new KeyframeEase(easeInObj.speed, easeInObj.influence),
          new KeyframeEase(easeInObj.speed, easeInObj.influence)
        ];
        var outEase3 = [
          new KeyframeEase(easeOutObj.speed, easeOutObj.influence),
          new KeyframeEase(easeOutObj.speed, easeOutObj.influence),
          new KeyframeEase(easeOutObj.speed, easeOutObj.influence)
        ];
        prop.setTemporalEaseAtKey(keyIndex, inEase3, outEase3);
      } else {
        var inEase1 = [new KeyframeEase(easeInObj.speed, easeInObj.influence)];
        var outEase1 = [new KeyframeEase(easeOutObj.speed, easeOutObj.influence)];
        prop.setTemporalEaseAtKey(keyIndex, inEase1, outEase1);
      }
    }

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      propertyPath: params.propertyPath,
      keyIndex: keyIndex,
      appliedEasing: params.easingType
    });

  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.3.3 MCP注册代码片段

```typescript
{
  name: "set-keyframe-easing",
  description: "设置指定关键帧的缓动曲线。支持linear/easeIn/easeOut/easeInOut/bezier/hold六种缓动类型",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string", description: "目标合成名称" },
      layerIndex: { type: "number", description: "目标图层索引" },
      propertyPath: { type: "string", description: "属性路径" },
      keyIndex: { type: "number", description: "关键帧索引" },
      easingType: {
        type: "string",
        enum: ["linear", "easeIn", "easeOut", "easeInOut", "bezier", "hold"]
      },
      easeIn: {
        type: "object",
        properties: {
          speed: { type: "number" },
          influence: { type": "number" }
        }
      },
      easeOut: {
        type: "object",
        properties: {
          speed: { type": "number" },
          influence: { type": "number" }
        }
      }
    },
    required: ["compName", "layerIndex", "propertyPath", "keyIndex", "easingType"]
  }
}
```

### 2.4 工具3：batch-add-effects

#### 2.4.1 完整参数Schema

```json
{
  "name": "batch-add-effects",
  "description": "批量向指定图层添加多个效果，支持效果参数预设",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string", "description": "目标合成名称" },
      "layerIndex": { "type": "number", "description": "目标图层索引" },
      "effects": {
        "type": "array",
        "description": "要添加的效果列表",
        "items": {
          "type": "object",
          "properties": {
            "effectMatchName": { "type": "string", "description": "效果matchName" },
            "settings": {
              "type": "object",
              "description": "效果参数",
              "additionalProperties": true
            }
          },
          "required": ["effectMatchName"]
        }
      }
    },
    "required": ["compName", "layerIndex", "effects"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "addedEffects": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "effectMatchName": { "type": "string" },
            "effectIndex": { "type": "number" },
            "effectName": { "type": "string" }
          }
        }
      }
    }
  }
}
```

#### 2.4.2 JSX脚本框架代码

```javascript
// batchAddEffects.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  app.beginUndoGroup("Batch Add Effects");

  try {
    var addedEffects = [];

    for (var i = 0; i < params.effects.length; i++) {
      var effectDef = params.effects[i];
      var effect = layer.Effects.addProperty(effectDef.effectMatchName);

      // 设置参数
      if (effectDef.settings) {
        for (var propName in effectDef.settings) {
          if (effectDef.settings.hasOwnProperty(propName)) {
            var prop = effect.property(propName);
            if (prop && prop.canSetValue) {
              prop.setValue(effectDef.settings[propName]);
            }
          }
        }
      }

      addedEffects.push({
        effectMatchName: effectDef.effectMatchName,
        effectIndex: effect.propertyIndex,
        effectName: effect.name
      });
    }

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      addedEffects: addedEffects
    });

  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.4.3 MCP注册代码片段

```typescript
{
  name: "batch-add-effects",
  description: "批量向指定图层添加多个效果。适用于需要叠加多个效果的风格化操作，如同时添加模糊+发光+调色",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      layerIndex: { type: "number" },
      effects: {
        type: "array",
        items: {
          type: "object",
          properties: {
            effectMatchName: { type": "string" },
            settings: { type": "object" }
          },
          required: ["effectMatchName"]
        }
      }
    },
    required: ["compName", "layerIndex", "effects"]
  }
}
```

### 2.5 工具4：set-blend-mode

#### 2.5.1 完整参数Schema

```json
{
  "name": "set-blend-mode",
  "description": "设置图层的混合模式",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string" },
      "layerIndex": { "type": "number" },
      "blendMode": {
        "type": "string",
        "enum": [
          "NONE", "DISSOLVE", "DANCING_DISSOLVE",
          "DARKEN", "MULTIPLY", "COLOR_BURN", "CLASSIC_COLOR_BURN", "LINEAR_BURN", "DARKER_COLOR",
          "ADD", "LIGHTEN", "SCREEN", "COLOR_DODGE", "CLASSIC_COLOR_DODGE", "LINEAR_DODGE", "LIGHTER_COLOR",
          "OVERLAY", "SOFT_LIGHT", "HARD_LIGHT", "LINEAR_LIGHT", "VIVID_LIGHT", "PIN_LIGHT", "HARD_MIX",
          "DIFFERENCE", "CLASSIC_DIFFERENCE", "EXCLUSION", "SUBTRACT", "DIVIDE",
          "HUE", "SATURATION", "COLOR", "LUMINOSITY",
          "STENCIL_ALPHA", "STENCIL_LUMA", "SILHOUETTE_ALPHA", "SILHOUETTE_LUMA",
          "ALPHA_ADD", "ALPHA_SILHOUETTE", "LUMINESCENT_PREMUL"
        ]
      }
    },
    "required": ["compName", "layerIndex", "blendMode"]
  }
}
```

#### 2.5.2 JSX脚本框架代码

```javascript
// setBlendMode.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  try {
    var blendModeMap = {
      "NONE": BlendingMode.NORMAL,
      "DISSOLVE": BlendingMode.DISSOLVE,
      "MULTIPLY": BlendingMode.MULTIPLY,
      "SCREEN": BlendingMode.SCREEN,
      "OVERLAY": BlendingMode.OVERLAY,
      "SOFT_LIGHT": BlendingMode.SOFT_LIGHT,
      "HARD_LIGHT": BlendingMode.HARD_LIGHT,
      "ADD": BlendingMode.ADD,
      "COLOR_DODGE": BlendingMode.COLOR_DODGE,
      "COLOR_BURN": BlendingMode.COLOR_BURN,
      "DARKEN": BlendingMode.DARKEN,
      "LIGHTEN": BlendingMode.LIGHTEN,
      "DIFFERENCE": BlendingMode.DIFFERENCE,
      "EXCLUSION": BlendingMode.EXCLUSION,
      "HUE": BlendingMode.HUE,
      "SATURATION": BlendingMode.SATURATION,
      "COLOR": BlendingMode.COLOR,
      "LUMINOSITY": BlendingMode.LUMINOSITY
    };

    var mode = blendModeMap[params.blendMode];
    if (mode === undefined) {
      return JSON.stringify({ success: false, error: "E105: 不支持的混合模式" });
    }

    layer.blendingMode = mode;

    return JSON.stringify({
      success: true,
      layerIndex: params.layerIndex,
      blendMode: params.blendMode
    });

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.5.3 MCP注册代码片段

```typescript
{
  name: "set-blend-mode",
  description: "设置图层混合模式。常用：SCREEN(滤色/发光叠加)、MULTIPLY(正片叠底/暗部叠加)、ADD(相加/光效叠加)、OVERLAY(叠加/对比增强)",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      layerIndex: { type: "number" },
      blendMode: { type: "string" }
    },
    required: ["compName", "layerIndex", "blendMode"]
  }
}
```

### 2.6 工具5：set-track-matte

#### 2.6.1 完整参数Schema

```json
{
  "name": "set-track-matte",
  "description": "设置图层的轨道遮罩类型",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string" },
      "layerIndex": { "type": "number" },
      "matteType": {
        "type": "string",
        "enum": [
          "NO_TRACK_MATTE",
          "ALPHA_TRACK_MATTE",
          "ALPHA_INVERTED_TRACK_MATTE",
          "LUMA_TRACK_MATTE",
          "LUMA_INVERTED_TRACK_MATTE"
        ],
        "description": "遮罩类型：ALPHA(Alpha遮罩)、LUMA(亮度遮罩)、INVERTED(反转)"
      }
    },
    "required": ["compName", "layerIndex", "matteType"]
  }
}
```

#### 2.6.2 JSX脚本框架代码

```javascript
// setTrackMatte.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  try {
    var matteMap = {
      "NO_TRACK_MATTE": TrackMatteType.NO_TRACK_MATTE,
      "ALPHA_TRACK_MATTE": TrackMatteType.ALPHA,
      "ALPHA_INVERTED_TRACK_MATTE": TrackMatteType.ALPHA_INVERTED,
      "LUMA_TRACK_MATTE": TrackMatteType.LUMA,
      "LUMA_INVERTED_TRACK_MATTE": TrackMatteType.LUMA_INVERTED
    };

    var matteType = matteMap[params.matteType];
    if (matteType === undefined) {
      return JSON.stringify({ success: false, error: "E106: 不支持的轨道遮罩类型" });
    }

    layer.trackMatteType = matteType;

    return JSON.stringify({
      success: true,
      layerIndex: params.layerIndex,
      matteType: params.matteType
    });

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.6.3 MCP注册代码片段

```typescript
{
  name: "set-track-matte",
  description: "设置图层轨道遮罩。ALPHA遮罩用上层Alpha通道，LUMA遮罩用上层亮度值。遮罩层需在目标图层上方",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      layerIndex: { type: "number" },
      matteType: {
        type: "string",
        enum: ["NO_TRACK_MATTE", "ALPHA_TRACK_MATTE", "ALPHA_INVERTED_TRACK_MATTE",
               "LUMA_TRACK_MATTE", "LUMA_INVERTED_TRACK_MATTE"]
      }
    },
    required: ["compName", "layerIndex", "matteType"]
  }
}
```

### 2.7 工具6：set-parent-layer

#### 2.7.1 完整参数Schema

```json
{
  "name": "set-parent-layer",
  "description": "设置图层的父子关系，使子图层跟随父图层变换",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string" },
      "layerIndex": { "type": "number", "description": "子图层索引" },
      "parentIndex": { "type": "number", "description": "父图层索引，0表示取消父子关系" }
    },
    "required": ["compName", "layerIndex", "parentIndex"]
  }
}
```

#### 2.7.2 JSX脚本框架代码

```javascript
// setParentLayer.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  try {
    if (params.parentIndex === 0) {
      layer.parent = null;
    } else {
      var parentLayer = comp.layer(params.parentIndex);
      if (!parentLayer) {
        return JSON.stringify({ success: false, error: "E107: 父图层索引无效" });
      }
      if (params.parentIndex === params.layerIndex) {
        return JSON.stringify({ success: false, error: "E108: 图层不能成为自己的父图层" });
      }
      layer.parent = parentLayer;
    }

    return JSON.stringify({
      success: true,
      layerIndex: params.layerIndex,
      parentIndex: params.parentIndex
    });

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.7.3 MCP注册代码片段

```typescript
{
  name: "set-parent-layer",
  description: "设置图层父子关系。子图层将继承父图层的变换。parentIndex=0取消父子关系。常用于Null控制多图层",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      layerIndex: { type: "number" },
      parentIndex: { type": "number" }
    },
    required: ["compName", "layerIndex", "parentIndex"]
  }
}
```

### 2.8 工具7：add-adjustment-layer

#### 2.8.1 完整参数Schema

```json
{
  "name": "add-adjustment-layer",
  "description": "创建调整图层，调整图层影响其下方所有图层",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string" },
      "name": { "type": "string", "default": "Adjustment Layer" },
      "position": { "type": "number", "description": "插入位置索引，0表示最上方", "default": 1 }
    },
    "required": ["compName"]
  }
}
```

#### 2.8.2 JSX脚本框架代码

```javascript
// addAdjustmentLayer.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  try {
    var adjLayer = comp.layers.addSolid(
      [0, 0, 0],
      params.name || "Adjustment Layer",
      comp.width,
      comp.height,
      comp.pixelAspect,
      comp.duration
    );
    adjLayer.adjustmentLayer = true;
    adjLayer.isGuideLayer = false;

    // 调整位置
    if (params.position && params.position > 0) {
      adjLayer.moveAfter(comp.layer(params.position));
    } else {
      adjLayer.moveToBeginning();
    }

    return JSON.stringify({
      success: true,
      layerName: adjLayer.name,
      layerIndex: adjLayer.index
    });

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.8.3 MCP注册代码片段

```typescript
{
  name: "add-adjustment-layer",
  description: "创建调整图层。调整图层本身不渲染，但会对其下方所有图层应用效果。常用于全局调色、全局模糊等",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      name: { type": "string" },
      position: { type": "number" }
    },
    required: ["compName"]
  }
}
```

### 2.9 工具8：add-precomp

#### 2.9.1 完整参数Schema

```json
{
  "name": "add-precomp",
  "description": "将指定图层预合成为新的合成",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string", "description": "源合成名称" },
      "name": { "type": "string", "description": "新预合成名称" },
      "layerIndices": {
        "type": "array",
        "items": { "type": "number" },
        "description": "要预合成的图层索引列表"
      },
      "moveAllAttributes": {
        "type": "boolean",
        "default": true,
        "description": "是否将所有属性移入新合成"
      }
    },
    "required": ["compName", "name", "layerIndices"]
  }
}
```

#### 2.9.2 JSX脚本框架代码

```javascript
// addPrecomp.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  try {
    var layers = [];
    for (var i = 0; i < params.layerIndices.length; i++) {
      var layer = comp.layer(params.layerIndices[i]);
      if (layer) {
        layers.push(layer);
      }
    }

    if (layers.length === 0) {
      return JSON.stringify({ success: false, error: "E109: 没有有效的图层索引" });
    }

    // 选中要预合成的图层
    for (var j = 0; j < layers.length; j++) {
      layers[j].selected = true;
    }

    var precomp = comp.layers.precompose(
      params.layerIndices,
      params.name,
      params.moveAllAttributes !== false
    );

    // 取消选择
    for (var k = 1; k <= comp.numLayers; k++) {
      comp.layer(k).selected = false;
    }

    return JSON.stringify({
      success: true,
      precompName: precomp.name,
      precompDuration: precomp.duration
    });

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.9.3 MCP注册代码片段

```typescript
{
  name: "add-precomp",
  description: "将指定图层预合成为新的合成。预合成可简化时间轴、嵌套效果、实现复杂层级结构",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      name: { type": "string" },
      layerIndices: { type": "array", items: { type": "number" } },
      moveAllAttributes: { type": "boolean" }
    },
    required: ["compName", "name", "layerIndices"]
  }
}
```

### 2.10 工具9：import-footage

#### 2.10.1 完整参数Schema

```json
{
  "name": "import-footage",
  "description": "导入素材文件到项目并添加到合成",
  "inputSchema": {
    "type": "object",
    "properties": {
      "filePath": { "type": "string", "description": "素材文件的绝对路径" },
      "compName": { "type": "string", "description": "目标合成名称（可选，不填则仅导入项目）" },
      "asSequence": { "type": "boolean", "default": false, "description": "是否作为序列导入" },
      "position": { "type": "number", "description": "在合成中的插入位置索引" }
    },
    "required": ["filePath"]
  }
}
```

#### 2.10.2 JSX脚本框架代码

```javascript
// importFootage.jsx
(function() {
  var params = __commandParams__;

  try {
    var importOptions = new ImportOptions(File(params.filePath));
    if (params.asSequence) {
      importOptions.sequence = true;
    }

    var footage = app.project.importFile(importOptions);
    if (!footage) {
      return JSON.stringify({ success: false, error: "E110: 导入素材失败" });
    }

    var result = {
      success: true,
      footageName: footage.name,
      footageType: footage.typeName || "Footage"
    };

    // 如果指定了合成，将素材添加到合成
    if (params.compName) {
      var comp = null;
      for (var i = 1; i <= app.project.numItems; i++) {
        if (app.project.item(i) instanceof CompItem &&
            app.project.item(i).name === params.compName) {
          comp = app.project.item(i);
          break;
        }
      }

      if (comp) {
        var layer = comp.layers.add(footage);
        if (params.position && params.position > 0) {
          layer.moveAfter(comp.layer(params.position));
        }
        result.layerIndex = layer.index;
        result.compName = params.compName;
      }
    }

    return JSON.stringify(result);

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.10.3 MCP注册代码片段

```typescript
{
  name: "import-footage",
  description: "导入素材文件到AE项目。支持图片、视频、音频序列等。可指定目标合成自动添加",
  inputSchema: {
    type: "object",
    properties: {
      filePath: { type: "string" },
      compName: { type": "string" },
      asSequence: { type": "boolean" },
      position: { type": "number" }
    },
    required: ["filePath"]
  }
}
```

### 2.11 工具10：set-motion-blur

#### 2.11.1 完整参数Schema

```json
{
  "name": "set-motion-blur",
  "description": "设置图层或合成的运动模糊属性",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string" },
      "layerIndex": { "type": "number", "description": "图层索引，0表示设置合成级别" },
      "enabled": { "type": "boolean", "description": "是否启用运动模糊" },
      "shutterAngle": { "type": "number", "description": "快门角度（0-720），默认180", "minimum": 0, "maximum": 720 },
      "shutterPhase": { "type": "number", "description": "快门相位（-360到360）", "minimum": -360, "maximum": 360 },
      "samplesPerFrame": { "type": "number", "description": "每帧采样数（高级3D渲染器）", "minimum": 2, "maximum": 64 }
    },
    "required": ["compName", "enabled"]
  }
}
```

#### 2.11.2 JSX脚本框架代码

```javascript
// setMotionBlur.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  try {
    if (params.layerIndex && params.layerIndex > 0) {
      // 图层级别
      var layer = comp.layer(params.layerIndex);
      if (!layer) {
        return JSON.stringify({ success: false, error: "E102" });
      }
      layer.motionBlur = params.enabled;
    }

    // 合成级别设置
    comp.motionBlur = params.enabled;

    if (params.shutterAngle !== undefined) {
      comp.shutterAngle = params.shutterAngle;
    }
    if (params.shutterPhase !== undefined) {
      comp.shutterPhase = params.shutterPhase;
    }

    return JSON.stringify({
      success: true,
      motionBlurEnabled: params.enabled,
      shutterAngle: comp.shutterAngle
    });

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.11.3 MCP注册代码片段

```typescript
{
  name: "set-motion-blur",
  description: "设置运动模糊。快门角度180°为标准电影感，360°为强烈拖尾。需同时启用合成和图层的运动模糊开关",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      layerIndex: { type": "number" },
      enabled: { type": "boolean" },
      shutterAngle: { type": "number" },
      shutterPhase: { type": "number" }
    },
    required: ["compName", "enabled"]
  }
}
```

### 2.12 工具11：add-mask-with-shape

#### 2.12.1 完整参数Schema

```json
{
  "name": "add-mask-with-shape",
  "description": "向图层添加指定形状的遮罩",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string" },
      "layerIndex": { "type": "number" },
      "vertices": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "x": { "type": "number" },
            "y": { "type": "number" },
            "inTangent": { "type": "array", "items": { "type": "number" } },
            "outTangent": { "type": "array", "items": { "type": "number" } }
          },
          "required": ["x", "y"]
        },
        "description": "遮罩顶点坐标数组"
      },
      "feather": {
        "type": "array",
        "items": { "type": "number" },
        "default": [0, 0],
        "description": "遮罩羽化值 [水平, 垂直]"
      },
      "mode": {
        "type": "string",
        "enum": ["add", "subtract", "intersect", "difference", "lighten", "darken", "none"],
        "default": "add",
        "description": "遮罩模式"
      },
      "opacity": { "type": "number", "default": 100, "description": "遮罩不透明度" },
      "expansion": { "type": "number", "default": 0, "description": "遮罩扩展" },
      "inverted": { "type": "boolean", "default": false, "description": "是否反转遮罩" }
    },
    "required": ["compName", "layerIndex", "vertices"]
  }
}
```

#### 2.12.2 JSX脚本框架代码

```javascript
// addMaskWithShape.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  try {
    // 创建遮罩
    var mask = layer.Masks.addProperty();
    var shape = new Shape();

    // 设置顶点
    var verts = [];
    var inTans = [];
    var outTans = [];

    for (var i = 0; i < params.vertices.length; i++) {
      var v = params.vertices[i];
      verts.push([v.x, v.y]);
      inTans.push(v.inTangent || [0, 0]);
      outTans.push(v.outTangent || [0, 0]);
    }

    shape.vertices = verts;
    shape.inTangents = inTans;
    shape.outTangents = outTans;
    shape.closed = true;

    mask.property("ADBE Mask Shape").setValue(shape);

    // 设置遮罩模式
    var modeMap = {
      "add": MaskMode.ADD,
      "subtract": MaskMode.SUBTRACT,
      "intersect": MaskMode.INTERSECT,
      "difference": MaskMode.DIFFERENCE,
      "lighten": MaskMode.LIGHTEN,
      "darken": MaskMode.DARKEN,
      "none": MaskMode.NONE
    };
    mask.maskMode = modeMap[params.mode] || MaskMode.ADD;

    // 设置羽化
    if (params.feather) {
      mask.property("ADBE Mask Feather").setValue(params.feather);
    }

    // 设置不透明度
    if (params.opacity !== undefined) {
      mask.property("ADBE Mask Opacity").setValue(params.opacity);
    }

    // 设置扩展
    if (params.expansion !== undefined) {
      mask.property("ADBE Mask Expansion").setValue(params.expansion);
    }

    // 设置反转
    if (params.inverted) {
      mask.property("ADBE Mask Shape").setValue(shape); // 反转通过inverted属性
      mask.inverted = true;
    }

    return JSON.stringify({
      success: true,
      maskIndex: mask.propertyIndex,
      vertexCount: verts.length
    });

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.12.3 MCP注册代码片段

```typescript
{
  name: "add-mask-with-shape",
  description: "向图层添加自定义形状遮罩。支持贝塞尔曲线顶点、羽化、模式设置。常用于区域限制效果范围",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      layerIndex: { type": "number" },
      vertices: { type": "array", items: { type": "object" } },
      feather: { type": "array", items: { type": "number" } },
      mode: { type": "string" },
      opacity: { type": "number" },
      expansion: { type": "number" },
      inverted: { type": "boolean" }
    },
    required: ["compName", "layerIndex", "vertices"]
  }
}
```

### 2.13 工具12：execute-atom-script

#### 2.13.1 完整参数Schema

```json
{
  "name": "execute-atom-script",
  "description": "执行由原子参数编译器生成的ExtendScript脚本，用于复杂效果组合操作",
  "inputSchema": {
    "type": "object",
    "properties": {
      "scriptContent": {
        "type": "string",
        "description": "编译器生成的ExtendScript代码"
      },
      "scriptName": {
        "type": "string",
        "description": "脚本名称（用于日志和调试）"
      },
      "timeout": {
        "type": "number",
        "default": 10000,
        "description": "执行超时时间（毫秒）"
      },
      "dryRun": {
        "type": "boolean",
        "default": false,
        "description": "干运行模式，仅验证语法不执行"
      }
    },
    "required": ["scriptContent"]
  }
}
```

#### 2.13.2 JSX脚本框架代码

```javascript
// executeAtomScript.jsx
(function() {
  var params = __commandParams__;

  if (params.dryRun) {
    // 干运行模式：仅检查语法
    try {
      // 尝试解析脚本（不执行）
      var fn = new Function(params.scriptContent);
      return JSON.stringify({
        success: true,
        dryRun: true,
        syntaxValid: true
      });
    } catch (e) {
      return JSON.stringify({
        success: false,
        dryRun: true,
        syntaxValid: false,
        error: "E111: 语法错误 - " + e.toString()
      });
    }
  }

  app.beginUndoGroup(params.scriptName || "Execute Atom Script");

  try {
    // 执行编译器生成的脚本
    eval(params.scriptContent);

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      scriptName: params.scriptName || "unnamed",
      executedAt: new Date().toISOString()
    });

  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({
      success: false,
      error: "E200: " + e.toString(),
      scriptName: params.scriptName || "unnamed"
    });
  }
})();
```

#### 2.13.3 MCP注册代码片段

```typescript
{
  name: "execute-atom-script",
  description: "执行原子参数编译器生成的ExtendScript。这是知识编译器到AE执行的直接通道，支持干运行验证",
  inputSchema: {
    type: "object",
    properties: {
      scriptContent: { type: "string" },
      scriptName: { type": "string" },
      timeout: { type": "number" },
      dryRun: { type": "boolean" }
    },
    required: ["scriptContent"]
  }
}
```

### 2.14 工具13：get-effect-properties

#### 2.14.1 完整参数Schema

```json
{
  "name": "get-effect-properties",
  "description": "获取图层上指定效果的所有属性及当前值",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string" },
      "layerIndex": { "type": "number" },
      "effectIndex": { "type": "number", "description": "效果索引（1-based）" }
    },
    "required": ["compName", "layerIndex", "effectIndex"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "effectName": { "type": "string" },
      "matchName": { "type": "string" },
      "properties": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "matchName": { "type": "string" },
            "value": { "type": "string" },
            "propertyType": { "type": "string" },
            "hasKeyframes": { "type": "boolean" },
            "keyframeCount": { "type": "number" }
          }
        }
      }
    }
  }
}
```

#### 2.14.2 JSX脚本框架代码

```javascript
// getEffectProperties.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  try {
    var effect = layer.Effects.property(params.effectIndex);
    if (!effect) {
      return JSON.stringify({ success: false, error: "E112: 效果索引无效" });
    }

    var props = [];
    for (var i = 1; i <= effect.numProperties; i++) {
      var prop = effect.property(i);
      if (prop) {
        var propInfo = {
          name: prop.name,
          matchName: prop.matchName,
          propertyType: prop.propertyType.toString(),
          hasKeyframes: false,
          keyframeCount: 0
        };

        if (prop.propertyType === PropertyType.PROPERTY) {
          try {
            propInfo.value = prop.value.toString();
          } catch (e) {
            propInfo.value = "(无法读取)";
          }

          if (prop.canSetExpression) {
            propInfo.hasKeyframes = prop.numKeys > 0;
            propInfo.keyframeCount = prop.numKeys;
          }
        }

        props.push(propInfo);
      }
    }

    return JSON.stringify({
      success: true,
      effectName: effect.name,
      matchName: effect.matchName,
      properties: props
    });

  } catch (e) {
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.14.3 MCP注册代码片段

```typescript
{
  name: "get-effect-properties",
  description: "获取图层上指定效果的所有属性值。用于验证效果参数、读取当前状态、检查关键帧",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      layerIndex: { type: "number" },
      effectIndex: { type": "number" }
    },
    required: ["compName", "layerIndex", "effectIndex"]
  }
}
```

### 2.15 工具14：set-effect-keyframes

#### 2.15.1 完整参数Schema

```json
{
  "name": "set-effect-keyframes",
  "description": "为效果属性设置多个关键帧",
  "inputSchema": {
    "type": "object",
    "properties": {
      "compName": { "type": "string" },
      "layerIndex": { "type": "number" },
      "effectIndex": { "type": "number" },
      "propName": { "type": "string", "description": "效果内的属性名" },
      "keyframes": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "time": { "type": "number" },
            "value": {
              "oneOf": [
                { "type": "number" },
                { "type": "array", "items": { "type": "number" } }
              ]
            },
            "easingType": {
              "type": "string",
              "enum": ["linear", "easeIn", "easeOut", "easeInOut", "hold"],
              "default": "linear"
            }
          },
          "required": ["time", "value"]
        }
      }
    },
    "required": ["compName", "layerIndex", "effectIndex", "propName", "keyframes"]
  }
}
```

#### 2.15.2 JSX脚本框架代码

```javascript
// setEffectKeyframes.jsx
(function() {
  var params = __commandParams__;

  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.layer(params.layerIndex);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  app.beginUndoGroup("Set Effect Keyframes");

  try {
    var effect = layer.Effects.property(params.effectIndex);
    if (!effect) {
      return JSON.stringify({ success: false, error: "E112" });
    }

    var prop = effect.property(params.propName);
    if (!prop || !prop.canSetValue) {
      return JSON.stringify({ success: false, error: "E113: 属性无效或不可设置" });
    }

    var keyframesAdded = 0;

    for (var i = 0; i < params.keyframes.length; i++) {
      var kf = params.keyframes[i];
      prop.setValueAtTime(kf.time, kf.value);
      keyframesAdded++;

      // 设置缓动
      if (kf.easingType && kf.easingType !== "linear") {
        var kfIndex = prop.nearestKeyIndex(kf.time);
        var inType, outType;

        switch (kf.easingType) {
          case "easeIn":
            inType = KeyframeInterpolationType.BEZIER;
            outType = KeyframeInterpolationType.LINEAR;
            break;
          case "easeOut":
            inType = KeyframeInterpolationType.LINEAR;
            outType = KeyframeInterpolationType.BEZIER;
            break;
          case "easeInOut":
            inType = KeyframeInterpolationType.BEZIER;
            outType = KeyframeInterpolationType.BEZIER;
            break;
          case "hold":
            inType = KeyframeInterpolationType.HOLD;
            outType = KeyframeInterpolationType.HOLD;
            break;
        }

        if (inType !== undefined) {
          prop.setInterpolationTypeAtKey(kfIndex, inType, outType);
        }
      }
    }

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      effectName: effect.name,
      propName: params.propName,
      keyframesAdded: keyframesAdded
    });

  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 2.15.3 MCP注册代码片段

```typescript
{
  name: "set-effect-keyframes",
  description: "为效果属性批量设置关键帧。与add-effect-with-keyframes不同，此工具用于已有效果的动画设置",
  inputSchema: {
    type: "object",
    properties: {
      compName: { type: "string" },
      layerIndex: { type": "number" },
      effectIndex: { type": "number" },
      propName: { type": "string" },
      keyframes: { type": "array", items: { type": "object" } }
    },
    required: ["compName", "layerIndex", "effectIndex", "propName", "keyframes"]
  }
}
```

---

## 第三章 Bridge通信协议扩展

### 3.1 命令文件格式升级

#### 3.1.1 V1格式（当前）

```json
{
  "command": "create-composition",
  "params": {
    "name": "My Comp",
    "width": 1920,
    "height": 1080
  },
  "timestamp": 1720000000000
}
```

**V1局限性**：
- 不支持复杂参数嵌套
- 缺少命令ID，无法追踪
- 无优先级和依赖关系
- 无超时控制

#### 3.1.2 V2格式（升级后）

```json
{
  "protocolVersion": 2,
  "commandId": "cmd-550e8400-e29b-41d4-a716-446655440000",
  "command": "add-effect-with-keyframes",
  "params": {
    "compName": "My Comp",
    "layerIndex": 1,
    "effectMatchName": "ADBE Gaussian Blur 2",
    "settings": {
      "Blurriness": 25,
      "Repeat Pixels": true
    },
    "keyframes": [
      {
        "propertyName": "Blurriness",
        "time": 0,
        "value": 0,
        "easingType": "easeOut"
      },
      {
        "propertyName": "Blurriness",
        "time": 1.5,
        "value": 50,
        "easingType": "easeInOut"
      },
      {
        "propertyName": "Blurriness",
        "time": 3,
        "value": 0,
        "easingType": "easeIn"
      }
    ]
  },
  "options": {
    "timeout": 10000,
    "priority": "normal",
    "dependsOn": null,
    "dryRun": false
  },
  "metadata": {
    "timestamp": 1720000000000,
    "source": "mcp-server",
    "correlationId": "req-abc123",
    "retryCount": 0
  }
}
```

**V2新增字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `protocolVersion` | number | 协议版本号，V2=2 |
| `commandId` | string | 全局唯一命令ID（UUID v4） |
| `options.timeout` | number | 命令超时时间（毫秒） |
| `options.priority` | string | 优先级：low/normal/high/critical |
| `options.dependsOn` | string/null | 依赖的前置命令ID |
| `options.dryRun` | boolean | 干运行模式（仅验证不执行） |
| `metadata.timestamp` | number | 命令创建时间戳 |
| `metadata.source` | string | 命令来源标识 |
| `metadata.correlationId` | string | 关联ID（用于追踪请求链路） |
| `metadata.retryCount` | number | 重试次数 |

### 3.2 结果文件格式升级

#### 3.2.1 V1格式（当前）

```json
{
  "success": true,
  "result": {
    "compositionName": "My Comp"
  }
}
```

#### 3.2.2 V2格式（升级后）

```json
{
  "protocolVersion": 2,
  "commandId": "cmd-550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "success": true,
    "effectIndex": 1,
    "effectName": "Gaussian Blur",
    "keyframesAdded": 3
  },
  "progress": {
    "percentage": 100,
    "currentStep": "completed",
    "totalSteps": 3,
    "message": "效果添加完成，已设置3个关键帧"
  },
  "timing": {
    "receivedAt": 1720000000125,
    "startedAt": 1720000000130,
    "completedAt": 1720000000345,
    "executionTimeMs": 215
  },
  "error": null,
  "metadata": {
    "bridgeVersion": "2.0.0",
    "aeVersion": "25.1",
    "scriptEngine": "ExtendScript"
  }
}
```

**V2新增字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `protocolVersion` | number | 协议版本号 |
| `commandId` | string | 对应命令的ID |
| `status` | string | 执行状态：pending/running/completed/failed/timeout |
| `progress` | object | 进度信息（支持长时间操作） |
| `progress.percentage` | number | 完成百分比 0-100 |
| `progress.currentStep` | string | 当前步骤描述 |
| `progress.totalSteps` | number | 总步骤数 |
| `progress.message` | string | 进度消息 |
| `timing` | object | 时间统计 |
| `error` | object/null | 错误信息（如有） |
| `metadata` | object | 运行时元数据 |

### 3.3 心跳机制

Bridge面板需要定期上报健康状态，MCP Server通过心跳检测面板是否在线：

#### 3.3.1 心跳文件格式

文件路径：`ae_mcp_heartbeat.json`

```json
{
  "bridgeVersion": "2.0.0",
  "aeVersion": "25.1",
  "status": "ready",
  "lastPollTime": 1720000000250,
  "pollInterval": 250,
  "pendingCommands": 0,
  "activeScript": null,
  "uptime": 3600000,
  "memoryUsage": {
    "available": "8GB",
    "aeProcess": "2.3GB"
  }
}
```

#### 3.3.2 心跳状态定义

| 状态 | 说明 | MCP Server行为 |
|------|------|---------------|
| `ready` | 面板就绪，可接受命令 | 正常发送命令 |
| `busy` | 正在执行脚本 | 等待执行完成 |
| `error` | 面板异常 | 不发送命令，等待恢复 |
| `offline` | 面板未启动 | 提示用户打开Bridge面板 |

#### 3.3.3 心跳检测逻辑

```typescript
// MCP Server端心跳检测
const HEARTBEAT_TIMEOUT = 5000; // 5秒无心跳视为离线
const HEARTBEAT_CHECK_INTERVAL = 1000; // 1秒检查一次

function checkBridgeHealth(): BridgeStatus {
  try {
    const heartbeat = JSON.parse(fs.readFileSync(HEARTBEAT_PATH, 'utf-8'));
    const elapsed = Date.now() - heartbeat.lastPollTime;

    if (elapsed > HEARTBEAT_TIMEOUT) {
      return { status: 'offline', lastSeen: heartbeat.lastPollTime };
    }

    return {
      status: heartbeat.status,
      lastSeen: heartbeat.lastPollTime,
      isBusy: heartbeat.status === 'busy'
    };
  } catch (e) {
    return { status: 'offline', lastSeen: 0 };
  }
}
```

### 3.4 错误码定义

#### 3.4.1 错误码体系

错误码采用三位数字编码，按类别分组：

| 范围 | 类别 | 说明 |
|------|------|------|
| E001-E099 | 通信错误 | MCP Server与Bridge之间的通信问题 |
| E100-E199 | 合成/图层错误 | AE项目结构相关错误 |
| E200-E299 | 脚本执行错误 | ExtendScript运行时错误 |
| E300-E399 | 效果操作错误 | 效果添加/参数设置相关错误 |
| E400-E499 | 参数验证错误 | 输入参数验证失败 |
| E500-E599 | 系统错误 | AE应用/系统级别错误 |
| E600-E699 | 超时错误 | 执行超时相关 |
| E700-E799 | 权限错误 | 安全/权限限制 |
| E800-E899 | 预编译错误 | 原子参数编译器错误 |
| E900-E999 | 保留 | 未来扩展 |

#### 3.4.2 详细错误码清单

**通信错误（E001-E099）**：

| 错误码 | 说明 | 建议操作 |
|--------|------|---------|
| E001 | 命令文件写入失败 | 检查文件权限和磁盘空间 |
| E002 | 命令文件格式无效 | 检查JSON格式 |
| E003 | 协议版本不匹配 | 检查Bridge和MCP Server版本 |
| E004 | 结果文件读取失败 | 检查文件权限 |
| E005 | 结果文件格式无效 | 检查Bridge输出格式 |
| E006 | Bridge面板离线 | 提示用户打开Bridge面板 |
| E007 | Bridge面板忙碌 | 等待当前命令完成 |
| E008 | 心跳检测失败 | 重启Bridge面板 |
| E009 | 命令ID冲突 | 重新生成命令ID |
| E010 | 命令依赖未满足 | 检查dependsOn命令是否完成 |

**合成/图层错误（E100-E199）**：

| 错误码 | 说明 | 建议操作 |
|--------|------|---------|
| E101 | 没有活动合成 | 确保有打开的合成 |
| E102 | 图层索引无效 | 检查图层索引范围 |
| E103 | 属性路径无效 | 检查属性路径语法 |
| E104 | 关键帧索引超出范围 | 检查numKeys |
| E105 | 不支持的混合模式 | 检查blendMode枚举值 |
| E106 | 不支持的轨道遮罩类型 | 检查matteType枚举值 |
| E107 | 父图层索引无效 | 检查父图层存在性 |
| E108 | 图层不能成为自己的父图层 | 修改parentIndex |
| E109 | 没有有效的图层索引 | 检查layerIndices数组 |
| E110 | 导入素材失败 | 检查文件路径和格式 |
| E111 | 语法错误 | 检查脚本语法 |
| E112 | 效果索引无效 | 检查效果数量 |
| E113 | 属性无效或不可设置 | 检查属性名和可写性 |

**脚本执行错误（E200-E299）**：

| 错误码 | 说明 | 建议操作 |
|--------|------|---------|
| E200 | ExtendScript运行时错误 | 查看详细错误信息 |
| E201 | 内存不足 | 简化操作或重启AE |
| E202 | 渲染引擎错误 | 检查渲染器设置 |
| E203 | DOM操作失败 | 检查AE状态 |
| E204 | 表达式计算错误 | 检查表达式语法 |
| E205 | Undo组未正确关闭 | 检查beginUndoGroup/endUndoGroup配对 |

**效果操作错误（E300-E399）**：

| 错误码 | 说明 | 建议操作 |
|--------|------|---------|
| E300 | 效果matchName无效 | 检查效果名称拼写 |
| E301 | 效果未安装 | 安装对应插件 |
| E302 | 效果参数名无效 | 查阅效果参数列表 |
| E303 | 效果参数值超范围 | 检查参数取值范围 |
| E304 | 效果不支持关键帧 | 该属性为只读 |
| E305 | 效果不支持表达式 | 检查canSetExpression |
| E306 | 效果属性类型不匹配 | 检查值类型是否与属性类型一致 |
| E307 | 批量效果添加部分失败 | 检查每个效果的错误信息 |
| E308 | 效果链执行顺序错误 | 调整效果顺序 |

**超时错误（E600-E699）**：

| 错误码 | 说明 | 建议操作 |
|--------|------|---------|
| E600 | 命令执行超时 | 增加timeout或简化操作 |
| E601 | Bridge轮询超时 | 检查Bridge面板状态 |
| E602 | 结果等待超时 | 检查脚本执行进度 |
| E603 | 心跳超时 | 重启Bridge面板 |

### 3.5 超时重试策略

#### 3.5.1 超时层级

```
┌──────────────────────────────────────────────────┐
│ Level 1: MCP Server 超时 (默认5000ms)            │
│   └→ Node.js等待结果文件超时                      │
├──────────────────────────────────────────────────┤
│ Level 2: Bridge 执行超时 (默认10000ms)            │
│   └→ ExtendScript执行时间超限                     │
├──────────────────────────────────────────────────┤
│ Level 3: AE应用超时 (默认30000ms)                 │
│   └→ AE渲染/合成处理超限                          │
└──────────────────────────────────────────────────┘
```

#### 3.5.2 重试策略配置

```typescript
interface RetryConfig {
  maxRetries: number;        // 最大重试次数，默认3
  initialDelay: number;      // 初始延迟(ms)，默认500
  maxDelay: number;          // 最大延迟(ms)，默认5000
  backoffMultiplier: number; // 退避乘数，默认2
  retryableErrors: string[]; // 可重试的错误码
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelay: 500,
  maxDelay: 5000,
  backoffMultiplier: 2,
  retryableErrors: [
    "E006", // Bridge面板离线（可能正在启动）
    "E007", // Bridge面板忙碌
    "E600", // 命令执行超时
    "E601", // Bridge轮询超时
    "E201", // 内存不足（重试可能成功）
    "E203", // DOM操作失败（临时状态）
  ]
};
```

#### 3.5.3 重试执行流程

```typescript
async function executeWithRetry(
  command: MCPCommand,
  config: RetryConfig = DEFAULT_RETRY_CONFIG
): Promise<MCPResult> {
  let lastError: Error | null = null;
  let delay = config.initialDelay;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      // 发送命令
      const result = await sendCommand(command);

      if (result.success) {
        return result;
      }

      // 检查是否可重试
      if (!config.retryableErrors.includes(result.errorCode)) {
        return result; // 不可重试的错误，直接返回
      }

      lastError = new Error(`Error ${result.errorCode}: ${result.errorMessage}`);

    } catch (e) {
      lastError = e as Error;
    }

    // 等待后重试
    if (attempt < config.maxRetries) {
      await sleep(delay);
      delay = Math.min(delay * config.backoffMultiplier, config.maxDelay);

      // 更新重试计数
      command.metadata.retryCount = attempt + 1;
    }
  }

  return {
    success: false,
    error: `E600: 超过最大重试次数(${config.maxRetries})`,
    lastError: lastError?.message
  };
}
```

#### 3.5.4 特殊场景重试策略

| 场景 | 策略 | 说明 |
|------|------|------|
| Bridge面板未启动 | 最多重试5次，每次延迟2秒 | 给用户时间打开面板 |
| 效果参数设置失败 | 不重试 | 参数错误需要人工修正 |
| 脚本执行超时 | 重试1次，增加超时时间 | 可能是临时负载高 |
| 批量操作部分失败 | 仅重试失败项 | 避免重复执行已成功的项 |
| AE渲染繁忙 | 重试3次，指数退避 | 等待渲染队列空闲 |

---

## 第四章 效果操作的完整MCP调用链

### 4.1 端到端调用链概览

从用户自然语言输入到AE执行的完整调用链：

```
用户输入                          知识推理                        编译执行
┌──────────┐    ┌─────────────────────────┐    ┌──────────────────────┐
│ "给这个文 │    │ 1. 解析词汇              │    │ 3. 原子参数→编译器    │
│  字加一个 │───→│ 2. 推理决策树→参数还原    │───→│ 4. 生成ExtendScript  │
│  暖色发光" │    │    →原子参数JSON          │    │    代码              │
└──────────┘    └─────────────────────────┘    └──────────┬───────────┘
                                                          │
                       传输                                │ 执行
┌──────────────────────┐    ┌─────────────────────────┐    │
│ 5. MCP Server        │    │ 6. Bridge面板            │    │
│    run-script        │←───│    轮询→执行JSX          │←───┘
│    →写命令文件         │    │    →写结果文件           │
└──────────┬───────────┘    └──────────┬──────────────┘
           │                           │
           └───────── 结果返回 ─────────┘
```

### 4.2 端到端示例1：添加高斯模糊

**用户输入**："给这个图层加一个高斯模糊，模糊度25"

#### 步骤1：解析词汇→推理决策树→参数还原

```json
{
  "input": "给这个图层加一个高斯模糊，模糊度25",
  "parsed": {
    "operation": "add_effect",
    "effectType": "gaussian_blur",
    "effectMatchName": "ADBE Gaussian Blur 2",
    "parameters": {
      "Blurriness": 25
    }
  }
}
```

推理过程：
- "高斯模糊" → 匹配解析词汇 VT-001 "均匀模糊扩散" → 效果识别 EI-001 "Gaussian Blur"
- "模糊度25" → 参数值 PV-001 "Blurriness = 25"
- 无时间描述 → 默认全程静态值

#### 步骤2：原子参数JSON

```json
{
  "operation": "addEffect",
  "target": {
    "compName": "auto-detect",
    "layerIndex": "auto-select"
  },
  "effect": {
    "matchName": "ADBE Gaussian Blur 2",
    "name": "Gaussian Blur"
  },
  "properties": [
    {
      "name": "Blurriness",
      "value": 25,
      "animated": false
    },
    {
      "name": "Repeat Pixels",
      "value": true,
      "animated": false
    }
  ]
}
```

#### 步骤3：编译器→ExtendScript

```javascript
// 由原子参数编译器生成的ExtendScript代码
(function() {
  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.selectedLayers[0] || comp.layer(1);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  app.beginUndoGroup("Add Gaussian Blur");

  try {
    var effect = layer.Effects.addProperty("ADBE Gaussian Blur 2");
    effect.property("Blurriness").setValue(25);
    effect.property("Repeat Pixels").setValue(true);

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      effectIndex: effect.propertyIndex,
      effectName: effect.name
    });
  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 步骤4：MCP调用

```typescript
// MCP Server调用
const result = await mcpClient.callTool("add-effect-with-keyframes", {
  compName: "Comp 1",
  layerIndex: 1,
  effectMatchName: "ADBE Gaussian Blur 2",
  settings: {
    "Blurriness": 25,
    "Repeat Pixels": true
  }
});
```

#### 步骤5：结果返回→验证

```json
{
  "success": true,
  "effectIndex": 1,
  "effectName": "Gaussian Blur",
  "keyframesAdded": 0
}
```

验证：调用 `get-effect-properties` 确认参数已正确设置。

### 4.3 端到端示例2：添加发光效果+关键帧动画

**用户输入**："给文字加一个暖色发光，前1秒从弱到强，然后稳定"

#### 步骤1：解析词汇

```json
{
  "input": "给文字加一个暖色发光，前1秒从弱到强，然后稳定",
  "parsed": {
    "operation": "add_effect_with_animation",
    "effectType": "glow",
    "effectMatchName": "ADBE Glo2",
    "parameters": {
      "Glow Threshold": 40,
      "Glow Radius": 50,
      "Glow Intensity": 1.5,
      "Color A": [255, 200, 100],
      "Color B": [255, 150, 50],
      "Glow Operation": "Add"
    },
    "animation": {
      "property": "Glow Intensity",
      "keyframes": [
        { "time": 0, "value": 0.3, "easing": "easeOut" },
        { "time": 1, "value": 1.5, "easing": "easeInOut" }
      ]
    }
  }
}
```

推理过程：
- "暖色发光" → VT-015 "暖色边缘光晕" → EI-015 "Glow效果" → ADBE Glo2
- "暖色" → PV-015 Color A/B 设为暖色系（橙黄色调）
- "从弱到强" → KF-003 渐变关键帧，Intensity 0.3→1.5
- "前1秒" → TL-001 时间范围0-1秒
- "然后稳定" → 持续保持最终值

#### 步骤2：原子参数JSON

```json
{
  "operation": "addEffectWithKeyframes",
  "target": {
    "compName": "auto-detect",
    "layerIndex": "auto-select"
  },
  "effect": {
    "matchName": "ADBE Glo2",
    "name": "Glow"
  },
  "properties": [
    { "name": "Glow Threshold", "value": 40 },
    { "name": "Glow Radius", "value": 50 },
    { "name": "Glow Intensity", "value": 0.3, "animated": true },
    { "name": "Color A", "value": [1, 0.784, 0.392, 1] },
    { "name": "Color B", "value": [1, 0.588, 0.196, 1] },
    { "name": "Glow Operation", "value": 3 }
  ],
  "keyframes": [
    {
      "propertyName": "Glow Intensity",
      "keyframes": [
        { "time": 0, "value": 0.3, "easingType": "easeOut" },
        { "time": 1, "value": 1.5, "easingType": "easeInOut" }
      ]
    }
  ]
}
```

#### 步骤3：编译器→ExtendScript

```javascript
(function() {
  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.selectedLayers[0] || comp.layer(1);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  app.beginUndoGroup("Add Warm Glow with Animation");

  try {
    // 1. 添加发光效果
    var effect = layer.Effects.addProperty("ADBE Glo2");

    // 2. 设置静态参数
    effect.property("Glow Threshold").setValue(40);
    effect.property("Glow Radius").setValue(50);
    effect.property("Color A").setValue([1, 0.784, 0.392, 1]);
    effect.property("Color B").setValue([1, 0.588, 0.196, 1]);
    effect.property("Glow Operation").setValue(3); // Add模式

    // 3. 设置Glow Intensity关键帧动画
    var intensityProp = effect.property("Glow Intensity");

    // 关键帧1：0秒，弱发光
    intensityProp.setValueAtTime(0, 0.3);

    // 关键帧2：1秒，强发光
    intensityProp.setValueAtTime(1, 1.5);

    // 设置缓动
    var kf1Index = intensityProp.nearestKeyIndex(0);
    var kf2Index = intensityProp.nearestKeyIndex(1);

    // 第一个关键帧：easeOut
    intensityProp.setInterpolationTypeAtKey(
      kf1Index,
      KeyframeInterpolationType.LINEAR,
      KeyframeInterpolationType.BEZIER
    );

    // 第二个关键帧：easeInOut
    intensityProp.setInterpolationTypeAtKey(
      kf2Index,
      KeyframeInterpolationType.BEZIER,
      KeyframeInterpolationType.BEZIER
    );

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      effectIndex: effect.propertyIndex,
      effectName: effect.name,
      keyframesAdded: 2
    });
  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 步骤4-5：MCP调用与验证

```typescript
const result = await mcpClient.callTool("add-effect-with-keyframes", {
  compName: "Comp 1",
  layerIndex: 1,
  effectMatchName: "ADBE Glo2",
  settings: {
    "Glow Threshold": 40,
    "Glow Radius": 50,
    "Glow Intensity": 0.3,
    "Color A": [1, 0.784, 0.392, 1],
    "Color B": [1, 0.588, 0.196, 1],
    "Glow Operation": 3
  },
  keyframes: [
    {
      propertyName: "Glow Intensity",
      time: 0,
      value: 0.3,
      easingType: "easeOut"
    },
    {
      propertyName: "Glow Intensity",
      time: 1,
      value: 1.5,
      easingType: "easeInOut"
    }
  ]
});

// 验证
const props = await mcpClient.callTool("get-effect-properties", {
  compName: "Comp 1",
  layerIndex: 1,
  effectIndex: result.effectIndex
});
```

### 4.4 端到端示例3：创建粒子系统（Particular）

**用户输入**："创建一个金色魔法粒子效果，从中心向上飘散"

#### 步骤1：解析词汇

```json
{
  "input": "创建一个金色魔法粒子效果，从中心向上飘散",
  "parsed": {
    "operation": "create_particle_system",
    "effectType": "particular",
    "effectMatchName": "TC Particular2",
    "style": "magic_golden",
    "emitter": {
      "type": "Sphere",
      "position": [960, 540, 0],
      "particlesPerSec": 150,
      "velocity": 25,
      "velocityRandom": 40
    },
    "particle": {
      "life": 3,
      "lifeRandom": 50,
      "size": 5,
      "sizeRandom": 50,
      "opacityRandom": 40,
      "color": [1, 0.84, 0]
    },
    "physics": {
      "gravity": -15,
      "airResistance": 0.8
    },
    "turbulence": {
      "amount": 8,
      "scale": 65,
      "evolution": 15
    },
    "sizeOverLife": "bell_curve",
    "opacityOverLife": "fade_in_out",
    "auxSystem": {
      "emit": "continuously",
      "type": "Streaklet",
      "size": 2,
      "life": 1.5
    }
  }
}
```

推理过程：
- "金色魔法粒子" → 参考视频案例解析库 CASE-1-3 → Particular黄金参数模板
- "从中心" → 发射器位置居中 [960, 540, 0]
- "向上飘散" → 重力为负值(-15)，模拟上浮
- "魔法" → Turbulence Field增加有机感，Size over Life钟形曲线

#### 步骤2：原子参数JSON

```json
{
  "operation": "addEffectWithSettings",
  "target": { "compName": "auto-detect", "layerIndex": "new-solid" },
  "effect": { "matchName": "TC Particular2", "name": "Particular" },
  "properties": [
    { "group": "Emitter", "name": "Emitter Type", "value": 3 },
    { "group": "Emitter", "name": "Position XY", "value": [960, 540] },
    { "group": "Emitter", "name": "Position Z", "value": 0 },
    { "group": "Emitter", "name": "Particles/sec", "value": 150 },
    { "group": "Emitter", "name": "Velocity", "value": 25 },
    { "group": "Emitter", "name": "Velocity Random", "value": 40 },
    { "group": "Particle", "name": "Life", "value": 3 },
    { "group": "Particle", "name": "Life Random", "value": 50 },
    { "group": "Particle", "name": "Size", "value": 5 },
    { "group": "Particle", "name": "Size Random", "value": 50 },
    { "group": "Particle", "name": "Opacity Random", "value": 40 },
    { "group": "Particle", "name": "Color", "value": [1, 0.84, 0] },
    { "group": "Physics", "name": "Gravity", "value": -15 },
    { "group": "Physics Air", "name": "Air Resistance", "value": 0.8 },
    { "group": "Physics Air", "name": "Turbulence Amount", "value": 8 },
    { "group": "Physics Air", "name": "Turbulence Scale", "value": 65 },
    { "group": "Physics Air", "name": "Turbulence Evolution Speed", "value": 15 }
  ]
}
```

#### 步骤3：编译器→ExtendScript

```javascript
(function() {
  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  app.beginUndoGroup("Create Golden Magic Particles");

  try {
    // 1. 创建黑色纯色层作为粒子载体
    var solidLayer = comp.layers.addSolid(
      [0, 0, 0],
      "Golden Magic Particles",
      comp.width, comp.height,
      comp.pixelAspect, comp.duration
    );

    // 2. 添加Particular效果
    var effect = solidLayer.Effects.addProperty("TC Particular2");

    // 3. 设置发射器参数
    effect.property("Emitter").property("Emitter Type").setValue(3); // Sphere
    effect.property("Emitter").property("Particles/sec").setValue(150);
    effect.property("Emitter").property("Velocity").setValue(25);
    effect.property("Emitter").property("Velocity Random").setValue(40);

    // 4. 设置粒子参数
    effect.property("Particle").property("Life").setValue(3);
    effect.property("Particle").property("Life Random").setValue(50);
    effect.property("Particle").property("Size").setValue(5);
    effect.property("Particle").property("Size Random").setValue(50);
    effect.property("Particle").property("Opacity Random").setValue(40);
    effect.property("Particle").property("Color").setValue([1, 0.84, 0]);

    // 5. 设置物理参数
    effect.property("Physics").property("Gravity").setValue(-15);
    effect.property("Physics Air").property("Air Resistance").setValue(0.8);
    effect.property("Physics Air").property("Turbulence Amount").setValue(8);

    // 6. 设置混合模式为Add（发光叠加）
    solidLayer.blendingMode = BlendingMode.ADD;

    // 7. 开启运动模糊
    solidLayer.motionBlur = true;
    comp.motionBlur = true;
    comp.shutterAngle = 360;

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      layerName: solidLayer.name,
      effectIndex: effect.propertyIndex,
      effectName: effect.name
    });
  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 步骤4-5：MCP调用与验证

使用 `execute-atom-script` 工具执行上述编译后的脚本，然后通过 `get-effect-properties` 验证参数是否正确设置。

### 4.5 端到端示例4：创建文字弹性入场动画

**用户输入**："给标题文字加一个弹性入场动画，从下方弹入"

#### 步骤1：解析词汇

```json
{
  "input": "给标题文字加一个弹性入场动画，从下方弹入",
  "parsed": {
    "operation": "add_text_animation",
    "animationType": "elastic_entrance",
    "direction": "from_bottom",
    "properties": {
      "position": { "startY": 740, "endY": 540 },
      "scale": { "start": 80, "end": 100, "overshoot": 110 },
      "opacity": { "start": 0, "end": 100 }
    },
    "easing": "elastic",
    "duration": 0.8
  }
}
```

推理过程：
- "弹性入场" → EC-005 "弹性缓动" → freq=3, decay=5
- "从下方弹入" → 位置动画：Y从740(下方)→540(居中)，overshoot到490
- "弹性" → Scale从80%→110%(overshoot)→100%(settle)

#### 步骤2：原子参数JSON

```json
{
  "operation": "animateTextEntrance",
  "target": { "compName": "auto-detect", "layerIndex": "auto-select" },
  "animation": {
    "position": {
      "keyframes": [
        { "time": 0, "value": [960, 740] },
        { "time": 0.8, "value": [960, 540] }
      ],
      "expression": "弹性表达式替代关键帧"
    },
    "scale": {
      "keyframes": [
        { "time": 0, "value": [80, 80] },
        { "time": 0.4, "value": [110, 110] },
        { "time": 0.8, "value": [100, 100] }
      ]
    },
    "opacity": {
      "keyframes": [
        { "time": 0, "value": 0 },
        { "time": 0.2, "value": 100 }
      ]
    }
  }
}
```

#### 步骤3：编译器→ExtendScript

```javascript
(function() {
  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  var layer = comp.selectedLayers[0] || comp.layer(1);
  if (!layer) {
    return JSON.stringify({ success: false, error: "E102" });
  }

  app.beginUndoGroup("Elastic Text Entrance");

  try {
    var inPoint = layer.inPoint;

    // 1. Position - 弹性表达式
    var posProp = layer.property("Transform").property("Position");
    posProp.expression = [
      'freq = 3; decay = 5;',
      'amp = 200; // 弹入幅度',
      't = Math.max(time - inPoint, 0);',
      'target = [960, 540];',
      'offset = amp * Math.sin(t * freq * 2 * Math.PI) / Math.exp(t * decay);',
      'target + [0, offset]'
    ].join('\n');

    // 2. Scale - 弹性缩放
    var scaleProp = layer.property("Transform").property("Scale");
    scaleProp.expression = [
      'freq = 4; decay = 6;',
      't = Math.max(time - inPoint, 0);',
      'startVal = 80; endVal = 100;',
      'if (t < 0.01) { [startVal, startVal]; }',
      'else {',
      '  amp = (endVal - startVal) * 0.15;',
      '  offset = amp * Math.sin(t * freq * 2 * Math.PI) / Math.exp(t * decay);',
      '  val = endVal + offset;',
      '  [val, val];',
      '}'
    ].join('\n');

    // 3. Opacity - 快速淡入
    var opacityProp = layer.property("Transform").property("Opacity");
    opacityProp.setValueAtTime(inPoint, 0);
    opacityProp.setValueAtTime(inPoint + 0.2, 100);

    // 设置缓动
    var kf1 = opacityProp.nearestKeyIndex(inPoint);
    var kf2 = opacityProp.nearestKeyIndex(inPoint + 0.2);
    opacityProp.setInterpolationTypeAtKey(kf1,
      KeyframeInterpolationType.LINEAR,
      KeyframeInterpolationType.BEZIER);
    opacityProp.setInterpolationTypeAtKey(kf2,
      KeyframeInterpolationType.BEZIER,
      KeyframeInterpolationType.BEZIER);

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      layerName: layer.name,
      animationsApplied: ["position_elastic", "scale_elastic", "opacity_fadeIn"]
    });
  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

### 4.6 端到端示例5：创建赛博朋克风格效果组合

**用户输入**："创建一个赛博朋克风格，要有故障效果、霓虹发光、扫描线和色差"

#### 步骤1：解析词汇

```json
{
  "input": "创建一个赛博朋克风格，要有故障效果、霓虹发光、扫描线和色差",
  "parsed": {
    "operation": "create_style_combo",
    "style": "cyberpunk",
    "effects": [
      {
        "type": "glitch",
        "effectMatchName": "ADBE DisplacementMap",
        "description": "故障位移效果"
      },
      {
        "type": "neon_glow",
        "effectMatchName": "ADBE Glo2",
        "description": "霓虹发光效果",
        "colorA": [0, 1, 1],
        "colorB": [1, 0, 1],
        "intensity": 2.0
      },
      {
        "type": "scanlines",
        "effectMatchName": "custom_scanlines",
        "description": "扫描线效果",
        "spacing": 4,
        "opacity": 30
      },
      {
        "type": "chromatic_aberration",
        "effectMatchName": "ADBE Shift Channels",
        "description": "色差/RGB分离效果",
        "shift": 3
      }
    ]
  }
}
```

推理过程：
- "赛博朋克" → 参考风格化预设宝典 → 效果组合配方
- "故障效果" → EI-045 Glitch → 位移映射+随机动画表达式
- "霓虹发光" → EI-015 Glow → 青色+品红双色发光
- "扫描线" → 自定义表达式/形状层 → 水平条纹叠加
- "色差" → EI-050 RGB分离 → 通道偏移3-5px

#### 步骤2：原子参数JSON

```json
{
  "operation": "createCyberpunkStyle",
  "target": { "compName": "auto-detect" },
  "effects": [
    {
      "layer": "target",
      "effectMatchName": "ADBE Glo2",
      "settings": {
        "Glow Threshold": 30,
        "Glow Radius": 60,
        "Glow Intensity": 2.0,
        "Color A": [0, 1, 1, 1],
        "Color B": [1, 0, 1, 1],
        "Glow Operation": 3
      }
    },
    {
      "layer": "target",
      "effectMatchName": "ADBE Channel Mixer",
      "settings": {
        "Red-Red": 100,
        "Red-Green": 0,
        "Green-Green": 100,
        "Blue-Blue": 100
      }
    }
  ],
  "additionalLayers": [
    {
      "type": "adjustment_layer",
      "name": "Scanlines",
      "effects": [
        {
          "effectMatchName": "ADBE Venetian Blinds",
          "settings": {
            "Transition Completion": 50,
            "Direction": 0,
            "Width": 4,
            "Feather": 0.5
          }
        }
      ],
      "blendMode": "MULTIPLY",
      "opacity": 30
    }
  ],
  "expressions": {
    "glitch_position": "seed = Math.floor(time * 15); seedRandom(seed, true); [random(-8, 8), random(-3, 3)]",
    "glitch_scale": "seed = Math.floor(time * 15); seedRandom(seed, true); [100 + random(-2, 2), 100]"
  }
}
```

#### 步骤3：编译器→ExtendScript

```javascript
(function() {
  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101" });
  }

  app.beginUndoGroup("Create Cyberpunk Style");

  try {
    // 1. 为目标图层添加霓虹发光
    var targetLayer = comp.selectedLayers[0] || comp.layer(1);
    if (!targetLayer) {
      return JSON.stringify({ success: false, error: "E102" });
    }

    var glow = targetLayer.Effects.addProperty("ADBE Glo2");
    glow.property("Glow Threshold").setValue(30);
    glow.property("Glow Radius").setValue(60);
    glow.property("Glow Intensity").setValue(2.0);
    glow.property("Color A").setValue([0, 1, 1, 1]);     // 青色
    glow.property("Color B").setValue([1, 0, 1, 1]);     // 品红
    glow.property("Glow Operation").setValue(3);          // Add模式

    // 2. 添加故障位移表达式
    var posProp = targetLayer.property("Transform").property("Position");
    posProp.expression = [
      '// 赛博朋克故障效果',
      'seed = Math.floor(time * 15);',
      'seedRandom(seed, true);',
      'glitchChance = random();',
      'if (glitchChance > 0.85) {',
      '  value + [random(-8, 8), random(-3, 3)];',
      '} else {',
      '  value;',
      '}'
    ].join('\n');

    // 3. 创建扫描线调整层
    var adjLayer = comp.layers.addSolid(
      [1, 1, 1],
      "Scanlines",
      comp.width, comp.height,
      comp.pixelAspect, comp.duration
    );
    adjLayer.adjustmentLayer = true;
    adjLayer.blendingMode = BlendingMode.MULTIPLY;
    adjLayer.property("Transform").property("Opacity").setValue(30);

    // 添加扫描线效果（使用Venetian Blinds近似）
    var scanEffect = adjLayer.Effects.addProperty("ADBE Venetian Blinds");
    scanEffect.property("Transition Completion").setValue(50);
    scanEffect.property("Direction").setValue(0);
    scanEffect.property("Width").setValue(4);
    scanEffect.property("Feather").setValue(0.5);

    // 4. 创建色差效果（RGB分离）
    var precompLayers = [targetLayer.index];
    var rgbShiftComp = comp.layers.precompose(
      precompLayers,
      "RGB Split",
      false
    );

    // 在预合成中添加色差
    var precomp = app.project.activeItem;
    for (var i = 1; i <= precomp.numLayers; i++) {
      var pLayer = precomp.layer(i);
      if (pLayer.Effects.numProperties === 0) {
        // 添加Shift Channels效果
        pLayer.Effects.addProperty("ADBE Shift Channels");
      }
    }

    // 切回主合成
    comp = app.project.activeItem;

    app.endUndoGroup();

    return JSON.stringify({
      success: true,
      effectsAdded: ["Glow (Neon)", "Glitch Position Expression", "Scanlines Adjustment", "RGB Split Precomp"],
      style: "cyberpunk"
    });

  } catch (e) {
    app.endUndoGroup();
    return JSON.stringify({ success: false, error: "E200: " + e.toString() });
  }
})();
```

#### 步骤4-5：MCP调用与验证

此复杂效果组合使用 `execute-atom-script` 工具执行，或分步使用 `batch-add-effects` + `setLayerExpression` + `add-adjustment-layer` 组合调用：

```typescript
// 分步调用方案
// Step 1: 批量添加效果
await mcpClient.callTool("batch-add-effects", {
  compName: "Comp 1",
  layerIndex: 1,
  effects: [
    {
      effectMatchName: "ADBE Glo2",
      settings: { "Glow Threshold": 30, "Glow Radius": 60, "Glow Intensity": 2.0 }
    }
  ]
});

// Step 2: 设置故障表达式
await mcpClient.callTool("setLayerExpression", {
  compName: "Comp 1",
  layerIndex: 1,
  propertyPath: "transform.position",
  expression: "seed = Math.floor(time * 15); seedRandom(seed, true); value + (random() > 0.85 ? [random(-8,8), random(-3,3)] : [0,0])"
});

// Step 3: 创建扫描线调整层
await mcpClient.callTool("add-adjustment-layer", {
  compName: "Comp 1",
  name: "Scanlines"
});

// Step 4: 设置混合模式和不透明度
await mcpClient.callTool("setLayerProperties", {
  compName: "Comp 1",
  layerIndex: 2,
  properties: { blendMode: "MULTIPLY", opacity: 30 }
});
```

---

## 附录A：常见效果matchName速查表

| 效果名称 | matchName | 分类 |
|---------|-----------|------|
| Gaussian Blur | ADBE Gaussian Blur 2 | 模糊 |
| Directional Blur | ADBE Motion Blur 2 | 模糊 |
| Radial Blur | ADBE Radial Blur 2 | 模糊 |
| Camera Lens Blur | ADBE Lens Blur | 模糊 |
| Fast Box Blur | ADBE Box Blur 2 | 模糊 |
| Glow | ADBE Glo2 | 发光辉光 |
| Drop Shadow | ADBE Drop Shadow | 发光辉光 |
| Inner Shadow | ADBE Inner Shadow | 发光辉光 |
| Outer Glow | ADBE Outer Glow | 发光辉光 |
| Inner Glow | ADBE Inner Glow | 发光辉光 |
| Levels | ADBE Pro Levels2 | 色彩调色 |
| Curves | ADBE Pro Curves2 | 色彩调色 |
| Hue/Saturation | ADBE HUE SATURATION | 色彩调色 |
| Color Balance | ADBE Color Balance 2 | 色彩调色 |
| Vibrance | ADBE Vibrance | 色彩调色 |
| Lumetri Color | ADBE Lumetri Color | 色彩调色 |
| CC Toner | CC Toner | 色彩调色 |
| Turbulent Displace | ADBE Turbulent Displace | 扭曲 |
| Mesh Warp | ADBE Mesh Warp | 扭曲 |
| Bulge | ADBE Bulge 2 | 扭曲 |
| Optics Compensation | ADBE Optics Compensation | 扭曲 |
| Wave Warp | ADBE Wave Warp 2 | 扭曲 |
| Distort | ADBE DisplacementMap | 扭曲 |
| Particular | TC Particular2 | 粒子(第三方) |
| Form | TC Form2 | 粒子(第三方) |
| Shine | ADBE Shine | 光效(第三方) |
| Starglow | ADBE Starglow | 光效(第三方) |
| Deep Glow | Deep Glow | 发光(第三方) |
| Saber | Saber | 发光(第三方) |
| Venetian Blinds | ADBE Venetian Blinds | 过渡 |
| CC Cross Blur | CC Cross Blur | 模糊 |
| Channel Mixer | ADBE Channel Mixer | 色彩 |
| Shift Channels | ADBE Shift Channels | 通道 |
| Noise | ADBE Noise2 | 噪点 |
| Remove Grain | ADBE Remove Grain | 降噪 |
| Unsharp Mask | ADBE Unsharp Mask2 | 锐化 |

## 附录B：Bridge面板轮询机制优化建议

### B.1 当前轮询机制的问题

1. **固定250ms轮询间隔**：低负载时浪费CPU，高负载时响应不够快
2. **无事件通知**：MCP Server无法主动获知Bridge状态变化
3. **单命令队列**：无法并行处理多个命令

### B.2 优化方案

#### 方案1：自适应轮询间隔

```javascript
// Bridge面板端自适应轮询
var BASE_INTERVAL = 250;    // 基础间隔
var MIN_INTERVAL = 50;      // 最小间隔（忙碌时）
var MAX_INTERVAL = 1000;    // 最大间隔（空闲时）
var currentInterval = BASE_INTERVAL;

function adaptivePoll() {
  var hasCommand = checkCommandFile();

  if (hasCommand) {
    // 有命令时缩短间隔
    currentInterval = Math.max(currentInterval * 0.7, MIN_INTERVAL);
  } else {
    // 无命令时延长间隔
    currentInterval = Math.min(currentInterval * 1.1, MAX_INTERVAL);
  }

  setTimeout(adaptivePoll, currentInterval);
}
```

#### 方案2：WebSocket通知（未来）

```
┌──────────────┐   WebSocket   ┌──────────────┐
│  MCP Server  │ ←───────────→ │  Bridge Panel │
│              │   双向实时通信  │              │
└──────────────┘               └──────────────┘
     不再需要文件轮询！
```

WebSocket方案将轮询延迟从250ms降低到<10ms，且支持双向事件通知，是未来的推荐方案。

## 附录C：安全规范

### C.1 allowedScripts白名单

所有新增JSX脚本必须加入白名单才能被Bridge执行。白名单配置：

```json
{
  "allowedScripts": [
    "addEffectWithKeyframes.jsx",
    "setKeyframeEasing.jsx",
    "batchAddEffects.jsx",
    "setBlendMode.jsx",
    "setTrackMatte.jsx",
    "setParentLayer.jsx",
    "addAdjustmentLayer.jsx",
    "addPrecomp.jsx",
    "importFootage.jsx",
    "setMotionBlur.jsx",
    "addMaskWithShape.jsx",
    "executeAtomScript.jsx",
    "getEffectProperties.jsx",
    "setEffectKeyframes.jsx"
  ],
  "securityPolicy": {
    "allowCustomScripts": true,
    "customScriptValidation": true,
    "maxScriptLength": 65536,
    "forbiddenAPIs": ["system.callSystem", "File.saveDialog"],
    "requireApproval": ["execute-atom-script"]
  }
}
```

### C.2 execute-atom-script安全控制

`execute-atom-script` 是最危险的工具（可执行任意代码），需要额外的安全控制：

1. **脚本长度限制**：最大64KB
2. **API白名单**：禁止调用 `system.callSystem()`、`File.saveDialog()` 等系统级API
3. **干运行验证**：正式执行前可先 dryRun 验证语法
4. **审批机制**：首次使用时需要用户确认
5. **沙箱标记**：在受限模式下执行的脚本自动添加try-catch包装

---

> **文档版本**：v1.0 | **最后更新**：2026-07-05 | **维护者**：AE Knowledge Vault

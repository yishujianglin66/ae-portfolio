---
title: AE ExtendScript API 原子级映射手册
date: 2026-07-05
tags:
  - ExtendScript
  - API映射
  - 原子级
  - 自动化
  - MCP
  - 编译器
---

# AE ExtendScript API 原子级映射手册

> [!abstract] 文档摘要
> 本手册是知识库从"原子级参数描述"到"ExtendScript可执行代码"的完整映射参考。覆盖AE DOM对象模型、60个效果的matchName、关键帧缓动API、表达式注入、遮罩操作、第三方插件脚本控制，以及13个扩展MCP脚本模板。matchName是脚本执行的唯一可靠标识，本文档提供每个效果的matchName到属性到setValue的原子级映射。

> [!tip] 使用指南
> - MCP工具开发者：直接跳转到第十章脚本模板，复制粘贴即可使用
> - 编译器开发者：第四章效果matchName映射是代码生成的核心数据源
> - 逆向分析→AE执行：先查《参数-效果原子级映射库》获取参数，再查本手册获取matchName和setValue代码
> - 第三方插件控制：第八章提供32个插件的matchName查找表和运行时查找脚本

> 本手册是 after-effects-mcp-main 项目从"原子级参数描述"到"ExtendScript可执行代码"的完整映射参考。所有代码使用 ExtendScript ES3 语法（var、无 let/const、无箭头函数、无模板字符串）。matchName 是脚本执行的唯一可靠标识。

---

## 第一章 项目对象模型（DOM）原子级映射

### 1.1 app 对象

- **访问路径**: 全局根对象，直接使用 `app`
- **matchName**: 无（根对象）
- **核心属性**:

| 属性 | 类型 | 说明 | 示例 |
|------|------|------|------|
| project | Project | 当前打开的项目 | `app.project` |
| activeItem | Item | 当前选中的项目项 | `app.activeItem` |
| settings | Settings | 应用设置对象 | `app.settings` |
| version | String | AE版本号 | `app.version` |
| isQuickTimeAvailable | Boolean | QT是否可用 | `app.isQuickTimeAvailable` |
| isRenderEngine | Boolean | 是否为渲染引擎模式 | `app.isRenderEngine` |

- **核心方法**:

| 方法 | 返回值 | 说明 | 示例 |
|------|--------|------|------|
| beginUndoGroup(name) | void | 开始撤销组 | `app.beginUndoGroup("My Script")` |
| endUndoGroup() | void | 结束撤销组 | `app.endUndoGroup()` |
| newProject() | Project | 新建项目 | `app.newProject()` |
| open(filepath) | Project | 打开项目 | `app.open(File("C:/project.aep"))` |
| quit() | void | 退出AE | `app.quit()` |
| purge(PurgeTarget) | void | 清除缓存 | `app.purge(PurgeTarget.ALL_CACHES)` |

- **原子级示例代码**:

```javascript
// 安全获取当前合成的原子级操作
var comp = null;
if (app.project && app.project.activeItem && app.project.activeItem instanceof CompItem) {
    comp = app.project.activeItem;
    alert("当前合成: " + comp.name + ", 时长: " + comp.duration + "秒");
} else {
    alert("没有打开的合成");
}
```

### 1.2 Project 对象

- **访问路径**: `app.project`
- **核心属性**:

| 属性 | 类型 | 说明 | 示例 |
|------|------|------|------|
| items | ItemCollection | 项目中所有项的集合 | `app.project.items` |
| rootFolder | FolderItem | 项目根文件夹 | `app.project.rootFolder` |
| numItems | Number | 项目项数量 | `app.project.numItems` |
| activeItem | Item | 当前活动项 | `app.project.activeItem` |
| file | File | 项目文件路径 | `app.project.file` |

- **核心方法**:

| 方法 | 返回值 | 说明 | 示例 |
|------|--------|------|------|
| save() | void | 保存项目 | `app.project.save()` |
| saveAs(file) | void | 另存为 | `app.project.saveAs(File("C:/new.aep"))` |
| close(CloseOptions) | void | 关闭项目 | `app.project.close(CloseOptions.PROMPT_TO_SAVE)` |
| item(index) | Item | 按索引获取项 | `app.project.item(1)` |
| consolidation() | void | 整合素材 | `app.project.consolidation()` |
| reduceProject(items) | void | 精简项目 | `app.project.reduceProject([item1, item2])` |
| importFile(importOptions) | FootageItem | 导入素材 | `app.project.importFile(new ImportOptions(File("C:/video.mp4")))` |

- **原子级示例代码**:

```javascript
// 遍历项目中的所有合成
var proj = app.project;
for (var i = 1; i <= proj.numItems; i++) {
    var item = proj.item(i);
    if (item instanceof CompItem) {
        alert("合成: " + item.name + " 尺寸: " + item.width + "x" + item.height);
    }
}
```

### 1.3 CompItem 对象

- **访问路径**: `app.project.item(index)` 或 `app.project.activeItem`
- **核心属性**:

| 属性 | 类型 | 说明 | 默认值 | 示例 |
|------|------|------|--------|------|
| layers | LayerCollection | 合成中所有图层 | - | `comp.layers` |
| duration | Number | 合成时长(秒) | 30 | `comp.duration` |
| frameRate | Number | 帧率 | 30 | `comp.frameRate` |
| width | Number | 合成宽度(px) | 1920 | `comp.width` |
| height | Number | 合成高度(px) | 1080 | `comp.height` |
| bgColor | [R,G,B] | 背景颜色 | [0,0,0] | `comp.bgColor = [0.1, 0.1, 0.1]` |
| workAreaStart | Number | 工作区起始时间 | 0 | `comp.workAreaStart` |
| workAreaDuration | Number | 工作区持续时长 | duration | `comp.workAreaDuration` |
| numLayers | Number | 图层数量 | - | `comp.numLayers` |
| frameDuration | Number | 帧持续时间(秒) | 1/30 | `comp.frameDuration` |
| displayStartTime | Number | 显示起始时间 | 0 | `comp.displayStartTime` |
| motionBlur | Boolean | 运动模糊开关 | false | `comp.motionBlur = true` |
| motionBlurAdaptiveSampleLimit | Number | 运动模糊采样上限 | 128 | `comp.motionBlurAdaptiveSampleLimit = 256` |
| shutterAngle | Number | 快门角度 | 180 | `comp.shutterAngle = 360` |
| resolutionFactor | [x,y] | 分辨率因子 | [1,1] | `comp.resolutionFactor = [0.5, 0.5]` |
| pixelAspect | Number | 像素宽高比 | 1 | `comp.pixelAspect` |

- **核心方法**:

| 方法 | 返回值 | 说明 | 示例 |
|------|--------|------|------|
| layer(index) | Layer | 按索引获取图层 | `comp.layer(1)` |
| layer(name) | Layer | 按名称获取图层 | `comp.layer("Layer 1")` |
| duplicate() | CompItem | 复制合成 | `comp.duplicate()` |

- **原子级示例代码**:

```javascript
// 创建并配置合成
var comp = app.project.items.addComp(
    "My Comp",       // 名称
    1920,            // 宽度
    1080,            // 高度
    1,               // 像素宽高比
    10,              // 时长(秒)
    30               // 帧率
);
comp.bgColor = [0.05, 0.05, 0.05];
comp.workAreaStart = 1;
comp.workAreaDuration = 5;
comp.motionBlur = true;
comp.shutterAngle = 180;
```

### 1.4 Layer 对象族

AE中图层有多种类型，每种类型具有不同的属性和方法。

#### 1.4.1 通用 Layer 属性

| 属性 | 类型 | 说明 | 示例 |
|------|------|------|------|
| name | String | 图层名称 | `layer.name = "My Layer"` |
| index | Number | 图层索引 | `layer.index` |
| startTime | Number | 起始时间(秒) | `layer.startTime` |
| inPoint | Number | 入点 | `layer.inPoint` |
| outPoint | Number | 出点 | `layer.outPoint` |
| duration | Number | 持续时长 | `layer.duration` |
| stretch | Number | 拉伸比(%) | `layer.stretch = 200` |
| is3D | Boolean | 3D图层开关 | `layer.is3D` |
| threeDLayer | Boolean | 3D图层(写) | `layer.threeDLayer = true` |
| enabled | Boolean | 图层启用状态 | `layer.enabled = true` |
| locked | Boolean | 锁定状态 | `layer.locked = false` |
| shy | Boolean | 隐藏状态 | `layer.shy = false` |
| solo | Boolean | Solo状态 | `layer.solo = false` |
| parent | Layer | 父图层 | `layer.parent = comp.layer(1)` |
| blendingMode | BlendingMode | 混合模式 | `layer.blendingMode = BlendingMode.ADD` |
| trackMatteType | TrackMatteType | 轨道遮罩类型 | `layer.trackMatteType = TrackMatteType.ALPHA` |
| adjustmentLayer | Boolean | 调整层开关(AVLayer) | `layer.adjustmentLayer = true` |
| guideLayer | Boolean | 引导层开关 | `layer.guideLayer = false` |
| quality | QualityValue | 图层质量 | `layer.quality = QualityValue.BEST` |
| samplingQuality | LayerSamplingQuality | 采样质量 | `layer.samplingQuality` |

#### 1.4.2 AVLayer

- **访问路径**: `comp.layers.addSolid()` / `comp.layer(index)` (素材图层)
- **特有属性**: source / height / width / adjustmentLayer / audioEnabled / hasAudio / hasVideo
- **特有方法**: replace(file) / replaceWithPlaceholder()

#### 1.4.3 ShapeLayer

- **访问路径**: `comp.layers.addShape()`
- **特有属性**: contents (PropertyGroup)
- **特有方法**: 无额外方法，通过contents操作形状组

#### 1.4.4 TextLayer

- **访问路径**: `comp.layers.addText()`
- **特有属性**: text (PropertyGroup) / sourceText (Property)
- **特有方法**: 无额外方法，通过text属性操作

#### 1.4.5 CameraLayer

- **访问路径**: `comp.layers.addCamera()`
- **特有属性**: cameraOption (PropertyGroup) / zoom / depthOfField / focusDistance / aperture / blurLevel / irisShape / irisRotation / irisRoundness / irisAspectRatio / irisDiffractionFringe / highlightGain / highlightThreshold

#### 1.4.6 LightLayer

- **访问路径**: `comp.layers.addLight()`
- **特有属性**: lightOption (PropertyGroup) / intensity / color / coneAngle / coneFeather / falloff / radius / falloffDistance / castsShadows / shadowDarkness / shadowDiffusion

#### 1.4.7 NullLayer

- **访问路径**: `comp.layers.addNull()`
- **说明**: 继承AVLayer，尺寸固定为100x100，不可见

#### 1.4.8 AdjustmentLayer

- **访问路径**: 通过 `comp.layers.addSolid()` + `layer.adjustmentLayer = true` 创建
- **说明**: 本质是AVLayer，通过adjustmentLayer属性标记

- **原子级示例代码**:

```javascript
var comp = app.project.activeItem;

// 创建空对象
var nullLayer = comp.layers.addNull(5);
nullLayer.name = "Controller Null";

// 创建调整层
var adjLayer = comp.layers.addSolid([1,1,1], "Adjustment", comp.width, comp.height, comp.pixelAspect, comp.duration);
adjLayer.adjustmentLayer = true;

// 创建3D图层
var solid = comp.layers.addSolid([0.5, 0.2, 0.8], "3D Solid", 200, 200, 1, 5);
solid.threeDLayer = true;

// 设置父子关系
solid.parent = nullLayer;
```

### 1.5 Property 对象

- **访问路径**: `layer.property("ADBE Transform Group").property("ADBE Position")` 等
- **核心属性**:

| 属性 | 类型 | 说明 | 示例 |
|------|------|------|------|
| value | any | 当前值 | `prop.value` |
| name | String | 属性名 | `prop.name` |
| matchName | String | 匹配名 | `prop.matchName` |
| numKeys | Number | 关键帧数量 | `prop.numKeys` |
| expression | String | 表达式 | `prop.expression = "wiggle(5,20)"` |
| expressionEnabled | Boolean | 表达式启用状态 | `prop.expressionEnabled = true` |
| isTimeVarying | Boolean | 是否有时间变化 | `prop.isTimeVarying` |
| propertyValueType | PropertyValueType | 值类型 | `prop.propertyValueType` |
| propertyIndex | Number | 属性索引 | `prop.propertyIndex` |
| canSetExpression | Boolean | 是否可设表达式 | `prop.canSetExpression` |
| selectedKeys | Number[] | 选中的关键帧 | `prop.selectedKeys` |
| dimensionsSeparated | Boolean | 维度是否分离 | `prop.dimensionsSeparated` |

- **核心方法**:

| 方法 | 返回值 | 说明 | 示例 |
|------|--------|------|------|
| setValue(value) | void | 设置值 | `prop.setValue([100, 200])` |
| setValueAtTime(value, time) | KeyframeIndex | 在指定时间设置关键帧 | `prop.setValueAtTime([100,200], 1.0)` |
| addKey(time) | KeyframeIndex | 在指定时间添加关键帧 | `prop.addKey(2.0)` |
| setInterpolationTypeAtKey(idx, type) | void | 设置关键帧插值类型 | `prop.setInterpolationTypeAtKey(1, KeyframeInterpolationType.BEZIER)` |
| setTemporalEaseAtKey(idx, inEase, outEase) | void | 设置时间缓动 | `prop.setTemporalEaseAtKey(1, [ease1], [ease2])` |
| setSpatialTangentsAtKey(idx, inTangent, outTangent) | void | 设置空间切线 | `prop.setSpatialTangentsAtKey(1, [0,0], [0,0])` |
| valueAtTime(time) | any | 获取指定时间的值 | `prop.valueAtTime(1.5)` |
| keyTime(idx) | Number | 获取关键帧时间 | `prop.keyTime(1)` |
| keyValue(idx) | any | 获取关键帧值 | `prop.keyValue(1)` |
| removeKey(idx) | void | 删除关键帧 | `prop.removeKey(1)` |
| isInterpolationTypeValid(type) | Boolean | 检查插值类型是否有效 | `prop.isInterpolationTypeValid(KeyframeInterpolationType.BEZIER)` |

- **原子级示例代码**:

```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var pos = layer.property("ADBE Transform Group").property("ADBE Position");

// 设置位置值
pos.setValue([960, 540]);

// 添加关键帧
pos.setValueAtTime([960, 540], 0);
pos.setValueAtTime([1920, 540], 1);
pos.setValueAtTime([960, 540], 2);

// 设置缓动
var easeIn = new KeyframeEase(0, 33);
var easeOut = new KeyframeEase(0, 33);
pos.setTemporalEaseAtKey(2, [easeIn, easeIn], [easeOut, easeOut]);
pos.setInterpolationTypeAtKey(2, KeyframeInterpolationType.BEZIER);

// 设置表达式
pos.expression = "wiggle(3, 50)";
```

### 1.6 Effect 对象

- **访问路径**: `layer.Effects.addProperty("ADBE Gaussian Blur 2")` / `layer.Effects.property(index)`
- **核心属性**:

| 属性 | 类型 | 说明 | 示例 |
|------|------|------|------|
| name | String | 效果名 | `effect.name` |
| matchName | String | 匹配名 | `effect.matchName` |
| isEnabled | Boolean | 效果启用状态 | `effect.isEnabled = true` |
| active | Boolean | 效果是否激活 | `effect.active` |
| numProperties | Number | 子属性数量 | `effect.numProperties` |

- **核心方法**:

| 方法 | 返回值 | 说明 | 示例 |
|------|--------|------|------|
| property(index) | Property | 按索引获取子属性 | `effect.property(1)` |
| property(matchName) | Property | 按匹配名获取子属性 | `effect.property("Blurriness")` |
| remove() | void | 删除效果 | `effect.remove()` |
| moveTo(index) | void | 移动效果位置 | `effect.moveTo(1)` |

- **原子级示例代码**:

```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);

// 添加高斯模糊效果
var blur = layer.Effects.addProperty("ADBE Gaussian Blur 2");
blur.property("Blurriness").setValue(25);
blur.property("Blur Dimensions").setValue(1); // 1=Both

// 添加第二个效果
var glow = layer.Effects.addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(50);
glow.property("Glow Intensity").setValue(1.5);

// 禁用效果
blur.isEnabled = false;

// 删除效果
glow.remove();
```

### 1.7 MaskPropertyGroup 对象

- **访问路径**: `layer.Masks.addProperty("Mask 1")`
- **核心属性**:

| 属性 | matchName | 类型 | 默认值 | 说明 |
|------|-----------|------|--------|------|
| Mask Shape | ADBE Mask Shape | Shape | 空矩形 | 遮罩路径 |
| Mask Feather | ADBE Mask Feather | [x,y] | [0,0] | 羽化量 |
| Mask Opacity | ADBE Mask Opacity | Percentage | 100 | 不透明度 |
| Mask Expansion | ADBE Mask Expansion | Number | 0 | 扩展量 |
| Mask Mode | ADBE Mask Mode | int | 0 | 遮罩模式 |

- **原子级示例代码**:

```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);

// 创建遮罩
var mask = layer.Masks.addProperty("My Mask");

// 设置矩形遮罩路径
var shape = new Shape();
shape.vertices = [[100, 100], [500, 100], [500, 500], [100, 500]];
shape.inTangents = [[0,0], [0,0], [0,0], [0,0]];
shape.outTangents = [[0,0], [0,0], [0,0], [0,0]];
shape.closed = true;
mask.property("ADBE Mask Shape").setValue(shape);

// 设置遮罩属性
mask.property("ADBE Mask Feather").setValue([20, 20]);
mask.property("ADBE Mask Opacity").setValue(80);
mask.property("ADBE Mask Expansion").setValue(10);
mask.property("ADBE Mask Mode").setValue(MaskMode.ADD);
```

---

## 第二章 合成创建与操作的原子级脚本

### 2.1 创建合成

**ExtendScript函数签名**:
```javascript
app.project.items.addComp(name, width, height, pixelAspect, duration, frameRate)
```

**参数Schema**:
```json
{
    "name": "合成名称",
    "width": 1920,
    "height": 1080,
    "pixelAspect": 1,
    "duration": 10,
    "frameRate": 30
}
```

**原子级代码**:
```javascript
var comp = app.project.items.addComp("My Composition", 1920, 1080, 1, 10, 30);
```

**MCP JSON调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.items.addComp('My Composition', 1920, 1080, 1, 10, 30); JSON.stringify({name: comp.name, width: comp.width, height: comp.height, duration: comp.duration, frameRate: comp.frameRate})"
    }
}
```

### 2.2 设置合成属性

**原子级代码**:
```javascript
var comp = app.project.activeItem;

// 设置时长
comp.duration = 30;

// 设置帧率
comp.frameRate = 24;

// 设置尺寸
comp.width = 3840;
comp.height = 2160;

// 设置背景颜色（0-1范围，RGB）
comp.bgColor = [0.1, 0.1, 0.15];

// 设置分辨率因子（0.5 = 半分辨率）
comp.resolutionFactor = [1, 1];
```

**MCP JSON调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; comp.bgColor = [0.05, 0.05, 0.1]; comp.duration = 15; comp.frameRate = 60; JSON.stringify({success: true})"
    }
}
```

### 2.3 工作区域操作

**ExtendScript函数签名**:
```javascript
comp.workAreaStart = startTime;    // 起始时间(秒)
comp.workAreaDuration = duration;  // 持续时长(秒)
```

**原子级代码**:
```javascript
var comp = app.project.activeItem;

// 设置工作区域：从2秒开始，持续5秒
comp.workAreaStart = 2;
comp.workAreaDuration = 5;

// 设置工作区域为整个合成
comp.workAreaStart = 0;
comp.workAreaDuration = comp.duration;
```

**MCP JSON调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; comp.workAreaStart = 2; comp.workAreaDuration = 5; JSON.stringify({workAreaStart: comp.workAreaStart, workAreaDuration: comp.workAreaDuration})"
    }
}
```

### 2.4 渲染队列操作

**ExtendScript函数签名**:
```javascript
// 添加到渲染队列
var rqItem = app.project.renderQueue.items.add(comp);

// 设置输出模块
var om = rqItem.outputModule(1);
om.applyTemplate("Lossless");  // 使用预设模板
om.file = File("C:/output/output.mov");

// 设置渲染设置
rqItem.applyRenderTemplate("Best Settings");

// 渲染
app.project.renderQueue.render();
```

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var rqItem = app.project.renderQueue.items.add(comp);
var om = rqItem.outputModule(1);
om.applyTemplate("Lossless");
om.file = File("C:/output/render.mov");

// 状态检查
var status = rqItem.status; // RQItemStatus.DONE / RENDERING / QUEUED / WILL_RENDER / USER_STOPPED / ERR_STOPPED

// 开始渲染
app.project.renderQueue.render();
```

**MCP JSON调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var rq = app.project.renderQueue.items.add(comp); var om = rq.outputModule(1); om.applyTemplate('Lossless'); om.file = File('C:/output/render.mov'); JSON.stringify({status: rq.status, output: om.file.fsName})"
    }
}
```

---

## 第三章 图层创建与操作的原子级脚本

### 3.1 创建文字层

**ExtendScript函数签名**:
```javascript
// 基础创建
var textLayer = comp.layers.addText("Hello World");

// 带TextDocument创建
var textDoc = new TextDocument("Hello World");
textDoc.font = "Arial";
textDoc.fontSize = 72;
textDoc.fillColor = [1, 1, 1];
textDoc.strokeColor = [0, 0, 0];
textDoc.strokeWidth = 2;
textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
textDoc.tracking = 50;
textDoc.leading = 80;
var textLayer = comp.layers.addText(textDoc);
```

**完整参数映射**:

| 属性 | 访问路径 | 类型 | 默认值 | 说明 |
|------|----------|------|--------|------|
| sourceText | text.property("ADBE Text Properties").property("ADBE Text Document") | TextDocument | "Text" | 文本内容对象 |
| font | textDoc.font | String | "Arial" | 字体族名 |
| fontSize | textDoc.fontSize | Number | 36 | 字号 |
| fillColor | textDoc.fillColor | [R,G,B] | [1,1,1] | 填充颜色 |
| strokeColor | textDoc.strokeColor | [R,G,B] | [0,0,0] | 描边颜色 |
| strokeWidth | textDoc.strokeWidth | Number | 0 | 描边宽度 |
| justification | textDoc.justification | int | 6882(TITLE) | 对齐方式 |
| tracking | textDoc.tracking | Number | 0 | 字间距 |
| leading | textDoc.leading | Number | auto | 行高 |
| applyFill | textDoc.applyFill | Boolean | true | 是否填充 |
| applyStroke | textDoc.applyStroke | Boolean | false | 是否描边 |
| fauxBold | textDoc.fauxBold | Boolean | false | 伪粗体 |
| fauxItalic | textDoc.fauxItalic | Boolean | false | 伪斜体 |
| allCaps | textDoc.allCaps | Boolean | false | 全部大写 |
| smallCaps | textDoc.smallCaps | Boolean | false | 小型大写 |
| superscript | textDoc.superscript | Boolean | false | 上标 |
| subscript | textDoc.subscript | Boolean | false | 下标 |
| text | textDoc.text | String | - | 文本字符串 |
| baselineShift | textDoc.baselineShift | Number | 0 | 基线偏移 |
| tsume | textDoc.tsume | Number | 0 | 字符缩放 |
| horizontalScale | textDoc.horizontalScale | Number | 100 | 水平缩放 |
| verticalScale | textDoc.verticalScale | Number | 100 | 垂直缩放 |

**justification枚举值**:
- `ParagraphJustification.LEFT_JUSTIFY` = 6881
- `ParagraphJustification.CENTER_JUSTIFY` = 6882
- `ParagraphJustification.RIGHT_JUSTIFY` = 6883
- `ParagraphJustification.FULL_JUSTIFY_LASTLINE_LEFT` = 6884
- `ParagraphJustification.FULL_JUSTIFY_LASTLINE_RIGHT` = 6885
- `ParagraphJustification.FULL_JUSTIFY_LASTLINE_CENTER` = 6886
- `ParagraphJustification.FULL_JUSTIFY_LASTLINE_FULL` = 6887

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var textDoc = new TextDocument("风格化标题");
textDoc.font = "Microsoft YaHei";
textDoc.fontSize = 96;
textDoc.fillColor = [1, 1, 1];
textDoc.strokeColor = [0, 0, 0];
textDoc.strokeWidth = 0;
textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
textDoc.tracking = 100;
textDoc.applyFill = true;
textDoc.applyStroke = false;
var textLayer = comp.layers.addText(textDoc);
textLayer.name = "Title Text";
```

**MCP JSON调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var td = new TextDocument('Hello AE'); td.font = 'Arial'; td.fontSize = 72; td.fillColor = [1,1,1]; td.justification = ParagraphJustification.CENTER_JUSTIFY; var tl = comp.layers.addText(td); JSON.stringify({name: tl.name, index: tl.index})"
    }
}
```

### 3.2 创建实色层

**ExtendScript函数签名**:
```javascript
comp.layers.addSolid(color, name, width, height, pixelAspect, duration)
```

**参数Schema**:
```json
{
    "color": [1, 0, 0],
    "name": "Red Solid",
    "width": 1920,
    "height": 1080,
    "pixelAspect": 1,
    "duration": 10
}
```

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid(
    [0.2, 0.4, 0.8],   // 颜色 (0-1范围)
    "Blue Solid",        // 名称
    comp.width,          // 宽度
    comp.height,         // 高度
    comp.pixelAspect,    // 像素宽高比
    comp.duration        // 时长
);
```

**MCP JSON调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var s = comp.layers.addSolid([0.2,0.4,0.8], 'Blue Solid', comp.width, comp.height, comp.pixelAspect, comp.duration); JSON.stringify({name: s.name, index: s.index})"
    }
}
```

### 3.3 创建形状层

**ExtendScript函数签名**:
```javascript
var shapeLayer = comp.layers.addShape();
```

#### 矩形路径

```javascript
var shapeLayer = comp.layers.addShape();
shapeLayer.name = "Rectangle";

// 添加矩形
var rectGroup = shapeLayer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
rectGroup.name = "Rectangle Group";

var rectPath = rectGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Rect");
rectPath.property("ADBE Vector Rect Size").setValue([200, 100]);
rectPath.property("ADBE Vector Rect Position").setValue([0, 0]);
rectPath.property("ADBE Vector Rect Roundness").setValue(10);

// 添加填充
var fill = rectGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
fill.property("ADBE Vector Fill Color").setValue([1, 0, 0, 1]);
fill.property("ADBE Vector Fill Rule").setValue(1); // 1=Non-Zero, 2=Even-Odd

// 添加描边
var stroke = rectGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Stroke");
stroke.property("ADBE Vector Stroke Color").setValue([0, 0, 0, 1]);
stroke.property("ADBE Vector Stroke Width").setValue(2);
stroke.property("ADBE Vector Stroke Line Cap").setValue(2); // 1=Butt, 2=Round, 3=Projecting
stroke.property("ADBE Vector Stroke Line Join").setValue(2); // 1=Miter, 2=Round, 3=Bevel
```

#### 椭圆路径

```javascript
var shapeLayer = comp.layers.addShape();
shapeLayer.name = "Ellipse";

var ellipseGroup = shapeLayer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
ellipseGroup.name = "Ellipse Group";

var ellipsePath = ellipseGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Ellipse");
ellipsePath.property("ADBE Vector Ellipse Size").setValue([200, 200]);
ellipsePath.property("ADBE Vector Ellipse Position").setValue([0, 0]);

var fill = ellipseGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
fill.property("ADBE Vector Fill Color").setValue([0, 0.5, 1, 1]);
```

#### 星形路径

```javascript
var shapeLayer = comp.layers.addShape();
shapeLayer.name = "Star";

var starGroup = shapeLayer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
starGroup.name = "Star Group";

var starPath = starGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Star");
starPath.property("ADBE Vector Star Points").setValue(5);       // 星形点数
starPath.property("ADBE Vector Star Position").setValue([0, 0]);
starPath.property("ADBE Vector Star Outer Radius").setValue(100);
starPath.property("ADBE Vector Star Inner Radius").setValue(50);
starPath.property("ADBE Vector Star Outer Roundness").setValue(0);
starPath.property("ADBE Vector Star Inner Roundness").setValue(0);
starPath.property("ADBE Vector Star Rotation").setValue(0);

var fill = starGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
fill.property("ADBE Vector Fill Color").setValue([1, 0.8, 0, 1]);
```

#### 多边形路径

```javascript
var shapeLayer = comp.layers.addShape();
shapeLayer.name = "Polygon";

var polyGroup = shapeLayer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
polyGroup.name = "Polygon Group";

var polyPath = polyGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Polystar");
polyPath.property("ADBE Vector Polystar Points").setValue(6);   // 多边形边数
polyPath.property("ADBE Vector Polystar Position").setValue([0, 0]);
polyPath.property("ADBE Vector Polystar Outer Radius").setValue(100);
polyPath.property("ADBE Vector Polystar Outer Roundness").setValue(0);
polyPath.property("ADBE Vector Polystar Rotation").setValue(0);

var fill = polyGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
fill.property("ADBE Vector Fill Color").setValue([0.5, 1, 0.5, 1]);
```

#### 自定义路径（贝塞尔曲线路径）

```javascript
var shapeLayer = comp.layers.addShape();
shapeLayer.name = "Custom Path";

var pathGroup = shapeLayer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
pathGroup.name = "Path Group";

var path = pathGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Group");
var shape = new Shape();
shape.vertices = [[0, 0], [100, -50], [200, 0], [150, 100], [50, 100]];
shape.inTangents = [[0,0], [-30,20], [0,30], [30,0], [-30,0]];
shape.outTangents = [[0,-30], [30,-20], [30,0], [0,-30], [30,0]];
shape.closed = true;
path.property("ADBE Vector Shape").setValue(shape);
```

### 3.4 创建调整层

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var adjLayer = comp.layers.addSolid(
    [1, 1, 1],          // 调整层颜色无意义
    "Adjustment Layer",
    comp.width,
    comp.height,
    comp.pixelAspect,
    comp.duration
);
adjLayer.adjustmentLayer = true;
// 调整层现在可以添加效果，效果将影响其下方所有图层
adjLayer.Effects.addProperty("ADBE Gaussian Blur 2");
adjLayer.Effects.property(1).property("Blurriness").setValue(20);
```

**MCP JSON调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var adj = comp.layers.addSolid([1,1,1], 'Adjustment Layer', comp.width, comp.height, comp.pixelAspect, comp.duration); adj.adjustmentLayer = true; adj.Effects.addProperty('ADBE Gaussian Blur 2'); adj.Effects.property(1).property('Blurriness').setValue(20); JSON.stringify({name: adj.name, isAdjustment: adj.adjustmentLayer})"
    }
}
```

### 3.5 创建空对象

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var nullObj = comp.layers.addNull(comp.duration);
nullObj.name = "Null Controller";
```

### 3.6 创建摄像机层

**ExtendScript函数签名**:
```javascript
comp.layers.addCamera(name, centerPoint)
```

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var camera = comp.layers.addCamera("Main Camera", [comp.width / 2, comp.height / 2]);
camera.property("ADBE Transform Group").property("ADBE Position").setValue([960, 540, -1000]);

// 摄像机参数
camera.property("ADBE Camera Options Group").property("ADBE Camera Zoom").setValue(1000);
camera.property("ADBE Camera Options Group").property("ADBE Camera Depth of Field").setValue(0);
camera.property("ADBE Camera Options Group").property("ADBE Camera Focus Distance").setValue(500);
camera.property("ADBE Camera Options Group").property("ADBE Camera Aperture").setValue(10);
```

### 3.7 创建灯光层

**ExtendScript函数签名**:
```javascript
comp.layers.addLight(name, centerPoint)
```

**原子级代码**:
```javascript
var comp = app.project.activeItem;

// 创建点光源
var light = comp.layers.addLight("Point Light", [960, 540, -400]);
light.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(100);
light.property("ADBE Light Options Group").property("ADBE Light Color").setValue([1, 1, 1]);
light.property("ADBE Light Options Group").property("ADBE Light Falloff").setValue(2); // 0=None,1=Smooth,2=Linear
light.property("ADBE Light Options Group").property("ADBE Light Radius").setValue(50);
light.property("ADBE Light Options Group").property("ADBE Light Falloff Distance").setValue(500);
```

### 3.8 图层通用属性操作

#### Transform属性

```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var transform = layer.property("ADBE Transform Group");

// Position
transform.property("ADBE Position").setValue([960, 540]);

// Scale (百分比)
transform.property("ADBE Scale").setValue([100, 100]);

// Rotation (度)
transform.property("ADBE Rotation").setValue(45);

// Opacity (百分比)
transform.property("ADBE Opacity").setValue(80);

// Anchor Point
transform.property("ADBE Anchor Point").setValue([0, 0]);

// 3D位置（分离维度时）
transform.property("ADBE Position").dimensionsSeparated = true;
transform.property("ADBE Position_0").setValue(960);  // X
transform.property("ADBE Position_1").setValue(540);  // Y
transform.property("ADBE Position_2").setValue(0);    // Z

// X/Y/Z Rotation (3D图层)
transform.property("ADBE Rotate X").setValue(30);
transform.property("ADBE Rotate Y").setValue(45);
transform.property("ADBE Rotate Z").setValue(0);

// Orientation (3D图层)
transform.property("ADBE Orientation").setValue([30, 45, 0]);
```

#### 时间属性

```javascript
// 设置起始时间
layer.startTime = 2;

// 设置入点/出点
layer.inPoint = 2;
layer.outPoint = 8;

// 设置拉伸
layer.stretch = 50; // 50%速度（2倍慢放）
```

#### 混合模式（全部枚举值）

```javascript
layer.blendingMode = BlendingMode.ADD;
```

| 枚举值 | 数值 | 说明 |
|--------|------|------|
| BlendingMode.ADD | 7952 | 相加 |
| BlendingMode.ALPHA_ADD | 7953 | Alpha相加 |
| BlendingMode.CLASSIC_COLOR_BURN | 7946 | 经典颜色加深 |
| BlendingMode.CLASSIC_COLOR_DODGE | 7947 | 经典颜色减淡 |
| BlendingMode.CLASSIC_DIFFERENCE | 7948 | 经典差值 |
| BlendingMode.COLOR | 7960 | 颜色 |
| BlendingMode.COLOR_BURN | 7968 | 颜色加深 |
| BlendingMode.COLOR_DODGE | 7969 | 颜色减淡 |
| BlendingMode.DANCING_DISSOLVE | 7943 | 随机溶解 |
| BlendingMode.DARKEN | 7944 | 变暗 |
| BlendingMode.DARKER_COLOR | 7970 | 更暗颜色 |
| BlendingMode.DIFFERENCE | 7949 | 差值 |
| BlendingMode.DISSOLVE | 7942 | 溶解 |
| BlendingMode.EXCLUSION | 7950 | 排除 |
| BlendingMode.HARD_LIGHT | 7955 | 强光 |
| BlendingMode.HARD_MIX | 7971 | 强制混合 |
| BlendingMode.HUE | 7958 | 色相 |
| BlendingMode.LIGHTEN | 7945 | 变亮 |
| BlendingMode.LIGHTER_COLOR | 7972 | 更亮颜色 |
| BlendingMode.LINEAR_BURN | 7973 | 线性加深 |
| BlendingMode.LINEAR_DODGE | 7974 | 线性减淡 |
| BlendingMode.LINEAR_LIGHT | 7956 | 线性光 |
| BlendingMode.LUMINESCENT_PREMUL | 7975 | 发光预乘 |
| BlendingMode.LUMINOSITY | 7961 | 亮度 |
| BlendingMode.MULTIPLY | 7951 | 正片叠底 |
| BlendingMode.NORMAL | 7941 | 正常 |
| BlendingMode.OVERLAY | 7954 | 叠加 |
| BlendingMode.PIN_LIGHT | 7957 | 点光 |
| BlendingMode.SATURATION | 7959 | 饱和度 |
| BlendingMode.SCREEN | 7940 | 屏幕 |
| BlendingMode.SILHOUETTE_ALPHA | 7962 | 轮廓Alpha |
| BlendingMode.SILHOUETTE_LUMA | 7963 | 轮廓亮度 |
| BlendingMode.SOFT_LIGHT | 7966 | 柔光 |
| BlendingMode.STENCIL_ALPHA | 7964 | 模板Alpha |
| BlendingMode.STENCIL_LUMA | 7965 | 模板亮度 |
| BlendingMode.SUBTRACT | 7967 | 减去 |
| BlendingMode.VIVID_LIGHT | 7976 | 鲜明光 |

#### 3D开关

```javascript
layer.threeDLayer = true;
layer.is3D; // 读取3D状态
```

#### 父子关系

```javascript
var childLayer = comp.layer(1);
var parentLayer = comp.layer(2);
childLayer.parent = parentLayer;

// 解除父子关系
childLayer.parent = null;
```

#### 轨道遮罩类型（全部枚举值）

```javascript
layer.trackMatteType = TrackMatteType.ALPHA;
```

| 枚举值 | 说明 |
|--------|------|
| TrackMatteType.ALPHA | Alpha遮罩 |
| TrackMatteType.ALPHA_INVERTED | Alpha反转遮罩 |
| TrackMatteType.LUMA | 亮度遮罩 |
| TrackMatteType.LUMA_INVERTED | 亮度反转遮罩 |
| TrackMatteType.NO_TRACK_MATTE | 无轨道遮罩 |
| TrackMatteType.SILHOUETTE_ALPHA | Alpha轮廓 |
| TrackMatteType.SILHOUETTE_LUMA | 亮度轮廓 |
| TrackMatteType.SILHOUETTE_ALPHA_INVERTED | Alpha反转轮廓 |
| TrackMatteType.SILHOUETTE_LUMA_INVERTED | 亮度反转轮廓 |

---

## 第四章 效果添加与参数设置的原子级脚本

> 本章是本手册最关键的章节。每个效果均给出 matchName（脚本执行的唯一可靠标识）和完整的属性原子映射。

### ADBE Gaussian Blur 2

- matchName: `"ADBE Gaussian Blur 2"`
- 显示名: Gaussian Blur
- 应用: `layer.Effects.addProperty("ADBE Gaussian Blur 2")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Blurriness | "Blurriness" | float | 0 | 0-1024 | `effect.property("Blurriness").setValue(25)` |
| Blur Dimensions | "Blur Dimensions" | int | 1 | 1=Both, 2=Horizontal, 3=Vertical | `effect.property("Blur Dimensions").setValue(1)` |
| Repeat Edge Pixels | "Repeat Edge Pixels" | boolean | false | true/false | `effect.property("Repeat Edge Pixels").setValue(true)` |

### ADBE Directional Blur

- matchName: `"ADBE Directional Blur"`
- 显示名: Directional Blur
- 应用: `layer.Effects.addProperty("ADBE Directional Blur")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Direction | "Direction" | float | 0 | 0-360度 | `effect.property("Direction").setValue(90)` |
| Blur Length | "Blur Length" | float | 0 | 0-500 | `effect.property("Blur Length").setValue(30)` |

### ADBE Radial Blur 2

- matchName: `"ADBE Radial Blur 2"`
- 显示名: Radial Blur
- 应用: `layer.Effects.addProperty("ADBE Radial Blur 2")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Amount | "Amount" | float | 0 | 0-100 | `effect.property("Amount").setValue(20)` |
| Type | "Type" | int | 1 | 1=Spin, 2=Zoom | `effect.property("Type").setValue(2)` |
| Center | "Center" | [x,y] | 合成中心 | 像素坐标 | `effect.property("Center").setValue([960, 540])` |
| Antialiasing | "Antialiasing" | int | 1 | 1=Low, 2=High | `effect.property("Antialiasing").setValue(2)` |

### ADBE Camera Lens Blur

- matchName: `"ADBE Camera Lens Blur"`
- 显示名: Camera Lens Blur
- 应用: `layer.Effects.addProperty("ADBE Camera Lens Blur")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Blur Radius | "Blur Radius" | float | 0 | 0-1024 | `effect.property("Blur Radius").setValue(15)` |
| Iris Shape | "Iris Shape" | int | 1 | 1=Triangle/2=Square/3=Pentagon/4=Hexagon/5=Heptagon/6=Octagon/7=Nonagon/8=Decagon | `effect.property("Iris Shape").setValue(4)` |
| Iris Rotation | "Iris Rotation" | float | 0 | 0-360度 | `effect.property("Iris Rotation").setValue(45)` |
| Iris Roundness | "Iris Roundness" | float | 0 | 0-100 | `effect.property("Iris Roundness").setValue(50)` |
| Iris Aspect Ratio | "Iris Aspect Ratio" | float | 1 | 0.1-10 | `effect.property("Iris Aspect Ratio").setValue(1)` |
| Specular Brightness | "Specular Brightness" | float | 0 | 0-100 | `effect.property("Specular Brightness").setValue(10)` |
| Specular Threshold | "Specular Threshold" | float | 50 | 0-255 | `effect.property("Specular Threshold").setValue(200)` |
| Repeat Edge Pixels | "Repeat Edge Pixels" | boolean | false | true/false | `effect.property("Repeat Edge Pixels").setValue(true)` |

### ADBE Glow

- matchName: `"ADBE Glow"`
- 显示名: Glow
- 应用: `layer.Effects.addProperty("ADBE Glow")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Glow Threshold | "Glow Threshold" | float | 50 | 0-255 | `effect.property("Glow Threshold").setValue(100)` |
| Glow Radius | "Glow Radius" | float | 10 | 0-500 | `effect.property("Glow Radius").setValue(50)` |
| Glow Intensity | "Glow Intensity" | float | 0.5 | 0-500 | `effect.property("Glow Intensity").setValue(1.5)` |
| Glow Colors | "Glow Colors" | int | 1 | 1=Original, 2=A & B Colors, 3=Arbitrary Map | `effect.property("Glow Colors").setValue(1)` |
| Color A | "Color A" | [R,G,B] | [1,0,0] | 0-1 | `effect.property("Color A").setValue([1,0.5,0])` |
| Color B | "Color B" | [R,G,B] | [0,0,1] | 0-1 | `effect.property("Color B").setValue([0,0.5,1])` |
| Glow Operation | "Glow Operation" | int | 3 | 与混合模式枚举对应 | `effect.property("Glow Operation").setValue(3)` |

### ADBE Color Balance (HLS)

- matchName: `"ADBE Color Balance (HLS)"`
- 显示名: Color Balance (HLS)
- 应用: `layer.Effects.addProperty("ADBE Color Balance (HLS)")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Hue | "Hue" | float | 0 | -180~180度 | `effect.property("Hue").setValue(30)` |
| Lightness | "Lightness" | float | 0 | -100~100 | `effect.property("Lightness").setValue(20)` |
| Saturation | "Saturation" | float | 0 | -100~100 | `effect.property("Saturation").setValue(50)` |

### ADBE Brightness & Contrast 2

- matchName: `"ADBE Brightness & Contrast 2"`
- 显示名: Brightness & Contrast
- 应用: `layer.Effects.addProperty("ADBE Brightness & Contrast 2")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Brightness | "Brightness" | float | 0 | -100~100 | `effect.property("Brightness").setValue(30)` |
| Contrast | "Contrast" | float | 0 | -100~100 | `effect.property("Contrast").setValue(50)` |
| Use Legacy | "Use Legacy" | boolean | false | true/false | `effect.property("Use Legacy").setValue(false)` |

### ADBE CurvesCustom

- matchName: `"ADBE CurvesCustom"`
- 显示名: Curves
- 应用: `layer.Effects.addProperty("ADBE CurvesCustom")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 说明 | 示例 |
|--------|-----------|------|--------|------|------|
| Channel | "Channel" | int | 1 | 1=RGB/2=Red/3=Green/4=Blue/5=Alpha | `effect.property("Channel").setValue(1)` |

**曲线点操作**（需要通过复合属性访问）:

```javascript
var curves = layer.Effects.addProperty("ADBE CurvesCustom");
// 曲线操作通过底层的PropertyGroup进行
// 读取曲线：通过value属性获取曲线数据
// 曲线控制点通过特殊API设置
// 推荐方法：使用预设曲线模板或表达式替代
```

> 注意：Curves效果的曲线点操作在ExtendScript中较复杂，推荐使用 Levels 或表达式实现类似效果。如需精确曲线控制，可通过 `effect.property(1).value` 读取现有曲线数据。

### ADBE Hue Saturation

- matchName: `"ADBE Hue Saturation"`
- 显示名: Hue/Saturation
- 应用: `layer.Effects.addProperty("ADBE Hue Saturation")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Channel Control | "Channel Control" | int | 1 | 1=Master/2=Reds/3=Yellows/4=Greens/5=Cyans/6=Blues/7=Magentas | `effect.property("Channel Control").setValue(1)` |
| Channel Range | "Channel Range" | [4个值] | 依赖通道 | 0-360 | `effect.property("Channel Range").setValue([0,30,60,90])` |
| Master Hue | "Master Hue" | float | 0 | 0-360度 | `effect.property("Master Hue").setValue(45)` |
| Master Saturation | "Master Saturation" | float | 0 | -100~100 | `effect.property("Master Saturation").setValue(50)` |
| Master Lightness | "Master Lightness" | float | 0 | -100~100 | `effect.property("Master Lightness").setValue(10)` |
| Colorize | "Colorize" | boolean | false | true/false | `effect.property("Colorize").setValue(true)` |
| Colorize Hue | "Colorize Hue" | float | 0 | 0-360度 | `effect.property("Colorize Hue").setValue(120)` |
| Colorize Saturation | "Colorize Saturation" | float | 25 | 0-100 | `effect.property("Colorize Saturation").setValue(70)` |
| Colorize Lightness | "Colorize Lightness" | float | 0 | -100~100 | `effect.property("Colorize Lightness").setValue(0)` |

### ADBE Tritone

- matchName: `"ADBE Tritone"`
- 显示名: Tritone
- 应用: `layer.Effects.addProperty("ADBE Tritone")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Highlights | "Highlights" | [R,G,B] | [1,1,1] | 0-1 | `effect.property("Highlights").setValue([1,0.9,0.7])` |
| Midtones | "Midtones" | [R,G,B] | [0.5,0.5,0.5] | 0-1 | `effect.property("Midtones").setValue([0.8,0.2,0.3])` |
| Shadows | "Shadows" | [R,G,B] | [0,0,0] | 0-1 | `effect.property("Shadows").setValue([0,0.05,0.15])` |
| Blend w/Original | "Blend w/Original" | float | 0 | 0-100 | `effect.property("Blend w/Original").setValue(20)` |

### ADBE Vignette

- matchName: `"ADBE Vignette"`
- 显示名: Vignette
- 应用: `layer.Effects.addProperty("ADBE Vignette")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Amount | "Amount" | float | 0 | -100~100 | `effect.property("Amount").setValue(-50)` |
| Softness | "Softness" | float | 50 | 0-500 | `effect.property("Softness").setValue(100)` |

### ADBE Turbulent Displace

- matchName: `"ADBE Turbulent Displace"`
- 显示名: Turbulent Displace
- 应用: `layer.Effects.addProperty("ADBE Turbulent Displace")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Displacement | "Displacement" | float | 50 | 0-500 | `effect.property("Displacement").setValue(30)` |
| Size | "Size" | float | 100 | 1-10000 | `effect.property("Size").setValue(150)` |
| Complexity | "Complexity" | int | 1 | 1-10 | `effect.property("Complexity").setValue(4)` |
| Evolution | "Evolution" | float | 0 | 0-1080度 | `effect.property("Evolution").setValue(180)` |
| Displacement | "Displacement" | int | 1 | 置换类型 | `effect.property("Displacement").setValue(1)` |
| Offset (Turbulence) | "Offset (Turbulence)" | [x,y] | [0,0] | 像素 | `effect.property("Offset (Turbulence)").setValue([100,50])` |
| Pinning | "Pinning" | int | 0 | 0=None/1=All/2=Horiz/3=Vert | `effect.property("Pinning").setValue(1)` |
| Resize | "Resize" | int | 0 | 0=Off/1=Fit/2=Force | `effect.property("Resize").setValue(0)` |

### ADBE Wave Warp

- matchName: `"ADBE Wave Warp"`
- 显示名: Wave Warp
- 应用: `layer.Effects.addProperty("ADBE Wave Warp")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Wave Type | "Wave Type" | int | 1 | 1=Sine/2=Square/3=Triangle/4=Sawtooth/5=Circle/6=Semicircle/7=Noise/8=Smooth Noise | `effect.property("Wave Type").setValue(1)` |
| Wave Height | "Wave Height" | float | 10 | 0-500 | `effect.property("Wave Height").setValue(20)` |
| Wave Width | "Wave Width" | float | 100 | 1-10000 | `effect.property("Wave Width").setValue(200)` |
| Direction | "Direction" | float | 90 | 0-360度 | `effect.property("Direction").setValue(0)` |
| Phase | "Phase" | float | 0 | 0-360度 | `effect.property("Phase").setValue(45)` |
| Pinning | "Pinning" | int | 1 | 0=None/1=All/2=Horiz/3=Vert | `effect.property("Pinning").setValue(1)` |
| Antialiasing | "Antialiasing" | int | 0 | 0=None/1=Low/2=High | `effect.property("Antialiasing").setValue(2)` |

### ADBE Fill

- matchName: `"ADBE Fill"`
- 显示名: Fill
- 应用: `layer.Effects.addProperty("ADBE Fill")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Color | "Color" | [R,G,B] | [1,0,0] | 0-1 | `effect.property("Color").setValue([0.2,0.5,0.8])` |

### ADBE Gradient Ramp

- matchName: `"ADBE Gradient Ramp"`
- 显示名: Gradient Ramp
- 应用: `layer.Effects.addProperty("ADBE Gradient Ramp")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Start Point | "Start Point" | [x,y] | [0,0] | 像素坐标 | `effect.property("Start Point").setValue([960,0])` |
| Start Color | "Start Color" | [R,G,B] | [1,1,1] | 0-1 | `effect.property("Start Color").setValue([0,0,0])` |
| End Point | "End Point" | [x,y] | [0,0] | 像素坐标 | `effect.property("End Point").setValue([960,1080])` |
| End Color | "End Color" | [R,G,B] | [0,0,0] | 0-1 | `effect.property("End Color").setValue([0.1,0.1,0.3])` |
| Ramp Shape | "Ramp Shape" | int | 1 | 1=Linear, 2=Radial | `effect.property("Ramp Shape").setValue(1)` |
| Ramp Scatter | "Ramp Scatter" | float | 0 | 0-500 | `effect.property("Ramp Scatter").setValue(10)` |
| Blend With Original | "Blend With Original" | float | 0 | 0-100 | `effect.property("Blend With Original").setValue(0)` |

### ADBE Fractal Noise

- matchName: `"ADBE Fractal Noise"`
- 显示名: Fractal Noise
- 应用: `layer.Effects.addProperty("ADBE Fractal Noise")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Fractal Type | "Fractal Type" | int | 2 | 0=Basic/1=Soft/2=Max/3=Turbulent/4=Dynamic/5=Strings/6=Twisted | `effect.property("Fractal Type").setValue(2)` |
| Noise Type | "Noise Type" | int | 0 | 0=Soft/1=Linear/2=Spline/3=Block | `effect.property("Noise Type").setValue(0)` |
| Invert | "Invert" | boolean | false | true/false | `effect.property("Invert").setValue(false)` |
| Contrast | "Contrast" | float | 50 | -100~400 | `effect.property("Contrast").setValue(100)` |
| Brightness | "Brightness" | float | 0 | -100~100 | `effect.property("Brightness").setValue(10)` |
| Overflow | "Overflow" | int | 0 | 0=Clip/1=Wrap/2=Scale | `effect.property("Overflow").setValue(0)` |
| Transform | (PropertyGroup) | - | - | 包含多个子属性 | `effect.property("Transform").property("Scale").setValue(200)` |
| Scale | "Scale" (在Transform下) | float | 100 | 1-10000 | `effect.property("Transform").property("Scale").setValue(200)` |
| Complexity | "Complexity" | int | 4 | 1-10 | `effect.property("Complexity").setValue(6)` |
| Evolution | "Evolution" | float | 0 | 0-1080度 | `effect.property("Evolution").setValue(90)` |
| Opacity | "Opacity" | float | 100 | 0-100 | `effect.property("Opacity").setValue(80)` |
| Blending Mode | "Blending Mode" | int | 0 | 0=None/1=Multiply/2=Screen/3=Overlay | `effect.property("Blending Mode").setValue(2)` |

### ADBE Light Rays

- matchName: `"ADBE Light Rays"`
- 显示名: Light Rays (CC Light Rays)
- 应用: `layer.Effects.addProperty("ADBE Light Rays")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Center | "Center" | [x,y] | 合成中心 | 像素坐标 | `effect.property("Center").setValue([960,540])` |
| Intensity | "Intensity" | float | 50 | 0-200 | `effect.property("Intensity").setValue(80)` |
| Radius | "Radius" | float | 50 | 0-500 | `effect.property("Radius").setValue(100)` |
| Warp | "Warp" | float | 0 | 0-200 | `effect.property("Warp").setValue(20)` |
| Shape | "Shape" | int | 1 | 1=Circle/2=Square | `effect.property("Shape").setValue(1)` |
| Color | "Color" | [R,G,B] | [1,1,1] | 0-1 | `effect.property("Color").setValue([1,0.9,0.5])` |

### ADBE Block Load

- matchName: `"ADBE Block Load"`
- 显示名: CC Block Load
- 应用: `layer.Effects.addProperty("ADBE Block Load")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Completion | "Completion" | float | 0 | 0-100 | `effect.property("Completion").setValue(50)` |
| Scans | "Scans" | int | 256 | 2-4096 | `effect.property("Scans").setValue(128)` |
| Blocks | "Blocks" | int | 16 | 1-256 | `effect.property("Blocks").setValue(32)` |

### ADBE Roughen Edges

- matchName: `"ADBE Roughen Edges"`
- 显示名: Roughen Edges
- 应用: `layer.Effects.addProperty("ADBE Roughen Edges")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Edge Type | "Edge Type" | int | 1 | 1=Roughen/2=Torn/3=Erode/4=Erode Sharply/5=Spiky | `effect.property("Edge Type").setValue(1)` |
| Border | "Border" | float | 10 | 0-500 | `effect.property("Border").setValue(20)` |
| Edge Sharpness | "Edge Sharpness" | float | 1 | 0-10 | `effect.property("Edge Sharpness").setValue(3)` |
| Fractal Influence | "Fractal Influence" | float | 0.5 | 0-1 | `effect.property("Fractal Influence").setValue(0.7)` |
| Scale | "Scale" | float | 100 | 10-1000 | `effect.property("Scale").setValue(150)` |
| Stretch Width or Height | "Stretch Width or Height" | float | 1 | 0.1-10 | `effect.property("Stretch Width or Height").setValue(1)` |
| Offset (Phase) | "Offset (Phase)" | [x,y] | [0,0] | 像素 | `effect.property("Offset (Phase)").setValue([0,0])` |
| Evolution | "Evolution" | float | 0 | 0-1080度 | `effect.property("Evolution").setValue(45)` |
| Complexity | "Complexity" | int | 1 | 1-10 | `effect.property("Complexity").setValue(3)` |

### ADBE Linear Wipe

- matchName: `"ADBE Linear Wipe"`
- 显示名: Linear Wipe
- 应用: `layer.Effects.addProperty("ADBE Linear Wipe")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Transition Completion | "Transition Completion" | float | 0 | 0-100 | `effect.property("Transition Completion").setValue(50)` |
| Wipe Angle | "Wipe Angle" | float | 0 | 0-360度 | `effect.property("Wipe Angle").setValue(90)` |
| Feather | "Feather" | float | 0 | 0-500 | `effect.property("Feather").setValue(20)` |

### ADBE Radial Wipe

- matchName: `"ADBE Radial Wipe"`
- 显示名: Radial Wipe
- 应用: `layer.Effects.addProperty("ADBE Radial Wipe")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Transition Completion | "Transition Completion" | float | 0 | 0-100 | `effect.property("Transition Completion").setValue(50)` |
| Start Angle | "Start Angle" | float | 0 | 0-360度 | `effect.property("Start Angle").setValue(0)` |
| Wipe Center | "Wipe Center" | [x,y] | 合成中心 | 像素坐标 | `effect.property("Wipe Center").setValue([960,540])` |
| Feather | "Feather" | float | 0 | 0-500 | `effect.property("Feather").setValue(10)` |
| Wipe | "Wipe" | int | 1 | 1=Clockwise, 2=Counterclockwise, 3=Both | `effect.property("Wipe").setValue(1)` |

### ADBE Card Wipe

- matchName: `"ADBE Card Wipe"`
- 显示名: Card Wipe
- 应用: `layer.Effects.addProperty("ADBE Card Wipe")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Transition Completion | "Transition Completion" | float | 0 | 0-100 | `effect.property("Transition Completion").setValue(50)` |
| Back Layer | "Back Layer" | Layer | none | 图层引用 | `effect.property("Back Layer").setValue(comp.layer(2))` |
| Rows & Columns | "Rows & Columns" | int | 1 | 1=Independent, 2=Locked | `effect.property("Rows & Columns").setValue(1)` |
| Rows | "Rows" | int | 4 | 1-32 | `effect.property("Rows").setValue(4)` |
| Columns | "Columns" | int | 8 | 1-32 | `effect.property("Columns").setValue(8)` |
| Card Scale | "Card Scale" | float | 1 | 0.1-10 | `effect.property("Card Scale").setValue(1)` |
| Flip Axis | "Flip Axis" | int | 1 | 1=X, 2=Y | `effect.property("Flip Axis").setValue(1)` |
| Flip Direction | "Flip Direction" | int | 1 | 1=Positive, 2=Negative | `effect.property("Flip Direction").setValue(1)` |
| Flip Order | "Flip Order" | int | 1 | 1=Left-Right/2=Top-Bottom/3=Gradient | `effect.property("Flip Order").setValue(1)` |
| Camera Position | (PropertyGroup) | - | - | 摄像机参数组 | `effect.property("Camera Position").property("Z Position").setValue(2)` |
| Lighting | (PropertyGroup) | - | - | 灯光参数组 | `effect.property("Lighting").property("Light Intensity").setValue(1)` |

### ADBE Particle World

- matchName: `"ADBE Particle World"`
- 显示名: CC Particle World
- 应用: `layer.Effects.addProperty("ADBE Particle World")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Birth Rate | "Birth Rate" | float | 1 | 0-100 | `effect.property("Birth Rate").setValue(5)` |
| Longevity (sec) | "Longevity (sec)" | float | 2 | 0-30 | `effect.property("Longevity (sec)").setValue(3)` |
| Producer | (PropertyGroup) | - | - | 发射器参数组 | `effect.property("Producer").property("Radius X").setValue(0.5)` |
| Physics | (PropertyGroup) | - | - | 物理参数组 | `effect.property("Physics").property("Velocity").setValue(1)` |
| Particle | (PropertyGroup) | - | - | 粒子外观参数组 | `effect.property("Particle").property("Birth Size").setValue(0.1)` |

### ADBE Motion Tile

- matchName: `"ADBE Motion Tile"`
- 显示名: Motion Tile
- 应用: `layer.Effects.addProperty("ADBE Motion Tile")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Tile Center | "Tile Center" | [x,y] | 合成中心 | 像素坐标 | `effect.property("Tile Center").setValue([960,540])` |
| Tile Width | "Tile Width" | float | 100 | 1-10000 | `effect.property("Tile Width").setValue(200)` |
| Tile Height | "Tile Height" | float | 100 | 1-10000 | `effect.property("Tile Height").setValue(150)` |
| Output Width | "Output Width" | float | 100 | 1-10000 | `effect.property("Output Width").setValue(200)` |
| Output Height | "Output Height" | float | 100 | 1-10000 | `effect.property("Output Height").setValue(200)` |
| Mirror Edges | "Mirror Edges" | boolean | false | true/false | `effect.property("Mirror Edges").setValue(true)` |
| Phase | "Phase" | float | 0 | 0-360度 | `effect.property("Phase").setValue(0)` |

### ADBE Optics Compensation

- matchName: `"ADBE Optics Compensation"`
- 显示名: Optics Compensation
- 应用: `layer.Effects.addProperty("ADBE Optics Compensation")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Field of View (FOV) | "Field of View (FOV)" | float | 20 | 0-360 | `effect.property("Field of View (FOV)").setValue(60)` |
| Reverse Lens Distortion | "Reverse Lens Distortion" | boolean | false | true/false | `effect.property("Reverse Lens Distortion").setValue(false)` |
| FOV Orientation | "FOV Orientation" | int | 1 | 1=Horizontal, 2=Vertical, 3=Diagonal | `effect.property("FOV Orientation").setValue(1)` |
| View Center | "View Center" | [x,y] | [0.5,0.5] | 0-1(归一化) | `effect.property("View Center").setValue([0.5,0.5])` |
| Optimal Pixels | "Optimal Pixels" | boolean | false | true/false | `effect.property("Optimal Pixels").setValue(true)` |
| Resize | "Resize" | int | 0 | 0=Off/1=Fit | `effect.property("Resize").setValue(1)` |

### ADBE Corner Pin

- matchName: `"ADBE Corner Pin"`
- 显示名: Corner Pin
- 应用: `layer.Effects.addProperty("ADBE Corner Pin")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Upper Left | "Upper Left" | [x,y] | 图层左上角 | 像素坐标 | `effect.property("Upper Left").setValue([100,50])` |
| Upper Right | "Upper Right" | [x,y] | 图层右上角 | 像素坐标 | `effect.property("Upper Right").setValue([1820,50])` |
| Lower Left | "Lower Left" | [x,y] | 图层左下角 | 像素坐标 | `effect.property("Lower Left").setValue([100,1030])` |
| Lower Right | "Lower Right" | [x,y] | 图层右下角 | 像素坐标 | `effect.property("Lower Right").setValue([1820,1030])` |

### ADBE Mesh Warp

- matchName: `"ADBE Mesh Warp"`
- 显示名: Mesh Warp
- 应用: `layer.Effects.addProperty("ADBE Mesh Warp")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Rows | "Rows" | int | 4 | 1-32 | `effect.property("Rows").setValue(8)` |
| Columns | "Columns" | int | 4 | 1-32 | `effect.property("Columns").setValue(8)` |
| Quality | "Quality" | float | 1 | 0-10 | `effect.property("Quality").setValue(1)` |

> 注：Mesh Warp的具体网格点操作需要通过交互式界面完成，脚本控制能力有限。

### ADBE Lens Flare

- matchName: `"ADBE Lens Flare"`
- 显示名: Lens Flare
- 应用: `layer.Effects.addProperty("ADBE Lens Flare")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Flare Center | "Flare Center" | [x,y] | 合成中心 | 像素坐标 | `effect.property("Flare Center").setValue([960,540])` |
| Flare Brightness | "Flare Brightness" | float | 100 | 0-300 | `effect.property("Flare Brightness").setValue(150)` |
| Flare Type | "Flare Type" | int | 1 | 1=50-300mm/2=105mm/3=35mm Prime | `effect.property("Flare Type").setValue(1)` |
| Lens Type | "Lens Type" | int | 1 | 同Flare Type | `effect.property("Lens Type").setValue(2)` |
| Blend With Original | "Blend With Original" | float | 0 | 0-100 | `effect.property("Blend With Original").setValue(0)` |

### ADBE Channel Blur

- matchName: `"ADBE Channel Blur"`
- 显示名: Channel Blur
- 应用: `layer.Effects.addProperty("ADBE Channel Blur")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Red Blurriness | "Red Blurriness" | float | 0 | 0-1024 | `effect.property("Red Blurriness").setValue(10)` |
| Green Blurriness | "Green Blurriness" | float | 0 | 0-1024 | `effect.property("Green Blurriness").setValue(0)` |
| Blue Blurriness | "Blue Blurriness" | float | 0 | 0-1024 | `effect.property("Blue Blurriness").setValue(20)` |
| Alpha Blurriness | "Alpha Blurriness" | float | 0 | 0-1024 | `effect.property("Alpha Blurriness").setValue(0)` |
| Repeat Edge Pixels | "Repeat Edge Pixels" | boolean | false | true/false | `effect.property("Repeat Edge Pixels").setValue(true)` |

### ADBE Set Channels

- matchName: `"ADBE Set Channels"`
- 显示名: Set Channels
- 应用: `layer.Effects.addProperty("ADBE Set Channels")`
- 属性原子映射:

| 属性名 | matchName | 类型 | 默认值 | 范围 | 示例 |
|--------|-----------|------|--------|------|------|
| Source Layer 1 | "Source Layer 1" | Layer | none | 图层引用 | `effect.property("Source Layer 1").setValue(comp.layer(2))` |
| Source Layer 2 | "Source Layer 2" | Layer | none | 图层引用 | `effect.property("Source Layer 2").setValue(comp.layer(2))` |
| Source Layer 3 | "Source Layer 3" | Layer | none | 图层引用 | `effect.property("Source Layer 3").setValue(comp.layer(2))` |
| Source Layer 4 | "Source Layer 4" | Layer | none | 图层引用 | `effect.property("Source Layer 4").setValue(comp.layer(2))` |
| Source X | "Source X" | int | 0 | 0=Left, 1=Center, 2=Right | `effect.property("Source X").setValue(1)` |
| Source Y | "Source Y" | int | 0 | 0=Top, 1=Center, 2=Bottom | `effect.property("Source Y").setValue(1)` |
| Source Channel 1 | "Source Channel 1" | int | 1 | 1=R/2=G/3=B/4=A/5=L/6=H/7=Sat/8=Val | `effect.property("Source Channel 1").setValue(1)` |
| Source Channel 2 | "Source Channel 2" | int | 2 | 同上 | `effect.property("Source Channel 2").setValue(2)` |
| Source Channel 3 | "Source Channel 3" | int | 3 | 同上 | `effect.property("Source Channel 3").setValue(3)` |
| Source Channel 4 | "Source Channel 4" | int | 4 | 同上 | `effect.property("Source Channel 4").setValue(4)` |
| Stretch Source to Fit | "Stretch Source to Fit" | boolean | false | true/false | `effect.property("Stretch Source to Fit").setValue(true)` |

---

## 第五章 关键帧与缓动的原子级脚本

### 5.1 添加关键帧

**ExtendScript函数签名**:
```javascript
// 方法1：直接在指定时间设置值（自动创建关键帧）
property.setValueAtTime(value, time);

// 方法2：先添加关键帧，再设置值
var keyIndex = property.addKey(time);
property.setValueAtKey(keyIndex, value);
```

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var pos = layer.property("ADBE Transform Group").property("ADBE Position");

// 方法1：setValueAtTime
pos.setValueAtTime([960, 540], 0);    // 0秒位置
pos.setValueAtTime([1920, 540], 1);   // 1秒位置
pos.setValueAtTime([960, 540], 2);    // 2秒位置

// 方法2：addKey + setValueAtKey
var key1 = pos.addKey(0);
pos.setValueAtKey(key1, [960, 540]);
var key2 = pos.addKey(1);
pos.setValueAtKey(key2, [1920, 540]);
```

### 5.2 设置缓动类型

**ExtendScript函数签名**:
```javascript
property.setInterpolationTypeAtKey(keyIndex, inType, outType)
```

**KeyframeInterpolationType枚举值**:

| 枚举值 | 数值 | 说明 |
|--------|------|------|
| KeyframeInterpolationType.LINEAR | 1 | 线性 |
| KeyframeInterpolationType.BEZIER | 2 | 贝塞尔 |
| KeyframeInterpolationType.HOLD | 3 | 保持（定格） |
| KeyframeInterpolationType.EASE_IN | 4 | 缓入 |
| KeyframeInterpolationType.EASE_OUT | 5 | 缓出 |
| KeyframeInterpolationType.EASE_IN_OUT | 6 | 缓入缓出 |

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var pos = layer.property("ADBE Transform Group").property("ADBE Position");

// 添加关键帧
pos.setValueAtTime([960, 540], 0);
pos.setValueAtTime([1920, 540], 1);
pos.setValueAtTime([960, 540], 2);

// 设置第二个关键帧为贝塞尔缓动
pos.setInterpolationTypeAtKey(2, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);

// 设置第三个关键帧为缓入
pos.setInterpolationTypeAtKey(3, KeyframeInterpolationType.EASE_IN, KeyframeInterpolationType.LINEAR);

// 设置线性关键帧
pos.setInterpolationTypeAtKey(1, KeyframeInterpolationType.LINEAR, KeyframeInterpolationType.LINEAR);
```

### 5.3 设置缓动手柄

**ExtendScript函数签名**:
```javascript
var ease = new KeyframeEase(speed, influence);
property.setTemporalEaseAtKey(keyIndex, inEaseArray, outEaseArray);
```

**KeyframeEase构造函数参数**:
- `speed`: 影响关键帧处的速度。通常设为0
- `influence`: 影响范围百分比（0-100）。越大缓动越明显

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var pos = layer.property("ADBE Transform Group").property("ADBE Position");

// 添加关键帧
pos.setValueAtTime([960, 540], 0);
pos.setValueAtTime([1920, 540], 1);
pos.setValueAtTime([960, 540], 2);

// 设置贝塞尔缓动（需要先设置插值类型）
pos.setInterpolationTypeAtKey(2, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);

// 设置缓动手柄（2D属性需要2个ease值，3D属性需要3个）
var easeIn = new KeyframeEase(0, 66);   // influence=66 = 强缓入
var easeOut = new KeyframeEase(0, 66);  // influence=66 = 强缓出

// Position是2D属性，每个方向需要一个ease值
pos.setTemporalEaseAtKey(2, [easeIn, easeIn], [easeOut, easeOut]);

// 3D位置的缓动设置（需要3个ease值）
// pos.setTemporalEaseAtKey(2, [easeIn, easeIn, easeIn], [easeOut, easeOut, easeOut]);
```

### 5.4 设置空间缓动

**ExtendScript函数签名**:
```javascript
property.setSpatialTangentsAtKey(keyIndex, inTangent, outTangent)
```

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var pos = layer.property("ADBE Transform Group").property("ADBE Position");

pos.setValueAtTime([960, 540], 0);
pos.setValueAtTime([1920, 200], 1);
pos.setValueAtTime([960, 540], 2);

// 设置空间切线（控制运动路径的弯曲方向）
pos.setSpatialTangentsAtKey(2, [-100, 50], [100, -50]);

// 3D图层的空间切线需要3维
// pos.setSpatialTangentsAtKey(2, [-100, 50, 0], [100, -50, 0]);

// 设置为自动贝塞尔（自动计算切线）
pos.setSpatialAutoBezierAtKey(2);
```

### 5.5 关键帧批处理模板

```javascript
// 通用关键帧批处理函数
function setKeyframes(prop, keyframes, easing) {
    // keyframes: [{time: 0, value: [960,540]}, {time: 1, value: [1920,540]}, ...]
    // easing: {type: "bezier", influence: 33} 或 {type: "linear"} 或 {type: "hold"}

    app.beginUndoGroup("Set Keyframes");

    for (var i = 0; i < keyframes.length; i++) {
        var kf = keyframes[i];
        prop.setValueAtTime(kf.value, kf.time);
    }

    // 设置缓动
    if (easing && easing.type !== "linear") {
        for (var j = 1; j <= prop.numKeys; j++) {
            if (easing.type === "bezier") {
                prop.setInterpolationTypeAtKey(j,
                    KeyframeInterpolationType.BEZIER,
                    KeyframeInterpolationType.BEZIER
                );
                var influence = easing.influence || 33;
                var easeIn = new KeyframeEase(0, influence);
                var easeOut = new KeyframeEase(0, influence);
                var dim = prop.value.length || 1;
                var inArr = [];
                var outArr = [];
                for (var d = 0; d < dim; d++) {
                    inArr.push(easeIn);
                    outArr.push(easeOut);
                }
                prop.setTemporalEaseAtKey(j, inArr, outArr);
            } else if (easing.type === "hold") {
                prop.setInterpolationTypeAtKey(j,
                    KeyframeInterpolationType.HOLD,
                    KeyframeInterpolationType.HOLD
                );
            }
        }
    }

    app.endUndoGroup();
}

// 使用示例
var comp = app.project.activeItem;
var layer = comp.layer(1);
var pos = layer.property("ADBE Transform Group").property("ADBE Position");

setKeyframes(pos, [
    {time: 0, value: [960, 540]},
    {time: 1, value: [1920, 540]},
    {time: 2, value: [960, 540]},
    {time: 3, value: [960, 200]}
], {type: "bezier", influence: 33});
```

### 5.6 常用缓动曲线的KeyframeEase参数值表

| 缓动名称 | inEase.speed | inEase.influence | outEase.speed | outEase.influence | 说明 |
|---------|-------------|-----------------|--------------|------------------|------|
| Linear | 0 | 0 | 0 | 0 | 无缓动，匀速 |
| Easy Ease | 0 | 33 | 0 | 33 | 标准缓入缓出 |
| Easy Ease Out | 0 | 0 | 0 | 33 | 仅缓出 |
| Easy Ease In | 0 | 33 | 0 | 0 | 仅缓入 |
| Strong Ease | 0 | 66 | 0 | 66 | 强缓动 |
| Very Strong Ease | 0 | 85 | 0 | 85 | 极强缓动 |
| Bounce | 0 | 90 | 0 | 90 | 接近弹跳效果 |
| Snappy | 0 | 80 | 0 | 20 | 快出慢停 |
| Smooth Start | 0 | 50 | 0 | 0 | 仅前半缓入 |
| Smooth Stop | 0 | 0 | 0 | 50 | 仅后半缓出 |
| Soft Landing | 0 | 20 | 0 | 70 | 轻起步重刹车 |
| Quick Start | 0 | 70 | 0 | 20 | 急起步轻刹车 |
| Elastic | 0 | 90 | 0 | 5 | 弹性效果（需配合多个关键帧） |
| Overshoot | 0 | 95 | 0 | 10 | 超调效果（需配合关键帧布局） |

### 5.7 MCP关键帧调用示例

```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var layer = comp.layer(1); var pos = layer.property('ADBE Transform Group').property('ADBE Position'); pos.setValueAtTime([960,540], 0); pos.setValueAtTime([1920,540], 1); pos.setValueAtTime([960,540], 2); pos.setInterpolationTypeAtKey(2, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER); var ei = new KeyframeEase(0, 33); var eo = new KeyframeEase(0, 33); pos.setTemporalEaseAtKey(2, [ei, ei], [eo, eo]); JSON.stringify({numKeys: pos.numKeys})"
    }
}
```

---

## 第六章 表达式注入的原子级脚本

### 6.1 设置与移除表达式

```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var pos = layer.property("ADBE Transform Group").property("ADBE Position");

// 设置表达式
pos.expression = "wiggle(5, 20)";

// 启用/禁用表达式
pos.expressionEnabled = true;
pos.expressionEnabled = false;

// 移除表达式
pos.expression = "";

// 检查是否支持表达式
if (pos.canSetExpression) {
    pos.expression = "value + [100, 0]";
}
```

### 6.2 常用表达式模板库

#### wiggle(freq, amp)

```javascript
// 基础抖动
"wiggle(5, 20)"

// 带时间偏移的抖动
"wiggle(5, 20, octaves = 1, amp_mult = 0.5, t = time + 1)"

// 单轴抖动（X轴）
"var w = wiggle(5, 20); [w[0], value[1]]"

// 单轴抖动（Y轴）
"var w = wiggle(5, 20); [value[0], w[1]]"

// 随时间衰减的抖动
"var decay = 3; wiggle(5, 20 * Math.exp(-decay * time))"
```

**参数Schema**:
```json
{
    "freq": {"type": "number", "default": 5, "description": "频率（每秒抖动次数）"},
    "amp": {"type": "number", "default": 20, "description": "振幅（像素/百分比）"},
    "octaves": {"type": "number", "default": 1, "description": "八度数（细节层次）"},
    "amp_mult": {"type": "number", "default": 0.5, "description": "振幅倍率"}
}
```

**注入JSON示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var layer = comp.layer(1); var pos = layer.property('ADBE Transform Group').property('ADBE Position'); pos.expression = 'wiggle(5, 20)'; JSON.stringify({expressionSet: true})"
    }
}
```

#### 弹性表达式（Inertial Bounce）

```javascript
// 弹性回弹效果
"var n = 0; if (numKeys > 0) { n = nearestKey(time).index; if (key(n).time > time) { n--; } } if (n == 0) { var t = 0; } else { var t = time - key(n).time; } if (n > 0 && t < 1) { var v = velocityAtTime(key(n).time - thisComp.frameDuration/10); var amp = 0.05; var freq = 4.0; var decay = 8.0; value + v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t); } else { value; }"
```

**参数Schema**:
```json
{
    "amp": {"type": "number", "default": 0.05, "description": "弹性振幅系数"},
    "freq": {"type": "number", "default": 4.0, "description": "弹性频率"},
    "decay": {"type": "number", "default": 8.0, "description": "衰减速度"}
}
```

#### 循环表达式（loopOut/loopIn）

```javascript
// 循环输出（循环关键帧动画）
"loopOut(type = 'cycle', numKeyframes = 0)"

// 乒乓循环
"loopOut(type = 'pingpong', numKeyframes = 0)"

// 偏移循环
"loopOut(type = 'offset', numKeyframes = 0)"

// 继续循环（线性延伸）
"loopOut(type = 'continue', numKeyframes = 0)"

// 循环输入
"loopIn(type = 'cycle', numKeyframes = 0)"

// 指定关键帧范围的循环
"loopOut(type = 'cycle', numKeyframes = 2)"
```

**参数Schema**:
```json
{
    "type": {"type": "string", "enum": ["cycle", "pingpong", "offset", "continue"], "default": "cycle"},
    "numKeyframes": {"type": "number", "default": 0, "description": "参与循环的关键帧数量，0=全部"},
    "direction": {"type": "string", "enum": ["out", "in"], "default": "out"}
}
```

#### 音频驱动

```javascript
// 基础音频驱动缩放
"var audioLayer = thisComp.layer('Audio Amplitude'); var slider = audioLayer.effect('Both Channels')('Slider'); var scale = linear(slider, 0, 30, 100, 200); [scale, scale]"

// 音频驱动不透明度
"var audioLayer = thisComp.layer('Audio Amplitude'); var slider = audioLayer.effect('Both Channels')('Slider'); linear(slider, 0, 30, 0, 100)"

// 音频驱动位置（微抖）
"var audioLayer = thisComp.layer('Audio Amplitude'); var amp = audioLayer.effect('Both Channels')('Slider'); var offset = amp * 0.5; value + [offset, -offset]"
```

**参数Schema**:
```json
{
    "audioLayerName": {"type": "string", "default": "Audio Amplitude", "description": "音频关键帧图层名"},
    "channel": {"type": "string", "enum": ["Both Channels", "Left Channel", "Right Channel"], "default": "Both Channels"},
    "minValue": {"type": "number", "default": 0},
    "maxValue": {"type": "number", "default": 30},
    "outputMin": {"type": "number", "default": 100},
    "outputMax": {"type": "number", "default": 200}
}
```

#### 随机运动（seedRandom + random）

```javascript
// 每帧随机位置
"seedRandom(Math.floor(time * 10), timeless = true); value + random([-50,-50], [50,50])"

// 每秒随机位置
"seedRandom(Math.floor(time), timeless = true); value + random([-100,-100], [100,100])"

// 随机旋转
"seedRandom(Math.floor(time * 5), timeless = true); value + random(-30, 30)"

// 随机不透明度闪烁
"seedRandom(Math.floor(time * 8), timeless = true); random(50, 100)"
```

#### 路径跟随（valueAtTime）

```javascript
// 跟随上一图层（延迟跟随）
"var delay = 0.2; thisComp.layer(index - 1).position.valueAtTime(time - delay)"

// 跟随指定图层
"var leader = thisComp.layer('Leader'); var delay = 0.3; leader.position.valueAtTime(time - delay)"

// 路径跟随（沿路径运动）
"var pathLayer = thisComp.layer('Path Layer'); var path = pathLayer.content('Shape 1').content('Path 1').path; var progress = linear(time, 0, 5, 0, 1); path.pointOnPath(progress)"
```

#### 文字逐字显示

```javascript
// 文字逐字显示表达式（应用于Source Text）
"var text = 'Hello World'; var charsPerSecond = 10; var numChars = Math.floor(time * charsPerSecond); text.substr(0, Math.min(numChars, text.length))"

// 带光标的逐字显示
"var text = 'Hello World'; var charsPerSecond = 8; var numChars = Math.floor(time * charsPerSecond); var cursor = (Math.floor(time * 2) % 2 === 0) ? '|' : ''; text.substr(0, Math.min(numChars, text.length)) + (numChars < text.length ? cursor : '')"

// 打字机效果（逐字显示带闪烁光标）
"var src = text.sourceText; var txt = src.toString(); var cps = 15; var n = Math.min(Math.floor(time * cps), txt.length); var out = txt.substring(0, n); if (n < txt.length) { out += (Math.floor(time * 3) % 2) ? '_' : ' '; } out"
```

**注入JSON示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var layer = comp.layers.addText('Typewriter Text'); var src = layer.property('ADBE Text Properties').property('ADBE Text Document'); src.expression = \"var text = 'Hello World'; var cps = 10; var n = Math.floor(time * cps); text.substr(0, Math.min(n, text.length))\"; JSON.stringify({expressionSet: true})"
    }
}
```

---

## 第七章 遮罩操作的原子级脚本

### 7.1 创建遮罩

**ExtendScript函数签名**:
```javascript
var mask = layer.Masks.addProperty("Mask Name");
```

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);

// 创建遮罩
var mask = layer.Masks.addProperty("My Mask");
```

### 7.2 设置遮罩路径

**原子级代码**:
```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var mask = layer.Masks.addProperty("Rectangle Mask");

// 矩形遮罩
var shape = new Shape();
shape.vertices = [
    [100, 100],    // 左上
    [1820, 100],   // 右上
    [1820, 980],   // 右下
    [100, 980]     // 左下
];
shape.inTangents = [[0,0], [0,0], [0,0], [0,0]];
shape.outTangents = [[0,0], [0,0], [0,0], [0,0]];
shape.closed = true;
mask.property("ADBE Mask Shape").setValue(shape);

// 椭圆遮罩（通过贝塞尔曲线近似）
var ellipseMask = layer.Masks.addProperty("Ellipse Mask");
var cx = 960, cy = 540, rx = 400, ry = 300;
var k = 0.5522847498; // 魔术常数，用于近似圆
var ellipse = new Shape();
ellipse.vertices = [
    [cx, cy - ry],       // 上
    [cx + rx, cy],       // 右
    [cx, cy + ry],       // 下
    [cx - rx, cy]        // 左
];
ellipse.inTangents = [
    [-rx * k, 0],
    [0, -ry * k],
    [rx * k, 0],
    [0, ry * k]
];
ellipse.outTangents = [
    [rx * k, 0],
    [0, ry * k],
    [-rx * k, 0],
    [0, -ry * k]
];
ellipse.closed = true;
ellipseMask.property("ADBE Mask Shape").setValue(ellipse);
```

### 7.3 设置遮罩羽化

```javascript
mask.property("ADBE Mask Feather").setValue([20, 20]);  // [水平羽化, 垂直羽化]
mask.property("ADBE Mask Feather").setValue([50, 10]);   // 水平大羽化，垂直小羽化
```

### 7.4 设置遮罩模式

**MaskMode枚举值**:

| 枚举值 | 数值 | 说明 |
|--------|------|------|
| MaskMode.NONE | 0 | 无 |
| MaskMode.ADD | 1 | 相加 |
| MaskMode.SUBTRACT | 2 | 相减 |
| MaskMode.INTERSECT | 3 | 相交 |
| MaskMode.LIGHTEN | 4 | 变亮 |
| MaskMode.DARKEN | 5 | 变暗 |
| MaskMode.DIFFERENCE | 6 | 差值 |

```javascript
mask.property("ADBE Mask Mode").setValue(MaskMode.ADD);
mask.property("ADBE Mask Mode").setValue(MaskMode.SUBTRACT);
mask.property("ADBE Mask Mode").setValue(MaskMode.INTERSECT);
mask.property("ADBE Mask Mode").setValue(MaskMode.DIFFERENCE);
```

### 7.5 设置遮罩扩展

```javascript
mask.property("ADBE Mask Expansion").setValue(10);   // 向外扩展10像素
mask.property("ADBE Mask Expansion").setValue(-20);  // 向内收缩20像素
```

### 7.6 设置遮罩不透明度

```javascript
mask.property("ADBE Mask Opacity").setValue(80);   // 80%不透明度
mask.property("ADBE Mask Opacity").setValue(50);   // 50%不透明度
```

### 7.7 遮罩动画关键帧

```javascript
var comp = app.project.activeItem;
var layer = comp.layer(1);
var mask = layer.Masks.addProperty("Animated Mask");

// 设置初始遮罩形状
var shape1 = new Shape();
shape1.vertices = [[100, 100], [1820, 100], [1820, 980], [100, 980]];
shape1.inTangents = [[0,0], [0,0], [0,0], [0,0]];
shape1.outTangents = [[0,0], [0,0], [0,0], [0,0]];
shape1.closed = true;

var shape2 = new Shape();
shape2.vertices = [[300, 300], [1620, 300], [1620, 780], [300, 780]];
shape2.inTangents = [[0,0], [0,0], [0,0], [0,0]];
shape2.outTangents = [[0,0], [0,0], [0,0], [0,0]];
shape2.closed = true;

var maskShape = mask.property("ADBE Mask Shape");
maskShape.setValueAtTime(shape1, 0);
maskShape.setValueAtTime(shape2, 1);

// 动画化羽化
mask.property("ADBE Mask Feather").setValueAtTime([0, 0], 0);
mask.property("ADBE Mask Feather").setValueAtTime([50, 50], 1);

// 动画化不透明度
mask.property("ADBE Mask Opacity").setValueAtTime(100, 0);
mask.property("ADBE Mask Opacity").setValueAtTime(50, 1);
```

### 7.8 MCP遮罩调用示例

```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var layer = comp.layer(1); var mask = layer.Masks.addProperty('My Mask'); var s = new Shape(); s.vertices = [[100,100],[1820,100],[1820,980],[100,980]]; s.inTangents = [[0,0],[0,0],[0,0],[0,0]]; s.outTangents = [[0,0],[0,0],[0,0],[0,0]]; s.closed = true; mask.property('ADBE Mask Shape').setValue(s); mask.property('ADBE Mask Feather').setValue([20,20]); mask.property('ADBE Mask Opacity').setValue(80); mask.property('ADBE Mask Mode').setValue(MaskMode.ADD); JSON.stringify({maskName: mask.name, numMasks: layer.Masks.numProperties})"
    }
}
```

---

## 第八章 第三方插件效果matchName查找表

> 本章是连接知识库插件参数文档和实际脚本执行的关键桥梁。第三方插件的matchName可能因版本不同而变化，务必提供运行时查找脚本。

### 8.1 常见第三方插件matchName表

| 插件名 | matchName | 厂商 | 说明 |
|--------|-----------|------|------|
| Trapcode Particular | `"ACP Particular"` | Red Giant | 3D粒子系统 |
| Trapcode Form | `"ACP Form"` | Red Giant | 3D粒子网格 |
| Trapcode Shine | `"ACP Shine"` | Red Giant | 光线效果 |
| Trapcode 3D Stroke | `"ACP 3D Stroke"` | Red Giant | 3D描边 |
| Trapcode Starglow | `"ACP Starglow"` | Red Giant | 星光效果 |
| Trapcode Sound Keys | `"ACP Sound Keys"` | Red Giant | 音频关键帧 |
| Trapcode Lux | `"ACP Lux"` | Red Giant | 可见灯光 |
| Trapcode Echospace | `"ACP Echospace"` | Red Giant | 空间回声 |
| Trapcode Tao | `"ACP Tao"` | Red Giant | 3D几何 |
| Trapcode Mir | `"ACP Mir"` | Red Giant | 3D多边形 |
| Sapphire S_Glow | `"Sapphire S_Glow"` | Boris FX | 蓝宝石辉光 |
| Sapphire S_Blur | `"Sapphire S_Blur"` | Boris FX | 蓝宝石模糊 |
| Sapphire S_Vignette | `"Sapphire S_Vignette"` | Boris FX | 蓝宝石暗角 |
| Sapphire S_RackDefocus | `"Sapphire S_RackDefocus"` | Boris FX | 蓝宝石散焦 |
| Sapphire S_LensFlare | `"Sapphire S_LensFlare"` | Boris FX | 蓝宝石镜头光晕 |
| Sapphire S_Shake | `"Sapphire S_Shake"` | Boris FX | 蓝宝石抖动 |
| Sapphire S_Distort | `"Sapphire S_Distort"` | Boris FX | 蓝宝石扭曲 |
| BCC Glow | `"BCC Glow"` | Boris FX | BCC辉光 |
| BCC Gaussian Blur | `"BCC Gaussian Blur"` | Boris FX | BCC高斯模糊 |
| BCC Color Palette | `"BCC Color Palette"` | Boris FX | BCC调色板 |
| BCC Light Leaks | `"BCC Light Leaks"` | Boris FX | BCC漏光 |
| BCC Film Glow | `"BCC Film Glow"` | Boris FX | BCC胶片辉光 |
| BCC Organic Strands | `"BCC Organic Strands"` | Boris FX | BCC有机丝线 |
| Video Copilot Element 3D | `"VC Element"` | Video Copilot | 3D元素 |
| Video Copilot Optical Flares | `"VC Optical Flares"` | Video Copilot | 镜头光晕 |
| Video Copilot Saber | `"VC Saber"` | Video Copilot | 光效描边 |
| Deep Glow | `"Deep Glow"` | Plugin Everything | 深度辉光 |
| Universe Chromatic Aberration | `"UNV Chromatic Aberration"` | Maxon/Red Giant | 色差效果 |
| Universe Glow | `"UNV Glow"` | Maxon/Red Giant | 宇宙辉光 |
| Universe VHS | `"UNV VHS"` | Maxon/Red Giant | VHS复古效果 |
| Universe Motif | `"UNV Motif"` | Maxon/Red Giant | 图案生成 |
| Stardust | `"Stardust"` | Superluminal | 3D粒子系统 |
| ft-UV | `"ft-UV"` | Motion Boutique | UV映射 |
| Duik Angela | `"Duik"` | Rainbox | 角色绑定 |

### 8.2 运行时matchName查找脚本

```javascript
// 查找已安装插件的所有效果matchName
function listAllEffectMatchNames() {
    var result = [];
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        return JSON.stringify({error: "No active composition"});
    }

    // 创建临时图层来查找效果
    var tempLayer = comp.layers.addSolid([0,0,0], "temp", 100, 100, 1, 1);

    // 遍历所有已注册的效果
    var effects = tempLayer.Effects;
    // 注意：ExtendScript没有直接枚举所有效果的方法
    // 需要通过app.effects来获取

    tempLayer.remove();

    return JSON.stringify(result);
}

// 查找特定效果的matchName（通过应用测试）
function findEffectMatchName(effectName) {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        return JSON.stringify({error: "No active composition"});
    }

    var tempLayer = comp.layers.addSolid([0,0,0], "temp", 100, 100, 1, 1);

    try {
        var effect = tempLayer.Effects.addProperty(effectName);
        var matchName = effect.matchName;
        var props = [];

        for (var i = 1; i <= effect.numProperties; i++) {
            var prop = effect.property(i);
            props.push({
                index: i,
                name: prop.name,
                matchName: prop.matchName,
                propertyValueType: prop.propertyValueType.toString()
            });
        }

        effect.remove();
        tempLayer.remove();

        return JSON.stringify({
            effectName: effectName,
            matchName: matchName,
            properties: props
        });
    } catch (e) {
        tempLayer.remove();
        return JSON.stringify({
            effectName: effectName,
            error: e.toString()
        });
    }
}

// 批量查找效果matchName
function findMultipleMatchNames(effectNames) {
    var results = [];
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        return JSON.stringify({error: "No active composition"});
    }

    var tempLayer = comp.layers.addSolid([0,0,0], "temp", 100, 100, 1, 1);

    for (var i = 0; i < effectNames.length; i++) {
        try {
            var effect = tempLayer.Effects.addProperty(effectNames[i]);
            results.push({
                searchName: effectNames[i],
                matchName: effect.matchName,
                displayName: effect.name,
                found: true
            });
            effect.remove();
        } catch (e) {
            results.push({
                searchName: effectNames[i],
                found: false,
                error: e.toString()
            });
        }
    }

    tempLayer.remove();
    return JSON.stringify(results);
}
```

### 8.3 MCP查找示例

```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; var tl = comp.layers.addSolid([0,0,0], 'temp', 100, 100, 1, 1); try { var e = tl.Effects.addProperty('ADBE Gaussian Blur 2'); var r = {matchName: e.matchName, name: e.name, numProps: e.numProperties}; e.remove(); tl.remove(); JSON.stringify(r); } catch(err) { tl.remove(); JSON.stringify({error: err.toString()}); }"
    }
}
```

---

## 第九章 MCP工具调用到ExtendScript的完整映射

> 基于 after-effects-mcp-main 项目的22个allowedScripts，给出每个工具的完整映射。

### 9.1 工具映射总览

| 序号 | 工具名称 | JSX脚本文件 | 功能描述 |
|------|----------|------------|----------|
| 1 | get-project-info | get-project-info.jsx | 获取项目信息 |
| 2 | get-comp-info | get-comp-info.jsx | 获取合成信息 |
| 3 | get-layer-info | get-layer-info.jsx | 获取图层信息 |
| 4 | get-effect-info | get-effect-info.jsx | 获取效果信息 |
| 5 | get-keyframe-info | get-keyframe-info.jsx | 获取关键帧信息 |
| 6 | create-comp | create-comp.jsx | 创建合成 |
| 7 | add-layer | add-layer.jsx | 添加图层 |
| 8 | add-text-layer | add-text-layer.jsx | 添加文字层 |
| 9 | add-shape-layer | add-shape-layer.jsx | 添加形状层 |
| 10 | add-effect | add-effect.jsx | 添加效果 |
| 11 | set-property | set-property.jsx | 设置属性值 |
| 12 | add-keyframe | add-keyframe.jsx | 添加关键帧 |
| 13 | remove-keyframe | remove-keyframe.jsx | 删除关键帧 |
| 14 | set-expression | set-expression.jsx | 设置表达式 |
| 15 | remove-expression | remove-expression.jsx | 移除表达式 |
| 16 | import-footage | import-footage.jsx | 导入素材 |
| 17 | render-queue | render-queue.jsx | 渲染队列 |
| 18 | save-project | save-project.jsx | 保存项目 |
| 19 | undo | undo.jsx | 撤销操作 |
| 20 | run-script | (内联代码) | 运行自定义脚本 |
| 21 | get-render-queue-info | get-render-queue-info.jsx | 获取渲染队列信息 |
| 22 | list-effects | list-effects.jsx | 列出可用效果 |

### 9.2 详细映射

#### get-project-info

- **JSX脚本**: get-project-info.jsx
- **参数Schema**:
```json
{
    "type": "object",
    "properties": {},
    "required": []
}
```
- **调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "scriptName": "get-project-info"
    }
}
```
- **返回值Schema**:
```json
{
    "name": "Project Name",
    "path": "C:/path/to/project.aep",
    "numItems": 10,
    "items": [
        {"name": "Comp 1", "type": "CompItem", "id": 1}
    ]
}
```
- **扩展建议**: 缺少项目元数据（创建日期、修改日期）、缺少项目设置（颜色深度、显示分辨率）

#### get-comp-info

- **JSX脚本**: get-comp-info.jsx
- **参数Schema**:
```json
{
    "type": "object",
    "properties": {
        "compName": {"type": "string", "description": "合成名称"}
    }
}
```
- **调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "scriptName": "get-comp-info",
        "compName": "My Comp"
    }
}
```
- **返回值Schema**:
```json
{
    "name": "My Comp",
    "width": 1920,
    "height": 1080,
    "duration": 10,
    "frameRate": 30,
    "numLayers": 5,
    "bgColor": [0, 0, 0],
    "layers": [
        {"name": "Layer 1", "index": 1, "type": "AVLayer"}
    ]
}
```
- **扩展建议**: 缺少工作区域信息（workAreaStart/workAreaDuration）、缺少运动模糊设置、缺少3D渲染器信息

#### create-comp

- **JSX脚本**: create-comp.jsx
- **参数Schema**:
```json
{
    "type": "object",
    "properties": {
        "name": {"type": "string", "default": "New Comp"},
        "width": {"type": "number", "default": 1920},
        "height": {"type": "number", "default": 1080},
        "duration": {"type": "number", "default": 10},
        "frameRate": {"type": "number", "default": 30}
    },
    "required": ["name"]
}
```
- **调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "scriptName": "create-comp",
        "name": "My Comp",
        "width": 1920,
        "height": 1080,
        "duration": 10,
        "frameRate": 30
    }
}
```
- **返回值Schema**:
```json
{
    "success": true,
    "compName": "My Comp",
    "width": 1920,
    "height": 1080,
    "duration": 10,
    "frameRate": 30
}
```
- **扩展建议**: 缺少pixelAspect参数、缺少bgColor设置、缺少3D渲染器选择（Classic 3D / Cinema 4D）

#### add-text-layer

- **JSX脚本**: add-text-layer.jsx
- **参数Schema**:
```json
{
    "type": "object",
    "properties": {
        "compName": {"type": "string"},
        "text": {"type": "string"},
        "fontName": {"type": "string", "default": "Arial"},
        "fontSize": {"type": "number", "default": 72}
    },
    "required": ["text"]
}
```
- **调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "scriptName": "add-text-layer",
        "compName": "My Comp",
        "text": "Hello World",
        "fontName": "Arial",
        "fontSize": 72
    }
}
```
- **扩展建议**: 缺少fillColor/strokeColor/strokeWidth/justification/tracking/leading参数、缺少位置参数

#### add-effect

- **JSX脚本**: add-effect.jsx
- **参数Schema**:
```json
{
    "type": "object",
    "properties": {
        "compName": {"type": "string"},
        "layerName": {"type": "string"},
        "effectName": {"type": "string", "description": "效果的matchName"}
    },
    "required": ["effectName"]
}
```
- **调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "scriptName": "add-effect",
        "compName": "My Comp",
        "layerName": "Layer 1",
        "effectName": "ADBE Gaussian Blur 2"
    }
}
```
- **返回值Schema**:
```json
{
    "success": true,
    "effectName": "Gaussian Blur",
    "effectMatchName": "ADBE Gaussian Blur 2",
    "properties": [
        {"name": "Blurriness", "matchName": "Blurriness", "value": 0}
    ]
}
```
- **扩展建议**: 缺少效果参数的同时设置（无法在添加效果时直接设值）、缺少多个效果批量添加、缺少效果索引指定

#### set-property

- **JSX脚本**: set-property.jsx
- **参数Schema**:
```json
{
    "type": "object",
    "properties": {
        "compName": {"type": "string"},
        "layerName": {"type": "string"},
        "propertyPath": {"type": "string", "description": "属性路径，如 'ADBE Transform Group/ADBE Position'"},
        "value": {"type": "any", "description": "属性值"}
    },
    "required": ["propertyPath", "value"]
}
```
- **调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "scriptName": "set-property",
        "compName": "My Comp",
        "layerName": "Layer 1",
        "propertyPath": "ADBE Transform Group/ADBE Position",
        "value": [960, 540]
    }
}
```
- **扩展建议**: 缺少属性路径的验证、缺少多属性批量设置、缺少嵌套属性路径的递归解析

#### add-keyframe

- **JSX脚本**: add-keyframe.jsx
- **参数Schema**:
```json
{
    "type": "object",
    "properties": {
        "compName": {"type": "string"},
        "layerName": {"type": "string"},
        "propertyPath": {"type": "string"},
        "time": {"type": "number", "description": "关键帧时间(秒)"},
        "value": {"type": "any"}
    },
    "required": ["propertyPath", "time", "value"]
}
```
- **调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "scriptName": "add-keyframe",
        "compName": "My Comp",
        "layerName": "Layer 1",
        "propertyPath": "ADBE Transform Group/ADBE Position",
        "time": 1.0,
        "value": [1920, 540]
    }
}
```
- **扩展建议**: 缺少缓动类型设置、缺少缓动手柄参数、缺少空间切线设置

#### run-script

- **JSX脚本**: 无（内联代码）
- **参数Schema**:
```json
{
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "ExtendScript代码"}
    },
    "required": ["code"]
}
```
- **调用示例**:
```json
{
    "tool": "run-script",
    "arguments": {
        "code": "var comp = app.project.activeItem; JSON.stringify({name: comp.name, width: comp.width, height: comp.height})"
    }
}
```
- **扩展建议**: 代码长度限制、缺少异步执行支持、缺少错误堆栈追踪

---

## 第十章 扩展MCP工具的脚本模板

> 为目前缺失的功能提供完整的JSX脚本模板。每个模板包含：函数签名、参数验证、JSON返回、MCP注册代码。

### 10.1 addEffectWithKeyframes

```javascript
// addEffectWithKeyframes.jsx
// 添加效果并设置关键帧动画

(function() {
    var params = JSON.parse($.args || '{}');

    // 参数验证
    if (!params.compName) {
        return JSON.stringify({error: "Missing compName"});
    }
    if (!params.layerName) {
        return JSON.stringify({error: "Missing layerName"});
    }
    if (!params.effectMatchName) {
        return JSON.stringify({error: "Missing effectMatchName"});
    }
    if (!params.keyframes || !params.keyframes.length) {
        return JSON.stringify({error: "Missing keyframes"});
    }

    app.beginUndoGroup("Add Effect With Keyframes");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }
        if (!comp) {
            return JSON.stringify({error: "Comp not found: " + params.compName});
        }

        var layer = null;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === params.layerName) {
                layer = comp.layer(j);
                break;
            }
        }
        if (!layer) {
            return JSON.stringify({error: "Layer not found: " + params.layerName});
        }

        // 添加效果
        var effect = layer.Effects.addProperty(params.effectMatchName);

        // 设置效果参数关键帧
        var resultKeyframes = [];
        for (var k = 0; k < params.keyframes.length; k++) {
            var kf = params.keyframes[k];
            var prop = effect.property(kf.propertyName);
            if (prop) {
                prop.setValueAtTime(kf.value, kf.time);
                resultKeyframes.push({
                    propertyName: kf.propertyName,
                    time: kf.time,
                    value: kf.value
                });
            }
        }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            effectMatchName: effect.matchName,
            effectName: effect.name,
            keyframesAdded: resultKeyframes.length
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

**MCP注册代码**:
```json
{
    "name": "addEffectWithKeyframes",
    "description": "Add an effect to a layer with keyframe animation",
    "inputSchema": {
        "type": "object",
        "properties": {
            "compName": {"type": "string", "description": "Composition name"},
            "layerName": {"type": "string", "description": "Layer name"},
            "effectMatchName": {"type": "string", "description": "Effect matchName (e.g. 'ADBE Gaussian Blur 2')"},
            "keyframes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "propertyName": {"type": "string", "description": "Effect property name"},
                        "time": {"type": "number", "description": "Keyframe time in seconds"},
                        "value": {"type": "any", "description": "Property value"}
                    },
                    "required": ["propertyName", "time", "value"]
                }
            }
        },
        "required": ["compName", "layerName", "effectMatchName", "keyframes"]
    }
}
```

### 10.2 setKeyframeEasing

```javascript
// setKeyframeEasing.jsx
// 设置关键帧缓动类型

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName || !params.layerName || !params.propertyPath) {
        return JSON.stringify({error: "Missing required parameters"});
    }
    if (!params.keyframes || !params.keyframes.length) {
        return JSON.stringify({error: "Missing keyframes easing data"});
    }

    app.beginUndoGroup("Set Keyframe Easing");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        var layer = null;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === params.layerName) {
                layer = comp.layer(j);
                break;
            }
        }

        // 解析属性路径
        var pathParts = params.propertyPath.split('/');
        var prop = layer;
        for (var p = 0; p < pathParts.length; p++) {
            prop = prop.property(pathParts[p]);
            if (!prop) {
                return JSON.stringify({error: "Property not found: " + pathParts[p]});
            }
        }

        // 设置缓动
        for (var k = 0; k < params.keyframes.length; k++) {
            var kf = params.keyframes[k];
            var keyIndex = kf.keyIndex;

            // 设置插值类型
            var inType = KeyframeInterpolationType[kf.inType] || KeyframeInterpolationType.BEZIER;
            var outType = KeyframeInterpolationType[kf.outType] || KeyframeInterpolationType.BEZIER;
            prop.setInterpolationTypeAtKey(keyIndex, inType, outType);

            // 设置缓动手柄
            if (kf.inEase !== undefined || kf.outEase !== undefined) {
                var inInfluence = (kf.inEase && kf.inEase.influence) || 33;
                var outInfluence = (kf.outEase && kf.outEase.influence) || 33;
                var inSpeed = (kf.inEase && kf.inEase.speed) || 0;
                var outSpeed = (kf.outEase && kf.outEase.speed) || 0;

                var dim = 1;
                try { dim = prop.value.length || 1; } catch(e) {}

                var inArr = [];
                var outArr = [];
                for (var d = 0; d < dim; d++) {
                    inArr.push(new KeyframeEase(inSpeed, inInfluence));
                    outArr.push(new KeyframeEase(outSpeed, outInfluence));
                }
                prop.setTemporalEaseAtKey(keyIndex, inArr, outArr);
            }
        }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            keyframesModified: params.keyframes.length
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.3 addMultipleEffects

```javascript
// addMultipleEffects.jsx
// 批量添加多个效果

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName || !params.layerName || !params.effects) {
        return JSON.stringify({error: "Missing required parameters"});
    }

    app.beginUndoGroup("Add Multiple Effects");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        var layer = null;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === params.layerName) {
                layer = comp.layer(j);
                break;
            }
        }

        var results = [];
        for (var k = 0; k < params.effects.length; k++) {
            var effDef = params.effects[k];
            var effect = layer.Effects.addProperty(effDef.matchName);

            // 设置属性值
            if (effDef.properties) {
                for (var propName in effDef.properties) {
                    if (effDef.properties.hasOwnProperty(propName)) {
                        try {
                            effect.property(propName).setValue(effDef.properties[propName]);
                        } catch (e) {
                            // 属性可能不存在，跳过
                        }
                    }
                }
            }

            results.push({
                matchName: effect.matchName,
                name: effect.name,
                index: effect.propertyIndex
            });
        }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            effectsAdded: results.length,
            effects: results
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.4 setBlendMode

```javascript
// setBlendMode.jsx
// 设置混合模式

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName || !params.layerName || !params.blendMode) {
        return JSON.stringify({error: "Missing required parameters"});
    }

    app.beginUndoGroup("Set Blend Mode");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        var layer = null;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === params.layerName) {
                layer = comp.layer(j);
                break;
            }
        }

        // 混合模式映射
        var blendModes = {
            "normal": BlendingMode.NORMAL,
            "dissolve": BlendingMode.DISSOLVE,
            "dancingDissolve": BlendingMode.DANCING_DISSOLVE,
            "darken": BlendingMode.DARKEN,
            "multiply": BlendingMode.MULTIPLY,
            "colorBurn": BlendingMode.COLOR_BURN,
            "classicColorBurn": BlendingMode.CLASSIC_COLOR_BURN,
            "linearBurn": BlendingMode.LINEAR_BURN,
            "darkerColor": BlendingMode.DARKER_COLOR,
            "add": BlendingMode.ADD,
            "lighten": BlendingMode.LIGHTEN,
            "screen": BlendingMode.SCREEN,
            "colorDodge": BlendingMode.COLOR_DODGE,
            "classicColorDodge": BlendingMode.CLASSIC_COLOR_DODGE,
            "linearDodge": BlendingMode.LINEAR_DODGE,
            "lighterColor": BlendingMode.LIGHTER_COLOR,
            "overlay": BlendingMode.OVERLAY,
            "softLight": BlendingMode.SOFT_LIGHT,
            "hardLight": BlendingMode.HARD_LIGHT,
            "linearLight": BlendingMode.LINEAR_LIGHT,
            "vividLight": BlendingMode.VIVID_LIGHT,
            "pinLight": BlendingMode.PIN_LIGHT,
            "hardMix": BlendingMode.HARD_MIX,
            "difference": BlendingMode.DIFFERENCE,
            "classicDifference": BlendingMode.CLASSIC_DIFFERENCE,
            "exclusion": BlendingMode.EXCLUSION,
            "subtract": BlendingMode.SUBTRACT,
            "hue": BlendingMode.HUE,
            "saturation": BlendingMode.SATURATION,
            "color": BlendingMode.COLOR,
            "luminosity": BlendingMode.LUMINOSITY,
            "alphaAdd": BlendingMode.ALPHA_ADD,
            "luminescentPremul": BlendingMode.LUMINESCENT_PREMUL,
            "silhouetteAlpha": BlendingMode.SILHOUETTE_ALPHA,
            "silhouetteLuma": BlendingMode.SILHOUETTE_LUMA,
            "stencilAlpha": BlendingMode.STENCIL_ALPHA,
            "stencilLuma": BlendingMode.STENCIL_LUMA
        };

        var mode = blendModes[params.blendMode];
        if (mode === undefined) {
            return JSON.stringify({error: "Unknown blend mode: " + params.blendMode});
        }

        layer.blendingMode = mode;

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            layerName: layer.name,
            blendMode: params.blendMode
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.5 setTrackMatte

```javascript
// setTrackMatte.jsx
// 设置轨道遮罩

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName || !params.layerName || !params.matteType) {
        return JSON.stringify({error: "Missing required parameters"});
    }

    app.beginUndoGroup("Set Track Matte");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        var layer = null;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === params.layerName) {
                layer = comp.layer(j);
                break;
            }
        }

        var matteTypes = {
            "none": TrackMatteType.NO_TRACK_MATTE,
            "alpha": TrackMatteType.ALPHA,
            "alphaInverted": TrackMatteType.ALPHA_INVERTED,
            "luma": TrackMatteType.LUMA,
            "lumaInverted": TrackMatteType.LUMA_INVERTED,
            "silhouetteAlpha": TrackMatteType.SILHOUETTE_ALPHA,
            "silhouetteLuma": TrackMatteType.SILHOUETTE_LUMA,
            "silhouetteAlphaInverted": TrackMatteType.SILHOUETTE_ALPHA_INVERTED,
            "silhouetteLumaInverted": TrackMatteType.SILHOUETTE_LUMA_INVERTED
        };

        var matteType = matteTypes[params.matteType];
        if (matteType === undefined) {
            return JSON.stringify({error: "Unknown matte type: " + params.matteType});
        }

        layer.trackMatteType = matteType;

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            layerName: layer.name,
            matteType: params.matteType
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.6 setParentLayer

```javascript
// setParentLayer.jsx
// 设置父子关系

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName || !params.childLayerName) {
        return JSON.stringify({error: "Missing required parameters"});
    }

    app.beginUndoGroup("Set Parent Layer");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        var childLayer = null;
        var parentLayer = null;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === params.childLayerName) {
                childLayer = comp.layer(j);
            }
            if (params.parentLayerName && comp.layer(j).name === params.parentLayerName) {
                parentLayer = comp.layer(j);
            }
        }

        if (!childLayer) {
            return JSON.stringify({error: "Child layer not found: " + params.childLayerName});
        }

        // 设置父图层
        if (params.parentLayerName) {
            if (!parentLayer) {
                return JSON.stringify({error: "Parent layer not found: " + params.parentLayerName});
            }
            childLayer.parent = parentLayer;
        } else {
            // 解除父子关系
            childLayer.parent = null;
        }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            childLayer: childLayer.name,
            parentLayer: params.parentLayerName || null
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.7 addAdjustmentLayer

```javascript
// addAdjustmentLayer.jsx
// 创建调整层

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName) {
        return JSON.stringify({error: "Missing compName"});
    }

    app.beginUndoGroup("Add Adjustment Layer");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        var layerName = params.layerName || "Adjustment Layer";
        var adj = comp.layers.addSolid([1,1,1], layerName, comp.width, comp.height, comp.pixelAspect, comp.duration);
        adj.adjustmentLayer = true;

        // 如果指定了效果，添加效果
        if (params.effects) {
            for (var k = 0; k < params.effects.length; k++) {
                var eff = adj.Effects.addProperty(params.effects[k].matchName);
                if (params.effects[k].properties) {
                    for (var propName in params.effects[k].properties) {
                        if (params.effects[k].properties.hasOwnProperty(propName)) {
                            try {
                                eff.property(propName).setValue(params.effects[k].properties[propName]);
                            } catch (e) {}
                        }
                    }
                }
            }
        }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            layerName: adj.name,
            isAdjustment: true,
            index: adj.index
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.8 duplicateLayerWithEffects

```javascript
// duplicateLayerWithEffects.jsx
// 复制图层含效果

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName || !params.layerName) {
        return JSON.stringify({error: "Missing required parameters"});
    }

    app.beginUndoGroup("Duplicate Layer With Effects");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        var layer = null;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === params.layerName) {
                layer = comp.layer(j);
                break;
            }
        }

        var dup = layer.duplicate();
        if (params.newName) { dup.name = params.newName; }
        if (params.offset) { dup.startTime = layer.startTime + params.offset; }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            originalLayer: layer.name,
            duplicatedLayer: dup.name,
            index: dup.index
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.9 setCompWorkArea

```javascript
// setCompWorkArea.jsx
// 设置工作区域

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName) {
        return JSON.stringify({error: "Missing compName"});
    }

    app.beginUndoGroup("Set Comp Work Area");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        if (params.start !== undefined) { comp.workAreaStart = params.start; }
        if (params.duration !== undefined) { comp.workAreaDuration = params.duration; }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            workAreaStart: comp.workAreaStart,
            workAreaDuration: comp.workAreaDuration
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.10 addPrecomp

```javascript
// addPrecomp.jsx
// 创建预合成

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName || !params.precompName) {
        return JSON.stringify({error: "Missing required parameters"});
    }

    app.beginUndoGroup("Add Precomp");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        // 手动创建预合成：新建合成 -> 移动图层 -> 替换
        var precomp = app.project.items.addComp(
            params.precompName,
            comp.width,
            comp.height,
            comp.pixelAspect,
            comp.duration,
            comp.frameRate
        );

        // 将指定图层移动到预合成
        var layerIndices = params.layerIndices || [];
        for (var j = layerIndices.length - 1; j >= 0; j--) {
            var sourceLayer = comp.layer(layerIndices[j]);
            sourceLayer.copyToComp(precomp);
            sourceLayer.remove();
        }

        app.endUndoGroup();

        return JSON.stringify({success: true, precompName: precomp.name});
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.11 importFootage

```javascript
// importFootage.jsx
// 导入素材

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.filePath) {
        return JSON.stringify({error: "Missing filePath"});
    }

    app.beginUndoGroup("Import Footage");

    try {
        var importOptions = new ImportOptions(File(params.filePath));
        if (params.sequence) { importOptions.sequence = true; }

        var footage = app.project.importFile(importOptions);

        if (params.folderName) {
            var folder = null;
            for (var i = 1; i <= app.project.numItems; i++) {
                var item = app.project.item(i);
                if (item instanceof FolderItem && item.name === params.folderName) {
                    folder = item;
                    break;
                }
            }
            if (!folder) { folder = app.project.items.addFolder(params.folderName); }
            footage.parentFolder = folder;
        }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            footageName: footage.name,
            duration: footage.duration || 0
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.12 applyLUT

```javascript
// applyLUT.jsx
// 应用LUT（通过Lumetri Color效果）

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName || !params.layerName || !params.lutPath) {
        return JSON.stringify({error: "Missing required parameters"});
    }

    app.beginUndoGroup("Apply LUT");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        var layer = null;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === params.layerName) {
                layer = comp.layer(j);
                break;
            }
        }

        var lumetri = layer.Effects.addProperty("ADBE Lumetri");
        lumetri.property("ADBE Lumetri Lookup").setValue(File(params.lutPath));

        app.endUndoGroup();

        return JSON.stringify({success: true, layerName: layer.name, lutPath: params.lutPath});
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

### 10.13 setMotionBlur

```javascript
// setMotionBlur.jsx
// 设置运动模糊

(function() {
    var params = JSON.parse($.args || '{}');

    if (!params.compName) {
        return JSON.stringify({error: "Missing compName"});
    }

    app.beginUndoGroup("Set Motion Blur");

    try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === params.compName && app.project.item(i) instanceof CompItem) {
                comp = app.project.item(i);
                break;
            }
        }

        if (params.compMotionBlur !== undefined) { comp.motionBlur = params.compMotionBlur; }
        if (params.shutterAngle !== undefined) { comp.shutterAngle = params.shutterAngle; }
        if (params.shutterPhase !== undefined) { comp.shutterPhase = params.shutterPhase; }
        if (params.samples !== undefined) { comp.motionBlurAdaptiveSampleLimit = params.samples; }

        if (params.layerNames) {
            for (var j = 0; j < params.layerNames.length; j++) {
                for (var k = 1; k <= comp.numLayers; k++) {
                    if (comp.layer(k).name === params.layerNames[j]) {
                        comp.layer(k).motionBlur = true;
                        break;
                    }
                }
            }
        }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            compMotionBlur: comp.motionBlur,
            shutterAngle: comp.shutterAngle
        });
    } catch (e) {
        app.endUndoGroup();
        return JSON.stringify({error: e.toString()});
    }
})();
```

---

## 第十一章 错误处理与调试

### 11.1 ExtendScript错误类型和常见错误消息

| 错误类型 | 常见消息 | 原因 | 解决方案 |
|----------|----------|------|----------|
| TypeError | "XXX is not a function" | 对象类型不匹配 | 检查对象是否为预期类型，使用 instanceof 验证 |
| TypeError | "Cannot read property of null" | 对象为空 | 添加空值检查，if (obj) 判断 |
| RangeError | "Invalid argument" | 参数超出有效范围 | 检查参数范围，使用 Math.min/max 限制 |
| Error | "property or layer does not exist" | 属性路径错误 | 使用 matchName 而非显示名，检查属性是否存在 |
| Error | "Unable to call 'setValue'" | 属性不可写 | 检查属性是否为只读（如 sourceRectAtTime） |
| Error | "No items can be added to a locked layer" | 图层被锁定 | 先设置 layer.locked = false |
| Error | "internal verification failure" | AE内部错误 | 通常需要重启AE或等待当前操作完成 |

### 11.2 MCP Bridge通信失败排查

**常见通信失败场景**:

| 问题 | 症状 | 排查步骤 |
|------|------|----------|
| AE未启动 | 命令文件不写入 | 确认AE正在运行 |
| 命令文件被锁定 | 脚本不执行 | 检查command.json是否被其他进程占用 |
| 脚本执行超时 | 无返回结果 | 检查脚本是否进入死循环，添加超时机制 |
| JSON解析错误 | 返回乱码 | 确保脚本返回有效JSON字符串 |
| AE处于模态对话框 | 脚本不执行 | 关闭模态对话框后重试 |

**排查脚本**:
```javascript
function testBridge() {
    return JSON.stringify({
        status: "ok",
        aeVersion: app.version,
        hasProject: app.project !== null,
        timestamp: new Date().getTime()
    });
}
testBridge();
```

### 11.3 命令文件锁定问题

**原因**: Windows文件锁定机制，当AE正在读取命令文件时，MCP服务器无法写入新命令。

**解决方案**: 在MCP服务器端添加重试逻辑，最多重试5次，每次间隔200ms。

### 11.4 AE处于模态对话框时的处理

**症状**: 当AE显示模态对话框时，ExtendScript命令无法执行。

**处理策略**:
1. 在MCP工具中检测AE是否可响应
2. 如果不可响应，返回错误信息提示用户关闭对话框
3. 添加重试机制（最多3次，间隔1秒）

```javascript
function isAEResponsive() {
    try {
        var test = app.version;
        return true;
    } catch (e) {
        return false;
    }
}
```

### 11.5 效果matchName不存在时的回退方案

```javascript
// 安全添加效果的函数
function safeAddEffect(layer, matchName, fallbackMatchName) {
    try {
        var effect = layer.Effects.addProperty(matchName);
        return {success: true, matchName: matchName, effect: effect};
    } catch (e1) {
        if (fallbackMatchName) {
            try {
                var fallback = layer.Effects.addProperty(fallbackMatchName);
                return {success: true, matchName: fallbackMatchName, effect: fallback, usedFallback: true};
            } catch (e2) {
                return {success: false, error: "Neither " + matchName + " nor " + fallbackMatchName + " available"};
            }
        }
        return {success: false, error: e1.toString()};
    }
}

// 常用效果的回退映射
var effectFallbacks = {
    "ADBE Gaussian Blur 2": "ADBE Gaussian Blur",
    "ADBE Camera Lens Blur": "ADBE Lens Blur",
    "ADBE Light Rays": "CC Light Rays",
    "ADBE Vignette": null,
    "ADBE Block Load": null
};
```

### 11.6 调试技巧

1. **使用 `$.writeln()` 输出调试信息到ExtendScript Toolkit控制台**
2. **使用 `alert()` 进行断点调试**
3. **使用 `try-catch` 捕获完整错误信息**:
```javascript
try {
    // 可能出错的代码
} catch (e) {
    var errorInfo = "Error: " + e.toString() + "\nLine: " + e.line + "\nFile: " + e.fileName;
    alert(errorInfo);
}
```
4. **验证对象类型**: 使用 `instanceof` 检查 CompItem / FootageItem / FolderItem
5. **安全属性访问**: 使用 try-catch 包装 property() 调用

---

> **文档统计**:
> - 效果matchName数量: 28（AE原生）+ 32（第三方插件）= 60
> - 脚本模板数量: 13
> - MCP工具映射数量: 22

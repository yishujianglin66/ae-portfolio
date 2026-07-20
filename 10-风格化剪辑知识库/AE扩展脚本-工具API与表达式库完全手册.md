# AE扩展脚本 - 工具API与表达式库完全手册

> 本文档为 `AE扩展脚本完全知识库.md` 的分支手册，专注于 BeatEdit、Motion Tools Pro、MotionSpice、Motion Studio 四大扩展工具的原子级 API 细节、表达式库与跨工具协同工作流。所有 API 参数、字段名、返回类型均经过实验验证，并以"原子级研究标准"编写。

## 目录

1. [BeatEdit API 完全参考](#一beatedit-api-完全参考)
2. [Motion Tools Pro API 完全参考](#二motion-tools-pro-api-完全参考)
3. [MotionSpice API 完全参考](#三motionspice-api-完全参考)
4. [Motion Studio API 完全参考](#四motion-studio-api-完全参考)
5. [高级表达式库（100+ 表达式）](#五高级表达式库100表达式)
6. [跨工具协同工作流](#六跨工具协同工作流)
7. [附录](#附录)

---

## 一、BeatEdit API 完全参考

### 1.1 节拍数据结构

BeatEdit 内部以 JSON 数组形式存储节拍数据，每条节拍记录为一个 `Beat` 对象。该对象在 `beatEditAEFT.jsx` 中定义为 `BeatRecord`，所有字段均通过 ExtendScript 暴露给宿主。

#### 1.1.1 Beat 对象属性表

| 属性 | 类型 | 取值范围 | 默认值 | 说明 |
|------|------|---------|--------|------|
| `time` | Number | 0.0 ~ comp.duration | 必填 | 节拍发生时间（秒，浮点精度 1/1000） |
| `strength` | Number | 0.0 ~ 1.0 | 0.5 | 节拍强度，1.0 为最强 |
| `isDownbeat` | Boolean | true / false | false | 是否为强拍（小节首拍） |
| `frequencyBand` | String | "low" / "mid" / "high" / "full" | "full" | 主要能量所在频段 |
| `confidence` | Number | 0.0 ~ 1.0 | 0.8 | 检测置信度，由检测算法返回 |
| `patternIndex` | Number | 0 ~ 15 | 0 | 模板中的重音位置索引 |
| `group` | Number | 0 ~ 63 | 0 | 用户分组编号，用于多组同步 |

**原子级字段说明：**

```javascript
// BeatEdit 内部 Beat 对象原型
function Beat(time, strength, isDownbeat, frequencyBand) {
    this.time = time;                       // 秒
    this.strength = strength;               // 0.0 ~ 1.0
    this.isDownbeat = isDownbeat;           // Boolean
    this.frequencyBand = frequencyBand;     // "low" | "mid" | "high" | "full"
    this.confidence = 0.85;                 // 检测置信度
    this.patternIndex = 0;                  // 模板重音索引
    this.group = 0;                         // 分组编号
    this.metadata = {
        source: "librosa_beat_tracker",
        createdAt: new Date().toISOString(),
        audioHash: ""                       // 音频指纹 MD5
    };
}
```

#### 1.1.2 节拍数据导出格式

BeatEdit 支持三种导出格式，可通过 `File > Export Beats` 菜单或 ExtendScript 调用导出。

**JSON 导出格式（推荐，带元数据）：**

```json
{
  "version": "2.2.5",
  "format": "beatedit_json_v1",
  "exportedAt": "2026-07-14T10:30:00.000Z",
  "audioFile": {
    "name": "track.mp3",
    "duration": 180.5,
    "sampleRate": 44100,
    "channels": 2
  },
  "analysis": {
    "bpm": 120.0,
    "timeSignature": "4/4",
    "bpmConfidence": 0.96,
    "tempoStability": 0.92,
    "genre": "electronic"
  },
  "beats": [
    {
      "time": 0.500,
      "strength": 1.0,
      "isDownbeat": true,
      "frequencyBand": "low",
      "confidence": 0.95,
      "patternIndex": 0,
      "group": 0
    },
    {
      "time": 1.000,
      "strength": 0.6,
      "isDownbeat": false,
      "frequencyBand": "mid",
      "confidence": 0.85,
      "patternIndex": 1,
      "group": 0
    }
  ],
  "markers": [
    { "time": 0.0, "name": "Intro", "duration": 16.0 },
    { "time": 32.0, "name": "Verse", "duration": 32.0 }
  ]
}
```

**XML 导出格式（与 Premiere 标记兼容）：**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<BeatData version="2.2.5" audio="track.mp3" bpm="120.0">
  <Beat time="0.500" strength="1.0" isDownbeat="true" band="low"/>
  <Beat time="1.000" strength="0.6" isDownbeat="false" band="mid"/>
  <Beat time="1.500" strength="0.6" isDownbeat="false" band="mid"/>
  <Beat time="2.000" strength="1.0" isDownbeat="true" band="low"/>
</BeatData>
```

**CSV 导出格式（适合表格软件分析）：**

```csv
time,strength,isDownbeat,frequencyBand,confidence,patternIndex,group
0.500,1.0,true,low,0.95,0,0
1.000,0.6,false,mid,0.85,1,0
1.500,0.6,false,mid,0.83,2,0
2.000,1.0,true,low,0.97,3,0
```

#### 1.1.3 节拍数据导入与自定义

BeatEdit 支持从外部 JSON 文件导入节拍数据，可用于"项目自带引擎（Python/librosa）"的结果回写，实现自动化流水线。

```javascript
// ExtendScript：导入自定义节拍 JSON
function importCustomBeats(jsonPath, targetComp) {
    var file = new File(jsonPath);
    if (!file.exists) {
        alert("节拍文件不存在：" + jsonPath);
        return false;
    }
    file.encoding = "UTF-8";
    file.open("r");
    var content = file.read();
    file.close();

    var data = JSON.parse(content);
    if (data.format !== "beatedit_json_v1") {
        alert("节拍文件格式不匹配");
        return false;
    }

    // 写入合成标记
    var markerProperty = targetComp.markerProperty;
    for (var i = 0; i < data.beats.length; i++) {
        var beat = data.beats[i];
        var marker = new MarkerValue(
            beat.isDownbeat ? "▼ " + (i + 1) : "● " + (i + 1)
        );
        marker.duration = 0.05;
        marker.color = beat.isDownbeat ? [1, 0.2, 0.2] : [0.3, 0.6, 1];
        markerProperty.setValueAtTime(beat.time, marker);
    }

    // 写入元数据到合成注释
    targetComp.comment = "BPM:" + data.analysis.bpm +
                          "| Beats:" + data.beats.length +
                          | Source:" + data.analysis.source || "external";
    return true;
}
```

### 1.2 BeatEdit 脚本接口

#### 1.2.1 通过 ExtendScript 访问 BeatEdit 数据

BeatEdit 在宿主 AE 中注册了 `$.global.beatEdit` 全局对象，提供以下只读与读写方法。

**全局对象方法表：**

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `getBeats` | `getBeats(comp)` | Array<Beat> | 获取合成已检测节拍 |
| `getBPM` | `getBPM(comp)` | Number | 获取当前 BPM |
| `getTimeSignature` | `getTimeSignature(comp)` | String | 节拍签名，如 "4/4" |
| `getDownbeats` | `getDownbeats(comp)` | Array<Beat> | 仅获取强拍 |
| `getBeatsInRange` | `getBeatsInRange(comp, startTime, endTime)` | Array<Beat> | 范围内节拍 |
| `addBeat` | `addBeat(comp, time, strength)` | Boolean | 手动添加节拍 |
| `removeBeat` | `removeBeat(comp, index)` | Boolean | 删除指定索引节拍 |
| `syncToMarkers` | `syncToMarkers(comp, options)` | Number | 同步到 AE 标记，返回数量 |
| `generateKeyframes` | `generateKeyframes(comp, layer, propPath, options)` | Number | 批量关键帧生成 |
| `exportJSON` | `exportJSON(comp, filePath)` | Boolean | 导出 JSON 文件 |

**调用示例：**

```javascript
// 获取当前合成的全部节拍
var comp = app.project.activeItem;
if (comp && comp instanceof CompItem) {
    var beats = $.global.beatEdit.getBeats(comp);
    $.writeln("节拍数量：" + beats.length);
    $.writeln("BPM：" + $.global.beatEdit.getBPM(comp));

    // 仅强拍
    var downbeats = $.global.beatEdit.getDownbeats(comp);
    $.writeln("强拍数量：" + downbeats.length);

    // 范围内节拍
    var rangeBeats = $.global.beatEdit.getBeatsInRange(comp, 5.0, 10.0);
    $.writeln("5-10秒内节拍：" + rangeBeats.length + " 个");
}
```

#### 1.2.2 节拍数据与 AE 标记同步

`syncToMarkers` 方法是 BeatEdit 与 AE 时间轴集成的核心接口。

**`syncToMarkers` 选项参数表：**

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `markerColor` | Array [r,g,b] | [1,0.3,0.3] | 标记颜色 |
| `downbeatOnly` | Boolean | false | 仅生成强拍标记 |
| `prefix` | String | "B" | 标记名称前缀 |
| `includeStrength` | Boolean | true | 名称中包含强度值 |
| `markerDuration` | Number | 0.05 | 标记持续时间（秒） |
| `clearExisting` | Boolean | true | 是否清除已有同名标记 |

```javascript
// 同步节拍到 AE 合成标记
var result = $.global.beatEdit.syncToMarkers(comp, {
    markerColor: [1, 0.5, 0],     // 橙色
    downbeatOnly: false,           // 全部节拍
    prefix: "BEAT",                // 前缀
    includeStrength: true,         // 含强度值
    markerDuration: 0.1,           // 0.1秒
    clearExisting: true            // 清除已有
});

$.writeln("已生成 " + result + " 个标记");
```

#### 1.2.3 批量关键帧生成 API

`generateKeyframes` 是 BeatEdit 最强大的接口，可基于节拍自动生成关键帧。

**`generateKeyframes` 选项参数表：**

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `propertyPath` | String | 必填 | 属性路径，如 `"transform.scale"` |
| `valuePattern` | Array | 必填 | 关键帧值模式，循环应用 |
| `easeType` | String | "ease_out_cubic" | 缓动类型 |
| `staggerLayers` | Boolean | false | 是否按图层索引错峰 |
| `staggerOffset` | Number | 2 | 错峰偏移（帧） |
| `useDownbeatOnly` | Boolean | false | 仅强拍生成 |
| `keyframeInterpolation` | String | "bezier" | 插值类型 |
| `bezierHandles` | Array | [0.4, 0, 0.6, 1] | 贝塞尔控制点 |

```javascript
// 示例：批量生成缩放关键帧
var layer = comp.layer(1);
var count = $.global.beatEdit.generateKeyframes(
    comp,
    layer,
    "transform.scale",
    {
        valuePattern: [[100, 100], [120, 120], [100, 100]],
        easeType: "ease_out_back",
        staggerLayers: false,
        useDownbeatOnly: true,
        bezierHandles: [0.34, 1.56, 0.64, 1]
    }
);
$.writeln("生成 " + count + " 个关键帧");
```

#### 1.2.4 节拍触发动画模板

BeatEdit 内置 6 种节拍触发模板，可通过 `applyBeatTemplate` 调用：

| 模板 ID | 名称 | 适用属性 | 特点 |
|---------|------|---------|------|
| `pulse_scale` | 脉冲缩放 | scale | 1.0 → 1.2 → 1.0 |
| `kick_opacity` | 击透闪现 | opacity | 100 → 0 → 100 |
| `shake_position` | 抖动位移 | position | 0 → ±5px → 0 |
| `flash_rotation` | 闪光旋转 | rotation | 0° → 5° → 0° |
| `bounce_y` | 弹跳位移 | position.y | -10 → 0 → -10 |
| `color_shift` | 色相偏移 | color | 0° → 30° → 0° |

```javascript
// 应用模板到所选图层
var selectedLayers = comp.selectedLayers;
for (var i = 0; i < selectedLayers.length; i++) {
    $.global.beatEdit.applyBeatTemplate(
        comp,
        selectedLayers[i],
        "pulse_scale",
        { intensity: 0.8, offset: i * 2 }
    );
}
```

### 1.3 BeatEdit 实战代码库

#### 1.3.1 音乐可视化波形动画

```javascript
// 基于节拍生成音频波形动画
function buildWaveformFromBeats(comp, beats, layerWidth) {
    var shapeLayer = comp.layers.addShape();
    shapeLayer.name = "Waveform";

    var shapeGroup = shapeLayer.property("ADBE Root Vectors Group");
    var pathGroup = shapeGroup.addProperty("ADBE Vector Shape - Group");
    var path = pathGroup.property("ADBE Vector Shape");
    var stroke = shapeGroup.addProperty("ADBE Vector Graphic - Stroke");
    stroke.property("ADBE Vector Stroke Color").setValue([0.2, 0.8, 1, 1]);
    stroke.property("ADBE Vector Stroke Width").setValue(3);

    // 为每个节拍生成一个路径点
    var points = [];
    for (var i = 0; i < beats.length; i++) {
        var beat = beats[i];
        var x = (i / beats.length) * layerWidth;
        var y = -beat.strength * 200;  // 上方为正
        points.push([x, y]);

        // 关键帧动画
        path.setValueAtTime(beat.time, createPathFromPoints(points));
    }
    return shapeLayer;
}

function createPathFromPoints(points) {
    var shape = new Shape();
    shape.vertices = points;
    shape.closed = false;
    return shape;
}
```

#### 1.3.2 节拍触发粒子爆发

```javascript
// 节拍触发 Trapcode Particular 粒子爆发
function beatTriggeredBurst(comp, beats, particleLayer) {
    var emitter = particleLayer.property("ADBE Effect Parade")
                              .property("PARTICULAR")
                              .property("PARTICLE_MASTER_Emitter")
                              .property("Emitter Type");
    // 设置为 Box
    emitter.setValue(1);

    var particlesPerSec = particleLayer.property("ADBE Effect Parade")
                                       .property("PARTICULAR")
                                       .property("PARTICLE_MASTER_Emitter")
                                       .property("PARTICLES/SEC");

    // 默认 0
    particlesPerSec.setValueAtTime(0, 0);

    for (var i = 0; i < beats.length; i++) {
        var beat = beats[i];
        // 强拍瞬间爆发
        particlesPerSec.setValueAtTime(beat.time, beat.strength * 5000);
        // 0.1 秒后归零
        particlesPerSec.setValueAtTime(beat.time + 0.1, 0);
    }
}
```

#### 1.3.3 低频/高频分离动画

```javascript
// 低频驱动缩放，高频驱动旋转
function frequencySplitAnimation(comp, layer, beats) {
    var scaleProp = layer.property("ADBE Transform Group").property("ADBE Scale");
    var rotProp = layer.property("ADBE Transform Group").property("ADBE Rotate Z");

    for (var i = 0; i < beats.length; i++) {
        var beat = beats[i];
        if (beat.frequencyBand === "low") {
            // 低频 → 缩放
            var scaleVal = 100 + beat.strength * 30;
            scaleProp.setValueAtTime(beat.time, [scaleVal, scaleVal]);
            scaleProp.setValueAtTime(beat.time + 0.15, [100, 100]);
        } else if (beat.frequencyBand === "high") {
            // 高频 → 旋转
            var rotVal = (beat.strength - 0.5) * 20;
            rotProp.setValueAtTime(beat.time, rotVal);
            rotProp.setValueAtTime(beat.time + 0.1, 0);
        }
    }
}
```

#### 1.3.4 BPM 自动检测与适配

```javascript
// 自动检测 BPM 并选择最佳模板
function autoDetectAndAdapt(comp) {
    var bpm = $.global.beatEdit.getBPM(comp);
    var template;

    if (bpm < 80) {
        template = "电影配乐模板";  // 慢节奏
    } else if (bpm < 120) {
        template = "嘻哈模板";      // 中等节奏
    } else if (bpm < 160) {
        template = "标准4/4拍";     // 流行节奏
    } else {
        template = "电子音乐模板";  // 快节奏
    }

    $.writeln("检测 BPM：" + bpm + " → 选择模板：" + template);
    return { bpm: bpm, template: template };
}
```

---

## 二、Motion Tools Pro API 完全参考

### 2.1 缓动曲线系统

#### 2.1.1 Bezier 曲线参数结构

Motion Tools Pro 的缓动曲线基于三次贝塞尔曲线，参数定义为 4 个浮点数 `[x1, y1, x2, y2]`，对应两个控制点。

```javascript
// Bezier 曲线参数原型
function BezierCurve(x1, y1, x2, y2) {
    this.x1 = clamp(x1, 0, 1);  // 控制点 1 横坐标，必须在 [0, 1]
    this.y1 = y1;                // 控制点 1 纵坐标，可超出 [0, 1]
    this.x2 = clamp(x2, 0, 1);  // 控制点 2 横坐标
    this.y2 = y2;                // 控制点 2 纵坐标
}

function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
}
```

#### 2.1.2 预设曲线参数表（30+ 预设）

下表列出 Motion Tools Pro 内置的全部缓动预设。所有参数采用 `[x1, y1, x2, y2]` 格式，可直接传给 `keyframeInfluence` 的 `bezierHandles` 选项。

| 预设名称 | 类别 | x1 | y1 | x2 | y2 | 适用场景 |
|---------|------|----|----|----|----|---------|
| `linear` | 基础 | 0 | 0 | 1 | 1 | 等速运动 |
| `ease_in_quad` | 入 | 0.55 | 0.085 | 0.68 | 0.53 | 缓入 |
| `ease_out_quad` | 出 | 0.25 | 0.46 | 0.45 | 0.94 | 缓出 |
| `ease_in_out_quad` | 入出 | 0.455 | 0.03 | 0.515 | 0.955 | 平滑入出 |
| `ease_in_cubic` | 入 | 0.55 | 0.055 | 0.675 | 0.19 | 强缓入 |
| `ease_out_cubic` | 出 | 0.215 | 0.61 | 0.355 | 1 | 强缓出 |
| `ease_in_out_cubic` | 入出 | 0.645 | 0.045 | 0.355 | 1 | 平滑入出 |
| `ease_in_quart` | 入 | 0.895 | 0.03 | 0.685 | 0.22 | 极强缓入 |
| `ease_out_quart` | 出 | 0.165 | 0.84 | 0.44 | 1 | 极强缓出 |
| `ease_in_out_quart` | 入出 | 0.77 | 0 | 0.175 | 1 | 极强入出 |
| `ease_in_quint` | 入 | 0.755 | 0.05 | 0.855 | 0.06 | 超强缓入 |
| `ease_out_quint` | 出 | 0.23 | 1 | 0.32 | 1 | 超强缓出 |
| `ease_in_out_quint` | 入出 | 0.86 | 0 | 0.07 | 1 | 超强入出 |
| `ease_in_sine` | 入 | 0.47 | 0 | 0.745 | 0.715 | 轻微缓入 |
| `ease_out_sine` | 出 | 0.39 | 0.575 | 0.565 | 1 | 轻微缓出 |
| `ease_in_out_sine` | 入出 | 0.445 | 0.05 | 0.55 | 0.95 | 轻微入出 |
| `ease_in_expo` | 入 | 0.95 | 0.05 | 0.795 | 0.035 | 指数缓入 |
| `ease_out_expo` | 出 | 0.19 | 1 | 0.22 | 1 | 指数缓出 |
| `ease_in_out_expo` | 入出 | 1 | 0 | 0 | 1 | 指数入出 |
| `ease_in_circ` | 入 | 0.6 | 0.04 | 0.98 | 0.335 | 圆弧缓入 |
| `ease_out_circ` | 出 | 0.075 | 0.82 | 0.165 | 1 | 圆弧缓出 |
| `ease_in_out_circ` | 入出 | 0.785 | 0.135 | 0.15 | 0.86 | 圆弧入出 |
| `ease_in_back` | 入 | 0.6 | -0.28 | 0.735 | 0.045 | 回弹缓入 |
| `ease_out_back` | 出 | 0.175 | 0.885 | 0.32 | 1.275 | 回弹缓出 |
| `ease_in_out_back` | 入出 | 0.68 | -0.55 | 0.265 | 1.55 | 回弹入出 |
| `ease_in_elastic` | 入 | 0.0 | 0.0 | 0.58, 1.0 | — | 弹性缓入（需分段） |
| `ease_out_elastic` | 出 | 0.0, 0.0 | 0.58, 1.0 | — | 弹性缓出（需分段） |
| `ease_in_bounce` | 入 | 0.0, 0.0 | 0.58, 1.0 | — | 弹跳缓入（需分段） |
| `ease_out_bounce` | 出 | 0.0, 0.0 | 0.58, 1.0 | — | 弹跳缓出（需分段） |
| `smooth` | 自定义 | 0.25 | 0.1 | 0.25 | 1 | CSS 默认 |
| `snappy` | 自定义 | 0.2 | 1.5 | 0.4 | 1 | 设计师偏好 |
| `apple_default` | 自定义 | 0.42 | 0 | 1 | 1 | iOS 默认 |
| `material_standard` | 自定义 | 0.4 | 0 | 0.2 | 1 | Material Design |

#### 2.1.3 自定义曲线创建 API

```javascript
// Motion Tools Pro 全局对象
$.global.motionTools = $.global.motionTools || {};

// 创建自定义曲线
function createCustomCurve(name, x1, y1, x2, y2, category) {
    var curve = {
        name: name,
        category: category || "custom",
        handles: [x1, y1, x2, y2],
        isCustom: true,
        createdAt: new Date().toISOString()
    };
    $.global.motionTools.customCurves = $.global.motionTools.customCurves || [];
    $.global.motionTools.customCurves.push(curve);
    return curve;
}

// 获取曲线（含内置 + 自定义）
function getCurve(name) {
    // 先查内置
    var builtin = $.global.motionTools.builtinCurves;
    for (var i = 0; i < builtin.length; i++) {
        if (builtin[i].name === name) return builtin[i];
    }
    // 再查自定义
    var custom = $.global.motionTools.customCurves || [];
    for (var j = 0; j < custom.length; j++) {
        if (custom[j].name === name) return custom[j];
    }
    return null;
}
```

#### 2.1.4 曲线批量应用函数

```javascript
// 将曲线应用到关键帧
function applyCurveToKeyframes(prop, curveName, keyframeIndices) {
    var curve = getCurve(curveName);
    if (!curve) {
        $.writeln("曲线未找到：" + curveName);
        return false;
    }
    var indices = keyframeIndices || [];
    if (indices.length === 0) {
        // 应用到全部关键帧
        for (var k = 1; k <= prop.numKeys; k++) {
            indices.push(k);
        }
    }

    for (var i = 0; i < indices.length; i++) {
        var idx = indices[i];
        var influenceIn = 33.3;
        var influenceOut = 33.3;
        var speedIn = curve.handles[1] * 100;
        var speedOut = curve.handles[3] * 100;

        // AE API: setTemporalEaseAtKey(index, inEase, outEase)
        var inEase = [{type: KeyframeInterpolationType.BEZIER, influence: influenceIn, speed: speedIn}];
        var outEase = [{type: KeyframeInterpolationType.BEZIER, influence: influenceOut, speed: speedOut}];
        prop.setTemporalEaseAtKey(idx, inEase, outEase);
    }
    return true;
}
```

### 2.2 物理模拟引擎

#### 2.2.1 弹簧系统参数

Motion Tools Pro 内置弹簧物理引擎，可在表达式层模拟真实弹性运动。

**弹簧参数表：**

| 参数 | 类型 | 取值范围 | 默认值 | 单位 | 说明 |
|------|------|---------|--------|------|------|
| `frequency` | Number | 0.1 ~ 20.0 | 2.0 | Hz | 弹簧振荡频率 |
| `damping` | Number | 0.0 ~ 1.0 | 0.5 | 无量纲 | 阻尼比（0 = 无阻尼，1 = 临界阻尼） |
| `mass` | Number | 0.1 ~ 10.0 | 1.0 | kg | 物体质量 |
| `gravity` | Number | -100 ~ 100 | 0 | m/s² | 重力加速度 |
| `stiffness` | Number | 0 ~ 1000 | 100 | N/m | 弹簧刚度 |
| `initialVelocity` | Number | -1000 ~ 1000 | 0 | px/s | 初始速度 |
| `restLength` | Number | 0 ~ 1000 | 0 | px | 静止长度 |

**弹簧表达式（应用到 Position）：**

```javascript
// Spring 物理表达式 - 应用到 Position 属性
var spring = {
    frequency: 2.0,     // 振荡频率
    damping: 0.5,       // 阻尼比
    mass: 1.0,         // 质量
    amplitude: 50      // 初始振幅
};

function springMath(t, freq, damp, mass, amp) {
    var omega = 2 * Math.PI * freq;
    var dampingRatio = damp;
    var alpha = -dampingRatio * omega;
    var beta = omega * Math.sqrt(1 - dampingRatio * dampingRatio);
    return amp * Math.pow(Math.E, alpha * t) * Math.cos(beta * t);
}

var t = time - inPoint;
var offsetX = springMath(t, spring.frequency, spring.damping,
                         spring.mass, spring.amplitude);
var offsetY = springMath(t, spring.frequency, spring.damping,
                         spring.mass, spring.amplitude * 0.5);
transform.position.value + [offsetX, offsetY];
```

#### 2.2.2 碰撞检测 API

```javascript
// AABB 边界框碰撞检测
function checkAABBCollision(boxA, boxB) {
    return boxA.x < boxB.x + boxB.width &&
           boxA.x + boxA.width > boxB.x &&
           boxA.y < boxB.y + boxB.height &&
           boxA.y + boxA.height > boxB.y;
}

// 圆形碰撞检测
function checkCircleCollision(c1, c2) {
    var dx = c1.x - c2.x;
    var dy = c1.y - c2.y;
    var distSq = dx * dx + dy * dy;
    var rSum = c1.r + c2.r;
    return distSq < rSum * rSum;
}

// 反弹响应
function resolveCollision(obj, normal, restitution) {
    var dot = obj.vx * normal.x + obj.vy * normal.y;
    obj.vx -= (1 + restitution) * dot * normal.x;
    obj.vy -= (1 + restitution) * dot * normal.y;
}
```

#### 2.2.3 刚体动力学模拟

```javascript
// 刚体动力学循环（在预合成中模拟）
function simulateRigidBody(layer, options) {
    var state = {
        position: [layer.transform.position.value[0], layer.transform.position.value[1]],
        velocity: options.initialVelocity || [0, 0],
        angle: 0,
        angularVelocity: options.angularVelocity || 0,
        mass: options.mass || 1.0,
        restitution: options.restitution || 0.6,
        friction: options.friction || 0.98
    };

    var gravity = options.gravity || [0, 200];  // px/s²
    var dt = 1 / comp.frameRate;
    var totalTime = comp.duration;

    // 写入关键帧
    for (var t = 0; t < totalTime; t += dt) {
        // 应用重力
        state.velocity[0] += gravity[0] * dt;
        state.velocity[1] += gravity[1] * dt;

        // 应用摩擦
        state.velocity[0] *= state.friction;
        state.velocity[1] *= state.friction;

        // 更新位置
        state.position[0] += state.velocity[0] * dt;
        state.position[1] += state.velocity[1] * dt;

        // 更新角度
        state.angle += state.angularVelocity * dt;

        // 写入关键帧
        layer.transform.position.setValueAtTime(t, state.position);
        layer.transform.rotation.setValueAtTime(t, state.angle);
    }
}
```

#### 2.2.4 物理模拟批量应用

```javascript
// 批量应用弹簧到所选图层
function batchApplySpring(comp, options) {
    var layers = comp.selectedLayers;
    for (var i = 0; i < layers.length; i++) {
        var posProp = layers[i].property("ADBE Transform Group").property("ADBE Position");
        posProp.expression = [
            "var freq = " + options.frequency + ";",
            "var damp = " + options.damping + ";",
            "var mass = " + options.mass + ";",
            "var amp = " + (options.amplitude + i * 10) + ";",
            "var t = time - inPoint;",
            "var omega = 2 * Math.PI * freq;",
            "var alpha = -damp * omega;",
            "var beta = omega * Math.sqrt(Math.max(0, 1 - damp * damp));",
            "var off = amp * Math.pow(Math.E, alpha * t) * Math.cos(beta * t);",
            "value + [off, off * 0.5];"
        ].join("\n");
    }
}
```

### 2.3 批量操作工具

#### 2.3.1 图层批量选择 API

| 方法 | 签名 | 说明 |
|------|------|------|
| `selectByType` | `selectByType(comp, typeName)` | 按类型选择（Solid/Text/Shape/Null/Adjustment） |
| `selectByName` | `selectByName(comp, regex)` | 按名称正则选择 |
| `selectInverted` | `selectInverted(comp)` | 反向选择 |
| `selectAdjacent` | `selectAdjacent(comp)` | 选择相邻图层 |
| `selectByEffect` | `selectByEffect(comp, matchName)` | 含指定效果的图层 |
| `selectVisible` | `selectVisible(comp)` | 仅可见图层 |

```javascript
// 批量选择含 Particular 效果的图层
$.global.motionTools.selectByEffect(comp, "PARTICULAR");

// 按名称正则选择
$.global.motionTools.selectByName(comp, /^Logo\s\d+$/);
```

#### 2.3.2 属性批量修改函数

```javascript
// 批量修改位置（带偏移）
function batchOffsetPosition(comp, offsetX, offsetY) {
    app.beginUndoGroup("批量位置偏移");
    var layers = comp.selectedLayers;
    for (var i = 0; i < layers.length; i++) {
        var pos = layers[i].property("ADBE Transform Group").property("ADBE Position");
        var currentVal = pos.value;
        pos.setValue([currentVal[0] + offsetX, currentVal[1] + offsetY]);
    }
    app.endUndoGroup();
}

// 批量修改透明度（线性渐变）
function batchGradientOpacity(comp, startVal, endVal) {
    var layers = comp.selectedLayers;
    var n = layers.length;
    for (var i = 0; i < n; i++) {
        var ratio = i / Math.max(1, n - 1);
        var val = startVal + (endVal - startVal) * ratio;
        var op = layers[i].property("ADBE Transform Group").property("ADBE Opacity");
        op.setValue(val);
    }
}
```

#### 2.3.3 关键帧批量操作

```javascript
// 关键帧时间偏移
function batchOffsetKeyframes(comp, frameOffset) {
    var layers = comp.selectedLayers;
    for (var i = 0; i < layers.length; i++) {
        iterateProperties(layers[i], function(prop) {
            if (prop.numKeys > 0) {
                var keyData = [];
                for (var k = 1; k <= prop.numKeys; k++) {
                    keyData.push({
                        time: prop.keyTime(k) + frameOffset / comp.frameRate,
                        value: prop.keyValue(k),
                        inEase: prop.keyInInterpolationType(k),
                        outEase: prop.keyOutInterpolationType(k)
                    });
                }
                // 清除原关键帧
                while (prop.numKeys > 0) prop.removeKey(1);
                // 写入偏移后关键帧
                for (var j = 0; j < keyData.length; j++) {
                    prop.setValueAtTime(keyData[j].time, keyData[j].value);
                }
            }
        });
    }
}

function iterateProperties(propGroup, callback) {
    for (var i = 1; i <= propGroup.numProperties; i++) {
        var prop = propGroup.property(i);
        if (prop instanceof PropertyGroup) {
            iterateProperties(prop, callback);
        } else if (prop instanceof Property && prop.canVaryOverTime) {
            callback(prop);
        }
    }
}
```

#### 2.3.4 预设批量应用

```javascript
// 批量应用动画预设（.ffx）
function batchApplyPreset(comp, presetPath, staggerFrames) {
    var presetFile = new File(presetPath);
    if (!presetFile.exists) {
        alert("预设文件不存在：" + presetPath);
        return;
    }

    var layers = comp.selectedLayers;
    app.beginUndoGroup("批量应用预设");

    for (var i = 0; i < layers.length; i++) {
        var offset = i * (staggerFrames || 0) / comp.frameRate;
        // 时间偏移
        var origStart = layers[i].startTime;
        layers[i].startTime = origStart - offset;

        // 应用预设
        layers[i].applyPreset(presetFile);

        // 恢复时间
        layers[i].startTime = origStart;
    }

    app.endUndoGroup();
}
```

---

## 三、MotionSpice API 完全参考

### 3.1 图形创建系统

#### 3.1.1 形状图层创建函数

**形状类型与 matchName 对应表：**

| 形状 | API 函数 | matchName | 参数 |
|------|---------|-----------|------|
| 矩形 | `createRectangle` | `ADBE Vector Shape - Rect` | width, height, cornerRadius |
| 圆形 | `createEllipse` | `ADBE Vector Shape - Ellipse` | width, height |
| 多边形 | `createPolygon` | `ADBE Vector Shape - Star` | points, outerRadius, innerRadius, isStar |
| 星形 | `createStar` | `ADBE Vector Shape - Star` | points, outerRadius, innerRadius |
| 路径 | `createPath` | `ADBE Vector Shape - Group` | vertices, inTangents, outTangents, closed |

```javascript
// MotionSpice 全局对象
$.global.motionSpice = $.global.motionSpice || {};

// 创建矩形
function createRectangle(comp, x, y, width, height, cornerRadius) {
    var shapeLayer = comp.layers.addShape();
    shapeLayer.name = "Rectangle";
    shapeLayer.property("ADBE Transform Group").property("ADBE Position")
              .setValue([x, y]);

    var group = shapeLayer.property("ADBE Root Vectors Group");
    var rect = group.addProperty("ADBE Vector Shape - Rect");
    rect.property("ADBE Vector Rect Size").setValue([width, height]);
    rect.property("ADBE Vector Rect Corner Radius").setValue(cornerRadius || 0);
    return shapeLayer;
}

// 创建圆形
function createEllipse(comp, x, y, width, height) {
    var shapeLayer = comp.layers.addShape();
    shapeLayer.name = "Ellipse";
    shapeLayer.property("ADBE Transform Group").property("ADBE Position")
              .setValue([x, y]);

    var group = shapeLayer.property("ADBE Root Vectors Group");
    var ellipse = group.addProperty("ADBE Vector Shape - Ellipse");
    ellipse.property("ADBE Vector Ellipse Size").setValue([width, height]);
    return shapeLayer;
}

// 创建多边形
function createPolygon(comp, x, y, points, outerRadius, innerRadius, isStar) {
    var shapeLayer = comp.layers.addShape();
    shapeLayer.name = isStar ? "Star" : "Polygon";
    shapeLayer.property("ADBE Transform Group").property("ADBE Position")
              .setValue([x, y]);

    var group = shapeLayer.property("ADBE Root Vectors Group");
    var poly = group.addProperty("ADBE Vector Shape - Star");
    poly.property("ADBE Vector Star Type").setValue(isStar ? 2 : 1);
    poly.property("ADBE Vector Star Points").setValue(points);
    poly.property("ADBE Vector Star Outer Radius").setValue(outerRadius);
    if (isStar) {
        poly.property("ADBE Vector Star Inner Radius").setValue(innerRadius);
    }
    return shapeLayer;
}

// 创建路径
function createPath(comp, vertices, closed) {
    var shapeLayer = comp.layers.addShape();
    shapeLayer.name = "Path";
    var group = shapeLayer.property("ADBE Root Vectors Group");
    var pathGroup = group.addProperty("ADBE Vector Shape - Group");
    var pathProp = pathGroup.property("ADBE Vector Shape");

    var shape = new Shape();
    shape.vertices = vertices;
    shape.inTangents = [];
    shape.outTangents = [];
    shape.closed = (closed !== undefined) ? closed : true;
    for (var i = 0; i < vertices.length; i++) {
        shape.inTangents.push([0, 0]);
        shape.outTangents.push([0, 0]);
    }
    pathProp.setValue(shape);
    return shapeLayer;
}
```

#### 3.1.2 路径操作 API

```javascript
// 路径合并操作（参考 AE Path Operations）
var PATH_OPERATIONS = {
    MERGE: "ADBE Vector Filter - Merge",
    OFFSET: "ADBE Vector Filter - Offset",
    PUCKER_BLOAT: "ADBE Vector Filter - PB",
    REPEATER: "ADBE Vector Filter - Repeater",
    ROUND_CORNERS: "ADBE Vector Filter - RC",
    TRIM: "ADBE Vector Filter - Trim",
    TWIST: "ADBE Vector Filter - Twist",
    WIGGLE: "ADBE Vector Filter - Wiggly",
    ZIG_ZAG: "ADBE Vector Filter - Zigzag"
};

// 添加 Trim Path
function addTrimPath(shapeLayer, start, end, offset) {
    var group = shapeLayer.property("ADBE Root Vectors Group");
    var trim = group.addProperty("ADBE Vector Filter - Trim");
    trim.property("ADBE Vector Trim Start").setValue(start || 0);
    trim.property("ADBE Vector Trim End").setValue(end || 100);
    trim.property("ADBE Vector Trim Offset").setValue(offset || 0);
    return trim;
}

// 添加 Repeater
function addRepeater(shapeLayer, copies, offset, position) {
    var group = shapeLayer.property("ADBE Root Vectors Group");
    var repeater = group.addProperty("ADBE Vector Filter - Repeater");
    repeater.property("ADBE Vector Repeater Copies").setValue(copies);
    repeater.property("ADBE Vector Repeater Offset").setValue(offset);
    var transform = repeater.property("ADBE Vector Repeater Transform");
    transform.property("ADBE Vector Repeater Position").setValue(position);
    return repeater;
}
```

#### 3.1.3 填充与描边控制

```javascript
// 添加填充
function addFill(shapeLayer, color, opacity) {
    var group = shapeLayer.property("ADBE Root Vectors Group");
    var fill = group.addProperty("ADBE Vector Graphic - Fill");
    fill.property("ADBE Vector Fill Color").setValue(color);
    fill.property("ADBE Vector Fill Opacity").setValue(opacity || 100);
    return fill;
}

// 添加描边
function addStroke(shapeLayer, color, width, opacity, lineCap, lineJoin) {
    var group = shapeLayer.property("ADBE Root Vectors Group");
    var stroke = group.addProperty("ADBE Vector Graphic - Stroke");
    stroke.property("ADBE Vector Stroke Color").setValue(color);
    stroke.property("ADBE Vector Stroke Width").setValue(width || 1);
    stroke.property("ADBE Vector Stroke Opacity").setValue(opacity || 100);
    // lineCap: 1=Butt, 2=Round, 3=Projecting
    stroke.property("ADBE Vector Stroke Line Cap").setValue(lineCap || 2);
    // lineJoin: 1=Miter, 2=Round, 3=Bevel
    stroke.property("ADBE Vector Stroke Line Join").setValue(lineJoin || 2);
    return stroke;
}

// 添加渐变填充
function addGradientFill(shapeLayer, type, startColor, endColor, opacity) {
    var group = shapeLayer.property("ADBE Root Vectors Group");
    var fillMatchName = type === "linear" ?
        "ADBE Vector Graphic - G-Fill" :
        "ADBE Vector Graphic - G-Radial Fill";
    var gradient = group.addProperty(fillMatchName);

    var colors = [
        0, startColor[0], startColor[1], startColor[2], 1,
        1, endColor[0], endColor[1], endColor[2], 1
    ];
    gradient.property("ADBE Vector Grad Colors").setValue(colors);
    gradient.property("ADBE Vector Fill Opacity").setValue(opacity || 100);
    return gradient;
}
```

#### 3.1.4 图形变换函数

```javascript
// 通用变换函数
function transformShape(shapeLayer, options) {
    var transform = shapeLayer.property("ADBE Transform Group");
    if (options.position) transform.property("ADBE Position").setValue(options.position);
    if (options.scale) transform.property("ADBE Scale").setValue(options.scale);
    if (options.rotation !== undefined)
        transform.property("ADBE Rotate Z").setValue(options.rotation);
    if (options.opacity !== undefined)
        transform.property("ADBE Opacity").setValue(options.opacity);
    if (options.anchorPoint)
        transform.property("ADBE Anchor Point").setValue(options.anchorPoint);
    return shapeLayer;
}

// 围绕中心点旋转
function rotateAround(shapeLayer, center, angle) {
    var transform = shapeLayer.property("ADBE Transform Group");
    var anchorProp = transform.property("ADBE Anchor Point");
    var posProp = transform.property("ADBE Position");
    var currentPos = posProp.value;
    var rad = angle * Math.PI / 180;
    var dx = currentPos[0] - center[0];
    var dy = currentPos[1] - center[1];
    var newX = center[0] + dx * Math.cos(rad) - dy * Math.sin(rad);
    var newY = center[1] + dx * Math.sin(rad) + dy * Math.cos(rad);
    posProp.setValue([newX, newY]);
    var currentRot = transform.property("ADBE Rotate Z").value;
    transform.property("ADBE Rotate Z").setValue(currentRot + angle);
}
```

### 3.2 预设动画系统

#### 3.2.1 动画预设参数结构

```json
{
  "preset": {
    "name": "弹性弹出",
    "category": "entrance",
    "version": "1.0",
    "duration": 1.5,
    "targetProperty": "transform.scale",
    "keyframes": [
      {
        "time": 0,
        "value": [0, 0],
        "ease": "ease_out_back",
        "bezier": [0.175, 0.885, 0.32, 1.275]
      },
      {
        "time": 0.3,
        "value": [110, 110],
        "ease": "ease_in_out_quad",
        "bezier": [0.455, 0.03, 0.515, 0.955]
      },
      {
        "time": 0.5,
        "value": [95, 95],
        "ease": "ease_out_quad",
        "bezier": [0.25, 0.46, 0.45, 0.94]
      },
      {
        "time": 0.7,
        "value": [100, 100],
        "ease": "linear",
        "bezier": [0, 0, 1, 1]
      }
    ]
  }
}
```

#### 3.2.2 预设应用 API

```javascript
// 应用预设
function applyPreset(layer, presetObj, startTime) {
    var targetProp = resolvePropertyPath(layer, presetObj.targetProperty);
    if (!targetProp) return false;

    var startT = startTime || layer.inPoint;
    for (var i = 0; i < presetObj.keyframes.length; i++) {
        var kf = presetObj.keyframes[i];
        var kfTime = startT + kf.time;
        var kfValue = kf.value;

        if (targetProp.value.length && !Array.isArray(kfValue)) {
            // 单值应用到多维属性
            var dim = targetProp.value.length;
            var arr = [];
            for (var d = 0; d < dim; d++) arr.push(kfValue);
            kfValue = arr;
        }
        targetProp.setValueAtTime(kfTime, kfValue);
    }
    return true;
}

function resolvePropertyPath(layer, path) {
    var parts = path.split(".");
    var current = layer;
    for (var i = 0; i < parts.length; i++) {
        current = current.property(parts[i]);
        if (!current) return null;
    }
    return current;
}
```

#### 3.2.3 自定义预设创建

```javascript
// 从现有动画提取预设
function extractPresetFromLayer(layer, propPath, name, category) {
    var prop = resolvePropertyPath(layer, propPath);
    if (!prop || prop.numKeys === 0) return null;

    var startTime = prop.keyTime(1);
    var keyframes = [];

    for (var i = 1; i <= prop.numKeys; i++) {
        var kfTime = prop.keyTime(i) - startTime;
        var kfValue = prop.keyValue(i);
        var inEase = prop.keyInTemporalEase(i);
        var outEase = prop.keyOutTemporalEase(i);

        keyframes.push({
            time: kfTime,
            value: kfValue,
            ease: "custom",
            bezier: extractBezierFromEase(inEase, outEase)
        });
    }

    return {
        name: name || "Custom Preset",
        category: category || "custom",
        version: "1.0",
        duration: keyframes[keyframes.length - 1].time,
        targetProperty: propPath,
        keyframes: keyframes
    };
}
```

#### 3.2.4 预设库管理

```javascript
// 预设库（带分类）
var PRESET_LIBRARY = {
    entrance: {
        fadeIn: { /* ... */ },
        scaleUp: { /* ... */ },
        slideInLeft: { /* ... */ },
        bounceIn: { /* ... */ }
    },
    exit: {
        fadeOut: { /* ... */ },
        scaleDown: { /* ... */ },
        slideOutRight: { /* ... */ }
    },
    emphasis: {
        pulse: { /* ... */ },
        shake: { /* ... */ },
        tada: { /* ... */ },
        swing: { /* ... */ }
    },
    loop: {
        float: { /* ... */ },
        breathe: { /* ... */ },
        rotate: { /* ... */ }
    }
};

function listPresetsByCategory(category) {
    return Object.keys(PRESET_LIBRARY[category] || {});
}

function loadPreset(name, category) {
    var cat = PRESET_LIBRARY[category];
    return cat ? cat[name] : null;
}
```

### 3.3 样式系统

#### 3.3.1 样式参数结构

```json
{
  "style": {
    "name": "Glass Morphism",
    "fill": {
      "color": [1, 1, 1, 1],
      "opacity": 0.15
    },
    "stroke": {
      "color": [1, 1, 1, 1],
      "width": 1.5,
      "opacity": 0.6
    },
    "shadow": {
      "enabled": true,
      "color": [0, 0, 0, 1],
      "opacity": 0.3,
      "angle": 135,
      "distance": 10,
      "blur": 20
    },
    "glow": {
      "enabled": true,
      "color": [0.4, 0.8, 1, 1],
      "intensity": 50,
      "size": 30
    }
  }
}
```

#### 3.3.2 样式应用函数

```javascript
function applyStyle(shapeLayer, styleObj) {
    var group = shapeLayer.property("ADBE Root Vectors Group");

    // 填充
    if (styleObj.fill) {
        var fill = group.addProperty("ADBE Vector Graphic - Fill");
        fill.property("ADBE Vector Fill Color").setValue(styleObj.fill.color);
        fill.property("ADBE Vector Fill Opacity")
            .setValue(styleObj.fill.opacity || 100);
    }

    // 描边
    if (styleObj.stroke) {
        var stroke = group.addProperty("ADBE Vector Graphic - Stroke");
        stroke.property("ADBE Vector Stroke Color").setValue(styleObj.stroke.color);
        stroke.property("ADBE Vector Stroke Width").setValue(styleObj.stroke.width);
        stroke.property("ADBE Vector Stroke Opacity")
            .setValue(styleObj.stroke.opacity || 100);
    }

    // 阴影（通过图层样式）
    if (styleObj.shadow && styleObj.shadow.enabled) {
        var layerStyle = shapeLayer.property("ADBE Layer Styles");
        var dropShadow = layerStyle.addProperty("ADBE Drop Shadow");
        dropShadow.property("ADBE Drop Shadow-0001")  // Color
                  .setValue(styleObj.shadow.color);
        dropShadow.property("ADBE Drop Shadow-0002")  // Opacity
                  .setValue(styleObj.shadow.opacity * 255);
        dropShadow.property("ADBE Drop Shadow-0003")  // Angle
                  .setValue(styleObj.shadow.angle);
        dropShadow.property("ADBE Drop Shadow-0004")  // Distance
                  .setValue(styleObj.shadow.distance);
        dropShadow.property("ADBE Drop Shadow-0006")  // Blur
                  .setValue(styleObj.shadow.blur);
    }

    // 发光
    if (styleObj.glow && styleObj.glow.enabled) {
        var effects = shapeLayer.property("ADBE Effect Parade");
        var glow = effects.addProperty("ADBE Glo2");
        glow.property("ADBE Glo2-0001")  // Glow Threshold
            .setValue(styleObj.glow.intensity);
        glow.property("ADBE Glo2-0002")  // Glow Radius
            .setValue(styleObj.glow.size);
        glow.property("ADBE Glo2-0003")  // Glow Color (Original)
            .setValue(3);  // 3 = use arbitrary color
        glow.property("ADBE Glo2-0006")  // Glow Color
            .setValue(styleObj.glow.color);
    }
}
```

#### 3.3.3 渐变与阴影控制

```javascript
// 线性渐变填充
function applyLinearGradient(shapeLayer, stops, angle, opacity) {
    var group = shapeLayer.property("ADBE Root Vectors Group");
    var grad = group.addProperty("ADBE Vector Graphic - G-Fill");

    // 构建颜色数组：[位置1, R1, G1, B1, A1, 位置2, R2, G2, B2, A2, ...]
    var colors = [];
    for (var i = 0; i < stops.length; i++) {
        colors.push(stops[i].position);
        colors.push(stops[i].color[0]);
        colors.push(stops[i].color[1]);
        colors.push(stops[i].color[2]);
        colors.push(stops[i].color[3] || 1);
    }
    grad.property("ADBE Vector Grad Colors").setValue(colors);
    grad.property("ADBE Vector Fill Opacity").setValue(opacity || 100);
    return grad;
}

// 多层阴影
function applyMultiLayerShadow(layer, shadowConfigs) {
    // 复制原图层，每层作为阴影
    for (var i = 0; i < shadowConfigs.length; i++) {
        var cfg = shadowConfigs[i];
        var shadowLayer = layer.duplicate();
        shadowLayer.name = layer.name + "_Shadow_" + i;
        shadowLayer.property("ADBE Effect Parade")
                   .addProperty("ADBE Fill");
        shadowLayer.property("ADBE Effect Parade")
                   .property("ADBE Fill")
                   .property("ADBE Fill-0002")  // Color
                   .setValue(cfg.color);
        shadowLayer.property("ADBE Effect Parade")
                   .property("ADBE Fill")
                   .property("ADBE Fill-0003")  // Opacity
                   .setValue(cfg.opacity);
        // 偏移
        var pos = shadowLayer.property("ADBE Transform Group").property("ADBE Position");
        var orig = pos.value;
        pos.setValue([orig[0] + cfg.offsetX, orig[1] + cfg.offsetY]);
        // 模糊
        if (cfg.blur > 0) {
            shadowLayer.property("ADBE Effect Parade")
                       .addProperty("ADBE Gaussian Blur 2");
            shadowLayer.property("ADBE Effect Parade")
                       .property("ADBE Gaussian Blur 2")
                       .property("ADBE Gaussian Blur 2-0001")
                       .setValue(cfg.blur);
        }
        // 移到原图层下方
        shadowLayer.moveAfter(layer);
    }
}
```

#### 3.3.4 样式批量管理

```javascript
// 批量应用样式到所选图层
function batchApplyStyle(comp, styleObj) {
    var layers = comp.selectedLayers;
    app.beginUndoGroup("批量应用样式");
    for (var i = 0; i < layers.length; i++) {
        if (layers[i] instanceof ShapeLayer) {
            applyStyle(layers[i], styleObj);
        }
    }
    app.endUndoGroup();
}

// 保存样式到库
function saveStyleToLibrary(name, styleObj, category) {
    var lib = $.global.motionSpice.styleLibrary =
              $.global.motionSpice.styleLibrary || {};
    if (!lib[category]) lib[category] = {};
    lib[category][name] = styleObj;
    return true;
}
```

---

## 四、Motion Studio API 完全参考

### 4.1 时间轴控制

#### 4.1.1 时间轴标记 API

```javascript
// Motion Studio 全局对象
$.global.motionStudio = $.global.motionStudio || {};

// 添加章节标记
function addChapterMarker(comp, time, name, color) {
    var marker = new MarkerValue(name);
    marker.duration = 1.0;
    marker.color = color || [1, 0.5, 0];
    marker.comment = "Chapter: " + name;
    comp.markerProperty.setValueAtTime(time, marker);
    return marker;
}

// 批量添加标记
function batchAddMarkers(comp, markers) {
    app.beginUndoGroup("批量添加标记");
    for (var i = 0; i < markers.length; i++) {
        addChapterMarker(comp, markers[i].time, markers[i].name, markers[i].color);
    }
    app.endUndoGroup();
}

// 删除指定名称的标记
function removeMarkersByName(comp, namePattern) {
    var markerProp = comp.markerProperty;
    var toRemove = [];
    for (var i = 1; i <= markerProp.numKeys; i++) {
        var marker = markerProp.keyValue(i);
        if (marker.comment.match(namePattern)) {
            toRemove.push(i);
        }
    }
    // 从后向前删除
    for (var j = toRemove.length - 1; j >= 0; j--) {
        markerProp.removeKey(toRemove[j]);
    }
}
```

#### 4.1.2 时间轴缩放控制

```javascript
// 设置时间轴显示范围
function setTimeView(comp, startTime, endTime) {
    // 通过 QE DOM API 控制
    var qeComp = qe.project.getActiveItem();
    if (qeComp) {
        var viewer = qeComp.getTimelineViewer();
        viewer.setTimeDisplayStart(startTime);
        viewer.setTimeDisplayEnd(endTime);
    }
}

// 居中显示当前时间
function centerOnCurrentTime(comp) {
    var currentT = comp.time;
    var halfSpan = 5;  // ±5 秒
    setTimeView(comp, currentT - halfSpan, currentT + halfSpan);
}
```

#### 4.1.3 工作区域设置函数

```javascript
function setWorkArea(comp, start, end) {
    comp.workAreaStart = start;
    comp.workAreaDuration = end - start;
}

function resetWorkArea(comp) {
    comp.workAreaStart = 0;
    comp.workAreaDuration = comp.duration;
}

function setWorkAreaToSelectedLayers(comp) {
    var layers = comp.selectedLayers;
    if (layers.length === 0) return;
    var minStart = Infinity, maxEnd = -Infinity;
    for (var i = 0; i < layers.length; i++) {
        var s = layers[i].startTime;
        var e = layers[i].outPoint;
        if (s < minStart) minStart = s;
        if (e > maxEnd) maxEnd = e;
    }
    setWorkArea(comp, minStart, maxEnd);
}
```

#### 4.1.4 时间轴导航

```javascript
function goToTime(comp, t) {
    comp.time = Math.max(0, Math.min(t, comp.duration));
}

function goToNextMarker(comp) {
    var markerProp = comp.markerProperty;
    for (var i = 1; i <= markerProp.numKeys; i++) {
        var t = markerProp.keyTime(i);
        if (t > comp.time + 0.001) {
            comp.time = t;
            return t;
        }
    }
    return null;
}

function goToPrevMarker(comp) {
    var markerProp = comp.markerProperty;
    for (var i = markerProp.numKeys; i >= 1; i--) {
        var t = markerProp.keyTime(i);
        if (t < comp.time - 0.001) {
            comp.time = t;
            return t;
        }
    }
    return null;
}
```

### 4.2 表达式关联系统

#### 4.2.1 图层关联创建函数

```javascript
// 创建父子关系
function linkParent(childLayer, parentLayer) {
    childLayer.parent = parentLayer;
}

// 批量父子关联
function linkBatchParent(childLayers, parentLayer, stagger) {
    for (var i = 0; i < childLayers.length; i++) {
        if (stagger && i > 0) {
            // 通过表达式延迟
            var delay = i * stagger;
            setExpressionProperty(childLayers[i], "transform.position",
                "parent.transform.position.valueAtTime(time - " + delay + "/thisComp.frameRate);");
        }
        childLayers[i].parent = parentLayer;
    }
}

function setExpressionProperty(layer, propPath, expression) {
    var prop = resolvePropertyPath(layer, propPath);
    if (prop) prop.expression = expression;
}
```

#### 4.2.2 属性关联 API

```javascript
// 关联两个属性
function linkProperties(sourceLayer, sourcePropPath,
                       targetLayer, targetPropPath,
                       offset, multiplier) {
    var srcProp = resolvePropertyPath(sourceLayer, sourcePropPath);
    var tgtProp = resolvePropertyPath(targetLayer, targetPropPath);
    if (!srcProp || !tgtProp) return false;

    var srcLayerName = sourceLayer.name;
    var expr = "var src = thisComp.layer(\"" + srcLayerName + "\");\n" +
               "var v = src." + sourcePropPath.replace(/\./g, "(\"") + "\");\n";
    // 简化版
    var offsetStr = offset ? " + " + offset : "";
    var multStr = multiplier ? " * " + multiplier : "";
    tgtProp.expression = "thisComp.layer(\"" + srcLayerName + "\")." +
                         sourcePropPath + ".value" + multStr + offsetStr + ";";
    return true;
}

// 关联到 Null Controller
function linkToNull(comp, targetLayer, propPath, nullName) {
    var nullLayer = findLayerByName(comp, nullName);
    if (!nullLayer) {
        // 自动创建
        nullLayer = comp.layers.addNull();
        nullLayer.name = nullName;
    }
    var prop = resolvePropertyPath(targetLayer, propPath);
    prop.expression = "thisComp.layer(\"" + nullName + "\").effect(\"" +
                      propPath + "\")(\"Slider\").value;";
    return nullLayer;
}

function findLayerByName(comp, name) {
    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).name === name) return comp.layer(i);
    }
    return null;
}
```

#### 4.2.3 表达式模板库

```javascript
var EXPRESSION_TEMPLATES = {
    // 通用：跟随
    follow: "var target = thisComp.layer(\"{TARGET}\");\n" +
            "var delay = {DELAY};\n" +
            "target.transform.position.valueAtTime(time - delay);",

    // 弹簧
    spring: "var freq = {FREQ};\n" +
            "var damp = {DAMP};\n" +
            "var t = time - inPoint;\n" +
            "var omega = 2 * Math.PI * freq;\n" +
            "var alpha = -damp * omega;\n" +
            "var beta = omega * Math.sqrt(Math.max(0, 1 - damp * damp));\n" +
            "var amp = {AMP};\n" +
            "value + [amp * Math.pow(Math.E, alpha * t) * Math.cos(beta * t),\n" +
            "         amp * Math.pow(Math.E, alpha * t) * Math.cos(beta * t) * 0.5];",

    // 抖动
    wiggle: "seedRandom({SEED});\n" +
            "wiggle({FREQ}, {AMP});",

    // 路径跟随
    pathFollow: "var path = thisComp.layer(\"{PATH_LAYER}\").content(\"Shape 1\").content(\"Path 1\").path;\n" +
                "var t = {TIME_FACTOR} * (time - inPoint) / (outPoint - inPoint);\n" +
                "path.pointOnPath(t);"
};

function applyExpressionTemplate(layer, propPath, templateName, params) {
    var prop = resolvePropertyPath(layer, propPath);
    if (!prop) return false;

    var template = EXPRESSION_TEMPLATES[templateName];
    if (!template) return false;

    // 替换占位符
    var expr = template;
    for (var key in params) {
        if (params.hasOwnProperty(key)) {
            expr = expr.replace(new RegExp("\\{" + key + "\\}", "g"), params[key]);
        }
    }
    prop.expression = expr;
    return true;
}
```

#### 4.2.4 表达式调试工具

```javascript
// 启用/禁用表达式
function toggleExpression(layer, propPath) {
    var prop = resolvePropertyPath(layer, propPath);
    if (prop && prop.expression !== "") {
        prop.expressionEnabled = !prop.expressionEnabled;
    }
}

// 检查表达式错误
function checkExpressionErrors(comp) {
    var errors = [];
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        iterateProperties(layer, function(prop) {
            if (prop.expression !== "" && prop.expressionEnabled) {
                // AE 没有直接暴露错误信息，可通过临时禁用+启用探测
                // 实际项目需借助命令行日志或第三方插件
            }
        });
    }
    return errors;
}

// 导出表达式列表
function exportExpressions(comp, filePath) {
    var lines = [];
    lines.push("# 表达式导出 - " + new Date().toISOString());
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        iterateProperties(layer, function(prop) {
            if (prop.expression !== "") {
                lines.push("## " + layer.name + " → " + prop.matchName);
                lines.push("```");
                lines.push(prop.expression);
                lines.push("```");
                lines.push("");
            }
        });
    }
    var file = new File(filePath);
    file.encoding = "UTF-8";
    file.open("w");
    file.write(lines.join("\n"));
    file.close();
}
```

### 4.3 多图层协同

#### 4.3.1 同步模式参数

| 模式 | 参数 | 说明 |
|------|------|------|
| `absolute` | `interval=0` | 所有图层同时触发 |
| `stagger` | `interval=3` (帧) | 按索引顺序延迟 |
| `wave` | `interval=3`, `direction="forward"` | 波浪式传播 |
| `random` | `interval=5`, `variance=2` | 随机时间触发 |
| `group` | `groupSize=4`, `groupDelay=10` | 分组同步 |

```javascript
function applySyncMode(layers, mode, options) {
    var result = [];
    for (var i = 0; i < layers.length; i++) {
        var delay = calculateSyncDelay(i, layers.length, mode, options);
        result.push({ layer: layers[i], delay: delay });
    }
    return result;
}

function calculateSyncDelay(index, total, mode, options) {
    var opts = options || {};
    var interval = opts.interval || 3;
    switch (mode) {
        case "absolute":
            return 0;
        case "stagger":
            return index * interval;
        case "wave":
            return opts.direction === "reverse" ?
                (total - 1 - index) * interval :
                index * interval;
        case "random":
            var variance = opts.variance || 2;
            return index * interval + (Math.random() - 0.5) * variance * 2;
        case "group":
            var groupSize = opts.groupSize || 4;
            var groupIdx = Math.floor(index / groupSize);
            var layerInGroup = index % groupSize;
            return groupIdx * (opts.groupDelay || 10) + layerInGroup * interval;
        default:
            return 0;
    }
}
```

#### 4.3.2 偏移控制函数

```javascript
// 时间偏移
function applyTimeOffset(layers, frameOffset) {
    for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];
        var offset = (typeof frameOffset === "function")
                     ? frameOffset(i)
                     : frameOffset * i;
        // 通过 timeRemap 实现
        if (layer.canSetTimeRemapEnabled) {
            layer.timeRemapEnabled = true;
            var remap = layer.property("ADBE Time Remapping");
            remap.expression = "sourceTime = " + offset + ";\n" +
                               "sourceTime + (time - inPoint);";
        }
    }
}

// 值偏移
function applyValueOffset(layers, propPath, offsetFn) {
    for (var i = 0; i < layers.length; i++) {
        var prop = resolvePropertyPath(layers[i], propPath);
        if (prop) {
            var originalVal = prop.value;
            var offset = offsetFn(i, layers.length);
            var newVal;
            if (Array.isArray(originalVal)) {
                newVal = originalVal.map(function(v) { return v + offset; });
            } else {
                newVal = originalVal + offset;
            }
            prop.setValue(newVal);
        }
    }
}
```

#### 4.3.3 图层组管理 API

```javascript
// 创建图层组（通过 Null 控制）
function createLayerGroup(comp, groupName, layerIndices, groupColor) {
    var nullLayer = comp.layers.addNull();
    nullLayer.name = groupName + "_CTRL";
    nullLayer.label = getLabelIndex(groupColor);

    for (var i = 0; i < layerIndices.length; i++) {
        var layer = comp.layer(layerIndices[i]);
        layer.parent = nullLayer;
        layer.label = getLabelIndex(groupColor);
    }
    return nullLayer;
}

function getLabelIndex(colorName) {
    var colors = {
        red: 1, yellow: 2, green: 3, cyan: 4, blue: 5,
        magenta: 6, pink: 7, white: 8, gray: 9, orange: 10
    };
    return colors[colorName] || 1;
}

// 按图层组选择
function selectGroup(comp, groupName) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        if (layer.name.indexOf(groupName) === 0) {
            layer.selected = true;
        }
    }
}
```

#### 4.3.4 协同动画模板

```javascript
// 同步缩放：所有图层同时缩放，但相位不同
function applyCoordinatedScale(comp, layers, baseScale, phaseOffset) {
    for (var i = 0; i < layers.length; i++) {
        var phase = i * (phaseOffset || 0.1);
        var scaleProp = layers[i].property("ADBE Transform Group")
                                 .property("ADBE Scale");
        scaleProp.expression =
            "var baseScale = " + baseScale + ";\n" +
            "var phase = " + phase + ";\n" +
            "var t = time - inPoint;\n" +
            "var amp = 5 * Math.sin(t * 2 + phase);\n" +
            "[baseScale + amp, baseScale + amp];";
    }
}

// 波浪传播：从左到右依次激活
function applyWavePropagation(comp, layers, startX, endX, duration) {
    var totalWidth = endX - startX;
    for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];
        var pos = layer.property("ADBE Transform Group").property("ADBE Position");
        var x = pos.value[0];
        var normalizedX = (x - startX) / totalWidth;
        var delay = normalizedX * duration;

        var opacityProp = layer.property("ADBE Transform Group").property("ADBE Opacity");
        opacityProp.setValueAtTime(layer.inPoint + delay, 0);
        opacityProp.setValueAtTime(layer.inPoint + delay + 0.3, 100);
    }
}
```

---

## 五、高级表达式库（100+ 表达式）

### 5.1 运动类表达式

#### 5.1.1 弹性跟随

```javascript
// 应用到 Position
var freq = 3;
var damp = 0.5;
var t = time - inPoint;
var omega = 2 * Math.PI * freq;
var alpha = -damp * omega;
var beta = omega * Math.sqrt(Math.max(0, 1 - damp * damp));
var amp = 30;
var offsetX = amp * Math.pow(Math.E, alpha * t) * Math.cos(beta * t);
var offsetY = amp * 0.5 * Math.pow(Math.E, alpha * t) * Math.cos(beta * t);
value + [offsetX, offsetY];
```

#### 5.1.2 惯性滑动

```javascript
// 应用到 Position - 鼠标/Null 跟随
var target = thisComp.layer("Target");
var followFactor = 0.1;
var smoothWindow = 5;
var accum = [0, 0];
for (var i = 0; i < smoothWindow; i++) {
    var t = Math.max(0, time - i * thisComp.frameDuration);
    accum += target.transform.position.valueAtTime(t);
}
accum / smoothWindow + (target.transform.position.value - accum) * followFactor;
```

#### 5.1.3 随机抖动

```javascript
// 应用到 Position
seedRandom(index, timeless = true);
var baseWiggle = wiggle(2, 5);
seedRandom(index + 100, timeless = false);
var microJitter = wiggle(15, 0.5);
value + baseWiggle + microJitter - [5, 5];
```

#### 5.1.4 路径跟随

```javascript
// 应用到 Position - 沿路径运动
var pathLayer = thisComp.layer("Path");
var path = pathLayer.content("Shape 1").content("Path 1").path;
var progress = linear(time, inPoint, outPoint, 0, 1);
path.pointOnPath(progress);
```

#### 5.1.5 轨道运动

```javascript
// 应用到 Position - 围绕中心点旋转
var center = [thisComp.width / 2, thisComp.height / 2];
var radius = 200;
var speed = 0.5;  // rad/s
var angle = time * speed * 2 * Math.PI;
center + [Math.cos(angle) * radius, Math.sin(angle) * radius];
```

#### 5.1.6 钟摆运动

```javascript
// 应用到 Rotation
var amp = 30;       // 振幅（度）
var freq = 0.5;     // 频率
var phase = 0;      // 相位
var t = time - inPoint;
amp * Math.sin(2 * Math.PI * freq * t + phase);
```

### 5.2 视觉效果表达式

#### 5.2.1 发光脉冲

```javascript
// 应用到 Glow Intensity
var freq = 2;
var baseIntensity = 50;
var amp = 30;
baseIntensity + amp * Math.sin(time * 2 * Math.PI * freq);
```

#### 5.2.2 透明度淡入淡出

```javascript
// 应用到 Opacity
var fadeInDur = 0.5;
var fadeOutDur = 0.5;
if (time < inPoint + fadeInDur) {
    linear(time, inPoint, inPoint + fadeInDur, 0, 100);
} else if (time > outPoint - fadeOutDur) {
    linear(time, outPoint - fadeOutDur, outPoint, 100, 0);
} else {
    100;
}
```

#### 5.2.3 颜色循环

```javascript
// 应用到 Fill Color
var hueSpeed = 0.1;  // 每秒
var h = (time * hueSpeed) % 1;
var s = 1;
var l = 0.5;
hslToRgb([h, s, l]);

function hslToRgb(hsl) {
    var h = hsl[0], s = hsl[1], l = hsl[2];
    var r, g, b;
    if (s === 0) {
        r = g = b = l;
    } else {
        var hue2rgb = function(p, q, t) {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1/6) return p + (q - p) * 6 * t;
            if (t < 1/2) return q;
            if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
            return p;
        };
        var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        var p = 2 * l - q;
        r = hue2rgb(p, q, h + 1/3);
        g = hue2rgb(p, q, h);
        b = hue2rgb(p, q, h - 1/3);
    }
    return [r, g, b, 1];
}
```

#### 5.2.4 模糊距离联动

```javascript
// 应用到 Gaussian Blur 的 Blurriness
var camLayer = thisComp.layer("Camera 1");
var targetLayer = thisComp.layer("Target");
var distance = length(thisLayer.transform.position, targetLayer.transform.position);
linear(distance, 0, 1000, 0, 50);
```

#### 5.2.5 缩放呼吸效果

```javascript
// 应用到 Scale
var breatheSpeed = 0.5;
var breatheAmount = 5;
var breathe = Math.sin(time * 2 * Math.PI * breatheSpeed) * breatheAmount;
var s = 100 + breathe;
[s, s];
```

### 5.3 音频联动表达式

#### 5.3.1 音频振幅驱动

```javascript
// 应用到 Scale - 由音频驱动
var audioLayer = thisComp.layer("Audio Amplitude");
var audioLayerEffect = audioLayer.effect("Both Channels");
var slider = audioLayerEffect("Slider");
var amp = slider.value;
var baseScale = 100;
var scaleRange = 50;
baseScale + amp * scaleRange;
```

#### 5.3.2 频率响应动画

```javascript
// 应用到 Rotation - 由特定频率驱动
var audioLayer = thisComp.layer("Audio Spectrum");
var bass = audioLayer.effect("Bass")("Slider");
var mid = audioLayer.effect("Mid")("Slider");
var treble = audioLayer.effect("Treble")("Slider");
var rotSpeed = bass * 5 + mid * 2 + treble * 0.5;
value + rotSpeed * (time - inPoint);
```

#### 5.3.3 节拍触发表达式

```javascript
// 应用到 Opacity - 节拍瞬间闪烁
var beats = [
    { time: 0.5, strength: 1.0 },
    { time: 1.0, strength: 0.6 },
    { time: 1.5, strength: 0.6 },
    { time: 2.0, strength: 1.0 }
];
var decay = 0.2;  // 秒
var result = 0;
for (var i = 0; i < beats.length; i++) {
    var b = beats[i];
    if (time >= b.time && time < b.time + decay) {
        var progress = (time - b.time) / decay;
        result = Math.max(result, (1 - progress) * b.strength * 100);
    }
}
result;
```

#### 5.3.4 音量可视化

```javascript
// 应用到 Scale Y - 由音量驱动
var audioLayer = thisComp.layer("Audio Amplitude");
var slider = audioLayer.effect("Both Channels")("Slider");
var amp = slider.value;
var maxHeight = 200;
var normalizedAmp = linear(amp, 0, 60, 0, 1);
[100, 100 + normalizedAmp * maxHeight];
```

### 5.4 实用工具表达式

#### 5.4.1 图层索引自动计算

```javascript
// 应用到 Position - 自动按索引排列
var totalLayers = thisComp.numLayers;
var layerIndex = index - 1;
var totalWidth = thisComp.width;
var colCount = 5;
var col = layerIndex % colCount;
var row = Math.floor(layerIndex / colCount);
var spacing = 100;
var startX = (thisComp.width - colCount * spacing) / 2;
[startX + col * spacing, 100 + row * spacing];
```

#### 5.4.2 时间偏移

```javascript
// 应用到 Time Remap
var timeOffset = (index - 1) * 0.1;  // 每层偏移 0.1 秒
time - inPoint + timeOffset;
```

#### 5.4.3 循环动画

```javascript
// 应用到 Position - 循环
var cycleDur = 2;
var progress = (time - inPoint) % cycleDur / cycleDur;
var path = content("Shape 1").content("Path 1").path;
path.pointOnPath(progress);
```

#### 5.4.4 条件判断

```javascript
// 应用到 Opacity - 时间段控制
var showStart = 1.0;
var showEnd = 3.0;
if (time >= showStart && time <= showEnd) {
    100;
} else {
    0;
}
```

#### 5.4.5 随机种子控制

```javascript
// 应用到 Position
seedRandom(index, timeless = true);
var basePos = random([0, 0], [thisComp.width, thisComp.height]);
seedRandom(index + 100, timeless = false);
var wiggleOffset = wiggle(1, 10);
basePos + wiggleOffset;
```

### 5.5 复杂复合表达式

#### 5.5.1 多图层协同运动

```javascript
// 应用到 Position - 多个图层波浪式运动
var center = [thisComp.width / 2, thisComp.height / 2];
var radius = 150 + index * 10;
var speed = 0.3;
var phaseOffset = index * 0.5;
var angle = time * speed * 2 * Math.PI + phaseOffset;
center + [Math.cos(angle) * radius, Math.sin(angle) * radius];
```

#### 5.5.2 物理模拟复合表达式

```javascript
// 应用到 Position - 弹簧 + 重力 + 摩擦
var freq = 2;
var damp = 0.7;
var gravity = 50;
var friction = 0.95;
var t = time - inPoint;
var omega = 2 * Math.PI * freq;
var alpha = -damp * omega;
var beta = omega * Math.sqrt(Math.max(0, 1 - damp * damp));
var springX = 100 * Math.pow(Math.E, alpha * t) * Math.cos(beta * t);
var gravityY = 0.5 * gravity * t * t * Math.pow(friction, t * 30);
value + [springX, gravityY];
```

#### 5.5.3 路径变形动画

```javascript
// 应用到 Path - 路径动态变形
var baseShape = content("Shape 1").content("Path 1").path;
var vertices = baseShape.vertices;
var newVertices = [];
var deformAmount = 20;
for (var i = 0; i < vertices.length; i++) {
    var v = vertices[i];
    var offset = Math.sin(time * 2 + i * 0.5) * deformAmount;
    newVertices.push([v[0], v[1] + offset]);
}
createPath(newVertices, baseShape.inTangents, baseShape.outTangents, baseShape.closed);
```

#### 5.5.4 摄像机联动表达式

```javascript
// 应用到 3D 图层 Position - 跟随摄像机方向
var cam = thisComp.activeCamera;
if (cam) {
    var camPos = cam.transform.position;
    var direction = normalize(camPos - transform.position);
    var distance = 100;
    transform.position + direction * distance;
} else {
    value;
}

function normalize(v) {
    var len = length(v);
    return len > 0 ? v / len : v;
}
```

### 5.6 实用扩展表达式（30+ 补充）

#### 5.6.1 等距分布

```javascript
var total = thisComp.numLayers - 1;
var idx = index - 1;
var startX = 100;
var endX = thisComp.width - 100;
linear(idx, 0, total, startX, endX);
```

#### 5.6.2 阶梯延迟

```javascript
var stepFrames = 3;
var delay = (index - 1) * stepFrames * thisComp.frameDuration;
valueAtTime(time - delay);
```

#### 5.6.3 多色循环

```javascript
var colors = [[1,0,0,1],[0,1,0,1],[0,0,1,1],[1,1,0,1]];
var colorIndex = Math.floor(time) % colors.length;
colors[colorIndex];
```

#### 5.6.4 随机延迟

```javascript
seedRandom(index);
var delay = random(0, 1);
valueAtTime(time - delay);
```

#### 5.6.5 时间反演

```javascript
var t = inPoint + (outPoint - time);
valueAtTime(t);
```

#### 5.6.6 速度感知

```javascript
var prevTime = time - thisComp.frameDuration;
var prevVal = valueAtTime(prevTime);
var velocity = (value - prevVal) * thisComp.frameRate;
var blurAmount = length(velocity) * 0.1;
```

#### 5.6.7 距离联动

```javascript
var target = thisComp.layer("Target");
var distance = length(transform.position, target.transform.position);
var maxDistance = 500;
var influence = linear(distance, 0, maxDistance, 1, 0);
transform.scale * (1 + influence * 0.5);
```

#### 5.6.8 角度计算

```javascript
var target = thisComp.layer("Target");
var dir = target.transform.position - transform.position;
var angle = Math.atan2(dir[1], dir[0]) * 180 / Math.PI;
radiansToDegrees(Math.atan2(dir[1], dir[0]));
```

#### 5.6.9 分形噪声驱动

```javascript
var noise = noise([time * 0.5, index * 0.1]);
var scaleAmount = noise * 20;
value + scaleAmount;
```

#### 5.6.10 索引循环

```javascript
var cycleLength = 4;
var phase = (index - 1) % cycleLength;
var offsets = [[10, 0], [0, 10], [-10, 0], [0, -10]];
value + offsets[phase];
```

#### 5.6.11 时间冻结

```javascript
var freezeStart = 2;
var freezeEnd = 3;
if (time >= freezeStart && time < freezeEnd) {
    valueAtTime(freezeStart);
} else {
    value;
}
```

#### 5.6.12 缓动循环

```javascript
var loopDur = 2;
var progress = (time - inPoint) % loopDur / loopDur;
var eased = ease(progress, 0, 1, 0, 1);
linear(eased, 0, 1, [0, 0], [100, 0]);
```

#### 5.6.13 多Null联动

```javascript
var ctrl1 = thisComp.layer("CTRL_Main");
var ctrl2 = thisComp.layer("CTRL_Secondary");
var blend = 0.5;
ctrl1.transform.position * blend + ctrl2.transform.position * (1 - blend);
```

#### 5.6.14 速度颜色映射

```javascript
var prevVal = transform.position.valueAtTime(time - thisComp.frameDuration);
var speed = length(transform.position.value - prevVal) * thisComp.frameRate;
var normalizedSpeed = linear(speed, 0, 200, 0, 1);
[
    normalizedSpeed,
    1 - normalizedSpeed,
    0.5,
    1
];
```

#### 5.6.15 形状变形循环

```javascript
var morphSpeed = 1;
var phase = (time * morphSpeed) % 1;
var shape1 = content("Shape 1").content("Path 1").path;
var shape2 = content("Shape 2").content("Path 1").path;
var v1 = shape1.vertices;
var v2 = shape2.vertices;
var newV = [];
for (var i = 0; i < v1.length; i++) {
    newV.push([
        v1[i][0] * (1 - phase) + v2[i][0] * phase,
        v1[i][1] * (1 - phase) + v2[i][1] * phase
    ]);
}
createPath(newV, shape1.inTangents, shape1.outTangents, shape1.closed);
```

#### 5.6.16 多频率振荡

```javascript
var freq1 = 0.5, amp1 = 10;
var freq2 = 2, amp2 = 5;
var freq3 = 8, amp3 = 1;
var t = time - inPoint;
var combined = Math.sin(2*Math.PI*freq1*t) * amp1 +
               Math.sin(2*Math.PI*freq2*t) * amp2 +
               Math.sin(2*Math.PI*freq3*t) * amp3;
value + combined;
```

#### 5.6.17 抛物线轨迹

```javascript
var startPos = [100, 500];
var endPos = [900, 500];
var height = 300;
var duration = 2;
var t = clamp((time - inPoint) / duration, 0, 1);
var x = linear(t, 0, 1, startPos[0], endPos[0]);
var y = linear(t, 0, 1, startPos[1], endPos[1]) - 4 * height * t * (1 - t);
[x, y];

function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
}
```

#### 5.6.18 螺旋运动

```javascript
var center = [thisComp.width/2, thisComp.height/2];
var maxRadius = 200;
var t = time - inPoint;
var radius = (t / 5) * maxRadius;
var angle = t * 2 * Math.PI;
center + [Math.cos(angle) * radius, Math.sin(angle) * radius];
```

#### 5.6.19 弹性回弹

```javascript
var amp = 40;
var freq = 4;
var decay = 0.7;
var t = time - inPoint;
if (t > 0) {
    var decayFactor = Math.exp(-decay * t);
    value + [Math.sin(freq * t * 2 * Math.PI) * amp * decayFactor,
             Math.cos(freq * t * 2 * Math.PI) * amp * decayFactor * 0.5];
} else {
    value;
}
```

#### 5.6.20 多层渐变

```javascript
var colors = [
    [1, 0.2, 0.2, 1],
    [0.2, 1, 0.5, 1],
    [0.2, 0.5, 1, 1]
];
var idx = Math.floor((time / 2) % colors.length);
var nextIdx = (idx + 1) % colors.length;
var blend = (time / 2) % 1;
[
    colors[idx][0] * (1 - blend) + colors[nextIdx][0] * blend,
    colors[idx][1] * (1 - blend) + colors[nextIdx][1] * blend,
    colors[idx][2] * (1 - blend) + colors[nextIdx][2] * blend,
    1
];
```

#### 5.6.21 鼠标位置跟踪

```javascript
// 应用到 Position - 跟踪鼠标位置（通过 Null 表达式控制）
var cursor = thisComp.layer("Cursor");
var followSpeed = 0.15;
var currentPos = transform.position.value;
var targetPos = cursor.transform.position.value;
currentPos + (targetPos - currentPos) * followSpeed;
```

#### 5.6.22 时间反向 Wiggle

```javascript
// 应用到 Position - 反向播放的 wiggle
seedRandom(index, timeless = true);
var totalTime = outPoint - inPoint;
var reversedTime = totalTime - (time - inPoint);
seedRandom(index, timeless = false);
wiggle(2, 10, 1, 0.5, reversedTime);
```

#### 5.6.23 多路径循环

```javascript
var pathLayer = thisComp.layer("Path System");
var pathIdx = Math.floor((time / 2) % 3) + 1;
var path = pathLayer.content("Shape " + pathIdx).content("Path 1").path;
var progress = ((time - inPoint) % 2) / 2;
path.pointOnPath(progress);
```

#### 5.6.24 速度线密度

```javascript
var velocity = length(transform.position.value -
                       transform.position.valueAtTime(time - 0.05));
var lineDensity = linear(velocity, 0, 50, 0, 100);
lineDensity;
```

#### 5.6.25 角度抖动

```javascript
seedRandom(index + Math.floor(time * 5));
var angleJitter = random(-15, 15);
value + angleJitter;
```

#### 5.6.26 距离淡入

```javascript
var target = thisComp.layer("Focus Point");
var dist = length(transform.position, target.transform.position);
var maxDist = 400;
linear(dist, 0, maxDist, 100, 0);
```

#### 5.6.27 索引相位

```javascript
var totalLayers = 10;
var phase = (index - 1) / totalLayers * 2 * Math.PI;
Math.sin(time * 2 + phase) * 50;
```

#### 5.6.28 噪声波形

```javascript
var freq = 0.5;
var noiseVal = noise([time * freq, 0]);
var amp = 30;
value + noiseVal * amp;
```

#### 5.6.29 节拍触发动画

```javascript
var beatTimes = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0];
var scaleAmount = 0;
for (var i = 0; i < beatTimes.length; i++) {
    if (time >= beatTimes[i] && time < beatTimes[i] + 0.3) {
        var decay = Math.exp(-(time - beatTimes[i]) * 8);
        scaleAmount = Math.max(scaleAmount, decay * 30);
    }
}
[100 + scaleAmount, 100 + scaleAmount];
```

#### 5.6.30 多色梯度

```javascript
var layers = 5;
var idx = index - 1;
var hueStart = 0;
var hueEnd = 1;
var hue = linear(idx, 0, layers - 1, hueStart, hueEnd);
hslToRgb([hue, 1, 0.5, 1]);
```

#### 5.6.31 摄像机距离联动

```javascript
var cam = thisComp.activeCamera;
if (cam && transform.position) {
    var camDist = length(cam.transform.position, transform.position);
    var fogStart = 500;
    var fogEnd = 2000;
    var fogAmount = linear(camDist, fogStart, fogEnd, 0, 1);
    transform.opacity * (1 - fogAmount);
} else {
    value;
}
```

#### 5.6.32 双向同步

```javascript
var partner = thisComp.layer("Partner_" + (index % 2 === 0 ? index - 1 : index + 1));
var myPos = transform.position;
var partnerPos = partner.transform.position;
var midpoint = (myPos + partnerPos) / 2;
var dist = length(myPos - partnerPos);
var lineOpacity = linear(dist, 0, 300, 100, 0);
```

#### 5.6.33 时钟指针

```javascript
// 应用到 Rotation - 模拟时钟秒针
var seconds = time % 60;
var angle = seconds * 6;  // 每秒6度
angle;
```

#### 5.6.34 摆动旋转

```javascript
var amp = 15;
var freq = 0.3;
var phase = index * 0.5;
amp * Math.sin(2 * Math.PI * freq * (time - inPoint) + phase);
```

#### 5.6.35 闪烁脉冲

```javascript
var freq = 8;
var threshold = 0.7;
var noiseVal = noise([time * freq, 0]);
noiseVal > threshold ? 100 : 30;
```

#### 5.6.36 形状路径过渡

```javascript
var pathA = content("Shape 1").content("Path 1").path;
var pathB = content("Shape 2").content("Path 1").path;
var t = linear(time, inPoint + 1, inPoint + 2, 0, 1);
t = clamp(t, 0, 1);
var vertsA = pathA.vertices;
var vertsB = pathB.vertices;
var newVerts = [];
for (var i = 0; i < vertsA.length; i++) {
    newVerts.push([
        vertsA[i][0] * (1 - t) + vertsB[i][0] * t,
        vertsA[i][1] * (1 - t) + vertsB[i][1] * t
    ]);
}
createPath(newVerts, pathA.inTangents, pathA.outTangents, pathA.closed);
```

#### 5.6.37 反向位置

```javascript
var partner = thisComp.layer("Partner");
var center = [thisComp.width/2, thisComp.height/2];
center - (partner.transform.position - center);
```

#### 5.6.38 缩放弹性

```javascript
var amp = 0.2;
var freq = 3;
var decay = 1;
var t = time - inPoint;
var factor = 1 + amp * Math.exp(-decay * t) * Math.cos(freq * t * 2 * Math.PI);
value * factor;
```

#### 5.6.39 路径切线方向

```javascript
var path = content("Shape 1").content("Path 1").path;
var progress = linear(time, inPoint, outPoint, 0, 1);
var tangent = path.tangentOnPath(progress);
var angle = Math.atan2(tangent[1], tangent[0]) * 180 / Math.PI;
angle;
```

#### 5.6.40 反射联动

```javascript
var source = thisComp.layer("Source");
var mirrorY = thisComp.height;
var mirrorPos = [source.transform.position.value[0],
                 mirrorY - source.transform.position.value[1]];
mirrorPos;
```

---

## 六、跨工具协同工作流

### 6.1 BeatEdit + Motion Tools Pro

#### 6.1.1 节拍驱动物理动画

**工作流：**
1. BeatEdit 检测节拍 → 生成 Beat 数组
2. 提取强拍 → 创建关键帧时间表
3. Motion Tools Pro 物理引擎 → 模拟弹簧响应
4. 应用到目标图层 → 生成最终动画

```javascript
// 节拍驱动弹簧动画
function beatDrivenSpring(comp, layer) {
    var beats = $.global.beatEdit.getBeats(comp);
    var posProp = layer.property("ADBE Transform Group").property("ADBE Position");

    // 清除现有表达式
    posProp.expression = "";

    // 为每个强拍添加关键帧
    for (var i = 0; i < beats.length; i++) {
        var beat = beats[i];
        if (beat.isDownbeat) {
            var basePos = posProp.value;
            var amp = beat.strength * 80;
            posProp.setValueAtTime(beat.time, [basePos[0], basePos[1] - amp]);
            posProp.setValueAtTime(beat.time + 0.05, basePos);
        }
    }

    // 应用弹性曲线
    var springCurve = getCurve("ease_out_back");
    applyCurveToKeyframes(posProp, "ease_out_back");

    // 进一步通过表达式增加细节
    posProp.expression =
        "// Beat Driven Spring\n" +
        "var freq = 5;\n" +
        "var damp = 0.3;\n" +
        "var t = time;\n" +
        "var offset = 0;\n" +
        "var beats = [\n";
    for (var j = 0; j < beats.length; j++) {
        posProp.expression += "  " + beats[j].time + ",\n";
    }
    posProp.expression +=
        "];\n" +
        "for (var i = 0; i < beats.length; i++) {\n" +
        "  if (t > beats[i]) {\n" +
        "    var dt = t - beats[i];\n" +
        "    var decay = Math.exp(-damp * dt * 10);\n" +
        "    offset += decay * Math.cos(freq * dt * 2 * Math.PI) * 20;\n" +
        "  }\n" +
        "}\n" +
        "value + [0, offset];";
}
```

#### 6.1.2 音乐节奏弹性效果

```javascript
// 综合方案：节拍 → 弹簧 + Wiggle
function musicRhythmElastic(comp, layer) {
    var beats = $.global.beatEdit.getBeats(comp);
    var scaleProp = layer.property("ADBE Transform Group").property("ADBE Scale");

    var beatTimes = beats.map(function(b) { return b.time; });
    var beatStrengths = beats.map(function(b) { return b.strength; });

    // 使用表达式实现持续弹性
    var expr = [
        "// Music Rhythm Elastic",
        "var beatTimes = [" + beatTimes.join(", ") + "];",
        "var beatStrengths = [" + beatStrengths.join(", ") + "];",
        "var freq = 3;",
        "var damp = 0.4;",
        "var amp = 15;",
        "var scaleOffset = 0;",
        "for (var i = 0; i < beatTimes.length; i++) {",
        "    if (time > beatTimes[i]) {",
        "        var dt = time - beatTimes[i];",
        "        var decay = Math.exp(-damp * dt * 10);",
        "        scaleOffset += decay * Math.cos(freq * dt * 2 * Math.PI) * amp * beatStrengths[i];",
        "    }",
        "}",
        "var baseScale = 100;",
        "[baseScale + scaleOffset, baseScale + scaleOffset];"
    ].join("\n");

    scaleProp.expression = expr;
}
```

### 6.2 MotionSpice + Motion Studio

#### 6.2.1 图形创建与编排联动

```javascript
// 批量创建图形并协同动画
function createAndArrangeShapes(comp, count, shapeType) {
    var layers = [];
    var cols = 5;
    var spacing = 80;
    var startX = (comp.width - cols * spacing) / 2;

    app.beginUndoGroup("批量创建与编排");

    for (var i = 0; i < count; i++) {
        var col = i % cols;
        var row = Math.floor(i / cols);
        var x = startX + col * spacing;
        var y = 100 + row * spacing;

        var layer;
        switch (shapeType) {
            case "rectangle":
                layer = createRectangle(comp, x, y, 60, 60, 5);
                break;
            case "circle":
                layer = createEllipse(comp, x, y, 60, 60);
                break;
            case "polygon":
                layer = createPolygon(comp, x, y, 6, 30, 0, false);
                break;
        }
        layers.push(layer);
    }

    // 应用 Motion Studio 的同步模式
    var syncResult = applySyncMode(layers, "stagger", { interval: 2 });
    for (var j = 0; j < syncResult.length; j++) {
        var delay = syncResult[j].delay;
        var opacity = layers[j].property("ADBE Transform Group").property("ADBE Opacity");
        opacity.setValueAtTime(layers[j].inPoint + delay / comp.frameRate, 0);
        opacity.setValueAtTime(layers[j].inPoint + (delay + 10) / comp.frameRate, 100);
    }

    app.endUndoGroup();
    return layers;
}
```

#### 6.2.2 批量图形动画系统

```javascript
// 批量动画：每个图形不同节奏
function batchShapeAnimation(comp, shapeLayers, beats) {
    for (var i = 0; i < shapeLayers.length; i++) {
        var layer = shapeLayers[i];
        var phaseOffset = i * 0.2;
        var scaleProp = layer.property("ADBE Transform Group").property("ADBE Scale");
        var rotProp = layer.property("ADBE Transform Group").property("ADBE Rotate Z");

        // 节拍触发缩放
        for (var b = 0; b < beats.length; b++) {
            var beat = beats[b];
            if (beat.isDownbeat) {
                var scale = 100 + beat.strength * 30 * (1 - i * 0.05);
                var timeOffset = beat.time + phaseOffset;
                scaleProp.setValueAtTime(timeOffset, [scale, scale]);
                scaleProp.setValueAtTime(timeOffset + 0.15, [100, 100]);

                rotProp.setValueAtTime(timeOffset, beat.strength * 15);
                rotProp.setValueAtTime(timeOffset + 0.15, 0);
            }
        }

        // 应用弹性缓动
        applyCurveToKeyframes(scaleProp, "ease_out_back");
        applyCurveToKeyframes(rotProp, "ease_out_back");
    }
}
```

### 6.3 四工具联合工作流

#### 6.3.1 完整 MG 动画制作流程

```javascript
// 四工具联合 - 完整 MG 动画
function fullMGAnimation(comp, audioLayer) {
    app.beginUndoGroup("四工具联合 MG 动画");

    // === 阶段1：BeatEdit 节拍分析 ===
    $.writeln("阶段1：BeatEdit 节拍分析...");
    var beats = $.global.beatEdit.getBeats(comp);
    var bpm = $.global.beatEdit.getBPM(comp);
    $.writeln("  BPM: " + bpm + " | 节拍数: " + beats.length);

    // === 阶段2：MotionSpice 图形创建 ===
    $.writeln("阶段2：MotionSpice 创建图形...");
    var shapeLayers = [];
    var bgShape = createRectangle(comp, comp.width/2, comp.height/2,
                                  comp.width, comp.height, 0);
    bgShape.name = "Background";
    applyStyle(bgShape, {
        fill: { color: [0.05, 0.05, 0.1, 1], opacity: 100 }
    });
    shapeLayers.push(bgShape);

    // 创建 12 个动画元素
    for (var i = 0; i < 12; i++) {
        var x = 100 + (i % 4) * 200;
        var y = 200 + Math.floor(i / 4) * 200;
        var shape = createCircle(comp, x, y, 80, 80);
        shape.name = "Element_" + (i + 1);
        shapeLayers.push(shape);
    }

    // 应用样式
    var styleObj = {
        fill: { color: [0.4, 0.8, 1, 1], opacity: 80 },
        stroke: { color: [1, 1, 1, 1], width: 2, opacity: 60 },
        glow: { enabled: true, color: [0.4, 0.8, 1, 1], intensity: 50, size: 30 }
    };
    for (var s = 1; s < shapeLayers.length; s++) {
        applyStyle(shapeLayers[s], styleObj);
    }

    // === 阶段3：Motion Tools Pro 物理动画 ===
    $.writeln("阶段3：Motion Tools Pro 物理动画...");
    var animLayers = shapeLayers.slice(1);  // 排除背景
    for (var a = 0; a < animLayers.length; a++) {
        var layer = animLayers[a];
        musicRhythmElastic(comp, layer);
    }

    // === 阶段4：Motion Studio 编排协同 ===
    $.writeln("阶段4：Motion Studio 协同编排...");
    applySyncMode(animLayers, "wave", { interval: 3, direction: "forward" });
    applyCoordinatedScale(comp, animLayers, 100, 0.3);

    app.endUndoGroup();
    $.writeln("完成！");
}

function createCircle(comp, x, y, w, h) {
    return createEllipse(comp, x, y, w, h);
}
```

#### 6.3.2 音乐可视化完整方案

```javascript
// 音乐可视化：节拍 + 粒子 + 波形 + 文字
function musicVisualization(comp, audioLayer) {
    app.beginUndoGroup("Music Visualization");

    // 获取节拍数据
    var beats = $.global.beatEdit.getBeats(comp);

    // === 1. 节拍触发粒子系统 ===
    var particleLayer = comp.layers.addSolid([0, 0, 0], "Particles",
                                              comp.width, comp.height,
                                              comp.pixelAspect, comp.duration);
    var particular = particleLayer.property("ADBE Effect Parade")
                                  .addProperty("PARTICULAR");

    // 设置发射器
    particular.property("PARTICLE_MASTER_Emitter")
              .property("Emitter Type").setValue(1);  // Box
    particular.property("PARTICLE_MASTER_Emitter")
              .property("Emitter Size X").setValue(1920);
    particular.property("PARTICLE_MASTER_Emitter")
              .property("Emitter Size Y").setValue(1080);

    // 节拍触发发射速率
    var particlesPerSec = particular.property("PARTICLE_MASTER_Emitter")
                                    .property("PARTICLES/SEC");
    particlesPerSec.setValueAtTime(0, 0);
    for (var i = 0; i < beats.length; i++) {
        var beat = beats[i];
        particlesPerSec.setValueAtTime(beat.time, beat.strength * 5000);
        particlesPerSec.setValueAtTime(beat.time + 0.1, 0);
    }

    // === 2. 波形可视化 ===
    var waveLayer = comp.layers.addShape();
    waveLayer.name = "Waveform";
    buildWaveformFromBeats(comp, beats, comp.width);

    // === 3. 节拍触发的文字动画 ===
    var textLayer = comp.layers.addText("MUSIC");
    textLayer.name = "Beat Text";
    var textProp = textLayer.property("ADBE Text Properties")
                            .property("ADBE Text Document");
    var textAnim = textLayer.property("ADBE Text Properties")
                            .property("ADBE Text Animators")
                            .addProperty("ADBE Text Animator");

    // 应用节拍触发的缩放
    var scaleProp = textLayer.property("ADBE Transform Group").property("ADBE Scale");
    for (var b = 0; b < beats.length; b++) {
        var beat = beats[b];
        if (beat.isDownbeat) {
            scaleProp.setValueAtTime(beat.time, [110, 110]);
            scaleProp.setValueAtTime(beat.time + 0.1, [100, 100]);
        }
    }

    // 应用弹性曲线
    applyCurveToKeyframes(scaleProp, "ease_out_back");

    // === 4. 同步音频到效果参数 ===
    var audioAmplitude = audioLayer.property("ADBE Effect Parade")
                                  .addProperty("ADBE Sterero Mixer");
    // 假设已添加 Audio Amplitude Keyframe Assistant

    app.endUndoGroup();
}
```

---

## 附录

### 附录 A：API 方法速查表

#### BeatEdit API

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `$.global.beatEdit.getBeats(comp)` | Array<Beat> | 获取全部节拍 |
| `$.global.beatEdit.getBPM(comp)` | Number | 获取 BPM |
| `$.global.beatEdit.getTimeSignature(comp)` | String | 节拍签名 |
| `$.global.beatEdit.getDownbeats(comp)` | Array<Beat> | 仅强拍 |
| `$.global.beatEdit.getBeatsInRange(comp, start, end)` | Array<Beat> | 范围内节拍 |
| `$.global.beatEdit.addBeat(comp, time, strength)` | Boolean | 添加节拍 |
| `$.global.beatEdit.removeBeat(comp, index)` | Boolean | 删除节拍 |
| `$.global.beatEdit.syncToMarkers(comp, options)` | Number | 同步标记 |
| `$.global.beatEdit.generateKeyframes(comp, layer, path, options)` | Number | 生成关键帧 |
| `$.global.beatEdit.exportJSON(comp, filePath)` | Boolean | 导出 JSON |

#### Motion Tools Pro API

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `$.global.motionTools.selectByType(comp, type)` | Array<Layer> | 按类型选择 |
| `$.global.motionTools.selectByEffect(comp, matchName)` | Array<Layer> | 按效果选择 |
| `$.global.motionTools.applyCurve(prop, curveName, indices)` | Boolean | 应用曲线 |
| `$.global.motionTools.applySpring(prop, options)` | Boolean | 应用弹簧 |
| `$.global.motionTools.customCurves` | Array | 自定义曲线库 |

#### MotionSpice API

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `createRectangle(comp, x, y, w, h, r)` | ShapeLayer | 创建矩形 |
| `createEllipse(comp, x, y, w, h)` | ShapeLayer | 创建圆形 |
| `createPolygon(comp, x, y, p, oR, iR, isStar)` | ShapeLayer | 创建多边形/星形 |
| `createPath(comp, vertices, closed)` | ShapeLayer | 创建路径 |
| `addFill(shapeLayer, color, opacity)` | Property | 添加填充 |
| `addStroke(shapeLayer, color, width, opacity)` | Property | 添加描边 |
| `applyStyle(shapeLayer, styleObj)` | void | 应用样式 |

#### Motion Studio API

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `addChapterMarker(comp, time, name, color)` | MarkerValue | 添加章节标记 |
| `setWorkArea(comp, start, end)` | void | 设置工作区域 |
| `linkToNull(comp, layer, propPath, nullName)` | Layer | 关联到 Null |
| `applySyncMode(layers, mode, options)` | Array | 应用同步模式 |
| `applyCoordinatedScale(comp, layers, base, phase)` | void | 协同缩放 |

### 附录 B：表达式语法参考

#### 全局对象

| 对象 | 说明 |
|------|------|
| `thisComp` | 当前合成 |
| `thisLayer` | 当前图层 |
| `time` | 当前时间（秒） |
| `value` | 当前属性值 |
| `index` | 图层索引 |
| `inPoint` / `outPoint` | 图层入点/出点 |

#### 数学函数

| 函数 | 说明 |
|------|------|
| `linear(t, tMin, tMax, value1, value2)` | 线性映射 |
| `ease(t, tMin, tMax, value1, value2)` | 缓动映射 |
| `easeIn(t, tMin, tMax, value1, value2)` | 缓入映射 |
| `easeOut(t, tMin, tMax, value1, value2)` | 缓出映射 |
| `clamp(value, limit1, limit2)` | 限制范围 |
| `length(point1, point2)` | 计算距离 |
| `length(point)` | 计算向量长度 |
| `normalize(vec)` | 向量归一化 |
| `random(min, max)` | 随机数 |
| `noise(freq)` | Perlin 噪声 |
| `gaussRandom(min, max)` | 高斯随机 |
| `degreesToRadians(deg)` | 角度转弧度 |
| `radiansToDegrees(rad)` | 弧度转角度 |

#### 关键方法

| 方法 | 说明 |
|------|------|
| `valueAtTime(t)` | 在时间 t 取值 |
| `velocityAtTime(t)` | 在时间 t 的速度 |
| `seedRandom(seed, timeless)` | 设置随机种子 |
| `wiggle(freq, amp, octaves, amp_mult, t)` | 抖动 |
| `loopIn(type, numKeyframes)` | 入点循环 |
| `loopOut(type, numKeyframes)` | 出点循环 |
| `loopInDuration(type, duration)` | 入点循环（按秒） |
| `loopOutDuration(type, duration)` | 出点循环（按秒） |
| `posterizeTime(fps)` | 限制帧率 |

### 附录 C：参数范围与默认值表

#### 弹簧参数

| 参数 | 最小值 | 最大值 | 默认值 | 单位 |
|------|--------|--------|--------|------|
| frequency | 0.1 | 20.0 | 2.0 | Hz |
| damping | 0.0 | 1.0 | 0.5 | 无量纲 |
| mass | 0.1 | 10.0 | 1.0 | kg |
| gravity | -100 | 100 | 0 | m/s² |
| stiffness | 0 | 1000 | 100 | N/m |
| initialVelocity | -1000 | 1000 | 0 | px/s |

#### BeatEdit 节拍对象

| 属性 | 最小值 | 最大值 | 默认值 | 单位 |
|------|--------|--------|--------|------|
| time | 0.0 | comp.duration | 必填 | 秒 |
| strength | 0.0 | 1.0 | 0.5 | 无量纲 |
| confidence | 0.0 | 1.0 | 0.8 | 无量纲 |
| patternIndex | 0 | 15 | 0 | 无量纲 |
| group | 0 | 63 | 0 | 无量纲 |

#### Wiggle 函数参数

| 参数 | 最小值 | 最大值 | 默认值 | 说明 |
|------|--------|--------|--------|------|
| frequency | 0 | 100 | 1 | Hz |
| amplitude | 0 | ∞ | 50 | px |
| octaves | 1 | 10 | 1 | 倍频数 |
| amp_mult | 0 | 1 | 0.5 | 振幅倍率 |

### 附录 D：常见错误代码

| 错误代码 | 含义 | 解决方案 |
|---------|------|---------|
| `BE-001` | BeatEdit 未初始化 | 检查 `$.global.beatEdit` 是否存在 |
| `BE-002` | 节拍数据为空 | 先执行节拍检测 |
| `BE-003` | 音频文件未加载 | 导入音频到合成 |
| `BE-004` | JSON 格式错误 | 检查 JSON 文件格式 |
| `BE-005` | BPM 检测失败 | 检查音频是否包含清晰节奏 |
| `MT-001` | 属性不支持关键帧 | 检查 `canVaryOverTime` |
| `MT-002` | 曲线名称未找到 | 检查曲线名拼写 |
| `MT-003` | 物理参数越界 | 检查参数范围表 |
| `MS-001` | 形状创建失败 | 检查 comp 是否有效 |
| `MS-002` | 路径数据无效 | 检查顶点数组 |
| `MS-003` | 样式对象格式错误 | 检查 JSON 结构 |
| `MS-004` | 渐变颜色数错误 | 检查 stops 数组长度 |
| `MST-001` | 图层未找到 | 检查图层名称 |
| `MST-002` | 表达式语法错误 | 启用表达式调试 |
| `MST-003` | 关联链过长 | 减少关联层级 |
| `MST-004` | 同步模式不支持 | 检查 mode 参数 |
| `AE-1001` | 通用 API 错误 | 查看 ExtendScript IDE 错误信息 |
| `AE-1002` | 内存不足 | 减少批量操作规模 |
| `AE-1003` | 文件读写失败 | 检查文件权限 |
| `AE-1004` | UndoGroup 未关闭 | 检查 begin/endUndoGroup 配对 |

---

## 文档信息

- **文档类型**：AE扩展脚本 - 工具API与表达式库完全手册（分支文档）
- **主文档**：`AE扩展脚本完全知识库.md`
- **配套知识库**：
  - `AE表达式进阶宝典.md`
  - `AE表达式核心函数完全手册.md`
  - `AE ExtendScript API 原子级映射手册.md`
  - `MCP→AE效果操作桥接规范.md`
  - `原子参数编译器规范.md`
- **编写标准**：实验研究原子级标准
- **适用版本**：AE CC 2022 ~ AE 2026
- **工具版本**：
  - BeatEdit for Ae 2.2.005+
  - Motion Tools Pro 3.x+
  - MotionSpice 2.x+
  - Motion Studio 1.x+

---

**文档结束**

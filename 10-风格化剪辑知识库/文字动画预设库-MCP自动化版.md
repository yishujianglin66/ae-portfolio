# 文字动画预设库 — MCP自动化版

本库所有预设均通过 MCP `executeAtomScript` 命令自动化调用，无需手动运行脚本。JSON 配置源位于 `config/text_animation_presets.json`。

---

## 五、社交媒体卡点风预设（15种）

本章节面向抖音/快手/B站/小红书等竖屏短视频卡点剪辑场景，所有预设均适配 1080×1920 竖屏合成，结合节拍时间数组（`beatTimes`）实现精准卡点。调用时通过 MCP 的 `executeAtomScript` 工具执行对应 JSX 代码即可。

---

### 1. 抖音弹跳标题 (Douyin Bounce Title)

**效果描述**：标题以缩放回弹方式入场，连续多次弹跳逐渐收敛至原始尺寸，模拟抖音流行标题的"Q弹"质感，配合鲜艳品红色填充，强烈吸引注意力。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 抖音弹跳标题 | 任意字符串 | 目标文字图层名，不存在则自动创建 |
| duration | 2.0 | 0.5-5.0s | 弹跳动画总时长 |
| intensity | 1.3 | 1.1-2.0 | 峰值缩放倍率，越大弹得越夸张 |
| bounceCount | 3 | 1-8 | 弹跳次数，越多越细碎 |
| baseScale | 100 | 50-200 | 基础缩放百分比 |
| color | [1,0.2,0.4] | [R,G,B] 0-1 | 文字填充色（品红） |

**适用场景**：抖音/快手竖屏开场标题、口播视频重点词强调、带货视频产品名弹出。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "douyin_bounce_title",
    "textLayerName": "抖音弹跳标题",
    "duration": 2.0,
    "intensity": 1.3,
    "bounceCount": 3,
    "baseScale": 100,
    "color": [1, 0.2, 0.4]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "抖音弹跳标题",
      duration: 2.0,
      intensity: 1.3,
      bounceCount: 3,
      baseScale: 100,
      color: [1, 0.2, 0.4]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var sc = layer.property("Scale");
    var t0 = layer.inPoint;
    var dt = p.duration / (p.bounceCount + 1);
    sc.setValueAtTime(t0,
      [p.baseScale * 0.3, p.baseScale * 0.3]);
    for (var i = 0; i < p.bounceCount; i++) {
      var peak = p.baseScale * p.intensity;
      sc.setValueAtTime(t0 + dt * (i + 0.5),
        [peak, peak]);
      sc.setValueAtTime(t0 + dt * (i + 1),
        [p.baseScale, p.baseScale]);
    }
    for (var k = 1; k <= sc.numKeys; k++) {
      sc.setInterpolationTypeAtKey(k,
        KeyframeInterpolationType.BEZIER,
        KeyframeInterpolationType.BEZIER);
      try {
        var ei = new KeyframeEase(0, 80);
        sc.setTemporalEaseAtKey(k,
          [ei, ei], [ei, ei]);
      } catch(e2) {}
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = 120;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Douyin Bounce Title",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 2. 卡点缩放标题 (Beat Scale Title)

**效果描述**：在每个节拍点触发缩放"重击"动画，瞬间放大至峰值后迅速回落，形成与音乐鼓点同步的视觉冲击，适合强节奏视频。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 卡点缩放标题 | 任意字符串 | 目标文字图层名 |
| beatTimes | [0.5,1.0,1.5,2.0,2.5] | 时间数组 | 节拍时间点（秒），相对图层入点 |
| scalePunch | 1.4 | 1.1-2.0 | 节拍峰值缩放倍率 |
| baseScale | 100 | 50-200 | 基础缩放百分比 |
| color | [1,0.9,0.1] | [R,G,B] 0-1 | 文字填充色（亮黄） |

**适用场景**：电子鼓点卡点、舞蹈视频节奏强调、游戏高光时刻标题。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "beat_scale_title",
    "textLayerName": "卡点缩放标题",
    "beatTimes": [0.5, 1.0, 1.5, 2.0, 2.5],
    "scalePunch": 1.4,
    "baseScale": 100,
    "color": [1, 0.9, 0.1]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "卡点缩放标题",
      beatTimes: [0.5, 1.0, 1.5, 2.0, 2.5],
      scalePunch: 1.4,
      baseScale: 100,
      color: [1, 0.9, 0.1]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var sc = layer.property("Scale");
    sc.setValue([p.baseScale, p.baseScale]);
    var t0 = layer.inPoint;
    for (var i = 0; i < p.beatTimes.length; i++) {
      var bt = t0 + p.beatTimes[i];
      var peak = p.baseScale * p.scalePunch;
      sc.setValueAtTime(bt, [peak, peak]);
      sc.setValueAtTime(bt + 0.08,
        [p.baseScale, p.baseScale]);
    }
    for (var k = 1; k <= sc.numKeys; k++) {
      sc.setInterpolationTypeAtKey(k,
        KeyframeInterpolationType.BEZIER,
        KeyframeInterpolationType.BEZIER);
      try {
        var ei = new KeyframeEase(0, 75);
        sc.setTemporalEaseAtKey(k,
          [ei, ei], [ei, ei]);
      } catch(e2) {}
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = 140;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Beat Scale Title",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 3. 竖屏霓虹标题 (Vertical Neon Title)

**效果描述**：为竖屏标题添加霓虹发光效果，自带描边、发光半径与不透明度闪烁，营造赛博朋克/夜店霓虹招牌质感。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 竖屏霓虹标题 | 任意字符串 | 目标文字图层名 |
| glowSize | 25 | 5-80 | 发光半径（像素） |
| glowIntensity | 1.5 | 0.5-4.0 | 发光强度 |
| flicker | 0.3 | 0-0.8 | 闪烁幅度（0=不闪） |
| color | [0.2,1,1] | [R,G,B] 0-1 | 霓虹色（青色） |
| bgColor | [0,0,0] | [R,G,B] 0-1 | 背景色（仅参考） |

**适用场景**：竖屏夜店/赛博朋克风视频、电音MV标题、夜间探店片头。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "vertical_neon_title",
    "textLayerName": "竖屏霓虹标题",
    "glowSize": 25,
    "glowIntensity": 1.5,
    "flicker": 0.3,
    "color": [0.2, 1, 1],
    "bgColor": [0, 0, 0]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "竖屏霓虹标题",
      glowSize: 25,
      glowIntensity: 1.5,
      flicker: 0.3,
      color: [0.2, 1, 1],
      bgColor: [0, 0, 0]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.applyFill = true;
    td.applyStroke = true;
    td.strokeColor = p.color;
    td.strokeWidth = 3;
    td.fontSize = 160;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var glow = layer.property("Effects")
      .addProperty("ADBE Glo 2");
    if (glow) {
      glow.property("ADBE Glo-0001")
        .setValue(p.glowSize);
      glow.property("ADBE Glo-0002")
        .setValue(p.glowIntensity);
      glow.property("ADBE Glo-0003")
        .setValue(p.color);
    }
    var op = layer.property("Opacity");
    var t0 = layer.inPoint;
    for (var i = 0; i < 20; i++) {
      var tt = t0 + i * 0.1;
      var v = 100 - p.flicker * 100 *
        (Math.random() * 0.5 + 0.5);
      op.setValueAtTime(tt, Math.max(60, v));
    }
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Vertical Neon Title",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 4. 闪现字幕 (Flash Subtitle)

**效果描述**：字幕在节拍点瞬间闪现/消失，配合极短的过渡时间形成"啪啪啪"的卡点字幕切换，适合快节奏口播与歌词字幕。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 闪现字幕 | 任意字符串 | 目标文字图层名 |
| beatTimes | [0,0.6,1.2,1.8] | 时间数组 | 字幕闪现时间点 |
| flashDuration | 0.05 | 0.02-0.2s | 闪现过渡时长 |
| fontSize | 80 | 40-200 | 字号 |
| color | [1,1,1] | [R,G,B] 0-1 | 文字色（白） |
| bgColor | [0,0,0] | [R,G,B] 0-1 | 背景色（仅参考） |

**适用场景**：歌词卡点字幕、口播重点词闪现、信息流视频字幕切换。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "flash_subtitle",
    "textLayerName": "闪现字幕",
    "beatTimes": [0, 0.6, 1.2, 1.8],
    "flashDuration": 0.05,
    "fontSize": 80,
    "color": [1, 1, 1],
    "bgColor": [0, 0, 0]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "闪现字幕",
      beatTimes: [0, 0.6, 1.2, 1.8],
      flashDuration: 0.05,
      fontSize: 80,
      color: [1, 1, 1],
      bgColor: [0, 0, 0]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = p.fontSize;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var op = layer.property("Opacity");
    var t0 = layer.inPoint;
    op.setValueAtTime(t0, 0);
    for (var i = 0; i < p.beatTimes.length; i++) {
      var bt = t0 + p.beatTimes[i];
      op.setValueAtTime(bt - p.flashDuration, 0);
      op.setValueAtTime(bt, 100);
      if (i < p.beatTimes.length - 1) {
        var nb = t0 + p.beatTimes[i + 1];
        op.setValueAtTime(nb - p.flashDuration, 100);
        op.setValueAtTime(nb, 0);
      }
    }
    for (var k = 1; k <= op.numKeys; k++) {
      op.setInterpolationTypeAtKey(k,
        KeyframeInterpolationType.LINEAR,
        KeyframeInterpolationType.LINEAR);
    }
    layer.property("Position").setValue(
      [comp.width / 2, comp.height * 0.8]);
    _result = {
      status: "success",
      preset: "Flash Subtitle",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 5. 弹幕滚动 (Danmaku Scroll)

**效果描述**：模拟B站/直播弹幕效果，文字从右向左滚动飘过，自动生成多行副本并错开高度，使用 Position 表达式实现基于时间的匀速滚动。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 弹幕滚动 | 任意字符串 | 基础图层名，副本自动编号 |
| scrollSpeed | 400 | 100-1200 | 滚动速度（像素/秒） |
| lineCount | 5 | 1-15 | 弹幕行数（副本数） |
| fontSize | 50 | 30-100 | 字号 |
| color | [1,1,1] | [R,G,B] 0-1 | 弹幕文字色 |
| direction | rtl | rtl/ltr | 滚动方向（右到左/左到右） |

**适用场景**：游戏录屏弹幕、直播切片、互动视频评论流、Vlog趣味弹幕。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "danmaku_scroll",
    "textLayerName": "弹幕滚动",
    "scrollSpeed": 400,
    "lineCount": 5,
    "fontSize": 50,
    "color": [1, 1, 1],
    "direction": "rtl"
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "弹幕滚动",
      scrollSpeed: 400,
      lineCount: 5,
      fontSize: 50,
      color: [1, 1, 1],
      direction: "rtl"
    };
    var baseName = p.textLayerName;
    var srcLayer = comp.layers.byName(baseName);
    if (!srcLayer) {
      var nt = comp.layers.addText(baseName);
      nt.name = baseName;
      srcLayer = nt;
    }
    var st = srcLayer.property("Source Text");
    var td = st.value;
    td.fillColor = p.color;
    td.fontSize = p.fontSize;
    td.applyStroke = true;
    td.strokeColor = [0, 0, 0];
    td.strokeWidth = 2;
    st.setValue(td);
    var dir = p.direction === "rtl" ? 1 : -1;
    var expr = "var sp = " + p.scrollSpeed + ";" +
      "var w = thisComp.width;" +
      "var t = time - inPoint;" +
      "var idx = (index % " + p.lineCount + ");" +
      "var off = idx * 90;" +
      "var x = w + 200 - t * sp * " + dir + ";" +
      "[x, value[1] + off - 200];";
    srcLayer.property("Position").expression = expr;
    for (var i = 1; i < p.lineCount; i++) {
      var dup = srcLayer.duplicate();
      dup.name = baseName + "_" + i;
      dup.property("Position").expression = expr;
      var nst = dup.property("Source Text");
      var ntd = nst.value;
      ntd.fontSize = p.fontSize;
      nst.setValue(ntd);
    }
    _result = {
      status: "success",
      preset: "Danmaku Scroll",
      layer: srcLayer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 6. 表情包文字 (Emoji Text)

**效果描述**：超大加粗描边文字配合高频抖动，模拟微信表情包/抖音热梗大字效果，黄底黑边或亮黄填充加粗黑描边，自带随机抖动。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 表情包文字 | 任意字符串 | 目标文字图层名 |
| fontSize | 200 | 80-400 | 字号（超大） |
| strokeColor | [0,0,0] | [R,G,B] 0-1 | 描边色（黑） |
| fillColor | [1,1,0.2] | [R,G,B] 0-1 | 填充色（亮黄） |
| shake | 15 | 0-50 | 抖动幅度（像素） |
| bgColor | [1,1,1] | [R,G,B] 0-1 | 背景色（仅参考） |

**适用场景**：搞笑段子大字、表情包梗图视频、吐槽强调、综艺花字。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "emoji_text",
    "textLayerName": "表情包文字",
    "fontSize": 200,
    "strokeColor": [0, 0, 0],
    "fillColor": [1, 1, 0.2],
    "shake": 15,
    "bgColor": [1, 1, 1]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "表情包文字",
      fontSize: 200,
      strokeColor: [0, 0, 0],
      fillColor: [1, 1, 0.2],
      shake: 15,
      bgColor: [1, 1, 1]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.fillColor;
    td.applyFill = true;
    td.applyStroke = true;
    td.strokeColor = p.strokeColor;
    td.strokeWidth = 12;
    td.fontSize = p.fontSize;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var pos = layer.property("Position");
    var t0 = layer.inPoint;
    var dur = layer.outPoint - t0;
    var steps = Math.floor(dur / 0.05);
    var baseX = comp.width / 2;
    var baseY = comp.height / 2;
    for (var i = 0; i <= steps; i++) {
      var tt = t0 + i * 0.05;
      var dx = (Math.random() - 0.5) * 2 * p.shake;
      var dy = (Math.random() - 0.5) * 2 * p.shake;
      pos.setValueAtTime(tt, [baseX + dx, baseY + dy]);
    }
    _result = {
      status: "success",
      preset: "Emoji Text",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 7. 卡点故障标题 (Beat Glitch Title)

**效果描述**：节拍点触发文字位置抖动 + RGB偏移故障效果，模拟信号干扰/数字损坏，营造赛博/复古VHS卡点视觉。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 卡点故障标题 | 任意字符串 | 目标文字图层名 |
| beatTimes | [0.4,0.9,1.4,1.9,2.4] | 时间数组 | 故障触发时间点 |
| glitchAmount | 30 | 5-100 | 位置抖动幅度（像素） |
| rgbSplit | 8 | 0-30 | RGB偏移量（像素） |
| color | [0.2,1,0.4] | [R,G,B] 0-1 | 文字色（荧光绿） |
| fontSize | 130 | 60-250 | 字号 |

**适用场景**：赛博朋克/电子风卡点、游戏故障特效、复古VHS转场标题。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "beat_glitch_title",
    "textLayerName": "卡点故障标题",
    "beatTimes": [0.4, 0.9, 1.4, 1.9, 2.4],
    "glitchAmount": 30,
    "rgbSplit": 8,
    "color": [0.2, 1, 0.4],
    "fontSize": 130
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "卡点故障标题",
      beatTimes: [0.4, 0.9, 1.4, 1.9, 2.4],
      glitchAmount: 30,
      rgbSplit: 8,
      color: [0.2, 1, 0.4],
      fontSize: 130
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = p.fontSize;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var pos = layer.property("Position");
    var cx = comp.width / 2;
    var cy = comp.height / 2;
    var t0 = layer.inPoint;
    pos.setValue([cx, cy]);
    for (var i = 0; i < p.beatTimes.length; i++) {
      var bt = t0 + p.beatTimes[i];
      var dx = (Math.random() - 0.5) * 2 * p.glitchAmount;
      pos.setValueAtTime(bt, [cx + dx, cy]);
      pos.setValueAtTime(bt + 0.06, [cx, cy]);
    }
    var off = layer.property("Effects")
      .addProperty("ADBE Offset");
    if (off) {
      var op = off.property("ADBE Offset-0001");
      op.setValue([0, 0]);
      for (var j = 0; j < p.beatTimes.length; j++) {
        var bt2 = t0 + p.beatTimes[j];
        op.setValueAtTime(bt2, [p.rgbSplit, 0]);
        op.setValueAtTime(bt2 + 0.06, [0, 0]);
      }
    }
    _result = {
      status: "success",
      preset: "Beat Glitch Title",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 8. 彩虹渐变标题 (Rainbow Gradient)

**效果描述**：文字色相随时间循环变化，形成流动彩虹效果，配合发光描边，营造梦幻/少女风/童趣视觉。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 彩虹渐变标题 | 任意字符串 | 目标文字图层名 |
| cycleSpeed | 1.0 | 0.1-5.0 | 色相循环速度（周/秒） |
| saturation | 1.0 | 0-1.0 | 饱和度 |
| fontSize | 150 | 60-300 | 字号 |
| glow | 1.2 | 0-3.0 | 发光强度 |
| bgColor | [0,0,0] | [R,G,B] 0-1 | 背景色（仅参考） |

**适用场景**：少女风/童趣视频标题、节日祝福、音乐可视化歌词、梦幻Vlog。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "rainbow_gradient",
    "textLayerName": "彩虹渐变标题",
    "cycleSpeed": 1.0,
    "saturation": 1.0,
    "fontSize": 150,
    "glow": 1.2,
    "bgColor": [0, 0, 0]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "彩虹渐变标题",
      cycleSpeed: 1.0,
      saturation: 1.0,
      fontSize: 150,
      glow: 1.2,
      bgColor: [0, 0, 0]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fontSize = p.fontSize;
    td.applyFill = true;
    td.applyStroke = false;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var fill = layer.property("Effects")
      .addProperty("ADBE Fill");
    if (fill) {
      var fc = fill.property("ADBE Fill-0001");
      fc.expression = "var h = (time * " + p.cycleSpeed +
        " * 360) % 360; hslToRgb([h/360, " +
        p.saturation + ", 0.5, 1]);";
      fill.property("ADBE Fill-0002").setValue(100);
    }
    var glow = layer.property("Effects")
      .addProperty("ADBE Glo 2");
    if (glow) {
      glow.property("ADBE Glo-0001").setValue(20);
      glow.property("ADBE Glo-0002")
        .setValue(p.glow);
    }
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Rainbow Gradient",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 9. 竖屏大字标题 (Vertical Big Title)

**效果描述**：超大字号标题居中显示，带描边加粗，缩放从0放大至110%后回落至100%，适合竖屏视频开场视觉锤。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 竖屏大字标题 | 任意字符串 | 目标文字图层名 |
| fontSize | 280 | 120-500 | 字号（超大） |
| color | [1,1,1] | [R,G,B] 0-1 | 填充色（白） |
| strokeColor | [1,0.2,0.4] | [R,G,B] 0-1 | 描边色（品红） |
| strokeWidth | 8 | 2-20 | 描边宽度 |
| bgColor | [0,0,0] | [R,G,B] 0-1 | 背景色（仅参考） |

**适用场景**：竖屏视频开场标题、品牌slogan、产品发布、口播金句。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "vertical_big_title",
    "textLayerName": "竖屏大字标题",
    "fontSize": 280,
    "color": [1, 1, 1],
    "strokeColor": [1, 0.2, 0.4],
    "strokeWidth": 8,
    "bgColor": [0, 0, 0]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "竖屏大字标题",
      fontSize: 280,
      color: [1, 1, 1],
      strokeColor: [1, 0.2, 0.4],
      strokeWidth: 8,
      bgColor: [0, 0, 0]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.applyFill = true;
    td.applyStroke = true;
    td.strokeColor = p.strokeColor;
    td.strokeWidth = p.strokeWidth;
    td.fontSize = p.fontSize;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var sc = layer.property("Scale");
    var t0 = layer.inPoint;
    sc.setValueAtTime(t0, [0, 0]);
    sc.setValueAtTime(t0 + 0.4, [110, 110]);
    sc.setValueAtTime(t0 + 0.55, [100, 100]);
    for (var k = 1; k <= sc.numKeys; k++) {
      sc.setInterpolationTypeAtKey(k,
        KeyframeInterpolationType.BEZIER,
        KeyframeInterpolationType.BEZIER);
      try {
        var ei = new KeyframeEase(0, 80);
        sc.setTemporalEaseAtKey(k,
          [ei, ei], [ei, ei]);
      } catch(e2) {}
    }
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Vertical Big Title",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 10. 快闪文字 (Quick Flash Text)

**效果描述**：文字在极短节拍间隔内反复闪现并缩放抖动，形成MV快闪/电音踩点效果，节奏感极强。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 快闪文字 | 任意字符串 | 目标文字图层名 |
| beatTimes | [0,0.15,0.3,0.45,0.6,0.75] | 时间数组 | 快闪时间点（密集） |
| flashCount | 6 | 3-20 | 闪现次数 |
| fontSize | 180 | 80-350 | 字号 |
| color | [1,0.3,0.6] | [R,G,B] 0-1 | 文字色（粉红） |
| bgColor | [0,0,0] | [R,G,B] 0-1 | 背景色（仅参考） |

**适用场景**：电音MV快闪、转场卡点、节奏挑战视频、信息轰炸式字幕。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "quick_flash_text",
    "textLayerName": "快闪文字",
    "beatTimes": [0, 0.15, 0.3, 0.45, 0.6, 0.75],
    "flashCount": 6,
    "fontSize": 180,
    "color": [1, 0.3, 0.6],
    "bgColor": [0, 0, 0]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "快闪文字",
      beatTimes: [0, 0.15, 0.3, 0.45, 0.6, 0.75],
      flashCount: 6,
      fontSize: 180,
      color: [1, 0.3, 0.6],
      bgColor: [0, 0, 0]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = p.fontSize;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var op = layer.property("Opacity");
    var sc = layer.property("Scale");
    var t0 = layer.inPoint;
    op.setValueAtTime(t0, 0);
    for (var i = 0; i < p.beatTimes.length; i++) {
      var bt = t0 + p.beatTimes[i];
      op.setValueAtTime(bt, 100);
      op.setValueAtTime(bt + 0.06, 0);
      sc.setValueAtTime(bt, [120, 120]);
      sc.setValueAtTime(bt + 0.06, [80, 80]);
    }
    for (var k = 1; k <= op.numKeys; k++) {
      op.setInterpolationTypeAtKey(k,
        KeyframeInterpolationType.LINEAR,
        KeyframeInterpolationType.LINEAR);
    }
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Quick Flash Text",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 11. 节拍切割 (Beat Cut)

**效果描述**：文字在节拍点瞬间从一侧"切割"滑入到另一侧再回归中心，配合方向模糊与运动模糊，形成凌厉的切割卡点。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 节拍切割 | 任意字符串 | 目标文字图层名 |
| beatTimes | [0.4,0.8,1.2,1.6,2.0] | 时间数组 | 切割时间点 |
| cutDirection | x | x/y | 切割方向（水平/垂直） |
| fontSize | 120 | 60-250 | 字号 |
| color | [1,1,1] | [R,G,B] 0-1 | 文字色 |
| blurAmount | 20 | 0-60 | 方向模糊长度 |

**适用场景**：动作向卡点、街舞/极限运动剪辑、酷炫转场标题。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "beat_cut",
    "textLayerName": "节拍切割",
    "beatTimes": [0.4, 0.8, 1.2, 1.6, 2.0],
    "cutDirection": "x",
    "fontSize": 120,
    "color": [1, 1, 1],
    "blurAmount": 20
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "节拍切割",
      beatTimes: [0.4, 0.8, 1.2, 1.6, 2.0],
      cutDirection: "x",
      fontSize: 120,
      color: [1, 1, 1],
      blurAmount: 20
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = p.fontSize;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var pos = layer.property("Position");
    var cx = comp.width / 2;
    var cy = comp.height / 2;
    var t0 = layer.inPoint;
    pos.setValue([cx, cy]);
    for (var i = 0; i < p.beatTimes.length; i++) {
      var bt = t0 + p.beatTimes[i];
      if (p.cutDirection === "x") {
        pos.setValueAtTime(bt - 0.02, [cx - 300, cy]);
        pos.setValueAtTime(bt + 0.02, [cx + 300, cy]);
        pos.setValueAtTime(bt + 0.12, [cx, cy]);
      } else {
        pos.setValueAtTime(bt - 0.02, [cx, cy - 300]);
        pos.setValueAtTime(bt + 0.02, [cx, cy + 300]);
        pos.setValueAtTime(bt + 0.12, [cx, cy]);
      }
    }
    for (var k = 1; k <= pos.numKeys; k++) {
      pos.setInterpolationTypeAtKey(k,
        KeyframeInterpolationType.LINEAR,
        KeyframeInterpolationType.LINEAR);
    }
    try { layer.motionBlur = true; } catch(e3) {}
    var dirBlur = layer.property("Effects")
      .addProperty("ADBE Directional Blur");
    if (dirBlur) {
      dirBlur.property("ADBE Directional Blur-0001")
        .setValue(0);
      dirBlur.property("ADBE Directional Blur-0002")
        .setValue(p.blurAmount);
    }
    _result = {
      status: "success",
      preset: "Beat Cut",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 12. 字符爆炸 (Character Explosion)

**效果描述**：利用文字动画器（Text Animator + Wiggly Selector）驱动每个字符位置与旋转随机爆炸，配合图层整体缩放收敛，形成文字炸裂消散效果。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 字符爆炸 | 任意字符串 | 目标文字图层名 |
| explodeForce | 300 | 50-800 | 爆炸扩散力（像素） |
| charCount | 8 | 2-20 | 字符数（仅参考） |
| fontSize | 130 | 60-250 | 字号 |
| color | [1,0.6,0.1] | [R,G,B] 0-1 | 文字色（橙） |
| gravity | 200 | 0-500 | 下落重力（像素/秒） |

**适用场景**：片尾消散、爆炸转场、能量释放特效标题、游戏击杀提示。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "character_explosion",
    "textLayerName": "字符爆炸",
    "explodeForce": 300,
    "charCount": 8,
    "fontSize": 130,
    "color": [1, 0.6, 0.1],
    "gravity": 200
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "字符爆炸",
      explodeForce: 300,
      charCount: 8,
      fontSize: 130,
      color: [1, 0.6, 0.1],
      gravity: 200
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = p.fontSize;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var textGrp = layer.property("ADBE Text Properties");
    var animGrp = textGrp.property("ADBE Text Animators");
    var anim = animGrp.addProperty("ADBE Text Animator");
    anim.name = "Explosion";
    anim.property("ADBE Text Selectors")
      .addProperty("ADBE Text Wiggly Selector");
    var posAd = anim.property("ADBE Text Properties")
      .addProperty("ADBE Text Position");
    var f = p.explodeForce;
    var g = p.gravity;
    posAd.expression = "[" + f +
      " * (wiggle(10," + f + ")[0] - 0.5) * 2, -" +
      g + " * (time - inPoint) + " + f +
      " * (wiggle(8," + f + ")[1] - 0.5) * 2]";
    var rotAd = anim.property("ADBE Text Properties")
      .addProperty("ADBE Text Rotation");
    rotAd.expression = "wiggle(5, 180)[0]";
    var sc2 = layer.property("Scale");
    var t0 = layer.inPoint;
    sc2.setValueAtTime(t0 + 0.3, [100, 100]);
    sc2.setValueAtTime(t0 + 0.8, [0, 0]);
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Character Explosion",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 13. 滑动卡点 (Slide Beat)

**效果描述**：文字在节拍点从指定方向滑入中心并停顿，配合缓动关键帧形成有节奏的滑入卡点，多段歌词/标题切换利器。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 滑动卡点 | 任意字符串 | 目标文字图层名 |
| beatTimes | [0.3,0.9,1.5,2.1] | 时间数组 | 滑入时间点 |
| slideDistance | 400 | 100-1000 | 滑入距离（像素） |
| direction | left | left/right/up/down | 滑入方向 |
| fontSize | 110 | 50-220 | 字号 |
| color | [0.3,0.8,1] | [R,G,B] 0-1 | 文字色（天蓝） |

**适用场景**：歌词卡点切换、信息流标题滑入、产品卖点轮播、教程步骤提示。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "slide_beat",
    "textLayerName": "滑动卡点",
    "beatTimes": [0.3, 0.9, 1.5, 2.1],
    "slideDistance": 400,
    "direction": "left",
    "fontSize": 110,
    "color": [0.3, 0.8, 1]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "滑动卡点",
      beatTimes: [0.3, 0.9, 1.5, 2.1],
      slideDistance: 400,
      direction: "left",
      fontSize: 110,
      color: [0.3, 0.8, 1]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = p.fontSize;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var pos = layer.property("Position");
    var cx = comp.width / 2;
    var cy = comp.height / 2;
    var t0 = layer.inPoint;
    var off = p.slideDistance;
    for (var i = 0; i < p.beatTimes.length; i++) {
      var bt = t0 + p.beatTimes[i];
      if (p.direction === "left") {
        pos.setValueAtTime(bt, [cx - off, cy]);
        pos.setValueAtTime(bt + 0.12, [cx, cy]);
      } else if (p.direction === "right") {
        pos.setValueAtTime(bt, [cx + off, cy]);
        pos.setValueAtTime(bt + 0.12, [cx, cy]);
      } else if (p.direction === "up") {
        pos.setValueAtTime(bt, [cx, cy + off]);
        pos.setValueAtTime(bt + 0.12, [cx, cy]);
      } else {
        pos.setValueAtTime(bt, [cx, cy - off]);
        pos.setValueAtTime(bt + 0.12, [cx, cy]);
      }
    }
    for (var k = 1; k <= pos.numKeys; k++) {
      pos.setInterpolationTypeAtKey(k,
        KeyframeInterpolationType.BEZIER,
        KeyframeInterpolationType.BEZIER);
      try {
        var ei = new KeyframeEase(0, 70);
        pos.setTemporalEaseAtKey(k,
          [ei, ei], [ei, ei]);
      } catch(e2) {}
    }
    _result = {
      status: "success",
      preset: "Slide Beat",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 14. 闪烁强调 (Blink Emphasis)

**效果描述**：文字按固定频率闪烁（透明度来回切换），并配合发光强度同步脉冲，形成警示/强调/直播红包雨式视觉提示。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 闪烁强调 | 任意字符串 | 目标文字图层名 |
| blinkRate | 0.15 | 0.05-0.5s | 闪烁周期（秒/次） |
| intensity | 1.5 | 0.5-3.0 | 发光峰值强度 |
| fontSize | 140 | 60-280 | 字号 |
| color | [1,0.9,0.2] | [R,G,B] 0-1 | 文字色（亮黄） |
| glow | 1.5 | 0-4.0 | 发光强度 |

**适用场景**：直播红包雨提示、警示标语、限时秒杀强调、活动倒计时。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "blink_emphasis",
    "textLayerName": "闪烁强调",
    "blinkRate": 0.15,
    "intensity": 1.5,
    "fontSize": 140,
    "color": [1, 0.9, 0.2],
    "glow": 1.5
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "闪烁强调",
      blinkRate: 0.15,
      intensity: 1.5,
      fontSize: 140,
      color: [1, 0.9, 0.2],
      glow: 1.5
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = p.fontSize;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var op = layer.property("Opacity");
    var t0 = layer.inPoint;
    var dur = layer.outPoint - t0;
    var n = Math.floor(dur / p.blinkRate);
    for (var i = 0; i < n; i++) {
      var tt = t0 + i * p.blinkRate;
      op.setValueAtTime(tt, i % 2 === 0 ? 100 : 30);
    }
    var glow = layer.property("Effects")
      .addProperty("ADBE Glo 2");
    if (glow) {
      glow.property("ADBE Glo-0001").setValue(15);
      var gi = glow.property("ADBE Glo-0002");
      var cnt = Math.floor(dur / p.blinkRate);
      for (var j = 0; j < cnt; j++) {
        var tt2 = t0 + j * p.blinkRate;
        gi.setValueAtTime(tt2,
          j % 2 === 0 ? p.glow : 0.3);
      }
    }
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Blink Emphasis",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 15. 弹性入场 (Elastic In)

**效果描述**：文字以弹性回弹方式缩放入场，从0放大至超调峰值后多次收敛震荡至目标尺寸，模拟弹簧物理质感，柔和而有韧性。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | 弹性入场 | 任意字符串 | 目标文字图层名 |
| duration | 1.2 | 0.5-3.0s | 入场动画总时长 |
| elasticity | 0.6 | 0.1-1.0 | 弹性系数，越大震荡越多 |
| overshoot | 1.4 | 1.1-2.0 | 首次超调倍率 |
| baseScale | 100 | 50-200 | 基础缩放百分比 |
| color | [0.5,1,0.7] | [R,G,B] 0-1 | 文字色（薄荷绿） |

**适用场景**：App UI演示动画、清新风Vlog标题、儿童/教育类视频、产品功能介绍。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "elastic_in",
    "textLayerName": "弹性入场",
    "duration": 1.2,
    "elasticity": 0.6,
    "overshoot": 1.4,
    "baseScale": 100,
    "color": [0.5, 1, 0.7]
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: "弹性入场",
      duration: 1.2,
      elasticity: 0.6,
      overshoot: 1.4,
      baseScale: 100,
      color: [0.5, 1, 0.7]
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = 130;
    td.fauxBold = true;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var sc = layer.property("Scale");
    var t0 = layer.inPoint;
    var bs = p.baseScale;
    var ov = bs * p.overshoot;
    var el = p.elasticity;
    sc.setValueAtTime(t0, [0, 0]);
    sc.setValueAtTime(t0 + p.duration * 0.3,
      [ov, ov]);
    sc.setValueAtTime(t0 + p.duration * 0.5,
      [bs * (1 - el * 0.3),
       bs * (1 - el * 0.3)]);
    sc.setValueAtTime(t0 + p.duration * 0.7,
      [bs * (1 + el * 0.15),
       bs * (1 + el * 0.15)]);
    sc.setValueAtTime(t0 + p.duration,
      [bs, bs]);
    for (var k = 1; k <= sc.numKeys; k++) {
      sc.setInterpolationTypeAtKey(k,
        KeyframeInterpolationType.BEZIER,
        KeyframeInterpolationType.BEZIER);
      try {
        var ei = new KeyframeEase(0, 75);
        sc.setTemporalEaseAtKey(k,
          [ei, ei], [ei, ei]);
      } catch(e2) {}
    }
    layer.property("Position").setValue(
      [comp.width / 2, comp.height / 2]);
    _result = {
      status: "success",
      preset: "Elastic In",
      layer: layer.name
    };
  } catch(e) {
    _result = {status:"error", message:e.toString()};
  }
  return JSON.stringify(_result);
})();
```

---

### 章节使用说明

1. **节拍时间获取**：`beatTimes` 数组建议通过音频分析工具（如 Audition 标记、第三方节拍检测）导出后填入，所有时间均为相对图层入点的秒数。
2. **竖屏合成**：本章节预设默认按 1080×1920 竖屏优化，文字自动居中；如用于横屏，`Position` 仍以合成中心为基准，无需改动。
3. **自动建层**：所有预设在目标图层不存在时会自动 `addText` 创建同名图层，便于无侵入调用。
4. **MCP 调用**：通过 `executeAtomScript` 命令传递预设名与参数，JSX 代码由服务端从 `config/text_animation_presets.json` 索引并执行，返回 `{status, preset, layer}` 结构化结果便于下游编排。
5. **颜色规范**：所有颜色均为 `[R, G, B]` 0-1 浮点数组，与 AE 的 `TextDocument.fillColor` / 效果颜色属性直接兼容。

---

## 二、Kinetic Typography 动态排版预设（15种）

本章节聚焦动态排版（Kinetic Typography）领域，通过文字动画器（Text Animator）与范围选择器（Range Selector）的原子级参数组合，实现字符级别的精细动态排版效果。所有预设均基于 `textIndex` 表达式变量实现逐字符差异化动画，调用时通过 MCP `executeAtomScript` 执行对应 JSX 代码，参数经 MCP 注入为脚本作用域变量（缺失时自动套用默认值）。

---

### 1. 字符瀑布流 (Character Waterfall)

**效果描述**：字符从画面上方依次"瀑布式"坠落至各自归位，逐字符延迟入场，形成自上而下的流水节奏感，适合多字符标题的优雅入场。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| duration | 1.0 | 0.3-3.0s | 单字符坠落时长 |
| intensity | 1.0 | 0.5-3.0 | 坠落幅度倍率 |
| stagger | 0.05 | 0.01-0.3s | 逐字符延迟间隔 |
| distance | 200 | 50-600 | 坠落起始偏移（像素） |

**适用场景**：影片标题入场、品牌Logo展示、片头字幕序列、诗歌/歌词逐字呈现。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "character_waterfall",
    "parameters": {
      "textLayerName": "标题文字",
      "duration": 1.2,
      "intensity": 1.0,
      "stagger": 0.04,
      "distance": 240
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var dur = (typeof duration !== "undefined")
            ? duration : 1.0;
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var stg = (typeof stagger !== "undefined")
            ? stagger : 0.05;
        var dist = (typeof distance !== "undefined")
            ? distance : 200;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Character Waterfall";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var pos = anm.addProperty("ADBE Text Position");
        var e = "var s = " + stg + ";";
        e += "var sT = inPoint + textIndex * s;";
        e += "var p = linear(time, sT, sT + " + dur + ", 0, 1);";
        e += "var y = -" + dist + " * " + inten + " * (1 - p);";
        e += "[0, y]";
        pos.expression = e;
        _result = {status:"success",
            preset:"Character Waterfall", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 2. 字距呼吸 (Tracking Breathe)

**效果描述**：字间距（Tracking）随正弦波周期性扩张与收缩，文字如呼吸般"吐纳"，赋予静态文字生命感与韵律感。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| intensity | 1.0 | 0.3-3.0 | 呼吸幅度倍率 |
| speed | 1.0 | 0.2-5.0 | 呼吸频率（Hz） |
| amount | 20 | 5-80 | 字距变化量（像素） |

**适用场景**：宣传片标语呼吸感、音乐MV歌词律动、品牌Slogan持续动效、沉浸式片头。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "tracking_breathe",
    "parameters": {
      "textLayerName": "Slogan",
      "intensity": 1.2,
      "speed": 0.8,
      "amount": 30
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var spd = (typeof speed !== "undefined")
            ? speed : 1.0;
        var amt = (typeof amount !== "undefined")
            ? amount : 20;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Tracking Breathe";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var trk = anm.addProperty("ADBE Text Tracking");
        var e = "var t = time * " + spd + " * 2 * Math.PI;";
        e += "var tr = " + amt + " * " + inten + " * Math.sin(t);";
        e += "tr";
        trk.expression = e;
        _result = {status:"success",
            preset:"Tracking Breathe", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 3. 文字舞蹈 (Text Dance)

**效果描述**：每个字符以 `textIndex` 为相位偏移上下跳舞，形成连绵的舞蹈波浪，字符高低错落如音符跳跃，配合节拍更具表现力。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| intensity | 1.0 | 0.3-3.0 | 舞蹈幅度倍率 |
| speed | 1.5 | 0.2-6.0 | 舞蹈频率（Hz） |
| amount | 50 | 10-200 | 跳跃高度（像素） |

**适用场景**：音乐节奏可视化、欢快短视频标题、儿童/萌系内容字幕、舞蹈教学节拍提示。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "text_dance",
    "parameters": {
      "textLayerName": "Dance",
      "intensity": 1.0,
      "speed": 2.0,
      "amount": 60
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var spd = (typeof speed !== "undefined")
            ? speed : 1.5;
        var amt = (typeof amount !== "undefined")
            ? amount : 50;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Text Dance";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var pos = anm.addProperty("ADBE Text Position");
        var e = "var ph = textIndex * 0.5;";
        e += "var y = " + amt + " * " + inten;
        e += " * Math.sin(time * " + spd + " * 2 * Math.PI + ph);";
        e += "[0, y]";
        pos.expression = e;
        _result = {status:"success",
            preset:"Text Dance", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 4. 弹性变形 (Elastic Morph)

**效果描述**：文字在入场时以衰减正弦波弹性变形，横向拉伸与纵向压缩交替进行，形成"Q弹果冻"般的形变回弹，过冲后稳定归位。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| duration | 1.5 | 0.5-4.0s | 弹性持续时长（影响衰减） |
| intensity | 1.0 | 0.3-2.5 | 形变幅度倍率 |
| amount | 0.3 | 0.1-0.8 | 形变量（比例） |

**适用场景**：App启动页标题、趣味弹窗文字、Q版动画字幕、电商大促标题。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "elastic_morph",
    "parameters": {
      "textLayerName": "弹性标题",
      "duration": 1.8,
      "intensity": 1.2,
      "amount": 0.35
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var dur = (typeof duration !== "undefined")
            ? duration : 1.5;
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var amt = (typeof amount !== "undefined")
            ? amount : 0.3;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Elastic Morph";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var sc = anm.addProperty("ADBE Text Scale");
        var decay = (3 / dur).toFixed(3);
        var freq = (8 / dur).toFixed(3);
        var e = "var t = time - inPoint;";
        e += "var d = " + decay + ";";
        e += "var f = " + freq + ";";
        e += "var el = Math.cos(t * f) * Math.exp(-t * d);";
        e += "var sx = 1 + " + amt + " * " + inten + " * el;";
        e += "var sy = 1 - " + amt + " * " + inten + " * el;";
        e += "[sx * 100, sy * 100]";
        sc.expression = e;
        _result = {status:"success",
            preset:"Elastic Morph", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 5. 节拍弹跳 (Beat Bounce)

**效果描述**：文字以 `Math.abs(Math.sin)` 生成节拍弹跳，每个节拍点上跳一次后回落，弹跳高度随节拍BPM精确同步，形成鼓点般的弹跳节奏。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| intensity | 1.0 | 0.3-3.0 | 弹跳高度倍率 |
| bpm | 120 | 60-200 | 节拍速率（拍/分钟） |
| amount | 100 | 20-300 | 弹跳高度（像素） |

**适用场景**：音乐节拍同步字幕、鼓点卡点标题、运动/健身视频节奏强调、电子舞曲可视化。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "beat_bounce",
    "parameters": {
      "textLayerName": "BEAT",
      "intensity": 1.0,
      "bpm": 128,
      "amount": 120
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var bpm = (typeof bpm !== "undefined") ? bpm : 120;
        var amt = (typeof amount !== "undefined")
            ? amount : 100;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Beat Bounce";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var pos = anm.addProperty("ADBE Text Position");
        var e = "var beat = time * " + bpm + " / 60;";
        e += "var b = Math.abs(Math.sin(beat * Math.PI));";
        e += "var y = -" + amt + " * " + inten + " * b;";
        e += "[0, y]";
        pos.expression = e;
        _result = {status:"success",
            preset:"Beat Bounce", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 6. 字符波浪 (Character Wave)

**效果描述**：字符以 `textIndex` 为相位偏移形成连续波浪起伏，整体如水面涟漪般连绵传递，比"文字舞蹈"更平缓柔和，呈波浪式流动。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| intensity | 1.0 | 0.3-3.0 | 波浪幅度倍率 |
| speed | 1.0 | 0.1-4.0 | 波浪传播速度（Hz） |
| amount | 60 | 10-200 | 波浪高度（像素） |
| phase | 0.4 | 0.1-1.5 | 逐字符相位间隔 |

**适用场景**：水主题/海洋题材字幕、柔和过渡标题、抒情MV歌词波动、品牌柔感标语。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "character_wave",
    "parameters": {
      "textLayerName": "Wave",
      "intensity": 1.0,
      "speed": 0.8,
      "amount": 70,
      "phase": 0.5
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var spd = (typeof speed !== "undefined")
            ? speed : 1.0;
        var amt = (typeof amount !== "undefined")
            ? amount : 60;
        var ph = (typeof phase !== "undefined")
            ? phase : 0.4;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Character Wave";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var pos = anm.addProperty("ADBE Text Position");
        var e = "var ph = textIndex * " + ph + ";";
        e += "var y = " + amt + " * " + inten;
        e += " * Math.sin(time * " + spd + " * 2 * Math.PI + ph);";
        e += "[0, y]";
        pos.expression = e;
        _result = {status:"success",
            preset:"Character Wave", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 7. 旋转排列 (Rotate Array)

**效果描述**：字符以逐字延迟从指定角度旋转归位，旋转量随入场进度线性衰减至0，形成字符依次"旋正"的阵列入场效果。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| duration | 1.0 | 0.3-3.0s | 单字符旋转时长 |
| intensity | 1.0 | 0.3-3.0 | 旋转幅度倍率 |
| stagger | 0.08 | 0.02-0.3s | 逐字符延迟间隔 |
| angle | 180 | 45-720 | 起始旋转角（度） |

**适用场景**：机械感/科技感标题入场、数据可视化标注、转场衔接文字、游戏UI文字。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "rotate_array",
    "parameters": {
      "textLayerName": "ROTATE",
      "duration": 1.0,
      "intensity": 1.0,
      "stagger": 0.06,
      "angle": 360
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var dur = (typeof duration !== "undefined")
            ? duration : 1.0;
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var stg = (typeof stagger !== "undefined")
            ? stagger : 0.08;
        var ang = (typeof angle !== "undefined")
            ? angle : 180;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Rotate Array";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var rot = anm.addProperty("ADBE Text Rotation");
        var e = "var s = " + stg + ";";
        e += "var sT = inPoint + textIndex * s;";
        e += "var p = linear(time, sT, sT + " + dur + ", 0, 1);";
        e += "var r = (1 - p) * " + ang + " * " + inten + ";";
        e += "r";
        rot.expression = e;
        _result = {status:"success",
            preset:"Rotate Array", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 8. 路径流动 (Path Flow)

**效果描述**：字符沿正弦/余弦复合曲线"流动"，X与Y方向以不同相位耦合位移，模拟文字沿曲线路径流淌的视觉，无需Mask路径即可实现流动感。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| intensity | 1.0 | 0.3-3.0 | 流动幅度倍率 |
| speed | 1.0 | 0.1-4.0 | 流动速度（Hz） |
| amount | 80 | 20-250 | 路径幅度（像素） |

**适用场景**：水流/气流主题字幕、丝带式文字动效、有机流动标题、文艺片头字幕。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "path_flow",
    "parameters": {
      "textLayerName": "Flow",
      "intensity": 1.0,
      "speed": 0.6,
      "amount": 90
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var spd = (typeof speed !== "undefined")
            ? speed : 1.0;
        var amt = (typeof amount !== "undefined")
            ? amount : 80;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Path Flow";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var pos = anm.addProperty("ADBE Text Position");
        var e = "var t = time * " + spd + ";";
        e += "var ph = textIndex * 0.3 + t * 2;";
        e += "var x = " + amt + " * 0.3 * " + inten;
        e += " * Math.cos(ph);";
        e += "var y = " + amt + " * " + inten + " * Math.sin(ph);";
        e += "[x, y]";
        pos.expression = e;
        _result = {status:"success",
            preset:"Path Flow", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 9. 频闪闪烁 (Strobe Flicker)

**效果描述**：文字不透明度以高频正弦波在0%与100%间硬切，形成频闪/故障感闪烁，频率越高越接近霓虹灯老化闪烁质感。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| intensity | 1.0 | 0.3-3.0 | 频率倍率（影响闪速） |
| freq | 8 | 1-30 | 基础闪烁频率（Hz） |
| threshold | 0 | -0.9-0.9 | 亮灭切换阈值 |

**适用场景**：故障艺术（Glitch）字幕、警示/警报文字、赛博朋克频闪标题、夜店霓虹老化感。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "strobe_flicker",
    "parameters": {
      "textLayerName": "WARNING",
      "intensity": 1.5,
      "freq": 10,
      "threshold": 0
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var frq = (typeof freq !== "undefined") ? freq : 8;
        var thr = (typeof threshold !== "undefined")
            ? threshold : 0;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Strobe Flicker";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var op = anm.addProperty("ADBE Text Opacity");
        var e = "var f = " + frq + " * " + inten + ";";
        e += "var v = Math.sin(time * f * 2 * Math.PI);";
        e += "v > " + thr + " ? 100 : 0";
        op.expression = e;
        _result = {status:"success",
            preset:"Strobe Flicker", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 10. 文字拉伸 (Text Stretch)

**效果描述**：文字横向缩放随正弦波拉伸收缩，纵向以倒数反向补偿（近似面积守恒），形成"橡皮筋"式横向弹性拉伸效果。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| intensity | 1.0 | 0.3-3.0 | 拉伸幅度倍率 |
| speed | 1.0 | 0.1-4.0 | 拉伸频率（Hz） |
| amount | 0.3 | 0.1-0.8 | 拉伸比例 |

**适用场景**：橡皮筋/弹性标题、呼吸感标语、漫画拟声字、运动品牌动态Logo。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "text_stretch",
    "parameters": {
      "textLayerName": "STRETCH",
      "intensity": 1.0,
      "speed": 1.2,
      "amount": 0.35
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var spd = (typeof speed !== "undefined")
            ? speed : 1.0;
        var amt = (typeof amount !== "undefined")
            ? amount : 0.3;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Text Stretch";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var sc = anm.addProperty("ADBE Text Scale");
        var e = "var s = 1 + " + amt + " * " + inten;
        e += " * Math.sin(time * " + spd + " * 2 * Math.PI);";
        e += "var inv = 1 / s;";
        e += "[s * 100, inv * 100]";
        sc.expression = e;
        _result = {status:"success",
            preset:"Text Stretch", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 11. 3D翻转阵列 (3D Flip Array)

**描述效果**：启用3D图层后，字符以逐字延迟横向缩放（0→100）模拟Y轴翻转，叠加Z轴旋转衰减，形成3D翻转阵列入场效果。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| duration | 1.2 | 0.4-3.0s | 单字符翻转时长 |
| intensity | 1.0 | 0.3-3.0 | 旋转幅度倍率 |
| stagger | 0.1 | 0.02-0.4s | 逐字符延迟间隔 |

**适用场景**：3D空间标题入场、科技/数据感字幕、卡片翻转入场、产品发布标题。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "3d_flip_array",
    "parameters": {
      "textLayerName": "3D FLIP",
      "duration": 1.2,
      "intensity": 1.0,
      "stagger": 0.08
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var dur = (typeof duration !== "undefined")
            ? duration : 1.2;
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var stg = (typeof stagger !== "undefined")
            ? stagger : 0.1;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        layer.threeDLayer = true;
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "3D Flip Array";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var sc = anm.addProperty("ADBE Text Scale");
        var e1 = "var s = " + stg + ";";
        e1 += "var sT = inPoint + textIndex * s;";
        e1 += "var p = linear(time, sT, sT + " + dur + ", 0, 1);";
        e1 += "var pe = easeOut(p, 0, 1, 0, 1);";
        e1 += "[pe * 100, 100]";
        sc.expression = e1;
        var rot = anm.addProperty("ADBE Text Rotation");
        var e2 = "var s = " + stg + ";";
        e2 += "var sT = inPoint + textIndex * s;";
        e2 += "var p = linear(time, sT, sT + " + dur + ", 0, 1);";
        e2 += "var r = (1 - p) * 90 * " + inten + ";";
        e2 += "r";
        rot.expression = e2;
        _result = {status:"success",
            preset:"3D Flip Array", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 12. 字符散聚 (Scatter Converge)

**效果描述**：字符以 `seedRandom(textIndex)` 生成确定性随机散布位置，随时间从散开状态以 `easeOut` 缓动汇聚归位，形成"散→聚"的汇聚入场。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| duration | 1.0 | 0.3-3.0s | 汇聚时长 |
| intensity | 1.0 | 0.3-3.0 | 散布范围倍率 |
| distance | 400 | 100-1000 | 散布半径（像素） |

**适用场景**：粒子汇聚标题、科幻/魔法文字成型、数据聚合可视化、片头字幕凝聚。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "scatter_converge",
    "parameters": {
      "textLayerName": "CONVERGE",
      "duration": 1.2,
      "intensity": 1.0,
      "distance": 500
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var dur = (typeof duration !== "undefined")
            ? duration : 1.0;
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var dist = (typeof distance !== "undefined")
            ? distance : 400;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Scatter Converge";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var pos = anm.addProperty("ADBE Text Position");
        var e = "seedRandom(textIndex, true);";
        e += "var rx = (random() - 0.5) * " + dist;
        e += " * " + inten + ";";
        e += "var ry = (random() - 0.5) * " + dist;
        e += " * " + inten + ";";
        e += "var t = time - inPoint;";
        e += "var p = linear(t, 0, " + dur + ", 0, 1);";
        e += "var m = easeOut(p, 0, 1, 1, 0);";
        e += "[rx * m, ry * m]";
        pos.expression = e;
        _result = {status:"success",
            preset:"Scatter Converge", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 13. 打字抖动 (Typewriter Shake)

**效果描述**：双动画器组合：动画器一以选择器Start关键帧0→100实现逐字"打字机"显隐；动画器二以 `wiggle` 实现逐字符随机抖动，二者叠加形成抖动打字效果。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| duration | 1.5 | 0.5-5.0s | 打字机总时长 |
| intensity | 1.0 | 0.3-3.0 | 抖动幅度倍率 |
| freq | 5 | 1-20 | 抖动频率（Hz） |
| shakeAmount | 15 | 0-60 | 抖动幅度（像素） |

**适用场景**：终端/黑客风格字幕、新闻打字标题、复古计算机文字、悬疑片头字幕。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "typewriter_shake",
    "parameters": {
      "textLayerName": "HACKER",
      "duration": 2.0,
      "intensity": 1.0,
      "freq": 6,
      "shakeAmount": 12
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var dur = (typeof duration !== "undefined")
            ? duration : 1.5;
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var frq = (typeof freq !== "undefined") ? freq : 5;
        var shk = (typeof shakeAmount !== "undefined")
            ? shakeAmount : 15;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm1 = anms.addProperty("ADBE Text Animator");
        anm1.name = "Typewriter";
        var sels1 = anm1.property("ADBE Text Selectors");
        var sel1 = sels1.addProperty("ADBE Text Range Selector");
        sel1.property("ADBE Text Selector End").setValue(100);
        var st = sel1.property("ADBE Text Selector Start");
        var op = anm1.addProperty("ADBE Text Opacity");
        op.setValue(0);
        var ip = layer.inPoint;
        st.setValueAtTime(ip, 0);
        st.setValueAtTime(ip + dur, 100);
        var anm2 = anms.addProperty("ADBE Text Animator");
        anm2.name = "Shake";
        var sels2 = anm2.property("ADBE Text Selectors");
        var sel2 = sels2.addProperty("ADBE Text Range Selector");
        sel2.property("ADBE Text Selector Start").setValue(0);
        sel2.property("ADBE Text Selector End").setValue(100);
        var pos2 = anm2.addProperty("ADBE Text Position");
        var amp = shk * inten;
        var e2 = "seedRandom(textIndex, false);";
        e2 += "wiggle(" + frq + ", " + amp + ")";
        pos2.expression = e2;
        _result = {status:"success",
            preset:"Typewriter Shake", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 14. 节拍缩放 (Beat Scale)

**效果描述**：文字缩放以 `Math.abs(Math.sin)` 节拍脉冲放大收缩，每个节拍点"心跳式"缩放一次，与BPM精确同步，形成与鼓点共振的缩放心跳。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| intensity | 1.0 | 0.3-3.0 | 缩放幅度倍率 |
| bpm | 120 | 60-200 | 节拍速率（拍/分钟） |
| amount | 0.5 | 0.1-1.5 | 缩放比例 |

**适用场景**：心跳/脉搏主题字幕、音乐节拍缩放标题、运动节奏强调、电子音乐可视化。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "beat_scale",
    "parameters": {
      "textLayerName": "PULSE",
      "intensity": 1.0,
      "bpm": 100,
      "amount": 0.6
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var bpm = (typeof bpm !== "undefined") ? bpm : 120;
        var amt = (typeof amount !== "undefined")
            ? amount : 0.5;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Beat Scale";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var sc = anm.addProperty("ADBE Text Scale");
        var e = "var beat = time * " + bpm + " / 60;";
        e += "var p = Math.abs(Math.sin(beat * Math.PI));";
        e += "var s = 1 + " + amt + " * " + inten + " * p;";
        e += "[s * 100, s * 100]";
        sc.expression = e;
        _result = {status:"success",
            preset:"Beat Scale", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

### 15. 字符接力 (Relay Pass)

**效果描述**：字符以 `textIndex` 为延迟依次从右侧滑入并旋转归位，前一个字符动画接近完成时后一个字符启动，形成"接力棒"式的依次传递入场。

**参数表**

| 参数 | 默认值 | 调整范围 | 说明 |
|------|--------|----------|------|
| textLayerName | Text | 任意字符串 | 目标文字图层名 |
| duration | 1.0 | 0.3-3.0s | 单字符动画时长 |
| intensity | 1.0 | 0.3-3.0 | 滑入/旋转幅度倍率 |
| stagger | 0.1 | 0.02-0.4s | 逐字符接力间隔 |
| distance | 120 | 30-400 | 滑入起始偏移（像素） |

**适用场景**：接力/传递主题标题、运动赛事字幕、依次揭晓式入场、节奏感片头序列。

**MCP 调用示例**

```json
{
  "command": "executeAtomScript",
  "params": {
    "preset": "relay_pass",
    "parameters": {
      "textLayerName": "RELAY",
      "duration": 1.0,
      "intensity": 1.0,
      "stagger": 0.12,
      "distance": 150
    }
  }
}
```

**完整 JSX 实现**

```jsx
(function() {
    var _result = {};
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            _result = {status:"error", message:"No active comp"};
            return JSON.stringify(_result);
        }
        var ln = (typeof textLayerName !== "undefined")
            ? textLayerName : "Text";
        var dur = (typeof duration !== "undefined")
            ? duration : 1.0;
        var inten = (typeof intensity !== "undefined")
            ? intensity : 1.0;
        var stg = (typeof stagger !== "undefined")
            ? stagger : 0.1;
        var dist = (typeof distance !== "undefined")
            ? distance : 120;
        var layer = comp.layer(ln);
        if (!layer || !(layer instanceof TextLayer)) {
            _result = {status:"error", message:"Text layer not found"};
            return JSON.stringify(_result);
        }
        var tp = layer.property("ADBE Text Properties");
        var anms = tp.property("ADBE Text Animators");
        var anm = anms.addProperty("ADBE Text Animator");
        anm.name = "Relay Pass";
        var sels = anm.property("ADBE Text Selectors");
        var sel = sels.addProperty("ADBE Text Range Selector");
        sel.property("ADBE Text Selector Start").setValue(0);
        sel.property("ADBE Text Selector End").setValue(100);
        var halfDur = (dur * 0.6).toFixed(3);
        var pos = anm.addProperty("ADBE Text Position");
        var e1 = "var s = " + stg + ";";
        e1 += "var sT = inPoint + textIndex * s;";
        e1 += "var p = linear(time, sT, sT + " + halfDur;
        e1 += ", 0, 1);";
        e1 += "var x = (1 - p) * " + dist + " * " + inten + ";";
        e1 += "[x, 0]";
        pos.expression = e1;
        var rot = anm.addProperty("ADBE Text Rotation");
        var e2 = "var s = " + stg + ";";
        e2 += "var sT = inPoint + textIndex * s;";
        e2 += "var p = linear(time, sT, sT + " + halfDur;
        e2 += ", 0, 1);";
        e2 += "var r = (1 - p) * 45 * " + inten + ";";
        e2 += "r";
        rot.expression = e2;
        _result = {status:"success",
            preset:"Relay Pass", layer:ln};
    } catch(e) {
        _result = {status:"error", message:e.toString()};
    }
    return JSON.stringify(_result);
})();
```

---

> 以上 15 个 Kinetic Typography 动态排版预设均通过 `textIndex` 表达式变量实现逐字符差异化动画，所有 JSX 代码均兼容 AE 2026（ExtendScript ES3），通过 MCP `executeAtomScript` 命令自动化调用。调用前请确保目标合成中存在对应名称的文字图层。


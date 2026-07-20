# AE 文字动画与特效系统深度研究报告

> **版本**: v2.0 | **日期**: 2026-07-14 | **深度**: 企业级 | **覆盖**: 30+效果 · 20+脚本 · 50+预设  
> **适用**: After Effects 2024-2026 | **范畴**: 文字动画架构 · 内置效果 · 高级技术 · 预设体系 · 多语言 · ExtendScript · 学术研究

---

## 目录

1. [文字动画系统架构](#1-文字动画系统架构)
2. [AE内置文字效果完全解析](#2-ae内置文字效果完全解析)
3. [高级文字动画技术](#3-高级文字动画技术)
4. [文字特效预设体系](#4-文字特效预设体系)
5. [多语言文字处理](#5-多语言文字处理)
6. [ExtendScript代码实现](#6-extendscript代码实现)
7. [学术研究参考](#7-学术研究参考)

---

## 1. 文字动画系统架构

### 1.1 Text Animator 三层体系

AE的文字动画系统基于三层架构：**TextAnimatorGroup → TextAnimator → AnimatorProperty**，每一层负责不同的抽象级别。

```
┌─────────────────────────────────────────────────┐
│              Text Layer (文字图层)                │
│  ┌───────────────────────────────────────────┐  │
│  │       TextAnimatorGroup (动画器组)         │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │    TextAnimator (动画器)             │  │  │
│  │  │  ┌─────────────────────────────┐    │  │  │
│  │  │  │  Range Selector (范围选择器) │    │  │  │
│  │  │  │  - Start / End / Offset     │    │  │  │
│  │  │  │  - Units / Shape / Smooth   │    │  │  │
│  │  │  └─────────────────────────────┘    │  │  │
│  │  │  ┌─────────────────────────────┐    │  │  │
│  │  │  │  Animator Properties        │    │  │  │
│  │  │  │  - Position / Scale / Opacity│   │  │  │
│  │  │  │  - Fill Color / Stroke etc. │    │  │  │
│  │  │  └─────────────────────────────┘    │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

#### 1.1.1 TextAnimatorGroup

文字动画器组是文字图层上的容器属性组（`Text.Animators`），一个文字图层可以有多个动画器组，每组独立控制不同的动画属性。

```javascript
// ExtendScript: 获取文字动画器组
var textLayer = app.project.activeItem.layer(1);
var animatorsGroup = textLayer.property("Text").property("Animators");
// 添加新动画器
var animator = animatorsGroup.addProperty("Animator");
```

**关键特性**：
- 多动画器叠加：每个动画器组独立计算，结果叠加
- 选择器类型：Range Selector（范围选择器）、Wiggly Selector（随机选择器）、Expression Selector（表达式选择器）
- 属性隔离：不同动画器组可分别控制Position、Scale、Opacity等

#### 1.1.2 TextAnimator（动画器）

每个动画器包含一个或多个选择器（Selector）和一组动画属性（Animator Properties）。

```javascript
// ExtendScript: 动画器结构
var animator = animatorsGroup.addProperty("Animator");
// 添加选择器
var rangeSelector = animator.property("Selectors").addProperty("Range Selector");
// 添加动画属性
var posProp = animator.property("Properties").addProperty("Position");
var scaleProp = animator.property("Properties").addProperty("Scale");
var opacityProp = animator.property("Properties").addProperty("Opacity");
```

#### 1.1.3 AnimatorProperty（动画属性）

可动画化的文字属性包括：

| 属性类别 | 属性名 | 说明 |
|---------|--------|------|
| 变换 | Position | 位置偏移（x, y） |
| 变换 | Scale | 缩放比例 |
| 变换 | Rotation | 旋转角度 |
| 变换 | Anchor Point | 锚点偏移 |
| 外观 | Opacity | 不透明度 |
| 外观 | Fill Color | 填充颜色 |
| 外观 | Fill Hue/Saturation/Brightness | 填充HSB |
| 外观 | Stroke Color | 描边颜色 |
| 外观 | Stroke Width | 描边宽度 |
| 外观 | Stroke Opacity | 描边不透明度 |
| 排版 | Tracking | 字间距 |
| 排版 | Line Anchor | 行锚点 |
| 排版 | Line Spacing | 行间距 |
| 高级 | Skew | 倾斜 |
| 高级 | Skew Axis | 倾斜轴 |
| 高级 | Blur | 模糊 |
| 高级 | Interletter Blending | 字间混合 |

### 1.2 逐字动画引擎

逐字（Per-Character）动画是AE文字动画的核心能力，通过 **Range Selector** 的 Start/End/Offset 三个参数实现精确控制。

#### 1.2.1 Range Selector 参数详解

| 参数 | 范围 | 说明 |
|------|------|------|
| Start | 0-100% | 选择范围起始位置 |
| End | 0-100% | 选择范围结束位置 |
| Offset | -100~100% | 范围偏移量 |
| Units | 百分比/索引 | 计量单位 |
| Based On | 字符/词/行 | 选择基准 |
| Shape | 方形/上坡/下坡/三角形/圆形/平滑 | 选择范围边缘形状 |
| Smoothness | 0-100% | 边缘平滑度 |
| Ease High | 0-100% | 高侧缓动 |
| Ease Low | 0-100% | 低侧缓动 |

#### 1.2.2 逐字动画实现原理

```
时间轴示例 (End 从0动画到100%):

t=0s:   [████████████████████]  End=0%    → 无文字可见
t=0.5s: [■■■■████████████████]  End=25%   → 前1/4文字动画完成
t=1s:   [■■■■■■■■████████████]  End=50%   → 前半文字动画完成
t=1.5s: [■■■■■■■■■■■■████████]  End=75%   → 3/4文字动画完成
t=2s:   [■■■■■■■■■■■■■■■■■■■■]  End=100%  → 全部文字动画完成

█ = 已完成动画  ░ = 正在过渡  ▓ = 未动画
```

#### 1.2.3 逐字入场动画表达式

```javascript
// 逐字淡入 + 上移动画表达式
// 应用于 Range Selector > End 属性
var dur = 2;        // 总时长(秒)
var stagger = 0.05; // 逐字延迟(秒)
var charIndex = textIndex;  // 当前字符索引
var charTotal = textTotal;  // 总字符数
var t = time - inPoint;
var charDelay = (charIndex / charTotal) * stagger * charTotal;
var progress = linear(t - charDelay, 0, dur, 0, 100);
easeOut(progress, 0, 100);
```

### 1.3 逐词/逐行动画

通过修改 Range Selector 的 **Based On** 属性，可以将选择基准从字符切换为词或行。

#### 1.3.1 逐词动画（Word Selector）

```javascript
// ExtendScript: 设置逐词动画
var rangeSel = animator.property("Selectors").property(1).property("Range Selector 1");
rangeSel.property("Based On").setValue(2); // 1=Characters, 2=Words, 3=Lines
rangeSel.property("Units").setValue(2);    // 1=Percentage, 2=Index
rangeSel.property("Start").setValue(0);
rangeSel.property("End").setValue(1);      // 一次选一个词
```

**逐词动画应用场景**：
- 字幕逐词高亮（卡拉OK效果）
- 逐词淡入的标题动画
- 词语级别的弹跳/缩放强调

#### 1.3.2 逐行动画（Line Selector）

```javascript
// ExtendScript: 设置逐行动画
rangeSel.property("Based On").setValue(3); // Lines
rangeSel.property("Units").setValue(2);    // Index
rangeSel.property("Start").setValue(0);
rangeSel.property("End").setValue(1);      // 一次选一行
```

**逐行动画应用场景**：
- 多行字幕逐行出现
- 列表项逐行入场
- 诗歌/歌词逐行展现

#### 1.3.3 Wiggly Selector（随机选择器）

```javascript
// ExtendScript: 添加随机选择器
var wigglySel = animator.property("Selectors").addProperty("Wiggly Selector");
wigglySel.property("Mode").setValue(1);    // 1=Add, 2=Subtract, 3=Intersect, 4=Min, 5=Max
wigglySel.property("Max Amount").setValue(100);
wigglySel.property("Min Amount").setValue(0);
wigglySel.property("Based On").setValue(1); // Characters
wigglySel.property("Wiggles Per Second").setValue(3);
wigglySel.property("Correlation").setValue(50);
wigglySel.property("Temporal Phase").setValue(0);
wigglySel.property("Spatial Phase").setValue(0);
```

### 1.4 表达式驱动文字动画

AE表达式系统提供了多个文字专用函数和变量，用于实现动态文字效果。

#### 1.4.1 sourceRectAtTime() — 文字边界框

```javascript
// 获取文字图层在指定时间的边界矩形
var rect = sourceRectAtTime(time);
// rect = { top, left, width, height }
// 注意：坐标相对于图层锚点

// 用法1：文字自动居中对齐
var rect = sourceRectAtTime(time);
var centerX = rect.left + rect.width / 2;
var centerY = rect.top + rect.height / 2;
// 修正位置使文字始终居中
transform.position - [centerX, centerY];

// 用法2：创建随文字宽度变化的下划线
var rect = sourceRectAtTime(time);
// 在形状图层上绘制下划线矩形
var w = rect.width;
var h = 2; // 下划线粗细
createPath(
    [[0, 0], [w, 0], [w, h], [0, h]],
    [], [], true
);
```

#### 1.4.2 text.sourceText — 源文字访问

```javascript
// 读取文字内容
var txt = text.sourceText;
// 获取文字样式对象(AE 2020+)
var style = text.sourceText.getStyleAt(0);
// 修改文字内容
text.sourceText = "新文字内容";

// 样式属性访问(AE 2020+)
var fontSize = style.fontSize;
var fontName = style.font;
var fillColor = style.fillColor;
var tracking = style.tracking;
```

#### 1.4.3 textIndex / textTotal — 字符级索引

```javascript
// textIndex: 当前字符在文字中的索引(1-based)
// textTotal: 文字总字符数
// 仅在选择器表达式或文字动画属性表达式中有效

// 示例1：逐字波浪动画(应用于Position属性)
var amp = 20;        // 波浪幅度
var freq = 0.5;      // 频率(每字符)
var speed = 3;       // 时间速度
var y = amp * Math.sin(freq * textIndex + speed * time);
[0, y];

// 示例2：逐字随机延迟淡入(应用于Opacity属性)
var delay = textIndex * 0.03;
var t = Math.max(0, time - inPoint - delay);
var progress = linear(t, 0, 0.5, 0, 100);
easeOut(progress, 0, 100);

// 示例3：螺旋入场(应用于Position属性)
var progress = (textIndex / textTotal);
var angle = progress * Math.PI * 4; // 2圈旋转
var radius = (1 - progress) * 200;  // 从外向内螺旋
var x = Math.cos(angle + time * 2) * radius;
var y = Math.sin(angle + time * 2) * radius;
[x, y];
```

#### 1.4.4 Expression Selector（表达式选择器）

```javascript
// ExtendScript: 添加表达式选择器
var exprSel = animator.property("Selectors").addProperty("Expression Selector");
// 设置表达式(控制每个字符的选择量 0-1)
exprSel.property("Amount").expression = 
    "var progress = textIndex / textTotal;" +
    "var wave = Math.sin(progress * Math.PI * 2 + time * 3);" +
    "(wave + 1) / 2;"; // 输出0-1范围

// 表达式选择器的高级用法：文字呼吸效果
exprSel.property("Amount").expression = 
    "var t = time * 2;" +
    "var breath = Math.sin(t) * 0.5 + 0.5;" +
    "var charWeight = Math.sin(textIndex / textTotal * Math.PI);" +
    "breath * charWeight;";
```

---

## 2. AE内置文字效果完全解析

### 2.1 CC系列文字效果

#### 2.1.1 CC Cylinder — 文字圆柱体

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Radius | Slider | 0-500 | 圆柱半径 |
| Rotation X/Y/Z | Angle | 0-360° | 3D旋转 |
| Light Intensity | Slider | 0-100 | 光照强度 |
| Light Color | Color | - | 光源颜色 |
| Light Height | Slider | 0-90° | 光源仰角 |
| Ambient | Slider | 0-100 | 环境光 |

**应用场景**：3D旋转标题、环形文字滚动、Logo 3D展示

#### 2.1.2 CC Sphere — 文字球体

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Radius | Slider | 0-500 | 球体半径 |
| Rotation X/Y/Z | Angle | 0-360° | 3D旋转 |
| Light Intensity | Slider | 0-100 | 光照强度 |
| Light Color | Color | - | 光源颜色 |
| Light Height | Slider | 0-90° | 光源仰角 |
| Ambient | Slider | 0-100 | 环境光 |

**应用场景**：地球文字、球形Logo、科幻标题

#### 2.1.3 CC Light Burst 2.5 — 光爆效果

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Center | Point | - | 爆发中心 |
| Intensity | Slider | 0-100 | 光爆强度 |
| Ray Length | Slider | 0-500 | 光线长度 |
| Burst | Slider | 1-100 | 爆发密度 |
| Color | Color | - | 光线颜色 |
| Blend w/ Original | Slider | 0-100 | 混合比例 |

**应用场景**：文字背后光爆、标题闪耀、能量释放

#### 2.1.4 CC Light Sweep — 扫光效果

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Center | Point | - | 扫光中心 |
| Direction | Angle | 0-360° | 扫光方向 |
| Shape | Menu | 线性/平滑 | 扫光形状 |
| Width | Slider | 1-100 | 扫光宽度 |
| Sweep Intensity | Slider | 0-100 | 扫光强度 |
| Edge Thickness | Slider | 0-100 | 边缘厚度 |
| Light Color | Color | - | 光线颜色 |
| Light Reception | Menu | - | 光线接收方式 |

**表达式控制扫光动画**：
```javascript
// 自动循环扫光
var cycle = 3; // 秒/次
var t = (time % cycle) / cycle;
var center = [effect("CC Light Sweep")("Center")[0], 
               effect("CC Light Sweep")("Center")[1]];
// 扫光位置从左到右移动
var x = linear(t, 0, 1, -500, sourceRectAtTime(time).width + 500);
[x, center[1]];
```

#### 2.1.5 CC Pixel Polly — 像素碎片化

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Force | Point | - | 碎片力方向与大小 |
| Gravity | Slider | 0-100 | 重力 |
| Spinning | Slider | 0-100 | 旋转量 |
| Rotation | Angle | 0-360° | 旋转方向 |
| Force Random | Slider | 0-100 | 力随机性 |
| Gravity Random | Slider | 0-100 | 重力随机性 |
| Spin Random | Slider | 0-100 | 旋转随机性 |
| Pollys | Menu | 平方/立方 | 碎片形状 |
| Background | Color | - | 背景色 |
| Scatter Speed | Slider | 0-100 | 散射速度 |

**应用场景**：文字碎裂消散、像素化爆炸、故障效果

#### 2.1.6 CC Vibrate — 振动效果

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Vibrate X/Y/Z | Slider | 0-100 | 各轴振幅 |
| Vibration Rate | Slider | 0-100 | 振动频率 |
| Pin Edges | Checkbox | - | 固定边缘 |
| Vibrate Affects | Menu | 位置/缩放/全部 | 影响属性 |

#### 2.1.7 CC WarpoMaatic — 扭曲变形

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Warp Style | Menu | 多种预设 | 扭曲样式 |
| Stretch | Slider | 0-100 | 拉伸量 |
| Intensity | Slider | 0-100 | 强度 |
| Speed | Slider | 0-100 | 速度 |
| Grid Spacing | Slider | 1-50 | 网格间距 |

### 2.2 文字3D效果

#### 2.2.1 3D Text (AE 2026) — 原生3D文字

AE 2026引入了原生3D文字渲染引擎，无需额外插件即可实现立体文字。

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Extrusion Depth | Slider | 0-500 | 挤出深度 |
| Bevel Style | Menu | 无/斜切/圆弧 | 倒角样式 |
| Bevel Depth | Slider | 0-100 | 倒角深度 |
| Bevel Steps | Slider | 1-10 | 倒角步数 |
| Front Material | Group | - | 前面材质 |
| Side Material | Group | - | 侧面材质 |
| Back Material | Group | - | 背面材质 |
| Light Position | Point | - | 光源位置 |
| Light Color | Color | - | 光源颜色 |
| Light Intensity | Slider | 0-100 | 光照强度 |
| Ambient Light | Slider | 0-100 | 环境光 |

#### 2.2.2 Repetile — 重复平铺

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Tile Center | Point | - | 平铺中心 |
| Tile Width | Slider | - | 平铺宽度 |
| Tile Height | Slider | - | 平铺高度 |
| Mirror Edges | Checkbox | - | 镜像边缘 |
| Expand Up/Down/Left/Right | Slider | - | 各方向扩展量 |
| Tiling | Menu | 重复/镜像/混合 | 平铺模式 |

#### 2.2.3 Bevel Alpha / Bevel Edges — 斜面效果

**Bevel Alpha**：基于Alpha通道生成斜面
| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Edge Thickness | Slider | 0-50 | 边缘厚度 |
| Light Angle | Angle | 0-360° | 光源角度 |
| Light Color | Color | - | 光色 |
| Light Intensity | Slider | 0-100 | 光强 |
| Highlight Intensity | Slider | 0-100 | 高光强度 |
| Shadow Intensity | Slider | 0-100 | 阴影强度 |

**Bevel Edges**：基于边缘轮廓生成斜面，参数类似Bevel Alpha但基于几何边缘。

### 2.3 文字发光效果

#### 2.3.1 Sapphire S_Glow — 蓝宝石发光

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Glow Bright | Slider | 0-10 | 发光亮度 |
| Glow Size | Slider | 0-500 | 发光尺寸 |
| Glow Color | Menu | 原色/暖色/冷色/自定义 | 发光颜色模式 |
| Tint Color | Color | - | 自定义色调 |
| Glow Width R/G/B | Slider | - | 各通道发光宽度 |
| Threshold | Slider | 0-1 | 发光阈值 |
| Combine | Menu | 加法/屏幕/混合 | 混合模式 |

#### 2.3.2 BCC Rays Text — BCC光线文字

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Ray Length | Slider | 0-1000 | 光线长度 |
| Ray Intensity | Slider | 0-100 | 光线强度 |
| Ray Angle | Angle | 0-360° | 光线角度 |
| Ray Thickness | Slider | 0-100 | 光线粗细 |
| Number of Rays | Slider | 1-100 | 光线数量 |
| Ray Color | Color | - | 光线颜色 |
| Source Point | Point | - | 光源点 |
| Apply Mode | Menu | - | 应用模式 |

#### 2.3.3 Trapcode Starglow on Text — 星光文字

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Preset | Menu | 12+预设 | 预设选择 |
| Streak Length | Slider | 0-500 | 星光长度 |
| Boost | Slider | 0-10 | 亮度提升 |
| Number of Streaks | Slider | 1-20 | 星光数 |
| Streak Angle Offset | Angle | 0-360° | 角度偏移 |
| Colormap | Gradient | - | 颜色映射 |
| Source Opacity | Slider | 0-100 | 源不透明度 |
| Glow Threshold | Slider | 0-255 | 发光阈值 |
| Glow Radius | Slider | 0-100 | 发光半径 |
| Mask | Layer | - | 遮罩图层 |

### 2.4 文字变形效果

#### 2.4.1 Reshape — 形变

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Source Mask | Menu | - | 源遮罩 |
| Destination Mask | Menu | - | 目标遮罩 |
| Boundary Mask | Menu | - | 边界遮罩 |
| Percent | Slider | 0-100% | 变形百分比 |
| Elasticity | Menu | 刚性/半刚性/流体 | 弹性模式 |

#### 2.4.2 Mesh Warp — 网格扭曲

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Rows | Slider | 1-100 | 网格行数 |
| Columns | Slider | 1-100 | 网格列数 |
| Distortion Mesh | Grid | - | 扭曲网格点 |

#### 2.4.3 Bulge — 凸起

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Bulge Center | Point | - | 凸起中心 |
| Horizontal Radius | Slider | 0-1000 | 水平半径 |
| Vertical Radius | Slider | 0-1000 | 垂直半径 |
| Bulge Height | Slider | -4~4 | 凸起高度(负=凹陷) |
| Pin Edges | Checkbox | - | 固定边缘 |
| Antialiasing | Menu | 低/中/高 | 抗锯齿 |

**凸起动画表达式**：
```javascript
// 呼吸式凸起动画
var freq = 1.5;  // 频率
var amp = 1.5;   // 振幅
var offset = 0;  // 偏移
amp * Math.sin(time * freq * Math.PI * 2) + offset;
```

#### 2.4.4 Turbulent Displace — 湍流位移

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Displacement Amount | Slider | 0-500 | 位移量 |
| Size | Slider | 1-500 | 湍流尺寸 |
| Complexity | Slider | 1-10 | 复杂度 |
| Evolution | Angle | 0-360° | 演化 |
| Evolution Options | Group | - | 演化选项 |
| Horizontal/Vertical Displacement | Slider | 0-100 | 各方向位移 |
| Resize Layer | Checkbox | - | 调整图层大小 |
| Random Seed | Slider | 0-1000 | 随机种子 |
| Noise Type | Menu | 柔和/锐利/锯齿 | 噪声类型 |
| Sub Displacement | Slider | 0-100 | 子位移 |
| Sub Scaling | Slider | 0-100 | 子缩放 |
| Sub Rotation | Angle | 0-360° | 子旋转 |
| Sub Evolution | Angle | 0-360° | 子演化 |
| Pin Edges | Checkbox | - | 固定边缘 |

#### 2.4.5 Liquidify / Twirl

**Liquidify**：基于网格的液态变形工具，交互式拖拽变形  
**Twirl**：旋转扭曲效果，中心点旋转扭曲程度可控

### 2.5 文字遮罩效果

#### 2.5.1 Alpha Matte 文字遮罩技术

```javascript
// ExtendScript: 使用文字图层作为Alpha遮罩
var textLayer = comp.layer("Text Layer");
var targetLayer = comp.layer("Background Layer");
// 设置轨道遮罩
targetLayer.trackMatteType = TrackMatteType.ALPHA; // 使用文字Alpha通道
// 确保文字图层在目标图层上方
textLayer.moveToBeginning();
```

**文字遮罩应用场景**：
- 文字内显示视频（文字填充效果）
- 文字形状的转场遮罩
- 文字揭示/隐藏底层内容

#### 2.5.2 Track Matte 类型

| 类型 | 常量值 | 说明 |
|------|--------|------|
| Alpha | 1 | Alpha遮罩 |
| Alpha Inverted | 2 | Alpha反转遮罩 |
| Luma | 3 | 亮度遮罩 |
| Luma Inverted | 4 | 亮度反转遮罩 |
| No Track Matte | 0 | 无遮罩 |

### 2.6 路径文字

#### 2.6.1 Mask Path 文字动画

```javascript
// ExtendScript: 让文字沿遮罩路径排列
var textLayer = comp.layer("Text Layer");
// 首先创建遮罩
var mask = textLayer.property("ADBE Mask Parade").addProperty("ADBE Mask");
// 设置遮罩路径
var maskPath = mask.property("ADBE Mask Shape");
// 设置文字沿路径
var textProp = textLayer.property("Text");
// Path Options在Text属性组下
var pathOptions = textProp.property("Path Options");
pathOptions.property("Path").setValue(mask.name); // 绑定遮罩路径
pathOptions.property("Reverse Path").setValue(false);
pathOptions.property("Perpendicular To Path").setValue(true); // 垂直于路径
pathOptions.property("Force Alignment").setValue(true); // 强制对齐
pathOptions.property("First Margin").setValue(0);  // 首边距
pathOptions.property("Last Margin").setValue(0);   // 末边距
```

**路径文字表达式动画**：
```javascript
// 沿路径移动文字（First Margin属性表达式）
var speed = 200;  // 像素/秒
var margin = time * speed;
// 可选：添加缓动
margin * ease(time, inPoint, inPoint + 1, 0, 1);
```

---

## 3. 高级文字动画技术

### 3.1 打字机效果 — 5种实现方式

#### 方式1：Range Selector 动画（推荐）

最简洁高效的方式，利用Range Selector的End属性动画。

```javascript
// ExtendScript: 创建Range Selector打字机效果
function createTypewriter_RangeSelector(textLayer, duration) {
    var animator = textLayer.property("Text").property("Animators").addProperty("Animator");
    var selector = animator.property("Selectors").addProperty("Range Selector");
    var opacity = animator.property("Properties").addProperty("Opacity");
    
    // 初始状态：全部透明
    opacity.setValueAtTime(0, 0);
    
    // End从0动画到100%
    selector.property("End").setValueAtTime(0, 0);
    selector.property("End").setValueAtTime(duration, 100);
    
    // 可选：添加光标效果
    // 在End位置添加1%的范围显示不同颜色
    var cursorAnimator = textLayer.property("Text").property("Animators").addProperty("Animator");
    var cursorSel = cursorAnimator.property("Selectors").addProperty("Range Selector");
    cursorSel.property("Start").expression = 
        "var endVal = thisComp.layer('" + textLayer.name + "').text.animator('Animator 1').selector('Range Selector 1').end;" +
        "endVal - 1;";
    cursorSel.property("End").expression = 
        "thisComp.layer('" + textLayer.name + "').text.animator('Animator 1').selector('Range Selector 1').end;";
    var cursorColor = cursorAnimator.property("Properties").addProperty("Fill Color");
    cursorColor.setValue([1, 0.5, 0]); // 橙色光标
    
    return animator;
}
```

#### 方式2：表达式方式

```javascript
// 应用于 Range Selector > End 属性的表达式
var textStr = text.sourceText;
var totalChars = textStr.length;
var typeSpeed = 15;  // 每秒字符数
var startTime = inPoint;
var currentChars = Math.floor((time - startTime) * typeSpeed);
var blinkChar = (Math.floor(time * 2) % 2 === 0) ? "|" : ""; // 闪烁光标
// 更新文字内容
text.sourceText = textStr.substr(0, Math.min(currentChars, totalChars)) + 
    (currentChars < totalChars ? blinkChar : "");
// 返回Range Selector End百分比
(clamp(currentChars, 0, totalChars) / totalChars) * 100;
```

#### 方式3：Text Animator + Expression Selector

```javascript
// Expression Selector实现随机打字机
var exprSel = animator.property("Selectors").addProperty("Expression Selector");
exprSel.property("Amount").expression = 
    "var typeIndex = Math.floor((time - inPoint) * 8);" + // 8字符/秒
    "textIndex <= typeIndex ? 100 : 0;";
```

#### 方式4：ExtendScript逐帧更新

```javascript
// ExtendScript: 逐帧更新文字内容
function createTypewriter_Script(comp, textLayer, fullText, charsPerSec) {
    var totalChars = fullText.length;
    var totalFrames = Math.ceil(totalChars / charsPerSec * comp.frameRate);
    
    for (var f = 0; f <= totalFrames; f++) {
        var t = f / comp.frameRate;
        var charCount = Math.min(Math.floor(f / comp.frameRate * charsPerSec), totalChars);
        var displayText = fullText.substring(0, charCount);
        if (charCount < totalChars) {
            displayText += "|"; // 光标
        }
        textLayer.property("Text").property("Source Text").setValueAtTime(t, displayText);
    }
}
```

#### 方式5：Pre-comp + Linear Wipe

利用Linear Wipe效果在预合成上从左到右擦除，模拟打字机效果。适合简单场景。

### 3.2 文字粒子化

#### 3.2.1 Trapcode Particular 文字爆炸

```javascript
// ExtendScript: 创建文字粒子爆炸效果
function createTextExplode_Particle(comp, textLayerName, particleCount) {
    var textLayer = comp.layer(textLayerName);
    
    // 1. 预合成文字图层
    var precompIndex = comp.layers.precomp([textLayer.index], "Text_Explode_Precomp", true);
    var precompLayer = comp.layer(precompIndex);
    
    // 2. 添加Particular效果
    var particular = precompLayer.Effects.addProperty("Trapcode Particular");
    
    // 3. 设置发射器
    particular.property("Emitter Type").setValue(5); // Layer Grid
    particular.property("Layer").setValue(textLayer.index); // 使用文字图层
    particular.property("Particles/sec").setValue(particleCount);
    particular.property("Velocity").setValue(200);
    particular.property("Velocity Random").setValue(50);
    particular.property("Emitter Size X").setValue(0);
    particular.property("Emitter Size Y").setValue(0);
    
    // 4. 设置粒子外观
    particular.property("Particle Type").setValue(6); // Sprite
    particular.property("Size").setValue(3);
    particular.property("Size Random").setValue(50);
    particular.property("Opacity").setValue(100);
    particular.property("Opacity Over Life").setValue(1); // 渐隐
    
    // 5. 添加物理
    particular.property("Physics Air").property("Gravity").setValue(-100);
    particular.property("Physics Air").property("Wind X").setValue(50);
    
    // 6. 关键帧动画
    particular.property("Particles/sec").setValueAtTime(0, particleCount);
    particular.property("Particles/sec").setValueAtTime(0.1, 0);
    
    return particular;
}
```

#### 3.2.2 CC Pixel Polly 文字碎裂

```javascript
// ExtendScript: CC Pixel Polly文字碎裂
function createTextExplode_PixelPolly(comp, textLayerName) {
    var textLayer = comp.layer(textLayerName);
    var effect = textLayer.Effects.addProperty("CC Pixel Polly");
    
    // 设置碎裂力
    effect.property("Force").setValueAtTime(0, [0, 0]);
    effect.property("Force").setValueAtTime(0.5, [300, -200]); // 爆炸方向
    effect.property("Gravity").setValue(50);
    effect.property("Spinning").setValue(80);
    effect.property("Force Random").setValue(70);
    effect.property("Gravity Random").setValue(50);
    effect.property("Spin Random").setValue(60);
    effect.property("Scatter Speed").setValue(30);
    
    return effect;
}
```

### 3.3 文字流体化

#### 3.3.1 Turbulent Displace + Displacement Map

```javascript
// ExtendScript: 文字流体变形效果
function createTextFluid(comp, textLayerName, intensity, evolutionSpeed) {
    var textLayer = comp.layer(textLayerName);
    var td = textLayer.Effects.addProperty("Turbulent Displace");
    
    td.property("Displacement Amount").setValue(intensity || 30);
    td.property("Size").setValue(80);
    td.property("Complexity").setValue(4);
    td.property("Noise Type").setValue(2); // Spline
    td.property("Evolution").expression = 
        "time * " + (evolutionSpeed || 0.5) + " * 360;";
    td.property("Random Seed").setValue(Math.floor(Math.random() * 1000));
    td.property("Horizontal Displacement").setValue(100);
    td.property("Vertical Displacement").setValue(100);
    td.property("Pin Edges").setValue(true);
    
    // 添加关键帧：渐进出现
    td.property("Displacement Amount").setValueAtTime(0, 0);
    td.property("Displacement Amount").setValueAtTime(1, intensity || 30);
    td.property("Displacement Amount").setValueAtTime(3, intensity || 30);
    td.property("Displacement Amount").setValueAtTime(4, 0);
    
    return td;
}
```

### 3.4 手写文字效果

#### 3.4.1 Trim Paths 方法

```javascript
// ExtendScript: 文字描边手写效果
function createHandwriteText(comp, textLayer, duration) {
    // 1. 从文字图层创建形状图层（需手动或用脚本）
    // 假设已有文字轮廓的形状图层
    var shapeLayer = comp.layers.addShape();
    var shapeGroup = shapeLayer.property("ADBE Root Vectors Group");
    
    // 2. 添加Trim Paths
    var trimPaths = shapeGroup.addProperty("ADBE Vector Filter - Trim");
    trimPaths.property("Start").setValue(0);
    trimPaths.property("End").setValueAtTime(0, 0);
    trimPaths.property("End").setValueAtTime(duration, 100);
    trimPaths.property("Trim Multiple Shapes").setValue(2); // Simultaneously
    
    // 3. 设置描边属性
    var stroke = shapeGroup.addProperty("ADBE Vector Graphic - Stroke");
    stroke.property("Color").setValue([1, 1, 1]);
    stroke.property("Stroke Width").setValue(3);
    stroke.property("Line Cap").setValue(2); // Round
    
    return shapeLayer;
}
```

#### 3.4.2 Write-on 效果方法

```javascript
// ExtendScript: Write-on效果模拟手写
function createHandwrite_WriteOn(comp, textLayer) {
    var effect = textLayer.Effects.addProperty("Write-on");
    // 需要逐帧设置画笔位置关键帧
    // Write-on效果通过Brush Position属性控制画笔路径
    var brushPos = effect.property("Brush Position");
    // 手动设置关键帧点（示例：沿文字轮廓）
    brushPos.setValueAtTime(0, [100, 100]);
    brushPos.setValueAtTime(0.5, [150, 120]);
    brushPos.setValueAtTime(1, [200, 100]);
    brushPos.setValueAtTime(1.5, [250, 130]);
    brushPos.setValueAtTime(2, [300, 100]);
    
    effect.property("Color").setValue([1, 1, 1]);
    effect.property("Brush Size").setValue(5);
    effect.property("Brush Hardness").setValue(80);
    effect.property("Brush Opacity").setValue(100);
    
    return effect;
}
```

### 3.5 文字故障效果（Glitch）

#### 3.5.1 RGB Split（色差分离）

```javascript
// ExtendScript: RGB色差故障效果
function createTextGlitch_RGBSplit(comp, textLayerName, offset) {
    var textLayer = comp.layer(textLayerName);
    offset = offset || 10;
    
    // 方法：复制3层，分别提取R/G/B通道并偏移
    // 层1: Red通道
    var redLayer = textLayer.duplicate();
    redLayer.name = textLayerName + "_R";
    var shiftR = redLayer.Effects.addProperty("Shift Channels");
    shiftR.property("Take Alpha From").setValue(2); // Red
    shiftR.property("Take Red From").setValue(2);   // Red
    shiftR.property("Take Green From").setValue(2);  // Red (discard G/B)
    shiftR.property("Take Blue From").setValue(2);   // Red
    redLayer.property("Position").expression = 
        "var base = transform.position; var glitch = " + offset + " * Math.sin(time * 15); [base[0] + glitch, base[1]];";
    redLayer.moveAfter(textLayer);
    
    // 层2: Green通道（原始位置）
    var greenLayer = textLayer.duplicate();
    greenLayer.name = textLayerName + "_G";
    var shiftG = greenLayer.Effects.addProperty("Shift Channels");
    shiftG.property("Take Red From").setValue(3);   // Green
    shiftG.property("Take Green From").setValue(3);
    shiftG.property("Take Blue From").setValue(3);
    greenLayer.moveAfter(redLayer);
    
    // 层3: Blue通道
    var blueLayer = textLayer.duplicate();
    blueLayer.name = textLayerName + "_B";
    var shiftB = blueLayer.Effects.addProperty("Shift Channels");
    shiftB.property("Take Red From").setValue(4);   // Blue
    shiftB.property("Take Green From").setValue(4);
    shiftB.property("Take Blue From").setValue(4);
    blueLayer.property("Position").expression = 
        "var base = transform.position; var glitch = " + offset + " * Math.sin(time * 15 + 1); [base[0] - glitch, base[1]];";
    blueLayer.moveAfter(greenLayer);
    
    // 原始层隐藏
    textLayer.enabled = false;
    
    // 设置混合模式
    redLayer.property("ADBE Blend Mode").setValue(16);  // Add
    greenLayer.property("ADBE Blend Mode").setValue(16);
    blueLayer.property("ADBE Blend Mode").setValue(16);
    
    return { red: redLayer, green: greenLayer, blue: blueLayer };
}
```

#### 3.5.2 Displacement Map + Turbulent Displace 组合故障

```javascript
// 表达式：间歇性故障触发器（应用于效果开关/Amount属性）
// 只在随机时间点触发故障
var glitchFreq = 5;     // 平均故障频率(次/秒)
var glitchDuration = 0.1; // 故障持续时间(秒)
var seed = Math.floor(time * glitchFreq);
var rand = random(seed);
var isGlitching = rand > 0.7; // 30%概率故障
var timeInGlitch = time - Math.floor(time * glitchFreq) / glitchFreq;
isGlitching && timeInGlitch < glitchDuration ? 100 : 0;
```

### 3.6 文字扫光效果

#### 3.6.1 CC Light Sweep 扫光

```javascript
// ExtendScript: 创建自动扫光效果
function createTextSweep(comp, textLayerName, sweepDuration) {
    var textLayer = comp.layer(textLayerName);
    var sweep = textLayer.Effects.addProperty("CC Light Sweep");
    
    // 计算文字宽度
    var rect = textLayer.sourceRectAtTime(0);
    var textWidth = rect.width;
    var centerX = rect.left + textWidth / 2;
    
    // 扫光中心从左到右
    sweep.property("Center").setValueAtTime(0, [rect.left - 50, rect.top + rect.height / 2]);
    sweep.property("Center").setValueAtTime(sweepDuration, [rect.left + textWidth + 50, rect.top + rect.height / 2]);
    sweep.property("Direction").setValue(0);
    sweep.property("Width").setValue(30);
    sweep.property("Sweep Intensity").setValue(100);
    sweep.property("Light Color").setValue([1, 0.95, 0.8]); // 暖白光
    
    return sweep;
}
```

#### 3.6.2 Linear Wipe + Track Matte 扫光

```javascript
// 方法：使用Linear Wipe在文字上方的渐变层创建扫光带
// 1. 创建渐变形状图层作为扫光带
// 2. 使用Track Matte限制扫光范围在文字内
// 3. Linear Wipe控制扫光进度
```

### 3.7 文字景深效果

#### 3.7.1 Camera Depth of Field

```javascript
// ExtendScript: 文字景深模糊
function createTextDOF(comp, textLayerName, focalDist, aperture) {
    // 1. 启用合成摄像机景深
    var camera = comp.layers.addCamera("DOF Camera", [comp.width/2, comp.height/2]);
    camera.property("ADBE Camera Options Group").property("Depth of Field").setValue(1); // On
    camera.property("ADBE Camera Options Group").property("Focus Distance").setValue(focalDist || 500);
    camera.property("ADBE Camera Options Group").property("Aperture").setValue(aperture || 50);
    camera.property("ADBE Camera Options Group").property("Blur Level").setValue(100);
    
    // 2. 文字图层开启3D
    var textLayer = comp.layer(textLayerName);
    textLayer.threeDLayer = true;
    // 设置Z位置(远离焦平面=更模糊)
    textLayer.property("Position").setValue([comp.width/2, comp.height/2, focalDist ? focalDist + 200 : 700]);
    
    return camera;
}
```

#### 3.7.2 Lens Blur 模拟景深

```javascript
// 使用Lens Blur效果模拟景深(不需要3D图层)
function createTextLensBlur(comp, textLayerName, blurAmount) {
    var textLayer = comp.layer(textLayerName);
    var lensBlur = textLayer.Effects.addProperty("Lens Blur");
    lensBlur.property("Iris Shape").setValue(2); // Triangle
    lensBlur.property("Iris Radius").setValue(blurAmount || 15);
    lensBlur.property("Iris Blade Curvature").setValue(50);
    lensBlur.property("Iris Rotation").setValue(0);
    lensBlur.property("Specular Brightness").setValue(20);
    lensBlur.property("Specular Threshold").setValue(200);
    
    // 动画：渐进模糊
    lensBlur.property("Iris Radius").setValueAtTime(0, 0);
    lensBlur.property("Iris Radius").setValueAtTime(2, blurAmount || 15);
    
    return lensBlur;
}
```

### 3.8 文字3D旋转

#### 3.8.1 3D Layer + Expressions

```javascript
// 文字3D层旋转动画表达式
// 应用于Y Rotation属性
var freq = 0.5;      // 旋转频率(圈/秒)
var easeIn = 0.5;    // 缓入时间
var t = time - inPoint;
var angle = t * freq * 360;
if (t < easeIn) {
    angle = easeOut(t, 0, easeIn, 0, easeIn * freq * 360);
}
angle;

// 3D翻转卡片效果（X Rotation表达式）
var flipTime = 1;    // 翻转时间
var t = clamp((time - inPoint) / flipTime, 0, 1);
// 使用cubic-bezier缓动
var eased = t < 0.5 
    ? 4 * t * t * t 
    : 1 - Math.pow(-2 * t + 2, 3) / 2;
eased * 180; // 翻转180度
```

#### 3.8.2 Element 3D 文字

```javascript
// Element 3D渲染3D文字
// 需要Video Copilot Element 3D插件
// 1. 在文字图层添加Element 3D效果
// 2. 在Element 3D Scene中导入3D文字模型
// 3. 使用Element 3D的材质和灯光系统

// ExtendScript: 添加Element 3D
function addElement3DText(comp, textLayerName) {
    var textLayer = comp.layer(textLayerName);
    var e3d = textLayer.Effects.addProperty("Element 3D");
    // Element 3D的具体参数需要在其面板中设置
    // 脚本主要控制渲染和合成参数
    return e3d;
}
```

---

## 4. 文字特效预设体系

### 4.1 MOGRT文字模板

#### 4.1.1 Essential Graphics面板

MOGRT（Motion Graphics Template）是AE的文字模板标准化格式，允许在Premiere Pro中直接编辑AE制作的文字动画。

```javascript
// ExtendScript: 创建MOGRT文字模板
function createMOGRTTextTemplate(config) {
    /*
    config = {
        compName: "模板名称",
        width: 1920,
        height: 1080,
        textLayers: [
            { name: "主标题", defaultText: "输入标题", fontSize: 72, font: "Microsoft YaHei" },
            { name: "副标题", defaultText: "输入副标题", fontSize: 36, font: "Microsoft YaHei" }
        ],
        controls: [
            { name: "动画速度", type: "slider", min: 0.1, max: 5, default: 1 },
            { name: "主色调", type: "color", default: [1, 1, 1] },
            { name: "启用扫光", type: "checkbox", default: true }
        ]
    };
    */
    
    var comp = app.project.items.addComp(
        config.compName, config.width, config.height, 
        1, 10, 30 // 10秒, 30fps
    );
    
    // 创建文字图层
    for (var i = 0; i < config.textLayers.length; i++) {
        var tl = config.textLayers[i];
        var textLayer = comp.layers.addText(tl.defaultText);
        textLayer.name = tl.name;
        
        // 设置字体属性
        var textDoc = textLayer.property("Text").property("Source Text").value;
        textDoc.fontSize = tl.fontSize;
        textDoc.font = tl.font;
        textLayer.property("Text").property("Source Text").setValue(textDoc);
        
        // 添加到Essential Graphics
        // AE 2020+ 支持脚本操作Essential Graphics
        if (app.version >= "17.0") {
            // 通过essentialGraphics API添加可编辑属性
            // textLayer.addToEssentialGraphics("Source Text");
        }
    }
    
    // 创建表达式控制
    var nullLayer = comp.layers.addNull();
    nullLayer.name = "Controls";
    
    for (var j = 0; j < config.controls.length; j++) {
        var ctrl = config.controls[j];
        var effect;
        switch (ctrl.type) {
            case "slider":
                effect = nullLayer.Effects.addProperty("ADBE Slider Control");
                effect.name = ctrl.name;
                effect.property("Slider").setValue(ctrl.default);
                break;
            case "color":
                effect = nullLayer.Effects.addProperty("ADBE Color Control");
                effect.name = ctrl.name;
                effect.property("Color").setValue(ctrl.default);
                break;
            case "checkbox":
                effect = nullLayer.Effects.addProperty("ADBE Checkbox Control");
                effect.name = ctrl.name;
                effect.property("Checkbox").setValue(ctrl.default ? 1 : 0);
                break;
            case "angle":
                effect = nullLayer.Effects.addProperty("ADBE Angle Control");
                effect.name = ctrl.name;
                effect.property("Angle").setValue(ctrl.default || 0);
                break;
            case "point":
                effect = nullLayer.Effects.addProperty("ADBE Point Control");
                effect.name = ctrl.name;
                if (ctrl.default) effect.property("Point").setValue(ctrl.default);
                break;
        }
    }
    
    return comp;
}
```

### 4.2 表达式控制文字

#### 4.2.1 控制器类型与应用

| 控制器 | 效果名 | 典型应用 |
|--------|--------|----------|
| Slider Control | ADBE Slider Control | 动画速度、间距、强度 |
| Checkbox Control | ADBE Checkbox Control | 开关效果、模式选择 |
| Color Control | ADBE Color Control | 主色调、发光颜色 |
| Angle Control | ADBE Angle Control | 旋转角度、方向 |
| Point Control | ADBE Point Control | 位置点、中心点 |

#### 4.2.2 Slider Control 驱动文字动画

```javascript
// 在文字图层中引用Slider Control的表达式
var ctrl = thisComp.layer("Controls");
var speed = ctrl.effect("Animation Speed")("Slider");
var intensity = ctrl.effect("Intensity")("Slider");

// Range Selector End表达式
var t = (time - inPoint) * speed;
linear(t, 0, 2, 0, 100);

// Position表达式
var y = Math.sin(time * speed * 2) * intensity;
[0, y];
```

### 4.3 文字响应式设计

#### 4.3.1 sourceRectAtTime() 自动适配

```javascript
// 文字框自动适配（背景框随文字宽度变化）
// 应用于Shape Layer的Size属性
var textLayer = thisComp.layer("Title Text");
var rect = textLayer.sourceRectAtTime(time);
var padding = 40; // 内边距
[rect.width + padding * 2, rect.height + padding * 2];

// 文字框位置跟随
// 应用于Shape Layer的Position属性
var textLayer = thisComp.layer("Title Text");
var rect = textLayer.sourceRectAtTime(time);
var textPos = textLayer.transform.position;
var padding = 40;
[textPos[0] - padding, textPos[1] - padding];

// 多行文字自动高度
// 应用于Shape Layer的高度
var textLayer = thisComp.layer("Body Text");
var rect = textLayer.sourceRectAtTime(time);
var minHeight = 100;
var padding = 30;
Math.max(rect.height + padding * 2, minHeight);
```

#### 4.3.2 文字自动缩放防溢出

```javascript
// 表达式：文字自动缩放以适应容器
var maxWidth = 800;  // 最大宽度
var textRect = sourceRectAtTime(time);
var currentWidth = textRect.width;
var scale = transform.scale[0];

if (currentWidth > maxWidth) {
    scale = (maxWidth / currentWidth) * 100;
}
[scale, scale];
```

### 4.4 文字动画预设库

#### 4.4.1 入场动画预设（15+）

| 预设名 | 类型 | 描述 | 关键参数 |
|--------|------|------|----------|
| Fade In | 基础 | 淡入 | Duration, Ease |
| Typewriter | 经典 | 打字机 | Speed, Cursor |
| Rise Up | 常用 | 上移淡入 | Distance, Duration |
| Drop Down | 重力 | 下落弹跳 | Bounce, Gravity |
| Scale Pop | 强调 | 缩放弹出 | Scale, Overshoot |
| Blur In | 柔和 | 模糊淡入 | Blur Amount |
| Slide Left | 方向 | 左滑入 | Distance, Ease |
| Slide Right | 方向 | 右滑入 | Distance, Ease |
| Rotate In | 旋转 | 旋转进入 | Angle, Axis |
| Flip In | 3D | 翻转进入 | Flip Angle |
| Bounce In | 物理 | 弹跳进入 | Bounces, Damping |
| Elastic In | 物理 | 弹性进入 | Amplitude, Period |
| Per Char Fade | 逐字 | 逐字淡入 | Stagger, Duration |
| Per Char Rise | 逐字 | 逐字上移 | Stagger, Distance |
| Per Char Spin | 逐字 | 逐字旋转 | Stagger, Angle |
| Wave In | 波浪 | 波浪入场 | Amplitude, Frequency |
| Spiral In | 特殊 | 螺旋进入 | Radius, Rotations |

#### 4.4.2 出场动画预设（10+）

| 预设名 | 类型 | 描述 |
|--------|------|------|
| Fade Out | 基础 | 淡出 |
| Sink Down | 重力 | 下沉消失 |
| Scale Collapse | 缩放 |
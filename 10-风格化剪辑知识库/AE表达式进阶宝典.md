---
title: AE表达式进阶宝典（完整版）
date: 2026-07-03
updated: 2026-07-12
related_docs:
  - "[[AE表达式与脚本完全手册]] - 表达式与脚本基础完全手册（本文为进阶宝典）"
tags:
  - 表达式
  - 进阶
  - 动画
  - 弹性
  - 物理
  - 音频驱动
  - 3D
  - 文字动画
  - 时间控制
sources:
  - motionscript.com (Dan Ebberts)
  - School of Motion
  - Adobe 官方表达式文档
  - Creative COW 社区
  - ae-expressions.docsforadobe.dev
---
# AE 表达式进阶宝典（完整版）

> 表达式是 AE 的真正威力所在——一行代码可以替代数十个关键帧。本宝典系统化覆盖物理模拟、运动控制、循环随机、音频驱动、3D 空间、文字动画、时间操控、高级模式等十二大领域，共收录 150+ 实战表达式，是 AE 高级用户的案头工具书。

---

## 一、表达式进阶基础

### 1.1 表达式引擎对比（Legacy vs JavaScript）

AE 自 CC 2019 起提供两种表达式引擎：

| 特性 | Legacy ExtendScript 引擎 | JavaScript 引擎（推荐） |
|------|--------------------------|--------------------------|
| 基础语言 | ES3 标准 | ES2018+ 现代 JS |
| 性能 | 较慢，逐行解释 | JIT 编译，速度提升 5× 以上 |
| 数组操作 | 不支持解构 | 支持解构、扩展运算符 |
| `let` / `const` | 不支持 | 完全支持 |
| 箭头函数 | 不支持 | 完全支持 |
| `for...of` | 不支持 | 完全支持 |
| 模板字符串 | 不支持 | 完全支持 |
| 默认参数 | 不支持 | 完全支持 |
| 调试体验 | 报错含糊 | 错误信息更精准 |
| 兼容性 | 老项目、老脚本 | 新项目首选 |

**切换方法**：`文件 → 项目设置 → 表达式引擎`，选择 `JavaScript`。

**迁移注意事项**：
- Legacy 中 `$.global` 全局对象在 JS 引擎中不可用
- Legacy 中部分 ExtendScript API（如 `File`、`Folder`）在 JS 引擎中需要通过不同方式访问
- 数组索引访问语法两种引擎都支持，但解构赋值仅 JS 引擎支持
- 条件表达式 `? :` 两种引擎都支持

### 1.2 表达式性能优化原则

**核心原则**：表达式在每一帧都会重新求值，性能瓶颈通常来自循环和跨图层引用。

| 优化策略 | 说明 | 示例 |
|----------|------|------|
| **避免深层循环** | 循环嵌套不超过 2 层 | 单层 for 循环代替嵌套 |
| **缓存计算结果** | 重复计算提到循环外 | `var pi = Math.PI;` 而非循环内反复调用 |
| **减少跨图层引用** | `thisComp.layer()` 每次都是开销 | 用 `L = thisComp.layer("X");` 缓存 |
| **优先使用内置函数** | `linear`、`ease` 比 `if/else` 快 | 用 `linear(t,0,1,0,100)` 代替手动插值 |
| **避免 `valueAtTime` 滥用** | 每次调用都触发历史计算 | 必要时再使用 |
| **使用 `posterizeTime`** | 降低表达式帧率 | `posterizeTime(12);` 降到 12fps |
| **分离表达式属性** | 同一表达式不要服务多属性 | 拆分为多个表达式 |
| **使用 `enable expressions`** | 不需要时整体关闭 | 调试时临时禁用 |

### 1.3 表达式调试技巧

```javascript
// 1. 通过文本图层打印变量值
text.sourceText = "当前值: " + value + " 时间: " + time;

// 2. 使用 try-catch 静默失败
try {
    // 可能出错的表达式
    result = thisComp.layer("可能不存在").transform.position;
} catch (e) {
    result = value; // 失败时回退到默认值
}

// 3. 使用注释快速切换逻辑
// 选项 A：调试模式
debug = true;
if (debug) {
    // 输出调试信息
    [value[0], value[1], 0]; // 强制显示
} else {
    value;
}

// 4. 检查图层是否存在
function layerExists(name) {
    try {
        thisComp.layer(name);
        return true;
    } catch (e) {
        return false;
    }
}

// 5. 使用 $.level 调试（仅 Legacy 引擎）
// $.level = 1; // 开启调试输出
```

**调试工作流**：
1. 在表达式字段右上角点击 `=` 图标，可临时禁用/启用
2. 错误信息会显示在表达式字段下方红条中
3. 选中属性后按 `EE` 可快速跳转到表达式
4. 使用 `另存为表达式预设` 保存调试好的表达式

### 1.4 表达式最佳实践

| 实践 | 说明 |
|------|------|
| **使用语义化变量名** | `springStiffness` 而非 `a` |
| **参数集中声明** | 开头统一声明所有可调参数 |
| **添加注释** | 关键逻辑、参数含义、使用说明 |
| **保留 `value` 作为基础** | 多数表达式以 `value + 增量` 结束 |
| **维度匹配** | 一维属性返回数字，二维返回 `[x,y]` |
| **避免硬编码** | 用 `thisLayer`、`thisComp` 替代绝对名称 |
| **处理边界情况** | `numKeys === 0`、`index === 1` 等 |
| **使用括号明确优先级** | `(a + b) * c` 而非 `a + b * c` |

### 1.5 表达式与关键帧的混合使用

```javascript
// 方式 1：表达式叠加在关键帧之上
// 关键帧定义主运动，表达式添加细节抖动
value + wiggle(2, 5); // 在关键帧动画基础上抖动

// 方式 2：表达式引用关键帧
// 根据最近关键帧触发弹性
n = nearestKey(time).index;
if (key(n).time > time) n--;
t = time - key(n).time;
v = velocityAtTime(key(n).time - 0.01);
value + v * 0.1 * Math.sin(t * 20) / Math.exp(t * 3);

// 方式 3：条件切换关键帧 vs 表达式
useExpression = effect("使用表达式")("开关");
if (useExpression) {
    wiggle(2, 50);
} else {
    value;
}

// 方式 4：时间分段 — 前半段关键帧，后半段表达式
if (time < 2) {
    value; // 关键帧区间
} else {
    // 表达式接管，从关键帧末值开始
    startVal = valueAtTime(2);
    startVal + Math.sin((time - 2) * 3) * 20;
}
```

---

## 二、物理模拟表达式（15 个）

### 2.1 重力模拟

**效果描述**：模拟自由落体，物体随时间加速下落。

```javascript
// 应用到 Position
g = 980;            // 重力加速度（像素/秒²）
v0 = [0, 0];        // 初速度
t0 = 0;             // 起始时间
t = time - t0;
pos = value + [v0[0] * t, v0[1] * t + 0.5 * g * t * t];
pos;
```

**参数说明**：
- `g`：重力强度，正值向下，980 接近真实地球重力
- `v0`：初始速度向量 `[x, y]`
- `t0`：起始下落时间

**使用方法**：应用到图层的 Position 属性，配合关键帧定义起始位置。

### 2.2 弹簧模拟

**效果描述**：基于胡克定律的真实弹簧物理，物体被拉离原位后弹性回弹。

```javascript
// 应用到 Position
rest = [960, 540];       // 静止位置
stiffness = 80;          // 刚度（弹性强度）
damping = 8;             // 阻尼（决定停下来快慢）
mass = 1;                // 质量

p = value;
v = [0, 0];
dt = thisComp.frameDuration;
steps = 4;               // 子步数（提高精度）

for (i = 0; i < steps; i++) {
    force = [
        (rest[0] - p[0]) * stiffness / mass,
        (rest[1] - p[1]) * stiffness / mass
    ];
    v = [v[0] + force[0] * dt, v[1] + force[1] * dt];
    v = [v[0] * (1 - damping * dt / mass), v[1] * (1 - damping * dt / mass)];
    p = [p[0] + v[0] * dt, p[1] + v[1] * dt];
}
p;
```

**参数说明**：`stiffness` 越大弹得越快；`damping` 越大停得越早；`mass` 越大运动越缓。

### 2.3 弹跳球

**效果描述**：球落地反弹，每次反弹高度递减直至停止。

```javascript
// 应用到 Position 的 Y 分量
t0 = inPoint;
t = time - t0;
g = 2000;                // 重力
v0 = -1200;              // 初始向上速度
bounces = 8;             // 反弹次数
damping = 0.6;           // 反弹衰减

y = value[1];
for (i = 0; i < bounces; i++) {
    bounceTime = (-2 * v0) / g * (1 + i);
    if (t < bounceTime) {
        y = value[1] + v0 * t + 0.5 * g * t * t;
        break;
    }
    v0 = v0 * damping * -1;
    t = t - bounceTime + (-2 * v0) / g;
}
[value[0], y];
```

### 2.4 摆锤运动

**效果描述**：模拟单摆运动，物体绕固定点周期摆动并衰减。

```javascript
// 应用到 Rotation
length = 200;            // 摆长
g = 980;                 // 重力
amp = 45;                // 初始角度（度）
damping = 0.5;           // 阻尼系数
t0 = inPoint;

omega = Math.sqrt(g / length); // 角频率
angle = amp * Math.cos(omega * (time - t0)) * Math.exp(-damping * (time - t0));
angle;
```

### 2.5 惯性运动

**效果描述**：物体跟随引导层运动，但有惯性延迟，停止后会"过冲"再回正。

```javascript
// 应用到 Position
leader = thisComp.layer("Leader");
lag = 0.2;               // 延迟时间
overshoot = 0.15;        // 过冲强度
damping = 4;             // 衰减

target = leader.position.valueAtTime(time - lag);
v = leader.position.velocityAtTime(time - lag);
delta = v * overshoot * Math.exp(-damping * 0.1);
value + (target - value) + delta;
```

### 2.6 摩擦力

**效果描述**：物体运动时受摩擦力影响逐渐减速直至停止。

```javascript
// 应用到 Position
v0 = [200, 100];         // 初速度
friction = 0.95;         // 摩擦系数（每帧保留比例）
t0 = inPoint;
dt = thisComp.frameDuration;

v = v0;
p = value;
t = time - t0;
frames = Math.floor(t / dt);
for (i = 0; i < frames; i++) {
    p = [p[0] + v[0] * dt, p[1] + v[1] * dt];
    v = [v[0] * friction, v[1] * friction];
}
p;
```

### 2.7 碰撞检测

**效果描述**：两个物体接近时触发响应，例如颜色变化或反弹。

```javascript
// 应用到任意属性，输出 0 或 1 表示是否碰撞
objA = thisComp.layer("BallA");
objB = thisComp.layer("BallB");
threshold = 100;         // 碰撞距离

dist = length(objA.position, objB.position);
if (dist < threshold) 1 else 0;
```

**进阶版（含反弹）**：

```javascript
// 应用到 BallA 的 Position
ballB = thisComp.layer("BallB");
threshold = 100;
elasticity = 0.8;

dir = value - ballB.position;
dist = length(dir);
if (dist < threshold && dist > 0) {
    push = (threshold - dist) * elasticity;
    norm = normalize(dir);
    value + norm * push;
} else {
    value;
}
```

### 2.8 风力效果

**效果描述**：物体受持续风力影响，带湍流扰动。

```javascript
// 应用到 Position
windDir = [1, 0];        // 风向
windStrength = 50;       // 风力强度
turbulence = 20;         // 湍流幅度
turbFreq = 1.5;          // 湍流频率

t = time - inPoint;
wind = [windDir[0] * windStrength * t, windDir[1] * windStrength * t];
wob = [wiggle(turbFreq, turbulence)[0] - value[0], wiggle(turbFreq, turbulence)[1] - value[1]];
value + wind + wob * 0.3;
```

### 2.9 磁力效果

**效果描述**：物体被磁铁吸引，距离越近吸引力越强。

```javascript
// 应用到 Position
magnet = thisComp.layer("Magnet").position;
strength = 50000;        // 磁力强度
maxDist = 600;           // 最大作用距离

dir = magnet - value;
dist = length(dir);
if (dist < maxDist && dist > 5) {
    force = strength / (dist * dist);
    value + normalize(dir) * force;
} else {
    value;
}
```

### 2.10 引力效果

**效果描述**：多个引力源（如行星）共同作用，类似万有引力。

```javascript
// 应用到 Position
planets = ["Planet1", "Planet2", "Planet3"];
G = 5000;                // 引力常数
totalForce = [0, 0];

for (i = 0; i < planets.length; i++) {
    try {
        p = thisComp.layer(planets[i]).position;
        dir = p - value;
        dist = length(dir);
        if (dist > 10) {
            f = G / (dist * dist);
            totalForce += normalize(dir) * f;
        }
    } catch (e) {}
}
value + totalForce * 0.1;
```

### 2.11 浮力效果

**效果描述**：物体在液体中受浮力影响，有上下波动。

```javascript
// 应用到 Position 的 Y 分量
waterLevel = 540;        // 水面 Y 坐标
density = 0.8;           // 物体密度（<1 浮，>1 沉）
buoyancy = 200;          // 浮力强度
waveAmp = 10;            // 波浪幅度
waveFreq = 1;            // 波浪频率

y = value[1];
if (y > waterLevel) {
    // 在水中
    wave = Math.sin(time * waveFreq * 2 * Math.PI) * waveAmp;
    y = waterLevel + wave + (y - waterLevel) * (1 - density);
}
[value[0], y];
```

### 2.12 流体阻力

**效果描述**：物体在流体中运动时受到与速度成正比的阻力。

```javascript
// 应用到 Position
v0 = [300, 0];           // 初速度
drag = 2;                // 阻力系数
t0 = inPoint;
t = time - t0;

// 解析解：v(t) = v0 * exp(-drag * t)
vx = v0[0] * Math.exp(-drag * t);
vy = v0[1] * Math.exp(-drag * t);
// 位置积分
x = value[0] + v0[0] * (1 - Math.exp(-drag * t)) / drag;
y = value[1] + v0[1] * (1 - Math.exp(-drag * t)) / drag;
[x, y];
```

### 2.13 弹性变形

**效果描述**：物体挤压拉伸，模拟软体撞击时的形变。

```javascript
// 应用到 Scale
stretch = 1.3;           // 最大拉伸倍数
squash = 0.7;            // 最大挤压倍数
freq = 8;                // 振荡频率
decay = 3;               // 衰减

// 检测撞击（Y 速度突变）
v = velocityAtTime(time - thisComp.frameDuration);
speed = length(v);
if (speed > 200) {
    t = time - nearestKey(time).time;
    deform = Math.sin(freq * t) * Math.exp(-decay * t);
    sx = 1 + (stretch - 1) * deform;
    sy = 1 - (1 - squash) * deform;
    [value[0] * sx, value[1] * sy];
} else {
    value;
}
```

### 2.14 刚体运动

**效果描述**：刚体不变形，仅做平移和旋转。

```javascript
// 应用到 Rotation（结合 Position 关键帧）
velocity = position.velocityAtTime(time);
angle = Math.atan2(velocity[1], velocity[0]) * 180 / Math.PI;
// 平滑过渡
smooth = 0.3;
angle = angle * smooth + value * (1 - smooth);
angle;
```

### 2.15 软体动力学

**效果描述**：模拟果冻/布丁等软体质感，多方向波动。

```javascript
// 应用到 Scale
jiggle = 0.15;           // 抖动幅度
freq = 4;                // 抖动频率
decay = 2;               // 衰减

t = time - inPoint;
wave1 = Math.sin(freq * t * 2 * Math.PI) * Math.exp(-decay * t);
wave2 = Math.cos(freq * t * 1.5 * 2 * Math.PI) * Math.exp(-decay * t * 0.8);

sx = 1 + jiggle * wave1;
sy = 1 - jiggle * wave1 * 0.8 + jiggle * wave2 * 0.2;
[sx * value[0], sy * value[1]];
```

---

## 三、运动控制表达式（15 个）

### 3.1 自动跟踪

**效果描述**：图层自动跟踪另一个图层的位置。

```javascript
// 应用到 Position
target = thisComp.layer("Target");
delay = 0;               // 延迟（秒）
target.position.valueAtTime(time - delay);
```

### 3.2 路径跟随

**效果描述**：物体沿 mask 路径运动。

```javascript
// 应用到 Position
path = thisComp.layer("PathLayer").mask("Mask 1").maskPath;
progress = (time - inPoint) / (outPoint - inPoint);
progress = clamp(progress, 0, 1);
path.pointOnPath(progress);
```

**带方向旋转版本**：

```javascript
// 应用到 Rotation
path = thisComp.layer("PathLayer").mask("Mask 1").maskPath;
progress = clamp((time - inPoint) / (outPoint - inPoint), 0, 1);
tangent = path.tangentOnPath(progress);
angle = Math.atan2(tangent[1], tangent[0]) * 180 / Math.PI;
angle;
```

### 3.3 方向计算

**效果描述**：自动计算运动方向，让物体"面向"运动方向。

```javascript
// 应用到 Rotation
v = transform.position.velocityAtTime(time);
if (length(v) > 1) {
    Math.atan2(v[1], v[0]) * 180 / Math.PI;
} else {
    value;
}
```

### 3.4 速度计算

**效果描述**：输出当前运动速度，可用于驱动其他属性。

```javascript
// 应用到 Slider Control
v = thisComp.layer("Moving").position.velocityAtTime(time);
speed = length(v);
speed;
```

### 3.5 加速度计算

**效果描述**：计算加速度，用于触发特效或反馈。

```javascript
// 应用到 Slider Control
v1 = thisComp.layer("Moving").position.velocityAtTime(time);
v2 = thisComp.layer("Moving").position.velocityAtTime(time - thisComp.frameDuration);
accel = (v1 - v2) / thisComp.frameDuration;
length(accel);
```

### 3.6 运动平滑

**效果描述**：平滑抖动的运动数据。

```javascript
// 应用到 Position
smoothWidth = 0.2;       // 平滑窗口（秒）
smoothSamples = 5;       // 采样数
smooth(smoothWidth, smoothSamples);
```

### 3.7 运动延迟

**效果描述**：多个图层依次延迟跟随，形成"拖尾"。

```javascript
// 应用到 Position
leader = thisComp.layer("Leader");
delay = 0.1 * index;     // 每层多延迟 0.1 秒
leader.position.valueAtTime(time - delay);
```

### 3.8 运动继承

**效果描述**：子图层继承父图层部分运动。

```javascript
// 应用到 Position
parent = thisComp.layer("Parent");
inheritance = 0.5;       // 继承比例（0-1）
parentDelta = parent.position - parent.transform.anchorPoint;
value + parentDelta * inheritance;
```

### 3.9 运动传递

**效果描述**：将一个图层的运动传递给另一个图层，可放大缩小。

```javascript
// 应用到 Position
source = thisComp.layer("Source");
scale = 2;               // 放大倍数
sourcePos = source.position - source.transform.anchorPoint;
value + sourcePos * scale;
```

### 3.10 运动约束

**效果描述**：将物体限制在某个范围内。

```javascript
// 应用到 Position
minX = 100;
maxX = 1820;
minY = 100;
maxY = 980;

x = clamp(value[0], minX, maxX);
y = clamp(value[1], minY, maxY);
[x, y];
```

### 3.11 IK（反向运动学）简化版

**效果描述**：两段肢体的 IK 求解，常用于角色动画。

```javascript
// 应用到上臂 Rotation（肘部）
upperArm = thisComp.layer("UpperArm");
lowerArm = thisComp.layer("LowerArm");
hand = thisComp.layer("Hand");

L1 = length(upperArm.position, lowerArm.position);
L2 = length(lowerArm.position, hand.position);
D = length(upperArm.position, hand.position);

// 余弦定理求肘部角度
cosA = (L1*L1 + D*D - L2*L2) / (2 * L1 * D);
angleA = Math.acos(clamp(cosA, -1, 1)) * 180 / Math.PI;

// 计算朝向
dir = hand.position - upperArm.position;
baseAngle = Math.atan2(dir[1], dir[0]) * 180 / Math.PI;
baseAngle - angleA;
```

### 3.12 FK（正向运动学）

**效果描述**：父级旋转带动子级，正向传递运动。

```javascript
// 应用到子级 Rotation
parent = thisComp.layer("ParentBone");
parentRot = parent.rotation.valueAtTime(time);
// FK 直接继承父级旋转
value + parentRot * 0.5; // 0.5 为继承比例
```

### 3.13 运动链

**效果描述**：多个图层形成链式跟随，类似绳索。

```javascript
// 应用到链中每个图层 Position
leader = thisComp.layer("Chain_01");  // 链首
delay = 0.05 * (index - leader.index);
stiffness = 0.6;                     // 跟随强度

target = leader.position.valueAtTime(time - delay);
value + (target - value) * stiffness;
```

### 3.14 多点约束

**效果描述**：物体被多个锚点共同约束（类似悬链线）。

```javascript
// 应用到 Position
points = [
    thisComp.layer("P1").position,
    thisComp.layer("P2").position,
    thisComp.layer("P3").position
];
weights = [0.3, 0.3, 0.4];           // 权重和为 1

x = 0; y = 0;
for (i = 0; i < points.length; i++) {
    x += points[i][0] * weights[i];
    y += points[i][1] * weights[i];
}
[x, y];
```

### 3.15 运动混合

**效果描述**：在两个运动状态间平滑过渡。

```javascript
// 应用到 Position
motionA = thisComp.layer("MotionA").position;
motionB = thisComp.layer("MotionB").position;
blend = effect("Blend")("Slider");   // 0-1 滑块

// 球面插值（更自然）
t = ease(blend, 0, 1, 0, 1);
lerp(motionA, motionB, t);
```

---

## 四、循环与重复表达式（10 个）

### 4.1 无缝循环

**效果描述**：让动画首尾衔接，无限循环播放。

```javascript
// 应用到任意属性，配合关键帧
loopOut("cycle");                  // 基础循环
loopOut("cycle", 0);               // 循环所有关键帧
loopOut("pingpong");               // 往复循环
loopOut("offset");                 // 偏移循环（保持增量趋势）
loopOut("continue");               // 延续速度
```

### 4.2 周期性运动

**效果描述**：使用正弦函数生成周期运动。

```javascript
// 应用到 Position
amp = [100, 50];          // 振幅
freq = [0.5, 0.7];        // 频率
phase = [0, Math.PI / 2]; // 相位

x = value[0] + amp[0] * Math.sin(2 * Math.PI * freq[0] * time + phase[0]);
y = value[1] + amp[1] * Math.sin(2 * Math.PI * freq[1] * time + phase[1]);
[x, y];
```

### 4.3 循环偏移

**效果描述**：循环时叠加增量，形成"螺旋上升"效果。

```javascript
// 应用到 Position
cyclesPerSec = 1;         // 每秒循环次数
offset = [50, 0];         // 每次循环的偏移
cycleTime = 1 / cyclesPerSec;

t = (time - inPoint) % cycleTime;
n = Math.floor((time - inPoint) / cycleTime);
value + offset * n + wiggle(1, 10) * (t / cycleTime);
```

### 4.4 循环缩放

**效果描述**：缩放周期性变化，"呼吸"效果。

```javascript
// 应用到 Scale
minScale = 80;
maxScale = 120;
freq = 0.5;               // 每秒呼吸次数
phase = 0;

t = (Math.sin(2 * Math.PI * freq * time + phase) + 1) / 2;
s = minScale + (maxScale - minScale) * t;
[s, s];
```

### 4.5 循环旋转

**效果描述**：360 度循环旋转，无缝衔接。

```javascript
// 应用到 Rotation
speed = 90;               // 度/秒
((time - inPoint) * speed) % 360;
```

### 4.6 循环颜色

**效果描述**：颜色在色环上循环变化。

```javascript
// 应用到 Fill Color
speed = 60;               // 度/秒
hue = ((time - inPoint) * speed) % 360;
hslToRgb = function(h, s, l) {
    h = h / 360;
    // HSL 转 RGB（简化版）
    c = (1 - Math.abs(2 * l - 1)) * s;
    x = c * (1 - Math.abs((h * 6) % 2 - 1));
    m = l - c / 2;
    if (h < 1/6) r=c,g=x,b=0;
    else if (h < 2/6) r=x,g=c,b=0;
    else if (h < 3/6) r=0,g=c,b=x;
    else if (h < 4/6) r=0,g=x,b=c;
    else if (h < 5/6) r=x,g=0,b=c;
    else r=c,g=0,b=x;
    return [r + m, g + m, b + m, 1];
};
hslToRgb(hue, 1, 0.5);
```

### 4.7 循环位置

**效果描述**：沿闭合路径循环移动。

```javascript
// 应用到 Position（路径循环）
points = [[200, 540], [960, 200], [1720, 540], [960, 880]];
duration = 4;             // 每圈秒数
t = ((time - inPoint) % duration) / duration;
segment = Math.floor(t * points.length);
localT = (t * points.length) - segment;
p1 = points[segment];
p2 = points[(segment + 1) % points.length];
[
    linear(localT, 0, 1, p1[0], p2[0]),
    linear(localT, 0, 1, p1[1], p2[1])
];
```

### 4.8 镜像循环

**效果描述**：往复循环，类似 loopOut("pingpong") 但更可控。

```javascript
// 应用到任意属性
cycleTime = 2;
t = (time - inPoint) % (cycleTime * 2);
if (t > cycleTime) t = cycleTime * 2 - t;
// 应用到 value
value + Math.sin(t * Math.PI / cycleTime) * 50;
```

### 4.9 随机循环

**效果描述**：每次循环生成不同随机值，但循环内保持稳定。

```javascript
// 应用到 Position
cycleTime = 1;
cycleIndex = Math.floor((time - inPoint) / cycleTime);
seedRandom(cycleIndex, true);
random([960, 540]) - [960, 540] + value;
```

### 4.10 条件循环

**效果描述**：根据条件决定是否循环。

```javascript
// 应用到 Rotation
cycleStart = 1;
cycleEnd = 5;
if (time >= cycleStart && time <= cycleEnd) {
    t = (time - cycleStart) % 1;
    t * 360;
} else {
    value;
}
```

---

## 五、随机与噪声表达式（10 个）

### 5.1 自然随机（Wiggle）

**效果描述**：基于柏林噪声的平滑随机抖动。

```javascript
// 应用到任意属性
freq = 2;                 // 每秒变化次数
amp = 50;                 // 变化幅度
octaves = 1;              // 倍频数（越多越细致）
ampMult = 0.5;            // 每倍频振幅递减

wiggle(freq, amp, octaves, ampMult, time);
```

### 5.2 有序随机

**效果描述**：在固定值集合中按顺序随机选取。

```javascript
// 应用到任意属性
values = [100, 200, 300, 400, 500];
stepTime = 0.5;           // 每 0.5 秒切换
seed = Math.floor(time / stepTime);
seedRandom(seed, true);
values[Math.floor(random(values.length))];
```

### 5.3 随机闪烁

**效果描述**：透明度随机闪烁，模拟霓虹灯故障。

```javascript
// 应用到 Opacity
freq = 8;                 // 闪烁频率
chance = 0.7;             // 亮起概率

seedRandom(Math.floor(time * freq), true);
random() < chance ? 100 : 20;
```

### 5.4 随机颜色

**效果描述**：每个图层随机分配颜色。

```javascript
// 应用到 Fill Color
seedRandom(index, true);
r = random();
g = random();
b = random();
[r, g, b, 1];
```

### 5.5 随机大小

**效果描述**：图层大小随机变化。

```javascript
// 应用到 Scale
minSize = 50;
maxSize = 150;
seedRandom(index, true);
s = random(minSize, maxSize);
[s, s];
```

### 5.6 随机旋转

**效果描述**：每个图层随机角度。

```javascript
// 应用到 Rotation
seedRandom(index, true);
random(0, 360);
```

### 5.7 随机延迟

**效果描述**：每个图层动画开始时间随机错开。

```javascript
// 应用到 Time Remap
maxDelay = 1;             // 最大延迟（秒）
seedRandom(index, true);
delay = random(0, maxDelay);
time - delay;
```

### 5.8 柏林噪声

**效果描述**：直接调用 noise() 函数获取柏林噪声值。

```javascript
// 应用到任意属性
speed = 1;
scale = 2;
n = noise(time * speed) * scale;
n += noise(time * speed * 2) * scale * 0.5;
n += noise(time * speed * 4) * scale * 0.25;
value + n * 50;
```

### 5.9 分形噪声

**效果描述**：多倍频柏林噪声叠加，模拟自然纹理。

```javascript
// 应用到任意属性
freq = 1;
amp = 100;
octaves = 4;              // 倍频层数
persistence = 0.5;        // 振幅递减
lacunarity = 2;           // 频率递增

total = 0;
maxValue = 0;
amplitude = 1;
frequency = freq;

for (i = 0; i < octaves; i++) {
    total += noise([time * frequency, 0]) * amplitude;
    maxValue += amplitude;
    amplitude *= persistence;
    frequency *= lacunarity;
}
value + (total / maxValue) * amp;
```

### 5.10 随机粒子

**效果描述**：模拟粒子初始状态，每个粒子随机位置和速度。

```javascript
// 应用到 Position
seedRandom(index, true);
x = random(0, 1920);
y = random(0, 1080);
vx = random(-50, 50);
vy = random(-50, 50);

t = time - inPoint;
[x + vx * t, y + vy * t];
```

---

## 六、音频驱动表达式（10 个）

> **前置准备**：右键音频图层 → 关键帧助手 → 将音频转换为关键帧，会生成"Audio Amplitude"图层，含 "Both Channels" 等滑块。

### 6.1 音频振幅提取

**效果描述**：提取音频振幅作为可调参数。

```javascript
// 应用到 Slider Control
audioLayer = thisComp.layer("Audio Amplitude");
audioLayer.effect("Both Channels")("Slider").value;
```

### 6.2 音频驱动缩放

**效果描述**：音量越大物体越大。

```javascript
// 应用到 Scale
audioLayer = thisComp.layer("Audio Amplitude");
audioAmp = audioLayer.effect("Both Channels")("Slider");

minAudio = 5;
maxAudio = 40;
minScale = 100;
maxScale = 150;

s = linear(audioAmp, minAudio, maxAudio, minScale, maxScale);
[s, s];
```

### 6.3 音频驱动位置

**效果描述**：物体随音频上下跳动。

```javascript
// 应用到 Position
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
sensitivity = 5;
y = audioAmp * sensitivity;
[value[0], value[1] - y];
```

### 6.4 音频驱动旋转

**效果描述**：物体随音频旋转。

```javascript
// 应用到 Rotation
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
sensitivity = 3;
audioAmp * sensitivity;
```

### 6.5 音频驱动颜色

**效果描述**：音量越大颜色越亮。

```javascript
// 应用到 Fill Color
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
brightness = linear(audioAmp, 0, 50, 0.2, 1);
[brightness, brightness * 0.3, brightness * 0.1, 1];
```

### 6.6 音频驱动透明度

**效果描述**：音量越大越不透明。

```javascript
// 应用到 Opacity
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
linear(audioAmp, 0, 30, 0, 100);
```

### 6.7 频率分频

**效果描述**：分离低频和高频，分别驱动不同效果。

```javascript
// 应用到 Slider Control，输出低频强度
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
// 简单低通滤波
alpha = 0.1;
smoothed = audioAmp.valueAtTime(time - thisComp.frameDuration) * (1 - alpha) + audioAmp * alpha;
smoothed;
```

**高频检测版本**：

```javascript
// 高频 = 原始 - 低频
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
alpha = 0.05;
lowPass = audioAmp;
for (i = 1; i < 30; i++) {
    lowPass = lowPass * (1 - alpha) + audioAmp.valueAtTime(time - i * thisComp.frameDuration) * alpha;
}
highFreq = audioAmp - lowPass;
highFreq;
```

### 6.8 节拍检测

**效果描述**：检测鼓点，每拍输出一个脉冲。

```javascript
// 应用到 Slider Control
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
threshold = 25;
cooldown = 0.3;           // 最小节拍间隔（秒）

// 回溯找最近节拍
f = timeToFrames(time);
lastBeat = 0;
while (f > 0) {
    t = framesToTime(f);
    if (audioAmp.valueAtTime(t) > threshold &&
        audioAmp.valueAtTime(t - thisComp.frameDuration) <= threshold) {
        if (time - t > cooldown) {
            lastBeat = t;
            break;
        }
    }
    f--;
}

// 节拍后衰减
timeSinceBeat = time - lastBeat;
Math.exp(-timeSinceBeat * 10);
```

### 6.9 音频频谱

**效果描述**：将音频转换为频谱条带。

```javascript
// 应用到形状图层的 Scale Y
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
i = index - 1;            // 频段索引
delay = i * 0.02;         // 每段延迟

// 模拟频段（实际需专业插件）
bandValue = audioAmp.valueAtTime(time - delay);
[100, bandValue * 5];
```

### 6.10 音频可视化

**效果描述**：综合音频驱动多属性，形成可视化。

```javascript
// 应用到 Position
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
i = index;
angle = (i / 20) * 2 * Math.PI;   // 排成圆形
radius = 200 + audioAmp * 5;

x = Math.cos(angle + time) * radius;
y = Math.sin(angle + time) * radius;
[960 + x, 540 + y];
```

---

## 七、3D 空间表达式（10 个）

### 7.1 3D 距离计算

**效果描述**：计算两个 3D 图层间距离。

```javascript
// 应用到 Slider Control
a = thisComp.layer("ObjA").position;
b = thisComp.layer("ObjB").position;
dx = a[0] - b[0];
dy = a[1] - b[1];
dz = a[2] - b[2];
Math.sqrt(dx*dx + dy*dy + dz*dz);
```

### 7.2 摄像机朝向

**效果描述**：3D 图层始终面向摄像机。

```javascript
// 应用到 Orientation（3D 图层）
cam = thisComp.activeCamera;
if (cam != null) {
    delta = cam.position - transform.position;
    // 计算朝向角度
    yaw = Math.atan2(delta[0], delta[2]) * 180 / Math.PI;
    pitch = Math.atan2(delta[1], Math.sqrt(delta[0]*delta[0] + delta[2]*delta[2])) * 180 / Math.PI;
    [pitch, yaw, 0];
} else {
    value;
}
```

### 7.3 3D 旋转

**效果描述**：3D 空间中绕任意轴旋转。

```javascript
// 应用到 Position（绕 Y 轴旋转）
center = [960, 540, 0];
radius = 300;
speed = 60;               // 度/秒

angle = degreesToRadians((time - inPoint) * speed);
x = center[0] + Math.cos(angle) * radius;
y = center[1];
z = center[2] + Math.sin(angle) * radius;
[x, y, z];
```

### 7.4 3D 缩放

**效果描述**：基于摄像机距离调整缩放，模拟透视。

```javascript
// 应用到 Scale
cam = thisComp.activeCamera;
if (cam != null) {
    dist = length(transform.position, cam.position);
    // 透视缩放
    focal = cam.cameraOption.zoom;
    scaleFactor = focal / (focal + dist);
    baseScale = 100;
    [baseScale * scaleFactor, baseScale * scaleFactor];
} else {
    value;
}
```

### 7.5 3D 位置约束

**效果描述**：3D 物体跟随另一 3D 物体的某个轴向。

```javascript
// 应用到 Position
target = thisComp.layer("Target");
followX = true;
followY = false;
followZ = true;

x = followX ? target.position[0] : value[0];
y = followY ? target.position[1] : value[1];
z = followZ ? target.position[2] : value[2];
[x, y, z];
```

### 7.6 3D 路径

**效果描述**：物体沿 3D 螺旋路径运动。

```javascript
// 应用到 Position
center = [960, 540, 0];
radius = 200;
heightPerSec = 100;
speed = 90;               // 度/秒
t = time - inPoint;

angle = degreesToRadians(t * speed);
x = center[0] + Math.cos(angle) * radius;
y = center[1] + t * heightPerSec;
z = center[2] + Math.sin(angle) * radius;
[x, y, z];
```

### 7.7 3D 碰撞

**效果描述**：3D 空间中两球碰撞检测与响应。

```javascript
// 应用到 Position
other = thisComp.layer("BallB");
threshold = 200;
elasticity = 0.8;

dir = [value[0] - other.position[0], value[1] - other.position[1], value[2] - other.position[2]];
dist = Math.sqrt(dir[0]*dir[0] + dir[1]*dir[1] + dir[2]*dir[2]);
if (dist < threshold && dist > 0) {
    push = (threshold - dist) * elasticity;
    norm = [dir[0]/dist, dir[1]/dist, dir[2]/dist];
    [value[0] + norm[0]*push, value[1] + norm[1]*push, value[2] + norm[2]*push];
} else {
    value;
}
```

### 7.8 3D 层次关系

**效果描述**：3D 父子图层自动保持空间关系。

```javascript
// 应用到子图层 Position
parent = thisComp.layer("Parent3D");
offset = [100, 0, 0];    // 相对父级的偏移

// 应用父级变换到偏移
parentRotY = degreesToRadians(parent.rotationY);
rotatedX = offset[0] * Math.cos(parentRotY) - offset[2] * Math.sin(parentRotY);
rotatedZ = offset[0] * Math.sin(parentRotY) + offset[2] * Math.cos(parentRotY);

[parent.position[0] + rotatedX, parent.position[1] + offset[1], parent.position[2] + rotatedZ];
```

### 7.9 3D 视差

**效果描述**：多层 3D 图层根据深度产生视差效果。

```javascript
// 应用到 Position
cam = thisComp.activeCamera;
parallaxStrength = 0.5;   // 视差强度
depth = transform.position[2];

if (cam != null) {
    camOffset = cam.position - [960, 540, 0];
    [
        value[0] - camOffset[0] * parallaxStrength * (depth / 1000),
        value[1] - camOffset[1] * parallaxStrength * (depth / 1000),
        value[2]
    ];
} else {
    value;
}
```

### 7.10 3D 空间变形

**效果描述**：3D 图层根据距摄像机远近变形。

```javascript
// 应用到 Scale
cam = thisComp.activeCamera;
if (cam != null) {
    dist = length(transform.position, cam.position);
    // 鱼眼效果：近处放大，远处缩小
    fishEye = 1 + 500 / (dist + 100);
    baseScale = 100;
    [baseScale * fishEye, baseScale * fishEye];
} else {
    value;
}
```

---

## 八、文字动画表达式（10 个）

### 8.1 逐字动画

**效果描述**：每个字符依次动画，形成波浪效果。

```javascript
// 应用到 Source Text 的动画属性
delay = 0.05;             // 每字延迟
charOffset = textIndex - 1;
y = Math.sin((time - charOffset * delay) * 5) * 20;
[value[0], value[1] + y];
```

### 8.2 逐行动画

**效果描述**：每行文字依次出现。

```javascript
// 应用到 Opacity
lineDelay = 0.3;          // 每行延迟
lineIndex = Math.floor(textIndex / 10); // 简化估算
opacity = clamp((time - inPoint - lineIndex * lineDelay) * 200, 0, 100);
opacity;
```

### 8.3 逐词动画

**效果描述**：按单词依次动画。

```javascript
// 应用到 Position
textSrc = text.sourceText;
wordIndex = 0;
charCount = 0;
for (i = 0; i < textIndex; i++) {
    if (textSrc[i] === " ") wordIndex++;
}
delay = 0.2;
y = ease(time - inPoint - wordIndex * delay, 0, 0.5, 50, 0);
[value[0], value[1] + y];
```

### 8.4 文字间距

**效果描述**：动态调整字间距。

```javascript
// 应用到 Source Text
tracking = 5 + Math.sin(time * 2) * 3;
text.sourceText.style.setTracking(tracking);
```

### 8.5 文字颜色

**效果描述**：逐字变色，形成彩虹效果。

```javascript
// 应用到 Fill Color
hue = (textIndex * 30 + time * 60) % 360;
h = hue / 360;
// HSL 转 RGB
c = 1;
x = c * (1 - Math.abs((h * 6) % 2 - 1));
m = 0;
if (h < 1/6) rgb = [c, x, 0];
else if (h < 2/6) rgb = [x, c, 0];
else if (h < 3/6) rgb = [0, c, x];
else if (h < 4/6) rgb = [0, x, c];
else if (h < 5/6) rgb = [x, 0, c];
else rgb = [c, 0, x];
[rgb[0] + m, rgb[1] + m, rgb[2] + m, 1];
```

### 8.6 文字大小

**效果描述**：字符大小随时间波动。

```javascript
// 应用到 Font Size
baseSize = 72;
wave = Math.sin(time * 3 + textIndex * 0.5) * 10;
baseSize + wave;
```

### 8.7 文字旋转

**效果描述**：每个字符随机旋转。

```javascript
// 应用到 Rotation
seedRandom(textIndex + Math.floor(time), true);
random(-15, 15);
```

### 8.8 文字位置

**效果描述**：字符位置随机偏移。

```javascript
// 应用到 Position
seedRandom(textIndex, true);
offsetX = random(-20, 20);
offsetY = random(-20, 20);
[value[0] + offsetX, value[1] + offsetY];
```

### 8.9 文字模糊

**效果描述**：运动中的文字模糊效果。

```javascript
// 应用到文本图层 Blur（通过表达式控制）
speed = 50;
[Math.abs(transform.position.velocityAtTime(time)[0]) * 0.1, 0];
```

### 8.10 文字特效

**效果描述**：打字机效果。

```javascript
// 应用到 Source Text
fullText = "Hello World, 表达式真好玩！";
typeSpeed = 10;          // 每秒字数
charsToShow = Math.floor((time - inPoint) * typeSpeed);
fullText.substring(0, charsToShow);
```

**带光标版本**：

```javascript
// 应用到 Source Text
fullText = "Hello World!";
typeSpeed = 10;
charsToShow = Math.floor((time - inPoint) * typeSpeed);
cursor = (Math.floor(time * 2) % 2 === 0) ? "|" : " ";
fullText.substring(0, Math.min(charsToShow, fullText.length)) + cursor;
```

---

## 九、时间控制表达式（10 个）

### 9.1 时间冻结

**效果描述**：在指定时间点冻结画面。

```javascript
// 应用到 Time Remap
freezeTime = 2;
if (time > freezeTime) {
    freezeTime;
} else {
    time;
}
```

### 9.2 时间减慢

**效果描述**：慢动作效果。

```javascript
// 应用到 Time Remap
slowFactor = 0.25;        // 1/4 速度
(time - inPoint) * slowFactor + inPoint;
```

### 9.3 时间加速

**效果描述**：快进效果。

```javascript
// 应用到 Time Remap
fastFactor = 4;           // 4 倍速
(time - inPoint) * fastFactor + inPoint;
```

### 9.4 时间倒流

**效果描述**：画面倒放。

```javascript
// 应用到 Time Remap
outPoint - (time - inPoint);
```

### 9.5 时间循环

**效果描述**：时间段内循环播放。

```javascript
// 应用到 Time Remap
loopStart = 1;
loopEnd = 3;
loopDur = loopEnd - loopStart;
loopStart + ((time - loopStart) % loopDur);
```

### 9.6 时间偏移

**效果描述**：整体时间前后偏移。

```javascript
// 应用到 Time Remap
offset = 2;               // 偏移 2 秒
time + offset;
```

### 9.7 时间重映射

**效果描述**：随时间变速，自由控制速度曲线。

```javascript
// 应用到 Time Remap
// 使用关键帧定义速度曲线，表达式平滑过渡
baseTime = value;
smoothTime = baseTime + wiggle(0.5, 0.2);
smoothTime;
```

### 9.8 时间抖动

**效果描述**：时间随机抖动，Glitch 效果。

```javascript
// 应用到 Time Remap
jitterAmount = 0.1;       // 抖动幅度
jitterFreq = 5;           // 抖动频率
time + wiggle(jitterFreq, jitterAmount);
```

### 9.9 时间冻结帧

**效果描述**：随机冻结画面若干帧，模拟卡顿。

```javascript
// 应用到 Time Remap
freezeDur = 0.2;
playDur = 0.5;
t = time - inPoint;
cycle = freezeDur + playDur;
cycleIndex = Math.floor(t / cycle);
localT = t % cycle;
if (localT < playDur) {
    inPoint + cycleIndex * playDur + localT;
} else {
    inPoint + (cycleIndex + 1) * playDur;
}
```

### 9.10 条件时间控制

**效果描述**：根据条件切换时间播放模式。

```javascript
// 应用到 Time Remap
marker = thisComp.marker.nearestKey(time);
if (marker.time > time) marker = thisComp.marker.nearestKey(time - 0.01);

if (marker.index % 2 === 0) {
    // 偶数标记区间：慢速
    (time - marker.time) * 0.5 + marker.time;
} else {
    // 奇数标记区间：正常
    time;
}
```

---

## 十、高级表达式模式（10 个）

### 10.1 状态机表达式

**效果描述**：基于状态机切换行为。

```javascript
// 应用到任意属性
// 通过标记定义状态切换
function getState(t) {
    markers = thisComp.marker;
    state = "idle";
    for (i = 1; i <= markers.numKeys; i++) {
        if (markers.key(i).time <= t) {
            state = markers.key(i).comment;
        }
    }
    return state;
}

currentState = getState(time);
switch (currentState) {
    case "idle":
        value;
        break;
    case "active":
        value + wiggle(5, 20);
        break;
    case "exit":
        value * 0.5;
        break;
    default:
        value;
}
```

### 10.2 事件驱动表达式

**效果描述**：基于关键帧事件触发响应。

```javascript
// 应用到 Position
trigger = effect("Trigger")("Slider");  // 事件触发器
threshold = 1;
cooldown = 0.5;

// 找最近触发时间
f = timeToFrames(time);
lastTrigger = -1;
while (f > 0) {
    t = framesToTime(f);
    if (trigger.valueAtTime(t) >= threshold &&
        trigger.valueAtTime(t - thisComp.frameDuration) < threshold) {
        lastTrigger = t;
        break;
    }
    f--;
}

if (lastTrigger > 0) {
    elapsed = time - lastTrigger;
    // 触发后弹跳
    value + [0, -50 * Math.exp(-elapsed * 5) * Math.cos(elapsed * 15)];
} else {
    value;
}
```

### 10.3 条件表达式

**效果描述**：多条件分支控制。

```javascript
// 应用到 Opacity
mode = effect("Mode")("Slider");

if (mode === 1) {
    // 模式 1：渐入
    ease(time, inPoint, inPoint + 1, 0, 100);
} else if (mode === 2) {
    // 模式 2：闪烁
    Math.sin(time * 5) > 0 ? 100 : 0;
} else if (mode === 3) {
    // 模式 3：音频驱动
    audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
    linear(audioAmp, 0, 30, 0, 100);
} else {
    100;
}
```

### 10.4 递归表达式

**效果描述**：链式延迟，每层依赖上一层。

```javascript
// 应用到 Position
maxDepth = 5;
delay = 0.05;

function getChainPosition(depth, t) {
    if (depth <= 0 || index - depth < 1) {
        return value;
    }
    prevLayer = thisComp.layer(index - depth);
    return prevLayer.position.valueAtTime(t - delay);
}

getChainPosition(Math.min(index - 1, maxDepth), time);
```

### 10.5 参数化表达式

**效果描述**：通过滑块控制参数，无需修改表达式。

```javascript
// 应用到 Position，需先添加 Expression Controls
amp = effect("Amplitude")("Slider");
freq = effect("Frequency")("Slider");
phase = effect("Phase")("Slider");

x = amp * Math.sin(2 * Math.PI * freq * time + phase);
y = amp * Math.cos(2 * Math.PI * freq * time + phase);
[value[0] + x, value[1] + y];
```

### 10.6 模块化表达式

**效果描述**：将通用函数封装到主合成，多处复用。

```javascript
// 在主合成某图层的 Source Text 中定义工具函数（作为字符串存储）
// 其他图层通过 eval 调用

// 工具库图层（Source Text）：
/*
function lerp(a, b, t) { return a + (b - a) * t; }
function clamp(val, min, max) { return Math.min(Math.max(val, min), max); }
function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
*/

// 调用方图层：
utils = thisComp.layer("Utils").text.sourceText.value;
eval(utils);
easeOutCubic(clamp(time / 2, 0, 1)) * 100;
```

### 10.7 表达式库构建

**效果描述**：通过注释标记组织表达式库，便于检索。

```javascript
// === EXPRESSION LIBRARY ===
// @category: physics
// @name: spring
// @params: stiffness, damping, mass

function spring(target, current, velocity, stiffness, damping, mass) {
    force = (target - current) * stiffness / mass;
    velocity = (velocity + force) * (1 - damping / mass);
    return { pos: current + velocity, vel: velocity };
}

// 调用
result = spring(value, value, [0,0], 80, 8, 1);
result.pos;
```

### 10.8 表达式预设

**效果描述**：将常用表达式保存为预设，拖拽即用。

**保存方法**：
1. 选中含表达式的属性
2. `动画 → 保存动画预设`
3. 命名保存到用户预设库

**调用方法**：从"效果与预设"面板拖拽到目标属性。

```javascript
// 预设模板：万能弹性
amp = effect("Amplitude")("Slider") || 0.1;
freq = effect("Frequency")("Slider") || 2.0;
decay = effect("Decay")("Slider") || 2.0;

n = 0;
if (numKeys > 0) {
    n = nearestKey(time).index;
    if (key(n).time > time) n--;
}
t = n > 0 ? time - key(n).time : 0;
v = n > 0 ? velocityAtTime(key(n).time - 0.01) : 0;
value + v * amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
```

### 10.9 表达式调试器

**效果描述**：通过文本图层实时显示表达式内部状态。

```javascript
// 应用到调试文本图层的 Source Text
targetLayer = thisComp.layer("Target");
pos = targetLayer.position.value;
vel = targetLayer.position.velocityAtTime(time);
speed = length(vel);

debug = "=== DEBUG INFO ===\n";
debug += "Time: " + time.toFixed(3) + "s\n";
debug += "Position: [" + pos[0].toFixed(1) + ", " + pos[1].toFixed(1) + "]\n";
debug += "Velocity: [" + vel[0].toFixed(1) + ", " + vel[1].toFixed(1) + "]\n";
debug += "Speed: " + speed.toFixed(1) + "\n";
debug += "Frame: " + timeToFrames(time) + "\n";
debug += "FPS: " + (1 / thisComp.frameDuration).toFixed(2);
debug;
```

### 10.10 表达式性能监控

**效果描述**：测量表达式执行时间。

```javascript
// 应用到 Slider Control（仅 JavaScript 引擎）
// 使用 performance.now() 测量
t0 = $.performanceNow ? $.performanceNow() : 0;

// 被测表达式
result = 0;
for (i = 0; i < 1000; i++) {
    result += Math.sin(i * 0.01);
}

t1 = $.performanceNow ? $.performanceNow() : 0;
// 输出执行时间（毫秒）
(t1 - t0);
```

---

## 十一、表达式实用技巧（20 个）

### 11.1 图层引用技巧

```javascript
// 按名称引用
L = thisComp.layer("LayerName");

// 按索引引用
L = thisComp.layer(1);

// 相对索引引用
L = thisComp.layer(index - 1);   // 上一层
L = thisComp.layer(index + 1);   // 下一层

// 引用当前图层
L = thisLayer;

// 跨合成引用
L = comp("OtherComp").layer("LayerName");

// 引用活动摄像机
cam = thisComp.activeCamera;

// 引用最上层
topLayer = thisComp.layer(thisComp.numLayers);
```

### 11.2 属性继承技巧

```javascript
// 继承父级位置
parentPos = parent.position;

// 仅继承父级某轴向
parentX = parent.position[0];
myY = value[1];
[parentX, myY];

// 父级变换矩阵分解
parentRot = parent.rotation;
parentScale = parent.scale;
```

### 11.3 坐标转换技巧

```javascript
// 图层坐标 → 合成坐标
layerToComp = thisLayer.toComp([0, 0]);

// 合成坐标 → 图层坐标
compToLayer = thisLayer.fromComp([960, 540]);

// 图层坐标 → 世界坐标（3D）
layerToWorld = thisLayer.toWorld([0, 0, 0]);

// 世界坐标 → 图层坐标（3D）
worldToLayer = thisLayer.fromWorld([0, 0, 0]);
```

### 11.4 颜色操作技巧

```javascript
// 颜色分量提取
c = effect("Color Control")("Color");
r = c[0]; g = c[1]; b = c[2]; a = c[3];

// 颜色亮度计算
brightness = 0.299 * r + 0.587 * g + 0.114 * b;

// 颜色反相
[1-r, 1-g, 1-b, a];

// 颜色混合
colorA = [1, 0, 0, 1];
colorB = [0, 0, 1, 1];
t = 0.5;
[
    lerp(colorA[0], colorB[0], t),
    lerp(colorA[1], colorB[1], t),
    lerp(colorA[2], colorB[2], t),
    1
];
```

### 11.5 数组操作技巧

```javascript
// 数组求和
arr = [1, 2, 3, 4, 5];
sum = 0;
for (i = 0; i < arr.length; i++) sum += arr[i];

// 数组最大值
arr = [3, 1, 4, 1, 5, 9, 2, 6];
maxVal = arr[0];
for (i = 1; i < arr.length; i++) {
    if (arr[i] > maxVal) maxVal = arr[i];
}

// 数组映射
arr = [1, 2, 3];
result = [];
for (i = 0; i < arr.length; i++) {
    result[i] = arr[i] * 2;
}

// 二维数组操作
v = [100, 200];
v = [v[0] + 10, v[1] + 5];

// JavaScript 引擎支持解构
v = value;
[x, y] = v;
[x + 10, y + 5];
```

### 11.6 字符串操作技巧

```javascript
// 字符串长度
text.sourceText.value.length;

// 截取
text.sourceText.value.substring(0, 10);

// 大小写
text.sourceText.value.toUpperCase();
text.sourceText.value.toLowerCase();

// 拼接
"Time: " + time.toFixed(2) + "s";

// 替换
text.sourceText.value.replace("old", "new");

// 分割
text.sourceText.value.split(" ");
```

### 11.7 数学运算技巧

```javascript
// 角度弧度转换
deg = radiansToDegrees(Math.PI);     // 180
rad = degreesToRadians(180);         // π

// 限制范围
clamp(value, 0, 100);
clamp(value, [0, 0], [100, 100]);    // 数组版本

// 线性映射
linear(time, 0, 5, 0, 100);          // 时间 0-5 映射到 0-100

// 缓动映射
ease(time, 0, 5, 0, 100);
easeIn(time, 0, 5, 0, 100);
easeOut(time, 0, 5, 0, 100);

// 插值
lerp(0, 100, 0.5);                   // 50

// 向量运算
v = [3, 4];
length(v);                           // 5
normalize(v);                        // [0.6, 0.8]

// 距离
dist = length([0,0], [3,4]);         // 5
```

### 11.8 逻辑控制技巧

```javascript
// 三元运算符
result = condition ? valueA : valueB;

// 短路求值
result = a && b;
result = a || b;

// switch-case（用 if-else 模拟）
mode = 1;
if (mode === 1) {
    result = "A";
} else if (mode === 2) {
    result = "B";
} else {
    result = "C";
}

// JavaScript 引擎支持 switch
switch (mode) {
    case 1: result = "A"; break;
    case 2: result = "B"; break;
    default: result = "C";
}
```

### 11.9 错误处理技巧

```javascript
// try-catch
try {
    L = thisComp.layer("可能不存在");
    result = L.position;
} catch (e) {
    result = value;
}

// 类型检查
function isUndefined(v) {
    return typeof v === "undefined";
}

// 默认值
function defaultValue(v, def) {
    return isUndefined(v) ? def : v;
}

// 安全数组访问
function safeGet(arr, index) {
    return (index >= 0 && index < arr.length) ? arr[index] : 0;
}
```

### 11.10 性能优化技巧

```javascript
// 1. 缓存重复引用
L = thisComp.layer("Target"); // 缓存
pos = L.position;             // 复用

// 2. 减少循环次数
// 不好：100 次循环
// 好：用数学公式直接计算

// 3. 使用内置函数
// 不好：手写插值
// 好：用 linear()、ease()

// 4. 限制 wiggle 复杂度
wiggle(2, 50, 1, 0.5);       // 指定倍频数，避免过高

// 5. posterizeTime 降低帧率
posterizeTime(12);
wiggle(2, 50);

// 6. 避免在循环内调用 valueAtTime
// 不好：for 循环内多次 valueAtTime
// 好：预先采样到数组
```

### 11.11 实用技巧：自动对齐到网格

```javascript
// 应用到 Position
gridSize = 50;
x = Math.round(value[0] / gridSize) * gridSize;
y = Math.round(value[1] / gridSize) * gridSize;
[x, y];
```

### 11.12 实用技巧：基于标记触发动画

```javascript
// 应用到任意属性
markers = thisComp.marker;
if (markers.numKeys > 0) {
    nearest = markers.nearestKey(time);
    if (nearest.time <= time) {
        t = time - nearest.time;
        // 在标记后 1 秒内触发动画
        ease(t, 0, 1, 0, 100);
    } else {
        0;
    }
} else {
    0;
}
```

### 11.13 实用技巧：根据图层名获取参数

```javascript
// 应用到任意属性
name = thisLayer.name;
// 假设图层名为 "Layer_001_x100"
parts = name.split("_");
xOffset = parseFloat(parts[2].substring(1)); // 100
value + [xOffset, 0];
```

### 11.14 实用技巧：随机种子复现

```javascript
// 相同种子 → 相同随机序列
seedRandom(42, true);
random(0, 100);           // 永远返回相同值

// 基于索引的确定性随机
seedRandom(index, timeless = true);
random([0, 0], [1920, 1080]);
```

### 11.15 实用技巧：时间区间检测

```javascript
// 检测当前是否在某时间段内
startT = 2;
endT = 5;
isActive = (time >= startT && time <= endT);
isActive ? 100 : 0;
```

### 11.16 实用技巧：图层可见性控制

```javascript
// 根据摄像机距离控制透明度
cam = thisComp.activeCamera;
if (cam != null) {
    dist = length(transform.position, cam.position);
    fadeIn = 500;
    fadeOut = 2000;
    linear(dist, fadeIn, fadeOut, 100, 0);
} else {
    100;
}
```

### 11.17 实用技巧：自动锚点居中

```javascript
// 应用到 Anchor Point
sourceRect = thisLayer.sourceRectAtTime(time, false);
x = sourceRect.left + sourceRect.width / 2;
y = sourceRect.top + sourceRect.height / 2;
[x, y];
```

### 11.18 实用技巧：关键帧速度提取

```javascript
// 应用到 Slider Control
v = transform.position.velocityAtTime(time);
length(v);
```

### 11.19 实用技巧：合成尺寸自适应

```javascript
// 应用到 Position，自动居中
[thisComp.width / 2, thisComp.height / 2];

// 应用到 Scale，根据合成尺寸缩放
baseWidth = 1920;
scaleFactor = thisComp.width / baseWidth;
value * scaleFactor;
```

### 11.20 实用技巧：表达式注释模板

```javascript
// ============================================
// 表达式：弹簧物理
// 作者：AE Knowledge Vault
// 日期：2026-07-12
// 应用到：Position
// 参数说明：
//   stiffness - 刚度（80 = 适中）
//   damping - 阻尼（8 = 适中）
// ============================================

stiffness = 80;
damping = 8;
// ... 表达式主体
```

---

## 十二、表达式代码库（50 个）

### A. 弹性与物理类（10 个）

#### A1. 万能弹性（Penner 缓动）
```javascript
amp = 0.1; freq = 2.0; decay = 2.0;
n = 0;
if (numKeys > 0) {
    n = nearestKey(time).index;
    if (key(n).time > time) n--;
}
t = n > 0 ? time - key(n).time : 0;
v = n > 0 ? velocityAtTime(key(n).time - 0.01) : 0;
value + v * amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
```

#### A2. 弹簧物理（数值积分）
```javascript
rest = value; stiffness = 80; damping = 8; mass = 1;
p = rest; v = [0, 0]; dt = thisComp.frameDuration;
for (i = 0; i < 4; i++) {
    f = [(rest[0]-p[0])*stiffness/mass, (rest[1]-p[1])*stiffness/mass];
    v = [v[0]+f[0]*dt, v[1]+f[1]*dt];
    v = [v[0]*(1-damping*dt/mass), v[1]*(1-damping*dt/mass)];
    p = [p[0]+v[0]*dt, p[1]+v[1]*dt];
}
p;
```

#### A3. 弹跳球
```javascript
t = time - inPoint; g = 2000; v0 = -1200; bounces = 8; damping = 0.6;
y = value[1];
for (i = 0; i < bounces; i++) {
    bt = -2 * v0 / g * (1 + i);
    if (t < bt) { y = value[1] + v0 * t + 0.5 * g * t * t; break; }
    v0 = -v0 * damping; t -= bt;
}
[value[0], y];
```

#### A4. 摆锤
```javascript
length = 200; g = 980; amp = 45; damping = 0.5;
omega = Math.sqrt(g / length);
amp * Math.cos(omega * (time - inPoint)) * Math.exp(-damping * (time - inPoint));
```

#### A5. 惯性延迟
```javascript
leader = thisComp.layer("Leader");
delay = 0.1 * index;
leader.position.valueAtTime(time - delay);
```

#### A6. 摩擦减速
```javascript
v0 = [200, 0]; friction = 0.95; t = time - inPoint;
v = v0; p = value;
frames = Math.floor(t / thisComp.frameDuration);
for (i = 0; i < frames; i++) {
    p = [p[0]+v[0]*thisComp.frameDuration, p[1]+v[1]*thisComp.frameDuration];
    v = [v[0]*friction, v[1]*friction];
}
p;
```

#### A7. 软体果冻
```javascript
jiggle = 0.15; freq = 4; decay = 2;
t = time - inPoint;
w1 = Math.sin(freq * t * 2 * Math.PI) * Math.exp(-decay * t);
w2 = Math.cos(freq * t * 1.5 * 2 * Math.PI) * Math.exp(-decay * t * 0.8);
[(1 + jiggle * w1) * value[0], (1 - jiggle * w1 * 0.8) * value[1]];
```

#### A8. 重力下落
```javascript
g = 980; t = time - inPoint;
[value[0], value[1] + 0.5 * g * t * t];
```

#### A9. 浮力波动
```javascript
waterLevel = 540; density = 0.8; waveAmp = 10; waveFreq = 1;
y = value[1];
if (y > waterLevel) {
    wave = Math.sin(time * waveFreq * 2 * Math.PI) * waveAmp;
    y = waterLevel + wave + (y - waterLevel) * (1 - density);
}
[value[0], y];
```

#### A10. 风力 + 湍流
```javascript
windDir = [1, 0]; windStrength = 50; turbFreq = 1.5; turbAmp = 20;
t = time - inPoint;
wind = [windDir[0] * windStrength * t, windDir[1] * windStrength * t];
wob = wiggle(turbFreq, turbAmp) - value;
value + wind + wob * 0.3;
```

### B. 运动控制类（10 个）

#### B1. 自动跟踪
```javascript
target = thisComp.layer("Target");
target.position.valueAtTime(time - 0.1);
```

#### B2. 路径跟随
```javascript
path = thisComp.layer("Path").mask("Mask 1").maskPath;
progress = clamp((time - inPoint) / (outPoint - inPoint), 0, 1);
path.pointOnPath(progress);
```

#### B3. 朝向运动方向
```javascript
v = transform.position.velocityAtTime(time);
length(v) > 1 ? Math.atan2(v[1], v[0]) * 180 / Math.PI : value;
```

#### B4. 运动平滑
```javascript
smooth(0.2, 5);
```

#### B5. 速度提取
```javascript
v = thisComp.layer("Moving").position.velocityAtTime(time);
length(v);
```

#### B6. 加速度提取
```javascript
v1 = thisComp.layer("Moving").position.velocityAtTime(time);
v2 = thisComp.layer("Moving").position.velocityAtTime(time - thisComp.frameDuration);
length((v1 - v2) / thisComp.frameDuration);
```

#### B7. 范围约束
```javascript
[clamp(value[0], 100, 1820), clamp(value[1], 100, 980)];
```

#### B8. 运动放大
```javascript
source = thisComp.layer("Source");
sourcePos = source.position - source.transform.anchorPoint;
value + sourcePos * 2;
```

#### B9. 链式跟随
```javascript
leader = thisComp.layer("Chain_01");
delay = 0.05 * (index - leader.index);
target = leader.position.valueAtTime(time - delay);
value + (target - value) * 0.6;
```

#### B10. 多点平均
```javascript
p1 = thisComp.layer("P1").position;
p2 = thisComp.layer("P2").position;
p3 = thisComp.layer("P3").position;
[(p1[0]+p2[0]+p3[0])/3, (p1[1]+p2[1]+p3[1])/3];
```

### C. 循环与周期类（5 个）

#### C1. 无缝循环
```javascript
loopOut("cycle");
```

#### C2. 往复循环
```javascript
loopOut("pingpong");
```

#### C3. 偏移循环
```javascript
loopOut("offset");
```

#### C4. 周期正弦
```javascript
amp = 50; freq = 0.5;
value + Math.sin(2 * Math.PI * freq * time) * amp;
```

#### C5. 镜像往复
```javascript
cycleTime = 2;
t = (time - inPoint) % (cycleTime * 2);
if (t > cycleTime) t = cycleTime * 2 - t;
value + Math.sin(t * Math.PI / cycleTime) * 50;
```

### D. 随机与噪声类（8 个）

#### D1. 自然抖动 Wiggle
```javascript
wiggle(2, 50);
```

#### D2. 可循环 Wiggle
```javascript
freq = 1; amp = 50; loopTime = 3;
seedRandom(200, true);
startPos = random([5000, 5000]);
radius = (loopTime / Math.PI) * freq;
t = time % loopTime;
x = startPos[0] + Math.cos(2 * Math.PI * t / loopTime) * radius;
y = startPos[1] + Math.sin(2 * Math.PI * t / loopTime) * radius;
value + (noise([x, y]) - 0.5) * 2 * amp;
```

#### D3. 随机闪烁
```javascript
seedRandom(Math.floor(time * 8), true);
random() < 0.7 ? 100 : 20;
```

#### D4. 随机颜色
```javascript
seedRandom(index, true);
[random(), random(), random(), 1];
```

#### D5. 随机位置（粒子）
```javascript
seedRandom(index, true);
x = random(0, 1920); y = random(0, 1080);
vx = random(-50, 50); vy = random(-50, 50);
t = time - inPoint;
[x + vx * t, y + vy * t];
```

#### D6. 分形噪声
```javascript
freq = 1; amp = 100; octaves = 4; persistence = 0.5; lacunarity = 2;
total = 0; maxValue = 0; amplitude = 1; frequency = freq;
for (i = 0; i < octaves; i++) {
    total += noise([time * frequency, 0]) * amplitude;
    maxValue += amplitude;
    amplitude *= persistence;
    frequency *= lacunarity;
}
value + (total / maxValue) * amp;
```

#### D7. 有序随机
```javascript
values = [100, 200, 300, 400, 500];
stepTime = 0.5;
seed = Math.floor(time / stepTime);
seedRandom(seed, true);
values[Math.floor(random(values.length))];
```

#### D8. 随机旋转
```javascript
seedRandom(index, true);
random(0, 360);
```

### E. 音频驱动类（5 个）

#### E1. 音频 → 缩放
```javascript
a = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
s = linear(a, 5, 40, 100, 150);
[s, s];
```

#### E2. 音频 → 位置
```javascript
a = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
[value[0], value[1] - a * 5];
```

#### E3. 音频 → 旋转
```javascript
a = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
a * 3;
```

#### E4. 音频 → 透明度
```javascript
a = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
linear(a, 0, 30, 0, 100);
```

#### E5. 音频 → 颜色
```javascript
a = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
b = linear(a, 0, 50, 0.2, 1);
[b, b * 0.3, b * 0.1, 1];
```

### F. 3D 与空间类（4 个）

#### F1. 3D 距离
```javascript
a = thisComp.layer("A").position;
b = thisComp.layer("B").position;
Math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2);
```

#### F2. 摄像机朝向
```javascript
cam = thisComp.activeCamera;
delta = cam.position - transform.position;
[Math.atan2(delta[1], Math.sqrt(delta[0]**2 + delta[2]**2)) * 180 / Math.PI,
 Math.atan2(delta[0], delta[2]) * 180 / Math.PI, 0];
```

#### F3. 3D 螺旋路径
```javascript
center = [960, 540, 0]; radius = 200; speed = 90; heightPerSec = 100;
t = time - inPoint;
angle = degreesToRadians(t * speed);
[center[0] + Math.cos(angle) * radius, center[1] + t * heightPerSec, center[2] + Math.sin(angle) * radius];
```

#### F4. 3D 视差
```javascript
cam = thisComp.activeCamera;
depth = transform.position[2];
camOffset = cam.position - [960, 540, 0];
[value[0] - camOffset[0] * 0.5 * (depth / 1000), value[1] - camOffset[1] * 0.5 * (depth / 1000), value[2]];
```

### G. 文字动画类（4 个）

#### G1. 逐字波浪
```javascript
delay = 0.05;
y = Math.sin((time - (textIndex - 1) * delay) * 5) * 20;
[value[0], value[1] + y];
```

#### G2. 打字机
```javascript
fullText = "Hello World!";
chars = Math.floor((time - inPoint) * 10);
fullText.substring(0, Math.min(chars, fullText.length));
```

#### G3. 逐字变色（彩虹）
```javascript
hue = (textIndex * 30 + time * 60) % 360;
h = hue / 360;
c = 1; x = c * (1 - Math.abs((h * 6) % 2 - 1));
rgb = h < 1/6 ? [c,x,0] : h < 2/6 ? [x,c,0] : h < 3/6 ? [0,c,x] : h < 4/6 ? [0,x,c] : h < 5/6 ? [x,0,c] : [c,0,x];
[rgb[0], rgb[1], rgb[2], 1];
```

#### G4. 逐字大小波动
```javascript
baseSize = 72;
baseSize + Math.sin(time * 3 + textIndex * 0.5) * 10;
```

### H. 时间控制类（4 个）

#### H1. 时间冻结
```javascript
if (time > 2) 2; else time;
```

#### H2. 慢动作
```javascript
(time - inPoint) * 0.25 + inPoint;
```

#### H3. 时间倒流
```javascript
outPoint - (time - inPoint);
```

#### H4. 时间抖动
```javascript
time + wiggle(5, 0.1);
```

### I. 实用工具类（10 个）

#### I1. 自动居中
```javascript
[thisComp.width / 2, thisComp.height / 2];
```

#### I2. 锚点居中
```javascript
r = thisLayer.sourceRectAtTime(time, false);
[r.left + r.width / 2, r.top + r.height / 2];
```

#### I3. 网格对齐
```javascript
grid = 50;
[Math.round(value[0] / grid) * grid, Math.round(value[1] / grid) * grid];
```

#### I4. 标记触发动画
```javascript
m = thisComp.marker.nearestKey(time);
if (m.time <= time) {
    ease(time - m.time, 0, 1, 0, 100);
} else {
    0;
}
```

#### I5. 图层索引偏移
```javascript
offset = (index - 1) * 2;
[value[0] + offset, value[1] + offset];
```

#### I6. 合成尺寸自适应缩放
```javascript
baseWidth = 1920;
scaleFactor = thisComp.width / baseWidth;
value * scaleFactor;
```

#### I7. 摄像机距离透明度
```javascript
cam = thisComp.activeCamera;
dist = length(transform.position, cam.position);
linear(dist, 500, 2000, 100, 0);
```

#### I8. 安全 try-catch
```javascript
try {
    thisComp.layer("Target").position;
} catch (e) {
    value;
}
```

#### I9. 条件开关
```javascript
useExpression = effect("Switch")("Checkbox");
useExpression ? wiggle(2, 50) : value;
```

#### I10. 调试输出
```javascript
debug = "Time: " + time.toFixed(2) + "\nPos: " + value;
// 在文本图层上显示
debug;
```

---

## 附录：表达式参考资源

| 资源 | 地址 | 说明 |
|------|------|------|
| **motionscript.com** | motionscript.com | Dan Ebberts 的表达式圣经 |
| **Adobe 表达式示例** | helpx.adobe.com | 官方范例与文档 |
| **School of Motion** | schoolofmotion.com | 表达式基础+进阶教程 |
| **Creative COW** | creativecow.net | 活跃的表达式问答社区 |
| **ae-expressions.docs** | ae-expressions.docsforadobe.dev | 表达式更新日志 |
| **Expression User Guide** | helpx.adobe.com/after-effects/using/expression-basics.html | 官方表达式手册 |
| **AE Enhancers** | aescripts.com | 表达式插件与脚本资源 |

---

## 附录：常用表达式函数速查

### 数学函数
| 函数 | 说明 |
|------|------|
| `Math.sin(x)` | 正弦 |
| `Math.cos(x)` | 余弦 |
| `Math.tan(x)` | 正切 |
| `Math.atan2(y, x)` | 反正切（用于角度计算） |
| `Math.sqrt(x)` | 平方根 |
| `Math.pow(x, y)` | x 的 y 次幂 |
| `Math.abs(x)` | 绝对值 |
| `Math.round(x)` | 四舍五入 |
| `Math.floor(x)` | 向下取整 |
| `Math.ceil(x)` | 向上取整 |
| `Math.min(a, b)` | 最小值 |
| `Math.max(a, b)` | 最大值 |
| `Math.random()` | 0-1 随机数 |
| `Math.PI` | 圆周率 |

### AE 专用函数
| 函数 | 说明 |
|------|------|
| `wiggle(freq, amp)` | 平滑随机抖动 |
| `random(min, max)` | 随机数 |
| `noise(x)` | 柏林噪声 |
| `linear(t, tMin, tMax, value1, value2)` | 线性映射 |
| `ease(t, tMin, tMax, value1, value2)` | 缓动映射 |
| `easeIn(t, tMin, tMax, value1, value2)` | 缓入映射 |
| `easeOut(t, tMin, tMax, value1, value2)` | 缓出映射 |
| `clamp(value, limit1, limit2)` | 限制范围 |
| `length(v)` | 向量长度 |
| `normalize(v)` | 归一化向量 |
| `lerp(a, b, t)` | 线性插值 |
| `degreesToRadians(deg)` | 角度转弧度 |
| `radiansToDegrees(rad)` | 弧度转角度 |
| `timeToFrames(t)` | 时间转帧数 |
| `framesToTime(f)` | 帧数转时间 |
| `posterizeTime(fps)` | 抽帧 |
| `loopOut(type, numKeys)` | 循环输出 |
| `loopIn(type, numKeys)` | 循环输入 |
| `valueAtTime(t)` | 在指定时间取值 |
| `velocityAtTime(t)` | 在指定时间取速度 |
| `smooth(width, samples)` | 平滑值 |

### 图层与属性
| 函数 | 说明 |
|------|------|
| `thisComp` | 当前合成 |
| `thisLayer` | 当前图层 |
| `thisProperty` | 当前属性 |
| `thisComp.layer(name)` | 按名称引用图层 |
| `thisComp.layer(index)` | 按索引引用图层 |
| `thisComp.numLayers` | 合成图层总数 |
| `thisComp.width` | 合成宽度 |
| `thisComp.height` | 合成高度 |
| `thisComp.frameDuration` | 单帧时长（秒） |
| `thisComp.duration` | 合成总时长 |
| `thisComp.activeCamera` | 活动摄像机 |
| `time` | 当前时间 |
| `inPoint` | 图层入点 |
| `outPoint` | 图层出点 |
| `index` | 图层索引 |
| `numKeys` | 关键帧数量 |
| `key(index)` | 获取关键帧 |
| `nearestKey(time)` | 最近关键帧 |
| `transform.position` | 位置属性 |
| `transform.scale` | 缩放属性 |
| `transform.rotation` | 旋转属性 |
| `transform.opacity` | 透明度属性 |
| `transform.anchorPoint` | 锚点属性 |

---

## 附录：表达式调试工作流

### 步骤 1：编写与测试
1. 选中目标属性，按 `Alt+Click`（Mac）或 `Ctrl+Click`（Win）秒表
2. 在表达式字段输入代码
3. 按小键盘 `Enter` 或点击字段外应用

### 步骤 2：调试
- 点击表达式字段右上角的 `=` 切换启用/禁用
- 错误信息显示在字段下方红条中
- 选中属性后按 `EE` 快速跳转到表达式
- 使用文本图层打印变量值进行调试

### 步骤 3：优化
- 用 `posterizeTime()` 降低帧率测试
- 移除不必要的 `valueAtTime` 调用
- 将重复计算缓存到变量

### 步骤 4：保存复用
1. 选中含表达式的属性
2. `动画 → 保存动画预设`
3. 命名并保存
4. 从"效果与预设"面板拖拽复用

---

## 附录：表达式性能基准

| 操作复杂度 | 帧率影响 | 建议 |
|------------|----------|------|
| 简单算术 | 几乎无 | 可自由使用 |
| `wiggle()` | 轻微 | 限制倍频数 |
| 单层循环（< 100 次） | 中等 | 可接受 |
| 嵌套循环 | 严重 | 避免使用 |
| 跨图层 `valueAtTime` | 严重 | 缓存结果 |
| `noise()` 多倍频 | 中等 | 限制倍频数 |

---

> 相关链接：[[expressions-library]] · [[剪辑思维与逻辑]] · [[风格化剪辑技巧与预设]] · [[AE2025新功能速览]] · [[AE-MCP桥接技术]] · [[AE原子参数编译器]]

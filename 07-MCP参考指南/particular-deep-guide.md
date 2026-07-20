# Trapcode Particular 深度指南

## 核心理念

> 粒子设计的本质不是"调参数"，而是编排粒子的生命周期叙事：
> **从哪里来 → 怎么活动 → 如何变化 → 怎样消逝**
>
> 每个粒子都是一个独立的叙事单元，这些单元最终构成视觉事件。

---

## 🚨 粒子突兀的十大原因

| # | 错误 | 为什么突兀 | 修复 |
|---|------|-----------|------|
| 1 | Velocity Random = 0 | 所有粒子同速 = 像军队列队 | 设 20-50% |
| 2 | 无 Opacity over Life | 粒子突然消失 = "pop"感 | 淡入+淡出曲线 |
| 3 | 无 Size over Life | 粒子大小不变 = 机械感 | 钟形或衰减曲线 |
| 4 | Size Random = 0 | 所有粒子一样大 | 设 30-60% |
| 5 | 无 Turbulence Field | 粒子直线运动 = 真空中 | Amount 5-30 |
| 6 | Air Resistance = 0 | 无空气感 = 太干净 | 0.5-3.0 |
| 7 | 无 Motion Blur | 运动不连贯 | Shutter 180-360° |
| 8 | Opacity Random = 0 | 无层次深度感 | 设 20-50% |
| 9 | Color = 纯白不变 | 单一颜色 = 缺乏情绪 | 暖色+Color over Life |
| 10 | 无 Aux System | 单层粒子 = 扁平 | On Death 次级粒子 |

---

## 📐 参数优先级与设置顺序

```
第一层: Emitter 逻辑
  ├── Emitter Type (Point/Box/Sphere/Grid/Light/Layer)
  ├── Position XY / Position Z
  ├── Particles/sec
  ├── Velocity + Velocity Random [%]
  ├── Velocity from Motion [%]
  └── Direction + Direction Random [%]

第二层: 粒子外观
  ├── Particle Type (Sphere/Glow Sphere/Star/Cloudlet/Smokelet/Streaklet/Custom)
  ├── Size + Size Random [%]
  ├── Opacity + Opacity Random [%]
  ├── Color + Color Random [%]
  └── Sphere Feather / Rotation

第三层: 生命周期曲线 ★★★ (最重要)
  ├── Size over Life       ← 粒子如何生长/萎缩
  ├── Opacity over Life    ← 粒子如何显现/消失
  ├── Color over Life      ← 粒子颜色如何演变
  └── Life [sec] + Life Random [%]

第四层: 物理系统
  ├── Gravity
  ├── Air Resistance
  ├── Wind X / Wind Y / Wind Z
  ├── Turbulence Field (Amount, Scale, Evolution, Octaves)
  ├── Spherical Field (Strength, Radius, Position)
  └── Spin Amplitude + Spin Frequency

第五层: Aux System（次级粒子）
  ├── Emit (Off/Continuously/On Death)
  ├── Particles/sec
  ├── Life [sec]
  ├── Type
  ├── Size + Size over Life
  ├── Opacity + Opacity over Life
  ├── Color + Color over Life
  └── Gravity / Velocity

第六层: 渲染与集成
  ├── Motion Blur (On/Off, Shutter Angle, Type, Levels)
  ├── Depth of Field
  ├── 3D Camera integration
  └── Obscuration Layer
```

---

## 🎨 生命周期曲线设计（粒子不生硬的秘诀）

### Size over Life 曲线模板

```
烟雾/魔法/蒸汽:
  ┌─────────────────────┐
  │         ╱╲          │  钟形: 0 → 大 → 小 → 0
  │        ╱  ╲         │  粒子膨胀后温柔消散
  │  0 ──╱    ╲── 0    │
  └─────────────────────┘

火花/碎屑/余烬:
  ┌─────────────────────┐
  │  ╲                   │  衰减: 大 → 0
  │   ╲                  │  粒子快速衰减
  │    ╲_________       │
  └─────────────────────┘

飘浮灰尘/雪花:
  ┌─────────────────────┐
  │  ───────────╲       │  平台+尾降: 恒定 → 尾部淡出
  │              ╲      │
  │               ╲── 0 │
  └─────────────────────┘

脉冲/心跳:
  ┌─────────────────────┐
  │  ╱╲  ╱╲  ╱╲       │  多次波动: 呼吸感
  │ ╱  ╲╱  ╲╱  ╲      │
  │╱              ╲── 0│
  └─────────────────────┘
```

### Opacity over Life 黄金法则

**永远不要在 Opacity over Life 留为默认直线！**

```
模板 (适用于 90% 场景):
  0% ──→ 100% (前 5-15% 的生命周期)   ← 淡入
  100% ───────────────→ 100% (中间)    ← 保持
  100% ──→ 0% (后 15-30% 的生命周期)   ← 淡出

为什么必须淡入淡出：
- 粒子刚生成时瞬间满不透明 = "突然冒出"
- 粒子死亡时瞬间消失 = "click" 感
- 淡入让粒子"融入"场景，淡出让粒子"融入"背景
```

### Color over Life 自然渐变

```
火焰:
  白 → 亮黄 → 橙 → 红 → 暗红 → 黑

魔法光点:
  亮金 → 暖橙 → 暗金/琥珀

水下气泡:
  浅蓝白 → 中蓝 → 深蓝透明

科幻能量:
  白 → 亮青 → 深蓝 → 紫黑

霓虹粒子:
  亮粉白 → 品红 → 紫 → 暗紫
```

---

## 🌊 Turbulence Field 详解

Turbulence Field 是让粒子从"机械"变"有机"的核心工具。

| 参数 | 小值效果 | 大值效果 |
|------|---------|---------|
| **Amount** (5-200) | 5-15: 微妙的有机漂移 | 50-100: 暴风混沌 |
| **Scale** (5-200) | 5-20: 高频抖动(火焰, 热浪) | 50-100: 大尺度涌流(星云, 水下) |
| **Evolution** | 0=静态场 (粒子路径固定) | 10-30°/秒=持续变化流 |
| **Octave Scale** | 低值=简单噪声 | 高值=丰富细节层 |
| **Fade-in Time** | 0=立即受扰 | 0.5-1s=逐渐被扰动(更自然) |

### Turbulence 组合配方

```
魔法/仙境飘浮:
  Amount 5-8, Scale 60-80, Evolution 12°/s, Fade-in 0.5s
  → 大尺度缓慢流动，粒子像在仙境中飘

火焰/热浪:
  Amount 20-30, Scale 10-20, Evolution 30°/s, Fade-in 0
  → 高频剧烈抖动，模拟火焰不稳定

水下/深海:
  Amount 20-25, Scale 40-60, Evolution 8°/s, Fade-in 1s
  → 中等频率+大尺度，模拟水流浪涌

风暴/龙卷:
  Amount 80-120, Scale 5-15, Evolution 45°/s
  → 极高频+极大力，混沌风暴

烟雾扩散:
  Amount 15, Scale 30, Evolution 10°/s, Fade-in 0.8s
  → 中型扰动，烟雾逐渐散开

星空/银河:
  Amount 3-5, Scale 100-200, Evolution 5°/s
  → 几乎不可见的极缓流，星星微移
```

---

## 🔮 Aux System（次级粒子系统）

### 为什么 Aux 是专业分水岭

单层 Particular = 所有粒子行为一致 = 看起来假
Aux System = 主粒子产生次级粒子 = 模仿自然界"事件链"

```
自然界中的事件链:
  水滴落入水面 → 涟漪扩散 → 小水珠飞溅
  火焰燃烧 → 火星飞起 → 灰烬飘落
  烟花爆炸 → 主焰散开 → 尾迹微光消散

Particular 模拟:
  主粒子 = 水滴/火焰/烟花主体
  Aux On Death = 涟漪/火星/尾迹
  Aux Continuously = 尾迹/烟缕/光晕
```

### Aux 参数指南

```
Emit 模式:
  - "On Death": 主粒子死亡时产生 → 适合爆炸碎片、火花余烬、水花涟漪
  - "Continuously": 主粒子存活期间持续 → 适合尾迹、烟缕、魔法光粉

Aux 粒子设计原则:
  - Life: 比主粒子短 (0.5-1.5s vs 主粒子 2-6s)
  - Size: 比主粒子小 (2-8px vs 主粒子 5-20px)
  - 数量: 比主粒子少或相等
  - Gravity: 通常比主粒子大 (碎片比主体落得快)
  - Color From Main [%]: 50-80% (继承但偏移)
```

### Aux 配方示例

```
魔法光点尾迹:
  Emit: Continuously
  Particles/sec: 30-50
  Type: Streaklet (或小 Star)
  Life: 1s
  Size: 2-3px
  Gravity: -5 (跟随主粒子向上)
  Color From Main: 60%

爆炸碎片:
  Emit: On Death
  Particles/sec: 200-500
  Type: Sphere / Cloudlet
  Life: 0.5-1s
  Size: 3-8px
  Gravity: 200-500 (碎片快速下落)
  Color From Main: 80%

焰火尾迹:
  Emit: Continuously
  Particles/sec: 100
  Type: Streaklet
  Life: 0.8s
  Size: 2-4px
  Velocity: 0 (自然漂散)
  Opacity over Life: 1→0 (线性)
  Color From Main: 50%
```

---

## 🎬 常见场景完整配方

### 金色魔法粒子飘浮（文字装饰）

```
Particular Layer 1: 主粒子
  Emitter: Sphere, Position [960, 400, -200]
  Particles/sec: 150
  Velocity: 25, Velocity Random: 40%
  Direction: Outwards, Direction Random: 25%
  Life: 4s, Life Random: 50%
  Size: 5, Size Random: 50%
  Opacity Random: 40%
  Color: [1, 0.85, 0.4] (暖金), Color Random: 10%
  
  Size over Life: 钟形 (0→5px→1px→0)
  Opacity over Life: 0→100(前10%)→100→0(后20%)
  Color over Life: 亮金→暖橙→暗金

  Gravity: -15
  Air Resistance: 0.8
  Turbulence: Amount 8, Scale 65, Evolution 15°/s
  Motion Blur: ON, Shutter 360°

  Aux System:
    Emit: Continuously
    Particles/sec: 60
    Type: Streaklet
    Life: 1.2s
    Size: 2px
    Color From Main: 60%

Particular Layer 2: 背景微尘（可选，增加深度）
  Emitter: Box, [960, 540, -500], Box Size [800, 400, 100]
  Particles/sec: 30
  Velocity: 5, Velocity Random: 80%
  Life: 8s, Life Random: 60%
  Size: 2, Size Random: 80%
  Opacity: 30%, Opacity Random: 50%
  Gravity: -3
  Turbulence: Amount 3, Scale 120, Evolution 5°/s
  (无 Aux — 安静背景层)
```

### 动态烟雾

```
  Emitter: Point, Position [960, 800]
  Particles/sec: 80
  Velocity: 50, Velocity Random: 30%
  Direction: 0° (向上), Direction Random: 15%
  Life: 5s, Life Random: 40%
  
  Particle Type: Cloudlet
  Size: 40, Size Random: 30%
  Size over Life: 钟形 (5→45→60→20→0)
  Opacity: 15%, Opacity Random: 20%
  Opacity over Life: 0→15(前10%)→15→0(后25%)
  Color: [0.7, 0.7, 0.7]
  
  Gravity: -8 (缓慢上升)
  Air Resistance: 3.0
  Turbulence: Amount 15, Scale 30, Evolution 10°/s
  Wind X: 15 (微风向右)
  
  No Aux (烟雾本身够软)
```

### 粒子爆炸

```
  Emitter: Sphere, Position [960, 540]
  Particles/sec: 3000 (瞬时: 设关键帧 3000→0 at 0.1s)
  Velocity: 500, Velocity Random: 30%
  Direction: Outwards
  Life: 2s, Life Random: 35%
  
  Particle Type: Glow Sphere
  Size: 8, Size Random: 40%
  Size over Life: 衰减 (8→0)
  Opacity over Life: 100→0 (线性)
  Color over Life: 白→黄→橙→暗
  
  Gravity: 100
  Air Resistance: 0.3
  Turbulence: Amount 25, Scale 15, Evolution 20°/s
  
  Aux System:
    Emit: On Death
    Particles/sec: 500
    Type: Streaklet
    Life: 0.6s
    Size: 2
    Gravity: 300
```

---

## 🔧 运动模糊与性能优化

### Motion Blur 参数
```
Motion Blur: ON
Shutter Angle: 180° (标准) / 360° (长拖尾, 更流动)
Type: Linear (快速) / Subframe Sample (精确)
Levels: 8 (平衡) / 16 (高质量)
```

### 性能优化策略
```
1. 预览时 Particles/sec 设为最终值的 1/4
2. Preview Resolution: 1/4 或 1/2
3. Caps Lock 暂停刷新 → 调整完参数再释放
4. GPU Acceleration: 确保开启 (Particular 2023+)
5. Color Depth: 16 bpc (烟雾避免条带)
6. 预合成重粒子层 → 渲染为 ProRes → 替换编辑
7. 复杂场景拆分为多个轻量 Particular 实例
```

---

## 💡 大师级技巧

1. **多发射器分层**: 不用一个Emitter做所有事，2-3个Particular实例 (前/中/后景) 更有深度
2. **Light Emitter**: 用灯光驱动发射器 = 完美的3D运动轨迹
3. **Obscuration Layer**: 指定3D图层作为遮挡 → 粒子正确被前景物体遮挡
4. **保存预设**: 调试好的设置存为.ffx → 快速复用
5. **Designer面板**: 双击Particular效果 → 3D实时布局可视化
6. **子像素插值**: Position Subframe 设 10x Smooth → 消除快速运动时的步进感
7. **负重力 = 漂浮**: -0.5 到 -20 之间，配合 Air Resistance 创造各种漂浮感
8. **叠加模式**: 粒子层设 Screen/Add 混合 → 光感叠加，暗色自动消失

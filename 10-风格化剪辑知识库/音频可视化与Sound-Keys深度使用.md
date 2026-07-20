---
title: 音频可视化与Sound-Keys深度使用
date: 2026-07-04
tags:
  - SoundKeys
  - 音频可视化
  - 表达式
  - 音频驱动
  - BeatEdit
  - 粒子同步
  - 口型同步
  - 实时VJ
---
# 🎵 音频可视化与 Sound Keys 深度使用

> 从 AE 原生频谱到 Sound Keys 多频段驱动的完整知识体系——表达式体系、实战配方、节拍检测、实时 VJ 方案。

---

## 🧬 Sound Keys 核心功能

### 工作原理

```
音频层 → FFT 频谱分析（32 频段）→ 框选频率/振幅范围
→ 生成 Output 数值 → 表达式链接到任意 AE 属性
```

Trapcode Sound Keys（Maxon/Red Giant 出品，**不再单独销售**——Maxon 于 2021 年终止单独永久许可，2024 年完全停止独立销售。现须通过 **Red Giant Complete 订阅**获取，$85/月或 $639/年）本质是一个**关键帧生成器**。对音频执行 FFT（快速傅里叶变换），分解为 **32 个可调节频段**，以彩色频谱柱状图实时显示。

### 频段分布

| 颜色 | 频率范围 | 缩放参数 | 典型音乐元素 |
|------|----------|---------|-------------|
| **红色** | 极低频 / Sub-Bass | **Sub Base** | 次低频、底鼓 sub 部分 |
| **红-橙色** | 低频 / Bass | **Base** | 底鼓（Kick Drum）、贝斯线 |
| **绿色** | 中频 / Mid | **Mid** | 人声、军鼓（Snare）、吉他 |
| **蓝色** | 高频 / Treble | **Treble** | 镲片（Hi-hat）、齿音、氛围声 |

### 核心参数详解

#### 频谱调整

| 参数 | 功能 | 建议 |
|------|------|------|
| **Scale** | 统一缩放所有频谱柱高度 | 提高使安静段可见，但可能引入噪声 |
| **Q (Smoothness)** | 频率响应平滑度 | **低 Q** = 尖锐（鼓点瞬态）· **高 Q** = 平滑（氛围/人声） |
| **Sub Base** | 仅缩放极低频柱 | 底鼓 sub 分量 |
| **Base** | 仅缩放低频柱 | 贝斯驱动型音乐 |
| **Mid** | 仅缩放中频柱 | 人声驱动动画 |
| **Treble** | 仅缩放高频柱 | 镲片、沙锤细节 |

> ⚠️ Q 参数方向：高的 Q 滑块值 = 更多的平滑（更宽带宽），与传统电气工程的 Q 定义方向相反。

#### 范围设置（最多 3 个独立 Range）

| 参数 | 说明 |
|------|------|
| **Active** | 开关该 Range |
| **Type** | `Average of Range`（均值）/ `Peak of Range`（峰值）/ `On/Off Trigger`（阈值二值输出） |
| **Corner 1 & 2** | 定义频率/振幅选取矩形框 |
| **Falloff** | `Instant`（无衰减）/ `Linear`（线性）/ `Exponential`（指数，最自然）/ `None (Integrate)`（永不衰减，累积模式） |
| **Falloff Time** | 衰减时长（秒），Linear/Exponential 模式有效 |
| **Output Min/Max** | 预设范围或 Custom 自定义 |
| **Output** | 生成的关键帧参数，可表达式 pick-whip |

### Keyframe 模式 vs 表达式链接

| 模式 | 工作方式 | 优点 | 缺点 |
|------|---------|------|------|
| **Keyframe 输出** | 点击 Apply 生成逐帧关键帧 | 可编辑；可导出到 C4D | 关键帧多影响性能 |
| **表达式链接** | pick-whip 到 `effect("Sound Keys")("Output 1")` | 实时响应；不产生大量关键帧 | 不可视调试略不便 |

> 💡 一般使用表达式链接。仅需导出到其他软件（如 C4D）时才 Apply。

---

## 📐 音频驱动的表达式体系

### 基本访问

```javascript
// 单通道
sk = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 1");

// 三通道组合
temp1 = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 1");
temp2 = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 2");
temp3 = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 3");

// Convert Audio to Keyframes（免费原生）
amp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
```

### 衰减与平滑

```javascript
// smooth() — 平滑攻击和释放
sk = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 1");
smooth(sk, 0.1, 2);  // 0.1秒窗口, 2个采样

// 自定义指数衰减（Dan Ebberts 经典公式）
decay = 7.5;
gotOne = false;
for (t = time; t > 0; t -= thisComp.frameDuration) {
    if (sk.valueAtTime(t) >= 7 && sk.valueAtTime(t) <= 13) {
        gotOne = true;
        break;
    }
}
gotOne ? 100 / Math.exp((time - t) * decay) : 0;

// linear() 重映射
sk = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 1");
linear(sk, 0, 100, 50, 150);  // 输入 0-100 → 输出 50-150
```

### 多频段分层控制策略

```
低频（Kick/Bass）  → 驱动大动作：缩放、发射器速率、物理时间因子
中频（人声/Snare） → 驱动中等动作：位置偏移、不透明度、粒子大小
高频（Hi-hat）     → 驱动细节：发光强度、旋转、色彩偏移
```

```javascript
// 低频驱动发射速率
bassOutput = thisComp.layer("SK_Data").effect("Sound Keys")("Output 1");
linear(bassOutput, 0, 100, 10, 500);  // → Particles/sec 10-500

// 中频驱动粒子大小
midOutput = thisComp.layer("SK_Data").effect("Sound Keys")("Output 2");
linear(midOutput, 0, 100, 2, 15);  // → Size 2-15
```

### 弹性动画

```javascript
// 脉冲式缩放
minAudio = 0; maxAudio = 100;
minScale = 100; maxScale = 120;
audioLev = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 1");
s = linear(audioLev, minAudio, maxAudio, minScale, maxScale);
[s, s]

// 音频驱动 wiggle（频率随音乐变化）
seedRandom(1);
a = wiggle(
    thisComp.layer("SoundKeys").effect("Sound Keys")("Output 2"),  // 频率
    10  // 幅度
);
[a[0], a[1]]

// BPM 正弦脉冲（无需音频层）
bpm = 130;
freq = bpm / 60;
amplitude = 50;
amplitude * Math.sin(2 * Math.PI * freq * time + degreesToRadians(270));
```

### 阈值触发

```javascript
// 基本阈值
amp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
threshold = 20;
if (amp > threshold) { value + [0, 10]; } else { value; }

// Sound Keys On/Off Trigger 替代方案
amp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
threshold = 15;
amp > threshold ? 100 : 0;
```

---

## 🎬 音频可视化实战配方

### 1. AE 原生 Audio Spectrum — 参数速查

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **频段数** | 64-200 | 更高 = 更密集柱状图 |
| **最大高度** | 200-800 px | 取决于合成尺寸 |
| **音频持续时间** | 100-130 ms | 控制响应速度 |
| **厚度** | 3-6 | 柱的宽度 |
| **柔和度** | 10-30% | 柔化边缘 |
| **色相插值** | +50（微妙彩虹）/ +200（强烈循环） | |
| **面选项** | A 面 / B 面 / A 和 B 面 | |

### 2. 圆形频谱

```
1. 纯色层 → Audio Spectrum
2. 效果 → 扭曲 → 极坐标（矩形到极线，插值 100%）
3. 面选项 = B 面
4. 颜色对称 = 开
5. 旋转关键帧 + loopOut("cycle")
```

### 3. 自定义路径频谱

```
1. 钢笔工具在纯色层上画蒙版
2. Audio Spectrum → 路径 = 选择该蒙版
3. 蒙版模式设为"减"获得最佳裁切效果
```

### 4. 多层深度叠加

```
1. 频谱纯色层复制 2-3 份
2. 每份不同最大高度（400/700/1000）+ 不同颜色
3. 不同显示选项（内层模拟线，外层数字）
4. 全部预合成
5. 复制预合成 → 高斯模糊 35px → 混合模式 Add → 50% 不透明度（发光层）
```

### 5. 百叶窗方块 EQ 风格

```
Audio Spectrum → 效果 → 过渡 → 百叶窗
→ 删除自动生成关键帧
→ 过渡完成量 ~50%
→ 调整方向和宽度
```

### 6. 多频段分层 EQ

```
Layer 1: 起频 1, 止频 150（低音，蓝色，Max H 400）
Layer 2: 起频 150, 止频 500（中音，绿色，Max H 700）
Layer 3: 起频 500, 止频 2000（高音，粉色，Max H 1000）
→ 预合成 → 复制 + 高斯模糊 35px + Add + 50%
```

---

## 🎛️ AE 原生音频工具对比

### 三大工具全景

| 维度 | Audio Spectrum | Audio Waveform | Convert Audio to Keyframes |
|------|---------------|----------------|---------------------------|
| **类型** | 视觉效果（直接渲染） | 视觉效果（直接渲染） | 关键帧助手（纯数据） |
| **显示** | 频率内容（频段柱/线/点） | 原始振幅（波形线） | 空对象上的 Slider 关键帧 |
| **可驱动范围** | 仅视觉效果 | 仅视觉效果 | **任意属性** |
| **频段控制** | ✅ 按频段 | ❌ 整体振幅 | ❌ 整体振幅 |
| **最佳场景** | 快速 EQ 可视化 | 播客/极简波形 | 驱动任何属性深度定制 |

### Audio Spectrum vs Audio Waveform

| 维度 | Audio Spectrum | Audio Waveform |
|------|---------------|----------------|
| **显示内容** | 频率内容（低/中/高音） | 原始振幅随时间变化 |
| **核心参数** | `频段数` | `显示采样数` |
| **频率参数** | ✅（起/止频率） | ❌ |
| **色相插值** | ✅ | ❌ |
| **声道选择** | ❌ | ✅（单声道/左/右） |
| **最佳用途** | 条形可视化、圆形频谱 | 经典示波器线、原始波形 |

---

## 🔌 第三方工具与脚本对比

| 工具 | 类型 | 价格 | 核心功能 |
|------|------|------|---------|
| **Trapcode Sound Keys** | AE 插件 | Red Giant Complete 订阅（$85/月或 $639/年） | 32 频段 FFT 分析，3 个独立 Range，表达式输出 |
| **BeatEdit v2.2** | AE 脚本 | $149.99 | AI 节拍跟踪 + Beat Wiggle + Stagger 交错 |
| **Beatnik v1.06** | AE 脚本 | aescripts 定价 | 双算法峰值检测 + 时间重映射 + Sound Keys 集成 |
| **BPM Pulse** | AE 面板 | ~$15 | BPM 输入，Sine/Snappy 脉冲模式 |
| **BCC+ Audio Visualizer** | AE 插件 | Continuum Suite 部分 | 70+ 预设，Generator/Gradient/Mirror/Polar/Glow |
| **FreqReact** | AE 脚本 | davey.studio 独立销售 ~$30-60 | 8 种 Reactor 类型，多频段反应控制 |
| **Rhubarb Lip Sync** | 命令行 | **免费开源** | 音素识别，自动口型关键帧 |
| **Auto Lip Sync** | AE 脚本 | aescripts 市场 | 自动口型同步 |

### Sound Keys vs 原生工具 — 选择指南

| 场景 | 推荐 |
|------|------|
| "2 分钟做个波形可视化" | **Audio Spectrum** |
| "Logo 随音乐脉冲缩放" | **Convert Audio to Keyframes** + 表达式 |
| "只有底鼓触发缩放，人声不影响" | **Sound Keys**（需频段隔离） |
| "驱动复杂粒子系统，多维度控制" | **Sound Keys 3 个 Range → Particular** |
| "预算有限，全部免费" | **Convert Audio to Keyframes** + 表达式 |

---

## ✨ 音频驱动粒子（Particular + Sound Keys）

### 完整管线

```
音频 → 纯色层 → Sound Keys →
    Range 1: 框选低频 → Output 1 → Particular Physics Time Factor
    Range 2: 框选中频 → Output 2 → Particular Particles/sec
    Range 3: 框选高频 → Output 3 → Particular Turbulence/Air

新建纯色层 → Particular → 各属性 Alt+Click pick-whip 到 Sound Keys Output
```

### 关键表达式

```javascript
// Physics Time Factor — 粒子速度随节拍
audioLev = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 1");

// Particles/sec — 强拍爆发
audioLev = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 1");
linear(audioLev, 0, 100, 10, 500);

// 脉冲缩放
audioLev = thisComp.layer("SoundKeys").effect("Sound Keys")("Output 1");
s = linear(audioLev, 0, 100, 100, 120);
[s, s];
```

### 扩展

- **Trapcode Form** + Sound Keys → 网格状音频可视化
- **Trapcode Mir** + Sound Keys → 3D 地形随音频起伏
- **Optical Flares** + Sound Keys → 光效亮度/颜色闪烁

---

## 🎤 音频驱动的角色动画

### 口型同步方案

| 方案 | 工作量 | 精度 | 成本 |
|------|--------|------|------|
| **表达式法**：Convert Audio to Keyframes + 嘴型层 Opacity 条件切换 | 中 | 低-中 | 免费 |
| **Auto Lip Sync 插件** | 低 | 中-高 | 付费 |
| **Rhubarb Lip Sync** | 中 | 高 | **免费开源** |
| **Adobe Character Animator** | 低 | 中 | CC 订阅包含 |

### 身体律动表达式

```javascript
// 上下摆动
t = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
yOffset = linear(t, 0, 20, 0, -30);
value + [0, yOffset];

// 配合 Posterize Time 调低帧率（10fps）避免抖动
```

---

## 🎚️ 实时音频可视化方案

| 工具 | 场景 | 音频分析 | 渲染 | 成本 |
|------|------|---------|------|------|
| **TouchDesigner** | VJ 现场、互动装置 | 原生 CHOPs（FFT+频段+节拍） | 实时 GPU | 免费非商业版 |
| **Notch** | 高端演唱会/电竞赛事 | 实时 FFT + Sound Modifier | 实时 GPU 3D | 高端授权 |
| **Resolume** | VJ 混剪/现场混合 | 内置 FFT 驱动参数 | 实时片段+特效 | $299+（Avenue） |
| **After Effects** | **预制内容设计** | Sound Keys / Convert Audio | 离线渲染 | CC 订阅 |

### 典型实时堆栈

```
Ableton Live / DJ Mixer（音频源）
    ├── TouchDesigner（实时生成式 3D）
    │       └── Syphon/Spout → Resolume（最终混合输出）→ LED 墙/投影
    └── Notch（高保真实时 3D 视觉）
            └── NDI/Spout → Resolume
```

---

## 🇨🇳 中国市场资源

### B站推荐教程

| 教程 | BV 号 |
|------|-------|
| Sound Keys + 表达式 — 音频驱动手机动画教程 | BV1KV4y1W7uw |
| Sound Keys 插件 — 多维度音频可视化创意（多P详细） | BV1VE411Y76y |
| AE 如何制作动感的音频可视化效果（Particular + SK + Deep Glow） | BV1Lr4y1S7wA |

### 核心资源站点

| 站点 | 特点 |
|------|------|
| **lookae.com**（大众脸） | 国内最大汉化插件下载站 |
| **c4dsky.com**（书生影视） | AE/C4D 资源、模板、插件 |
| **cgtimo.com** | AE 插件/脚本汉化版 + 教程 |
| **newcger.com**（新CG儿） | 免费模板、素材 |
| **vjshi.com**（光厂） | 商用模板市场（如音乐可视化模板 ¥109） |

### 国内特色工具

| 工具 | 音频可视化能力 |
|------|--------------|
| **剪映** | AI 自动踩点——"节拍一"（稀疏，2拍一点）和"节拍二"（密集，1拍一点） |
| **必剪** | B站官方，内置音频可视化模板 |
| **快影** | 快手官方，音乐卡点功能 |

---

## 📊 Sound Keys 快速参考卡

| 项目 | 值 |
|------|-----|
| 频段数 | 32 |
| Range 数 | 最多 3 个独立 Range |
| 颜色编码 | 红(Sub Bass) → 红橙(Bass) → 绿(Mid) → 蓝(Treble) |
| Output 访问 | `effect("Sound Keys")("Output 1")` |
| 衰减模式 | Instant / Linear / Exponential / None(Integrate) |
| Range 类型 | Average / Peak / On/Off Trigger |
| 获取方式 | Red Giant Complete 订阅（$85/月或 $639/年），不再单独销售 |

### 表达式速查

| 目的 | 表达式 |
|------|--------|
| 获取 SK Output | `thisComp.layer("SK").effect("Sound Keys")("Output 1")` |
| 获取 Audio Amplitude | `thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider")` |
| 重映射范围 | `linear(input, inMin, inMax, outMin, outMax)` |
| 平滑数据 | `smooth(data, windowSec, samples)` |
| BPM 正弦脉冲 | `amp * Math.sin(2 * PI * (bpm/60) * time + phase)` |
| 阈值触发 | `if (amp > threshold) { result1; } else { result2; }` |

---

> 相关链接：[[Particular粒子实战案例大全]] · [[AE表达式进阶宝典]] · [[E3D与3D合成实战]] · [[商业项目全流程]] · [[🎬-风格化剪辑知识库-MOC]]

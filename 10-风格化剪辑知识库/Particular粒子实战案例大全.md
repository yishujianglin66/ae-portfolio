---
title: Particular粒子实战案例大全
date: 2026-07-04
tags:
  - Particular
  - 粒子特效
  - 实战配方
  - Stardust
  - 性能优化
  - 表达式
  - JSX
---
# ✨ Particular 粒子实战案例大全（完整版）

> Trapcode Particular 从核心参数到生产级配方——灰尘/火焰/魔法/雨雪/星空/光纤/水面——全覆盖。本文档面向 AE 合成师与动效设计师，提供完整的参数表、JSX 脚本、表达式与 20 个生产级案例。

---

## 目录

- [一、Particular 基础](#一particular-基础)
- [二、Emitter（发射器）完全指南](#二emitter发射器完全指南)
- [三、Particle（粒子）完全指南](#三particle粒子完全指南)
- [四、Physics（物理）完全指南](#四physics物理完全指南)
- [五、Aux System（辅助系统）](#五aux-system辅助系统)
- [六、渲染与优化](#六渲染与优化)
- [七、实战案例（20 个完整案例）](#七实战案例20-个完整案例)
- [八、与 AE 其他效果组合](#八与-ae-其他效果组合)
- [九、Particular 表达式控制](#九particular-表达式控制)
- [十、Particular JSX 脚本](#十particular-jsx-脚本)

---

## 一、Particular 基础

### 1.1 Trapcode Particular 插件概述

Trapcode Particular 是 Maxon（原 Red Giant）旗下的旗舰 3D 粒子系统插件，专为 Adobe After Effects 设计。自 2005 年由 Peder Norrby 开发以来，已成为行业标准的 2.5D/3D 粒子解决方案。

**核心特性：**

- 真实的 3D 粒子空间（与 AE 摄像机、灯光深度交互）
- 8 种发射器类型（Point / Box / Sphere / Grid / Light / Layer / Layer Grid / Text）
- 3 种物理模型（Air / Bounce / Fluid）
- 强大的辅助系统（Aux System）实现拖尾、子粒子分支
- 支持自定义 Sprite 粒子
- GPU 加速（Particular 5.0+）
- 内置 355+ 预设

**版本演进：**

| 版本 | 年份 | 关键特性 |
|------|------|---------|
| 1.0 | 2005 | 首版发布 |
| 2.0 | 2010 | 加入 Light 发射器、Sprite |
| 3.0 | 2016 | 新 UI、更快的渲染 |
| 4.0 | 2018 | OBJ 模型支持、Fluid 物理 |
| 5.0 | 2020 | GPU 加速、多帧渲染 |
| 6.0 | 2023 | 性能优化、预设库扩展 |

### 1.2 系统要求与安装

**最低系统要求：**

| 项目 | Windows | macOS |
|------|---------|-------|
| OS | Win 10 64-bit | macOS 10.14+ |
| CPU | Intel i5 / AMD Ryzen 5 | Apple M1 或 Intel i5 |
| RAM | 16 GB（推荐 32 GB+） | 同左 |
| GPU | NVIDIA GTX 1060 / AMD RX 580 | Apple GPU 或同等级 |
| VRAM | 4 GB | 4 GB |
| AE 版本 | CC 2019+ | CC 2019+ |
| 硬盘 | 2 GB（含预设） | 2 GB |

**安装步骤：**

1. 下载 Maxon App（<https://www.maxon.net/maxon-app>）
2. 登录 Maxon 账号
3. 在 "Products" 中选择 Trapcode Suite 安装
4. 重启 AE，在 Effect → Trapcode → Particular 中调用
5. 激活许可（订阅或试用 14 天）

**卸载注意**：通过 Maxon App 卸载，不要手动删除插件文件，否则会残留预设索引。

### 1.3 界面与参数总览

Particular 的所有参数集中在 Effect Controls 面板，分为 9 个主要折叠组：

```
Particular
├── Emitter（发射器）
├── Particle（粒子）
├── Shader（着色）
├── Physics（物理）
├── Aux System（辅助系统）
├── World Transform（世界变换）
├── Visibility（可见性）
├── Rendering（渲染）
└── About（关于）
```

**关键开关：**

- `Visibility`：可见性渐变（控制远近距离淡出）
- `World Transform`：整体旋转粒子世界（不影响发射器位置）
- `Preview`：预览模式（仅显示首帧或当前帧粒子）

### 1.4 核心概念：Emitter, Particle, Physics, Aux System

**1. Emitter（发射器）**
决定粒子"在哪里、以什么方式"出生。可以理解为粒子工厂。

**2. Particle（粒子）**
决定每个粒子"长什么样、活多久"。包括大小、颜色、纹理、生命周期等。

**3. Physics（物理）**
决定粒子"出生后如何运动"。模拟重力、风、湍流、碰撞等。

**4. Aux System（辅助系统）**
让主粒子在特定时刻（死亡时、持续、碰撞时）发射子粒子，用于制作拖尾、爆炸碎片、烟雾延续等效果。

> 这四个模块构成 Particular 的"粒子生命周期"：**出生 → 表现 → 运动 → 衍生 → 死亡**。

### 1.5 渲染模式与性能优化

Particular 提供三种渲染模式：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| Full Render | 完整渲染，所有粒子精确计算 | 最终输出 |
| Draft Render | 草稿模式，跳过部分细节 | 实时预览 |
| Motion Preview | 仅显示运动轨迹 | 调试运动路径 |

**性能优化建议：**

1. 编辑阶段使用 Draft Render，最终渲染时切回 Full
2. 限制粒子寿命（Life）—— 越短 = 越少活跃粒子 = 越快
3. 关闭未使用的系统（如不用 Aux 就关闭）
4. 长合成拆分为短循环（51 分钟 → 14h 渲染）
5. GPU 渲染（Particular 5+）
6. RAM 32 GB+

---

## 二、Emitter（发射器）完全指南

发射器（Emitter）决定粒子的"出生方式"。它是 Particular 的第一个核心模块。

### 2.1 Emitter Type 详解

#### 2.1.1 Point（点发射器）

**行为**：所有粒子从同一个三维点出发。

**关键参数：**

| 参数 | 单位 | 范围 | 说明 |
|------|------|------|------|
| Position X/Y/Z | px | -∞ ~ +∞ | 发射器三维位置 |
| Direction Spread | ° | 0 ~ 360 | 发射角度散布 |
| Velocity | px/s | 0 ~ 5000 | 初始速度 |
| Velocity Random | % | 0 ~ 100 | 速度随机百分比 |
| Velocity from Motion | % | 0 ~ 100 | 继承发射器运动速度 |
| Emission Rate | p/s | 0 ~ 1e6 | 每秒发射粒子数 |

**适用场景**：
- 爆炸（一次性高密度发射）
- 喷泉、火花
- 魔法聚焦点
- 烟花

**JSX 示例**：

```javascript
// 设置点发射器爆炸效果
var layer = app.project.activeItem.selectedLayers[0];
var fx = layer.property("Effects").property("Particular");
fx.property("Emitter").property("Emitter Type").setValue(0); // Point
fx.property("Emitter").property("Particles/sec").setValueAtTime(0, 0);
fx.property("Emitter").property("Particles/sec").setValueAtTime(1.0, 5000);
fx.property("Emitter").property("Particles/sec").setValueAtTime(1.05, 0);
fx.property("Emitter").property("Velocity").setValue(800);
fx.property("Emitter").property("Velocity Random").setValue(50);
```

#### 2.1.2 Box（盒形发射器）

**行为**：粒子在 3D 盒形体积内随机位置出生。

**关键参数：**

| 参数 | 单位 | 范围 | 说明 |
|------|------|------|------|
| Emitter Size X | px | 0 ~ 10000 | 盒子宽度 |
| Emitter Size Y | px | 0 ~ 10000 | 盒子高度 |
| Emitter Size Z | px | 0 ~ 10000 | 盒子深度 |
| Position | px | — | 盒子中心位置 |

**适用场景**：
- 烟雾、灰尘充满空间
- 雨、雪（扁平 Box 覆盖屏幕顶部）
- 漂浮粒子（无方向速度）

#### 2.1.3 Sphere（球形发射器）

**行为**：粒子在球体内随机分布，越接近中心密度越高。

**关键参数：**

| 参数 | 单位 | 说明 |
|------|------|------|
| Emitter Size X/Y/Z | px | 球体半径 |
| Position | px | 球心 |

**适用场景**：
- 球形爆炸
- 星空背景
- 能量球

#### 2.1.4 Grid（网格发射器）

**行为**：粒子按规则网格点阵生成。

**关键参数：**

| 参数 | 说明 |
|------|------|
| Particles in X/Y/Z | 网格各轴粒子数 |
| Emitter Size X/Y/Z | 网格总尺寸 |

**适用场景**：
- 数据流、LED 阵列
- 规则结构化粒子
- 矩阵效果

#### 2.1.5 Light（灯光发射器）

**行为**：将 AE 合成中的 Point Light / Spot Light 作为发射源。

**关键参数：**

| 参数 | 说明 |
|------|------|
| Light Name | 选择匹配名称的灯光 |
| Use Light Properties | 启用灯光颜色/强度影响粒子 |
| Use Size from Light | 灯光大小影响发射范围 |

**适用场景**：
- 拖尾光迹（Video Copilot 经典）
- 光绘效果
- 多点同时发射（多个灯光）

#### 2.1.6 Layer（图层发射器）

**行为**：以 3D 图层的 Alpha 通道作为发射面，粒子从图像中"出生"。

**关键参数：**

| 参数 | 说明 |
|------|------|
| Layer | 选择参考图层 |
| Layer Sampling | 采样方式（出生、随机、顺序） |
| Layer RGB Usage | RGB 通道如何影响粒子颜色 |
| Particle Birth Time | 粒子出生时间映射 |

**适用场景**：
- Logo 溶解、文字化粒子
- 图像元素化为粒子
- 粒子汇聚成图像（反向使用）

#### 2.1.7 Layer Grid（图层网格发射器）

**行为**：在图层 Alpha 上按网格采样，规则阵列粒子。

**适用场景**：自定义形状的结构化粒子矩阵。

#### 2.1.8 Text（文字发射器）

**行为**：以 AE 文字图层的轮廓作为发射面。

**关键参数**：

| 参数 | 说明 |
|------|------|
| Text Layer | 选择文字图层 |
| Sampling Mode | 采样模式 |
| Character/Word/Line | 按字符/词/行采样 |

**适用场景**：
- 文字粒子化
- 文字汇聚消散

### 2.2 Position 相关参数

| 参数 | 说明 | 表达式示例 |
|------|------|-----------|
| Position XY | 发射器 XY 位置 | `wiggle(1, 100)` |
| Position Z | 发射器 Z 位置 | `Math.sin(time)*200` |
| Position Subframe | 子帧采样模式（Linear / 10x / 10x Smooth） | — |

**Position Subframe** 影响"快速移动发射器时拖尾是否平滑"。10x Smooth 用于高速运动，避免拖尾出现阶梯。

### 2.3 Direction（方向）参数

| 选项 | 行为 |
|------|------|
| Outward | 球形向外（默认） |
| Directional | 单一方向 |
| Bi-Directional | 双向 |
| Random | 随机方向 |
| Demo | 演示模式 |

**Directional 配套参数**：

| 参数 | 单位 | 说明 |
|------|------|------|
| X Rotation | ° | 方向 X 旋转 |
| Y Rotation | ° | 方向 Y 旋转 |
| Spread | ° | 散布角度（0 = 直线，180 = 半球） |

### 2.4 Velocity（速度）参数

| 参数 | 单位 | 默认 | 说明 |
|------|------|------|------|
| Velocity | px/s | 100 | 初始速度 |
| Velocity Random | % | 0 | 随机百分比 |
| Velocity from Motion | % | 0 | 继承发射器运动 |
| Velocity Distribution | 0-1 | 0.5 | 速度分布偏向 |

### 2.5 Emission Rate（发射速率）

**Particles/sec** 决定每秒发射粒子数。结合关键帧可实现"爆炸"（突增）、"渐变"（递增/递减）等效果。

**表达式示例（节拍发射）**：

```javascript
// 每秒爆发一次
var t = time % 1;
t < 0.05 ? 5000 : 0;
```

### 2.6 Emitter Size 参数

不同 Emitter Type 的 Size 含义不同：

| Emitter Type | Size 含义 |
|--------------|----------|
| Point | 无 |
| Box | 盒子三轴长度 |
| Sphere | 球体半径 |
| Grid | 网格总尺寸 |
| Layer | 不适用 |
| Light | 不适用（灯光大小决定） |

### 2.7 Spread 参数

Spread 控制粒子发射的散布角度（仅 Direction = Directional / Bi-Directional 时有效）。

| Spread 值 | 效果 |
|----------|------|
| 0 | 完全直线 |
| 30 | 窄束 |
| 90 | 半球 |
| 180 | 全方向 |

### 2.8 各发射器参数速查表

| 发射器 | 最佳用途 | 关键参数 |
|--------|---------|---------|
| Point | 爆炸、聚焦喷射 | Position, Velocity |
| Box | 烟雾、灰尘、雨、雪 | Emitter Size XYZ |
| Sphere | 爆炸、星空、碎片 | Emitter Size |
| Grid | 数据流、LED 阵列 | Particles in XYZ |
| Light | 拖尾光线、光绘 | Light Name, Position |
| Layer | Logo 溶解、文字化粒子 | Layer, Layer Sampling |
| Layer Grid | 自定义形状阵列 | Layer, Grid Settings |
| Text | 文字粒子化 | Text Layer, Sampling Mode |

---

## 三、Particle（粒子）完全指南

粒子模块决定每个粒子的"外观与生命周期"。

### 3.1 Life（生命周期）

| 参数 | 单位 | 默认 | 说明 |
|------|------|------|------|
| Life | 秒 | 5 | 粒子寿命 |
| Life Random | % | 0 | 寿命随机 |

> **寿命与粒子数量关系**：屏幕上同时存在的粒子数 ≈ `Particles/sec × Life`。这是性能估算的核心公式。

### 3.2 Size（大小）

| 参数 | 单位 | 说明 |
|------|------|------|
| Size | px | 粒子尺寸 |
| Size Random | % | 大小随机 |
| Size over Life | 曲线 | 寿命内大小变化 |

**Size over Life 曲线形状**：

| 形状 | 效果 |
|------|------|
| ↗ 上升 | 渐大（烟雾扩散） |
| ↘ 下降 | 渐小（消散） |
| ↗↘ 山峰 | 先大后小（爆炸） |
| ↘↗ 谷底 | 先小后大（汇聚） |
| 平直 | 恒定 |

### 3.3 Size over Life（生命周期大小变化）

通过双击曲线点添加控制点，拖动调整贝塞尔曲线。常见预设：

```
爆炸：1.0 → 0.3（前 20% 急速缩小）
烟雾：0.3 → 1.0（线性增长）
萤火虫：保持 0.5 → 0.5
汇聚：0.1 → 1.0（指数上升）
```

### 3.4 Color（颜色）

| 参数 | 说明 |
|------|------|
| Color | 主色 |
| Color Random | 颜色随机度 |
| Color over Life | 寿命内颜色渐变 |
| Random Color Mode | 颜色随机模式（同色/渐变/HSV） |

**Color over Life 多色梯度示例**：

```
火焰：白(0%) → 黄(20%) → 橙(50%) → 红(80%) → 黑(100%)
魔法：白 → 金 → 青 → 品红
死亡：彩色 → 灰色
```

### 3.5 Color over Life（生命周期颜色变化）

通过 Gradient Editor 设置多色渐变。每一档对应粒子寿命的百分比位置。

### 3.6 Opacity（透明度）

| 参数 | 说明 |
|------|------|
| Opacity | 整体透明度 |
| Opacity Random | 随机透明度 |
| Opacity over Life | 寿命内透明度曲线 |

**常用 Opacity over Life 曲线**：

- 烟雾：淡入 → 保持 → 淡出（梯形）
- 火花：满 → 线性消失
- 闪烁：满 → 0 → 满 → 0（多峰）

### 3.7 Opacity over Life

与 Size over Life 类似，通过曲线编辑。重要提示：**Opacity over Life 的"出生淡入"和"死亡淡出"** 能避免粒子突然出现/消失的"硬边"。

### 3.8 Blend Mode（混合模式）

| 模式 | 效果 | 适用 |
|------|------|------|
| Normal | 普通叠加 | 默认 |
| Add | 相加（变亮） | 火、光、爆炸 |
| Screen | 滤色 | 烟雾、光线 |
| Lighten | 取亮 | 光斑 |

> **Add 是粒子的"黄金模式"**：多个粒子叠加自然产生过曝，模拟真实光感。

### 3.9 Texture（纹理）

**Particle Type 选项**：

| 类型 | 视觉特征 | 常见用途 |
|------|---------|---------|
| Sphere | 实体 3D 球（可受光） | 碎片、火花 |
| Glow Sphere | 柔光球（混合 Add） | 余烬、魔法、萤火虫 |
| Star | 星形粒子 | 魔法闪烁、闪光 |
| Cloudlet | 软半透明体积块 | 烟雾、灰尘、大气 |
| Streaklet | 可调长度拖尾 | 雨、光迹、光纤 |
| Sprite | 自定义图像/合成 | 花瓣、叶子、自定义形状 |
| Sprite (No Color) | 不染色 Sprite | 真实素材粒子 |
| Faded Sphere | 软边球 | 雪花、光斑 |
| Square | 方块 | 像素风 |
| Circle | 圆 | 简单粒子 |

**Sprite 设置参数**：

| 参数 | 说明 |
|------|------|
| Texture | 选择图层作为纹理 |
| Time Sampling | 时间采样方式 |
| Subframe Sampling | 子帧采样 |
| Number of Samples | 采样数 |
| Random Frame | 随机帧 |
| Split Color | 拆分颜色通道 |
| Layer RGB Usage | RGB 通道用法 |
| Layer Alpha Usage | Alpha 通道用法 |

### 3.10 Glow（发光）

> Particular 自身无 Glow 模块，需配合 AE 的 Glow 效果使用。详见第八章。

### 3.11 完整参数表

| 模块 | 参数 | 范围 | 默认 |
|------|------|------|------|
| Particle | Life | 0-60s | 5 |
| Particle | Life Random | 0-100% | 0 |
| Particle | Particle Type | 0-10 | 0 (Sphere) |
| Particle | Sphere Feather | 0-100 | 50 |
| Particle | Size | 0-100 | 5 |
| Particle | Size Random | 0-100% | 0 |
| Particle | Size over Life | curve | flat |
| Particle | Opacity | 0-100 | 100 |
| Particle | Opacity Random | 0-100% | 0 |
| Particle | Opacity over Life | curve | flat |
| Particle | Color | RGB | white |
| Particle | Color Random | 0-100% | 0 |
| Particle | Color over Life | gradient | flat |
| Particle | Blend Mode | 0-3 | 0 (Normal) |
| Particle | Streaklet Amount | 0-100 | 10 |
| Particle | Cloudlet Density | 0-100 | 50 |

---

## 四、Physics（物理）完全指南

物理系统决定粒子出生后的运动方式。

### 4.1 Physics Model（物理模型）

| 模型 | 用途 |
|------|------|
| **Air** | 默认——气体行为（烟雾、灰尘、火） |
| **Bounce** | 碰撞地面层——水滴溅射、弹跳碎片 |
| **Fluid** | 液体模拟（水、油、粘稠物） |

### 4.2 Air 参数详解

Air 模拟气体行为，是默认且最常用的物理模型。

#### 4.2.1 Motion Path（运动路径）

不可用——这是 Air 模型下的概念。Air 主要通过以下参数控制：

#### 4.2.2 Spin（旋转）

| 参数 | 单位 | 说明 |
|------|------|------|
| Spin Amplitude | °/s | 旋转幅度 |
| Spin Amount | % | 旋转百分比 |
| Spin Phase | ° | 旋转相位 |

**Spin 用途**：让粒子在运动中带轻微自旋，避免过于规则的"线性"感。

#### 4.2.3 Wind（风）

| 参数 | 单位 | 说明 |
|------|------|------|
| Wind X | px/s | X 方向风 |
| Wind Y | px/s | Y 方向风 |
| Wind Z | px/s | Z 方向风 |
| Air | — | 空气阻力（越大，粒子越快停止） |

**Wind 表达式（阵风）**：

```javascript
// 阵风：随机大风
var gust = Math.sin(time * 0.5) * 100;
gust + wiggle(0.3, 50);
```

#### 4.2.4 Turbulence（湍流）

| 参数 | 单位 | 说明 |
|------|------|------|
| Affect Size | % | 影响大小 |
| Affect Position | px | 影响位置（最重要） |
| Scale | px | 湍流场缩放 |
| Complexity | 1-6 | 复杂度（噪声叠加层数） |
| Evolution | — | 演化（随时间变化） |
| Octave Multiplier | — | 倍频 |
| Octave Scale | — | 倍频缩放 |
| Move with Wind | % | 跟随风移动 |
| Random Seed | int | 随机种子 |

**Turbulence 应用案例**：

```
灰尘：Affect Position 50-200, Scale 10-30, Complexity 3
火焰卷动：Affect Position 100-300, Scale 5-15, Evolution +time*30
烟雾上升：Affect Position 100-200, Scale 20-40
魔法闪烁：Affect Position 30-80, Scale 5-10
```

#### 4.2.5 Wavy（波浪）

`Wavy` 是 Turbulence 的子模式，让湍流形成波浪状运动。用于水波、海面气流。

### 4.3 Bounce 参数详解

Bounce 模型让粒子与 3D 图层（Floor Layer）发生碰撞反弹。

#### 4.3.1 Bounce Plane（弹跳平面）

| 参数 | 说明 |
|------|------|
| Floor Layer | 选择作为地面的 3D 图层 |
| Floor Mode | 反弹模式（无限平面 / 有限） |

#### 4.3.2 Friction（摩擦力）

| 参数 | 单位 | 说明 |
|------|------|------|
| Friction | 0-100 | 摩擦系数 |
| Slide | 0-100 | 滑行系数 |

**Friction 数值参考**：

```
0 = 完全无摩擦（冰面）
30 = 木地板
50 = 水泥
80 = 沙地
100 = 黏住不动
```

#### 4.3.3 Bounce（弹跳系数）

| 参数 | 单位 | 说明 |
|------|------|------|
| Bounce | 0-200% | 反弹高度百分比 |
| Bounce Velocity | — | 反弹速度 |
| Max Bounces | int | 最大反弹次数 |

### 4.4 Fluid 参数详解

Fluid（流体）模拟粒子群作为流体的运动。

| 参数 | 单位 | 说明 |
|------|------|------|
| Velocity | px/s | 流体速度 |
| Viscosity | 0-100 | 粘度 |
| Diffusion | 0-100 | 扩散率 |
| Simulation | — | 仿真质量（Draft/High/Very High） |

**Fluid 应用场景**：
- 水流
- 油漆
- 烟雾高仿真
- 沙流

> **Fluid 性能开销大**：建议限制粒子数（< 50000）+ 短寿命（< 3s）。

### 4.5 Gravity（重力）

所有物理模型共享：

| 参数 | 单位 | 默认 | 说明 |
|------|------|------|------|
| Gravity | px/s² | 0 | 重力（正=向下） |
| Gravity Random | % | 0 | 随机重力 |
| Gravity Attract | — | 0 | 朝向发射器吸引 |

**重力数值参考**：

```
无重力（飘）= 0
雪 = 20-60
雨 = 500-1000
火花下落 = 100-200
真实地球（视觉感受） = 200-500
```

---

## 五、Aux System（辅助系统）

Aux System 让主粒子在特定时机"生育"子粒子，用于制作拖尾、爆炸碎片、烟雾延续。

### 5.1 Emit（发射模式）

| 模式 | 行为 | 典型场景 |
|------|------|---------|
| Off | 关闭 | — |
| At Death | 主粒子死亡时发射 | 爆炸碎片、烟花 |
| Continuously | 持续发射 | 拖尾、烟雾 |
| On Collision | 碰撞时发射 | 水滴溅射（需 Bounce 物理） |

### 5.2 Aux 粒子参数

| 参数 | 说明 |
|------|------|
| Emit Rate | 子粒子发射率 |
| Emit Distance | 发射距离 |
| Emit Probability | 发射概率 |
| Type | 子粒子类型 |
| Size | 子粒子大小 |
| Size over Life | 子粒子大小曲线 |
| Color over Life | 子粒子颜色 |
| Life | 子粒子寿命 |
| Opacity | 子粒子透明度 |
| Inherit Velocity | 继承父粒子速度 |
| Inherit Size | 继承父粒子大小 |
| Inherit Color | 继承父粒子颜色 |
| Inherit Opacity | 继承透明度 |
| Blend Mode | 子粒子混合模式 |
| Gravity | 子粒子重力 |
| Wind | 子粒子风 |
| Turbulence Position | 子粒子湍流位置 |
| Spread | 子粒子散布 |
| Velocity | 子粒子速度 |

### 5.3 Aux 粒子与主粒子的关系

**继承（Inherit）参数**决定子粒子从父粒子获取多少属性：

| Inherit 值 | 含义 |
|-----------|------|
| 0 | 完全独立 |
| 50 | 继承一半 |
| 100 | 完全继承 |

**典型组合**：

| 场景 | Aux 配置 |
|------|---------|
| 拖尾 | Continuously, Rate 50, Velocity 0, Inherit Velocity 100, Size 30% |
| 爆炸碎片 | At Death, Rate 50, Velocity 500, Life 1s |
| 水滴溅射 | On Collision, Rate 500, Velocity 100, Life 0.5s |
| 烟雾延续 | At Death, Cloudlet, Size 200, Life 5s, Opacity 10% |

---

## 六、渲染与优化

### 6.1 渲染模式

| 模式 | 说明 |
|------|------|
| Full Render | 完整渲染 |
| Draft Render | 草稿（跳过部分计算） |
| Motion Preview | 仅运动预览 |

### 6.2 Motion Blur（运动模糊）

| 参数 | 说明 |
|------|------|
| Motion Blur | On/Off |
| Shutter Angle | °（默认 180，大值=长拖影） |
| Motion Blur Depth | 模糊深度 |

> **雨、光迹必开 Motion Blur**，使快速移动粒子产生自然拖影。

### 6.3 Depth of Field（景深）

| 参数 | 说明 |
|------|------|
| Depth of Field | On/Off |
| Blur Amount | 模糊量 |
| Focal Distance | 焦距 |
| Focal Point Size | 焦点大小 |
| Aperture Size | 光圈大小 |

景深与 AE 摄像机的 DOF 联动。需要打开摄像机层的 "Enable Depth of Field"。

### 6.4 性能优化技巧

| 排名 | 策略 | 效果 |
|------|------|------|
| 1 | 长合成拆为短循环 | 51 分钟渲染从 50h 压至 14h |
| 2 | 限制粒子寿命 | 越短 = 越少活跃粒子 = 越快 |
| 3 | GPU 渲染（Particular 5+） | CUDA/Metal 加速 |
| 4 | 关闭不用系统（Aux / Spherical Field） | 节省计算 |
| 5 | Precomp + Time Remap 快拖尾 | 4x 时长合成→重映射加速 |
| 6 | RAM 32GB+ | 16GB 是底线 |

**B 站 30x 加速技巧**：预渲染粒子层为半分辨率代理 → 时间线编辑用代理 → 最终渲染切回全分辨率。

### 6.5 GPU 加速设置

Particular 5+ 支持 GPU 渲染：

1. 在 Rendering 模块下找到 `GPU`
2. 选择 `Auto` / `CUDA` / `Metal` / `OpenCL`
3. 启用后渲染速度提升 2-5 倍

> 若 GPU 不稳定，回退到 CPU 渲染。Mac M 系列原生支持 Metal 加速。

---

## 七、实战案例（20 个完整案例）

### 7.1 粒子汇聚文字

**效果描述**：粒子从四周飞向文字图层，最终汇聚成文字形状。

**参数设置**：

```
Emitter:
  Emitter Type: Layer
  Layer: Text Layer (预先创建的文字 3D 图层)
  Layer Sampling: Random - Still Frame
  Emitter Size X/Y/Z: 2000/2000/0
  Position: 画面中心
  Particles/sec: 5000
  Velocity: 800
  Velocity Random: 50
  Direction: Outward（粒子从文字向外发射后通过反向汇聚实现）

Physics:
  Physics Model: Air
  Air:
    Wind: 0,0,0
    Turbulence: Affect Position 0

Particle:
  Life: 2s
  Particle Type: Sphere
  Size: 3
  Opacity: 80
  Color: 白色

实现汇聚：
  使用 Time-Reverse Layer（图层 → 时间 → 时间反向图层）将"消散"动画反转为"汇聚"
```

**实现步骤**：

1. 新建合成 1920×1080，10 秒
2. 创建文字层 "PARTICLES"，开启 3D
3. 新建黑色固态层，添加 Particular
4. Emitter Type = Layer，Layer = 文字层
5. Particles/sec = 5000，Velocity = 800
6. Particle Life = 2s，Type = Sphere，Size = 3
7. 渲染前 3 秒（粒子飞散）
8. 右键图层 → Time → Time-Reverse Layer
9. 在反向后加 Glow + Curves 提亮

**JSX 脚本**：

```javascript
// 粒子汇聚文字自动设置
var comp = app.project.activeItem;
var textLayer = comp.layers[1]; // 假设文字层是第 2 层
var solid = comp.layers.addSolid([0,0,0], "Particular", comp.width, comp.height, 1);
solid.moveAfter(textLayer);

var fx = solid.property("Effects").addProperty("Particular");
fx.property("Emitter").property("Emitter Type").setValue(5); // Layer
fx.property("Emitter").property("Layer").setValue(textLayer);
fx.property("Emitter").property("Particles/sec").setValue(5000);
fx.property("Emitter").property("Velocity").setValue(800);
fx.property("Emitter").property("Velocity Random").setValue(50);
fx.property("Particle").property("Life").setValue(2);
fx.property("Particle").property("Particle Type").setValue(0); // Sphere
fx.property("Particle").property("Size").setValue(3);
fx.property("Particle").property("Opacity").setValue(80);

// 反向图层
solid.enabled = true;
var reversedLayer = solid.duplicate();
reversedLayer.timeRemapEnabled = true;
var timeRemap = reversedLayer.property("Time Remap");
var duration = comp.duration;
for (var t = 0; t <= duration; t += 0.1) {
    timeRemap.setValueAtTime(t, duration - t);
}
solid.enabled = false;
```

**效果截图描述**：白色"PARTICLES"文字由大量小粒子组成，背景为深色，文字外围有微弱粒子飞散痕迹，整体呈现科技感与未来感。

---

### 7.2 粒子消散文字

**效果描述**：完整文字逐渐化为粒子向各方向飘散消失。

**参数设置**：

```
Emitter:
  Emitter Type: Layer
  Layer: Text Layer
  Layer Sampling: Random - Still Frame
  Position: 文字位置
  Particles/sec: 3000
  Velocity: 200（缓慢飘散）
  Velocity Random: 80
  Direction: Outward

Physics:
  Air:
    Wind X: 50（轻风）
    Turbulence:
      Affect Position: 100
      Scale: 20
      Complexity: 3

Particle:
  Life: 3s
  Particle Type: Faded Sphere
  Size: 2
  Size over Life: 恒定 → 后 30% 缩小
  Opacity over Life: 0-70% 恒定 80% → 70-100% 淡出
  Color: 文字色

渐隐动画：
  在文字层加 Opacity 关键帧，0-1s 满值 → 1-3s 渐变到 0
  Particular 在文字消失后接管
```

**实现步骤**：

1. 新建合成，10 秒
2. 创建文字"DISPERSE"，开启 3D
3. 文字 Opacity：0-1s = 100，1-3s = 100→0
4. 黑色固态层加 Particular
5. Emitter Type = Layer，Layer = 文字层
6. Emitter Position 与文字中心对齐
7. Particles/sec = 3000，Velocity = 200，Velocity Random = 80
8. Physics Air → Wind X = 50，Turbulence Position = 100，Scale = 20
9. Particle Life = 3s，Type = Faded Sphere，Size = 2
10. Opacity over Life = 后 30% 淡出

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var textLayer = comp.layers[1];
var solid = comp.layers.addSolid([0,0,0], "Disperse", comp.width, comp.height, 1);
solid.moveAfter(textLayer);
textLayer.threeDLayer = true;

var fx = solid.property("Effects").addProperty("Particular");
fx.property("Emitter").property("Emitter Type").setValue(5);
fx.property("Emitter").property("Layer").setValue(textLayer);
fx.property("Emitter").property("Particles/sec").setValue(3000);
fx.property("Emitter").property("Velocity").setValue(200);
fx.property("Emitter").property("Velocity Random").setValue(80);
fx.property("Physics").property("Air").property("Wind X").setValue(50);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(100);
fx.property("Physics").property("Air").property("Turbulence Scale").setValue(20);
fx.property("Particle").property("Life").setValue(3);
fx.property("Particle").property("Particle Type").setValue(8); // Faded Sphere
fx.property("Particle").property("Size").setValue(2);

// 文字渐隐动画
var opacity = textLayer.property("Opacity");
opacity.setValueAtTime(0, 100);
opacity.setValueAtTime(1, 100);
opacity.setValueAtTime(3, 0);
```

**效果截图描述**：黑色背景上的"DISPERSE"白色文字，左半部分仍是完整字，右半部分已化为白色粒子向外飘散，呈现"风化"质感。

---

### 7.3 火焰效果

**效果描述**：底部升起的真实火焰，包含火芯、中焰、烟雾、火花四层。

**参数设置**（四层法）：

| 层 | 粒子类型 | 关键参数 |
|----|---------|---------|
| 火芯 | Glow Sphere | Size 2-8, Life 0.5-1.5s, Color: 白→黄→橙→红, Blend: Add |
| 中焰 | Glow Sphere | Size 8-20, Color: 橙→暗红, 更多 Turbulence |
| 烟雾 | Cloudlet | Size 100-250, Opacity 5-15%, Life 2-5s, Color: 灰/黑 |
| 火花 | Glow Sphere | P/s 5-20, Velocity 200-400, Gravity 100-200, Color: 亮橙 |

**核心参数（火芯层）**：

```
Emitter:
  Type: Point
  Position: 画面底部中央
  Particles/sec: 500
  Velocity: 100
  Direction: Directional (向上, X Rotation=90)

Physics:
  Air:
    Wind: 0
    Turbulence: Affect Position 80, Scale 8, Evolution +time*30

Particle:
  Life: 1.2s
  Type: Glow Sphere
  Size: 5
  Size over Life: 上升曲线
  Color over Life: 白(0%) → 黄(20%) → 橙(50%) → 红(80%) → 黑(100%)
  Opacity over Life: 0-10% 淡入 → 10-80% 100% → 80-100% 淡出
  Blend Mode: Add
```

**实现步骤**：

1. 新建 1920×1080 合成，黑色背景
2. 创建 4 个固态层分别命名：FireCore / FireMid / Smoke / Sparks
3. 每层添加 Particular，按上表设置
4. 全部 Emitter Position 设在底部中央
5. Direction = Directional，X Rotation = 90（向上）
6. 火芯 Blend = Add，叠加效果
7. 全部加 Glow（半径 30，阈值 50%，强度 1.5）
8. 顶层加 Curves 提亮整体

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;

function createFireLayer(name, particleType, size, velocity, particlesPerSec, life, colorOverLife) {
    var solid = comp.layers.addSolid([0,0,0], name, comp.width, comp.height, 1);
    var fx = solid.property("Effects").addProperty("Particular");
    
    fx.property("Emitter").property("Emitter Type").setValue(0); // Point
    fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height-100]);
    fx.property("Emitter").property("Particles/sec").setValue(particlesPerSec);
    fx.property("Emitter").property("Velocity").setValue(velocity);
    fx.property("Emitter").property("Direction").setValue(1); // Directional
    fx.property("Emitter").property("X Rotation").setValue(90);
    
    fx.property("Physics").property("Air").property("Turbulence Position").setValue(80);
    fx.property("Physics").property("Air").property("Turbulence Scale").setValue(8);
    
    fx.property("Particle").property("Life").setValue(life);
    fx.property("Particle").property("Particle Type").setValue(particleType);
    fx.property("Particle").property("Size").setValue(size);
    fx.property("Particle").property("Blend Mode").setValue(1); // Add
    
    // Glow
    solid.property("Effects").addProperty("Glow");
    return solid;
}

var fireCore = createFireLayer("FireCore", 1, 5, 100, 500, 1.2); // Glow Sphere
var fireMid = createFireLayer("FireMid", 1, 15, 80, 300, 1.5);
var smoke = comp.layers.addSolid([0,0,0], "Smoke", comp.width, comp.height, 1);
var smokeFx = smoke.property("Effects").addProperty("Particular");
smokeFx.property("Emitter").property("Emitter Type").setValue(0);
smokeFx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height-100]);
smokeFx.property("Emitter").property("Particles/sec").setValue(100);
smokeFx.property("Emitter").property("Velocity").setValue(150);
smokeFx.property("Emitter").property("Direction").setValue(1);
smokeFx.property("Emitter").property("X Rotation").setValue(90);
smokeFx.property("Particle").property("Life").setValue(3);
smokeFx.property("Particle").property("Particle Type").setValue(4); // Cloudlet
smokeFx.property("Particle").property("Size").setValue(200);
smokeFx.property("Particle").property("Opacity").setValue(10);
```

**效果截图描述**：底部升起的橙红色火焰，向上 1/3 处亮白火芯，中段橙色焰，顶部转为灰色烟雾，零星橙色火花四溅，背景全黑。

---

### 7.4 烟雾效果

**效果描述**：缓慢上升、扩散、淡出的烟雾。

**参数设置**：

```
Emitter:
  Type: Point（或 Box，体积更分散）
  Position: 底部
  Particles/sec: 50-200
  Velocity: 50-100（缓慢上升）

Physics:
  Air:
    Wind X: 20（轻微飘移）
    Turbulence:
      Affect Position: 100-200
      Scale: 30
      Complexity: 4
      Evolution: +time*10
    Air Resistance: 0.5

Particle:
  Life: 5s
  Type: Cloudlet
  Size: 100-250
  Size over Life: 上升曲线（0.3 → 1.0）
  Opacity: 10%
  Opacity over Life: 梯形（淡入-保持-淡出）
  Color: 灰白 → 深灰
  Blend Mode: Screen
```

**实现步骤**：

1. 新建合成，黑色背景
2. 固态层加 Particular
3. Emitter Type = Point，位置在底部中央
4. Particles/sec = 100，Velocity = 80
5. Physics Air Turbulence Position = 150，Scale = 30
6. Particle Type = Cloudlet，Size = 200，Life = 5s
7. Opacity = 10%，Opacity over Life = 梯形曲线
8. Color over Life = 灰白 → 深灰
9. Blend Mode = Screen
10. 加 Glow（半径 50）

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Smoke", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(0);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height-50]);
fx.property("Emitter").property("Particles/sec").setValue(100);
fx.property("Emitter").property("Velocity").setValue(80);

fx.property("Physics").property("Air").property("Turbulence Position").setValue(150);
fx.property("Physics").property("Air").property("Turbulence Scale").setValue(30);
fx.property("Physics").property("Air").property("Turbulence Complexity").setValue(4);

fx.property("Particle").property("Life").setValue(5);
fx.property("Particle").property("Particle Type").setValue(4); // Cloudlet
fx.property("Particle").property("Size").setValue(200);
fx.property("Particle").property("Opacity").setValue(10);
fx.property("Particle").property("Blend Mode").setValue(2); // Screen

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：底部缓缓升起的灰白色烟雾团，向上逐渐扩散、变稀，整体柔和半透明，背景深色。

---

### 7.5 雪花飘落

**效果描述**：自然飘落的雪花，带轻微摆动。

**参数设置**：

```
Emitter:
  Type: Box
  Emitter Size X: 2000
  Emitter Size Y: 0
  Emitter Size Z: 500
  Position: 画面顶部
  Particles/sec: 200-800
  Velocity: 30-80
  Direction: Directional (向下)
  X Rotation: 90

Physics:
  Gravity: 20-60
  Air:
    Wind X: 10-50
    Turbulence:
      Affect Position: 20-50
      Scale: 5-10

Particle:
  Life: 5-15s
  Type: Faded Sphere 或 Cloudlet
  Size: 3-8
  Size Random: 50%
  Opacity over Life: 淡入 → 保持 → 淡出
  Color: 白
  Blend Mode: Screen
```

**实现步骤**：

1. 新建合成，深蓝色背景（夜空）
2. 固态层加 Particular
3. Emitter Type = Box，Emitter Size X = 2000，Y = 0，Z = 500
4. Position Y = -100（屏幕顶部上方）
5. Particles/sec = 500，Velocity = 50
6. Direction = Directional，X Rotation = 90（向下）
7. Physics Gravity = 40，Wind X = 30
8. Turbulence Position = 30，Scale = 8
9. Particle Life = 10s，Type = Faded Sphere，Size = 5
10. Size Random = 50%

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Snow", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(1); // Box
fx.property("Emitter").property("Emitter Size X").setValue(2000);
fx.property("Emitter").property("Emitter Size Y").setValue(0);
fx.property("Emitter").property("Emitter Size Z").setValue(500);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, -100]);
fx.property("Emitter").property("Particles/sec").setValue(500);
fx.property("Emitter").property("Velocity").setValue(50);
fx.property("Emitter").property("Direction").setValue(1);
fx.property("Emitter").property("X Rotation").setValue(90);

fx.property("Physics").property("Gravity").setValue(40);
fx.property("Physics").property("Air").property("Wind X").setValue(30);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(30);
fx.property("Physics").property("Air").property("Turbulence Scale").setValue(8);

fx.property("Particle").property("Life").setValue(10);
fx.property("Particle").property("Particle Type").setValue(8); // Faded Sphere
fx.property("Particle").property("Size").setValue(5);
fx.property("Particle").property("Size Random").setValue(50);
fx.property("Particle").property("Blend Mode").setValue(2); // Screen
```

**效果截图描述**：深蓝夜空中飘落的白色雪花，大小不一，呈自然摆动轨迹，近景雪花大且模糊，远景细小密集。

---

### 7.6 雨滴效果

**效果描述**：高速下落的雨丝，带角度。

**参数设置**：

```
Emitter:
  Type: Box
  Emitter Size X: 2500
  Emitter Size Y: 0
  Emitter Size Z: 1000
  Position: 画面顶部上方
  Particles/sec: 500-3000
  Velocity: 600-1500
  Direction: Directional
  X Rotation: 100（略带角度）

Physics:
  Gravity: 500-1000
  Air:
    Wind X: 50-300

Particle:
  Life: 0.3-1s
  Type: Streaklet
  Streaklet Amount: 8-16
  Size: 1-3
  Color: 浅蓝白
  Opacity: 60
  Blend Mode: Screen/Add

Rendering:
  Motion Blur: On
  Shutter Angle: 360
```

**实现步骤**：

1. 新建合成，灰色阴天背景
2. 固态层加 Particular
3. Emitter Type = Box，Size X = 2500，Y = 0，Z = 1000
4. Position Y = -200
5. Particles/sec = 1500，Velocity = 1000
6. Direction = Directional，X Rotation = 100
7. Physics Gravity = 800，Wind X = 150
8. Particle Type = Streaklet，Streaklet Amount = 12
9. Life = 0.6s，Size = 2
10. Motion Blur = On，Shutter Angle = 360

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Rain", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(1);
fx.property("Emitter").property("Emitter Size X").setValue(2500);
fx.property("Emitter").property("Emitter Size Y").setValue(0);
fx.property("Emitter").property("Emitter Size Z").setValue(1000);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, -200]);
fx.property("Emitter").property("Particles/sec").setValue(1500);
fx.property("Emitter").property("Velocity").setValue(1000);
fx.property("Emitter").property("Direction").setValue(1);
fx.property("Emitter").property("X Rotation").setValue(100);

fx.property("Physics").property("Gravity").setValue(800);
fx.property("Physics").property("Air").property("Wind X").setValue(150);

fx.property("Particle").property("Life").setValue(0.6);
fx.property("Particle").property("Particle Type").setValue(5); // Streaklet
fx.property("Particle").property("Streaklet Amount").setValue(12);
fx.property("Particle").property("Size").setValue(2);
fx.property("Particle").property("Blend Mode").setValue(1); // Add

fx.property("Rendering").property("Motion Blur").setValue(1);
fx.property("Rendering").property("Shutter Angle").setValue(360);
```

**效果截图描述**：灰色阴雨背景下的密集雨丝，从右上向左下倾斜，远景雨丝细密，近景雨丝长且明显，整体带运动模糊。

---

### 7.7 星空粒子

**效果描述**：深邃宇宙背景中闪烁的星空。

**参数设置**：

```
Emitter:
  Type: Box
  Emitter Size X/Y/Z: 5000/3000/2000
  Position: 画面中心
  Particles/sec: 1000
  Velocity: 0（静止）
  Direction: Outward

Physics:
  Gravity: 0
  Air:
    Wind: 0
    Turbulence: Affect Position 5（轻微）

Particle:
  Life: 60s（永久）
  Type: Glow Sphere
  Size: 1-3
  Size Random: 80%
  Size over Life: 锯齿（闪烁）
  Opacity over Life: 锯齿（闪烁）
  Color: 白 / 浅蓝 / 浅黄（不同星类）
  Color Random: 30%
  Blend Mode: Add
```

**实现步骤**：

1. 新建合成，深紫黑色背景
2. 固态层加 Particular
3. Emitter Type = Box，Size XYZ = 5000/3000/2000
4. Particles/sec = 1000，Velocity = 0
5. Physics Gravity = 0
6. Particle Life = 60s，Type = Glow Sphere
7. Size = 2，Size Random = 80%
8. Color = 白色，Color Random = 30%
9. Blend Mode = Add
10. 加 Glow + Deep Glow 提亮

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Stars", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(1);
fx.property("Emitter").property("Emitter Size X").setValue(5000);
fx.property("Emitter").property("Emitter Size Y").setValue(3000);
fx.property("Emitter").property("Emitter Size Z").setValue(2000);
fx.property("Emitter").property("Particles/sec").setValue(1000);
fx.property("Emitter").property("Velocity").setValue(0);

fx.property("Physics").property("Gravity").setValue(0);

fx.property("Particle").property("Life").setValue(60);
fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
fx.property("Particle").property("Size").setValue(2);
fx.property("Particle").property("Size Random").setValue(80);
fx.property("Particle").property("Color Random").setValue(30);
fx.property("Particle").property("Blend Mode").setValue(1); // Add

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：深邃宇宙背景上散布无数星点，大小不一，部分明亮带光晕，整体呈深邃神秘氛围。

---

### 7.8 光线粒子

**效果描述**：跟随路径移动的光迹拖尾。

**参数设置**：

```
Emitter:
  Type: Light(s)
  Light Name: EmitterLight
  Position: 通过 Point Light 位置动画
  Particles/sec: 50-200
  Velocity: 0（光移动本身就是轨迹）

Physics:
  Gravity: 0
  Air:
    Wind: 0
    Turbulence: Affect Position 10（微摆）

Particle:
  Life: 2-5s
  Type: Streaklet
  Streaklet Amount: 8-16
  Size: 2-6
  Color: 自定义（青/品红/金）
  Blend Mode: Add
```

**Video Copilot 经典法**：

1. 创建 Point Light，命名 "Emitter"
2. 动画灯光位置（画路径）
3. 新建固态层加 Particular，Emitter Type = Light(s)
4. Light Name = Emitter
5. Velocity = 0
6. Particle Type = Streaklet，Streaklet Amount = 12
7. P/s = 100，Life = 3s，Size = 4
8. Blend Mode = Add
9. 加 Glow + Curves
10. 对灯光位置加表达式 `wiggle(0.5, 100)` 制造随机摆动

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;

// 创建点光源
var light = comp.layers.addLight("Emitter", [comp.width/2, comp.height/2]);
light.property("Position").setValueAtTime(0, [comp.width/2, comp.height/2, 0]);
light.property("Position").setValueAtTime(2, [comp.width*0.2, comp.height*0.3, 200]);
light.property("Position").setValueAtTime(4, [comp.width*0.8, comp.height*0.7, -200]);
light.property("Position").setValueAtTime(6, [comp.width/2, comp.height/2, 0]);

// 创建粒子层
var solid = comp.layers.addSolid([0,0,0], "LightStreak", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(4); // Light(s)
fx.property("Emitter").property("Light Name").setValue("Emitter");
fx.property("Emitter").property("Particles/sec").setValue(100);
fx.property("Emitter").property("Velocity").setValue(0);

fx.property("Physics").property("Air").property("Turbulence Position").setValue(10);

fx.property("Particle").property("Life").setValue(3);
fx.property("Particle").property("Particle Type").setValue(5); // Streaklet
fx.property("Particle").property("Streaklet Amount").setValue(12);
fx.property("Particle").property("Size").setValue(4);
fx.property("Particle").property("Color").setValue([0, 1, 1]); // 青
fx.property("Particle").property("Blend Mode").setValue(1); // Add

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：黑色空间中一条青色光迹沿曲线路径流动，光迹带柔和拖尾，整体发光柔和，路径有随机摆动感。

---

### 7.9 能量爆发

**效果描述**：从中心向外的能量爆炸，带光晕和余烬。

**参数设置**：

```
Emitter:
  Type: Point
  Position: 画面中心
  Particles/sec: 关键帧（0 → 10000 → 0，0.1s 内）
  Velocity: 1500
  Velocity Random: 60
  Direction: Outward

Physics:
  Gravity: 100（轻微下落）
  Air:
    Turbulence: Affect Position 50

Particle:
  Life: 1.5s
  Type: Glow Sphere
  Size: 4
  Size over Life: 1.0 → 0.2
  Color over Life: 白 → 黄 → 橙 → 红 → 黑
  Opacity over Life: 0-5% 淡入 → 5-80% 100% → 80-100% 淡出
  Blend Mode: Add

Aux System:
  Emit: At Death
  Particles/sec: 20
  Type: Glow Sphere
  Life: 0.8s
  Inherit Velocity: 50
```

**实现步骤**：

1. 新建合成，黑色背景
2. 固态层加 Particular
3. Emitter Type = Point，Position = 中心
4. Particles/sec 关键帧：0s = 0，0.05s = 10000，0.1s = 0
5. Velocity = 1500，Velocity Random = 60
6. Physics Gravity = 100，Turbulence Position = 50
7. Particle Life = 1.5s，Type = Glow Sphere，Size = 4
8. Color over Life = 白→黄→橙→红→黑
9. Aux System Emit = At Death，Rate = 20，Life = 0.8s
10. Blend Mode = Add + Glow

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Burst", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(0);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height/2]);

var ps = fx.property("Emitter").property("Particles/sec");
ps.setValueAtTime(0, 0);
ps.setValueAtTime(0.05, 10000);
ps.setValueAtTime(0.1, 0);

fx.property("Emitter").property("Velocity").setValue(1500);
fx.property("Emitter").property("Velocity Random").setValue(60);

fx.property("Physics").property("Gravity").setValue(100);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(50);

fx.property("Particle").property("Life").setValue(1.5);
fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
fx.property("Particle").property("Size").setValue(4);
fx.property("Particle").property("Blend Mode").setValue(1); // Add

// Aux System
fx.property("Aux System").property("Emit").setValue(2); // At Death
fx.property("AuxSystem").property("Particles/sec").setValue(20);
fx.property("AuxSystem").property("Life").setValue(0.8);

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：画面中心一个明亮白核向四周喷射橙红光粒，呈球形辐射，外缘带余烬和暗淡拖尾，整体极亮。

---

### 7.10 爆炸效果

**效果描述**：含火球、碎片、烟雾、火花的完整爆炸。

**参数设置**（四层）：

| 层 | 类型 | 关键参数 |
|----|------|---------|
| 火球 | Glow Sphere | P/s 突发 3000，Velocity 800, Life 1s, Color 白→橙→黑 |
| 烟雾 | Cloudlet | P/s 500, Velocity 300, Life 4s, Opacity 30% |
| 碎片 | Sphere | P/s 200, Velocity 1200, Life 3s, Gravity 400, Bounce 物理 |
| 火花 | Glow Sphere | P/s 500, Velocity 2000, Life 1.5s, Gravity 300 |

**实现步骤**：

1. 新建合成，黑色背景
2. 创建 4 个固态层：Fireball / Smoke / Debris / Sparks
3. 每层 Particular，Emitter Type = Point，Position = 中心
4. 火球层：P/s 关键帧 0s=0, 0.03s=3000, 0.06s=0，Velocity 800，Life 1s
5. 烟雾层：P/s=500, Velocity=300, Cloudlet, Size=300, Life=4s
6. 碎片层：P/s=200, Velocity=1200, Sphere, Size=4, Life=3s, Physics=Bounce
7. 火花层：P/s=500, Velocity=2000, Life=1.5s, Gravity=300
8. 所有层 Blend = Add（除烟雾 = Screen）
9. 全部加 Glow

**JSX 脚本**（简化版，仅火球层）：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Explosion_Fireball", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(0);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height/2]);

var ps = fx.property("Emitter").property("Particles/sec");
ps.setValueAtTime(0, 0);
ps.setValueAtTime(0.03, 3000);
ps.setValueAtTime(0.06, 0);

fx.property("Emitter").property("Velocity").setValue(800);
fx.property("Emitter").property("Velocity Random").setValue(80);

fx.property("Physics").property("Physics Model").setValue(1); // Bounce
fx.property("Physics").property("Bounce").setValue(20);

fx.property("Particle").property("Life").setValue(1);
fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
fx.property("Particle").property("Size").setValue(8);
fx.property("Particle").property("Blend Mode").setValue(1); // Add

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：黑色画面中央一团亮黄橙色火球，四周飞散小型碎片与火花，火球周围有灰色烟雾团，整体呈典型电影爆炸瞬间。

---

### 7.11 魔法粒子

**效果描述**：从法杖发出的多彩魔法光粒，带闪烁和拖尾。

**参数设置**：

```
Emitter:
  Type: Light
  Light Name: MagicLight
  Particles/sec: 200
  Velocity: 200-500
  Velocity Random: 80

Physics:
  Gravity: 100-300
  Air:
    Turbulence: Affect Position 50

Particle:
  Life: 0.5-2s
  Life Random: 100%
  Type: Glow Sphere 或 Star
  Size: 2-6
  Size Random: 100%
  Size over Life: 满 → 快速缩小（燃尽）
  Color: Random from Gradient（白/金/青/品红）
  Blend Mode: Add

Aux System:
  Emit: Continuously
  Rate: 30
  Life: 0.5s
  Inherit Velocity: 80
```

**实现步骤**：

1. 新建合成，黑色背景
2. 创建 Point Light "MagicLight"，动画其位置
3. 固态层加 Particular
4. Emitter Type = Light(s)，Light Name = MagicLight
5. Particles/sec = 200，Velocity = 300，Velocity Random = 80
6. Physics Gravity = 200，Turbulence Position = 50
7. Particle Life = 1s，Life Random = 100%
8. Type = Glow Sphere，Size = 4，Size Random = 100%
9. Color over Life = 多色渐变（白→金→青→品红）
10. Aux System = Continuously, Rate = 30
11. Blend Mode = Add + Glow + Curves 提亮

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;

var light = comp.layers.addLight("MagicLight", [comp.width/2, comp.height/2]);
light.property("Position").expression = "wiggle(1, 200) + [960, 540, 0]";

var solid = comp.layers.addSolid([0,0,0], "Magic", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(4); // Light
fx.property("Emitter").property("Light Name").setValue("MagicLight");
fx.property("Emitter").property("Particles/sec").setValue(200);
fx.property("Emitter").property("Velocity").setValue(300);
fx.property("Emitter").property("Velocity Random").setValue(80);

fx.property("Physics").property("Gravity").setValue(200);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(50);

fx.property("Particle").property("Life").setValue(1);
fx.property("Particle").property("Life Random").setValue(100);
fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
fx.property("Particle").property("Size").setValue(4);
fx.property("Particle").property("Size Random").setValue(100);
fx.property("Particle").property("Blend Mode").setValue(1); // Add

fx.property("AuxSystem").property("Emit").setValue(3); // Continuously
fx.property("AuxSystem").property("Particles/sec").setValue(30);
fx.property("AuxSystem").property("Life").setValue(0.5);

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：黑色背景上从中心点发出的多彩魔法光粒，带白、金、青、品红多色，部分粒子带短拖尾，整体梦幻魔幻。

---

### 7.12 落叶飘落

**效果描述**：使用 Sprite 粒子模拟自然飘落的树叶。

**参数设置**：

```
Emitter:
  Type: Box
  Emitter Size X: 2000
  Emitter Size Y: 0
  Position: 画面顶部
  Particles/sec: 100
  Velocity: 30
  Direction: Directional (向下)
  X Rotation: 90

Physics:
  Gravity: 30
  Air:
    Wind X: 50
    Turbulence: Affect Position 100, Scale 15
    Spin Amplitude: 200

Particle:
  Life: 15s
  Type: Sprite
  Texture: 落叶图片（带 Alpha）
  Size: 30-60
  Size Random: 60%
  Color: 不染色（Use Layer）
  Blend Mode: Normal
```

**实现步骤**：

1. 准备落叶 PNG（带 Alpha）
2. 新建合成，秋色背景
3. 固态层加 Particular
4. Emitter Type = Box，Size X = 2000，Y = 0
5. Particles/sec = 100，Velocity = 30
6. Direction = Directional，X Rotation = 90
7. Physics Gravity = 30，Wind X = 50
8. Turbulence Position = 100，Spin Amplitude = 200
9. Particle Type = Sprite，Texture = 落叶图片
10. Size = 50，Size Random = 60%

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var leafLayer = comp.layers[1]; // 落叶图片层

var solid = comp.layers.addSolid([0,0,0], "Leaves", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(1); // Box
fx.property("Emitter").property("Emitter Size X").setValue(2000);
fx.property("Emitter").property("Emitter Size Y").setValue(0);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, -100]);
fx.property("Emitter").property("Particles/sec").setValue(100);
fx.property("Emitter").property("Velocity").setValue(30);
fx.property("Emitter").property("Direction").setValue(1);
fx.property("Emitter").property("X Rotation").setValue(90);

fx.property("Physics").property("Gravity").setValue(30);
fx.property("Physics").property("Air").property("Wind X").setValue(50);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(100);
fx.property("Physics").property("Air").property("Spin Amplitude").setValue(200);

fx.property("Particle").property("Life").setValue(15);
fx.property("Particle").property("Particle Type").setValue(6); // Sprite
fx.property("Particle").property("Texture").setValue(leafLayer);
fx.property("Particle").property("Size").setValue(50);
fx.property("Particle").property("Size Random").setValue(60);
```

**效果截图描述**：秋色背景中飘落的红色、橙色、黄色树叶，旋转下落，大小不一，自然分布。

---

### 7.13 气泡上升

**效果描述**：水中向上飘升的气泡。

**参数设置**：

```
Emitter:
  Type: Box
  Emitter Size X: 500
  Emitter Size Y: 0
  Position: 画面底部
  Particles/sec: 30
  Velocity: 100（向上）

Physics:
  Gravity: -50（负值=向上）
  Air:
    Turbulence: Affect Position 30

Particle:
  Life: 5s
  Type: Sphere
  Size: 5-20
  Size Random: 80%
  Opacity: 50
  Color: 浅蓝白
  Blend Mode: Screen
  Sphere Feather: 80（高羽化=透明气泡感）
```

**实现步骤**：

1. 新建合成，蓝色水下背景
2. 固态层加 Particular
3. Emitter Type = Box，Size X = 500，Y = 0
4. Position Y = 屏幕底部
5. Particles/sec = 30，Velocity = 100
6. Direction = Directional，X Rotation = -90（向上）
7. Physics Gravity = -50（负值）
8. Turbulence Position = 30
9. Particle Type = Sphere，Size = 15，Size Random = 80%
10. Sphere Feather = 80，Opacity = 50
11. Blend Mode = Screen

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Bubbles", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(1);
fx.property("Emitter").property("Emitter Size X").setValue(500);
fx.property("Emitter").property("Emitter Size Y").setValue(0);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height+50]);
fx.property("Emitter").property("Particles/sec").setValue(30);
fx.property("Emitter").property("Velocity").setValue(100);
fx.property("Emitter").property("Direction").setValue(1);
fx.property("Emitter").property("X Rotation").setValue(-90);

fx.property("Physics").property("Gravity").setValue(-50);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(30);

fx.property("Particle").property("Life").setValue(5);
fx.property("Particle").property("Particle Type").setValue(0); // Sphere
fx.property("Particle").property("Size").setValue(15);
fx.property("Particle").property("Size Random").setValue(80);
fx.property("Particle").property("Sphere Feather").setValue(80);
fx.property("Particle").property("Opacity").setValue(50);
fx.property("Particle").property("Blend Mode").setValue(2); // Screen
```

**效果截图描述**：蓝色水下背景中向上飘升的透明气泡，大小不一，呈半透明柔和形态。

---

### 7.14 沙尘暴

**效果描述**：横向吹过的沙尘暴。

**参数设置**：

```
Emitter:
  Type: Box
  Emitter Size X: 0
  Emitter Size Y: 1500
  Emitter Size Z: 500
  Position: 画面左侧外
  Particles/sec: 2000
  Velocity: 800（向右）
  Direction: Directional
  Y Rotation: 90

Physics:
  Gravity: 0
  Air:
    Wind X: 300
    Turbulence: Affect Position 200, Scale 25

Particle:
  Life: 4s
  Type: Cloudlet
  Size: 150
  Size Random: 70%
  Opacity: 15
  Color: 沙黄
  Blend Mode: Screen
```

**实现步骤**：

1. 新建合成，沙漠背景
2. 固态层加 Particular
3. Emitter Type = Box，Size Y = 1500，Z = 500
4. Position X = -200（画面外左）
5. Particles/sec = 2000，Velocity = 800
6. Direction = Directional，Y Rotation = 90（向右）
7. Physics Gravity = 0，Wind X = 300
8. Turbulence Position = 200，Scale = 25
9. Particle Type = Cloudlet，Size = 150，Size Random = 70%
10. Opacity = 15，Color = 沙黄

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Sandstorm", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(1);
fx.property("Emitter").property("Emitter Size X").setValue(0);
fx.property("Emitter").property("Emitter Size Y").setValue(1500);
fx.property("Emitter").property("Emitter Size Z").setValue(500);
fx.property("Emitter").property("Position XY").setValue([-200, comp.height/2]);
fx.property("Emitter").property("Particles/sec").setValue(2000);
fx.property("Emitter").property("Velocity").setValue(800);
fx.property("Emitter").property("Direction").setValue(1);
fx.property("Emitter").property("Y Rotation").setValue(90);

fx.property("Physics").property("Gravity").setValue(0);
fx.property("Physics").property("Air").property("Wind X").setValue(300);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(200);
fx.property("Physics").property("Air").property("Turbulence Scale").setValue(25);

fx.property("Particle").property("Life").setValue(4);
fx.property("Particle").property("Particle Type").setValue(4); // Cloudlet
fx.property("Particle").property("Size").setValue(150);
fx.property("Particle").property("Size Random").setValue(70);
fx.property("Particle").property("Opacity").setValue(15);
fx.property("Particle").property("Color").setValue([0.76, 0.6, 0.42]); // 沙黄
fx.property("Particle").property("Blend Mode").setValue(2); // Screen
```

**效果截图描述**：沙漠背景中横向飞驰的沙黄色尘雾，遮挡远景，整体沙土色，密度高且模糊。

---

### 7.15 光斑散景

**效果描述**：柔和的散景光斑背景。

**参数设置**：

```
Emitter:
  Type: Box
  Emitter Size X/Y/Z: 3000/2000/1000
  Position: 中心
  Particles/sec: 100
  Velocity: 0

Physics:
  Gravity: 0
  Air:
    Wind X: 20
    Turbulence: Affect Position 10

Particle:
  Life: 30s
  Type: Faded Sphere
  Size: 50-150
  Size Random: 80%
  Opacity: 60
  Color: 暖黄 / 粉 / 蓝
  Color Random: 50%
  Blend Mode: Add

Camera:
  Enable Depth of Field
  Aperture: 50
  Focal Distance: 中景
```

**实现步骤**：

1. 新建合成，深色背景
2. 创建摄像机，开启 DOF，Aperture = 50
3. 固态层加 Particular
4. Emitter Type = Box，Size XYZ = 3000/2000/1000
5. Particles/sec = 100，Velocity = 0
6. Physics Gravity = 0，Wind X = 20
7. Particle Life = 30s，Type = Faded Sphere
8. Size = 100，Size Random = 80%
9. Opacity = 60，Color Random = 50%
10. Blend Mode = Add

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;

// 创建摄像机
var cam = comp.layers.addCamera("MainCam", [0, 0]);
cam.property("ADBE Camera Options Group").property("ADBE Camera Depth of Field").setValue(1);
cam.property("ADBE Camera Options Group").property("ADBE Camera Aperture").setValue(50);

var solid = comp.layers.addSolid([0,0,0], "Bokeh", comp.width, comp.height, 1);
solid.threeDLayer = true;
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(1);
fx.property("Emitter").property("Emitter Size X").setValue(3000);
fx.property("Emitter").property("Emitter Size Y").setValue(2000);
fx.property("Emitter").property("Emitter Size Z").setValue(1000);
fx.property("Emitter").property("Particles/sec").setValue(100);
fx.property("Emitter").property("Velocity").setValue(0);

fx.property("Physics").property("Gravity").setValue(0);
fx.property("Physics").property("Air").property("Wind X").setValue(20);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(10);

fx.property("Particle").property("Life").setValue(30);
fx.property("Particle").property("Particle Type").setValue(8); // Faded Sphere
fx.property("Particle").property("Size").setValue(100);
fx.property("Particle").property("Size Random").setValue(80);
fx.property("Particle").property("Opacity").setValue(60);
fx.property("Particle").property("Color Random").setValue(50);
fx.property("Particle").property("Blend Mode").setValue(1); // Add
```

**效果截图描述**：深色背景上散布的暖色调圆形光斑，部分清晰、部分因景深模糊，整体柔和梦幻。

---

### 7.16 粒子路径

**效果描述**：粒子沿预定路径流动。

**参数设置**：

```
方法：使用 Mask Path 控制发射器位置

Emitter:
  Type: Light(s)
  Light Name: PathLight
  Particles/sec: 100
  Velocity: 0

Physics:
  Gravity: 0
  Air:
    Wind: 0

Particle:
  Life: 3s
  Type: Streaklet
  Streaklet Amount: 10
  Size: 3
  Color: 青
  Blend Mode: Add
```

**实现步骤**：

1. 新建合成，黑色背景
2. 创建 Point Light "PathLight"
3. 给灯光 Position 加表达式，绑定到 Mask Path
4. 固态层加 Particular
5. Emitter Type = Light(s)，Light Name = PathLight
6. Particles/sec = 100，Velocity = 0
7. Particle Life = 3s，Type = Streaklet
8. Blend Mode = Add + Glow

**位置表达式（沿 Mask 路径）**：

```javascript
// 灯光 Position 表达式
var maskLayer = thisComp.layer("PathMask");
var maskPath = maskLayer.mask("Mask 1").property("Mask Path");
var pathPoint = maskPath.pointOnPath(time / thisComp.duration);
[pathPoint[0], pathPoint[1], 0];
```

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var light = comp.layers.addLight("PathLight", [0, 0]);

// 设置 Position 表达式
light.property("Position").expression = [
    'var maskLayer = thisComp.layer("PathMask");',
    'var maskPath = maskLayer.mask("Mask 1").property("Mask Path");',
    'var pathPoint = maskPath.pointOnPath(time / thisComp.duration);',
    '[pathPoint[0], pathPoint[1], 0];'
].join("\n");

var solid = comp.layers.addSolid([0,0,0], "PathParticles", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(4); // Light
fx.property("Emitter").property("Light Name").setValue("PathLight");
fx.property("Emitter").property("Particles/sec").setValue(100);
fx.property("Emitter").property("Velocity").setValue(0);

fx.property("Particle").property("Life").setValue(3);
fx.property("Particle").property("Particle Type").setValue(5); // Streaklet
fx.property("Particle").property("Streaklet Amount").setValue(10);
fx.property("Particle").property("Size").setValue(3);
fx.property("Particle").property("Color").setValue([0, 1, 1]); // 青
fx.property("Particle").property("Blend Mode").setValue(1); // Add

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：黑色背景上一条青色光迹沿曲线路径流动，光迹带柔和拖尾，整体科技感强。

---

### 7.17 拖尾效果

**效果描述**：移动物体后的粒子拖尾。

**参数设置**：

```
方法 1：Aux System 持续发射

Emitter:
  Type: Light
  Light Name: TrailLight
  Particles/sec: 100
  Velocity: 0

Particle:
  Life: 2s
  Type: Glow Sphere
  Size: 4
  Color: 主色
  Blend Mode: Add
  Opacity over Life: 满淡入 → 线性淡出

Aux System:
  Emit: Continuously
  Rate: 50
  Life: 1s
  Type: Glow Sphere
  Size: 2
  Color: 主色
  Inherit Velocity: 100
  Blend Mode: Add
```

**实现步骤**：

1. 创建 Point Light "TrailLight"，动画位置
2. 固态层加 Particular
3. Emitter Type = Light(s)，Velocity = 0
4. Particle Life = 2s，Type = Glow Sphere
5. Opacity over Life = 后期淡出
6. Aux System = Continuously，Rate = 50
7. Aux Life = 1s，Inherit Velocity = 100
8. Blend Mode = Add + Glow

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var light = comp.layers.addLight("TrailLight", [comp.width/2, comp.height/2]);

// 圆形运动
light.property("Position").expression = [
    'var r = 400;',
    'var cx = thisComp.width/2;',
    'var cy = thisComp.height/2;',
    'var t = time * 2;',
    '[cx + Math.cos(t) * r, cy + Math.sin(t) * r, 0];'
].join("\n");

var solid = comp.layers.addSolid([0,0,0], "Trail", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(4);
fx.property("Emitter").property("Light Name").setValue("TrailLight");
fx.property("Emitter").property("Particles/sec").setValue(100);
fx.property("Emitter").property("Velocity").setValue(0);

fx.property("Particle").property("Life").setValue(2);
fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
fx.property("Particle").property("Size").setValue(4);
fx.property("Particle").property("Blend Mode").setValue(1); // Add

fx.property("AuxSystem").property("Emit").setValue(3); // Continuously
fx.property("AuxSystem").property("Particles/sec").setValue(50);
fx.property("AuxSystem").property("Life").setValue(1);
fx.property("AuxSystem").property("Size").setValue(2);
fx.property("AuxSystem").property("Inherit Velocity").setValue(100);

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：黑色背景上一个圆形轨迹的光粒拖尾，颜色明亮带柔和过渡，整体旋转流动感强。

---

### 7.18 闪电粒子

**效果描述**：模拟闪电放电的粒子效果。

**参数设置**：

```
Emitter:
  Type: Point
  Position: 起点
  Particles/sec: 关键帧（突发 5000 → 0）
  Velocity: 1000
  Velocity Random: 100
  Direction: Directional（向终点）

Physics:
  Gravity: 0
  Air:
    Turbulence: Affect Position 300, Scale 3（高强度细密）

Particle:
  Life: 0.3s
  Type: Streaklet
  Streaklet Amount: 20
  Size: 2
  Color: 白蓝
  Opacity: 100
  Blend Mode: Add

Aux System:
  Emit: Continuously
  Rate: 30
  Life: 0.2s
  Type: Glow Sphere
  Size: 1
```

**实现步骤**：

1. 新建合成，黑色背景
2. 固态层加 Particular
3. Emitter Type = Point，Position = 起点
4. Particles/sec 关键帧：0s=0, 0.02s=5000, 0.05s=0
5. Velocity = 1000，Velocity Random = 100
6. Physics Gravity = 0
7. Turbulence Position = 300，Scale = 3（高强度细密）
8. Particle Life = 0.3s，Type = Streaklet
9. Color = 白蓝（[0.8, 0.9, 1]）
10. Aux System = Continuously，Rate = 30
11. Blend Mode = Add + Glow

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Lightning", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(0);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height/2]);

var ps = fx.property("Emitter").property("Particles/sec");
ps.setValueAtTime(0, 0);
ps.setValueAtTime(0.02, 5000);
ps.setValueAtTime(0.05, 0);

fx.property("Emitter").property("Velocity").setValue(1000);
fx.property("Emitter").property("Velocity Random").setValue(100);

fx.property("Physics").property("Gravity").setValue(0);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(300);
fx.property("Physics").property("Air").property("Turbulence Scale").setValue(3);

fx.property("Particle").property("Life").setValue(0.3);
fx.property("Particle").property("Particle Type").setValue(5); // Streaklet
fx.property("Particle").property("Streaklet Amount").setValue(20);
fx.property("Particle").property("Size").setValue(2);
fx.property("Particle").property("Color").setValue([0.8, 0.9, 1]); // 白蓝
fx.property("Particle").property("Blend Mode").setValue(1); // Add

fx.property("AuxSystem").property("Emit").setValue(3);
fx.property("AuxSystem").property("Particles/sec").setValue(30);
fx.property("AuxSystem").property("Life").setValue(0.2);

solid.property("Effects").addProperty("Glow");
```

**效果截图描述**：黑色背景上一道分叉的蓝白闪电，从中心向外辐射，带强烈光晕，整体尖锐闪亮。

---

### 7.19 水墨扩散

**效果描述**：水墨在纸上扩散的效果。

**参数设置**：

```
Emitter:
  Type: Point
  Position: 中心
  Particles/sec: 50
  Velocity: 30
  Velocity Random: 50

Physics:
  Physics Model: Fluid
  Fluid:
    Velocity: 20
    Viscosity: 50
    Diffusion: 80

Particle:
  Life: 5s
  Type: Cloudlet
  Size: 80
  Size over Life: 上升曲线
  Opacity: 30
  Opacity over Life: 淡入 → 保持 → 淡出
  Color: 黑
  Blend Mode: Multiply
```

**实现步骤**：

1. 新建合成，米色背景（宣纸色）
2. 固态层加 Particular
3. Emitter Type = Point，Position = 中心
4. Particles/sec = 50，Velocity = 30
5. Physics Model = Fluid
6. Fluid Velocity = 20，Viscosity = 50，Diffusion = 80
7. Particle Life = 5s，Type = Cloudlet
8. Size = 80，Size over Life = 上升
9. Opacity = 30，Color = 黑
10. Blend Mode = Multiply（让水墨与背景融合）

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Ink", comp.width, comp.height, 1);
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(0);
fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height/2]);
fx.property("Emitter").property("Particles/sec").setValue(50);
fx.property("Emitter").property("Velocity").setValue(30);
fx.property("Emitter").property("Velocity Random").setValue(50);

fx.property("Physics").property("Physics Model").setValue(2); // Fluid
fx.property("Physics").property("Fluid").property("Velocity").setValue(20);
fx.property("Physics").property("Fluid").property("Viscosity").setValue(50);
fx.property("Physics").property("Fluid").property("Diffusion").setValue(80);

fx.property("Particle").property("Life").setValue(5);
fx.property("Particle").property("Particle Type").setValue(4); // Cloudlet
fx.property("Particle").property("Size").setValue(80);
fx.property("Particle").property("Opacity").setValue(30);
fx.property("Particle").property("Color").setValue([0, 0, 0]); // 黑
fx.property("Particle").property("Blend Mode").setValue(3); // Multiply
```

**效果截图描述**：米色宣纸背景上一团黑色水墨从中心向外扩散，边缘呈不规则扩散形态，整体东方水墨韵味。

---

### 7.20 赛博朋克粒子

**效果描述**：赛博朋克风格的霓虹粒子。

**参数设置**：

```
Emitter:
  Type: Box
  Emitter Size X/Y/Z: 1920/1080/500
  Position: 中心
  Particles/sec: 500
  Velocity: 50
  Direction: Outward

Physics:
  Gravity: 0
  Air:
    Wind X: 30
    Turbulence: Affect Position 100, Scale 8

Particle:
  Life: 8s
  Type: Glow Sphere
  Size: 3
  Size Random: 60%
  Color: 随机青/品红（赛博朋克双色）
  Color Random: 100%
  Blend Mode: Add
  Opacity over Life: 锯齿（闪烁）

Camera:
  Enable Depth of Field
  Aperture: 30

后期：
  Glow (Radius 50, Intensity 2)
  Curves (RGB 通道分色提亮)
  Chromatic Aberration（色差）
```

**实现步骤**：

1. 新建合成，深紫色背景
2. 创建摄像机，开启 DOF
3. 固态层加 Particular
4. Emitter Type = Box，Size XYZ = 1920/1080/500
5. Particles/sec = 500，Velocity = 50
6. Physics Gravity = 0，Wind X = 30
7. Turbulence Position = 100，Scale = 8
8. Particle Life = 8s，Type = Glow Sphere
9. Size = 3，Size Random = 60%
10. Color = 青，Color Random = 100%（部分粒子变品红）
11. Opacity over Life = 锯齿（闪烁）
12. Blend Mode = Add
13. 加 Glow + Curves + Chromatic Aberration

**JSX 脚本**：

```javascript
var comp = app.project.activeItem;
var cam = comp.layers.addCamera("MainCam", [0, 0]);
cam.property("ADBE Camera Options Group").property("ADBE Camera Depth of Field").setValue(1);

var solid = comp.layers.addSolid([0,0,0], "Cyberpunk", comp.width, comp.height, 1);
solid.threeDLayer = true;
var fx = solid.property("Effects").addProperty("Particular");

fx.property("Emitter").property("Emitter Type").setValue(1);
fx.property("Emitter").property("Emitter Size X").setValue(1920);
fx.property("Emitter").property("Emitter Size Y").setValue(1080);
fx.property("Emitter").property("Emitter Size Z").setValue(500);
fx.property("Emitter").property("Particles/sec").setValue(500);
fx.property("Emitter").property("Velocity").setValue(50);

fx.property("Physics").property("Gravity").setValue(0);
fx.property("Physics").property("Air").property("Wind X").setValue(30);
fx.property("Physics").property("Air").property("Turbulence Position").setValue(100);
fx.property("Physics").property("Air").property("Turbulence Scale").setValue(8);

fx.property("Particle").property("Life").setValue(8);
fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
fx.property("Particle").property("Size").setValue(3);
fx.property("Particle").property("Size Random").setValue(60);
fx.property("Particle").property("Color").setValue([0, 1, 1]); // 青
fx.property("Particle").property("Color Random").setValue(100);
fx.property("Particle").property("Blend Mode").setValue(1); // Add

solid.property("Effects").addProperty("Glow");
solid.property("Effects").addProperty("Curves");
```

**效果截图描述**：深紫黑背景中散布的青色与品红色霓虹光粒，大小不一，部分闪烁，整体赛博朋克霓虹氛围浓烈。

---

## 八、与 AE 其他效果组合

Particular 与 AE 原生效果的组合能极大拓展其表现力。

### 8.1 Particular + Glow

**组合方案**：在 Particular 图层上加 Glow 效果。

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| Glow Threshold | 50% | 高于阈值的区域发光 |
| Glow Radius | 30-80 | 光晕半径 |
| Glow Intensity | 1.5-3 | 强度 |
| Glow Colors | Original | 保持原色 |

**变种**：使用 Deep Glow（第三方）效果更柔和真实。

### 8.2 Particular + Curves

**组合方案**：用 Curves 精修色调。

| 通道 | 调整 | 效果 |
|------|------|------|
| RGB | S 曲线 | 提高对比 |
| Red | 上升 | 偏暖 |
| Blue | 上升 | 偏冷 |
| Alpha | 上升 | 提亮透明区 |

### 8.3 Particular + Depth of Field

**组合方案**：开启摄像机 DOF，让远近粒子自然模糊。

```
1. 创建摄像机
2. 摄像机属性 → Enable Depth of Field
3. Aperture: 30-100
4. Focal Distance: 对准中景粒子
5. Particular 自动根据 Z 位置应用模糊
```

### 8.4 Particular + Camera

**组合方案**：让粒子参与 3D 摄像机运动。

```
1. 摄像机动画（推拉摇移）
2. 粒子在 3D 空间分布（Emitter Size Z > 0）
3. 摄像机穿过粒子层时产生强烈景深变化
```

### 8.5 Particular + Light

**组合方案**：AE 灯光影响粒子颜色和明度。

| Particle 设置 | 行为 |
|--------------|------|
| Shader → Light → Shadow | 接收灯光阴影 |
| Shader → Light → Reflection | 反射高光 |
| Light Affects Particle | 灯光颜色染色 |

### 8.6 10 种组合方案速查

| # | 组合 | 效果 |
|---|------|------|
| 1 | Particular + Glow + Curves | 标准提亮流程 |
| 2 | Particular + Depth of Field | 真实景深 |
| 3 | Particular + Camera (运动) | 3D 穿越粒子 |
| 4 | Particular + Light | 灯光影响粒子 |
| 5 | Particular + Bloom | 电影级光晕 |
| 6 | Particular + Chromatic Aberration | 赛博朋克色差 |
| 7 | Particular + Noise | 胶片颗粒 |
| 8 | Particular + Colorama | 创意调色 |
| 9 | Particular + Displacement Map | 扭曲粒子 |
| 10 | Particular + Time Remap | 时间冻结/慢动作 |

### 8.7 组合 JSX 脚本

```javascript
// 标准提亮流程：Particular + Glow + Curves
var comp = app.project.activeItem;
var solid = comp.layers.addSolid([0,0,0], "Particles", comp.width, comp.height, 1);

var particular = solid.property("Effects").addProperty("Particular");
// ... 设置 Particular 参数 ...

var glow = solid.property("Effects").addProperty("Glow");
glow.property("Glow Threshold").setValue(0.5);
glow.property("Glow Radius").setValue(50);
glow.property("Glow Intensity").setValue(2);

var curves = solid.property("Effects").addProperty("Curves");
// S 曲线
curves.property("Master").setValueAtKey(1, [0, 0.1]);
curves.property("Master").setValueAtKey(2, [0.5, 0.5]);
curves.property("Master").setValueAtKey(3, [1, 0.9]);
```

---

## 九、Particular 表达式控制

通过表达式可让粒子参数动态响应音乐、时间、其他图层等。

### 9.1 粒子位置表达式

```javascript
// 发射器位置绕圆运动
var r = 400;
var cx = thisComp.width/2;
var cy = thisComp.height/2;
var t = time * 1.5;
[cx + Math.cos(t) * r, cy + Math.sin(t) * r];
```

### 9.2 粒子数量表达式

```javascript
// 节拍发射：每 0.5s 爆发一次
var beat = time % 0.5;
beat < 0.05 ? 2000 : 50;
```

### 9.3 音频驱动粒子

```javascript
// Particles/sec 由音频振幅驱动
var audioLayer = thisComp.layer("Audio Amplitude");
var both = audioLayer.effect("Both Channels")("Slider");
both * 1000;
```

**完整音频驱动流程**：

1. 导入音乐到合成
2. 右键音频 → Keyframe Assistant → Convert Audio to Keyframes
3. 生成 "Audio Amplitude" 文本层
4. 在 Particular 的 `Particles/sec` 上加表达式：
   ```javascript
   var audioLayer = thisComp.layer("Audio Amplitude");
   audioLayer.effect("Both Channels")("Slider") * 500;
   ```

### 9.4 粒子颜色表达式

```javascript
// 颜色随时间变化（彩虹）
var hue = (time * 0.1) % 1;
hslToRgb([hue, 1, 0.5, 1]);
```

### 9.5 粒子大小表达式

```javascript
// 大小由音频驱动
var audioLayer = thisComp.layer("Audio Amplitude");
var both = audioLayer.effect("Both Channels")("Slider");
2 + both * 5;
```

### 9.6 速度表达式

```javascript
// 速度根据时间递增
100 + time * 50;
```

### 9.7 重力表达式

```javascript
// 重力呈正弦波动（漂浮感）
Math.sin(time * 2) * 100;
```

### 9.8 风表达式（阵风）

```javascript
// 阵风：随机大风
var gust = Math.sin(time * 0.5) * 100;
gust + wiggle(0.3, 50);
```

### 9.9 湍流演化表达式

```javascript
// 湍流随时间演化
time * 30;
```

### 9.10 10 个实用表达式速查

| # | 用途 | 表达式 |
|---|------|--------|
| 1 | 圆周运动 | `[cx + Math.cos(t)*r, cy + Math.sin(t)*r]` |
| 2 | 节拍发射 | `beat<0.05?2000:50` |
| 3 | 音频驱动 P/s | `audio*500` |
| 4 | 彩虹色 | `hslToRgb([time*0.1%1,1,0.5,1])` |
| 5 | 音频驱动 Size | `2+audio*5` |
| 6 | 加速 | `100+time*50` |
| 7 | 漂浮重力 | `Math.sin(time*2)*100` |
| 8 | 阵风 | `Math.sin(time*0.5)*100+wiggle(0.3,50)` |
| 9 | 湍流演化 | `time*30` |
| 10 | wiggle 摆动 | `wiggle(1, 100)` |

---

## 十、Particular JSX 脚本

JSX 脚本可批量自动化粒子创建和参数设置。

### 10.1 自动创建粒子图层脚本

```javascript
// 自动创建标准粒子层
(function() {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        alert("请先打开一个合成");
        return;
    }
    
    var solid = comp.layers.addSolid([0,0,0], "AutoParticles", comp.width, comp.height, 1);
    var fx = solid.property("Effects").addProperty("Particular");
    
    // 默认配置
    fx.property("Emitter").property("Emitter Type").setValue(0); // Point
    fx.property("Emitter").property("Particles/sec").setValue(100);
    fx.property("Emitter").property("Velocity").setValue(200);
    
    fx.property("Particle").property("Life").setValue(3);
    fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
    fx.property("Particle").property("Size").setValue(5);
    fx.property("Particle").property("Blend Mode").setValue(1); // Add
    
    // 自动加 Glow
    solid.property("Effects").addProperty("Glow");
    
    alert("粒子图层已创建！");
})();
```

### 10.2 粒子参数批量设置脚本

```javascript
// 批量设置选中层的粒子参数
(function() {
    var comp = app.project.activeItem;
    var layers = comp.selectedLayers;
    
    if (layers.length === 0) {
        alert("请先选择至少一个粒子层");
        return;
    }
    
    var preset = {
        emitterType: 0,
        particlesPerSec: 500,
        velocity: 300,
        life: 2,
        size: 4,
        blendMode: 1
    };
    
    for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];
        var fx = layer.property("Effects").property("Particular");
        if (!fx) continue;
        
        fx.property("Emitter").property("Emitter Type").setValue(preset.emitterType);
        fx.property("Emitter").property("Particles/sec").setValue(preset.particlesPerSec);
        fx.property("Emitter").property("Velocity").setValue(preset.velocity);
        fx.property("Particle").property("Life").setValue(preset.life);
        fx.property("Particle").property("Size").setValue(preset.size);
        fx.property("Particle").property("Blend Mode").setValue(preset.blendMode);
    }
    
    alert("已批量设置 " + layers.length + " 个图层");
})();
```

### 10.3 粒子动画序列脚本

```javascript
// 创建粒子动画序列
(function() {
    var comp = app.project.activeItem;
    var solid = comp.layers.addSolid([0,0,0], "Sequence", comp.width, comp.height, 1);
    var fx = solid.property("Effects").addProperty("Particular");
    
    fx.property("Emitter").property("Emitter Type").setValue(0);
    fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height/2]);
    
    // 序列：5 次爆发
    var ps = fx.property("Emitter").property("Particles/sec");
    ps.setValueAtTime(0, 0);
    
    for (var i = 0; i < 5; i++) {
        var burstTime = i * 1.0; // 每秒一次
        ps.setValueAtTime(burstTime, 0);
        ps.setValueAtTime(burstTime + 0.02, 3000);
        ps.setValueAtTime(burstTime + 0.05, 0);
    }
    
    fx.property("Emitter").property("Velocity").setValue(800);
    fx.property("Particle").property("Life").setValue(1.5);
    fx.property("Particle").property("Particle Type").setValue(1);
    fx.property("Particle").property("Size").setValue(4);
    fx.property("Particle").property("Blend Mode").setValue(1);
    
    solid.property("Effects").addProperty("Glow");
})();
```

### 10.4 火焰预设脚本

```javascript
// 一键应用火焰预设
(function() {
    var comp = app.project.activeItem;
    var solid = comp.layers.addSolid([0,0,0], "Fire", comp.width, comp.height, 1);
    var fx = solid.property("Effects").addProperty("Particular");
    
    // Emitter
    fx.property("Emitter").property("Emitter Type").setValue(0);
    fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height-100]);
    fx.property("Emitter").property("Particles/sec").setValue(500);
    fx.property("Emitter").property("Velocity").setValue(100);
    fx.property("Emitter").property("Direction").setValue(1);
    fx.property("Emitter").property("X Rotation").setValue(90);
    
    // Physics
    fx.property("Physics").property("Air").property("Turbulence Position").setValue(80);
    fx.property("Physics").property("Air").property("Turbulence Scale").setValue(8);
    
    // Particle
    fx.property("Particle").property("Life").setValue(1.2);
    fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
    fx.property("Particle").property("Size").setValue(5);
    fx.property("Particle").property("Blend Mode").setValue(1); // Add
    
    // Glow
    var glow = solid.property("Effects").addProperty("Glow");
    glow.property("Glow Radius").setValue(30);
    glow.property("Glow Intensity").setValue(1.5);
    
    alert("火焰预设已应用");
})();
```

### 10.5 雨预设脚本

```javascript
// 一键应用雨预设
(function() {
    var comp = app.project.activeItem;
    var solid = comp.layers.addSolid([0,0,0], "Rain", comp.width, comp.height, 1);
    var fx = solid.property("Effects").addProperty("Particular");
    
    fx.property("Emitter").property("Emitter Type").setValue(1); // Box
    fx.property("Emitter").property("Emitter Size X").setValue(2500);
    fx.property("Emitter").property("Emitter Size Y").setValue(0);
    fx.property("Emitter").property("Emitter Size Z").setValue(1000);
    fx.property("Emitter").property("Position XY").setValue([comp.width/2, -200]);
    fx.property("Emitter").property("Particles/sec").setValue(1500);
    fx.property("Emitter").property("Velocity").setValue(1000);
    fx.property("Emitter").property("Direction").setValue(1);
    fx.property("Emitter").property("X Rotation").setValue(100);
    
    fx.property("Physics").property("Gravity").setValue(800);
    fx.property("Physics").property("Air").property("Wind X").setValue(150);
    
    fx.property("Particle").property("Life").setValue(0.6);
    fx.property("Particle").property("Particle Type").setValue(5); // Streaklet
    fx.property("Particle").property("Streaklet Amount").setValue(12);
    fx.property("Particle").property("Size").setValue(2);
    fx.property("Particle").property("Blend Mode").setValue(1); // Add
    
    fx.property("Rendering").property("Motion Blur").setValue(1);
    fx.property("Rendering").property("Shutter Angle").setValue(360);
    
    alert("雨预设已应用");
})();
```

### 10.6 雪预设脚本

```javascript
// 一键应用雪预设
(function() {
    var comp = app.project.activeItem;
    var solid = comp.layers.addSolid([0,0,0], "Snow", comp.width, comp.height, 1);
    var fx = solid.property("Effects").addProperty("Particular");
    
    fx.property("Emitter").property("Emitter Type").setValue(1);
    fx.property("Emitter").property("Emitter Size X").setValue(2000);
    fx.property("Emitter").property("Emitter Size Y").setValue(0);
    fx.property("Emitter").property("Emitter Size Z").setValue(500);
    fx.property("Emitter").property("Position XY").setValue([comp.width/2, -100]);
    fx.property("Emitter").property("Particles/sec").setValue(500);
    fx.property("Emitter").property("Velocity").setValue(50);
    fx.property("Emitter").property("Direction").setValue(1);
    fx.property("Emitter").property("X Rotation").setValue(90);
    
    fx.property("Physics").property("Gravity").setValue(40);
    fx.property("Physics").property("Air").property("Wind X").setValue(30);
    fx.property("Physics").property("Air").property("Turbulence Position").setValue(30);
    fx.property("Physics").property("Air").property("Turbulence Scale").setValue(8);
    
    fx.property("Particle").property("Life").setValue(10);
    fx.property("Particle").property("Particle Type").setValue(8); // Faded Sphere
    fx.property("Particle").property("Size").setValue(5);
    fx.property("Particle").property("Size Random").setValue(50);
    fx.property("Particle").property("Blend Mode").setValue(2); // Screen
    
    alert("雪预设已应用");
})();
```

### 10.7 烟雾预设脚本

```javascript
// 一键应用烟雾预设
(function() {
    var comp = app.project.activeItem;
    var solid = comp.layers.addSolid([0,0,0], "Smoke", comp.width, comp.height, 1);
    var fx = solid.property("Effects").addProperty("Particular");
    
    fx.property("Emitter").property("Emitter Type").setValue(0);
    fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height-50]);
    fx.property("Emitter").property("Particles/sec").setValue(100);
    fx.property("Emitter").property("Velocity").setValue(80);
    
    fx.property("Physics").property("Air").property("Turbulence Position").setValue(150);
    fx.property("Physics").property("Air").property("Turbulence Scale").setValue(30);
    fx.property("Physics").property("Air").property("Turbulence Complexity").setValue(4);
    
    fx.property("Particle").property("Life").setValue(5);
    fx.property("Particle").property("Particle Type").setValue(4); // Cloudlet
    fx.property("Particle").property("Size").setValue(200);
    fx.property("Particle").property("Opacity").setValue(10);
    fx.property("Particle").property("Blend Mode").setValue(2); // Screen
    
    var glow = solid.property("Effects").addProperty("Glow");
    glow.property("Glow Radius").setValue(50);
    
    alert("烟雾预设已应用");
})();
```

### 10.8 爆炸预设脚本

```javascript
// 一键应用爆炸预设（四层）
(function() {
    var comp = app.project.activeItem;
    var layers = [];
    var names = ["Fireball", "Smoke", "Debris", "Sparks"];
    var types = [1, 4, 0, 1]; // Glow Sphere, Cloudlet, Sphere, Glow Sphere
    var velocities = [800, 300, 1200, 2000];
    var lives = [1, 4, 3, 1.5];
    var sizes = [8, 300, 4, 3];
    var opacities = [100, 30, 100, 100];
    var blendModes = [1, 2, 0, 1]; // Add, Screen, Normal, Add
    var particlesPerSec = [3000, 500, 200, 500];
    
    for (var i = 0; i < 4; i++) {
        var solid = comp.layers.addSolid([0,0,0], "Explosion_" + names[i], comp.width, comp.height, 1);
        var fx = solid.property("Effects").addProperty("Particular");
        
        fx.property("Emitter").property("Emitter Type").setValue(0);
        fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height/2]);
        
        // 突发发射（仅火球层和碎片层）
        var ps = fx.property("Emitter").property("Particles/sec");
        if (i === 0 || i === 2 || i === 3) {
            ps.setValueAtTime(0, 0);
            ps.setValueAtTime(0.03, particlesPerSec[i]);
            ps.setValueAtTime(0.06, 0);
        } else {
            ps.setValueAtTime(0, 0);
            ps.setValueAtTime(0.05, particlesPerSec[i]);
            ps.setValueAtTime(0.5, 0);
        }
        
        fx.property("Emitter").property("Velocity").setValue(velocities[i]);
        fx.property("Emitter").property("Velocity Random").setValue(80);
        
        if (i === 2) {
            fx.property("Physics").property("Physics Model").setValue(1); // Bounce
        }
        fx.property("Physics").property("Gravity").setValue(100);
        
        fx.property("Particle").property("Life").setValue(lives[i]);
        fx.property("Particle").property("Particle Type").setValue(types[i]);
        fx.property("Particle").property("Size").setValue(sizes[i]);
        fx.property("Particle").property("Opacity").setValue(opacities[i]);
        fx.property("Particle").property("Blend Mode").setValue(blendModes[i]);
        
        solid.property("Effects").addProperty("Glow");
        layers.push(solid);
    }
    
    alert("爆炸预设已应用（4 层）");
})();
```

### 10.9 性能优化脚本

```javascript
// 一键应用性能优化设置
(function() {
    var comp = app.project.activeItem;
    var layers = comp.selectedLayers;
    
    if (layers.length === 0) {
        alert("请先选择粒子层");
        return;
    }
    
    for (var i = 0; i < layers.length; i++) {
        var fx = layers[i].property("Effects").property("Particular");
        if (!fx) continue;
        
        // 切换到 Draft Render
        fx.property("Rendering").property("Render Mode").setValue(1);
        
        // 关闭 Aux System（如果未使用）
        var auxEmit = fx.property("AuxSystem").property("Emit");
        if (auxEmit.value === 0) {
            // 已关闭
        }
        
        // 限制粒子寿命
        var life = fx.property("Particle").property("Life").value;
        if (life > 5) {
            fx.property("Particle").property("Life").setValue(5);
        }
        
        // 限制 Particles/sec
        var ps = fx.property("Emitter").property("Particles/sec").value;
        if (ps > 5000) {
            fx.property("Emitter").property("Particles/sec").setValue(5000);
        }
    }
    
    alert("已对 " + layers.length + " 个图层应用性能优化");
})();
```

### 10.10 10 个实用 JSX 脚本速查

| # | 脚本名称 | 功能 |
|---|---------|------|
| 1 | AutoCreateParticles | 自动创建标准粒子层 |
| 2 | BatchSetParams | 批量设置选中层参数 |
| 3 | ParticleSequence | 创建粒子动画序列 |
| 4 | FirePreset | 一键火焰预设 |
| 5 | RainPreset | 一键雨预设 |
| 6 | SnowPreset | 一键雪预设 |
| 7 | SmokePreset | 一键烟雾预设 |
| 8 | ExplosionPreset | 一键爆炸预设（4 层） |
| 9 | PerformanceOptimizer | 一键性能优化 |
| 10 | AudioDrivenParticles | 音频驱动粒子（自动生成） |

### 10.11 音频驱动粒子完整脚本

```javascript
// 音频驱动粒子（完整自动化）
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    
    // 查找音频振幅层
    var audioLayer = null;
    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).name === "Audio Amplitude") {
            audioLayer = comp.layer(i);
            break;
        }
    }
    
    if (!audioLayer) {
        alert("未找到 Audio Amplitude 层，请先用 Keyframe Assistant → Convert Audio to Keyframes 生成");
        return;
    }
    
    // 创建粒子层
    var solid = comp.layers.addSolid([0,0,0], "AudioParticles", comp.width, comp.height, 1);
    var fx = solid.property("Effects").addProperty("Particular");
    
    // 基础设置
    fx.property("Emitter").property("Emitter Type").setValue(0); // Point
    fx.property("Emitter").property("Position XY").setValue([comp.width/2, comp.height/2]);
    fx.property("Emitter").property("Velocity").setValue(300);
    
    // Particles/sec 由音频驱动
    fx.property("Emitter").property("Particles/sec").expression = 
        'var a = thisComp.layer("Audio Amplitude"); a.effect("Both Channels")("Slider") * 500;';
    
    // Size 由音频驱动
    fx.property("Particle").property("Size").expression = 
        'var a = thisComp.layer("Audio Amplitude"); 2 + a.effect("Both Channels")("Slider") * 3;';
    
    // 静态参数
    fx.property("Particle").property("Life").setValue(1.5);
    fx.property("Particle").property("Particle Type").setValue(1); // Glow Sphere
    fx.property("Particle").property("Size Random").setValue(50);
    fx.property("Particle").property("Blend Mode").setValue(1); // Add
    fx.property("Physics").property("Gravity").setValue(100);
    
    // Glow
    solid.property("Effects").addProperty("Glow");
    
    alert("音频驱动粒子已创建！");
})();
```

---

## 附录：参数索引速查

### A.1 Emitter 参数索引

| 参数 | 路径 | 说明 |
|------|------|------|
| Emitter Type | Emitter → Emitter Type | 发射器类型 |
| Position XY | Emitter → Position XY | XY 位置 |
| Position Z | Emitter → Position Z | Z 位置 |
| Particles/sec | Emitter → Particles/sec | 每秒粒子数 |
| Velocity | Emitter → Velocity | 速度 |
| Velocity Random | Emitter → Velocity Random | 速度随机 |
| Direction | Emitter → Direction | 方向 |
| X Rotation | Emitter → X Rotation | X 旋转 |
| Y Rotation | Emitter → Y Rotation | Y 旋转 |
| Spread | Emitter → Spread | 散布 |
| Emitter Size X | Emitter → Emitter Size X | 盒子 X |
| Emitter Size Y | Emitter → Emitter Size Y | 盒子 Y |
| Emitter Size Z | Emitter → Emitter Size Z | 盒子 Z |

### A.2 Particle 参数索引

| 参数 | 路径 | 说明 |
|------|------|------|
| Life | Particle → Life | 寿命 |
| Life Random | Particle → Life Random | 寿命随机 |
| Particle Type | Particle → Particle Type | 类型 |
| Size | Particle → Size | 大小 |
| Size Random | Particle → Size Random | 大小随机 |
| Size over Life | Particle → Size over Life | 寿命大小曲线 |
| Opacity | Particle → Opacity | 透明度 |
| Opacity Random | Particle → Opacity Random | 透明度随机 |
| Opacity over Life | Particle → Opacity over Life | 寿命透明度曲线 |
| Color | Particle → Color | 颜色 |
| Color Random | Particle → Color Random | 颜色随机 |
| Color over Life | Particle → Color over Life | 寿命颜色渐变 |
| Blend Mode | Particle → Blend Mode | 混合模式 |
| Sphere Feather | Particle → Sphere Feather | 球羽化 |
| Streaklet Amount | Particle → Streaklet Amount | Streaklet 数量 |
| Cloudlet Density | Particle → Cloudlet Density | Cloudlet 密度 |

### A.3 Physics 参数索引

| 参数 | 路径 | 说明 |
|------|------|------|
| Physics Model | Physics → Physics Model | 物理模型 |
| Gravity | Physics → Gravity | 重力 |
| Wind X | Physics → Air → Wind X | X 风 |
| Wind Y | Physics → Air → Wind Y | Y 风 |
| Wind Z | Physics → Air → Wind Z | Z 风 |
| Air Resistance | Physics → Air → Air | 空气阻力 |
| Turbulence Position | Physics → Air → Turbulence Position | 湍流位置 |
| Turbulence Scale | Physics → Air → Turbulence Scale | 湍流缩放 |
| Turbulence Complexity | Physics → Air → Turbulence Complexity | 湍流复杂度 |
| Spin Amplitude | Physics → Air → Spin Amplitude | 旋转幅度 |
| Floor Layer | Physics → Bounce → Floor Layer | 地面层 |
| Bounce | Physics → Bounce → Bounce | 反弹系数 |
| Friction | Physics → Bounce → Friction | 摩擦力 |
| Fluid Velocity | Physics → Fluid → Velocity | 流体速度 |
| Viscosity | Physics → Fluid → Viscosity | 粘度 |
| Diffusion | Physics → Fluid → Diffusion | 扩散率 |

### A.4 Aux System 参数索引

| 参数 | 路径 | 说明 |
|------|------|------|
| Emit | Aux System → Emit | 发射模式 |
| Particles/sec | Aux System → Particles/sec | 子粒子率 |
| Life | Aux System → Life | 子粒子寿命 |
| Type | Aux System → Type | 子粒子类型 |
| Size | Aux System → Size | 子粒子大小 |
| Inherit Velocity | Aux System → Inherit Velocity | 继承速度 |
| Inherit Size | Aux System → Inherit Size | 继承大小 |
| Inherit Color | Aux System → Inherit Color | 继承颜色 |

### A.5 Rendering 参数索引

| 参数 | 路径 | 说明 |
|------|------|------|
| Render Mode | Rendering → Render Mode | 渲染模式 |
| Motion Blur | Rendering → Motion Blur | 运动模糊 |
| Shutter Angle | Rendering → Shutter Angle | 快门角度 |
| Depth of Field | Rendering → Depth of Field | 景深 |
| GPU | Rendering → GPU | GPU 加速 |

---

## 附录：常见问题 FAQ

### Q1：粒子数量过多导致渲染慢？

**A**：使用以下优化策略：
1. 限制 Life（屏幕粒子数 ≈ Particles/sec × Life）
2. 关闭未使用的 Aux / Spherical Field
3. 编辑阶段用 Draft Render
4. 启用 GPU 加速（Particular 5+）
5. 长合成拆为短循环

### Q2：粒子与摄像机不交互？

**A**：检查：
1. Particular 是 2.5D，会自动与 AE 摄像机交互
2. 确保 Emitter Size Z > 0（粒子分布在 3D 空间）
3. 摄像机属性开启 Enable Depth of Field

### Q3：拖尾不连续？

**A**：将 Emitter → Position Subframe 改为 `10x Linear` 或 `10x Smooth`，避免快速移动时拖尾出现阶梯。

### Q4：Aux System 不发射子粒子？

**A**：检查：
1. Emit 模式选对（At Death / Continuously / On Collision）
2. 主粒子寿命足够（Life > 0.5s）
3. Aux Particles/sec > 0

### Q5：Fluid 物理太慢？

**A**：Fluid 性能开销大，建议：
1. 粒子数 < 50000
2. 寿命 < 3s
3. Simulation Quality = Draft（预览）/ High（最终）
4. 启用 GPU

### Q6：如何让粒子消失更自然？

**A**：使用 `Opacity over Life` 曲线，让粒子在出生时淡入、死亡时淡出。常见曲线为"梯形"或"先升后降"。

### Q7：如何让粒子颜色变化更丰富？

**A**：使用 `Color over Life` 多色梯度，配合 `Color Random` 增加变化。也可用表达式驱动颜色（见第九章）。

### Q8：如何让爆炸效果更真实？

**A**：使用多层组合（火球 + 烟雾 + 碎片 + 火花），每层独立参数。配合 Glow + Curves 提亮。

---

## 附录：Particular vs Stardust 对比

| 维度 | Particular | Stardust |
|------|-----------|----------|
| 工作流 | AE 图层+效果面板 | 节点系统 |
| 学习曲线 | 平缓 | 陡峭 |
| 3D 能力 | OBJ 仅做发射器形状 | 完整 3D 模型粒子+碰撞检测 |
| Aux 层级 | 一层子粒子 | 多层分支 |
| 价格 | 订阅（Maxon One ~$99/月） | $189 一次性永久 |
| 最佳场景 | 快速产出、标准 VFX | 高端定制、电影/MV |
| 预设数 | 355+ | 200+ |
| GPU 加速 | Particular 5+ | 全程 GPU |

**建议**：从 Particular 入门（海量教程+预设），需要 3D 模型粒子或极端粒子数时升级到 Stardust。

---

## 附录：学习资源

| 资源 | 类型 | 级别 |
|------|------|------|
| Video Copilot Light Streaks | 免费视频 | 中高级 |
| Chad Perkins *Particular Fundamentals* | 付费 (~4h) | 入门 |
| B 站 *Particular 从入门到精通* | 免费 | 入门-进阶 |
| Fox Studio 硬核参数全解 | 免费博客 | 高级 |
| 355+ 内置预设 | 官方 | 全部 |
| Maxon 官方文档 | 官方 | 全部 |
| Red Giant Trapcode YouTube | 免费 | 全部 |

---

> 相关链接：[[静止系MAD知识体系]] · [[风格化剪辑技巧与预设]] · [[AE-AI工具整合工作流]] · [[🎬-风格化剪辑知识库-MOC]]

---
title: AE新手教程工程深度解析（10套AEP实机逆向）
date: 2026-07-23
tags:
  - AEP解析
  - 效果参数
  - 风格化
  - 新手教程
  - 逆向分析
  - matchName
---
# AE新手教程工程深度解析（10套AEP实机逆向）

> [!abstract] 文档摘要
> 本文档通过对 `D:\BaiduNetdiskDownload\AE新手10套` 中 9 个 AEP 工程文件的二进制逆向解析，提取了所有实际使用的效果 matchName、合成参数、图层结构和第三方插件。这些真实工程数据为效果系统开发、风格化模板构建和 JSX 脚本生成提供了可靠的一手参考。

> [!tip] 数据来源
> - 9 个 AEP 工程（从 2MB 到 19MB），覆盖简单/一般/较难/量多四个难度
> - 通过 `aep_binary_parser.py` 离线二进制扫描提取，无需 AE 启动
> - 所有 matchName 均为实机工程中使用过的真实值

---

## 一、工程总览

| 工程名 | 难度 | 分辨率 | 帧率 | 文件大小 | 核心特征 |
|--------|------|--------|------|----------|----------|
| 初音 | 简单 | 3840×2160 (4K) | 50/60fps | 2.1 MB | 3D层+Mocha+TextureFlux |
| do you mean | 简单 | 1920×1080 + 4K | 25/30fps | 10.3 MB | Hue/Saturation+Ramp |
| 李诗雅竖屏 | 简单 | 2160×3840 (竖屏) | 25/30fps | 9.9 MB | Lumetri调色+Looks插件 |
| 独自升级 | 一般 | 1920×1080 | 50/60fps | 3.2 MB | Exposure+Audio Spectrum+Flicker |
| 五条悟 | 一般 | 1920×1080 | 24-60fps | 5.6 MB | CrackedTiles+Exposure+Mocha |
| 猫猫 | 一般 | 1920×1080 + 1080×1080 | 30/60fps | 16.1 MB | B&W+Box Blur+Film Strip |
| 8.15 | 一般 | 1920×1080 + 4K | 24-60fps | 18.7 MB | Deep Glow+B&W+Box Blur |
| 美人鱼 | 较难 | 1920×1080 + 4K | 24-60fps | 6.1 MB | Audio Spectrum+BCC LED+Twixtor |
| 蓝色监狱 | 量多 | 1920×1080 + 4K | 24-60fps | 8.3 MB | TextureCells+CrackedTiles+Mocha |
| 辉夜 | 一般 | 1920×1080 + 4K | 24-60fps | - | 枫叶素材+调色 |

### 关键发现

```
合成分辨率分布：
├── 1920×1080 (FHD) — 所有工程均包含，主力合成
├── 3840×2160 (4K) — 7/9 工程使用，用于高质量输出
├── 2160×3840 (竖屏4K) — 1/9（李诗雅），短视频平台
├── 1280×720 (HD) — 4/9 工程，预览/代理合成
└── 1080×1080 (方形) — 1/9（猫猫），Instagram/社交媒体

帧率使用频率：
├── 60fps — 9/9（全部），流畅动画/补帧
├── 50fps — 7/9，PAL 区域标准
├── 30fps — 7/9，标准帧率
├── 24fps — 4/9，电影感
└── 25fps — 4/9，PAL 标准
```

---

## 二、效果 matchName 完整清单（实机验证）

### 2.1 调色/校正类（出现频率最高）

| matchName | 效果名称 | 使用工程 | 频率 |
|-----------|----------|----------|------|
| `ADBE Lumetri` | Lumetri Color | 全部工程 | ★★★★★ |
| `ADBE Exposure2` | Exposure | 独自升级/五条悟/蓝色监狱/8.15 | ★★★★ |
| `ADBE Brightness & Contrast 2` | Brightness & Contrast | 多工程 | ★★★★ |
| `ADBE HUE SATURATION` | Hue/Saturation | do you mean | ★★★ |
| `ADBE CurvesCustom` | Curves | 多工程 | ★★★ |
| `ADBE Tint` | Tint | 多工程 | ★★★ |
| `ADBE Tritone` | Tritone | 多工程 | ★★★ |
| `ADBE Black&White` | Black & White | 猫猫/8.15 | ★★ |
| `ADBE PhotoFilterPS` | Photo Filter | 多工程 | ★★ |
| `ADBE Invert` | Invert | 多工程 | ★★ |
| `ADBE Shift Channels` | Shift Channels | 多工程 | ★★ |
| `ADBE Fill` | Fill | 多工程 | ★★ |

> [!warning] matchName 注意
> - `ADBE HUE SATURATION` 必须**全大写**，不是 `ADBE Hue/Saturation`
> - `ADBE Exposure2` 带数字后缀 `2`
> - `ADBE Brightness & Contrast 2` 也带 `2`
> - `ADBE Black&White` 没有空格，`&` 直接连接

### 2.2 模糊/锐化类

| matchName | 效果名称 | 使用工程 | 频率 |
|-----------|----------|----------|------|
| `ADBE Gaussian Blur` | Gaussian Blur | 多工程 | ★★★★ |
| `ADBE Gaussian Blur 2` | Gaussian Blur 2 (旧版) | 多工程 | ★★★ |
| `ADBE Box Blur2` | Box Blur | 猫猫/8.15 | ★★ |
| `ADE Unsharp Mask2` | Unsharp Mask | 多工程 | ★★ |
| `ADBE Sharpen` | Sharpen | 多工程 | ★ |

### 2.3 生成类

| matchName | 效果名称 | 使用工程 | 频率 |
|-----------|----------|----------|------|
| `ADBE Fractal Noise` | Fractal Noise | 多工程（重度使用） | ★★★★★ |
| `ADBE Ramp` | Ramp (渐变) | 多工程 | ★★★★ |
| `ADBE Noise2` | Noise | 多工程 | ★★ |
| `ADBE Venetian Blinds` | Venetian Blinds | 多工程 | ★★ |

### 2.4 扭曲/变形类

| matchName | 效果名称 | 使用工程 | 频率 |
|-----------|----------|----------|------|
| `ADBE Turbulent Displace` | Turbulent Displace | 多工程 | ★★★★ |
| `ADBE Wave Warp` | Wave Warp | 多工程 | ★★★ |
| `ADBE Mosaic` | Mosaic | 多工程 | ★★ |
| `ADBE Tile` | Tile | 多工程 | ★★ |
| `ADBE Optics Compensation` | Optics Compensation | 多工程 | ★★ |
| `ADBE WRPMESH` | Mesh Warp | 多工程 | ★★ |
| `ADBE Geometry2` | Geometry | 多工程 | ★★ |

### 2.5 风格化类

| matchName | 效果名称 | 使用工程 | 频率 |
|-----------|----------|----------|------|
| `ADBE Glo2` | Glow | 多工程 | ★★★★ |
| `ADBE Emboss` | Emboss (浮雕) | 多工程 | ★★ |
| `ADBE Escher` | Escher | 初音/多工程 | ★ |
| `ADBE Samurai` | Samurai (水墨) | 多工程 | ★ |

### 2.6 转场/特殊生成

| matchName | 效果名称 | 使用工程 | 频率 |
|-----------|----------|----------|------|
| `ADBE CM CrackedTiles` | Cracked Tiles | 五条悟/蓝色监狱 | ★★ |

### 2.7 音频响应类

| matchName | 效果名称 | 使用工程 | 频率 |
|-----------|----------|----------|------|
| `ADBE AudSpect` | Audio Spectrum | 美人鱼 | ★ |

### 2.8 3D 层/材质类（初音等使用）

```
3D 相关 matchName（来自初音工程）：
├── ADBE Extrsn Depth          — 3D 挤出深度
├── ADBE Extrsn Options Group  — 3D 挤出选项组
├── ADBE Bevel Styles          — 斜角样式
├── ADBE Bevel Depth           — 斜角深度
├── ADBE Bevel Direction       — 斜角方向
├── ADBE Fresnel Coefficient   — 菲涅尔系数
├── ADBE Glossiness Coefficient — 光泽系数
├── ADBE Index of Refraction   — 折射率
├── ADBE Reflection Coefficient — 反射系数
├── ADBE Transparency Coefficient — 透明系数
├── ADBE Light Transmission    — 光透射
├── ADBE Plane Curvature       — 平面曲率
├── ADBE Plane Subdivision     — 平面细分
└── ADBE Plane Options Group   — 平面选项组
```

### 2.9 文字动画类

```
文字效果 matchName（多工程使用）：
├── ADBE Text Document          — 文字文档
├── ADBE Text Properties        — 文字属性
├── ADBE Text More Options      — 文字更多选项
├── ADBE Text Path Options      — 文字路径选项
├── ADBE Text Animator          — 文字动画器
├── ADBE Text Animators         — 文字动画器集合
├── ADBE Text Animator Properties — 动画器属性
├── ADBE Text Selector          — 文字选择器
├── ADBE Text Selectors         — 选择器集合
├── ADBE Text Range Advanced    — 范围高级
├── ADBE Text Range Shape       — 范围形状
├── ADBE Text Render Order      — 渲染顺序
├── ADBE Text Random Seed       — 随机种子
├── ADBE Text Randomize Order   — 随机顺序
├── ADBE Text Rotation          — 文字旋转
├── ADBE Text Scale 3D          — 3D 缩放
├── ADBE Text Tracking Amount   — 字距
├── ADBE Text Opacity           — 文字不透明度
├── ADBE Text Blur              — 文字模糊
├── ADBE Text Character Blend Mode — 字符混合模式
├── ADBE Text Levels Min Ease   — 最小缓动
├── ADBE Text Percent Start     — 百分比起始
├── ADBE Text Percent Offset    — 百分比偏移
├── ADBE Text Line Anchor       — 行锚点
└── ADBE Text Track Type        — 轨道类型
```

---

## 三、第三方插件使用统计

从 AEP 二进制中提取的非 ADBE 插件引用：

| 插件名 | 使用工程 | 用途 | 安装状态 |
|--------|----------|------|----------|
| **S_TextureFlux** (Sapphire) | 初音/五条悟 | 纹理流动效果 | ✅ 已安装 (287 aex) |
| **S_TextureCells** (Sapphire) | 蓝色监狱 | 细胞纹理 | ✅ 已安装 |
| **S_Flicker** (Sapphire) | 独自升级 | 闪烁效果 | ✅ 已安装 |
| **Deep Glow** | 8.15/独自升级 | 高级发光 | ✅ 已安装 |
| **BCC LED** | 美人鱼 | LED 点阵效果 | ✅ 已安装 (BCCLED.aex) |
| **BCC Halftone** | 独自升级 | 半调网点 | ✅ 已安装 (BCCHalftone.aex) |
| **BCC Prism** | 独自升级 | 棱镜色散 | ✅ 已安装 (BCCPrism.aex) |
| **BCC Swish Pan** | 独自升级 | 快速摇摄转场 | ✅ 已安装 (BCCSwishPan.aex) |
| **Mocha** (Planar tracking) | 初音/五条悟/蓝色监狱 | 平面跟踪/遮罩 | ✅ 已安装 (内置) |
| **Looks** (Colorista) | 李诗雅/独自升级 | 专业调色 | ✅ 已安装 |
| **Twitch** (VideoCopilot) | 独自升级 | 故障/抖动效果 | ✅ 已安装 |
| **EFX Chromatic** | 独自升级 | 色差/色散 | ✅ 已安装 |
| **Twixtor** | 初音/美人鱼 | 光学补帧/变速 | ❌ 未安装（素材已预渲染，无需插件） |
| **Instant 4K** | do you mean | 超分辨率放大 | ❌ 未安装（ScaleUp.aex 可替代） |

> [!important] 2026-07-23 修正
> BCC (Boris Continuum Complete) 实际已安装 450 个插件！之前扫描脚本因文件名匹配错误（`"BCC Halftone"` vs `BCCHalftone.aex`）误报为缺失。
> 教程工程所需插件**实际覆盖率 = 100%**（Twixtor/Instant 4K 效果已预渲染到素材视频中）。

### 插件环境总览（2026-07-23 扫描）

```
AE 2025 插件总量：2217 个 .aex
├── Continuum Plug-ins (BCC): 450
├── Effects (内置): 299
├── Sapphire Plug-ins: 287
├── FCE7 + FEC Presets: 200
├── Ignite Pro/Core: 154
├── Digital Film Tools: 145
├── NewBlue: 114
├── DF4: 106
├── Digieffects: 68
├── Vision Effects (RE:Vision RSMB等): 56
├── Red Giant: 43
├── VideoCopilot: 9
└── 其他: ~266

已安装脚本面板 (ScriptUI Panels): 19 个
├── Duik Bassel / Motion 2 / GifGun / Animation Kit
├── TypeMonkey / Easy Arrows / Holomatrix / Projection 3D
└── mcp-bridge-auto (MCP通信)
```

---

## 四、风格化技术总结

### 4.1 常见效果组合模式（从工程中提取）

```
模式1：赛博朋克/霓虹风格（独自升级/五条悟）
├── Exposure2 → 曝光调整
├── Lumetri → 色彩分级
├── Fractal Noise + Overlay混合模式 → 纹理叠加
├── Glow (ADBE Glo2) → 发光
└── Turbulent Displace → 扭曲变形

模式2：动漫混剪风格（蓝色监狱/五条悟）
├── CrackedTiles → 碎裂转场
├── Mocha → 角色跟踪
├── Sapphire TextureFlux → 纹理叠加
├── Tint → 色调映射
└── Wave Warp → 波动变形

模式3：清新/文艺风格（do you mean/李诗雅）
├── Hue/Saturation → 色彩调整
├── Ramp → 渐变背景
├── Lumetri/Looks → 专业调色
├── Gaussian Blur → 柔化
└── Photo Filter → 暖色调滤镜

模式4：复古/胶片风格（猫猫/8.15）
├── Black & White → 黑白化
├── Box Blur → 模糊
├── Film Strip → 胶片边框
├── Noise → 噪点
└── Deep Glow → 柔光

模式5：音频响应风格（美人鱼）
├── Audio Spectrum → 音频频谱可视化
├── BCC LED → LED 点阵
├── Twixtor → 光学变速
└── Lumetri → 调色
```

### 4.2 合成结构模式

```
典型图层结构（从上到下）：
├── [调整图层] — Lumetri/Exposure/Levels
├── [文字层] — Text + Glow + 动画
├── [纹理叠加层] — Fractal Noise + Overlay/Screen 混合模式
├── [主视频层] — 调色 + 风格化效果
├── [背景层] — Ramp/纯色
└── [摄像机] — 3D 空间（部分工程）

混合模式使用频率：
├── Overlay — 纹理叠加（最常用）
├── Screen — 发光叠加
├── Add — 光效叠加
└── Difference — 遮罩/运动检测
```

---

## 五、对项目的开发指导意义

### 5.1 TextFX 效果系统修正建议

基于实机 AEP 解析，以下 matchName 已确认为真实可用：

```python
# 已验证的效果 matchName（来自 9 个真实工程）
VERIFIED_EFFECTS = {
    "glow": "ADBE Glo2",                    # 内置 Glow
    "fractal_noise": "ADBE Fractal Noise",  # 分形噪波
    "gaussian_blur": "ADBE Gaussian Blur",  # 高斯模糊
    "levels": "ADBE Easy Levels",           # 色阶（实机验证）
    "hue_saturation": "ADBE HUE SATURATION", # 色相/饱和度（全大写）
    "exposure": "ADBE Exposure2",           # 曝光
    "tint": "ADBE Tint",                    # 染色
    "tritone": "ADBE Tritone",             # 三色
    "curves": "ADBE CurvesCustom",          # 曲线
    "brightness_contrast": "ADBE Brightness & Contrast 2",
    "black_white": "ADBE Black&White",      # 黑白
    "photo_filter": "ADBE PhotoFilterPS",   # 照片滤镜
    "invert": "ADBE Invert",                # 反相
    "ramp": "ADBE Ramp",                    # 渐变
    "turbulent_displace": "ADBE Turbulent Displace",
    "wave_warp": "ADBE Wave Warp",          # 波浪变形
    "mosaic": "ADBE Mosaic",                # 马赛克
    "tile": "ADBE Tile",                    # 平铺
    "optics_compensation": "ADBE Optics Compensation",
    "mesh_warp": "ADBE WRPMESH",            # 网格变形
    "noise": "ADBE Noise2",                 # 噪点
    "sharpen": "ADBE Sharpen",              # 锐化
    "unsharp_mask": "ADBE Unsharp Mask2",   # USM锐化
    "box_blur": "ADBE Box Blur2",           # 方框模糊
    "emboss": "ADBE Emboss",                # 浮雕
    "fill": "ADBE Fill",                    # 填充
    "venetian_blinds": "ADBE Venetian Blinds",
    "audio_spectrum": "ADBE AudSpect",      # 音频频谱
    "cracked_tiles": "ADBE CM CrackedTiles", # 碎裂瓷砖
    "shift_channels": "ADBE Shift Channels", # 通道偏移
}
```

### 5.2 新增效果模板方向

基于工程分析，以下效果组合在真实教程中被高频使用，建议作为模板优先开发：

1. **赛博朋克调色模板** — Exposure2 + Lumetri + Tint + Glow
2. **纹理叠加模板** — Fractal Noise + Overlay 混合 + 不透明度动画
3. **动漫转场模板** — CrackedTiles + Wave Warp + Mosaic
4. **复古胶片模板** — Black&White + Box Blur + Noise + PhotoFilter
5. **音频响应模板** — Audio Spectrum + 位置/缩放表达式驱动
6. **竖屏短视频模板** — 2160×3840 + Lumetri + 文字动画

### 5.3 参数范围参考（从工程二进制提取）

```
Fractal Noise 常用参数范围：
├── Noise Type: Basic (1) / Spline (3)
├── Fractal Type: Dynamic (3) / Turbulent Smooth (6)
├── Size: 5-50（纹理大小）
├── Complexity: 1-6（细节层次）
├── Sub Influence: 0.3-0.8
├── Sub Offset: 0-50
├── Evolution: 0+360° 关键帧动画
└── Brightness: -50 到 +50（注意不是 -100 到 100）

Glow (ADBE Glo2) 常用参数：
├── Threshold: 30-70%
├── Radius: 10-50
├── Colors: A 和 B 双色（常见青+品红）
└── Blend Mode: Screen / Add

Lumetri 常用子效果：
├── Basic Correction — 曝光/对比/饱和
├── Creative — 褪色胶片/锐化/饱和度
├── Curves — RGB 曲线
├── Color Wheels — 色轮调色
└── Vignette — 暗角
```

---

## 六、素材与输出规范

### 6.1 视频素材特征

```
素材格式分布：
├── MP4 (H.264) — 绝大多数，主力素材格式
├── MOV — 少量（猫猫工程，Mac 录制素材）
└── 无 RAW/ProRes 素材（新手教程级别）

素材分辨率：
├── 1920×1080 — 主力
├── 3840×2160 (4K) — 高质量素材（初音/Twixtor）
└── 竖屏素材 — 李诗雅工程

Twixtor 使用：
├── 初音 — Hatsune Miku Twixtor 4K.mp4 (504 MB)
└── 美人鱼 — alya-twixtor04.mp4 (100 MB)
→ 说明：高速运动/慢动作场景使用 Twixtor 光学补帧
```

### 6.2 成品输出规范

```
成品视频统计：
├── 格式：全部 MP4
├── 时长：10-25 秒（短视频平台标准）
├── 大小：12-23 MB
├── 分辨率：1080p 为主
└── 用途：抖音/B站/小红书
```

---

## 七、与现有知识库的关联

- [[AE效果视觉特征库]] — 本文档的效果 matchName 可作为视觉特征库的补充索引
- [[AE-滤镜效果系统完全指南]] — matchName 对照表
- [[参数-效果原子级映射库]] — 参数范围的实机验证
- `ae/textfx_effects.py` — 代码中的 matchName 应参照本文档的 VERIFIED_EFFECTS

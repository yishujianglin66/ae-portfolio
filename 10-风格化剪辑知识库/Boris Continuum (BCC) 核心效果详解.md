---
title: Boris Continuum (BCC) 核心效果详解
date: 2026-07-05
tags:
  - BCC
  - Continuum
  - Boris FX
  - 粒子
  - 光效
  - 抠像
  - 转场
  - 修复
---
# Boris Continuum (BCC) 核心效果详解

> Boris Continuum Complete (BCC) 是 AE 中功能最全面的第三方插件套件，涵盖粒子系统、3D物体、光效、抠像、转场、调色、修复、跟踪等。本地安装共 **450 个效果**。

---

## 一、BCC 效果分类总览

| 类别 | 数量（估） | 说明 | 核心效果 |
|------|-----------|------|---------|
| **3D Objects** | 15+ | 三维挤压物体/文字 | Extruded EPS, Extruded Spline, Extruded Text, 3D Objects |
| **Particles** | 10+ | 粒子系统 | Particle Emitter 3D, Particle Array 3D, Particle String, Comet, Rain, Snow, Sparks, Stars, Bubbles |
| **Lights** | 15+ | 光效/灯光 | Lens Flare, Spotlight, Xenon Spotlight, Glare, Glow, Light Sweep, Rays, Laser Beam |
| **Key & Blend** | 20+ | 抠像与合成 | Primatte Studio, Chroma Key Studio, Luma Key, Matte Choker, Alpha Cleanup, Light Wrap |
| **Transitions** | 50+ | 转场效果 | 所有 BCC 转场（Wipe/Dissolve/Glow/Zoom等） |
| **Color & Tone** | 25+ | 调色与色调 | Color Balance, Color Grade, Color Match, Three Way Color, Hue Sat Light |
| **Film Style** | 10+ | 电影风格化 | Film Damage, Film Glow, Film Process, Film Grain, Vignette |
| **Image Restoration** | 15+ | 图像修复 | Noise Reduction, Dust & Scratches, Flicker Fixer, Smooth Tone, DV Fixer |
| **Match Move** | 10+ | 运动跟踪/匹配 | Corner Pin, Match Move, Mocha (内置), Stabilizer |
| **Perspective** | 10+ | 透视变换 | 3D Extruded, Bender, Burnt Film, Page Turn, Cylinder, Sphere |
| **Stylize** | 25+ | 风格化 | Cartoon, Charcoal, Edge Glow, Emboss, Mosaic, Painterly, Pencil Sketch |
| **Time** | 5+ | 时间效果 | Beat Reactor, Jitter, Looper, Posterize Time, Trails |
| **Warp** | 15+ | 扭曲变形 | Bulge, Displacement Map, Kaleidoscope, Lens Distortion, Mirror, Polar, Ripple, Turbulence, Wave |
| **Blur & Sharpen** | 15+ | 模糊与锐化 | Directional Blur, Gaussian Blur, Lens Blur, Motion Blur, Radial Blur, Unsharp Mask |
| **Textures** | 15+ | 纹理生成 | Brushed Metal, Clouds, Fractal Noise, Granite, Marble, Stone, Wood |
| **Generate** | 15+ | 生成效果 | Grid, Ramp, Vignette, Checkerboard, Grid Wipe, Primitives |

---

## 二、BCC Particle Emitter 3D — 三维粒子发射器

> BCC 中最强大的粒子效果，支持 3D 空间粒子系统。

### 参数详解

| 参数组 | 参数 | 范围 | 说明 | 关键帧常用 |
|--------|------|------|------|-----------|
| **Emitter** | Emitter Type | Point/Line/Box/Sphere/Layer | - | 发射器类型 | ✅ |
| | Position X/Y/Z | - | px | 发射器位置 | ✅ |
| | Rotation X/Y/Z | 0-360 | ° | 发射器旋转 | ✅ |
| | Particles/sec | 0-10000+ | - | 每秒发射粒子数 | ✅ |
| | Velocity | 0-1000+ | px/s | 初速度 | ✅ |
| | Velocity Random | 0-100 | % | 速度随机值 | ✅ |
| | Spread X/Y/Z | 0-180 | ° | 发射扩散角 | ✅ |
| **Particle** | Shape | Sphere/Box/Star/Blob/Sprite | - | 粒子形状 | ✅ |
| | Size | 0-500 | px | 粒子大小 | ✅ |
| | Size Over Life | - | - | 生命周期内大小变化曲线 | ✅ |
| | Opacity | 0-100 | % | 不透明度 | ✅ |
| | Opacity Over Life | - | - | 生命周期内透明度曲线 | ✅ |
| | Color | RGB | - | 粒子颜色 | ✅ |
| | Color Over Life | - | - | 生命周期内颜色变化 | ✅ |
| | Rotation | 0-360 | ° | 粒子旋转 | ✅ |
| | Spin | -100-100 | °/sec | 自旋速度 | ✅ |
| | Life | 0.1-60 | sec | 粒子生命周期 | ✅ |
| | Life Random | 0-100 | % | 生命周期随机值 | ✅ |
| **Physics** | Gravity | -1000-1000+ | - | 重力 | ✅ |
| | Wind X/Y/Z | - | - | 风力 | ✅ |
| | Drag | 0-10 | - | 阻力/空气阻力 | ✅ |
| | Bounce | 0-100 | % | 地面反弹 | ✅ |
| | Bounce Floor | - | - | 地面位置 | ✅ |
| | Turbulence | 0-1000 | - | 湍流强度 | ✅ |
| | Turb Scale | 0-10 | - | 湍流缩放 | ✅ |
| | Turb Speed | 0-10 | - | 湍流演化速度 | ✅ |
| **Render** | Render Mode | Normal/Motion Blur/Glow | - | 渲染模式 | ✅ |
| | Motion Blur | 0-1 | - | 运动模糊量 | ✅ |
| | Glow | 0-100 | % | 发光强度 | ✅ |
| | Glow Radius | 0-100 | px | 发光半径 | ✅ |
| | Blend Mode | Add/Screen/Overlay | - | 混合模式 | ✅ |
| **Depth** | Depth of Field | On/Off | - | 景深 | ✅ |
| | Focus Distance | 0-50000 | px | 焦距 | ✅ |
| | Aperture | 0-1000 | px | 光圈 | ✅ |
| **Camera** | Camera | AE Camera/BCC Camera | - | 摄像机 | ✅ |

---

## 三、BCC Lens Flare 3D — 镜头光晕

> 专业 3D 镜头光晕，支持真实光学系统模拟。

| 参数组 | 参数 | 范围 | 说明 |
|--------|------|------|------|
| **Flare** | Source X/Y/Z | - | px | 光源位置 |
| | Intensity | 0-10 | - | 总强度 |
| | Scale | 0-10 | - | 整体缩放 |
| | Rotation | 0-360 | ° | 旋转 |
| | Aspect Ratio | 0.1-10 | - | 宽高比（变形镜头） |
| **Glow** | Glow Size | 0-10 | - | 中央发光大小 |
| | Glow Intensity | 0-10 | - | 中央发光强度 |
| | Glow Color | RGB | - | 发光颜色 |
| **Rings** | Ring Count | 0-50 | - | 光环数量 |
| | Ring Size | 0-10 | - | 光环大小 |
| | Ring Intensity | 0-10 | - | 光环强度 |
| | Ring Color | RGB | - | 光环颜色 |
| **Rays** | Ray Count | 0-200 | - | 光线数量 |
| | Ray Length | 0-10 | - | 光线长度 |
| | Ray Intensity | 0-10 | - | 光线强度 |
| | Ray Width | 0-1 | - | 光线宽度 |
| **Ghosts** | Ghost Count | 0-30 | - | 鬼影（光圈叶片反射）数量 |
| | Ghost Intensity | 0-10 | - | 鬼影强度 |
| | Ghost Size | 0-10 | - | 鬼影大小 |
| | Ghost Spacing | 0-10 | - | 鬼影间距 |
| **Chromatic** | Chromatic Aberration | 0-1 | - | 色差/色散 |
| | Red Offset / Blue Offset | - | - | 红蓝色偏移 |
| **Anamorphic** | Anamorphic | On/Off | - | 变形宽银幕模式 |
| | Squeeze | 0.5-2 | - | 挤压比 |
| **Animation** | Auto Rotate | -10-10 | - | 自动旋转速度 |
| | Flicker Amount | 0-1 | - | 闪烁幅度 |
| | Flicker Speed | 0-10 | - | 闪烁速度 |
| **Output** | Blend Mode | Add/Screen/Overlay | - | 混合模式 |
| | Flare Only | On/Off | - | 只输出光晕 |

---

## 四、BCC Primatte Studio / Chroma Key Studio — 专业抠像

> BCC 的专业级抠像工具，Primatte 是业界领先的蓝屏绿屏抠像算法。

### Primatte Studio 参数

| 参数组 | 参数 | 范围 | 说明 |
|--------|------|------|------|
| **Key Color** | Key Color | RGB | - | 抠像底色（绿/蓝） |
| | Pick Key Color | - | - | 用取色器选择底色 |
| **Matte** | Matte Density | 0-100 | % | 遮罩密度/不透明度 |
| | Matte Softness | 0-100 | % | 遮罩柔化 |
| | Matte Contract/Expand | -100-100 | % | 遮罩收缩/扩展 |
| **Spill** | Spill Suppression | 0-100 | % | 溢色抑制强度 |
| | Spill Color | RGB | - | 溢色颜色 |
| | Despill Bias | -100-100 | % | 去溢色偏移 |
| **Edges** | Edge Softness | 0-100 | % | 边缘柔化 |
| | Edge Thinning | -100-100 | % | 边缘细化 |
| | Choke | -100-100 | % | 边缘收缩 |
| **Foreground** | FG Density | 0-100 | % | 前景密度 |
| | FG Saturation | 0-200 | % | 前景饱和度 |
| | FG Brightness | -100-100 | % | 前景亮度 |
| **Screen Correction** | Screen Level | - | - | 屏幕校正（不均匀背景） |
| | Screen Softness | 0-100 | % | 屏幕柔化 |
| **Cleanup** | Clean FG Noise | 0-100 | - | 清除前景噪点 |
| | Clean BG Noise | 0-100 | - | 清除背景噪点 |
| **Light Wrap** | Light Wrap | On/Off | - | 光包裹（边缘融合） |
| | Wrap Intensity | 0-100 | % | 光包裹强度 |
| | Wrap Softness | 0-100 | % | 光包裹柔化 |
| | Wrap Color | RGB | - | 光包裹颜色 |
| **View** | View Mode | Final/Matte/Source/Spill etc | - | 查看模式（用于检查） |

### 抠像工作流

1. **选择底色**：用吸管吸取屏幕的平均绿/蓝色
2. **调整遮罩**：调整 Matte Density 直到背景接近透明
3. **处理边缘**：Edge Softness + Choke 精细调整边缘
4. **抑制溢色**：Spill Suppression 去除边缘绿色溢出
5. **清理噪点**：Clean FG/BG Noise 清除残留杂点
6. **光包裹**：Light Wrap 让前景边缘融入背景光

---

## 五、BCC Light Sweep — 光线扫过

> 一道光束从画面扫过的效果，常用于文字揭示、LOGO出场。

| 参数组 | 参数 | 范围 | 说明 |
|--------|------|------|------|
| **Light** | Light Center | X,Y | px | 光束中心位置 |
| | Light Direction | 0-360 | ° | 光束角度 |
| | Light Width | 0-1000 | px | 光束宽度 |
| | Light Length | 0-5000 | px | 光束长度 |
| | Light Intensity | 0-10 | - | 光束强度 |
| | Light Color | RGB | - | 光束颜色 |
| **Edge** | Edge Softness | 0-100 | % | 边缘柔化 |
| | Edge Thickness | 0-100 | % | 边缘厚度 |
| **Shine** | Shine Intensity | 0-10 | - | 闪烁强度 |
| | Shine Width | 0-100 | % | 闪烁宽度 |
| | Shine Detail | 0-100 | % | 闪烁细节 |
| **Glow** | Glow Radius | 0-200 | px | 发光半径 |
| | Glow Intensity | 0-10 | - | 发光强度 |
| **Animation** | Sweep Speed | -10-10 | - | 扫过速度 |
| | Sweep Phase | 0-100 | % | 扫过相位 |
| | Flicker | 0-1 | - | 闪烁 |
| **Composite** | Blend Mode | Add/Screen/Overlay | - | 混合模式 |
| | Light Only | On/Off | - | 只输出光 |

### 典型文字扫光动画
```
0s:   Sweep Phase = 0%
0.5s: Sweep Phase = 100%
```
配合文字层，光从左扫到右揭示文字

---

## 六、BCC Glow — 发光效果

| 参数组 | 参数 | 范围 | 说明 |
|--------|------|------|------|
| **Glow** | Glow Amount | 0-10 | - | 发光强度 |
| | Glow Radius | 0-500 | px | 发光半径 |
| | Glow Threshold | 0-1 | - | 发光阈值 |
| | Glow Threshold Softness | 0-1 | - | 阈值柔化 |
| **Color** | Glow Color | RGB | - | 发光染色 |
| | Color Tint | 0-100 | % | 染色强度 |
| | Color Gamma | 0.1-10 | - | 颜色Gamma |
| **Shapes** | Horizontal Glow / Vertical Glow | 0-10 | - | 横向/纵向发光比例 |
| | Glow Aspect | 0.1-10 | - | 发光宽高比 |
| **Quality** | Glow Quality | 1-10 | - | 发光质量（采样精度） |
| **Options** | Glow From Alpha | On/Off | - | 从Alpha通道发光 |
| | Glow Only | On/Off | - | 只输出发光 |
| | Blend Mode | Add/Screen/Normal | - | 混合模式 |

---

## 七、BCC Film Damage — 胶片损坏效果

> 模拟老电影胶片的划痕、灰尘、毛发、闪烁等效果。

| 参数组 | 参数 | 范围 | 说明 |
|--------|------|------|------|
| **Scratches** | Scratch Amount | 0-100 | % | 划痕数量 |
| | Scratch Length | 0-100 | % | 划痕长度 |
| | Scratch Width | 0-100 | % | 划痕宽度 |
| | Scratch Opacity | 0-100 | % | 划痕不透明度 |
| | Scratch Speed | -10-10 | - | 划痕移动速度 |
| **Dust** | Dust Amount | 0-100 | % | 灰尘数量 |
| | Dust Size | 0-100 | % | 灰尘大小 |
| | Dust Opacity | 0-100 | % | 灰尘不透明度 |
| **Hair** | Hair Amount | 0-100 | % | 毛发数量 |
| | Hair Length | 0-100 | % | 毛发长度 |
| **Flicker** | Flicker Amount | 0-100 | % | 闪烁幅度 |
| | Flicker Speed | 0-20 | Hz | 闪烁频率 |
| **Grain** | Grain Amount | 0-100 | % | 颗粒数量 |
| | Grain Size | 0-100 | % | 颗粒大小 |
| **Color** | Color Bleaching | 0-100 | % | 颜色漂白/褪色 |
| | Yellowing | 0-100 | % | 黄化（老胶片感） |
| | Contrast Loss | 0-100 | % | 对比度损失 |
| **Warp** | Warp Amount | 0-100 | % | 胶片翘曲量 |
| | Warp Speed | 0-10 | - | 翘曲速度 |
| **Gate Hair** | Gate Hair Amount | 0-100 | % | 片门毛发（边缘毛发） |

---

## 八、BCC Stabilizer / Match Move — 稳定与跟踪

### BCC Stabilizer（画面稳定）

| 参数 | 范围 | 说明 |
|------|------|------|
| Stabilize Mode | Position / Scale / Rotation / All | 稳定模式 |
| Smoothness | 0-10 | 平滑度 |
| Accuracy | Low/Medium/High | 跟踪精度 |
| Crop / No Crop | - | 是否裁剪边缘 |
| Edge Fill | Transparent/Repeat/Mirror | 边缘填充方式 |

### BCC Match Move（运动匹配）

| 参数 | 范围 | 说明 |
|------|------|------|
| Tracker 1-4 | - | 4个跟踪点 |
| - Track Position | On/Off | 跟踪位置 |
| - Track Scale | On/Off | 跟踪缩放 |
| - Track Rotation | On/Off | 跟踪旋转 |
| Apply To | Layer / Effect Point | 应用目标 |
| Offset X/Y | - | 偏移量 |
| Scale | 0-5 | 缩放补偿 |
| Rotation Offset | -360-360 | ° | 旋转偏移 |

---

## 九、BCC 转场效果 (BCC Transitions)

### 转场分类

| 类别 | 效果示例 | 说明 |
|------|---------|------|
| **Wipe** | Linear Wipe, Radial Wipe, V Wipe, Star Wipe | 擦除类 |
| **Dissolve** | Cross Dissolve, Add Dissolve, Glow Dissolve | 溶解类 |
| **Blur** | Blur Dissolve, Directional Blur Wipe | 模糊类 |
| **3D** | Cube Spin, Door, Flip, Page Turn, Sphere | 3D转场 |
| **Zoom** | Zoom, Zoom Blur, Multisample Zoom | 缩放类 |
| **Glow** | Glow Dissolve, Light Wipe | 发光类 |
| **Distort** | Ripple, Wave, Bend, Twister | 扭曲类 |
| **Slide** | Slide, Push, Split | 滑动类 |
| **Stretch** | Stretch, Stretch Dissolve | 拉伸类 |
| **Iris** | Iris Round, Iris Star, Iris Diamond | 虹膜/光圈类 |
| **Grid** | Grid Wipe, Checker Wipe | 网格类 |
| **Fun** | Pinwheel, Heart, Swirl | 趣味类 |

### 转场通用参数

| 参数 | 范围 | 说明 |
|------|------|------|
| Transition Completion | 0-100 | % | 转场完成度 |
| Border Width | 0-100 | % | 边框宽度 |
| Border Color | RGB | - | 边框颜色 |
| Border Softness | 0-100 | % | 边框柔化 |
| Feather | 0-100 | % | 边缘羽化 |
| Reverse | On/Off | - | 反向转场 |
| Direction | 0-360 | ° | 转场方向 |

---

## 十、BCC Color Grade — 调色

> 三级调色工具（阴影/中间调/高光）。

| 参数组 | 参数 | 范围 | 说明 |
|--------|------|------|------|
| **Overall** | Gain | 0-2 | - | 整体增益 |
| | Lift | -0.5-0.5 | - | 暗部提升 |
| | Gamma | 0.1-10 | - | Gamma |
| | Saturation | 0-2 | - | 整体饱和度 |
| **Shadows** | Shadow Red/Green/Blue | -1-1 | - | 阴影三色调整 |
| | Shadow Saturation | 0-2 | - | 阴影饱和度 |
| **Midtones** | Mid Red/Green/Blue | -1-1 | - | 中间调三色调整 |
| | Mid Saturation | 0-2 | - | 中间调饱和度 |
| | Midtone Range | 0-1 | - | 中间调范围 |
| **Highlights** | High Red/Green/Blue | -1-1 | - | 高光三色调整 |
| | High Saturation | 0-2 | - | 高光饱和度 |
| **Temperature** | Temperature | -100-100 | - | 色温 |
| | Tint | -100-100 | - | 色调 |
| **Contrast** | Contrast | -100-100 | % | 对比度 |
| | Pivot | 0-1 | - | 对比度中心 |
| **Vignette** | Vignette Amount | 0-100 | % | 暗角强度 |
| | Vignette Size | 0-100 | % | 暗角大小 |
| | Vignette Softness | 0-100 | % | 暗角柔化 |

---

## 十一、BCC 3D Extruded Text / EPS — 三维挤压文字

> 从文字或 EPS 路径创建 3D 挤压物体。

| 参数组 | 参数 | 范围 | 说明 |
|--------|------|------|------|
| **Source** | Source Text Layer | - | - | 文字图层（可选） |
| | Text | - | - | 直接输入文字 |
| | Font | - | - | 字体 |
| | Size | 0-1000 | px | 文字大小 |
| **Extrusion** | Extrusion Depth | 0-1000 | px | 挤压深度 |
| | Bevel Style | None/Flat/Round/Chamfer | - | 斜角样式 |
| | Bevel Depth | 0-100 | px | 斜角深度 |
| | Bevel Width | 0-100 | px | 斜角宽度 |
| **Transform** | Position X/Y/Z | - | px | 3D位置 |
| | Rotation X/Y/Z | 0-360 | ° | 3D旋转 |
| | Scale | 0-10 | - | 缩放 |
| **Material** | Front Color / Back Color / Side Color | RGB | - | 各面颜色 |
| | Opacity | 0-100 | % | 不透明度 |
| | Shininess | 0-100 | % | 光泽度 |
| | Specular | 0-100 | % | 高光强度 |
| **Lighting** | Light 1-3 | - | - | 3盏灯光 |
| | - Light Type | Point/Directional/Ambient | - | 灯光类型 |
| | - Light Intensity | 0-10 | - | 灯光强度 |
| | - Light Color | RGB | - | 灯光颜色 |
| | - Light Position X/Y/Z | - | px | 灯光位置 |
| **Camera** | Camera | AE Camera/BCC Camera | - | 摄像机 |

---

## 十二、BCC 其他重要效果速查

| 效果 | 功能 | 核心参数 |
|------|------|---------|
| BCC Unsharp Mask | 锐化 | Amount, Radius, Threshold |
| BCC Lens Blur | 镜头模糊 | Blur Size, Iris Shape, Highlights |
| BCC Motion Blur | 运动模糊 | Blur Angle, Blur Length |
| BCC Directional Blur | 方向模糊 | Direction, Length |
| BCC Radial Blur | 放射模糊 | Amount, Center, Type |
| BCC Gaussian Blur | 高斯模糊 | Blur Radius |
| BCC Displacement Map | 置换贴图 | Map Layer, Amount X/Y |
| BCC Turbulence | 湍流扭曲 | Amount, Frequency, Speed |
| BCC Ripple | 波纹 | Amplitude, Frequency, Phase |
| BCC Kaleidoscope | 万花筒 | Size, Sides, Rotation |
| BCC Polar | 极坐标 | Type, Amount |
| BCC Bulge | 凸出/凹进 | Amount, Radius, Center |
| BCC Mirror | 镜像 | Reflection Center, Angle |
| BCC Cylinder | 圆柱弯曲 | Amount, Axis |
| BCC Sphere | 球面化 | Amount, Radius, Center |
| BCC Page Turn | 翻页 | Fold Position, Radius, Light |
| BCC Cartoon | 卡通化 | Edge Amount, Color Reduction |
| BCC Mosaic | 马赛克 | Block Size, Pattern |
| BCC Emboss | 浮雕 | Direction, Relief, Smoothness |
| BCC Painterly | 绘画风格 | Brush Size, Stroke Length, Paint Amount |
| BCC Pencil Sketch | 铅笔画 | Line Amount, Line Thickness, Shading |
| BCC Charcoal | 炭笔画 | Charcoal Amount, Detail, Roughness |
| BCC Fractal Noise | 分形噪波 | Amplitude, Scale, Complexity, Evolution |
| BCC Clouds | 云层 | Cloud Color, Sky Color, Speed, Coverage |
| BCC Brushed Metal | 拉丝金属 | Direction, Roughness, Highlight |
| BCC Vignette | 暗角 | Amount, Size, Softness, Center |
| BCC Film Grain | 胶片颗粒 | Amount, Size, Color |
| BCC Noise Reduction | 降噪 | Threshold, Amount, Temporal |
| BCC Dust and Scratches | 去尘划痕 | Radius, Threshold |
| BCC Flicker Fixer | 去闪烁 | Smoothing, Temporal |
| BCC Beat Reactor | 节拍反应器 | Audio Layer, Frequency, Output Value |
| BCC Jitter | 抖动 | Amount, Frequency, Speed |
| BCC Trails | 拖尾/重影 | Number of Trails, Decay, Delay |
| BCC Looper | 循环 | Loop In/Out Point, Crossfade |
| BCC Posterize Time | 抽帧 | Frame Rate |
| BCC Alpha Process | Alpha通道处理 | Invert, Levels, Blur, Choke |
| BCC Matte Choker | 遮罩抑制 | Choke, Gray Level |
| BCC Light Wrap | 光包裹 | Wrap Amount, Wrap Softness, Wrap Color |

---

## 十三、深度原理：核心算法与数学模型 🔬

### 13.1 Primatte Studio 抠像算法原理

#### 多面体色彩空间分割

Primatte 的核心算法是在 3D RGB 色彩空间中用多面体（多面体外壳）分割前景和背景：

```
RGB 色彩空间中的三类区域：
  1. 全背景区（Full Background） → 输出Alpha=0
  2. 全前景区（Full Foreground） → 输出Alpha=1
  3. 过渡区（Transitional/Semi-transparent） → 0<Alpha<1

多面体结构：
  - 内多面体 = 100%前景（不透明）
  - 外多面体 = 0%前景（完全透明）
  - 内外之间 = 渐变过渡（半透明）
```

#### 多面体几何构造

```
初始状态：
  在RGB立方体内，背景色点周围生成一个小的多面体（如12面体/20面体）
  顶点方向 = 从背景色指向各原色/补色方向

扩展/收缩操作：
  - 选择操作面 → 沿法线方向移动
  - 平滑操作 → 调整相邻面，保持形状平滑
  - 微调操作 → 单个顶点调整

这就是 Primatte 界面中"大/中/小选区"工具的几何含义
```

#### 溢出抑制（Spill Suppression）

```
绿幕溢出的成因：
  绿色光线反射到前景物体边缘
  导致前景边缘偏绿

溢出抑制算法：
  方法1：降低绿色通道（简单但影响饱和度）
  方法2：向反方向（品红）偏移（保留更多细节）
  方法3：基于亮度的自适应抑制（Primatte采用）

数学表达：
  G_suppressed = G - spill_amount × (G - neutral_gray)
  或用颜色矩阵做去溢出变换
```

#### Alpha 边缘优化（Matte Choker / Alpha Cleanup）

```
腐蚀（Erode / Choke）：
  收缩Alpha边缘，去除边缘绿边
  数学形态学中的"腐蚀"操作

膨胀（Dilate）：
  扩展Alpha边缘，填充空洞
  数学形态学中的"膨胀"操作

开运算 = 先腐蚀后膨胀：
  去除小噪点，平滑边缘

闭运算 = 先膨胀后腐蚀：
  填充小空洞，连接断裂边缘

高斯模糊 + 色阶调整：
  柔化边缘过渡
```

### 13.2 平面跟踪数学（Mocha / Match Move 原理）

#### 四点透视变换（Corner Pin）

```
四个角点定义透视变换：
  源点：(x1,y1), (x2,y2), (x3,y3), (x4,y4)
  目标点：(x1',y1'), (x2',y2'), (x3',y3'), (x4',y4')

单应矩阵（Homography Matrix）H（3×3）：
  [x']   [ h11 h12 h13 ] [x]
  [y'] = [ h21 h22 h23 ] [y]
  [w']   [ h31 h32 h33 ] [1]

  实际坐标：x' = x'/w', y' = y'/w'

8个自由度（h33=1归一化），4对对应点恰好求解
```

#### 平面跟踪的优化目标

```
对于每一帧，找到最佳单应矩阵 H，使得：
  E = Σ |I_t(x,y) - I_{t-1}(H^{-1}(x,y))|² 最小

其中：
  I_t = 当前帧图像
  I_{t-1} = 参考帧图像
  H = 单应变换矩阵
  E = 残差能量（要最小化）

优化方法：
  LK光流 → 高斯牛顿法 → 列文伯格-马夸尔特法
```

#### 运动参数分解

```
平面运动可分解为：
  - 平移（Translation）：X/Y 位移
  - 旋转（Rotation）：平面内旋转
  - 缩放（Scale）：均匀/非均匀缩放
  - 剪切（Shear）：倾斜
  - 透视（Perspective）：近大远小

自由度：
  平移 2 + 旋转 1 + 缩放 2 + 剪切 1 + 透视 2 = 8
  → 与单应矩阵自由度一致
```

### 13.3 3D 挤压几何生成（Extruded Text 原理）

#### 挤压（Extrusion）几何构造

```
从2D轮廓生成3D几何体的步骤：
  1. 输入：闭合2D路径（贝塞尔曲线）
  2. 三角化：将2D形状切成三角形（正面/背面）
  3. 挤压：沿Z轴方向复制顶点生成侧面
  4. 斜角（Bevel）：在边缘处添加过渡几何
```

#### 斜角（Bevel）类型与几何

```
Flat 斜角：
  - 45度斜面
  - 简单且快
  - 几何少

Round 斜角：
  - 圆弧过渡
  - 更平滑真实
  - 分段数越多越平滑

Chamfer 斜角：
  - 倒角（平面斜切）
  - 工业感强
  - 用于机械/科技感文字
```

#### 法线计算与光照

```
顶点法线决定光照效果：
  平面法线 = 两个边向量的叉积
  顶点法线 = 相邻面法线的加权平均

平滑着色（Smooth Shading）：
  顶点法线插值 → 平滑过渡
  斜角处用平滑法线 → 圆润感

平面着色（Flat Shading）：
  整面共用一个法线 → 棱角分明
  机械风格常用
```

### 13.4 图像修复算法（Image Restoration）

#### 降噪算法原理

```
空间域降噪：
  1. 高斯模糊 → 简单但损失细节
  2. 中值滤波 → 去除椒盐噪声
  3. 双边滤波（Bilateral Filter）→ 保边降噪
  4. 非局部均值（Non-Local Means）→ 高级降噪

时间域降噪（Temporal Denoising）：
  利用前后帧信息
  E(x,y,t) = α×I(x,y,t) + (1-α)×E(x,y,t-1)
  α = 学习率/更新率

BCC Noise Reduction 可能采用：
  空间双边滤波 + 时域累计平均
```

#### 划痕/尘点检测与修复

```
检测阶段：
  1. 异常亮度像素检测（与邻域差异大）
  2. 形状分析（线状=划痕，点状=尘点）
  3. 时域一致性检查（只有1帧=划痕，持续=正常内容）

修复阶段（Inpainting 图像修复）：
  方法1：邻域像素插值（简单快速）
  方法2：偏微分方程（PDE）扩散（平滑自然）
  方法3：纹理合成（保持细节）
  方法4：基于样本的修复（最佳匹配块填充）

BCC Dust and Scratches 可能用：
  中值滤波 + 阈值检测 + 插值修复
```

#### 闪烁消除（Flicker Fixer）

```
闪烁成因：
  - 胶片老化
  - 灯光频率不匹配
  - 老视频信号不稳定

算法原理：
  1. 统计每帧平均亮度
  2. 分析亮度波动的频率成分
  3. 滤除高频闪烁（保留缓慢变化）
  4. 对每帧做曝光补偿

时域滤波：
  brightness_smoothed(t) = Σ w(τ) × brightness(t+τ)
  w = 加权窗函数（高斯/矩形）
```

### 13.5 Lens Blur 镜头模糊物理模型

#### 散景（Bokeh）的光学原理

```
镜头模糊 = 积分成像（不是简单的高斯模糊）

对于每个输出像素：
  颜色 = ∫(光圈区域内) 入射光 × 光圈形状 dA

光圈形状（Iris Shape）：
  - 圆形 → 最柔美的散景
  - 多边形（5-8边）→ 真实镜头感
  - 叶片数越多 → 越接近圆形
```

#### 景深计算公式

```
弥散圆直径（Circle of Confusion, CoC）：
  c = A × |d - f| / d × f² / (f² - A×|d-f|)

简化版：
  c ≈ A × |d - focus_dist| / focus_dist² × f / N

其中：
  A = 光圈大小
  d = 物体距离
  f = 焦距
  N = f数（f/A）
  focus_dist = 对焦距离

CoC > 1像素 → 模糊
```

#### Bokeh 高光处理

```
真实镜头中，高光点会呈现光圈形状
而不是高斯模糊的柔和渐变

算法要点：
  1. 对于高亮像素，按光圈形状扩散
  2. 使用"累加+归一化"而非简单平均
  3. 处理 HDR 范围的高光（浮点精度）
```

### 13.6 光包裹（Light Wrap）合成原理

```
Light Wrap 的成因：
  前景物体边缘被背景光照亮
  特别是强背光/逆光场景
  边缘出现半透明的环境光

算法实现：
  1. 提取前景边缘（Alpha边缘）
  2. 背景模糊处理（模拟光线散射）
  3. 用边缘Mask混合背景色到前景
  4. 控制：Wrap Amount = 强度，Wrap Softness = 边缘宽度

数学表达：
  output = foreground + wrap_amount × edge_mask × blurred_background
```

---

## 十四、实验室级质量基准与测试 🧪

### 14.1 抠像质量评估标准

#### 抠像质量量化指标

| 指标 | 计算公式 | 理想值 | 说明 |
|------|---------|--------|------|
| **边缘平滑度** | Alpha边缘梯度变化 | 均匀S型 | 无跳变、无锯齿 |
| **溢出抑制率** | 边缘绿/蓝减少比例 | >90% | 去绿/蓝效果 |
| **前景保留度** | 前景细节保留率 | >95% | 不损失毛发/纹理 |
| **边缘透明度** | 半透明区域准确性 | 接近真实 | 玻璃/烟雾等 |
| **噪点水平** | Alpha通道噪点 | <1% | 干净的Alpha |

#### 抠像难度分级

| 难度 | 场景特征 | 推荐工具 | 处理时间 |
|------|---------|---------|---------|
| 1星 | 纯色背景，光线均匀，简单物体 | Keylight / 线性键控 | 5分钟 |
| 2星 | 一般绿幕，有阴影，边缘清晰 | Primatte / Keylight | 15分钟 |
| 3星 | 毛发/透明物体，光照不均 | Primatte + 精细调整 | 1-2小时 |
| 4星 | 复杂运动，多颜色背景溢出 | 多通道抠像 + Rotoscope | 4-8小时 |
| 5星 | 火焰/烟雾/玻璃，极复杂边缘 | 逐帧手绘 + 多个Mask | 数天 |

### 14.2 3D 文字性能基准

| 参数设置 | 渲染速度（1080p） | 内存占用 | 质量 |
|---------|------------------|---------|------|
| 简单文字，无斜角 | 实时（60fps） | <50MB | - |
| 中等复杂度文字，Round斜角 | 10-20fps | 100MB | 良好 |
| 复杂路径文字，高细分 | 2-5fps | 300MB | 优秀 |
| E3D级别高质量文字 | <1fps | 500MB+ | 电影级 |

---

## 十五、企业级工作流与最佳实践 🏢

### 15.1 抠像工作流标准

```
标准蓝/绿幕抠像流程：
  Step 1: 素材预处理
    - 色彩空间转换（Log→线性/Rec709）
    - 曝光/对比度统一
    - 降噪（如有必要）

  Step 2: 初步键控
    - 用Primatte/Keylight取背景色
    - 生成基础Alpha

  Step 3: Matte优化
    - Matte Choker 收缩边缘
    - Alpha 模糊柔化
    - 去除噪点（Denoise Alpha）
    - 修复问题区域（Rotoscope补充）

  Step 4: 溢出抑制
    - 去除边缘绿/蓝色溢出
    - 保留前景自然色彩
    - Light Wrap 光包裹

  Step 5: 合成整合
    - 与新背景合成
    - 色彩匹配
    - 边缘光影整合
```

### 15.2 跟踪与匹配工作流

```
平面跟踪工作流：
  Step 1: 选择跟踪平面
    - 高对比度、纹理丰富
    - 平面特征明显
    - 无遮挡或遮挡少

  Step 2: 初始跟踪
    - 画好跟踪区域
    - 逐帧向前跟踪
    - 及时修正漂移

  Step 3: 跟踪数据优化
    - 平滑跟踪曲线
    - 手动修正误差帧
    - 多参考点交叉验证

  Step 4: 应用匹配
    - Corner Pin / Match Move
    - 运动模糊匹配
    - 透视匹配
```

### 15.3 性能优化策略

```
L1 预览优化：
  - 降低预览分辨率（1/2, 1/4）
  - 关闭非必要效果
  - 用代理素材

L2 效果级优化：
  - 抠像：先做粗抠预览，精细最后再开
  - 3D文字：预览用低细分
  - 模糊：预览用低Quality
  - 降噪：关闭时域降噪预览

L3 工程级优化：
  - 预合成/预渲染复杂效果
  - 调整层共享效果
  - 智能RAM缓存管理

L4 系统级优化：
  - GPU加速（CUDA/OpenCL）
  - 充足内存 + SSD缓存
  - 多帧渲染最终输出
```

---

## 十六、故障排查手册 🔧

### 16.1 抠像常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| **边缘有绿边** | 溢出抑制不足 / Matte太宽 | 增加Spill Suppression / Choke Matte |
| **前景有半透明区域** | 前景色与背景色太接近 | 调整选区范围 / 用Rotoscope补充 |
| **Alpha有噪点** | 素材噪点多 / 键控太敏感 | Alpha降噪 / 增加阈值柔化 |
| **头发丝丢失** | 键太硬 / 阈值太高 | 降低Clip Rollback / 用精细键控 |
| **运动边缘锯齿** | 素材压缩 artifacts | 先降噪再抠 / 用高质量素材 |
| **玻璃/透明物体难抠** | 半透明区域 | 用不同通道组合 / 多遍抠像 |
| **Primatte 颜色溢出** | 选色区域不对 | 用Clean BG/FG工具重新选取 |

### 16.2 跟踪常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| **跟踪漂移** | 特征点丢失 / 光照变化 | 增加跟踪点 / 手动修正 |
| **透视不准** | 平面不平 / 镜头畸变 | 校正畸变 / 多点约束 |
| **运动模糊不匹配** | 快门角度不同 | 调整运动模糊参数 |
| **遮挡处理难** | 前景遮挡跟踪面 | 分阶段跟踪 / 手动关键帧 |

### 16.3 3D文字常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| **文字有锯齿** | 分辨率太低 / 抗锯齿不足 | 提高分辨率 / 提高抗锯齿 |
| **斜角不自然** | 斜角分段太少 | 增加Bevel Segments |
| **光照不对** | 灯光位置/类型不对 | 调整灯光参数 / 用AE灯光 |
| **渲染慢** | 几何太复杂 / 抗锯齿太高 | 降低细分 / 优化设置 |

---

## 十七、学术与技术参考 📚

### 抠像与合成

1. **Smith, A. R., & Blinn, J. F. (1996). "Blue Screen Matting".** SIGGRAPH
   → 蓝屏/绿屏抠像经典论文

2. **Ruzon, M. A., & Tomasi, C. (2000). "Alpha Estimation in Natural Images".** CVPR
   → 自然图像Alpha估计

3. **Gastal, E. S. L., & Oliveira, M. M. (2010). "Shared Sampling for Real-Time Alpha Matting".**
   → 实时抠像算法

### 运动跟踪

1. **Lucas, B. D., & Kanade, T. (1981). "An Iterative Image Registration Technique".**
   → LK光流法，跟踪算法基础

2. **Baker, S., & Matthews, I. (2004). "Lucas-Kanade 20 Years On: A Unifying Framework".**
   → LK算法的统一框架

3. **Hartley, R., & Zisserman, A. "Multiple View Geometry in Computer Vision".**
   → 多视图几何经典教材

### 图像修复

1. **Bertalmio, M., et al. (2000). "Image Inpainting".** SIGGRAPH
   → 图像修复开创性论文

2. **Buades, A., et al. (2005). "A Non-Local Algorithm for Image Denoising".** CVPR
   → 非局部均值降噪

3. **Rudin, L. I., et al. (1992). "Nonlinear Total Variation Based Noise Removal Algorithms".**
   → TV降噪算法

---

> 相关文档：
> - [[Sapphire蓝宝石插件核心效果详解]]
> - [[AE效果视觉特征库]]
> - [[AE第三方插件与脚本知识库]]
> - [[企业级VFX工作流与质量标准]]
> - [[AE特效学术研究资料汇编]]

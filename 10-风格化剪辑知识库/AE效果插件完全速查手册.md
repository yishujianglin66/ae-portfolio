# AE效果插件完全速查手册

> 版本：AE 2026 | 更新日期：2026年7月
> 适用版本：After Effects CC 2020 - 2026

---

## 一、效果插件使用基础

### 1.1 效果添加方法

| 方法 | 操作步骤 | 适用场景 |
|------|----------|----------|
| 菜单栏添加 | 选中图层 → Effect 菜单 → 选择效果类别 → 选择具体效果 | 精确查找特定效果 |
| 效果面板搜索 | Window → Effects & Presets → 搜索框输入效果名 → 双击或拖拽到图层 | 快速查找已知效果 |
| 右键菜单添加 | 时间轴右键点击图层 → Effect → 选择效果 | 快速访问常用效果 |
| 拖拽添加 | 从效果面板拖拽效果到目标图层上 | 批量添加或直观操作 |
| 快捷键 | 选中图层后，在效果面板搜索并按 Enter | 高效操作 |

### 1.2 效果控制（Effect Controls）面板

**面板功能：**
- 查看和调整所有已添加效果的参数
- 调整效果顺序（拖拽排序）
- 开关效果（fx 图标）
- 重置效果参数
- 保存/应用动画预设

**关键操作：**
- 点击效果名称前的小三角展开/折叠参数
- 按 `fx` 图标临时关闭效果预览
- 右键效果名称可重命名、复制、删除
- 参数前的秒表图标用于添加关键帧动画

### 1.3 效果顺序对最终效果的影响

**重要原则：效果从上到下依次计算，顺序不同结果不同**

| 效果顺序原则 | 说明 | 示例 |
|-------------|------|------|
| 先调色后模糊 | 模糊会柔化颜色过渡 | 适合梦幻、柔焦效果 |
| 先模糊后调色 | 调色基于模糊后的像素 | 颜色更均匀 |
| 先键控后调色 | 对抠像后的画面调色 | 避免边缘色偏 |
| 先变形后调色 | 变形后再调色 | 调色基于变形结果 |
| 先调色后变形 | 调色后再变形 | 颜色保持原始分布 |

**常用效果堆叠顺序（从上到下）：**
1. 键控/遮罩类效果
2. 颜色校正类效果
3. 扭曲/变形类效果
4. 模糊/锐化类效果
5. 风格化/发光类效果
6. 透视/投影类效果

### 1.4 效果开关/复制/保存预设

**效果开关：**
- 单个效果开关：点击 Effect Controls 面板中效果前的 `fx` 图标
- 所有效果开关：图层开关中的 `fx` 列（时间轴面板）
- 快捷键：选中图层按 `E` 展开所有效果

**效果复制：**
- 复制单个效果：右键效果 → Copy
- 复制所有效果：选中图层 → `Ctrl+C` → 选中目标图层 → `Ctrl+V`（Paste）
- 仅粘贴效果：Edit → Paste → 选择 Paste as Effects

**保存预设：**
1. 在 Effect Controls 面板选中一个或多个效果
2. 选择 Animation → Save Animation Preset
3. 命名并保存到预设文件夹
4. 可通过 Effects & Presets 面板随时调用

### 1.5 调整层（Adjustment Layer）批量应用效果

**创建方法：**
- 菜单：Layer → New → Adjustment Layer
- 快捷键：`Ctrl+Alt+Y`
- 右键时间轴空白处 → New → Adjustment Layer

**特点：**
- 调整层本身不显示内容
- 其下方所有图层都会受到调整层效果的影响
- 可以使用蒙版控制效果作用区域
- 调整层顺序影响效果叠加

**使用场景：**
- 统一调色（全片色调统一）
- 整体模糊（景深效果）
- 全局噪波（胶片颗粒）
- 暗角效果
- 色差效果

---

## 二、内置效果分类速查

### 2.1 颜色校正（Color Correction）

#### Brightness & Contrast（亮度与对比度）

| 项目 | 内容 |
|------|------|
| 中文名 | 亮度与对比度 |
| 功能描述 | 调整图像的整体亮度和对比度，是最基础的调色工具 |
| 核心参数 | Brightness（亮度）：-100 ~ 100，默认 0 |
| | Contrast（对比度）：-100 ~ 100，默认 0 |
| | Use Legacy（使用旧版）：勾选后使用旧算法 |
| 典型应用 | 快速调整画面明暗、增加画面对比度、基础曝光校正 |

#### Color Balance（色彩平衡）

| 项目 | 内容 |
|------|------|
| 中文名 | 色彩平衡 |
| 功能描述 | 通过调整阴影、中间调、高光区域的红/绿/蓝通道来改变画面色调 |
| 核心参数 | Shadow Red-Balance（阴影红平衡）：-100 ~ 100，默认 0 |
| | Shadow Green-Balance（阴影绿平衡）：-100 ~ 100，默认 0 |
| | Shadow Blue-Balance（阴影蓝平衡）：-100 ~ 100，默认 0 |
| | Midtone Red-Balance（中间调红平衡）：-100 ~ 100，默认 0 |
| | Midtone Green-Balance（中间调绿平衡）：-100 ~ 100，默认 0 |
| | Midtone Blue-Balance（中间调蓝平衡）：-100 ~ 100，默认 0 |
| | Highlight Red-Balance（高光红平衡）：-100 ~ 100，默认 0 |
| | Highlight Green-Balance（高光绿平衡）：-100 ~ 100，默认 0 |
| | Highlight Blue-Balance（高光蓝平衡）：-100 ~ 100，默认 0 |
| | Preserve Luminosity（保持亮度）：勾选后保持整体亮度不变 |
| 典型应用 | 画面偏色校正、营造冷暖色调氛围、分区域调色 |

#### Hue/Saturation（色相/饱和度）

| 项目 | 内容 |
|------|------|
| 中文名 | 色相/饱和度 |
| 功能描述 | 调整图像的色相、饱和度和明度，可针对单通道调色 |
| 核心参数 | Channel Control（通道控制）：Master / Reds / Yellows / Greens / Cyans / Blues / Magentas |
| | Master Hue（主色相）：-180 ~ 180 度，默认 0 |
| | Master Saturation（主饱和度）：-100 ~ 100，默认 0 |
| | Master Lightness（主亮度）：-100 ~ 100，默认 0 |
| | Channel Range（通道范围）：显示和调整颜色范围 |
| | Colorize（彩色化）：勾选后将图像转为单色 |
| | Colorize Hue（彩色化色相）：0 ~ 360 度，默认 0 |
| | Colorize Saturation（彩色化饱和度）：0 ~ 100，默认 25 |
| | Colorize Lightness（彩色化亮度）：-100 ~ 100，默认 0 |
| 典型应用 | 调整画面饱和度、更换物体颜色、单色效果、创意调色 |

#### Levels（色阶）

| 项目 | 内容 |
|------|------|
| 中文名 | 色阶 |
| 功能描述 | 通过调整阴影、中间调和高光的色阶值来校正图像的色调范围和色彩平衡 |
| 核心参数 | Channels（通道）：RGB / Red / Green / Blue / Alpha |
| | Histogram（直方图）：显示像素分布（只读） |
| | Input Black（输入黑色）：0 ~ 255，默认 0 |
| | Input White（输入白色）：0 ~ 255，默认 255 |
| | Gamma（伽马）：0.01 ~ 10，默认 1.0 |
| | Output Black（输出黑色）：0 ~ 255，默认 0 |
| | Output White（输出白色）：0 ~ 255，默认 255 |
| | Clip To Output Black/White（剪切到输出黑/白） |
| 典型应用 | 曝光校正、对比度调整、定义黑白场、单通道调色 |

#### Curves（曲线）

| 项目 | 内容 |
|------|------|
| 中文名 | 曲线 |
| 功能描述 | 通过调整曲线形状精确控制图像的色调和色彩，是最强大的调色工具之一 |
| 核心参数 | Channel（通道）：RGB / Red / Green / Blue / Alpha |
| | Curves（曲线）：可添加最多14个控制点 |
| | Input（输入）：0 ~ 255 |
| | Output（输出）：0 ~ 255 |
| | Curve Type（曲线类型）：Smooth / Linear |
| 典型应用 | 精细调色、S曲线增加对比度、创意色调效果、胶片质感调色 |

#### Colorama（彩光）

| 项目 | 内容 |
|------|------|
| 中文名 | 彩光 / 彩色光 |
| 功能描述 | 将图像的亮度值映射到自定义的渐变颜色上，创造丰富的色彩效果 |
| 核心参数 | Input Phase（输入相位）：控制颜色映射的起始相位 |
| | Get Phase From（获取相位自）：选择相位来源通道 |
| | Add Phase（添加相位）：添加额外相位 |
| | Output Cycle（输出循环）：自定义颜色渐变 |
| | Use Preset Palette（使用预设调色板）：多种预设可选 |
| | Cycle Repetitions（循环重复）：0 ~ 100，默认 1 |
| | Interpolate（插值）：勾选后颜色平滑过渡 |
| | Pixel Selection（像素选择）：控制哪些像素受影响 |
| | Masking（蒙版）：选择蒙版图层 |
| 典型应用 | 赛博朋克风格、热成像效果、创意色彩映射、霓虹效果 |

#### Photo Filter（照片滤镜）

| 项目 | 内容 |
|------|------|
| 中文名 | 照片滤镜 |
| 功能描述 | 模拟相机镜头前添加彩色滤镜的效果，调整画面整体色调 |
| 核心参数 | Filter（滤镜）：多种预设滤镜（Warming Filter/Cooling Filter 等） |
| | Color（颜色）：自定义滤镜颜色 |
| | Density（密度）：0 ~ 100%，默认 25% |
| | Preserve Luminosity（保持亮度）：勾选后保持亮度不变 |
| 典型应用 | 快速营造暖调/冷调氛围、模拟胶片滤镜、统一画面色调 |

#### Auto Color / Auto Contrast / Auto Levels（自动校正）

| 效果名 | 功能描述 | 核心参数 | 典型应用 |
|--------|----------|----------|----------|
| Auto Color（自动颜色） | 自动校正图像的颜色和对比度 | Temporal Smoothing（时间平滑）：0 ~ 10 秒 | 快速校正偏色、一键调色 |
| Auto Contrast（自动对比度） | 自动调整图像对比度，不改变颜色 | Temporal Smoothing：0 ~ 10 秒 | 快速增强画面对比度 |
| Auto Levels（自动色阶） | 自动调整输入色阶的黑白场 | Temporal Smoothing：0 ~ 10 秒 | 快速曝光校正 |

**共同参数：**
- Temporal Smoothing（时间平滑）：基于前后帧进行平滑校正
- Scene Detect（场景检测）：检测场景切换
- Black Clip/White Clip（黑色/白色剪切）：0 ~ 10%，默认 0.1%
- Snap Neutral Midtones（对齐中性中间调）

#### Channel Mixer（通道混合器）

| 项目 | 内容 |
|------|------|
| 中文名 | 通道混合器 |
| 功能描述 | 通过混合当前颜色通道来修改颜色通道，实现创意调色效果 |
| 核心参数 | Red-Red / Red-Green / Red-Blue：红色通道混合比例，-200 ~ 200%，默认 100/0/0 |
| | Green-Red / Green-Green / Green-Blue：绿色通道混合比例，-200 ~ 200%，默认 0/100/0 |
| | Blue-Red / Blue-Green / Blue-Blue：蓝色通道混合比例，-200 ~ 200%，默认 0/0/100 |
| | Red/Green/Blue-Constant：常数偏移，-200 ~ 200%，默认 0 |
| | Monochrome（单色）：勾选后转为灰度图像 |
| 典型应用 | 高质量黑白转换、创意色调分离、特殊色彩效果、红外模拟 |

#### Tint（染色）

| 项目 | 内容 |
|------|------|
| 中文名 | 染色 |
| 功能描述 | 将图像映射到两种颜色上：黑色像素映射到一种颜色，白色像素映射到另一种颜色 |
| 核心参数 | Map Black To（映射黑色到）：颜色，默认黑色 |
| | Map White To（映射白色到）：颜色，默认白色 |
| | Amount to Tint（染色量）：0 ~ 100%，默认 100% |
| 典型应用 | 双色调效果、复古色调、单色艺术效果、快速调色 |

#### Tritone（三色渐变）

| 项目 | 内容 |
|------|------|
| 中文名 | 三色渐变 / 三色调 |
| 功能描述 | 将图像的阴影、中间调、高光分别映射到三种不同的颜色 |
| 核心参数 | Highlight（高光）：颜色，默认白色 |
| | Midtones（中间调）：颜色，默认 50% 灰色 |
| | Shadows（阴影）：颜色，默认黑色 |
| | Blend With Original（与原始图像混合）：0 ~ 100%，默认 0% |
| 典型应用 | 三色艺术效果、复古电影色调、创意调色、风格化处理 |

#### Leave Color（保留颜色）

| 项目 | 内容 |
|------|------|
| 中文名 | 保留颜色 |
| 功能描述 | 保留图像中指定的颜色，将其他颜色转为灰度 |
| 核心参数 | Color To Leave（要保留的颜色）：选择保留的颜色 |
| | Amount To Decolor（去色量）：0 ~ 100%，默认 100% |
| | Tolerance（容差）：0 ~ 100%，默认 20% |
| | Edge Softness（边缘柔化）：0 ~ 5%，默认 0% |
| | Match colors（匹配颜色）：使用 RGB / 色相 |
| 典型应用 | 突出主体、电影感画面、创意视觉效果、强调特定元素 |

#### Change Color（更改颜色）

| 项目 | 内容 |
|------|------|
| 中文名 | 更改颜色 |
| 功能描述 | 更改图像中指定颜色范围的色相、饱和度和亮度 |
| 核心参数 | View（视图）：Corrected Layer / Color Correction Mask |
| | Hue Transform（色相变换）：-180 ~ 180 度，默认 0 |
| | Lightness Transform（亮度变换）：-100 ~ 100%，默认 0 |
| | Saturation Transform（饱和度变换）：-100 ~ 100%，默认 0 |
| | Color To Change（要更改的颜色）：选择目标颜色 |
| | Matching Tolerance（匹配容差）：0 ~ 100%，默认 30% |
| | Matching Softness（匹配柔化）：0 ~ 100%，默认 0% |
| | Match Colors（匹配颜色）：RGB / Hue / Chroma |
| 典型应用 | 更换物体颜色、调整局部颜色、创意调色 |

#### Equalize（均衡）

| 项目 | 内容 |
|------|------|
| 中文名 | 均衡 |
| 功能描述 | 重新分布图像的亮度值，使其更均匀地分布整个亮度范围 |
| 核心参数 | Equalize（均衡方式）：RGB / Brightness / Photoshop Style |
| | Amount to Equalize（均衡量）：0 ~ 100%，默认 100% |
| 典型应用 | 增强暗部细节、调整曝光不均、增强对比度 |

#### Gamma/Pedestal/Gain（伽马/基色/增益）

| 项目 | 内容 |
|------|------|
| 中文名 | 伽马/基色/增益 |
| 功能描述 | 独立控制每个通道的伽马、基色（黑电平）和增益（白电平） |
| 核心参数 | Black Stretch（黑色拉伸）：0 ~ 1，默认 0 |
| | Red/Green/Blue Gamma：0 ~ 5，默认 1 |
| | Red/Green/Blue Pedestal：-1 ~ 1，默认 0 |
| | Red/Green/Blue Gain：0 ~ 5，默认 1 |
| 典型应用 | 精确色彩校正、通道级调整、专业调色 |

---

### 2.2 模糊与锐化（Blur & Sharpen）

#### Fast Box Blur（快速方框模糊）

| 项目 | 内容 |
|------|------|
| 中文名 | 快速方框模糊 |
| 功能描述 | 高性能的方框模糊效果，渲染速度快，可分别控制水平和垂直模糊 |
| 核心参数 | Blurriness（模糊度）：0 ~ 1000+，默认 0 |
| | Blur Dimensions（模糊方向）：Horizontal and Vertical / Horizontal / Vertical |
| | Repeat Edge Pixels（重复边缘像素）：勾选后边缘更清晰 |
| | Blur Radius（模糊半径）：取决于模糊度 |
| 典型应用 | 快速模糊背景、运动模糊模拟、性能优化、景深效果 |

#### Gaussian Blur（高斯模糊）

| 项目 | 内容 |
|------|------|
| 中文名 | 高斯模糊 |
| 功能描述 | 经典的高斯模糊效果，产生平滑自然的模糊效果 |
| 核心参数 | Blurriness（模糊度）：0 ~ 1000+，默认 0 |
| | Blur Dimensions（模糊方向）：Horizontal and Vertical / Horizontal / Vertical |
| | Repeat Edge Pixels（重复边缘像素）：勾选后边缘不变暗 |
| 典型应用 | 柔化图像、景深效果、发光效果配合、减少噪点 |

#### Radial Blur（径向模糊）

| 项目 | 内容 |
|------|------|
| 中文名 | 径向模糊 |
| 功能描述 | 产生旋转或缩放式的径向模糊效果 |
| 核心参数 | Amount（数量）：0 ~ 100，默认 5 |
| | Center（中心）：模糊中心点坐标 |
| | Type（类型）：Spin（旋转）/ Zoom（缩放） |
| | Antialiasing（消除锯齿）：Low / High |
| 典型应用 | 速度感效果、旋转动感、爆炸中心效果、镜头变焦效果 |

#### Lens Blur（镜头模糊）

| 项目 | 内容 |
|------|------|
| 中文名 | 镜头模糊 |
| 功能描述 | 模拟真实相机镜头的虚化效果，支持虹膜形状、高光等高级控制 |
| 核心参数 | Blur Radius（模糊半径）：0 ~ 100，默认 0 |
| | Iris Shape（虹膜形状）：六边形/圆形/自定义等 |
| | Iris Blade Count（叶片数）：5 ~ 12，默认 6 |
| | Iris Blade Curvature（叶片曲率）：0 ~ 100%，默认 0% |
| | Iris Rotation（旋转）：0 ~ 360 度，默认 0 |
| | Depth Map Layers（深度图层）：可选深度图控制模糊 |
| | Specular Highlight（镜面高光）：控制高光表现 |
| | Threshold（阈值）：0 ~ 255，默认 255 |
| | Brightness（亮度）：0 ~ 200%，默认 100% |
| 典型应用 | 真实景深效果、背景虚化、散景效果、模拟大光圈镜头 |

#### Motion Tile（运动平铺）

| 项目 | 内容 |
|------|------|
| 中文名 | 运动平铺 |
| 功能描述 | 复制图像并以网格方式平铺，可用于创建图案或运动模糊效果 |
| 核心参数 | Tile Center（平铺中心）：中心点坐标 |
| | Tile Width/Height（平铺宽度/高度）：0 ~ 100%，默认 100% |
| | Output Width/Height（输出宽度/高度）：0 ~ 1000%，默认 100% |
| | Mirror Edges（镜像边缘）：勾选后边缘镜像 |
| | Phase（相位）：控制平铺偏移 |
| | Horizontal Phase（水平相位）：控制水平偏移 |
| 典型应用 | 动态背景、纹理平铺、万花筒效果、重复图案 |

#### Bilateral Blur（双边模糊）

| 项目 | 内容 |
|------|------|
| 中文名 | 双边模糊 |
| 功能描述 | 智能模糊效果，在模糊的同时保留边缘细节 |
| 核心参数 | Radius（半径）：0 ~ 50，默认 5 |
| | Threshold（阈值）：0 ~ 100，默认 20 |
| | Colorize（彩色化）：勾选后保持颜色信息 |
| 典型应用 | 人像磨皮、减少噪点、柔化皮肤、保留边缘的模糊 |

#### Sharpen（锐化）

| 项目 | 内容 |
|------|------|
| 中文名 | 锐化 |
| 功能描述 | 通过增加相邻像素的对比度来锐化图像 |
| 核心参数 | Sharpen Amount（锐化量）：0 ~ 400%，默认 0% |
| 典型应用 | 增强画面清晰度、修复轻微模糊、强调细节 |

#### Unsharp Mask（非锐化蒙版）

| 项目 | 内容 |
|------|------|
| 中文名 | 非锐化蒙版 / USM锐化 |
| 功能描述 | 专业的锐化工具，通过查找边缘并增加对比度来锐化 |
| 核心参数 | Amount（数量）：0 ~ 500%，默认 50% |
| | Radius（半径）：0 ~ 200，默认 1.0 |
| | Threshold（阈值）：0 ~ 255，默认 0 |
| 典型应用 | 专业锐化、增强边缘细节、照片清晰度提升、视频锐化 |

#### CC Radial Fast Blur

| 项目 | 内容 |
|------|------|
| 中文名 | CC快速径向模糊 |
| 功能描述 | 高性能的径向模糊，比内置径向模糊速度更快 |
| 核心参数 | Amount（数量）：0 ~ 200，默认 10 |
| | Center（中心）：中心点坐标 |
| | Zoom（缩放）：Brightest / Darkest / Center / Standard |
| | Method（方法）：Fastest / Prefer Quality |
| 典型应用 | 速度线效果、爆炸冲击、zoom 运动效果、快速径向模糊 |

#### CC Vector Blur

| 项目 | 内容 |
|------|------|
| 中文名 | CC矢量模糊 |
| 功能描述 | 基于参考图层的方向进行方向性模糊 |
| 核心参数 | Type（类型）：Directional / Radial / Fisheye / Refraction / Flow / Mapper |
| | Amount（数量）：0 ~ 200，默认 10 |
| | Angle（角度）：0 ~ 360 度，默认 0 |
| | Vector Map（矢量图）：参考图层 |
| | Softness（柔化）：0 ~ 50，默认 0 |
| 典型应用 | 动态模糊、流动效果、能量效果、创意模糊 |

---

### 2.3 生成（Generate）

#### 4-Color Gradient（四色渐变）

| 项目 | 内容 |
|------|------|
| 中文名 | 四色渐变 |
| 功能描述 | 创建四角不同颜色的渐变效果 |
| 核心参数 | Position 1/2/3/4：四个角的位置 |
| | Color 1/2/3/4：四个角的颜色 |
| | Blend（混合）：0 ~ 100，默认 30 |
| | Jitter（抖动）：0 ~ 100，默认 0 |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| | Blending Mode（混合模式）：与原图层的混合模式 |
| 典型应用 | 彩色渐变背景、氛围光效、彩色叠加、创意背景 |

#### Ramp（渐变）

| 项目 | 内容 |
|------|------|
| 中文名 | 渐变 |
| 功能描述 | 创建线性或径向渐变效果 |
| 核心参数 | Start of Ramp（渐变起点）：起始位置 |
| | Start Color（起始颜色）：起始颜色 |
| | End of Ramp（渐变终点）：结束位置 |
| | End Color（结束颜色）：结束颜色 |
| | Ramp Shape（渐变形状）：Linear Ramp（线性）/ Radial Ramp（径向） |
| | Ramp Scatter（渐变扩散）：0 ~ 200，默认 0 |
| | Blending With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 渐变背景、天空模拟、蒙版过渡、光效叠加 |

#### Checkerboard（棋盘格）

| 项目 | 内容 |
|------|------|
| 中文名 | 棋盘格 |
| 功能描述 | 创建黑白相间的棋盘格图案 |
| 核心参数 | Anchor（锚点）：棋盘格起始位置 |
| | Size From（大小来源）：Corner Point / Width Slider / Width & Height Sliders |
| | Corner（角点）：角落位置 |
| | Width/Height（宽度/高度）：格子大小 |
| | Feather（羽化）：0 ~ 100，默认 0 |
| | Color 1/2：两种颜色 |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| | Blending Mode（混合模式） |
| 典型应用 | 透明背景标识、纹理背景、图案素材、检测变形 |

#### Circle（圆形）

| 项目 | 内容 |
|------|------|
| 中文名 | 圆形 |
| 功能描述 | 创建实心或空心圆形 |
| 核心参数 | Center（中心）：圆心位置 |
| | Radius（半径）：0 ~ 2000+，默认 100 |
| | Edge（边缘）：None / Edge Radius / Edge Thickness / Edge Feather |
| | Feather（羽化）：内外边缘羽化 |
| | Invert Circle（反转圆形） |
| | Color（颜色）：填充颜色 |
| | Opacity（不透明度） |
| | Blending Mode（混合模式） |
| 典型应用 | 圆形元素、光环、蒙版、指示圈、聚光灯效果 |

#### Ellipse（椭圆）

| 项目 | 内容 |
|------|------|
| 中文名 | 椭圆 |
| 功能描述 | 创建椭圆形状，支持厚度和柔化 |
| 核心参数 | Position（位置）：中心位置 |
| | Width/Height（宽度/高度）：椭圆尺寸 |
| | Thickness（厚度）：0 ~ 1000，默认 5 |
| | Softness（柔化）：0 ~ 100，默认 0 |
| | Inside/Outside Color（内/外颜色） |
| 典型应用 | 椭圆边框、环形元素、装饰图形 |

#### Fill（填充）

| 项目 | 内容 |
|------|------|
| 中文名 | 填充 |
| 功能描述 | 为图层或蒙版区域填充颜色 |
| 核心参数 | Fill Mask（填充蒙版）：选择蒙版 |
| | Color（颜色）：填充颜色 |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| 典型应用 | 纯色填充、蒙版填充、颜色覆盖 |

#### Stroke（描边）

| 项目 | 内容 |
|------|------|
| 中文名 | 描边 |
| 功能描述 | 为蒙版或路径创建描边效果，可制作动画 |
| 核心参数 | Path（路径）：选择蒙版/路径 |
| | Color（颜色）：描边颜色 |
| | Brush Size（画笔大小）：0 ~ 500，默认 2 |
| | Brush Hardness（画笔硬度）：0 ~ 100%，默认 100% |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| | Start/End（起点/终点）：0 ~ 100%，默认 0/100 |
| | Paint Style（绘制风格）：On Original Image / On Transparent / Reveal Original Image |
| 典型应用 | 路径动画、描边文字、勾勒轮廓、生长动画 |

#### Write-on（书写）

| 项目 | 内容 |
|------|------|
| 中文名 | 书写 |
| 功能描述 | 创建动态的书写或绘画效果，画笔位置可动画 |
| 核心参数 | Brush Position（画笔位置）：画笔位置（可动画） |
| | Color（颜色）：画笔颜色 |
| | Brush Size（画笔大小）：0 ~ 500，默认 5 |
| | Brush Hardness（画笔硬度）：0 ~ 100%，默认 50% |
| | Brush Opacity（画笔不透明度）：0 ~ 100%，默认 100% |
| | Stroke Length（描边长度）：0 ~ 300，默认 0（无限） |
| | Brush Spacing（画笔间距）：0 ~ 100%，默认 25% |
| | Paint Time Properties（绘制时间属性）：控制颜色/大小随时间变化 |
| 典型应用 | 手写文字、绘画动画、路径描绘、特效线条 |

#### Vegas（勾画）

| 项目 | 内容 |
|------|------|
| 中文名 | 勾画 / 维加斯 |
| 功能描述 | 在图像边缘或蒙版路径周围创建流动的光效线条，类似霓虹灯效果 |
| 核心参数 | Stroke（描边）：Image Contours / Mask/Path |
| | Segments（段数）：1 ~ 64，默认 1 |
| | Length（长度）：0.001 ~ 1.0，默认 0.5 |
| | Segment Distribution（段分布）：Bunches / Even |
| | Rotation（旋转）：控制光效流动 |
| | Random Phase（随机相位） |
| | Color（颜色）：光效颜色 |
| | Width（宽度）：线条宽度 |
| | Hardness（硬度）：边缘硬度 |
| | Start Opacity / Mid-point Opacity / End Opacity |
| 典型应用 | 霓虹灯效果、能量边缘、光效流动、科技感线条 |

#### Grid（网格）

| 项目 | 内容 |
|------|------|
| 中文名 | 网格 |
| 功能描述 | 创建网格图案 |
| 核心参数 | Anchor（锚点）：网格起始点 |
| | Size From（大小来源）：Corner Point / Width Slider / Width & Height Sliders |
| | Corner（角点） |
| | Width/Height（宽度/高度）：网格大小 |
| | Border（边框）：线宽 |
| | Feather（羽化）：边缘羽化 |
| | Color（颜色）：网格颜色 |
| | Invert Grid（反转网格） |
| | Opacity（不透明度） |
| | Blending Mode（混合模式） |
| 典型应用 | 网格背景、参考线、透视网格、纹理图案 |

#### Lens Flare（镜头光晕）

| 项目 | 内容 |
|------|------|
| 中文名 | 镜头光晕 |
| 功能描述 | 模拟相机镜头产生的光晕和光斑效果 |
| 核心参数 | Flare Center（光晕中心）：光晕位置 |
| | Flare Brightness（光晕亮度）：0 ~ 300%，默认 100% |
| | Lens Type（镜头类型）：50-300mm Zoom / 35mm Prime / 105mm Prime |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 太阳光晕、灯光效果、氛围营造、镜头感 |

#### Lightning（闪电）

| 项目 | 内容 |
|------|------|
| 中文名 | 闪电 |
| 功能描述 | 创建逼真的闪电效果，可动画 |
| 核心参数 | Start Point / End Point：起止点 |
| | Segments（段数）：3 ~ 500，默认 15 |
| | Amplitude（振幅）：0 ~ 2000，默认 100 |
| | Detail Level（细节级别）：0 ~ 10，默认 3 |
| | Detail Amplitude（细节振幅）：0 ~ 100，默认 40 |
| | Branching（分支）：0 ~ 10，默认 3 |
| | Rebranching（再分支）：0 ~ 10，默认 3 |
| | Branch Angle（分支角度）：0 ~ 90 度，默认 45 |
| | Branch Segments（分支段数）：1 ~ 30，默认 3 |
| | Speed（速度）：0 ~ 100，默认 5 |
| | Core Color / Glow Color：核心/光晕颜色 |
| 典型应用 | 闪电特效、电流效果、能量冲击、科幻特效 |

#### Audio Spectrum（音频频谱）

| 项目 | 内容 |
|------|------|
| 中文名 | 音频频谱 |
| 功能描述 | 将音频的频率以频谱柱状图或波形形式可视化 |
| 核心参数 | Audio Layer（音频图层）：选择音频图层 |
| | Start Point / End Point：频谱位置 |
| | Path（路径）：可选路径显示 |
| | Use Polar Path（使用极坐标路径） |
| | Frequency Bands（频段数）：1 ~ 1024，默认 64 |
| | Maximum Height（最大高度）：0 ~ 4000，默认 500 |
| | Audio Duration（音频持续时间）：0 ~ 60 秒，默认 0.05 |
| | Audio Offset（音频偏移）：-10 ~ 10 秒，默认 0 |
| | Thickness（厚度）：0 ~ 100，默认 1 |
| | Softness（柔化）：0 ~ 100%，默认 50% |
| | Inside/Outside Color：内/外颜色 |
| | Hue Interpolation（色相插值） |
| 典型应用 | 音乐可视化、音频反应动画、MV效果、DJ背景 |

#### Audio Waveform（音频波形）

| 项目 | 内容 |
|------|------|
| 中文名 | 音频波形 |
| 功能描述 | 以波形图的方式显示音频振幅 |
| 核心参数 | Audio Layer（音频图层）：选择音频图层 |
| | Start Point / End Point：波形位置 |
| | Path（路径）：可选路径 |
| | Maximum Height（最大高度）：0 ~ 4000，默认 100 |
| | Audio Duration（音频持续时间）：0 ~ 60 秒，默认 5 |
| | Audio Offset（音频偏移）：-10 ~ 10 秒，默认 0 |
| | Displayed Samples（显示采样）：1 ~ 10000，默认 256 |
| | Thickness（厚度）：0 ~ 100，默认 1 |
| | Softness（柔化）：0 ~ 100%，默认 0% |
| | Inside/Outside Color：内/外颜色 |
| | Waveform Options（波形选项）：Mono / Stereo / Digital |
| 典型应用 | 音频可视化、字幕波形、播客视频、音乐节奏显示 |

---

### 2.4 扭曲（Distort）

#### Mesh Warp（网格变形）

| 项目 | 内容 |
|------|------|
| 中文名 | 网格变形 |
| 功能描述 | 通过可调节的网格控制点来扭曲图像 |
| 核心参数 | Rows（行数）：1 ~ 31，默认 3 |
| | Columns（列数）：1 ~ 31，默认 3 |
| | Quality（品质）：0 ~ 100，默认 10 |
| | Grid（网格）：显示网格 |
| | Deformation Grid（变形网格）：显示变形网格 |
| 典型应用 | 面部变形、图像局部调整、创意扭曲、布料模拟 |

#### Bezier Warp（贝塞尔曲线变形）

| 项目 | 内容 |
|------|------|
| 中文名 | 贝塞尔曲线变形 |
| 功能描述 | 通过四条贝塞尔曲线控制图像四个边的形状 |
| 核心参数 | Top Left / Top Right / Bottom Left / Bottom Right：四个角点 |
| | Top Left/Right Tangent：上边切线控制点 |
| | Bottom Left/Right Tangent：下边切线控制点 |
| | Left Top/Bottom Tangent：左边切线控制点 |
| | Right Top/Bottom Tangent：右边切线控制点 |
| | Quality（品质）：0 ~ 100，默认 10 |
| 典型应用 | 图像包裹变形、曲面贴图、纸张弯曲效果 |

#### Bulge（膨胀）

| 项目 | 内容 |
|------|------|
| 中文名 | 膨胀 |
| 功能描述 | 使图像中心区域向外凸起或向内凹陷 |
| 核心参数 | Horizontal/Vertical Radius（水平/垂直半径）：0 ~ 500，默认 200 |
| | Bulge Center（膨胀中心）：中心位置 |
| | Bulge Height（膨胀高度）：-5 ~ 5，默认 1.0 |
| | Taper Radius（锥形半径）：0 ~ 500，默认 0 |
| | Antialiasing（消除锯齿）：Low / Medium / High |
| | Pin All Edges（固定所有边缘） |
| 典型应用 | 放大镜效果、人物脸部变形、搞笑效果、球面化局部 |

#### Corner Pin（边角定位）

| 项目 | 内容 |
|------|------|
| 中文名 | 边角定位 |
| 功能描述 | 通过移动图像的四个角来实现透视变形 |
| 核心参数 | Upper Left / Upper Right / Lower Left / Lower Right：四个角点位置 |
| 典型应用 | 屏幕替换、海报贴图、透视匹配、画面变形 |

#### Displacement Map（置换图）

| 项目 | 内容 |
|------|------|
| 中文名 | 置换图 |
| 功能描述 | 使用参考图层的亮度值来扭曲当前图像 |
| 核心参数 | Displacement Map Layer（置换图层）：参考图层 |
| | Use For Horizontal/Vertical Displacement：水平/垂直置换通道 |
| | Max Horizontal/Vertical Displacement：最大水平/垂直置换量 |
| | Displacement Map Behavior（置换图行为）：居中 / 拉伸适配 / 平铺 |
| | Edge Behavior（边缘行为）：重复边缘像素 / 包裹 |
| | Expand Output（扩展输出） |
| 典型应用 | 扭曲特效、水面反射、热浪效果、玻璃折射 |

#### Magnify（放大）

| 项目 | 内容 |
|------|------|
| 中文名 | 放大 |
| 功能描述 | 放大图像的某个区域，模拟放大镜效果 |
| 核心参数 | Shape（形状）：Circle / Square |
| | Center（中心）：放大区域中心 |
| | Magnification（放大倍数）：0 ~ 2000%，默认 200% |
| | Size（大小）：0 ~ 2000，默认 100 |
| | Feather（羽化）：0 ~ 200，默认 0 |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| | Scaling（缩放）：Standard / Soft |
| | Blend Mode（混合模式） |
| 典型应用 | 放大镜效果、细节强调、产品展示、教学演示 |

#### Mirror（镜像）

| 项目 | 内容 |
|------|------|
| 中文名 | 镜像 |
| 功能描述 | 沿指定轴反射图像的一侧到另一侧 |
| 核心参数 | Reflection Center（反射中心）：反射轴位置 |
| | Reflection Angle（反射角度）：0 ~ 360 度，默认 0 |
| 典型应用 | 对称效果、万花筒、水面倒影、镜像构图 |

#### Offset（偏移）

| 项目 | 内容 |
|------|------|
| 中文名 | 偏移 |
| 功能描述 | 移动图像位置，移出画面的部分从对面重新进入 |
| 核心参数 | Shift Center To（移动中心到）：偏移位置 |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 无缝滚动背景、纹理动画、循环背景、故障效果 |

#### Optics Compensation（光学补偿）

| 项目 | 内容 |
|------|------|
| 中文名 | 光学补偿 |
| 功能描述 | 添加或移除镜头畸变效果 |
| 核心参数 | Field of View (FOV)（视野）：0 ~ 180 度，默认 30 |
| | Reverse Lens Distortion（反转镜头失真） |
| | FOV Orientation（视野方向）：Horizontal / Vertical / Diagonal |
| | View Center（视图中心）：畸变中心 |
| | Optimal Pixels（最佳像素） |
| | Resize（调整大小）：Off / Maximize |
| 典型应用 | 镜头畸变校正、鱼眼效果、广角效果、透视校正 |

#### Polar Coordinates（极坐标）

| 项目 | 内容 |
|------|------|
| 中文名 | 极坐标 |
| 功能描述 | 在直角坐标和极坐标之间转换图像 |
| 核心参数 | Interpolation（插值）：High / Low |
| | Type of Conversion（转换类型）：Rect to Polar（矩形到极坐标）/ Polar to Rect（极坐标到矩形） |
| 典型应用 | 圆形文字、极坐标变形、隧道效果、圆形全景 |

#### Reshape（重塑）

| 项目 | 内容 |
|------|------|
| 中文名 | 重塑 |
| 功能描述 | 使用源蒙版和目标蒙版来重新定义图像形状 |
| 核心参数 | Source Mask（源蒙版）：原始形状蒙版 |
| | Destination Mask（目标蒙版）：目标形状蒙版 |
| | Boundary Mask（边界蒙版）：可选边界限制 |
| | Percent（百分比）：0 ~ 100%，默认 100% |
| | Elasticity（弹性）：Stiff / Less Stiff / Below Normal / Normal / Above Normal / Liquid / Super Fluid |
| | Correspondence Points（对应点数）：0 ~ 1000 |
| 典型应用 | 变形动画、形状转换、角色变形、物体变形 |

#### Ripple（波纹）

| 项目 | 内容 |
|------|------|
| 中文名 | 波纹 |
| 功能描述 | 创建同心圆形波纹扭曲效果 |
| 核心参数 | Radius（半径）：0 ~ 2000，默认 200 |
| | Center of Ripple（波纹中心）：波纹原点 |
| | Type of Conversion（转换类型）：Asymmetric / Symmetric |
| | Wavelength（波长）：0.01 ~ 10000，默认 50 |
| | Amplitude（振幅）：0 ~ 5000，默认 5 |
| | Phase（相位）：0 ~ 360 度，默认 0 |
| 典型应用 | 水面波纹、冲击波效果、音波可视化、水滴效果 |

#### Spherize（球面化）

| 项目 | 内容 |
|------|------|
| 中文名 | 球面化 |
| 功能描述 | 将图像扭曲成球面效果 |
| 核心参数 | Radius（半径）：0 ~ 2000，默认 500 |
| | Center of Sphere（球心）：球心位置 |
| 典型应用 | 球面效果、鱼眼效果、3D球面贴图、放大镜 |

#### Turbulent Displace（动荡置换）

| 项目 | 内容 |
|------|------|
| 中文名 | 动荡置换 / 湍流置换 |
| 功能描述 | 使用分形噪波创建有机的扭曲变形效果 |
| 核心参数 | Displacement（置换方式）：Turbulent / Bulge / Twist |
| | Amount（数量）：0 ~ 500，默认 20 |
| | Size（大小）：2 ~ 512，默认 50 |
| | Offset（偏移）：噪波偏移 |
| | Complexity（复杂度）：1 ~ 10，默认 4 |
| | Evolution（演化）：噪波动画相位 |
| | Evolution Options（演化选项）：循环演化等 |
| | Pinning（固定）：固定边缘 |
| | Antialiasing（消除锯齿）：Low / Medium / High |
| 典型应用 | 火焰扭曲、水流效果、有机变形、故障艺术、能量场 |

#### Twirl（扭转）

| 项目 | 内容 |
|------|------|
| 中文名 | 扭转 |
| 功能描述 | 以中心为轴旋转扭曲图像 |
| 核心参数 | Angle（角度）：-9999 ~ 9999 度，默认 0 |
| | Twirl Radius（扭转半径）：0 ~ 2000，默认 500 |
| | Twirl Center（扭转中心）：扭转中心位置 |
| 典型应用 | 漩涡效果、龙卷风、黑洞效果、创意扭曲 |

#### Wave Warp（波浪变形）

| 项目 | 内容 |
|------|------|
| 中文名 | 波浪变形 |
| 功能描述 | 创建周期性的波浪扭曲效果 |
| 核心参数 | Wave Type（波浪类型）：Sine / Square / Triangle / Sawtooth etc. |
| | Wave Height（波高）：0 ~ 10000，默认 100 |
| | Wave Width（波长）：1 ~ 10000，默认 400 |
| | Direction（方向）：0 ~ 360 度，默认 0 |
| | Wave Speed（波速）：-10 ~ 10，默认 2 |
| | Pinning（固定）：固定边缘 |
| | Phase（相位）：0 ~ 360 度，默认 0 |
| | Antialiasing（消除锯齿）：Low / Medium / High |
| 典型应用 | 水面效果、旗帜飘动、布料波动、波浪动画 |

#### CC Bend It

| 项目 | 内容 |
|------|------|
| 中文名 | CC弯曲 |
| 功能描述 | 从一端弯曲图层 |
| 核心参数 | Bend（弯曲）：-100 ~ 100，默认 0 |
| | Start / End Point：起止点 |
| | Distort（扭曲）：-50 ~ 50，默认 0 |
| | Render Pre Start / Post End：开始前/结束后渲染方式 |
| 典型应用 | 纸张弯曲、物体弯折、翻页效果、弹性变形 |

#### CC Bender

| 项目 | 内容 |
|------|------|
| 中文名 | CC弯曲器 |
| 功能描述 | 图层整体弯曲效果，多种弯曲模式 |
| 核心参数 | Amount（数量）：-100 ~ 100，默认 0 |
| | Style（样式）：High / Normal / Low |
| | Axis（轴）：Vertical / Horizontal |
| 典型应用 | 弯曲变形、纸张效果、弹性动画 |

#### CC Blobbylize

| 项目 | 内容 |
|------|------|
| 中文名 | CC融化变形 |
| 功能描述 | 模拟液态融化的变形效果 |
| 核心参数 | Blobbiness（融状）：0 ~ 500，默认 100 |
| | Softness（柔化）：0 ~ 500，默认 100 |
| | Cut Away（切除）：0 ~ 100%，默认 0% |
| 典型应用 | 融化效果、液体变形、金属融化、有机变形 |

#### CC Flo Motion

| 项目 | 内容 |
|------|------|
| 中文名 | CC流动运动 |
| 功能描述 | 创建流动式的扭曲效果 |
| 核心参数 | Knots 1/2：两个控制点位置 |
| | Amount 1/2：两个控制点的扭曲量 |
| | Falloff（衰减）：0 ~ 1，默认 0.5 |
| 典型应用 | 流体效果、扭曲变形、能量漩涡 |

#### CC Griddler

| 项目 | 内容 |
|------|------|
| 中文名 | CC网格扭曲 |
| 功能描述 | 将图像分散成网格状方块并扭曲 |
| 核心参数 | Tile Size（方块大小）：1 ~ 500，默认 60 |
| | X/Y Offset：X/Y 偏移 |
| | Displacement（置换）：-1 ~ 1，默认 0 |
| | Rotation（旋转）：-1 ~ 1，默认 0 |
| | Cut Tile（剪切方块） |
| 典型应用 | 方块散落、故障效果、拼图动画 |

#### CC Lens

| 项目 | 内容 |
|------|------|
| 中文名 | CC镜头 |
| 功能描述 | 镜头扭曲效果，可创建鱼眼或凸透镜效果 |
| 核心参数 | Center（中心）：镜头中心 |
| | Size（大小）：0 ~ 1000，默认 200 |
| | Convergence（会聚）：-100 ~ 100，默认 0 |
| 典型应用 | 鱼眼效果、放大镜、镜头畸变、哈哈镜 |

#### CC Page Turn

| 项目 | 内容 |
|------|------|
| 中文名 | CC翻页 |
| 功能描述 | 创建逼真的翻页效果 |
| 核心参数 | Fold Position（折叠位置）：折叠线位置 |
| | Fold Direction（折叠方向）：折叠角度 |
| | Fold Radius（折叠半径）：0 ~ 200，默认 0 |
| | Back Page（背面页）：背面图层 |
| | Back Opacity（背面不透明度）：0 ~ 100%，默认 100% |
| | Light Direction（灯光方向）：光影方向 |
| | Highlight Color（高光颜色） |
| 典型应用 | 翻书效果、页面切换、日历翻页、杂志翻页 |

#### CC Power Pin

| 项目 | 内容 |
|------|------|
| 中文名 | CC强力边角定位 |
| 功能描述 | 增强版的边角定位，支持透视和运动模糊 |
| 核心参数 | Top Left / Top Right / Bottom Left / Bottom Right：四个角 |
| | Perspective（透视）：0 ~ 100，默认 0 |
| | Unstretch（取消拉伸）：0 ~ 100，默认 0 |
| | Expansion（扩展）：-100 ~ 100，默认 0 |
| | Motion Blur（运动模糊）：开关 |
| 典型应用 | 屏幕替换、透视贴图、高级边角变形 |

#### CC Ripple Pulse

| 项目 | 内容 |
|------|------|
| 中文名 | CC波纹脉冲 |
| 功能描述 | 创建动态的波纹脉冲效果 |
| 核心参数 | Ripple（波纹）：0 ~ 1000，默认 100 |
| | Center（中心）：波纹中心 |
| | Time Span（时间跨度）：0 ~ 10 秒，默认 2 秒 |
| | Amplitude（振幅）：0 ~ 500，默认 50 |
| | Pulse Level（脉冲级别）：0 ~ 1，默认 0 |
| 典型应用 | 冲击波、水滴波纹、音波效果、能量扩散 |

#### CC Slant

| 项目 | 内容 |
|------|------|
| 中文名 | CC倾斜 |
| 功能描述 | 倾斜扭曲效果 |
| 核心参数 | Slant（倾斜）：-100 ~ 100，默认 0 |
| | Stretching（拉伸）：On / Off |
| | Floor（地板）：0 ~ 1，默认 1 |
| | Floor Angle（地板角度）：-180 ~ 180 度，默认 0 |
| 典型应用 | 倾斜效果、透视变形、物体倾斜 |

#### CC Smear

| 项目 | 内容 |
|------|------|
| 中文名 | CC涂抹 |
| 功能描述 | 基于蒙版的涂抹变形效果 |
| 核心参数 | Source Mask（源蒙版） |
| | Displacement Mask（置换蒙版） |
| | Displacement Percentage（置换百分比）：0 ~ 2000%，默认 100% |
| | Percentage（百分比）：0 ~ 100%，默认 100% |
| | Elasticity（弹性）：多种模式 |
| 典型应用 | 涂抹变形、局部变形、绘画效果 |

#### CC Split

| 项目 | 内容 |
|------|------|
| 中文名 | CC分割 |
| 功能描述 | 将图像从中间分割并分离 |
| 核心参数 | Split（分割）：0 ~ 100，默认 0 |
| | Direction（方向）：0 ~ 360 度，默认 0 |
| 典型应用 | 分割转场、故障效果、图像分离 |

#### CC Split 2

| 项目 | 内容 |
|------|------|
| 中文名 | CC分割2 |
| 功能描述 | 增强版分割效果，支持多点分割 |
| 核心参数 | Split A/B：两个分割点 |
| | Gap A/B：两个间隙 |
| | Point A/B：两个分割点位置 |
| 典型应用 | 复杂分割转场、多段分离效果 |

#### CC Tiler

| 项目 | 内容 |
|------|------|
| 中文名 | CC平铺 |
| 功能描述 | 将图像缩小并平铺显示 |
| 核心参数 | Scale（缩放）：0 ~ 100%，默认 50% |
| | Center（中心）：平铺中心 |
| | Edges（边缘）：Warp / Mirror |
| 典型应用 | 平铺背景、图案效果、万花筒 |

#### CC WarpoMatic

| 项目 | 内容 |
|------|------|
| 中文名 | CC扭曲器 |
| 功能描述 | 多种预设扭曲效果的集合 |
| 核心参数 | Warp Amount（扭曲量）：0 ~ 200，默认 50 |
| | Warp Style（扭曲样式）：多种预设 |
| | Object Reflectivity（物体反射率） |
| 典型应用 | 快速扭曲效果、创意变形、多种扭曲预设 |

---

### 2.5 风格化（Stylize）

#### Brush Strokes（画笔描边）

| 项目 | 内容 |
|------|------|
| 中文名 | 画笔描边 |
| 功能描述 | 模拟手绘画笔的绘画效果 |
| 核心参数 | Stroke Angle（描边角度）：0 ~ 360 度，默认 45 |
| | Brush Size（画笔大小）：0 ~ 10，默认 2 |
| | Stroke Length（描边长度）：0 ~ 40，默认 15 |
| | Stroke Density（描边密度）：0 ~ 2.0，默认 1.0 |
| | Stroke Randomness（描边随机性）：0 ~ 1.0，默认 1.0 |
| | Paint Surface（绘画表面）：Paint on Original / Paint on White / Paint on Black / Paint on Transparent |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 绘画效果、手绘风格、艺术化处理、油画效果 |

#### Cartoon（卡通）

| 项目 | 内容 |
|------|------|
| 中文名 | 卡通 |
| 功能描述 | 将真实图像转换为卡通风格 |
| 核心参数 | Render（渲染）：Fill / Edge / Fill & Edge |
| | Detail Radius（细节半径）：0 ~ 50，默认 5 |
| | Detail Threshold（细节阈值）：0 ~ 1.0，默认 0.5 |
| | Edge Threshold（边缘阈值）：0 ~ 1.0，默认 0.5 |
| | Edge Softness（边缘柔化）：0 ~ 1.0，默认 0.5 |
| | Edge Width（边缘宽度）：0 ~ 5，默认 1 |
| | Shading Steps（阴影阶数）：0 ~ 8，默认 4 |
| | Shading Softness（阴影柔化）：0 ~ 50，默认 5 |
| 典型应用 | 卡通风格、动漫效果、游戏风格、艺术化处理 |

#### Color Emboss（彩色浮雕）

| 项目 | 内容 |
|------|------|
| 中文名 | 彩色浮雕 |
| 功能描述 | 创建带颜色的浮雕效果，边缘有光影感 |
| 核心参数 | Direction（方向）：0 ~ 360 度，默认 45 |
| | Relief（起伏）：0 ~ 100，默认 5 |
| | Contrast（对比度）：0 ~ 100，默认 50 |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 浮雕效果、纹理增强、金属质感、凹凸效果 |

#### Emboss（浮雕）

| 项目 | 内容 |
|------|------|
| 中文名 | 浮雕 |
| 功能描述 | 创建灰度浮雕效果 |
| 核心参数 | Direction（方向）：0 ~ 360 度，默认 45 |
| | Relief（起伏）：0 ~ 100，默认 5 |
| | Contrast（对比度）：0 ~ 100，默认 50 |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 浮雕效果、纹理显现、印章效果、凹凸贴图 |

#### Find Edges（查找边缘）

| 项目 | 内容 |
|------|------|
| 中文名 | 查找边缘 |
| 功能描述 | 检测图像中的边缘并高亮显示 |
| 核心参数 | Invert（反转）：反转效果 |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 素描效果、线稿效果、边缘检测、科技感轮廓 |

#### Glow（发光）

| 项目 | 内容 |
|------|------|
| 中文名 | 发光 |
| 功能描述 | 为图像的高亮区域添加发光效果，是最常用的效果之一 |
| 核心参数 | Glow Based On（发光基于）：Color Channels / Alpha Channels |
| | Glow Threshold（发光阈值）：0 ~ 100%，默认 60% |
| | Glow Radius（发光半径）：0 ~ 200，默认 15 |
| | Glow Intensity（发光强度）：0 ~ 10，默认 1.0 |
| | Composite Original（合成原始图层）：On Top / Behind / None |
| | Glow Operation（发光运算）：Add / Screen 等混合模式 |
| | Glow Colors（发光颜色）：Original Colors / A & B Colors / Arbitrary Map |
| | Color Looping（颜色循环）：多种循环模式 |
| | Color Loops（颜色循环数）：1 ~ 10，默认 1 |
| | Color A / Color B：两种颜色 |
| | Glow Dimensions（发光方向）：Horizontal and Vertical / Horizontal / Vertical |
| 典型应用 | 光效、霓虹、魔法效果、文字发光、粒子发光 |

#### Mosaic（马赛克）

| 项目 | 内容 |
|------|------|
| 中文名 | 马赛克 |
| 功能描述 | 将图像像素化为方块马赛克效果 |
| 核心参数 | Horizontal Blocks（水平块数）：1 ~ 4000，默认 60 |
| | Vertical Blocks（垂直块数）：1 ~ 4000，默认 60 |
| | Sharp Colors（锐利颜色）：勾选后颜色更锐利 |
| 典型应用 | 打码效果、像素艺术、隐私保护、风格化处理 |

#### Motion Tile（运动平铺）

| 项目 | 内容 |
|------|------|
| 中文名 | 运动平铺 |
| 功能描述 | 复制并平铺图像，可创建动态效果 |
| 核心参数 | Tile Center（平铺中心） |
| | Tile Width/Height（平铺宽度/高度）：0 ~ 100%，默认 100% |
| | Output Width/Height（输出宽度/高度）：0 ~ 1000%，默认 100% |
| | Mirror Edges（镜像边缘） |
| | Phase（相位）：动画控制 |
| | Horizontal Phase（水平相位） |
| 典型应用 | 动态背景、万花筒效果、纹理平铺 |

#### Posterize（色调分离）

| 项目 | 内容 |
|------|------|
| 中文名 | 色调分离 |
| 功能描述 | 减少图像中的色调级别，创建色块效果 |
| 核心参数 | Level（色阶数）：2 ~ 32，默认 4 |
| 典型应用 | 木刻效果、复古风格、波普艺术、色彩简化 |

#### Roughen Edges（粗糙边缘）

| 项目 | 内容 |
|------|------|
| 中文名 | 粗糙边缘 |
| 功能描述 | 使用分形噪波使图像边缘变得粗糙不规则 |
| 核心参数 | Edge Type（边缘类型）：Roughen / Roughen Color / Rusty / Photocopy / Sponge / Stamped / Torn / Clumpy / Smoky / Chiseled / Chiseled Color |
| | Edge Color（边缘颜色）：适用于部分类型 |
| | Border（边框）：0 ~ 500，默认 5 |
| | Edge Sharpness（边缘锐度）：0 ~ 100%，默认 40% |
| | Fractal Influence（分形影响）：0 ~ 100%，默认 50% |
| | Scale（缩放）：0 ~ 1000，默认 100 |
| | Stretch Width or Height（拉伸宽度或高度）：-500 ~ 500，默认 1 |
| | Offset（偏移）：噪波偏移 |
| | Complexity（复杂度）：1 ~ 10，默认 3 |
| | Evolution（演化）：动画控制 |
| 典型应用 | 水墨边缘、燃烧效果、破损效果、有机边缘、毛边文字 |

#### Scatter（散布）

| 项目 | 内容 |
|------|------|
| 中文名 | 散布 |
| 功能描述 | 将图像像素随机分散，创建颗粒化效果 |
| 核心参数 | Scatter Amount（散布数量）：0 ~ 200，默认 0 |
| | Grain（颗粒）：Both / Horizontal / Vertical |
| | Scatter Randomness（散布随机性）：Every Frame / Animation |
| 典型应用 | 颗粒效果、磨砂玻璃、像素分散、故障艺术 |

#### Strobe Light（闪光灯）

| 项目 | 内容 |
|------|------|
| 中文名 | 闪光灯 |
| 功能描述 | 定期对图像进行运算或颜色切换，模拟闪光灯效果 |
| 核心参数 | Strobe Color（闪光颜色）：闪光时的颜色 |
| | Blends With Original（与原始混合）：0 ~ 100%，默认 100% |
| | Strobe Duration（闪光持续时间）：0 ~ 5 秒，默认 0.05 |
| | Strobe Period（闪光周期）：0 ~ 10 秒，默认 1 |
| | Random Strobe Probability（随机闪光概率）：0 ~ 100%，默认 0% |
| | Strobe（闪光方式）：Operates On Color Only / Makes Layer Transparent |
| | Strobe Operator（闪光运算）：Copy / Add / Subtract 等 |
| 典型应用 | 闪光灯效果、故障闪烁、节奏闪烁、恐怖效果 |

#### Texturize（纹理）

| 项目 | 内容 |
|------|------|
| 中文名 | 纹理 |
| 功能描述 | 将另一个图层的纹理映射到当前图层上 |
| 核心参数 | Texture Layer（纹理图层）：选择纹理图层 |
| | Light Direction（灯光方向）：0 ~ 360 度，默认 45 |
| | Texture Contrast（纹理对比度）：0 ~ 2，默认 1 |
| | Texture Placement（纹理放置）：Tile Texture / Center Texture / Stretch Texture to Fit |
| 典型应用 | 纹理叠加、质感增强、凹凸贴图、材质模拟 |

#### Threshold（阈值）

| 项目 | 内容 |
|------|------|
| 中文名 | 阈值 |
| 功能描述 | 将图像转换为纯黑白两色，根据阈值判断 |
| 核心参数 | Level（色阶）：0 ~ 255，默认 128 |
| 典型应用 | 黑白效果、剪影效果、图形化处理、像素艺术 |

#### CC Burn Film

| 项目 | 内容 |
|------|------|
| 中文名 | CC胶片燃烧 |
| 功能描述 | 模拟胶片燃烧的效果 |
| 核心参数 | Burn（燃烧）：0 ~ 100，默认 0 |
| | Center（中心）：燃烧中心 |
| | Random Seed（随机种子）：控制随机性 |
| 典型应用 | 胶片燃烧效果、转场效果、复古效果 |

#### CC Glass

| 项目 | 内容 |
|------|------|
| 中文名 | CC玻璃 |
| 功能描述 | 模拟玻璃折射和凹凸效果 |
| 核心参数 | Surface（表面）：选择表面图层 |
| | Displacement（置换）：0 ~ 100，默认 20 |
| | Softness（柔化）：0 ~ 100，默认 5 |
| | Maps（贴图）：Height Map / Normal Map |
| | Light / Light Intensity / Light Color：灯光控制 |
| | Shading（着色）：0 ~ 100，默认 50 |
| 典型应用 | 玻璃效果、折射效果、水纹效果、质感表现 |

#### CC Hexagon

| 项目 | 内容 |
|------|------|
| 中文名 | CC六边形 |
| 功能描述 | 创建六边形图案效果 |
| 核心参数 | Size（大小）：1 ~ 1000，默认 50 |
| | Shape（形状）：Hexagon / Star |
| | Left / Right Offset：左右偏移 |
| 典型应用 | 六边形图案、蜂巢效果、几何背景 |

#### CC Kaleida

| 项目 | 内容 |
|------|------|
| 中文名 | CC万花筒 |
| 功能描述 | 万花筒效果，创建对称图案 |
| 核心参数 | Center（中心）：万花筒中心 |
| | Size（大小）：0 ~ 500，默认 100 |
| | Rotation（旋转）：0 ~ 360 度，默认 0 |
| | Mirroring（镜像）：On / Off |
| | Faces（面数）：3 ~ 32，默认 4 |
| 典型应用 | 万花筒效果、曼陀罗图案、对称艺术、迷幻效果 |

#### CC Mr. Smoothie

| 项目 | 内容 |
|------|------|
| 中文名 | CC平滑 |
| 功能描述 | 平滑图像轮廓 |
| 核心参数 | Property（属性）：Size / Position |
| | Value（值）：平滑程度 |
| | Shape（形状）：Round / Square / Star |
| 典型应用 | 轮廓平滑、形状优化、边缘柔化 |

#### CC Plastic

| 项目 | 内容 |
|------|------|
| 中文名 | CC塑料 |
| 功能描述 | 创建塑料质感的凹凸效果 |
| 核心参数 | Bump Height（凹凸高度）：0 ~ 50，默认 10 |
| | Softness（柔化）：0 ~ 30，默认 5 |
| | Light Intensity（灯光强度）：0 ~ 100，默认 50 |
| | Light Color（灯光颜色） |
| | Light Type（灯光类型）：Point Light / Distant Light |
| | Light Position（灯光位置） |
| | Light Height（灯光高度）：0 ~ 100，默认 60 |
| | Shading（着色）：0 ~ 100，默认 50 |
| 典型应用 | 塑料质感、凹凸效果、按钮效果、3D质感 |

#### CC RepeTile

| 项目 | 内容 |
|------|------|
| 中文名 | CC重复平铺 |
| 功能描述 | 在四个方向扩展并平铺图像边缘 |
| 核心参数 | Expand Right / Left / Up / Down：四个方向扩展量 |
| | Tiling（平铺）：Off / On / Transparent |
| 典型应用 | 纹理扩展、边缘平铺、画布扩展 |

#### CC Threshold RGB

| 项目 | 内容 |
|------|------|
| 中文名 | RGB阈值 |
| 功能描述 | 分别对RGB通道应用阈值效果 |
| 核心参数 | Red Threshold（红色阈值）：0 ~ 255，默认 128 |
| | Green Threshold（绿色阈值）：0 ~ 255，默认 128 |
| | Blue Threshold（蓝色阈值）：0 ~ 255，默认 128 |
| | Invert（反转） |
| 典型应用 | 彩色阈值效果、故障艺术、波普艺术、特殊色彩效果 |

---

### 2.6 透视（Perspective）

#### 3D Glasses（3D眼镜）

| 项目 | 内容 |
|------|------|
| 中文名 | 3D眼镜 |
| 功能描述 | 将两个图层合成为立体3D效果，支持多种3D格式 |
| 核心参数 | Left View / Right View：左右视图图层 |
| | Stereo Pair Type（立体对类型）：Side by Side / Top-Bottom |
| | 3D View（3D视图）：多种3D显示模式 |
| | Swap Left-Right（交换左右） |
| | Convergence Offset（会聚偏移） |
| 典型应用 | 3D立体效果、红蓝立体、VR内容、立体电影 |

#### Bevel Alpha（斜面Alpha）

| 项目 | 内容 |
|------|------|
| 中文名 | 斜面Alpha |
| 功能描述 | 为Alpha通道边缘添加立体斜面效果 |
| 核心参数 | Edge Thickness（边缘厚度）：0 ~ 500，默认 3 |
| | Light Angle（灯光角度）：0 ~ 360 度，默认 -45 |
| | Light Color（灯光颜色）：默认白色 |
| | Light Intensity（灯光强度）：0 ~ 5，默认 0.8 |
| 典型应用 | 3D文字效果、立体按钮、Logo立体效果、浮雕效果 |

#### Bevel Edges（斜面边缘）

| 项目 | 内容 |
|------|------|
| 中文名 | 斜面边缘 |
| 功能描述 | 为图层边缘添加立体斜面效果 |
| 核心参数 | Edge Thickness（边缘厚度）：0 ~ 0.5，默认 0.1 |
| | Light Angle（灯光角度）：0 ~ 360 度，默认 45 |
| | Light Color（灯光颜色）：默认白色 |
| | Light Intensity（灯光强度）：0 ~ 5，默认 0.8 |
| 典型应用 | 立体边框、相框效果、卡片立体效果 |

#### CC Cylinder（CC圆柱）

| 项目 | 内容 |
|------|------|
| 中文名 | CC圆柱 |
| 功能描述 | 将图像卷曲成圆柱面 |
| 核心参数 | Radius（半径）：0 ~ 5000，默认 1000 |
| | Rotation（旋转）：0 ~ 360 度，默认 0 |
| | Rotation Position（旋转位置）：X/Y/Z |
| | Light（灯光）：灯光控制 |
| | Render（渲染）：Full / Outside / Inside |
| 典型应用 | 圆柱贴图、滚动字幕、3D圆柱效果 |

#### CC Sphere（CC球体）

| 项目 | 内容 |
|------|------|
| 中文名 | CC球体 |
| 功能描述 | 将图像包裹到球面上，创建3D球效果 |
| 核心参数 | Radius（半径）：0 ~ 5000，默认 250 |
| | Offset（偏移）：球体位置偏移 |
| | Light（灯光）：灯光控制 |
| | Shading（着色）：0 ~ 100，默认 50 |
| | Texture（纹理）：纹理贴图控制 |
| | Rotation（旋转）：X/Y/Z 旋转 |
| 典型应用 | 3D球体、地球效果、玻璃球、水晶球、球体贴图 |

#### CC Spotlight（CC聚光灯）

| 项目 | 内容 |
|------|------|
| 中文名 | CC聚光灯 |
| 功能描述 | 创建聚光灯照射效果 |
| 核心参数 | From（来源）：灯光位置 |
| | To（指向）：灯光目标位置 |
| | Height（高度）：0 ~ 500，默认 100 |
| | Cone Angle（锥形角度）：0 ~ 180 度，默认 45 |
| | Edge Softness（边缘柔化）：0 ~ 100%，默认 50% |
| | Color（颜色）：灯光颜色 |
| | Intensity（强度）：0 ~ 200，默认 100 |
| | Render（渲染）：Spotlight / Colorize / Lighting |
| 典型应用 | 聚光灯效果、舞台灯光、手电筒效果、氛围光 |

#### Drop Shadow（投影）

| 项目 | 内容 |
|------|------|
| 中文名 | 投影 |
| 功能描述 | 为图层添加阴影效果，最常用的效果之一 |
| 核心参数 | Shadow Color（阴影颜色）：默认黑色 |
| | Opacity（不透明度）：0 ~ 100%，默认 75% |
| | Direction（方向）：0 ~ 360 度，默认 135 |
| | Distance（距离）：0 ~ 2000，默认 5 |
| | Softness（柔和度）：0 ~ 2000，默认 5 |
| | Spread（扩散）：0 ~ 100%，默认 0% |
| 典型应用 | 文字阴影、图层立体感、悬浮效果、UI设计 |

#### Radial Shadow（径向阴影）

| 项目 | 内容 |
|------|------|
| 中文名 | 径向阴影 |
| 功能描述 | 创建径向光源产生的阴影，模拟点光源投影 |
| 核心参数 | Shadow Color（阴影颜色）：默认黑色 |
| | Opacity（不透明度）：0 ~ 100%，默认 75% |
| | Light Source（光源）：光源位置 |
| | Projection Distance（投影距离）：0 ~ 2000，默认 20 |
| | Softness（柔和度）：0 ~ 2000，默认 10 |
| | Render（渲染）：Regular / Glass Edge |
| | Color Influence（颜色影响）：0 ~ 100%，默认 0% |
| 典型应用 | 立体阴影、投影效果、悬空物体、灯光阴影 |

---

### 2.7 通道（Channel）

#### Alpha Levels（Alpha色阶）

| 项目 | 内容 |
|------|------|
| 中文名 | Alpha色阶 |
| 功能描述 | 调整Alpha通道的色阶，控制透明度 |
| 核心参数 | Input Black Limit（输入黑限制）：0 ~ 255，默认 0 |
| | Input White Limit（输入白限制）：0 ~ 255，默认 255 |
| | Output Black Limit（输出黑限制）：0 ~ 255，默认 0 |
| | Output White Limit（输出白限制）：0 ~ 255，默认 255 |
| 典型应用 | 调整蒙版透明度、优化Alpha通道、边缘处理 |

#### Arithmetic（运算）

| 项目 | 内容 |
|------|------|
| 中文名 | 运算 |
| 功能描述 | 对通道进行简单的数学运算 |
| 核心参数 | Operator（运算符）：多种运算方式 |
| | Red/Green/Blue Value：各通道运算值 |
| | Clip Result（剪切结果） |
| 典型应用 | 通道调整、特殊效果、数学运算 |

#### Blend（混合）

| 项目 | 内容 |
|------|------|
| 中文名 | 混合 |
| 功能描述 | 将两个图层以多种方式混合 |
| 核心参数 | Blend With Layer（混合图层）：选择混合图层 |
| | Mode（模式）：Crossfade / Color Only / Tint Only / Darken Only / Lighten Only |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 50% |
| | If Layer Sizes Differ（如果图层大小不同）：Center / Stretch to Fit / Tile |
| 典型应用 | 图层混合、图像融合、过渡效果 |

#### Calculations（计算）

| 项目 | 内容 |
|------|------|
| 中文名 | 计算 |
| 功能描述 | 将两个图层的指定通道进行混合运算 |
| 核心参数 | Input Channel（输入通道）：RGBA各通道 |
| | Second Layer / Second Layer Channel：第二个图层和通道 |
| | Blending Mode（混合模式）：多种混合模式 |
| | Preserve Transparency（保持透明度） |
| 典型应用 | 通道合成、蒙版创建、高级混合 |

#### Channel Combiner（通道组合器）

| 项目 | 内容 |
|------|------|
| 中文名 | 通道组合器 |
| 功能描述 | 提取、组合和操作通道 |
| 核心参数 | Source Channels（源通道）：选择来源 |
| | From（来自）：多种通道来源 |
| | To（到）：输出方式 |
| | Invert（反转） |
| | Use 2nd Layer（使用第二图层） |
| | Solid Alpha（纯色Alpha） |
| 典型应用 | 通道转换、颜色空间转换、提取通道 |

#### Compound Arithmetic（复合运算）

| 项目 | 内容 |
|------|------|
| 中文名 | 复合运算 |
| 功能描述 | 使用另一个图层的通道进行数学运算 |
| 核心参数 | Second Source Layer（第二源图层） |
| | Operator（运算符）：多种运算 |
| | Operate on Channels（操作通道）：RGB / ARGB |
| | Overflow Behavior（溢出行为）：Clip / Wrap / Scale |
| | Stretch Second Source to Fit（拉伸第二源以适配） |
| 典型应用 | 高级通道运算、复合效果、数学合成 |

#### Invert（反转）

| 项目 | 内容 |
|------|------|
| 中文名 | 反转 |
| 功能描述 | 反转图像的颜色或通道信息 |
| 核心参数 | Channel（通道）：RGB / Red / Green / Blue / Alpha / Hue / Lightness / Saturation / YIQ / Y / U / V |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 颜色反转、负片效果、反相蒙版、创意调色 |

#### Minimax（最小最大值）

| 项目 | 内容 |
|------|------|
| 中文名 | 最小最大值 |
| 功能描述 | 扩展或收缩Alpha通道或颜色通道的亮部或暗部 |
| 核心参数 | Operation（运算）：Minimum / Maximum |
| | Radius（半径）：0 ~ 1000，默认 1 |
| | Channel（通道）：Alpha / Color / Alpha & Color |
| | Direction（方向）：Horizontal & Vertical / Horizontal / Vertical |
| | Don't Shrink Edges（不收缩边缘） |
| 典型应用 | 蒙版膨胀/收缩、去除噪点、边缘处理、创建光晕 |

#### Remove Color Matting（移除颜色蒙版）

| 项目 | 内容 |
|------|------|
| 中文名 | 移除颜色蒙版 |
| 功能描述 | 移除键控后残留的背景色边 |
| 核心参数 | Background Color（背景颜色）：要移除的颜色 |
| 典型应用 | 抠像后处理、去除颜色边、优化键控结果 |

#### Set Channels（设置通道）

| 项目 | 内容 |
|------|------|
| 中文名 | 设置通道 |
| 功能描述 | 将其他图层的通道复制到当前图层的各个通道 |
| 核心参数 | Source Layer 1/2/3/4：四个源图层 |
| | Set Red/Green/Blue/Alpha To Source 1/2/3/4's：设置各通道来源 |
| 典型应用 | 通道重组、自定义通道、颜色通道交换 |

#### Set Matte（设置蒙版）

| 项目 | 内容 |
|------|------|
| 中文名 | 设置蒙版 |
| 功能描述 | 将另一个图层的通道作为当前图层的蒙版 |
| 核心参数 | Take Matte From Layer（从图层获取蒙版）：选择蒙版图层 |
| | Use For Matte（用于蒙版）：选择蒙版通道 |
| | Invert（反转） |
| | Stretch Matte to Fit（拉伸蒙版以适配） |
| | Premultiply Matte Layer（预乘蒙版图层） |
| | Blending With Original（与原始混合）：0 ~ 100%，默认 0% |
| 典型应用 | 自定义蒙版、轨道蒙版替代、蒙版来源切换 |

#### Shift Channels（转换通道）

| 项目 | 内容 |
|------|------|
| 中文名 | 转换通道 |
| 功能描述 | 在图层内部交换或设置各通道来源 |
| 核心参数 | Take Alpha From（Alpha来源）：Alpha / Red / Green / Blue / Full / Off |
| | Take Red From（红色来源）：同上 |
| | Take Green From（绿色来源）：同上 |
| | Take Blue From（蓝色来源）：同上 |
| 典型应用 | 通道交换、创建特殊效果、灰度转换 |

#### Solid Composite（纯色合成）

| 项目 | 内容 |
|------|------|
| 中文名 | 纯色合成 |
| 功能描述 | 将图层与纯色背景合成 |
| 核心参数 | Color（颜色）：纯色颜色 |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| | Source Opacity（源不透明度）：0 ~ 100%，默认 100% |
| | Blending Mode（混合模式）：多种模式 |
| 典型应用 | 纯色背景、颜色叠加、快速合成 |

---

### 2.8 键控（Keying）

#### Color Key（颜色键）

| 项目 | 内容 |
|------|------|
| 中文名 | 颜色键 |
| 功能描述 | 基于指定颜色进行简单抠像，适合纯色背景 |
| 核心参数 | Key Color（键控颜色）：要抠除的颜色 |
| | Color Tolerance（颜色容差）：0 ~ 255，默认 0 |
| | Edge Thin（边缘薄厚）：-10 ~ 10，默认 0 |
| | Edge Feather（边缘羽化）：0 ~ 10，默认 0 |
| 典型应用 | 简单纯色抠像、背景去除、基础键控 |

#### Keylight (1.2)（专业抠像）

| 项目 | 内容 |
|------|------|
| 中文名 | 专业抠像（Keylight） |
| 功能描述 | 业界领先的专业蓝/绿屏抠像工具，效果精准 |
| 核心参数 | Screen Colour（屏幕颜色）：要抠除的背景色 |
| | Screen Gain（屏幕增益）：0 ~ 100，默认 1 |
| | Screen Balance（屏幕平衡）：0 ~ 100，默认 50 |
| | Screen Softness（屏幕柔化）：0 ~ 100，默认 0 |
| | Clip Black / Clip White：裁切黑/白场 |
| | Clip Rollback（裁切回滚） |
| | Despill Bias（溢色偏移） |
| | Alpha Bias（Alpha偏移） |
| | Edge Colour Correction（边缘颜色校正） |
| | Foreground Colour Correction（前景颜色校正） |
| | Inside Mask / Outside Mask：内/外蒙版 |
| | Replace Method（替换方法）：Source / Duplicate / Soft Colour / Hard Colour |
| 典型应用 | 专业绿/蓝屏抠像、高质量键控、电影级抠像 |

#### Luma Key（亮度键）

| 项目 | 内容 |
|------|------|
| 中文名 | 亮度键 |
| 功能描述 | 基于图像的亮度值进行抠像 |
| 核心参数 | Key Type（键控类型）：Key Out Brighter / Key Out Darker / Key Out Similar / Key Out Dissimilar |
| | Threshold（阈值）：0 ~ 255，默认 128 |
| | Tolerance（容差）：0 ~ 255，默认 0 |
| | Edge Thin（边缘薄厚）：-10 ~ 10，默认 0 |
| | Edge Feather（边缘羽化）：0 ~ 10，默认 0 |
| 典型应用 | 高对比度抠像、火焰/烟雾抠像、亮度差异抠像 |

#### Difference Matte（差值蒙版）

| 项目 | 内容 |
|------|------|
| 中文名 | 差值蒙版 |
| 功能描述 | 通过对比源图层和差值图层的差异创建蒙版 |
| 核心参数 | Difference Layer（差值图层）：参考图层 |
| | If Layer Sizes Differ（如果图层大小不同）：Center / Stretch to Fit |
| | Matching Tolerance（匹配容差）：0 ~ 255，默认 0 |
| | Matching Softness（匹配柔化）：0 ~ 255，默认 0 |
| | Blur Before Difference（差值前模糊）：0 ~ 100，默认 0 |
| | Invert（反转） |
| 典型应用 | 固定背景抠像、物体移动提取、背景差分 |

#### Extract（提取）

| 项目 | 内容 |
|------|------|
| 中文名 | 提取 |
| 功能描述 | 基于指定通道的亮度范围提取蒙版 |
| 核心参数 | Channel（通道）：Luminance / Red / Green / Blue / Alpha |
| | Histogram（直方图）：像素分布 |
| | Black Point / White Point：黑/白点 |
| | Black Softness / White Softness：黑/白柔化 |
| 典型应用 | 亮度蒙版、通道提取、高级抠像 |

#### Linear Color Key（线性颜色键）

| 项目 | 内容 |
|------|------|
| 中文名 | 线性颜色键 |
| 功能描述 | 基于线性颜色空间的键控，可微调颜色范围 |
| 核心参数 | Preview（预览）：预览窗口 |
| | View（视图）：Final Output / Source / Source Alpha / Matte Only / Corrected Matte |
| | Key Color（键控颜色）：要抠除的颜色 |
| | Match colors（匹配颜色）：Using RGB / Using Hue / Using Chroma |
| | Matching Softness（匹配柔化）：0 ~ 100%，默认 1% |
| | Matching Tolerance（匹配容差）：0 ~ 100%，默认 1% |
| | Key Operation（键控操作）：Key Colors / Keep Colors |
| 典型应用 | 精确颜色键控、多颜色范围抠像 |

#### Spill Suppressor（溢色抑制）

| 项目 | 内容 |
|------|------|
| 中文名 | 溢色抑制 |
| 功能描述 | 去除抠像后前景物体边缘残留的背景色溢色 |
| 核心参数 | Color To Suppress（抑制颜色）：要去除的溢色 |
| | Color Accuracy（颜色精度）：Fast / Faster / Best |
| | Suppression（抑制量）：0 ~ 100%，默认 100% |
| 典型应用 | 抠像溢色处理、绿/蓝屏边处理、边缘颜色校正 |

#### Inner/Outer Key（内/外键）

| 项目 | 内容 |
|------|------|
| 中文名 | 内/外键 |
| 功能描述 | 使用内蒙版和外蒙版创建精确的键控效果 |
| 核心参数 | Foreground (Inside)（前景内蒙版）：选择内蒙版 |
| | Additional Foreground（附加前景）：附加蒙版 |
| | Background (Outside)（背景外蒙版）：选择外蒙版 |
| | Single Mask Highlight Radius（单蒙版高亮半径） |
| | Cleanup Foreground / Background：清理前/背景 |
| | Edge Thin / Edge Feather：边缘薄厚/羽化 |
| 典型应用 | 精细抠像、毛发处理、Roto辅助、复杂边缘抠像 |

---

### 2.9 蒙版（Matte）

#### Matte Choker（蒙版收缩）

| 项目 | 内容 |
|------|------|
| 中文名 | 蒙版收缩 |
| 功能描述 | 分两阶段收缩或扩展蒙版，精细控制边缘 |
| 核心参数 | Geometric Softness 1/2（几何柔化）：0 ~ 100，默认 2/2 |
| | Choke 1/2（抑制）：-100 ~ 100，默认 0/0 |
| | Gray Level Softness 1/2（灰度柔化）：0 ~ 100%，默认 50%/50% |
| | Iterations（迭代）：1 ~ 100，默认 1 |
| 典型应用 | 蒙版边缘优化、收缩/扩展蒙版、精细控制 |

#### Simple Choker（简单抑制）

| 项目 | 内容 |
|------|------|
| 中文名 | 简单抑制 |
| 功能描述 | 简单的蒙版收缩或扩展效果 |
| 核心参数 | Choke Matte（抑制蒙版）：-100 ~ 100，默认 0 |
| 典型应用 | 快速收缩蒙版、去除边缘白边、简单蒙版调整 |

#### Refine Matte（优化蒙版）

| 项目 | 内容 |
|------|------|
| 中文名 | 优化蒙版 |
| 功能描述 | 综合优化蒙版质量的工具 |
| 核心参数 | Smooth（平滑）：0 ~ 100，默认 0 |
| | Feather（羽化）：0 ~ 100，默认 0 |
| | Choke（抑制）：-100 ~ 100，默认 0 |
| | Reduce Chatter（减少抖动）：0 ~ 100，默认 0 |
| | Decontamination（净化）：0 ~ 100%，默认 0% |
| 典型应用 | 蒙版优化、去除抖动、边缘净化 |

#### Refine Soft Matte（优化柔和蒙版）

| 项目 | 内容 |
|------|------|
| 中文名 | 优化柔和蒙版 |
| 功能描述 | 优化半透明或柔和边缘的蒙版 |
| 核心参数 | Softness（柔化）：0 ~ 50，默认 0 |
| | Edge Threshold（边缘阈值）：0 ~ 100%，默认 50% |
| | Reduce Chatter（减少抖动）：0 ~ 100，默认 0 |
| 典型应用 | 毛发蒙版、烟雾蒙版、柔和边缘优化 |

#### Refine Hard Matte（优化生硬蒙版）

| 项目 | 内容 |
|------|------|
| 中文名 | 优化生硬蒙版 |
| 功能描述 | 优化硬边缘蒙版，去除锯齿和不平滑 |
| 核心参数 | Smooth（平滑）：0 ~ 100，默认 0 |
| | Feather（羽化）：0 ~ 100，默认 0 |
| | Choke（抑制）：-100 ~ 100，默认 0 |
| | Reduce Chatter（减少抖动）：0 ~ 100，默认 0 |
| 典型应用 | 硬边缘蒙版优化、几何形状蒙版、去除锯齿 |

---

### 2.10 模拟（Simulation）

#### CC Ball Action

| 项目 | 内容 |
|------|------|
| 中文名 | CC球化动作 |
| 功能描述 | 将图像分解成小球并产生动力学效果 |
| 核心参数 | Scatter（散射）：0 ~ 1000，默认 500 |
| | Twist（扭曲）：-5 ~ 5，默认 0 |
| | Grid Spacing（网格间距）：2 ~ 500，默认 10 |
| | Ball Size（球大小）：0 ~ 100，默认 75 |
| | Instability State（不稳定状态）：控制动画 |
| | Light / Shading：灯光和着色 |
| 典型应用 | 球化转场、粒子化效果、碎球效果 |

#### CC Bubbles

| 项目 | 内容 |
|------|------|
| 中文名 | CC气泡 |
| 功能描述 | 生成气泡上升效果 |
| 核心参数 | Bubble Amount（气泡数量）：0 ~ 1000，默认 200 |
| | Speed（速度）：0 ~ 5，默认 1 |
| | Size（大小）：0 ~ 100，默认 20 |
| | Amplitude / Wavelength：振幅/波长 |
| | Reflection / Refraction：反射/折射 |
| 典型应用 | 气泡效果、水下场景、碳酸饮料、沸腾效果 |

#### CC Drizzle

| 项目 | 内容 |
|------|------|
| 中文名 | CC细雨 |
| 功能描述 | 模拟雨滴落在水面产生涟漪的效果 |
| 核心参数 | Drip（滴落）：控制滴落速度 |
| | Displacement（置换）：0 ~ 500，默认 50 |
| | Ripple / Smooth / Spread：波纹参数 |
| 典型应用 | 雨滴涟漪、水面效果、雨天场景 |

#### CC Hair

| 项目 | 内容 |
|------|------|
| 中文名 | CC毛发 |
| 功能描述 | 生成毛发或草类效果 |
| 核心参数 | Length（长度）：0 ~ 100，默认 30 |
| | Thickness（厚度）：0 ~ 10，默认 1 |
| | Density（密度）：0 ~ 1000，默认 500 |
| | Splaying（展开）：0 ~ 100，默认 50 |
| | Gravity（重力）：0 ~ 100，默认 0 |
| | Noise / Wind：噪波/风 |
| 典型应用 | 毛发效果、草地、绒毛、织物纹理 |

#### CC Mr. Mercury

| 项目 | 内容 |
|------|------|
| 中文名 | CC水银 |
| 功能描述 | 模拟液态金属流动效果 |
| 核心参数 | Radius X/Y：XY方向半径 |
| | Direction / Velocity / Birth Rate：方向/速度/出生率 |
| | Longevity / Producer：寿命/产生器 |
| | Blob / Reflection / Add Particle：粒子参数 |
| | Light / Shading：灯光和着色 |
| 典型应用 | 水银效果、液态金属、流动粒子、岩浆效果 |

#### CC Particle Systems II

| 项目 | 内容 |
|------|------|
| 中文名 | CC粒子系统II |
| 功能描述 | 经典的2D粒子系统 |
| 核心参数 | Birth Rate（出生率）：粒子产生速率 |
| | Longevity（寿命）：粒子存活时间 |
| | Producer Position / Radius X/Y：产生器位置和范围 |
| | Physics（物理）：Velocity / Gravity / Resistance etc. |
| | Particle（粒子）：Type / Size / Opacity etc. |
| 典型应用 | 粒子效果、火花、烟雾、尘土、多种粒子动画 |

#### CC Particle World

| 项目 | 内容 |
|------|------|
| 中文名 | CC粒子世界 |
| 功能描述 | 3D空间粒子系统，支持摄像机 |
| 核心参数 | Birth Rate / Longevity：出生率/寿命 |
| | Producer（产生器）：Position X/Y/Z + Radius X/Y/Z |
| | Physics（物理）：Animation / Velocity / Gravity etc. |
| | Particle（粒子）：Type / Size / Opacity / Color |
| | Camera（摄像机）：支持AE摄像机 |
| | Grid / Ground Plane：网格/地平面 |
| 典型应用 | 3D粒子效果、空间粒子、星云、粒子场景 |

#### CC Rain

| 项目 | 内容 |
|------|------|
| 中文名 | CC雨 |
| 功能描述 | 快速创建下雨效果 |
| 核心参数 | Raindrops（雨滴数）：0 ~ 10000，默认 5000 |
| | Speed（速度）：0 ~ 5000，默认 1000 |
| | Angle（角度）：-90 ~ 90 度，默认 20 |
| | Size（大小）：0 ~ 100，默认 30 |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| | Source Depth（来源深度）：3D深度 |
| 典型应用 | 下雨效果、雨天氛围、动态雨景 |

#### CC Snow

| 项目 | 内容 |
|------|------|
| 中文名 | CC雪 |
| 功能描述 | 快速创建下雪效果 |
| 核心参数 | Flakes（雪花数）：0 ~ 10000，默认 2000 |
| | Speed（速度）：0 ~ 500，默认 200 |
| | Wobble Amount（晃动量）：0 ~ 5，默认 1 |
| | Size（大小）：0 ~ 100，默认 50 |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| | Source Depth（来源深度）：3D深度 |
| 典型应用 | 下雪效果、冬日场景、雪花飘落 |

#### CC Star Burst

| 项目 | 内容 |
|------|------|
| 中文名 | CC星爆 |
| 功能描述 | 创建星空穿梭效果 |
| 核心参数 | Speed（速度）：0 ~ 500，默认 60 |
| | Size（大小）：0 ~ 100，默认 50 |
| | Phase（相位）：动画控制 |
| | Opacity（不透明度）：0 ~ 100%，默认 100% |
| | Grid Spacing（网格间距）：控制星星密度 |
| 典型应用 | 太空穿梭、超光速、星空旅行、速度感 |

#### Foam（气泡）

| 项目 | 内容 |
|------|------|
| 中文名 | 气泡 / 泡沫 |
| 功能描述 | 逼真的气泡/泡沫模拟，支持粒子流动和碰撞 |
| 核心参数 | View（视图）：Draft / Draft + Flow / Rendered |
| | Producer（产生器）：Point / Box / Line / Circle / Image |
| | Bubbles（气泡）：Size / Size Variance / Lifespan etc. |
| | Physics（物理）：Initial Speed / Wind / Turbulence etc. |
| | Zoom（缩放）：整体缩放 |
| | Universe Size（宇宙大小）：粒子空间大小 |
| | Rendering（渲染）：Blend Mode / Texture etc. |
| 典型应用 | 气泡效果、泡沫、流体模拟、粒子流动 |

#### Particle Playground（粒子运动场）

| 项目 | 内容 |
|------|------|
| 中文名 | 粒子运动场 |
| 功能描述 | AE内置的复杂粒子系统，功能强大但操作复杂 |
| 核心参数 | Cannon（加农炮）：从点发射粒子 |
| | Grid（网格）：从网格生成粒子 |
| | Layer Exploder（图层爆炸）：爆炸图层生成粒子 |
| | Particle Exploder（粒子爆炸）：粒子爆炸 |
| | Layer Map（图层映射）：用图层替换粒子 |
| | Gravity（重力）：重力效果 |
| | Repel（排斥）：粒子间排斥 |
| | Wall（墙）：粒子碰撞墙 |
| | Persistent / Ephemeral Property Mappers：属性映射 |
| 典型应用 | 复杂粒子效果、文字粒子化、爆炸效果、群体动画 |

#### Shatter（碎片）

| 项目 | 内容 |
|------|------|
| 中文名 | 碎片 |
| 功能描述 | 创建物体炸裂成碎片的效果，支持物理模拟 |
| 核心参数 | View（视图）：Rendered / Draft etc. |
| | Shape（形状）：Pattern / Custom Shatter |
| | Force 1/2（作用力）：爆炸力控制 |
| | Gradient（渐变）：渐变力控制 |
| | Physics（物理）：Rotation Speed / Gravity / Viscosity etc. |
| | Texture（纹理）：碎片颜色/纹理 |
| | Camera System（摄像机系统）：Camera Position / Corner Pins / AE Camera |
| 典型应用 | 爆炸效果、破碎效果、碎片转场、玻璃破碎 |

#### Wave World（波形世界）

| 项目 | 内容 |
|------|------|
| 中文名 | 波形世界 |
| 功能描述 | 模拟水面波纹的生成和传播，通常作为置换图使用 |
| 核心参数 | View（视图）：Height Map / Wireframe / Wireframe Preview |
| | Ground（地面）：地面设置 |
| | Simulator（模拟器）：Wave Speed / Damping / Reflect Walls |
| | Production（生成）：Height Map Resolution / Quality |
| | Producer 1/2（产生器）：Type / Position / Height etc. |
| 典型应用 | 水面波纹、涟漪效果、声波可视化、动态置换图 |

#### Card Dance（卡片舞蹈）

| 项目 | 内容 |
|------|------|
| 中文名 | 卡片舞蹈 |
| 功能描述 | 将图像分割成卡片状方块并进行有序的动画变换 |
| 核心参数 | Rows / Columns（行/列）：卡片数量 |
| | Back Layer（背面图层）：卡片背面 |
| | Gradient Layer 1/2（渐变图层）：控制动画顺序 |
| | Rotation Order / Transformation Order：旋转/变换顺序 |
| | Position (X/Y/Z) / Rotation (X/Y/Z) / Scale：变换参数 |
| | Camera System（摄像机系统）：多种摄像机模式 |
| | Light / Material：灯光和材质 |
| 典型应用 | 卡片翻转、矩阵转场、方块动画、像素化转场 |

#### Card Wipe（卡片擦除）

| 项目 | 内容 |
|------|------|
| 中文名 | 卡片擦除 |
| 功能描述 | 以卡片翻转的方式进行画面过渡 |
| 核心参数 | Transition Completion（过渡完成）：0 ~ 100%，默认 0% |
| | Transition Width（过渡宽度）：0 ~ 100%，默认 50% |
| | Backward / Forward Layers：前/后图层 |
| | Rows / Columns：行/列数 |
| | Tile Flip Direction（瓷砖翻转方向） |
| | Flip Axis / Flip Direction：翻转轴/方向 |
| | Random Order（随机顺序） |
| | Camera / Light / Material：摄像机/灯光/材质 |
| 典型应用 | 转场效果、卡片翻页、矩阵切换、方块过渡 |

#### Caustics（焦散）

| 项目 | 内容 |
|------|------|
| 中文名 | 焦散 |
| 功能描述 | 模拟水下焦散效果和光的折射 |
| 核心参数 | Bottom（底部）：底部图层 |
| | Water（水）：水面图层 |
| | Sky（天空）：天空图层 |
| | Light（灯光）：灯光位置和强度 |
| | Surface / Underwater：表面/水下设置 |
| 典型应用 | 水下焦散、水底光效、光线穿透、水面折射 |

---

### 2.11 噪波与颗粒（Noise & Grain）

#### Add Grain（添加颗粒）

| 项目 | 内容 |
|------|------|
| 中文名 | 添加颗粒 |
| 功能描述 | 添加真实的胶片颗粒效果 |
| 核心参数 | Viewing Mode（查看模式）：Preview / Final Output / Split Screen |
| | Preset（预设）：多种胶片类型预设 |
| | Amount（数量）：0 ~ 100，默认 10 |
| | Size（大小）：0.1 ~ 10，默认 1 |
| | Softness（柔化）：0 ~ 1，默认 0.5 |
| | Aspect Ratio（宽高比）：0.1 ~ 10，默认 1 |
| | Channel Intensity（通道强度）：R/G/B各通道颗粒强度 |
| | Channel Size（通道大小）：各通道颗粒大小 |
| | Color（颜色）：单色/彩色颗粒 |
| | Auto Animation（自动动画）/ Speed |
| 典型应用 | 胶片质感、复古效果、数字降噪反操作、统一颗粒 |

#### Fractal Noise（分形噪波）

| 项目 | 内容 |
|------|------|
| 中文名 | 分形噪波 |
| 功能描述 | 创建有机的分形噪波图案，是最常用的效果之一 |
| 核心参数 | Fractal Type（分形类型）：多种分形算法 |
| | Noise Type（噪波类型）：Block / Linear / Soft / Spline |
| | Invert（反转）：反转噪波 |
| | Contrast（对比度）：0 ~ 400，默认 100 |
| | Brightness（亮度）：-100 ~ 100，默认 0 |
| | Overflow（溢出）：Clip / Soft Clip / Wrap Back |
| | Transform（变换）：Rotation / Scale / Offset |
| | Complexity（复杂度）：1 ~ 20，默认 6 |
| | Sub Settings（子设置）：子影响/子缩放/子旋转 |
| | Evolution（演化）：动画相位 |
| | Evolution Options（演化选项）：循环演化 |
| | Blending Mode（混合模式）：与原图层混合 |
| 典型应用 | 烟雾、云层、火焰、纹理、置换图、特效元素 |

#### Match Grain（匹配颗粒）

| 项目 | 内容 |
|------|------|
| 中文名 | 匹配颗粒 |
| 功能描述 | 将一个素材的颗粒匹配到另一个素材上 |
| 核心参数 | Viewing Mode（查看模式） |
| | Noise Source Layer（噪波源图层）：要匹配的源 |
| | Sampling Point / Sampling Size：采样点/大小 |
| | Compensate for Existing Noise（补偿现有噪点） |
| | Reduce Noise（减少噪波）：0 ~ 100，默认 0 |
| | Amount（数量）：0 ~ 100，默认 10 |
| | Size / Color / Fine Tuning：精细调整 |
| 典型应用 | 素材颗粒统一、合成匹配、多源素材整合 |

#### Noise（噪波）

| 项目 | 内容 |
|------|------|
| 中文名 | 噪波 |
| 功能描述 | 添加随机噪波效果 |
| 核心参数 | Amount of Noise（噪波数量）：0 ~ 100%，默认 30% |
| | Noise Type（噪波类型）：Use Color Noise（彩色噪波） |
| | Clip Result Values（剪切结果值） |
| 典型应用 | 添加噪点、老电影效果、数字噪波、纹理基础 |

#### Noise Alpha（噪波Alpha）

| 项目 | 内容 |
|------|------|
| 中文名 | 噪波Alpha |
| 功能描述 | 在Alpha通道添加噪波 |
| 核心参数 | Noise（噪波）：Uniform Random / Random Squared / Triangular etc. |
| | Amount（数量）：-100 ~ 100，默认 50 |
| | Noise Type（噪波类型）：Spatial Granularity |
| | Wrap (Fold) Values（环绕折叠值） |
| 典型应用 | 边缘噪波、Alpha扰动、溶解效果 |

#### Noise HLS（噪波HLS）

| 项目 | 内容 |
|------|------|
| 中文名 | 噪波HLS |
| 功能描述 | 在色相、亮度、饱和度通道分别添加噪波 |
| 核心参数 | Hue（色相）：0 ~ 60，默认 0 |
| | Lightness（亮度）：0 ~ 60，默认 12 |
| | Saturation（饱和度）：0 ~ 60，默认 12 |
| | Noise Type（噪波类型）：Uniform / Squared / Grain / Random etc. |
| | Grain Size（颗粒大小）：0 ~ 60，默认 5 |
| 典型应用 | 胶片颗粒、彩色噪点、纹理效果 |

#### Noise HLS Auto（自动噪波HLS）

| 项目 | 内容 |
|------|------|
| 中文名 | 自动噪波HLS |
| 功能描述 | 自动动画的HLS噪波 |
| 核心参数 | Hue / Lightness / Saturation：各通道噪波量 |
| | Noise Type（噪波类型） |
| | Grain Size（颗粒大小） |
| | Auto Animation Speed（自动动画速度）：0 ~ 50，默认 10 |
| 典型应用 | 动态颗粒效果、动画噪波、无需关键帧的噪波动画 |

#### Remove Grain（移除颗粒）

| 项目 | 内容 |
|------|------|
| 中文名 | 移除颗粒 |
| 功能描述 | 减少或移除图像中的颗粒和噪点 |
| 核心参数 | Viewing Mode（查看模式）：Preview / Final Output / Split Screen |
| | Noise Reduction Settings（降噪设置） |
| | Red/Green/Blue Pass（各通道处理） |
| | Fine Tuning（精细调整）：Chroma Suppression / Texture etc. |
| | Unsharp Mask（非锐化蒙版）：降噪后锐化 |
| | Sampling（采样）：采样点设置 |
| 典型应用 | 视频降噪、去除颗粒、修复老素材、低光降噪 |

#### Turbulent Noise（湍动噪波）

| 项目 | 内容 |
|------|------|
| 中文名 | 湍动噪波 |
| 功能描述 | 更高质量的分形噪波，更适合有机效果 |
| 核心参数 | Fractal Type / Noise Type：分形/噪波类型 |
| | Invert / Contrast / Brightness：基础参数 |
| | Transform：变换设置 |
| | Complexity（复杂度）：1 ~ 20，默认 6 |
| | Evolution（演化）：动画控制 |
| | Sub Influence / Sub Rotation / Sub Scale：子设置 |
| 典型应用 | 烟雾、火焰、云、湍流效果、动态纹理 |

---

### 2.12 过渡（Transition）

#### Block Dissolve（块溶解）

| 项目 | 内容 |
|------|------|
| 中文名 | 块溶解 |
| 功能描述 | 以随机方块的形式溶解图像 |
| 核心参数 | Transition Completion（过渡完成）：0 ~ 100%，默认 0% |
| | Block Width / Block Height：方块宽/高，默认 100 |
| | Feather（羽化）：0 ~ 100，默认 0 |
| | Soft Edges (Best Quality)（柔化边缘） |
| 典型应用 | 方块转场、像素化消失、马赛克过渡 |

#### Card Wipe（卡片擦除）

| 项目 | 内容 |
|------|------|
| 中文名 | 卡片擦除 |
| 功能描述 | 以卡片翻转的方式过渡画面（详见模拟类） |
| 核心参数 | 见模拟类 Card Wipe 完整参数 |
| 典型应用 | 转场效果、翻页动画、矩阵切换 |

#### Gradient Wipe（渐变擦除）

| 项目 | 内容 |
|------|------|
| 中文名 | 渐变擦除 |
| 功能描述 | 基于渐变图层的亮度值进行擦除过渡 |
| 核心参数 | Transition Completion（过渡完成）：0 ~ 100%，默认 0% |
| | Transition Softness（过渡柔化）：0 ~ 100%，默认 0% |
| | Gradient Layer（渐变图层）：参考渐变图层 |
| | Gradient Placement（渐变放置）：Tile Gradient / Center Gradient / Stretch Gradient to Fit |
| | Invert Gradient（反转渐变） |
| 典型应用 | 渐变转场、自定义转场形状、遮罩过渡 |

#### Iris Wipe（光圈擦除）

| 项目 | 内容 |
|------|------|
| 中文名 | 光圈擦除 |
| 功能描述 | 以多边形光圈的形式进行擦除 |
| 核心参数 | Iris Center（光圈中心）：中心点 |
| | Iris Points（光圈点数）：3 ~ 32，默认 6 |
| | Outer Radius（外半径）：0 ~ 1500，默认 200 |
| | Use Inner Radius（使用内半径） |
| | Inner Radius（内半径）：0 ~ 1500，默认 0 |
| | Rotation（旋转）：0 ~ 360 度，默认 0 |
| | Feather（羽化）：0 ~ 100，默认 0 |
| 典型应用 | 光圈转场、聚光灯效果、开场/结尾转场 |

#### Linear Wipe（线性擦除）

| 项目 | 内容 |
|------|------|
| 中文名 | 线性擦除 |
| 功能描述 | 以直线的方式进行擦除过渡 |
| 核心参数 | Transition Completion（过渡完成）：0 ~ 100%，默认 0% |
| | Wipe Angle（擦除角度）：0 ~ 360 度，默认 0 |
| | Feather（羽化）：0 ~ 2000，默认 0 |
| 典型应用 | 直线转场、滑动过渡、简单实用的转场 |

#### Radial Wipe（径向擦除）

| 项目 | 内容 |
|------|------|
| 中文名 | 径向擦除 |
| 功能描述 | 以扇形扫描的方式进行擦除 |
| 核心参数 | Transition Completion（过渡完成）：0 ~ 100%，默认 0% |
| | Start Angle（起始角度）：0 ~ 360 度，默认 0 |
| | Wipe Center（擦除中心）：中心点 |
| | Wipe（擦除方向）：Clockwise / Counterclockwise / Both |
| | Feather（羽化）：0 ~ 2000，默认 0 |
| 典型应用 | 扫描转场、时钟擦除、圆形进度、雷达效果 |

#### Venetian Blinds（百叶窗）

| 项目 | 内容 |
|------|------|
| 中文名 | 百叶窗 |
| 功能描述 | 以百叶窗条纹的方式进行过渡 |
| 核心参数 | Transition Completion（过渡完成）：0 ~ 100%，默认 0% |
| | Direction（方向）：0 ~ 360 度，默认 0 |
| | Width（宽度）：1 ~ 3200，默认 40 |
| | Feather（羽化）：0 ~ 2000，默认 0 |
| 典型应用 | 百叶窗转场、条纹过渡、复古转场效果 |

#### CC Grid Wipe

| 项目 | 内容 |
|------|------|
| 中文名 | CC网格擦除 |
| 功能描述 | 以网格扩展的方式进行擦除 |
| 核心参数 | Completion（完成度）：0 ~ 100%，默认 0% |
| | Center（中心）：擦除中心 |
| | Rotation（旋转）：0 ~ 360 度，默认 0 |
| | Tiles X/Y：XY方向瓦片数 |
| | Border（边框）：边框宽度 |
| | Feather（羽化）：边缘柔化 |
| 典型应用 | 网格转场、扩散效果、方块过渡 |

#### CC Image Wipe

| 项目 | 内容 |
|------|------|
| 中文名 | CC图像擦除 |
| 功能描述 | 基于参考图像的亮度进行擦除 |
| 核心参数 | Completion（完成度）：0 ~ 100%，默认 0% |
| | Layer（图层）：参考图层 |
| | Softness（柔化）：0 ~ 50，默认 10 |
| | Gradient Layer（渐变图层） |
| | Auto Softness（自动柔化） |
| 典型应用 | 自定义形状转场、Logo揭示、复杂图形过渡 |

#### CC Jaws

| 项目 | 内容 |
|------|------|
| 中文名 | CC锯齿擦除 |
| 功能描述 | 创建锯齿状的擦除效果 |
| 核心参数 | Completion（完成度）：0 ~ 100%，默认 0% |
| | Center（中心）：中心点 |
| | Direction（方向）：0 ~ 360 度，默认 0 |
| | Width（宽度）：0 ~ 100，默认 30 |
| | Amount（数量）：1 ~ 100，默认 20 |
| 典型应用 | 锯齿转场、牙齿状过渡、特殊形状擦除 |

#### CC Light Wipe

| 项目 | 内容 |
|------|------|
| 中文名 | CC光效擦除 |
| 功能描述 | 带光效的擦除过渡 |
| 核心参数 | Completion（完成度）：0 ~ 100%，默认 0% |
| | Center（中心）：中心点 |
| | Direction（方向）：0 ~ 360 度，默认 0 |
| | Shape（形状）：多种形状 |
| | Intensity（强度）：0 ~ 100，默认 50 |
| | Color（颜色）：光效颜色 |
| 典型应用 | 光效转场、发光过渡、魔法效果 |

#### CC Radial Scale Wipe

| 项目 | 内容 |
|------|------|
| 中文名 | CC径向缩放擦除 |
| 功能描述 | 从中心缩放的径向擦除效果 |
| 核心参数 | Completion（完成度）：0 ~ 100%，默认 0% |
| | Center（中心）：中心点 |
| | Edge Thickness（边缘厚度）：0 ~ 1，默认 0.25 |
| | Edge Softness（边缘柔化）：0 ~ 1，默认 0.25 |
| | Flip（翻转） |
| 典型应用 | 缩放转场、圆形过渡、扩散效果 |

#### CC Twister

| 项目 | 内容 |
|------|------|
| 中文名 | CC扭转擦除 |
| 功能描述 | 以扭转的方式进行转场 |
| 核心参数 | Completion（完成度）：0 ~ 100%，默认 0% |
| | Center（中心）：中心点 |
| | Shape（形状）：Circle / Square |
| | Reverse（反转） |
| 典型应用 | 扭转转场、螺旋过渡、漩涡效果 |

---

### 2.13 时间（Time）

#### CC Force Motion Blur

| 项目 | 内容 |
|------|------|
| 中文名 | CC强制运动模糊 |
| 功能描述 | 为快速运动的物体强制添加运动模糊 |
| 核心参数 | Motion Blur Samples（运动模糊采样）：2 ~ 32，默认 8 |
| | Shutter Angle（快门角度）：0 ~ 720，默认 180 |
| | Shutter Phase（快门相位）：-360 ~ 360，默认 0 |
| 典型应用 | 增强运动模糊、快速物体模糊、补帧后处理 |

#### CC Time Blend

| 项目 | 内容 |
|------|------|
| 中文名 | CC时间混合 |
| 功能描述 | 混合当前帧和前后帧，创建拖影效果 |
| 核心参数 | Time Offset (sec)（时间偏移）：-10 ~ 10 秒，默认 0 |
| | Blend With Original（与原始混合）：0 ~ 100%，默认 50% |
| 典型应用 | 拖影效果、运动残影、回声效果 |

#### CC Wide Time

| 项目 | 内容 |
|------|------|
| 中文名 | CC宽时 |
| 功能描述 | 模拟慢快门的时间累积效果 |
| 核心参数 | Forward Steps（向前步数）：0 ~ 200，默认 10 |
| | Backward Steps（向后步数）：0 ~ 200，默认 10 |
| 典型应用 | 慢快门效果、光轨效果、运动轨迹 |

#### Echo（拖尾）

| 项目 | 内容 |
|------|------|
| 中文名 | 拖尾 / 回声 |
| 功能描述 | 将多个时间帧叠加，创建拖尾和残影效果 |
| 核心参数 | Echo Time (seconds)（回波时间）：-5 ~ 5 秒，默认 0.033 |
| | Number of Echoes（回波数量）：1 ~ 200，默认 3 |
| | Starting Intensity（起始强度）：0 ~ 10，默认 1 |
| | Decay（衰减）：0 ~ 10，默认 0.5 |
| | Echo Operator（回波运算）：Add / Maximum / Minimum / Screen / Composite In Back / Composite In Front / Blend |
| 典型应用 | 拖尾效果、残影动画、运动轨迹、光剑效果 |

#### Posterize Time（色调分离时间）

| 项目 | 内容 |
|------|------|
| 中文名 | 色调分离时间 / 抽帧 |
| 功能描述 | 降低图层的帧率，创建跳帧效果 |
| 核心参数 | Frame Rate（帧率）：0.01 ~ 99，默认 8 |
| 典型应用 | 跳帧效果、定格动画、复古效果、低帧率风格 |

#### Time Difference（时间差值）

| 项目 | 内容 |
|------|------|
| 中文名 | 时间差值 |
| 功能描述 | 比较两个时间点的图像差异 |
| 核心参数 | Target（目标）：目标图层 |
| | Time Offset (sec)（时间偏移）：-30 ~ 30 秒，默认 0 |
| | Contrast（对比度）：0 ~ 200，默认 100 |
| | Absolute Difference（绝对差值） |
| | Alpha Channel（Alpha通道）：Original / Full / Lightness / Hue / Saturation |
| 典型应用 | 运动检测、差异分析、边缘检测、故障效果 |

#### Time Displacement（时间置换）

| 项目 | 内容 |
|------|------|
| 中文名 | 时间置换 |
| 功能描述 | 根据置换图的亮度，用不同时间的像素替换当前像素 |
| 核心参数 | Time Displacement Layer（时间置换图层）：置换参考图 |
| | Max Displacement Time (sec)（最大置换时间）：-10 ~ 10 秒，默认 1 |
| | Time Resolution (frames/sec)（时间分辨率）：1 ~ 120，默认 30 |
| | If Layer Sizes Differ（如果图层大小不同）：Stretch Map to Fit / Center Map |
| 典型应用 | 液态时间、扭曲效果、时光倒流、创意特效 |

#### Timewarp（时间扭曲）

| 项目 | 内容 |
|------|------|
| 中文名 | 时间扭曲 |
| 功能描述 | 高质量的变速工具，支持帧混合和像素运动估计 |
| 核心参数 | Method（方法）：Whole Frames / Frame Mix / Pixel Motion |
| | Adjust Time By（调整时间方式）：Speed / Source Frame |
| | Speed（速度）：1 ~ 10000%，默认 100% |
| | Source Frame（源帧）：对应帧位置 |
| | Tuning（调整）：Vector Detail / Error Threshold etc.（用于Pixel Motion） |
| | Motion Blur（运动模糊）：开关和参数 |
| | Matte Layer（蒙版图层）：可选蒙版 |
| 典型应用 | 变速调整、慢动作、快进、帧率转换 |

---

### 2.14 文字（Text）

#### Basic Text（基本文字）

| 项目 | 内容 |
|------|------|
| 中文名 | 基本文字 |
| 功能描述 | 创建基础文字，支持简单的文字属性控制 |
| 核心参数 | Edit Text（编辑文字）：输入文字内容 |
| | Font（字体）：选择字体 |
| | Style（样式）：Regular / Bold / Italic / Bold Italic |
| | Direction（方向）：Horizontal / Vertical |
| | Alignment（对齐）：Left / Center / Right |
| | Position（位置）：文字位置 |
| | Fill and Stroke（填充和描边）：颜色和描边设置 |
| | Size（大小）：0 ~ 1024，默认 60 |
| | Tracking（字间距）：-50 ~ 500，默认 0 |
| | Line Spacing（行间距）：0 ~ 500，默认 10 |
| 典型应用 | 基础文字、快速文字元素、简单文字动画 |

#### Numbers（数字）

| 项目 | 内容 |
|------|------|
| 中文名 | 数字 |
| 功能描述 | 创建动态数字效果，支持多种数字格式和动画 |
| 核心参数 | Format（格式）：Number / Timecode / Short Date / Long Date etc. |
| | Type（类型）：Number / Leading Zero / English Words etc. |
| | Random Values（随机值）：随机数字 |
| | Value/Offset/Random Max：数值控制 |
| | Decimal Places（小数位数）：0 ~ 10，默认 0 |
| | Current Time/Date（当前时间/日期）：使用系统时间 |
| | Position / Size / Tracking：位置/大小/字间距 |
| | Fill and Stroke：填充和描边 |
| 典型应用 | 数字动画、计数器、时间码显示、数据可视化 |

#### Path Text（路径文字）

| 项目 | 内容 |
|------|------|
| 中文名 | 路径文字 |
| 功能描述 | 让文字沿路径排列，支持路径动画 |
| 核心参数 | Path Options（路径选项）：形状类型/控制点/切线 |
| | Shape Type（形状类型）：Bezier / Circle / Line |
| | Control Points（控制点）：路径控制点 |
| | Fill and Stroke（填充和描边） |
| | Character（字符）：大小/字间距/方向 |
| | Paragraph（段落）：对齐/边距 |
| | Advanced（高级）：可见字符/抖动/基线偏移 |
| 典型应用 | 路径文字、曲线文字、流动文字、文字动画 |

#### Timecode（时间码）

| 项目 | 内容 |
|------|------|
| 中文名 | 时间码 |
| 功能描述 | 生成时间码显示 |
| 核心参数 | Display Format（显示格式）：SMPTE HH:MM:SS:FF / Frames etc. |
| | Time Units（时间单位）：24 / 25 / 30 / 48 / 50 / 60 fps |
| | Drop Frame（丢帧） |
| | Starting Frame（起始帧）：起始帧号 |
| | Text Position / Text Size：文字位置/大小 |
| | 4 Field / Field Symbol：场标记 |
| | Label Text / Label Opacity：标签文字/不透明度 |
| 典型应用 | 时间码显示、测试卡、后期制作参考 |

---

### 2.15 实用工具（Utility）

#### Cineon Converter（Cineon转换器）

| 项目 | 内容 |
|------|------|
| 中文名 | Cineon转换器 |
| 功能描述 | 在Cineon文件和标准视频之间转换色彩 |
| 核心参数 | Converter Type（转换类型）：Linear to Log / Log to Linear etc. |
| | 10 Bit Black / White：10位黑/白值 |
| | Internal Black / White：内部黑/白值 |
| | Gamma（伽马）：伽马值 |
| | Highlight Rolloff（高光衰减） |
| 典型应用 | 胶片色彩转换、Cineon素材处理、后期调色流程 |

#### Color Profile Converter（颜色配置文件转换器）

| 项目 | 内容 |
|------|------|
| 中文名 | 颜色配置文件转换器 |
| 功能描述 | 在不同颜色配置文件之间转换 |
| 核心参数 | Input Profile（输入配置文件） |
| | Output Profile（输出配置文件） |
| | Intent（渲染意图）：Perceptual / Relative Colorimetric etc. |
| | Use Black Point Compensation（使用黑点补偿） |
| 典型应用 | 色彩空间转换、色彩管理、跨设备颜色匹配 |

#### Grow Bounds（范围增长）

| 项目 | 内容 |
|------|------|
| 中文名 | 范围增长 |
| 功能描述 | 增加图层的渲染范围，避免效果被裁切 |
| 核心参数 | Pixels（像素）：0 ~ 2000，默认 0 |
| 典型应用 | 解决效果边缘裁切、扩展图层边界、模糊/发光边缘修复 |

#### HDR Compander（HDR压缩扩展器）

| 项目 | 内容 |
|------|------|
| 中文名 | HDR压缩扩展器 |
| 功能描述 | 压缩或扩展HDR图像的动态范围 |
| 核心参数 | Mode（模式）：Compress / Expand |
| | Gain（增益）：0 ~ 10，默认 1 |
| | Gamma（伽马）：0.01 ~ 10，默认 1 |
| 典型应用 | HDR处理、动态范围调整、曝光控制 |

#### HDR Highlight Compression（HDR高光压缩）

| 项目 | 内容 |
|------|------|
| 中文名 | HDR高光压缩 |
| 功能描述 | 压缩HDR图像的高光区域 |
| 核心参数 | Amount（数量）：0 ~ 100%，默认 50% |
| 典型应用 | HDR高光压制、曝光校正、过曝修复 |

---

## 三、第三方效果插件

### 3.1 Red Giant Trapcode Suite

Trapcode Suite 是业界最著名的粒子和动态图形插件套装，广泛应用于电影、电视和广告制作。

#### Trapcode Particular（粒子系统）

| 项目 | 内容 |
|------|------|
| 中文名 | 粒子系统 |
| 功能描述 | 业界领先的3D粒子系统，可创建火焰、烟雾、雨雪、星云等几乎所有粒子效果 |
| 核心参数 - 发射器 | Emitter Type（发射器类型）：Point / Box / Sphere / Grid / Light / Layer / Layer Grid / OBJ Model |
| | Position X/Y/Z：发射器位置 |
| | Particles/sec（粒子/秒）：发射速率，默认 100 |
| | Emitter Size X/Y/Z：发射器尺寸 |
| | Direction（方向）：Directional / Bi-Directional / Disc / Outwards |
| | Direction Spread / Velocity / Velocity Random / Velocity from Motion |
| 核心参数 - 粒子 | Life [sec]（寿命）：粒子存活时间，默认 3 |
| | Particle Type（粒子类型）：Glow Sphere / Star / Cloudlet / Streaklet / Sprite / Sprite Color / Sprite Fill / Texture / Textured Polygon / Motion Polygon / Glow Sphere (No DOF) / Star (No DOF) / Cloudlet (No DOF) |
| | Sphere Feather / Cloudlet Feather：粒子羽化 |
| | Size（大小）：粒子大小，默认 6 |
| | Size over Life：寿命期间大小变化曲线 |
| | Opacity / Opacity over Life：不透明度及其变化 |
| | Set Color（设置颜色）：At Birth / Over Life / Random from Gradient |
| | Color（颜色）：粒子颜色 |
| | Color over Life：寿命期间颜色变化 |
| | Color Random：颜色随机性 |
| | Transfer Mode（混合模式）：Add / Screen / Lighten / Normal |
| | Glow / Glow Size / Glow Opacity：发光控制 |
| 核心参数 - 物理 | Physics Model（物理模型）：Air / Bounce |
| | Gravity（重力）：重力大小 |
| | Physics Time Factor（物理时间因子）：时间缩放 |
| | Air → Wind X/Y/Z：风力 |
| | Air → Turbulence Field / Affect Position / Affect Size / Affect Opacity：湍流场 |
| | Air → Spin Amplitude / Spin Frequency：旋转 |
| | Air → Wind Visibility：风的可见性 |
| | Air → Air Resistance：空气阻力 |
| | Air → Rotation Speed：旋转速度 |
| 核心参数 - 辅助系统 | Emit（发射）：Off / Continuously / At Bounce Event / At Contact Event |
| | Particles / sec（辅助粒子/秒） |
| | Type / Life / Size / Velocity / Color：辅助粒子参数 |
| 核心参数 - 可见性 | Far Vanish / Far Start Falloff：远处消失/开始衰减 |
| | Near Start Falloff / Near Vanish：近处开始衰减/消失 |
| | Z at Current Frame：当前帧Z深度 |
| | Opacity Falloff：不透明度衰减曲线 |
| 核心参数 - 动态模糊 | Motion Blur（运动模糊）：On / Off |
| | Shutter Angle / Shutter Phase / Type / Levels |
| 典型应用 | 火焰、烟雾、爆炸、粒子特效、魔法效果、星空、雪花、雨、光效 |

#### Trapcode Form（形状粒子）

| 项目 | 内容 |
|------|------|
| 中文名 | 形状粒子 / 形态 |
| 功能描述 | 基于网格的3D粒子系统，粒子固定在空间中，可受音频和分形场影响而变形 |
| 核心参数 - 基础 | Base Form（基础形态）：Box-Grid / Box-Strings / Sphere-Layered / Sphere-String / Orbs / OBJ Model / Light S / Audio Reactors (legacy) |
| | Size X/Y/Z：尺寸 |
| | Particles in X/Y/Z：各轴粒子数 |
| | Position / Rotation / Pivot：位置/旋转/枢轴 |
| | Particle Density（粒子密度） |
| 核心参数 - 粒子 | Particle Type：Sphere / Glow Sphere / Star / Cloudlet / Streaklet / Sprite etc. |
| | Size / Opacity / Color：粒子属性 |
| | Size over X/Y/Z：各轴大小变化 |
| 核心参数 - 快速映射 | Layer Maps（图层映射）：用图层映射粒子属性 |
| | Color & Alpha / Displacement / Fractal Strengthening |
| 核心参数 - 分形场 | Fractal Field（分形场）：Affect Size / Affect Opacity / Displace |
| | Displace Mode：Smooth / Spherical / Swirl / Twist / Random |
| | Amplitude / Frequency / Offset / Scale / Complexity |
| | Flow X/Y/Z / Flow Evolution：流动动画 |
| 核心参数 - 球形场 | Spherical Field（球形场）：Strength / Position / Radius / Scale / Feather |
| 核心参数 - 音频反应 | Audio React（音频反应）：选择音频图层 |
| | Reactor 1/2：音频反应器，可控制多种粒子属性 |
| 典型应用 | 音频可视化、抽象形态、3D粒子形态、动态流体效果 |

#### Trapcode Shine（光效扫光）

| 项目 | 内容 |
|------|------|
| 中文名 | 光效 / 扫光 |
| 功能描述 | 创建专业的体积光和光芒效果，模拟光线穿透效果 |
| 核心参数 - 光源点 | Source Point（源点）：光源位置 |
| | Use Mask（使用蒙版）：None / Alpha / Light Transfer |
| | Source Point Alpha：源点Alpha处理 |
| 核心参数 - 光芒 | Ray Length（光线长度）：0 ~ 100，默认 5 |
| | Detai Mode（细节模式）：High / Low |
| | Detail（细节）：0 ~ 20，默认 10 |
| | Boost Light（增强光）：0 ~ 100，默认 30 |
| | Colorize（着色）：None / One Color / 2-Color Gradient / 3-Color Gradient / 5-Color Gradient |
| | Highlight Colors / Mid Highs / Midtones / Mid Lows / Shadows：各区域颜色 |
| | Base On（基于）：Lightness / Luminance / Alpha / Red / Green / Blue |
| 核心参数 - 发光 | Shimmer（闪烁）：Amount / Detail / Phase / Use Loop / Radius / Revolutions |
| | Boost Light：光增强 |
| 核心参数 - 输出 | Source Opacity（源不透明度） |
| | Shine Opacity（光效不透明度） |
| | Transfer Mode（混合模式）：Add / Screen / Overlay etc. |
| | One Pass / Two Pass：单/双通道 |
| 典型应用 | 文字扫光、体积光、太阳光、光芒效果、Logo光效 |

#### Trapcode Starglow（星光）

| 项目 | 内容 |
|------|------|
| 中文名 | 星光 |
| 功能描述 | 为画面高光点创建星形光芒效果，类似星光镜 |
| 核心参数 - 预设 | Preset（预设）：多种星光预设 |
| 核心参数 - 输入 | Input Channel（输入通道）：Lightness / Luminance / Red / Green / Blue / Alpha |
| | Threshold / Threshold Soft（阈值/柔化） |
| | Use Mask（使用蒙版） |
| 核心参数 - 光芒 | Streak Length（条纹长度）：0 ~ 100，默认 20 |
| | Boost Light（增强光）：0 ~ 100，默认 30 |
| | Individual Lengths（单独长度）：8个方向各自长度 |
| | Individual Colors（单独颜色）：8个方向各自颜色 |
| 核心参数 - 闪烁 | Shimmer（闪烁）：Amount / Detail / Phase / Boost Light |
| 核心参数 - 颜色 | Colormap A/B（颜色映射）：多种渐变模式 |
| 核心参数 - 输出 | Source Opacity / Starglow Opacity |
| | Transfer Mode（混合模式） |
| 典型应用 | 星光效果、星芒、镜头高光、钻石闪光、霓虹灯光 |

#### Trapcode Mir（三维几何体）

| 项目 | 内容 |
|------|------|
| 中文名 | 三维几何体 |
| 功能描述 | 创建有机的3D几何形态，可用于地形、抽象形态等 |
| 核心参数 - 形态 | Form（形态）：Plane / Sphere / Cube / OBJ Model / 3D Model |
| | Size / Size Y / Size Z：尺寸 |
| | Subdivisions（细分）：X/Y/Z方向细分 |
| | Rotation / Position / Pivot：变换 |
| 核心参数 - 置换 | Displace（置换）：Amount / Type / Layer / 3D Noise |
| | 3D Noise（3D噪波）：Type / Amplitude / Scale / Octaves / Evolution |
| 核心参数 - 着色 | Shading（着色）：Shading Style / Color / Ambient / Diffuse / Specular / Shininess |
| | Side Mode（侧面模式）：Front Only / Front and Back / Wireframe / Front Side Back etc. |
| 核心参数 - 纹理 | Texture（纹理）：Texture Layer / UV Mapping / Texture Alpha |
| 核心参数 - 音频反应 | Audio React（音频反应）：音频驱动属性变化 |
| 核心参数 - 摄像机 | Camera（摄像机）：AE Camera / Mir Camera |
| 典型应用 | 3D地形、抽象几何体、科幻场景、动态纹理、微观世界 |

#### Trapcode Tao（路径动画）

| 项目 | 内容 |
|------|------|
| 中文名 | 道 / 路径动画 |
| 功能描述 | 沿路径生成几何图形和动画，创建复杂的路径特效 |
| 核心参数 - 路径 | Path Type（路径类型）：Masks / Paths / Preset / 3D Spline / Maya Path |
| | Path Group（路径组）：蒙版路径选择 |
| | Offset / Reverse Path / Taper |
| 核心参数 - 几何 | Geometry Type（几何类型）：Line / Ribbon / Thin Tube / Thick Tube / GeoSphere / Icosahedron / Cube / Torus / Cross Section |
| | Size / Thickness / Rotation / Twist：大小/厚度/旋转/扭曲 |
| | Segments（分段数）：路径分段 |
| 核心参数 - 重复 | Repeat Mode（重复模式）：Off / Specify Amount / Fit to Path |
| | Amount / Offset / Randomize：重复数量/偏移/随机 |
| 核心参数 - 着色 | Shading（着色）：Flat / Smooth / Reflection / Ambient Occlusion |
| | Color / Side Mode / Alpha |
| 核心参数 - 分形 | Fractal（分形）：分形变形 |
| 核心参数 - 音频反应 | Audio React（音频反应） |
| 典型应用 | 路径动画、光线效果、3D路径、抽象线条、DNA链、管道 |

#### Trapcode Echospace（三维拖尾）

| 项目 | 内容 |
|------|------|
| 中文名 | 三维拖尾 |
| 功能描述 | 为3D图层创建重复的拖尾和回声效果 |
| 核心参数 | Repeater（重复器）：重复数量 |
| | Delay（延迟）：延迟时间 |
| | Opacity（不透明度）：不透明度变化 |
| | Scale（缩放）：缩放变化 |
| | Rotation（旋转）：旋转变化 |
| | Position Offset（位置偏移） |
| | Taper（锥度）：首尾锥度 |
| 典型应用 | 3D拖尾、运动残影、路径复制、回声效果 |

#### Trapcode Lux（聚光灯）

| 项目 | 内容 |
|------|------|
| 中文名 | 聚光灯 |
| 功能描述 | 让AE的灯光产生可见的体积光效果 |
| 核心参数 | Light Rays（光线）：光线数量 |
| | Ray Length（光线长度） |
| | Ray Thickness（光线厚度） |
| | Volume（体积）：体积光强度 |
| | Color（颜色）：灯光颜色 |
| | Intensity（强度）：灯光强度 |
| 典型应用 | 体积光、可见灯光、舞台灯光、光束效果 |

#### Trapcode Sound Keys（音频驱动）

| 项目 | 内容 |
|------|------|
| 中文名 | 音频键帧 |
| 功能描述 | 分析音频并生成关键帧，驱动其他效果动画 |
| 核心参数 - 音频设置 | Audio Layer（音频图层）：选择音频 |
| | Audio Duration（音频持续时间） |
| | Audio Offset（音频偏移） |
| 核心参数 - 频谱显示 | Spectrum（频谱）：显示音频频谱 |
| | Range 1/2/3（范围）：三个频率范围 |
| | Keyframe Type（关键帧类型）：Output / Apply to Property |
| 核心参数 - 输出 | Output Min/Max：输出数值范围 |
| | Falloff（衰减）：峰值衰减速度 |
| | Hold（保持）：峰值保持时间 |
| 典型应用 | 音频驱动动画、音乐节奏同步、音频可视化 |

#### Trapcode Horizon（三维地平线）

| 项目 | 内容 |
|------|------|
| 中文名 | 三维地平线 |
| 功能描述 | 创建无限的3D地平线和天空背景 |
| 核心参数 - 天空 | Sky Mode（天空模式）：9-Color Gradient / Layer / 360° Layer |
| | Horizon Color / Mid Color / Zenith Color：地平线/中间/天顶颜色 |
| | 2x Mid Levels / 2x Horizon Levels：更多层级颜色 |
| 核心参数 - 地面 | Ground Mode（地面模式）：Off / 5-Color Gradient / Reflection Layer |
| | Ground Size / Ground Position / Ground Tilt |
| | Ground Color Near / Ground Horizon Color |
| 核心参数 - 摄像机 | Camera（摄像机）：AE Camera / Horizon Camera |
| | Auto-Align to Comp Camera |
| 核心参数 - 光晕 | Glow（光晕）：Threshold / Intensity / Radius |
| 典型应用 | 3D环境背景、天空模拟、地平线、全景背景 |

---

### 3.2 Video Copilot插件

Video Copilot 是知名的AE插件开发商，以高质量和易用性著称。

#### Optical Flares（镜头光晕）

| 项目 | 内容 |
|------|------|
| 中文名 | 光学光晕 / 镜头光晕 |
| 功能描述 | 专业级镜头光晕插件，提供逼真的镜头眩光效果 |
| 核心参数 - 位置 | Position XY（位置）：光晕中心位置 |
| | Position Z（Z轴位置）：深度位置 |
| | Orientation / Rotation / Scale：方向/旋转/缩放 |
| | Brightness（亮度）：0 ~ 1000%，默认 100% |
| 核心参数 - 光晕设置 | Flare Type（光晕类型）：预设多种 |
| | Custom Flares（自定义光晕）：自定义元素组合 |
| | Color（颜色）：整体颜色 |
| | Color Tint（着色）：色调 |
| | Glow（发光）：光晕整体发光 |
| | Streaks（条纹）：光线条纹 |
| 核心参数 - 遮罩 | Source Mask（源蒙版）：限制光晕出现区域 |
| | Layer Mask（图层蒙版）：用图层控制光晕 |
| 核心参数 - 动画 | Twinkle（闪烁）：Amount / Speed / Randomness |
| | Pulse（脉冲）：闪烁脉冲 |
| 核心参数 - 渲染 | Render Mode（渲染模式）：Light Foreground / Light Background / Light Foreground & Background / Color Foreground / Color Background |
| | Motion Blur（运动模糊） |
| 典型应用 | 镜头光晕、太阳光晕、灯光效果、光学特效、电影感 |

#### Element 3D（三维模型）

| 项目 | 内容 |
|------|------|
| 中文名 | 三维模型 / E3D |
| 功能描述 | 高性能3D模型渲染插件，支持模型导入、材质、灯光和动画 |
| 核心参数 - 场景设置 | Scene Interface（场景界面）：场景设置面板 |
| | Import 3D Model：导入模型 |
| | Particle Look：粒子样式 |
| 核心参数 - 组 | Group 1/2/3/4/5：五个模型组 |
| | Group Enable（组开关） |
| | Particle / Object / Layer / Mask：粒子/物体/图层/蒙版模式 |
| 核心参数 - 粒子模式 | Particles / sec（粒子/秒） |
| | Particle Type（粒子类型） |
| | Emitter（发射器）：Point / Box / Sphere / Light / Layer / Nulls |
| | Physics（物理）：Gravity / Air Resistance etc. |
| | Particle Size / Opacity / Rotation |
| 核心参数 - 渲染 | Render Mode（渲染模式）：Full / Wireframe / Depth / Normals etc. |
| | Shading（着色）：Ambient / Diffuse / Specular / Reflection |
| | Environment（环境）：环境贴图 |
| | Material / Texture：材质和纹理 |
| 核心参数 - 变形 | Deform（变形）：Bend / Twist / Taper / Pivot etc. |
| 核心参数 - 世界变换 | World Position / Rotation / Scale：整体变换 |
| 核心参数 - 输出 | Output（输出）：Beauty / Depth / Matte / Specular / Reflection / Normals / Ambient Occlusion |
| | Multi-Pass（多通道输出） |
| 典型应用 | 3D文字、3D Logo、三维模型渲染、产品展示、场景合成 |

#### Saber（能量光效）

| 项目 | 内容 |
|------|------|
| 中文名 | 军刀 / 能量光效 |
| 功能描述 | 创建高质量的能量光效、光剑、霓虹等效果 |
| 核心参数 - 核心 | Core Settings（核心设置）：Core Size / Core Glow / Core Color |
| | Glow Settings（发光设置）：Glow Size / Glow Intensity / Glow Color |
| 核心参数 - 类型 | Preset（预设）：多种光效预设 |
| | Customize Preset（自定义预设） |
| 核心参数 - 图层 | Customize Core（自定义核心）：Text Layer / Mask Layer / Image Layer |
| | Text Layer（文字图层）：用文字做光效 |
| | Mask Layer（蒙版图层）：用蒙版做光效 |
| 核心参数 - 动画 | Offset（偏移）：光效流动 |
| | Taper（锥度）：首尾锥度 |
| | Distort（扭曲）：扭曲效果 |
| 核心参数 - 发光 | Glow Falloff（发光衰减） |
| | Glow Bias（发光偏移） |
| 典型应用 | 光剑效果、霓虹灯光、能量线、魔法效果、描边光效 |

#### Twixtor（超级慢动作）

| 项目 | 内容 |
|------|------|
| 中文名 | 超级慢动作 |
| 功能描述 | 高质量慢动作插件，使用光流法实现极其平滑的变速效果 |
| 核心参数 - 速度控制 | Frame Rate（帧率）：输出帧率 |
| | Speed（速度）：速度百分比 |
| | Time Remap（时间重映射）：自定义时间曲线 |
| | Source Frame（源帧）：源帧位置 |
| 核心参数 - 跟踪 | Motion Sensitivity（运动敏感度） |
| | Tracking Accuracy（跟踪精度） |
| | Motion Blur（运动模糊）：开关和参数 |
| 核心参数 - 智能处理 | Smart Processing（智能处理）：智能补帧算法 |
| | Foreground Bias（前景偏移） |
| 核心参数 - 遮罩 | Foreground / Background Matte：前/背景蒙版 |
| 典型应用 | 超级慢动作、变速特效、帧率转换、高质量慢放 |

#### Sure Target（摄像机目标）

| 项目 | 内容 |
|------|------|
| 中文名 | 摄像机目标 |
| 功能描述 | 自动控制摄像机在多个目标点之间移动，制作巡游动画 |
| 核心参数 - 目标 | Number of Targets（目标数量）：1 ~ 100 |
| | Target 1/2/3...：各目标图层 |
| | Target Position / Point of Interest：目标位置和关注点 |
| 核心参数 - 摄像机 | Camera（摄像机）：选择摄像机 |
| | Auto Focus（自动对焦） |
| 核心参数 - 动画 | Ease In / Ease Out：缓入缓出 |
| | Ease Type（缓动类型） |
| | Hold Time（保持时间） |
| 核心参数 - 路径 | Smooth Path（平滑路径） |
| | Path Curvature（路径曲率） |
| 典型应用 | 摄像机巡游、场景切换、产品展示、空间漫游 |

#### Heat Distortion（热浪扭曲）

| 项目 | 内容 |
|------|------|
| 中文名 | 热浪扭曲 |
| 功能描述 | 模拟热浪、热空气、火焰等引起的空气扭曲效果 |
| 核心参数 - 扭曲 | Distortion Amount（扭曲量）：扭曲强度 |
| | Distortion Scale（扭曲缩放）：噪波大小 |
| | Speed（速度）：动画速度 |
| | Detail（细节）：扭曲细节 |
| 核心参数 - 噪波 | Noise Type（噪波类型）：多种噪波模式 |
| | Noise Evolution（噪波演化） |
| 核心参数 - 遮罩 | Distortion Mask（扭曲蒙版）：限制扭曲区域 |
| 核心参数 - 通道 | Channel Offset（通道偏移）：色差效果 |
| 典型应用 | 热浪效果、火焰扭曲、空气折射、海市蜃楼、热气流 |

---

### 3.3 Boris FX Sapphire（蓝宝石）

Sapphire 是业界最全面的视觉效果插件套装，提供超过250个效果，广泛用于电影和电视行业。

#### 分类概述

| 类别 | 功能说明 | 代表效果 |
|------|----------|----------|
| Lights（灯光） | 各种灯光、光晕、光效 | S_LensFlare, S_Glow, S_Rays |
| Blur + Sharpen（模糊锐化） | 多种模糊和锐化效果 | S_ZDepthBlur, S_MotionBlur |
| Distort（扭曲） | 各类变形扭曲效果 | S_WarpBubble, S_Distort |
| Stylize（风格化） | 艺术和风格化处理 | S_Cartoon, S_Paint |
| Transition（过渡） | 高级转场效果 | S_Dissolve, S_GlowDissolve |
| Time（时间） | 时间相关效果 | S_TimeWarp |
| Render（生成） | 生成类效果 | S_Clouds, S_Gradient |
| Composite（合成） | 合成相关效果 | S_EdgeFlash, S_ZComp |
| Color and Tone（颜色色调） | 调色和色调工具 | S_ColorShift, S_Tint |
| Matte（蒙版） | 蒙版处理工具 | S_Matte, S_SimpleMatte |
| Key and Blend（键控混合） | 键控和混合效果 | S_EdgeBlur, S_Zap |

#### 常用核心效果

**S_Glow（发光）：**
- 功能：高质量发光效果，比内置Glow更细腻
- 核心参数：Threshold / Radius / Intensity / Color
- 应用：电影级发光、柔光效果、氛围渲染

**S_Zap（闪电）：**
- 功能：逼真的闪电和电流效果
- 核心参数：Start/End Point / Thickness / Intensity / Color / Glow
- 应用：闪电特效、电流、能量束、科幻效果

**S_LensFlare（镜头光晕）：**
- 功能：真实的镜头光晕效果，支持自定义元素
- 核心参数：Position / Brightness / Flare Type / Elements
- 应用：电影光晕、太阳光、灯光效果、光学特效

**S_WarpBubble（气泡扭曲）：**
- 功能：有机的气泡状扭曲效果
- 核心参数：Amplitude / Frequency / Speed / Size
- 应用：水面扭曲、热浪、流体效果、有机变形

**S_Clouds（云彩）：**
- 功能：逼真的3D云彩效果
- 核心参数：Cloud Type / Density / Coverage / Lighting
- 应用：天空效果、云层、氛围背景

**S_Rays（光线）：**
- 功能：体积光和神光效果
- 核心参数：Source Point / Num Rays / Length / Intensity
- 应用：神光、体积光、光芒效果、丁达尔效应

**S_Cartoon（卡通）：**
- 功能：高质量卡通风格转换
- 核心参数：Edge Detection / Color Regions / Line Width
- 应用：卡通风格、动漫效果、艺术化处理

**S_Shake（震动）：**
- 功能：各种相机震动效果
- 核心参数：Amplitude / Frequency / Type
- 应用：地震、爆炸震动、手持效果、冲击感

---

### 3.4 Boris Continuum Complete (BCC)

Boris Continuum Complete (BCC) 是另一款顶级插件套装，提供超过350个效果和过渡。

#### 分类概述

| 类别 | 功能说明 |
|------|----------|
| 3D Objects（3D物体） | 3D文字、形状和物体 |
| Art Looks（艺术外观） | 各种艺术风格效果 |
| Blur and Sharpen（模糊锐化） | 模糊和锐化类效果 |
| Color and Tone（颜色色调） | 调色和颜色校正 |
| Image Restoration（图像修复） | 图像修复和增强 |
| Keying and Matte（键控蒙版） | 抠像和蒙版工具 |
| Lights（灯光） | 灯光和光效 |
| Match Move（匹配移动） | 跟踪和匹配移动 |
| Particles（粒子） | 粒子效果 |
| Perspective（透视） | 透视和3D效果 |
| Stylize（风格化） | 风格化效果 |
| Textures（纹理） | 纹理生成 |
| Time（时间） | 时间效果 |
| Transitions（过渡） | 转场效果 |
| Warp（扭曲） | 扭曲变形 |

#### 常用核心效果

**BCC+3D Objects：**
- 功能：创建3D文字和形状
- 应用：3D标题、立体Logo、3D图形

**BCC Film Glow（电影发光）：**
- 功能：电影级发光效果
- 应用：柔光、电影感、氛围光

**BCC Color Match（颜色匹配）：**
- 功能：快速匹配两个素材的颜色
- 应用：色彩统一、多机位匹配、合成调色

**BCC Magic Sharp（魔法锐化）：**
- 功能：智能锐化，增强细节
- 应用：视频清晰度提升、细节增强

**BCC Chroma Key（色度键）：**
- 功能：高级抠像工具
- 应用：绿屏抠像、蓝屏抠像

**BCC Light Sweep（扫光）：**
- 功能：扫光效果
- 应用：文字光效、Logo扫光、转场光效

**BCC Particle System（粒子系统）：**
- 功能：2D粒子系统
- 应用：粒子效果、火花、烟雾

**BCC Titled Film（标题胶片）：**
- 功能：复古电影效果
- 应用：复古风格、老电影效果

---

### 3.5 其他重要插件

#### Duik Bassel（骨骼绑定）

| 项目 | 内容 |
|------|------|
| 中文名 | 骨骼绑定 |
| 功能描述 | 强大的2D骨骼绑定和角色动画工具集 |
| 核心功能 | Auto-rig（自动绑定）：一键为角色创建骨骼系统 |
| | Bones（骨骼）：骨骼创建和控制 |
| | Controllers（控制器）：各种控制器 |
| | IK/FK（正向/反向运动学） |
| | DUIK Tools：各种动画辅助工具 |
| | Morphing（变形）：形状变形 |
| | Camera & Tools：摄像机工具 |
| | Constraint（约束）：各种约束控制 |
| 典型应用 | 角色动画、人物绑定、MG动画、骨骼动画 |

#### Motion4（运动图形）

| 项目 | 内容 |
|------|------|
| 中文名 | 运动图形 |
| 功能描述 | Cinema 4D风格的运动图形工具，用于创建复杂的动态图形 |
| 核心功能 | Cloner（克隆器）：复制图层到网格/径向/对象 |
| | Effector（效果器）：效果器控制克隆属性 |
| | Fracture（破碎）：蒙版破碎效果 |
| | Plain / Random / Formula / Step：各种效果器 |
| | Tracer（追踪器）：追踪运动轨迹 |
| 典型应用 | 动态图形、克隆动画、阵列效果、MG动画 |

#### Overlord（AI导入）

| 项目 | 内容 |
|------|------|
| 中文名 | AI导入 |
| 功能描述 | 将Illustrator的形状和图层直接传输到After Effects |
| 核心功能 | Shapes Transfer（形状传输）：直接传输AI形状 |
| | Layer Structure（图层结构）：保持AI图层结构 |
| | Live Update（实时更新）：AI中修改后AE同步更新 |
| | Groups & Layers（组和图层）：完整的层级支持 |
| 典型应用 | AI到AE工作流、矢量图形动画、Logo动画 |

#### Flow（动画曲线）

| 项目 | 内容 |
|------|------|
| 中文名 | 动画曲线 |
| 功能描述 | 直观的动画曲线编辑工具，提供预设曲线库 |
| 核心功能 | Curve Presets（曲线预设）：多种缓动曲线 |
| | Curve Editor（曲线编辑器）：可视化曲线编辑 |
| | Easy Ease（缓动）：一键应用缓动 |
| | Custom Presets（自定义预设）：保存自定义曲线 |
| | Expressions（表达式）：表达式生成 |
| 典型应用 | 动画曲线调整、缓动效果、运动设计、关键帧优化 |

#### Lumetri Color（高级调色）

| 项目 | 内容 |
|------|------|
| 中文名 | 高级调色 |
| 功能描述 | 专业的调色面板，集成在AE中（PR同款调色工具） |
| 核心功能 | Basic Correction（基础校正）：白平衡/曝光/对比/饱和度 |
| | Creative（创意）：Look预设/Intensity/Amount |
| | Curves（曲线）：RGB曲线/各通道曲线 |
| | Color Wheels（色轮）：阴影/中间调/高光色轮 |
| | HSL Secondary（HSL辅助）：HSL辅助调色 |
| | Vignette（暗角）：Amount/Midpoint/Roundness/Feather |
| 典型应用 | 专业调色、电影级调色、颜色校正、创意调色 |

---

## 四、效果组合方案

### 4.1 战斗场景效果组合

**适用场景：** 动作片、打斗场景、爆炸冲击、战斗画面

**效果堆叠顺序（从上到下）：**

| 序号 | 效果名称 | 核心参数 | 作用 |
|------|----------|----------|------|
| 1 | Lumetri Color | Temperature: 10-15, Tint: 5-10 | 暖色调氛围 |
| 2 | Curves | S曲线增加对比度 | 增强画面对比 |
| 3 | Glow | Threshold: 80%, Radius: 20, Intensity: 2.5 | 高光发光 |
| 4 | Color Balance | Highlight Red: +20, Midtone Red: +10 | 暖色偏向 |
| 5 | Optics Compensation | FOV: 35-40度 | 广角畸变感 |
| 6 | Radial Blur (CC Radial Fast Blur) | Amount: 15-30, Center: 画面中心 | 径向动感模糊 |
| 7 | Lens Distortion (Optics Compensation) | 轻微桶形畸变 | 边缘扭曲 |
| 8 | Vignette (Lumetri) | Amount: -30, Midpoint: 60% | 暗角聚焦 |
| 9 | Add Grain | Amount: 15, Size: 1.2 | 胶片颗粒感 |
| 10 | CC Ripple Pulse | 可选，爆炸时使用 | 冲击波效果 |

**完整参数表：**

```
【战斗场景效果预设】
调整层应用范围：全片战斗片段
1. 基础调色：
   - Lumetri Color
     · Exposure: +0.3
     · Contrast: +20
     · Highlights: -10
     · Shadows: -5
     · Whites: +5
     · Blacks: -5
     · Saturation: -5
     · Temperature: +12 (偏暖)
     · Tint: +5 (偏洋红)
   - Curves
     · 中灰点轻微上提
     · 暗部下压
     · 高光略微上提（S曲线）

2. 光效与模糊：
   - Glow
     · Glow Based On: Color Channels
     · Glow Threshold: 80%
     · Glow Radius: 20
     · Glow Intensity: 2.5
     · Glow Operation: Add
     · Glow Colors: Original Colors
   - CC Radial Fast Blur
     · Amount: 20 (爆炸时可增至50-100)
     · Center: 画面中心或爆炸点
     · Method: Prefer Quality

3. 畸变与动态：
   - Optics Compensation
     · Field of View: 38度
     · View Center: 画面中心
   - Motion Tile (轻微位移)
     · Phase X/Y: 极细微动画（震动效果）

4. 暗角与颗粒：
   - Lumetri Color Vignette
     · Amount: -35
     · Midpoint: 55%
     · Roundness: +15%
     · Feather: 50%
   - Add Grain
     · Amount: 12
     · Size: 1.0
     · Softness: 0.5
     · Mono: on (单色颗粒)
```

**叠加顺序原则：**
调色 → 光效 → 模糊 → 畸变 → 暗角 → 颗粒
（先改变像素颜色，再变形，最后加整体质感）

---

### 4.2 情感场景效果组合

**适用场景：** 情感戏、回忆、慢镜头、温暖场景

**效果堆叠顺序：**

| 序号 | 效果名称 | 核心参数 | 作用 |
|------|----------|----------|------|
| 1 | Photo Filter | Warming Filter (85), Density: 25% | 暖色调 |
| 2 | Brightness & Contrast | Brightness: +5, Contrast: -10 | 柔和低对比 |
| 3 | Gaussian Blur | Blurriness: 2-5 | 柔焦效果 |
| 4 | Glow | Threshold: 70%, Radius: 30, Intensity: 1.5 | 柔光扩散 |
| 5 | Lens Flare (Optical Flares) | Brightness: 30-50% | 光晕梦幻感 |
| 6 | Vignette | Amount: -25, Midpoint: 50% | 暗角聚焦 |
| 7 | Add Grain | Amount: 8-10, Size: 1.5 | 胶片质感 |
| 8 | Fill (淡黄色 + 叠加模式) | Opacity: 10-15%, Mode: Overlay | 整体暖黄 |

**完整参数表：**

```
【情感场景效果预设】
调整层应用范围：回忆/情感片段
1. 色调调整：
   - Photo Filter
     · Filter: Warming Filter (85)
     · Density: 30%
     · Preserve Luminosity: on
   - Color Balance
     · Midtone Red: +15
     · Midtone Yellow: +10
     · Highlight Yellow: +5
   - Hue/Saturation
     · Master Saturation: -10
     · Master Lightness: +5

2. 柔焦效果：
   - Gaussian Blur
     · Blurriness: 3 (正常) / 8-15 (梦幻)
     · Blur Dimensions: Horizontal and Vertical
   - Glow
     · Glow Threshold: 65%
     · Glow Radius: 40
     · Glow Intensity: 1.2
     · Glow Operation: Screen
     · Composite Original: On Top

3. 光晕效果：
   - Lens Flare / Optical Flares
     · Brightness: 30-40%
     · Position: 画面边角
     · Warm色调预设

4. 质感层：
   - Vignette (Lumetri)
     · Amount: -25
     · Midpoint: 60%
     · Roundness: +10
     · Feather: 60%
   - Add Grain
     · Amount: 8
     · Size: 1.5
     · Softness: 0.7
     · Color: 0 (单色)
```

---

### 4.3 科幻场景效果组合

**适用场景：** 科幻片、赛博朋克、未来感、科技感

**效果堆叠顺序：**

| 序号 | 效果名称 | 核心参数 | 作用 |
|------|----------|----------|------|
| 1 | Channel Mixer | Blue +10 in Red, Red +10 in Blue | 青色调 |
| 2 | Curves | 蓝通道上提，红通道下压 | 赛博朋克调色 |
| 3 | Glow | Threshold: 60%, Radius: 25, Intensity: 3.0 | 霓虹发光 |
| 4 | Optics Compensation | FOV: 45度 | 广角感 |
| 5 | Chromatic Aberration (CC Vector Blur) | 轻微色偏 | 色差效果 |
| 6 | Scan Lines (Grid + 低不透明度) | Opacity: 5-8% | 扫描线 |
| 7 | Noise | Amount: 3-5% | 噪波质感 |
| 8 | Vignette | Amount: -40, Midpoint: 40% | 深暗角 |
| 9 | Colorama | 低强度，颜色映射 | 色彩错位感 |

**完整参数表：**

```
【科幻场景效果预设】
调整层应用范围：科幻/赛博朋克场景
1. 调色：
   - Lumetri Color
     · Temperature: -15 (冷调)
     · Tint: -10 (偏绿)
     · Exposure: 0
     · Contrast: +15
     · Saturation: +5
     · Highlights: -15
     · Shadows: +5
   - Curves
     · Blue: 中灰点上提
     · Red: 暗部下压
     · Green: 中间调微提
   - Hue/Saturation
     · Blues: +20 Saturation
     · Cyans: +15 Saturation
     · Reds: -10 Saturation

2. 发光效果：
   - Glow
     · Glow Threshold: 55%
     · Glow Radius: 25
     · Glow Intensity: 3.0
     · Glow Operation: Add
     · Glow Colors: A & B Colors
     · Color A: 青色 (#00FFFF)
     · Color B: 紫色 (#FF00FF)
     · Color Looping: Sawtooth In

3. 光学效果：
   - Optics Compensation
     · Field of View: 42度
   - RGB分裂 (可用Shift Channels + 位移模拟)
     · Red: 向右偏移1-2像素
     · Blue: 向左偏移1-2像素
     · (通过两个调整层+Set Channels实现)

4. 扫描线：
   - Grid
     · Size From: Height Slider
     · Height: 2-4 (细线)
     · Border: 0.5
     · Color: 白色
     · Opacity: 5-8%
     · Blending Mode: Overlay
     · 或使用 Fractal Noise + 极坐标

5. 暗角与颗粒：
   - Vignette
     · Amount: -40
     · Midpoint: 35%
     · Roundness: 0
     · Feather: 40%
   - Fractal Noise
     · Opacity: 5%
     · Blending Mode: Overlay
     · Uniform Scaling: on
     · Scale: 150
     · Complexity: 3
```

---

### 4.4 复古场景效果组合

**适用场景：** 老电影、80年代复古、怀旧、纪录片历史片段

**效果堆叠顺序：**

| 序号 | 效果名称 | 核心参数 | 作用 |
|------|----------|----------|------|
| 1 | Tint / Tritone | 暖棕色调 | 双色电影感 |
| 2 | Posterize | Levels: 10-15 | 色调分离 |
| 3 | Add Grain | Amount: 25-35, Size: 1.5-2.0 | 胶片颗粒 |
| 4 | Dust & Scratches (Grain + Noise) | 划痕和灰尘 | 老电影质感 |
| 5 | Vignette | Amount: -45, Midpoint: 45% | 重暗角 |
| 6 | Color Balance | Midtone Yellow: +20 | 泛黄效果 |
| 7 | Brightness & Contrast | Contrast: +15 | 对比度增强 |
| 8 | Blur (轻微) | Blurriness: 0.5-1 | 轻微柔化 |
| 9 | Posterize Time | Frame Rate: 12-18 fps | 跳帧效果 |
| 10 | 划痕素材叠加 | 混合模式 Screen | 胶片划痕 |

**完整参数表：**

```
【复古场景效果预设】
调整层应用范围：复古/历史片段
1. 色调处理：
   - Tritone
     · Highlight: 浅黄 #F5E6C8
     · Midtones: 棕黄 #C4A35A
     · Shadows: 深棕 #3D2B1F
     · Blend With Original: 40%
   - Photo Filter
     · Filter: 自定义深黄色
     · Density: 20%
   - Hue/Saturation
     · Master Saturation: -25
     · Master Lightness: +3

2. 色调分离：
   - Posterize
     · Level: 12
   - 配合 Blend With Original 调整强度

3. 胶片颗粒：
   - Add Grain
     · Preset: 8mm Film 或 16mm Film
     · Amount: 30
     · Size: 1.8
     · Softness: 0.6
     · Color: 30% (轻微彩色颗粒)
   - Noise HLS
     · Lightness: 10
     · Grain Size: 8

4. 划痕与灰尘：
   - 方法一：使用划痕素材叠加
     · 素材：老电影划痕视频
     · 混合模式：Screen / Add
     · 不透明度：20-30%
   - 方法二：使用 Fractal Noise 模拟
     · 类型：Dynamic Progressive
     · 对比度：极高
     · 亮度：很高
     · 混合模式：Screen
     · 不透明度：10-15%

5. 暗角与边框：
   - Vignette
     · Amount: -45
     · Midpoint: 40%
     · Roundness: -10 (更方)
     · Feather: 30%
   - 可选：添加黑色边框
     · 使用矩形蒙版 + 反选
     · 或使用 Stroke 效果

6. 动态效果：
   - Posterize Time
     · Frame Rate: 15 fps (可选)
   - 轻微抖动
     · 位置关键帧 + 微小随机偏移
     · 或使用 Wiggle 表达式
```

---

### 4.5 悬疑场景效果组合

**适用场景：** 悬疑片、恐怖片、惊悚场景、氛围营造

**效果堆叠顺序：**

| 序号 | 效果名称 | 核心参数 | 作用 |
|------|----------|----------|------|
| 1 | Brightness & Contrast | Brightness: -10, Contrast: +20 | 高反差 |
| 2 | Hue/Saturation | Saturation: -30 ~ -50 | 低饱和 |
| 3 | Curves | 暗部压低，高光保留 | 暗部细节丢失 |
| 4 | Tint | 蓝绿色调 | 冷色调 |
| 5 | Gaussian Blur | Blurriness: 0.5-2 | 轻微模糊 |
| 6 | Noise | Amount: 5-8% | 颗粒噪点 |
| 7 | Vignette | Amount: -50, Midpoint: 30% | 重暗角 |
| 8 | Flicker (Strobe Light) | 低频率闪烁 | 不稳定感 |
| 9 | Color Balance | Shadow Blue: +15 | 阴影偏蓝 |

**完整参数表：**

```
【悬疑场景效果预设】
调整层应用范围：悬疑/惊悚片段
1. 调色：
   - Lumetri Color
     · Exposure: -0.3 (偏暗)
     · Contrast: +25 (高对比)
     · Highlights: -20 (压暗高光)
     · Shadows: -15 (更深的暗部)
     · Whites: -10
     · Blacks: -5
     · Saturation: -40 (低饱和)
     · Temperature: -5 (偏冷)
     · Tint: -5 (偏绿)
   - Curves
     · RGB: S曲线，暗部更深
     · Blue: 阴影微提（蓝调）
     · Green: 中间调微提（绿调）

2. 模糊与柔化：
   - Fast Box Blur
     · Blurriness: 1.5
     · Blur Dimensions: Horizontal and Vertical
   - 可配合 Blend With Original 调整

3. 噪点与颗粒：
   - Add Grain
     · Amount: 10
     · Size: 1.0
     · Softness: 0.5
     · Mono: on
   - 或使用 Noise
     · Amount of Noise: 6%
     · Use Color Noise: off (单色)

4. 暗角与聚焦：
   - Vignette
     · Amount: -50
     · Midpoint: 25%
     · Roundness: +20 (更圆)
     · Feather: 45%

5. 不稳定感：
   - Strobe Light
     · Strobe Duration: 0.02 秒
     · Strobe Period: 1.5 秒
     · Strobe Operator: Add
     · Strobe Color: 白色
     · Blends With Original: 95%
   - 或使用表达式做亮度轻微波动
     · wiggle(2, 5) 应用到亮度

6. 可选：呼吸感
   - 位置/缩放轻微波动
   · 缩放: [0.5, 1] 速度/强度
   · 模拟手持呼吸感
```

---

## 五、效果插件速查表

### 5.1 按功能索引

| 想要的效果 | 推荐插件 | 说明 |
|-----------|----------|------|
| **调色类** | | |
| 基础调色 | Lumetri Color | 最全面的调色工具 |
| 快速调亮度对比度 | Brightness & Contrast | 简单直接 |
| 精确调色 | Curves | 最灵活的调色工具 |
| 色阶调整 | Levels | 黑白场定义 |
| 色相饱和度调整 | Hue/Saturation | 改变颜色和鲜艳度 |
| 色彩平衡 | Color Balance | 分区域调色 |
| 照片滤镜效果 | Photo Filter | 快速色调调整 |
| 双色调 | Tint / Tritone | 单色/三色效果 |
| 保留颜色 | Leave Color | 突出单一颜色 |
| 通道混合 | Channel Mixer | 创意黑白/调色 |
| 自动调色 | Auto Color / Auto Levels | 一键校正 |
| **光效类** | | |
| 基础发光 | Glow | 最常用发光效果 |
| 镜头光晕 | Lens Flare / Optical Flares | 镜头眩光 |
| 星光 | Trapcode Starglow | 星芒效果 |
| 体积光 | Trapcode Shine | 光束效果 |
| 霓虹灯效果 | Vegas / Saber | 流动光效 |
| 闪电 | Lightning / S_Zap | 闪电电流 |
| 能量光效 | Saber | 光剑/能量束 |
| **模糊类** | | |
| 快速模糊 | Fast Box Blur | 性能优先 |
| 高斯模糊 | Gaussian Blur | 标准模糊 |
| 径向模糊 | CC Radial Fast Blur | 速度感模糊 |
| 镜头模糊 | Lens Blur | 景深虚化 |
| 运动模糊 | CC Force Motion Blur | 增强运动模糊 |
| 双边模糊 | Bilateral Blur | 保留边缘的模糊 |
| **扭曲类** | | |
| 边角定位 | Corner Pin / CC Power Pin | 透视变形 |
| 置换图 | Displacement Map | 扭曲特效 |
| 波浪扭曲 | Wave Warp / Ripple | 波浪效果 |
| 球面化 | Spherize / CC Sphere | 球面效果 |
| 湍流扭曲 | Turbulent Displace | 有机变形 |
| 极坐标 | Polar Coordinates | 圆形效果 |
| 放大镜 | Magnify / CC Lens | 局部放大 |
| **粒子类** | | |
| 3D粒子系统 | Trapcode Particular | 最强大的粒子插件 |
| 形态粒子 | Trapcode Form | 形状粒子 |
| 内置粒子 | CC Particle World / Particle Playground | 基础粒子 |
| 雨雪效果 | CC Rain / CC Snow | 快速雨雪 |
| 气泡 | CC Bubbles / Foam | 气泡效果 |
| 爆炸碎片 | Shatter | 破碎效果 |
| **键控类** | | |
| 专业抠像 | Keylight (1.2) | 行业标准 |
| 颜色键 | Color Key / Linear Color Key | 简单抠像 |
| 亮度键 | Luma Key | 亮度抠像 |
| 差值蒙版 | Difference Matte | 背景差分 |
| 溢色抑制 | Spill Suppressor | 去除色边 |
| 蒙版优化 | Matte Choker / Refine Matte | 精细调整 |
| **时间类** | | |
| 慢动作 | Timewarp / Twixtor | 变速 |
| 拖尾效果 | Echo / CC Wide Time | 运动残影 |
| 抽帧效果 | Posterize Time | 跳帧 |
| **3D类** | | |
| 3D模型 | Element 3D | 3D渲染 |
| 3D球体 | CC Sphere | 快速球形效果 |
| 3D圆柱 | CC Cylinder | 圆柱贴图 |
| 投影 | Drop Shadow / Radial Shadow | 阴影效果 |
| 斜面 | Bevel Alpha / Bevel Edges | 立体边缘 |
| **风格化类** | | |
| 卡通效果 | Cartoon / S_Cartoon | 卡通风格 |
| 马赛克 | Mosaic | 像素化 |
| 查找边缘 | Find Edges | 线稿效果 |
| 浮雕 | Emboss / Color Emboss | 浮雕效果 |
| 粗糙边缘 | Roughen Edges | 毛边效果 |
| 画笔描边 | Brush Strokes | 绘画效果 |
| 万花筒 | CC Kaleida | 对称图案 |
| 塑料效果 | CC Plastic | 凹凸质感 |
| **生成类** | | |
| 渐变 | Ramp / 4-Color Gradient | 渐变背景 |
| 分形噪波 | Fractal Noise / Turbulent Noise | 烟雾/火焰/纹理 |
| 棋盘格/网格 | Checkerboard / Grid | 图案生成 |
| 描边动画 | Stroke / Write-on / Vegas | 绘制动画 |
| 音频可视化 | Audio Spectrum / Audio Waveform | 音乐可视化 |
| **转场类** | | |
| 线性擦除 | Linear Wipe | 基础转场 |
| 径向擦除 | Radial Wipe | 扫描转场 |
| 渐变擦除 | Gradient Wipe | 自定义形状 |
| 卡片擦除 | Card Wipe / CC Grid Wipe | 方块转场 |
| 翻页 | CC Page Turn | 翻书效果 |
| 光圈擦除 | Iris Wipe | 聚光灯转场 |
| 块溶解 | Block Dissolve | 方块溶解 |

### 5.2 按插件名称索引

| 插件名称 | 类别 | 主要用途 |
|---------|------|---------|
| 4-Color Gradient | 生成 | 四色渐变背景 |
| Add Grain | 噪波颗粒 | 添加胶片颗粒 |
| Alpha Levels | 通道 | Alpha色阶调整 |
| Arithmetic | 通道 | 通道数学运算 |
| Auto Color | 颜色校正 | 自动颜色校正 |
| Auto Contrast | 颜色校正 | 自动对比度 |
| Auto Levels | 颜色校正 | 自动色阶 |
| Bevel Alpha | 透视 | Alpha斜面立体 |
| Bevel Edges | 透视 | 边缘斜面立体 |
| Bezier Warp | 扭曲 | 贝塞尔曲线变形 |
| Bilateral Blur | 模糊锐化 | 双边模糊（保留边缘） |
| Block Dissolve | 过渡 | 方块溶解 |
| Brightness & Contrast | 颜色校正 | 亮度对比度调整 |
| Brush Strokes | 风格化 | 画笔描边效果 |
| Bulge | 扭曲 | 膨胀效果 |
| Calculator | 通道 | 计算（注：Calculations） |
| Card Dance | 模拟 | 卡片舞蹈动画 |
| Card Wipe | 过渡/模拟 | 卡片擦除转场 |
| Caustics | 模拟 | 焦散效果 |
| CC Ball Action | 模拟 | 球化动作 |
| CC Bend It | 扭曲 | 弯曲效果 |
| CC Bender | 扭曲 | 弯曲器 |
| CC Blobbylize | 扭曲 | 融化变形 |
| CC Bubbles | 模拟 | 气泡效果 |
| CC Burn Film | 风格化 | 胶片燃烧 |
| CC Cylinder | 透视 | 圆柱效果 |
| CC Drizzle | 模拟 | 细雨效果 |
| CC Flo Motion | 扭曲 | 流动运动 |
| CC Force Motion Blur | 时间 | 强制运动模糊 |
| CC Glass | 风格化 | 玻璃效果 |
| CC Glue Gun | 生成 | 注：常见CC效果 |
| CC Griddler | 扭曲 | 网格扭曲 |
| CC Grid Wipe | 过渡 | 网格擦除 |
| CC Hair | 模拟 | 毛发效果 |
| CC Hexagon | 风格化 | 六边形图案 |
| CC Image Wipe | 过渡 | 图像擦除 |
| CC Jaws | 过渡 | 锯齿擦除 |
| CC Kaleida | 风格化 | 万花筒 |
| CC Lens | 扭曲 | 镜头扭曲 |
| CC Light Wipe | 过渡 | 光效擦除 |
| CC Light Sweep | 生成 | 扫光效果 |
| CC Mr. Mercury | 模拟 | 水银效果 |
| CC Mr. Smoothie | 风格化 | 平滑效果 |
| CC Page Turn | 扭曲/过渡 | 翻页效果 |
| CC Particle Systems II | 模拟 | 粒子系统II |
| CC Particle World | 模拟 | 3D粒子世界 |
| CC Plastic | 风格化 | 塑料质感 |
| CC Power Pin | 扭曲 | 强力边角定位 |
| CC Rain | 模拟 | 下雨效果 |
| CC Radial Fast Blur | 模糊锐化 | 快速径向模糊 |
| CC Radial Scale Wipe | 过渡 | 径向缩放擦除 |
| CC RepeTile | 风格化 | 重复平铺 |
| CC Ripple Pulse | 扭曲 | 波纹脉冲 |
| CC Slant | 扭曲 | 倾斜效果 |
| CC Smear | 扭曲 | 涂抹效果 |
| CC Snow | 模拟 | 下雪效果 |
| CC Sphere | 透视 | 球体效果 |
| CC Split | 扭曲 | 分割效果 |
| CC Split 2 | 扭曲 | 分割效果2 |
| CC Spotlight | 透视 | 聚光灯效果 |
| CC Star Burst | 模拟 | 星爆效果 |
| CC Threshold RGB | 风格化 | RGB阈值 |
| CC Tiler | 扭曲 | 平铺效果 |
| CC Time Blend | 时间 | 时间混合 |
| CC Twister | 过渡 | 扭转擦除 |
| CC Vector Blur | 模糊锐化 | 矢量模糊 |
| CC WarpoMatic | 扭曲 | 扭曲器 |
| CC Wide Time | 时间 | 宽时效果 |
| Change Color | 颜色校正 | 更改颜色 |
| Channel Combiner | 通道 | 通道组合器 |
| Channel Mixer | 颜色校正 | 通道混合器 |
| Checkerboard | 生成 | 棋盘格 |
| Circle | 生成 | 圆形 |
| Color Balance | 颜色校正 | 色彩平衡 |
| Color Emboss | 风格化 | 彩色浮雕 |
| Color Key | 键控 | 颜色键 |
| Color Link | 通道 | 颜色链接 |
| Color Profile Converter | 实用工具 | 颜色配置文件转换 |
| Color Stabilizer | 颜色校正 | 颜色稳定器 |
| Colorama | 颜色校正 | 彩光效果 |
| Compound Arithmetic | 通道 | 复合运算 |
| Corner Pin | 扭曲 | 边角定位 |
| Displacement Map | 扭曲 | 置换图 |
| Drop Shadow | 透视 | 投影 |
| Echo | 时间 | 拖尾效果 |
| Ellipse | 生成 | 椭圆 |
| Emboss | 风格化 | 浮雕 |
| Equalize | 颜色校正 | 均衡 |
| Extract | 键控 | 提取 |
| Fast Box Blur | 模糊锐化 | 快速方框模糊 |
| Fill | 生成 | 填充 |
| Find Edges | 风格化 | 查找边缘 |
| Fractal Noise | 噪波颗粒 | 分形噪波 |
| Foam | 模拟 | 气泡/泡沫 |
| Gamma/Pedestal/Gain | 颜色校正 | 伽马基色增益 |
| Gaussian Blur | 模糊锐化 | 高斯模糊 |
| Glow | 风格化 | 发光 |
| Grid | 生成 | 网格 |
| Grow Bounds | 实用工具 | 范围增长 |
| HDR Compander | 实用工具 | HDR压缩扩展器 |
| HDR Highlight Compression | 实用工具 | HDR高光压缩 |
| Hue/Saturation | 颜色校正 | 色相饱和度 |
| Invert | 通道 | 反转 |
| Inner/Outer Key | 键控 | 内外键 |
| Iris Wipe | 过渡 | 光圈擦除 |
| Keylight (1.2) | 键控 | 专业抠像 |
| Leave Color | 颜色校正 | 保留颜色 |
| Lens Blur | 模糊锐化 | 镜头模糊 |
| Lens Flare | 生成 | 镜头光晕 |
| Levels | 颜色校正 | 色阶 |
| Linear Color Key | 键控 | 线性颜色键 |
| Linear Wipe | 过渡 | 线性擦除 |
| Luma Key | 键控 | 亮度键 |
| Magnify | 扭曲 | 放大 |
| Match Grain | 噪波颗粒 | 匹配颗粒 |
| Matte Choker | 蒙版 | 蒙版收缩 |
| Max | 通道 | 最大（注：Minimax） |
| Mesh Warp | 扭曲 | 网格变形 |
| Minimax | 通道 | 最小最大值 |
| Mirror | 扭曲 | 镜像 |
| Mosaic | 风格化 | 马赛克 |
| Motion Tile | 模糊锐化/风格化 | 运动平铺 |
| Noise | 噪波颗粒 | 噪波 |
| Noise Alpha | 噪波颗粒 | 噪波Alpha |
| Noise HLS | 噪波颗粒 | 噪波HLS |
| Noise HLS Auto | 噪波颗粒 | 自动噪波HLS |
| Offset | 扭曲 | 偏移 |
| Optics Compensation | 扭曲 | 光学补偿 |
| Paint Bucket | 生成 | 注：Paint Bucket |
| Particle Playground | 模拟 | 粒子运动场 |
| Photo Filter | 颜色校正 | 照片滤镜 |
| Polar Coordinates | 扭曲 | 极坐标 |
| Posterize | 风格化 | 色调分离 |
| Posterize Time | 时间 | 色调分离时间 |
| Radial Blur | 模糊锐化 | 径向模糊 |
| Radial Shadow | 透视 | 径向阴影 |
| Radial Wipe | 过渡 | 径向擦除 |
| Ramp | 生成 | 渐变 |
| Refine Hard Matte | 蒙版 | 优化生硬蒙版 |
| Refine Matte | 蒙版 | 优化蒙版 |
| Refine Soft Matte | 蒙版 | 优化柔和蒙版 |
| Remove Color Matting | 通道 | 移除颜色蒙版 |
| Remove Grain | 噪波颗粒 | 移除颗粒 |
| Reshape | 扭曲 | 重塑 |
| Ripple | 扭曲 | 波纹 |
| Roughen Edges | 风格化 | 粗糙边缘 |
| Scatter | 风格化 | 散布 |
| Set Channels | 通道 | 设置通道 |
| Set Matte | 通道 | 设置蒙版 |
| Shatter | 模拟 | 碎片 |
| Shift Channels | 通道 | 转换通道 |
| Sharpen | 模糊锐化 | 锐化 |
| Simple Choker | 蒙版 | 简单抑制 |
| Solid Composite | 通道 | 纯色合成 |
| Spherize | 扭曲 | 球面化 |
| Spill Suppressor | 键控 | 溢色抑制 |
| Stroke | 生成 | 描边 |
| Strobe Light | 风格化 | 闪光灯 |
| Texturize | 风格化 | 纹理 |
| Threshold | 风格化 | 阈值 |
| Tint | 颜色校正 | 染色 |
| Tritone | 颜色校正 | 三色渐变 |
| Turbulent Displace | 扭曲 | 动荡置换 |
| Turbulent Noise | 噪波颗粒 | 湍动噪波 |
| Twirl | 扭曲 | 扭转 |
| Unsharp Mask | 模糊锐化 | 非锐化蒙版 |
| Venetian Blinds | 过渡 | 百叶窗 |
| Wave Warp | 扭曲 | 波浪变形 |
| Wave World | 模拟 | 波形世界 |
| Write-on | 生成 | 书写 |
| Vegas | 生成 | 勾画 |

### 5.3 常用快捷键

| 快捷键 | 功能 |
|--------|------|
| **效果相关** | |
| `E` | 展开所选图层的所有效果 |
| `U` | 展开所有带有关键帧的属性 |
| `UU` | 展开所有修改过的属性 |
| `Shift + E` | ？(注：添加效果后可配合) |
| `Ctrl + Alt + Shift + E` | 应用最近使用的效果 |
| **调整层** | |
| `Ctrl + Alt + Y` | 新建调整层 |
| **关键帧** | |
| `Alt + Shift + 属性快捷键` | 在当前时间添加关键帧 |
| `F9` | 关键帧自动贝塞尔（缓动） |
| `Shift + F9` | 缓入 |
| `Ctrl + Alt + K` | 关键帧助手 |
| **视图控制** | |
| `,` / `.` | 放大/缩小预览 |
| `/` | 适配视图到窗口 |
| `Ctrl + Alt + ;` | 安全框开关 |
| **时间轴** | |
| `J` / `K` | 跳转到上/下一个关键帧 |
| `I` / `O` | 跳转到入点/出点 |
| `Home` / `End` | 跳转到开始/结束 |
| `Space` | 播放/暂停 |
| **混合模式** | |
| `Shift + =` / `Shift + -` | 切换混合模式（上/下一个） |
| **蒙版** | |
| `M` | 展开蒙版路径 |
| `MM` | 展开所有蒙版属性 |
| `F` | 展开蒙版羽化 |
| `T` | 展开不透明度 |
| `S` | 展开缩放 |
| `R` | 展开旋转 |
| `P` | 展开位置 |
| `A` | 展开锚点 |
| **图层操作** | |
| `Ctrl + D` | 复制图层 |
| `Ctrl + Shift + D` | 分离图层 |
| `Alt + [ / ]` | 设置入点/出点到当前时间 |
| `[ / ]` | 移动图层入点/出点到当前时间 |
| `Ctrl + Alt + R` | 时间反向 |
| `Ctrl + T` | 时间伸缩 |
| **预览** | |
| `0` (数字键盘) | RAM预览 |
| `.` (数字键盘) | 逐帧前进 |
| `,` (数字键盘) | 逐帧后退 |
| **工具** | |
| `V` | 选择工具 |
| `H` | 手形工具 |
| `Z` | 缩放工具 |
| `W` | 旋转工具 |
| `Y` | 锚点工具 |
| `Q` | 形状工具组 |
| `G` | 钢笔工具 |
| `T` | 文字工具 |
| `Ctrl + Shift + Q` | 切换笔刷工具 |

---

> **最后更新：** 2026年7月 | **适用版本：** After Effects 2026
>
> 本手册为速查参考，具体参数请以实际软件版本为准。
> 建议结合实际项目多加练习，熟练掌握各类效果的特性和组合技巧。

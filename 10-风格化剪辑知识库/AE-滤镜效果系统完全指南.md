# AE 滤镜效果系统完全指南

> 本指南涵盖 After Effects 效果系统架构、8大效果分类、200+内置效果详解、100+第三方效果概览，以及完整的 ExtendScript 自动化代码实现。

---

## 目录

1. [AE效果系统架构](#1-ae效果系统架构)
2. [色彩校正滤镜](#2-色彩校正滤镜)
3. [模糊与锐化滤镜](#3-模糊与锐化滤镜)
4. [扭曲与变形滤镜](#4-扭曲与变形滤镜)
5. [生成滤镜](#5-生成滤镜)
6. [风格化滤镜](#6-风格化滤镜)
7. [模拟与过渡滤镜](#7-模拟与过渡滤镜)
8. [第三方滤镜系统](#8-第三方滤镜系统)
9. [效果预设与表达式控制](#9-效果预设与表达式控制)
10. [ExtendScript代码实现](#10-extendscript代码实现)

---

## 1. AE效果系统架构

### 1.1 效果分类体系

AE内置效果按功能分为8大类别，每类覆盖不同的视觉处理领域：

| 类别 | 英文名 | 效果数量 | 核心功能 |
|------|--------|---------|---------|
| 色彩校正 | Color Correction | 30+ | 色彩调整、调色、通道操作 |
| 模糊锐化 | Blur & Sharpen | 15+ | 聚焦、景深、运动模糊 |
| 扭曲变形 | Distort | 20+ | 空间变形、液体变形、3D扭曲 |
| 生成 | Generate | 20+ | 填充、渐变、光效、粒子 |
| 模拟 | Simulation | 10+ | 粒子系统、雨雪气泡 |
| 风格化 | Stylize | 20+ | 艺术化、电影感、故障风格 |
| 过渡 | Transition | 10+ | 场景切换过渡效果 |
| 实用 | Utility | 5+ | 色彩空间、HDR、通道管理 |

### 1.2 效果渲染管线

AE效果渲染遵循从内到外的管线，按以下顺序处理：

```
Source Footage
    ↓
Effect 1 (最内层效果)
    ↓
Effect 2
    ↓
...Effect N (最外层效果)
    ↓
Layer Transform (位移/缩放/旋转/透明度)
    ↓
Layer Masks & Track Mattes
    ↓
Blend Mode (混合模式)
    ↓
Comp Level Compositing
    ↓
Adjustment Layer Effects
    ↓
Render Output
```

**关键渲染规则：**
- 效果从上到下依次应用（Effect Controls面板中从上至下）
- 效果先于图层变换（Transform）执行
- 调整图层效果在合成级别作用于所有下方图层
- 预合成（Pre-comp）中的效果在合成时被"烘焙"

### 1.3 效果参数系统

#### Property层级结构

```
Project
  └── Comp
        └── Layer
              └── PropertyGroup (Effect)
                    ├── Property (参数1)
                    │     ├── value (当前值)
                    │     ├── keyframes[] (关键帧数组)
                    │     └── expression (表达式)
                    ├── Property (参数2)
                    └── PropertyGroup (子参数组)
```

#### 可关键帧属性类型

| 类型 | ExtendScript 常量 | 示例 |
|------|-------------------|------|
| 数值 | `PropertyType.PROPERTY` | Blur Radius = 20.0 |
| 颜色 | `PropertyType.PROPERTY` | Color = [1,0,0,1] |
| 角度 | `PropertyType.PROPERTY` | Angle = 45° |
| 点 | `PropertyType.PROPERTY` | Center = [640,360] |
| 下拉菜单 | `PropertyType.PROPERTY` | Blend Mode = 1 |
| 布尔 | `PropertyType.PROPERTY` | Compositing Options |
| 图层选择 | `PropertyType.PROPERTY` | Displacement Map Layer |

#### 表达式控制

效果参数可绑定表达式，实现动态控制：

```javascript
// 绑定到滑块控制
effect("Gaussian Blur")("Blurriness").expression = 'effect("Slider Control")("Slider")';

// 基于时间的动画
effect("Opacity")("Opacity").expression = 'Math.sin(time * 2) * 50 + 50';

// 关联其他图层
effect("Displacement Map")("Horizontal Displacement").expression = 
    'thisComp.layer("Control").effect("Amount")("Slider")';
```

### 1.4 效果合成模式

#### 效果堆叠顺序

效果堆叠遵循**从上到下**的处理顺序，后一个效果接收前一个效果的输出作为输入：

```
原始图层
  → Effect A: Gaussian Blur (先处理)
    → Effect B: Hue/Saturation (后处理，作用于模糊后的结果)
      → Effect C: Levels (最终处理)
        → 输出
```

#### 调整图层效果

调整图层是AE中最强大的效果应用方式：

- **作用范围**：时间轴中位于调整图层下方的所有图层
- **遮罩控制**：调整图层上的遮罩可限制效果影响区域
- **性能优势**：一个调整图层应用效果，避免对每个图层重复添加

#### 预合成效果

预合成时效果应用有两种模式：

1. **Leave all attributes in**：效果留在当前合成，预合成仅包含源图层
2. **Move all attributes into the new composition**：效果随图层移入预合成

---

## 2. 色彩校正滤镜

### 2.1 基础调整效果

#### Brightness & Contrast（亮度与对比度）

| 参数 | 类型 | 范围 | 默认值 | 说明 |
|------|------|------|--------|------|
| Brightness | 数值 | -100~100 | 0 | 整体亮度调整 |
| Contrast | 数值 | -100~100 | 0 | 整体对比度调整 |
| Use Legacy | 布尔 | - | Off | 使用旧版算法 |

```javascript
// ExtendScript: 添加并设置Brightness & Contrast
var effect = layer.Effects.addProperty("ADBE Brightness and Contrast");
effect.property(1).setValue(15);  // Brightness = 15
effect.property(2).setValue(30);  // Contrast = 30
```

#### Curves（曲线）

| 参数 | 类型 | 说明 |
|------|------|------|
| Channel | 下拉菜单 | RGB / Red / Green / Blue / Alpha |
| 曲线点 | 点集合 | 自定义曲线形状 |

```javascript
// ExtendScript: 操作Curves效果
var curvesEffect = layer.Effects.addProperty("ADBE Curves");
var curvesGroup = curvesEffect.property(1); // Curves property group
// 曲线操作需通过关键帧或预设方式设置
```

#### Levels（色阶）

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Channel | 下拉 | RGB/Red/Green/Blue/Alpha | 通道选择 |
| Input Black | 数值 | 0~255 | 黑场输入 |
| Input White | 数值 | 0~255 | 白场输入 |
| Gamma | 数值 | 0.01~9.99 | 灰度系数 |
| Output Black | 数值 | 0~255 | 黑场输出 |
| Output White | 数值 | 0~255 | 白场输出 |

```javascript
// ExtendScript: Levels设置
var levels = layer.Effects.addProperty("ADBE Pro Levels2");
levels.property("Input Black").setValue(10);
levels.property("Input White").setValue(245);
levels.property("Gamma").setValue(1.2);
levels.property("Output Black").setValue(0);
levels.property("Output White").setValue(255);
```

#### Hue/Saturation（色相/饱和度）

| 参数 | 类型 | 范围 | 说明 |
|------|------|------|------|
| Channel Control | 下拉 | Master/Reds/... | 通道选择 |
| Channel Range | 色轮 | - | 通道范围 |
| Master Hue | 角度 | -180~180 | 主色相偏移 |
| Master Saturation | 数值 | -100~100 | 主饱和度 |
| Master Lightness | 数值 | -100~100 | 主亮度 |
| Colorize | 布尔 | - | 着色模式 |
| Colorize Hue | 角度 | 0~360 | 着色色相 |
| Colorize Saturation | 数值 | 0~100 | 着色饱和度 |
| Colorize Lightness | 数值 | -100~100 | 着色亮度 |

```javascript
// ExtendScript: Hue/Saturation
var hue = layer.Effects.addProperty("ADBE HUE SATURATION");
hue.property(3).setValue(45);  // Master Hue = 45°
hue.property(4).setValue(-30); // Master Saturation = -30
hue.property(5).setValue(10);  // Master Lightness = +10
```

#### Color Balance（色彩平衡）

| 参数 | 说明 |
|------|------|
| Shadow Red/Blue/Green Balance | 暗部色彩平衡 |
| Midtone Red/Blue/Green Balance | 中间调色彩平衡 |
| Highlight Red/Blue/Green Balance | 高光色彩平衡 |
| Preserve Luminosity | 保持明度 |

#### Exposure（曝光度）

| 参数 | 范围 | 说明 |
|------|------|------|
| Exposure | -20~20 | 曝光度调整 |
| Offset | -0.5~0.5 | 偏移 |
| Gamma Correction | 0.01~9.99 | 伽马校正 |

### 2.2 专业调色效果

#### Lumetri Color（AE 2026增强版）

AE 2026中的Lumetri Color面板集成度更高，支持完整的专业调色工作流：

| 模块 | 参数 | 说明 |
|------|------|------|
| Basic Correction | Temperature, Tint, Contrast, Highlights, Shadows, Whites, Blacks, Saturation | 基础校正 |
| Creative | Look预设, Faded Film, Sharpen, Vibrance, Saturation | 创意调色 |
| Curves | RGB/Red/Green/Blue/ luminance曲线 | 曲线调色 |
| Color Wheels | 四路调色轮（Master/Shadow/Midtone/Highlight） | 色轮调色 |
| HSL Secondary | 色相/饱和度/亮度限定 + 二次调色 | 限定调色 |
| Vignette | Amount, Midpoint, Roundness, Feather | 暗角效果 |

```javascript
// ExtendScript: Lumetri Color
var lumetri = layer.Effects.addProperty("ADBE Lumetri Color");
// 通过MatchName访问参数
lumetri.property("ADBE Lumetri Color-0001").setValue(6500); // Temperature
lumetri.property("ADBE Lumetri Color-0002").setValue(5);    // Tint
```

#### CC Color Neutralizer

| 参数 | 说明 |
|------|------|
| Method | 补色方法选择 |
| Black, White, Midtones | 各区域色彩偏移 |
| Tint | 整体色调 |

### 2.3 色彩效果

#### Tint（着色）

| 参数 | 说明 |
|------|------|
| Map Black To | 映射黑色的颜色 |
| Map White To | 映射白色的颜色 |
| Amount to Tint | 着色强度 0~100% |

```javascript
// ExtendScript: Tint效果
var tint = layer.Effects.addProperty("ADBE Tint");
tint.property(1).setValue([0.1, 0.1, 0.3, 1]); // Map Black To 深蓝
tint.property(2).setValue([0.8, 0.7, 0.5, 1]); // Map White To 暖白
tint.property(3).setValue(80); // Amount = 80%
```

#### Fill（填充）

| 参数 | 说明 |
|------|------|
| Color | 填充颜色 |
| Invert Fill | 反转填充（仅填充遮罩外部） |
| Horizontal Feather | 水平羽化 |
| Vertical Feather | 垂直羽化 |
| Opacity | 不透明度 |

#### Tritone（三色调）

| 参数 | 说明 |
|------|------|
| Highlights | 高光颜色 |
| Midtones | 中间调颜色 |
| Shadows | 暗部颜色 |
| Blend With Original | 与原始画面混合度 |

#### Colorama（色彩映射）

| 参数 | 说明 |
|------|------|
| Input Phase | 输入相位（通道选择 + 相位偏移） |
| Output Cycle | 输出色环（可自定义色标） |
| Modify | 修改方式（R/G/B/Alpha/All） |
| Blend With Original | 混合度 |

#### CC Toner

| 参数 | 说明 |
|------|------|
| Highlights | 高光颜色 |
| Midtones | 中间调颜色 |
| Shadows | 暗部颜色 |
| Blend | 混合度 |

#### Posterize（色调分离）

| 参数 | 说明 |
|------|------|
| Level | 色阶数量（2~255） |

#### Shift Channels（通道位移）

| 参数 | 说明 |
|------|------|
| Take Alpha From | Alpha通道来源 |
| Take Red From | Red通道来源 |
| Take Green From | Green通道来源 |
| Take Blue From | Blue通道来源 |

### 2.4 色彩空间效果

#### Color Profile Converter（色彩配置文件转换器）

| 参数 | 说明 |
|------|------|
| Input Profile | 输入色彩配置文件 |
| Output Profile | 输出色彩配置文件 |
| Intent | 渲染意图（Perceptual/Saturation/Relative/Absolute） |

#### Grow Bounds（增长边界）

| 参数 | 说明 |
|------|------|
| Pixels | 增长像素数 |

> Grow Bounds 不是色彩效果，但常与色彩效果配合使用——当效果被裁切时，先添加Grow Bounds扩展渲染边界。

#### HDR Compander（HDR压缩扩展器）

| 参数 | 说明 |
|------|------|
| Mode | Compress / Expand |
| Gain | 增益 |
| Gamma | 伽马值 |

### 2.5 通道操作效果

#### Channel Mixer（通道混合器）

| 参数 | 说明 |
|------|------|
| Red-Red, Red-Green, Red-Blue | 红通道的各通道混合比例 |
| Green-Red, Green-Green, Green-Blue | 绿通道的各通道混合比例 |
| Blue-Red, Blue-Green, Blue-Blue | 蓝通道的各通道混合比例 |
| Red-Const, Green-Const, Blue-Const | 各通道常量偏移 |
| Monochrome | 单色模式 |

```javascript
// ExtendScript: Channel Mixer 创建电影胶片感
var mixer = layer.Effects.addProperty("ADBE Channel Mixer");
// Red通道: R=100, G=20, B=10
mixer.property(2).setValue(100);
mixer.property(3).setValue(20);
mixer.property(4).setValue(10);
// Green通道: R=10, G=100, B=20
mixer.property(6).setValue(10);
mixer.property(7).setValue(100);
mixer.property(8).setValue(20);
// Blue通道: R=5, G=15, B=100
mixer.property(10).setValue(5);
mixer.property(11).setValue(15);
mixer.property(12).setValue(100);
```

#### Set Channels（设置通道）

从其他图层或本图层获取通道，支持灰度转换模式。

#### Calculations（计算）

将两个图层的通道进行数学运算（加/减/乘/差值等）。

#### Compound Arithmetic（复合算术）

对图层进行数学运算，支持Add/Subtract/Multiply/Difference等模式。

---

## 3. 模糊与锐化滤镜

### 3.1 模糊效果

#### Gaussian Blur（高斯模糊）

| 参数 | 范围 | 说明 |
|------|------|------|
| Blurriness | 0~300+ | 模糊量 |
| Blur Dimensions | 下拉 | All/Horizontal/Vertical |
| Repeat Edge Pixels | 布尔 | 重复边缘像素 |

```javascript
// ExtendScript: Gaussian Blur
var blur = layer.Effects.addProperty("ADBE Gaussian Blur 2");
blur.property(1).setValue(25);      // Blurriness
blur.property(2).setValue(1);       // Blur Dimensions = All
blur.property(3).setValue(true);    // Repeat Edge Pixels
```

#### Fast Box Blur（快速方框模糊）

| 参数 | 范围 | 说明 |
|------|------|------|
| Blurriness | 0~300+ | 模糊量 |
| Blur Dimensions | 下拉 | All/Horizontal/Vertical |
| Repeat Edge Pixels | 布尔 | 重复边缘像素 |
| Iterations | 1~10 | 迭代次数（越高越平滑） |

> Fast Box Blur 性能优于 Gaussian Blur，是大面积模糊的首选。

#### Camera Lens Blur（摄像机镜头模糊）

| 参数 | 说明 |
|------|------|
| Blurriness | 模糊量 |
| Iris Shape | 光圈形状（Triangle/Square/Pentagon/Hexagon/...） |
| Iris Rotation | 光圈旋转 |
| Iris Roundness | 光圈圆度 |
| Iris Aspect Ratio | 光圈宽高比 |
| Iris Blade Curvature | 光圈叶片曲率 |
| Specular Brightness | 高光亮度 |
| Specular Threshold | 高光阈值 |
| Depth Map Layer | 深度贴图图层 |
| Depth Map Channel | 深度贴图通道 |
| Focal Plane | 焦平面距离 |
| Focal Radius | 焦点半径 |
| Highlight | 高光设置 |

```javascript
// ExtendScript: Camera Lens Blur + 深度图
var clb = layer.Effects.addProperty("ADBE Camera Lens Blur");
clb.property("Blurriness").setValue(30);
clb.property("Iris Shape").setValue(5);  // Hexagon
clb.property("Depth Map Layer").setValue(2); // 指向深度图图层
clb.property("Focal Plane").setValue(128);
```

#### CC Cross Blur（CC交叉模糊）

同时水平和垂直模糊，产生交叉光晕效果。

#### CC Radial Fast Blur（CC径向快速模糊）

| 参数 | 说明 |
|------|------|
| Amount | 径向模糊量 |
| Center | 中心点 |
| Style | 模糊风格 |

#### Directional Blur（方向模糊）

| 参数 | 说明 |
|------|------|
| Direction | 模糊方向（角度） |
| Blur Length | 模糊长度 |

#### Motion Blur（运动模糊）

通过CC Force Motion Blur或Pixel Motion Blur实现，详见3.4节。

### 3.2 锐化效果

#### Unsharp Mask（USM锐化）

| 参数 | 范围 | 说明 |
|------|------|------|
| Amount | 0~500 | 锐化量 |
| Radius | 0.1~100 | 锐化半径 |
| Threshold | 0~255 | 锐化阈值 |

```javascript
// ExtendScript: Unsharp Mask
var usm = layer.Effects.addProperty("ADBE Unsharp Mask");
usm.property(1).setValue(80);   // Amount
usm.property(2).setValue(2.0);  // Radius
usm.property(3).setValue(5);    // Threshold
```

#### Sharpen（锐化）

| 参数 | 范围 | 说明 |
|------|------|------|
| Sharpen Amount | 0~100 | 锐化量 |

### 3.3 景深效果

#### Camera Depth of Field

通过3D摄像机自带景深控制，配合Camera Lens Blur效果实现。

#### 模拟景深工作流

```
1. 创建深度图（灰度图层，近=0/远=255）
2. 添加Camera Lens Blur效果
3. 指定Depth Map Layer
4. 调整Focal Plane和Focal Radius
5. 设置Iris Shape模拟光圈形状
```

#### Tilt-Shift（移轴模拟）

通过多层模糊+遮罩实现移轴效果：

```javascript
// ExtendScript: 移轴模糊模拟
function createTiltShift(layer, bandY, bandHeight, blurAmount) {
    // 添加Fast Box Blur
    var blur = layer.Effects.addProperty("ADBE Fast Box Blur");
    blur.property(1).setValue(blurAmount);
    blur.property(3).setValue(true);
    
    // 在调整图层上创建线性遮罩
    // 注意：实际实现需通过调整图层+遮罩
}
```

### 3.4 运动模糊效果

#### CC Force Motion Blur（CC强制运动模糊）

| 参数 | 说明 |
|------|------|
| Motion Blur Samples | 运动模糊采样数 |
| Override Shutter Angle | 覆盖快门角度 |
| Shutter Angle | 快门角度 |
| Native Motion Blur | 使用原生运动模糊 |

```javascript
// ExtendScript: CC Force Motion Blur
var mb = layer.Effects.addProperty("CC Force Motion Blur");
mb.property(1).setValue(8);    // Samples = 8
mb.property(2).setValue(true); // Override Shutter Angle
mb.property(3).setValue(180);  // Shutter Angle = 180°
```

#### Pixel Motion Blur（像素运动模糊）

| 参数 | 说明 |
|------|------|
| Motion Blur Samples | 采样数 |
| Shutter Angle | 快门角度 |
| Shutter Samples | 快门采样 |
| Vector Detail | 矢量细节 |

#### RSMB (ReelSmart Motion Blur) — 第三方

RE:Vision Effects出品的专业运动模糊插件，自动分析运动并添加物理正确的运动模糊。

---

## 4. 扭曲与变形滤镜

### 4.1 基础扭曲效果

#### Transform（变换）

| 参数 | 说明 |
|------|------|
| Anchor Point | 锚点 |
| Position | 位置 |
| Scale Height/Width | 缩放 |
| Skew | 倾斜 |
| Skew Axis | 倾斜轴 |
| Rotation | 旋转 |
| Opacity | 不透明度 |
| Use Composition Shutter Angle | 使用合成快门角度 |
| Shutter Angle | 快门角度 |

> 注意：Transform效果与图层自身变换独立，可叠加使用。

#### Warp（变形）

| 参数 | 说明 |
|------|------|
| Warp Style | 变形样式（Arc/Lower/Upper/Fish/Bulge/...） |
| Warp Axis | 变形轴 |
| Bend | 弯曲度 |
| H/Vertical Distortion | 水平/垂直扭曲 |

#### Bezier Warp（贝塞尔变形）

| 参数 | 说明 |
|------|------|
| Top Left/Right Vertex | 上左/右顶点 |
| Bottom Left/Right Vertex | 下左/右顶点 |
| Top/Bottom/Left/Right Tangent | 各边切线 |
| Quality | 质量 |

#### Bulge（凸出）

| 参数 | 说明 |
|------|------|
| Horizontal/Vertical Radius | 水平/垂直半径 |
| Bulge Center | 凸出中心 |
| Bulge Height | 凸出高度 |
| Taper Radius | 锥度半径 |
| Pinning | 固定方式 |

#### Magnify（放大镜）

| 参数 | 说明 |
|------|------|
| Shape | 形状（Circle/Square） |
| Center | 中心 |
| Magnification | 放大倍数 |
| Link | 链接方式 |
| Size | 尺寸 |
| Feather | 羽化 |
| Opacity | 不透明度 |
| Scaling | 缩放方式 |
| Blending Mode | 混合模式 |

#### Mesh Warp（网格变形）

通过贝塞尔网格进行自由变形，可逐点控制。

### 4.2 高级扭曲效果

#### Displacement Map（位移映射）

| 参数 | 说明 |
|------|------|
| Displacement Map Layer | 位移贴图图层 |
| Use For Horizontal/Vertical Displacement | 水平/垂直通道选择 |
| Max Horizontal/Vertical Displacement | 最大位移量 |
| Displacement Map Behavior | 贴图行为 |
| Edge Behavior | 边缘行为 |

```javascript
// ExtendScript: Displacement Map
var disp = layer.Effects.addProperty("ADBE Displacement Map");
disp.property(1).setValue(mapLayerIndex); // 位移贴图图层
disp.property(2).setValue(1);             // Horizontal = Red
disp.property(3).setValue(50);            // Max Horizontal
disp.property(4).setValue(1);             // Vertical = Red
disp.property(5).setValue(50);            // Max Vertical
```

#### Turbulent Displace（湍流位移）

| 参数 | 说明 |
|------|------|
| Displacement | 位移量 |
| Size | 大小 |
| Offset | 偏移 |
| Complexity | 复杂度 |
| Evolution | 演化 |
| Evolution Options | 演化选项（循环演化等） |
| Pinning | 固定 |
| Reshape | 重塑类型 |

```javascript
// ExtendScript: Turbulent Displace 水波效果
var turb = layer.Effects.addProperty("ADBE Turbulent Displace");
turb.property(1).setValue(30);    // Displacement
turb.property(2).setValue(80);    // Size
turb.property(4).setValue(3);     // Complexity
turb.property(5).setValueAtTime(0, 0);
turb.property(5).setValueAtTime(5, 3); // Evolution动画
```

#### Optics Compensation（光学补偿）

| 参数 | 说明 |
|------|------|
| Field of View | 视场角 |
| Reverse Lens Distortion | 反转镜头畸变 |
| FOV Orientation | FOV方向 |
| View Center | 视图中心 |
| Optimal Pixels | 最优像素 |

#### Polar Coordinates（极坐标）

| 参数 | 说明 |
|------|------|
| Interpolation | 插值 0~100% |
| Type of Conversion | Rect to Polar / Polar to Rect |

#### Spherize（球面化）

| 参数 | 说明 |
|------|------|
| Radius | 球面半径 |
| Center of Sphere | 球面中心 |
| Amount | 球面化量 -100~100 |

#### Twirl（旋转扭曲）

| 参数 | 说明 |
|------|------|
| Angle | 扭转角度 |
| Twirl Radius | 扭转半径 |
| Twirl Center | 扭转中心 |

#### Wave Warp（波浪变形）

| 参数 | 说明 |
|------|------|
| Wave Type | 波浪类型（Sine/Circle/Triangle/...） |
| Wave Height | 波高 |
| Wave Width | 波宽 |
| Direction | 方向 |
| Wave Speed | 波速 |
| Pinning | 固定 |
| Phase | 相位 |

### 4.3 液体变形效果

#### Liquify（液化）

液化效果提供7种工具：

| 工具 | 快捷键 | 说明 |
|------|--------|------|
| Warp | W | 推移变形 |
| Turbulence | T | 湍流扰动 |
| Pucker | P | 收缩 |
| Bloat | B | 膨胀 |
| Twirl Clockwise | R | 顺时针旋转 |
| Twirl Counter Clockwise | L | 逆时针旋转 |
| Reconstruct | E | 重建恢复 |

#### Reshape（重塑）

通过源遮罩和目标遮罩进行形变映射。

### 4.4 空间扭曲效果

#### CC Bend It（CC弯曲）

将图层沿自定义路径弯曲，支持两点弯曲控制。

#### CC Cylinder（CC圆柱体）

将图层映射到圆柱体表面，可控制半径、旋转等。

#### CC Sphere（CC球体）

将图层映射到球体表面，支持光照和旋转控制。

| 参数 | 说明 |
|------|------|
| Rotation X/Y/Z | 三轴旋转 |
| Radius | 球体半径 |
| Light | 光照强度 |
| Light Height | 光照高度 |
| Light Direction | 光照方向 |
| Ambient | 环境光 |

#### CC Page Turn（CC翻页）

模拟3D翻页效果，支持自定义翻页方向和曲面。

#### CC Ripple Pulse（CC涟漪脉冲）

从指定点产生涟漪扩散效果。

---

## 5. 生成滤镜

### 5.1 填充与渐变效果

#### 4-Color Gradient（四色渐变）

| 参数 | 说明 |
|------|------|
| Points 1-4 | 四个颜色点位置 |
| Colors 1-4 | 四个颜色 |
| Blend | 混合度 |
| Jitter | 抖动 |
| Opacity | 不透明度 |
| Blending Mode | 混合模式 |

#### Gradient Ramp（渐变）

| 参数 | 说明 |
|------|------|
| Start of Ramp | 渐变起点 |
| Start Color | 起始颜色 |
| End of Ramp | 渐变终点 |
| End Color | 结束颜色 |
| Ramp Shape | 渐变形状（Linear/Radial） |
| Ramp Scatter | 渐变散布 |
| Blend With Original | 与原始混合 |

```javascript
// ExtendScript: Gradient Ramp
var ramp = layer.Effects.addProperty("ADBE Ramp");
ramp.property(1).setValue([0, 0]);           // Start Point
ramp.property(2).setValue([0, 0, 0.2, 1]);  // Start Color (深蓝)
ramp.property(3).setValue([960, 540]);       // End Point
ramp.property(4).setValue([0.1, 0, 0.3, 1]);// End Color (紫色)
ramp.property(5).setValue(2);                // Radial
```

#### Radio Waves（无线电波）

生成从中心向外扩散的同心波纹。

### 5.2 图案生成效果

#### Cell Pattern（单元图案）

| 参数 | 说明 |
|------|------|
| Cell Pattern | 图案类型（Bubbles/Crystals/Pavement/...） |
| Contrast | 对比度 |
| Overflow | 溢出处理 |
| Disperse | 分散度 |
| Size | 大小 |
| Offset | 偏移 |
| Tiling Options | 平铺选项 |
| Evolution | 演化 |

#### Checkerboard（棋盘格）

| 参数 | 说明 |
|------|------|
| Anchor | 锚点 |
| Size From | 尺寸来源 |
| Corner | 角点 |
| Width/Height | 宽高 |
| Feather | 羽化 |
| Color | 颜色 |
| Opacity | 不透明度 |
| Blending Mode | 混合模式 |

#### Grid（网格）

| 参数 | 说明 |
|------|------|
| Anchor | 锚点 |
| Size From | 尺寸来源 |
| Width/Height | 宽高 |
| Border | 边框宽度 |
| Feather | 羽化 |
| Color | 颜色 |
| Opacity | 不透明度 |
| Blending Mode | 混合模式 |

#### Fractal Noise（分形噪声）

| 参数 | 说明 |
|------|------|
| Set Choice | 分形类型 |
| Noise Type | 噪声类型 |
| Invert | 反转 |
| Contrast | 对比度 |
| Brightness | 亮度 |
| Overflow | 溢出 |
| Transform | 变换组（旋转/缩放/偏移） |
| Complexity | 复杂度 |
| Sub Settings | 子分形设置 |
| Evolution | 演化 |
| Evolution Options | 演化选项 |
| Opacity | 不透明度 |
| Blending Mode | 混合模式 |

```javascript
// ExtendScript: Fractal Noise 云层生成
var fn = layer.Effects.addProperty("ADBE Fractal Noise");
fn.property(1).setValue(9);    // Clouds
fn.property(2).setValue(1);    // Soft Linear
fn.property(5).setValue(200);  // Contrast
fn.property(6).setValue(-20);  // Brightness
fn.property(9).setValue(6);    // Complexity
// Evolution动画
fn.property(14).setValueAtTime(0, 0);
fn.property(14).setValueAtTime(10, 5);
```

#### Turbulent Noise（湍流噪声）

Fractal Noise的增强版，GPU加速，参数类似但渲染更快。

### 5.3 光效生成效果

#### Lens Flare（镜头光晕）

| 参数 | 说明 |
|------|------|
| Flare Center | 光晕中心 |
| Flare Brightness | 光晕亮度 |
| Lens Type | 镜头类型（50-300mm/35mm/105mm） |
| Blend With Original | 与原始混合 |

#### CC Light Burst（CC光爆）

| 参数 | 说明 |
|------|------|
| Intensity | 强度 |
| Ray Length | 光线长度 |
| Burst | 光爆中心 |
| Shape | 形状 |
| Transfer Mode | 转换模式 |

#### CC Light Rays（CC光线）

| 参数 | 说明 |
|------|------|
| Intensity | 强度 |
| Radius | 半径 |
| Warp | 扭曲 |
| Shape | 形状 |
| Direction | 方向 |
| Center | 中心 |
| Transfer Mode | 转换模式 |

#### CC Light Sweep（CC扫光）

| 参数 | 说明 |
|------|------|
| Center | 中心 |
| Direction | 方向 |
| Shape | 形状（Linear/Smooth/Round） |
| Width | 宽度 |
| Sweep Intensity | 扫光强度 |
| Edge Intensity | 边缘强度 |
| Edge Thickness | 边缘厚度 |
| Light Color | 光颜色 |
| Light Reception | 光线接收 |

### 5.4 粒子生成效果

#### CC Particle Systems II（CC粒子系统II）

| 参数 | 说明 |
|------|------|
| Birth Rate | 出生率 |
| Longevity (sec) | 寿命 |
| Producer | 发生器（位置/半径/速度/方向等） |
| Physics | 物理设置（动画/速度/重力/等） |
| Particle | 粒子外观（类型/颜色/大小/透明度等） |

#### CC Particle World（CC粒子世界）

3D版粒子系统，支持3D空间中的粒子运动。

| 参数 | 说明 |
|------|------|
| Birth Rate | 出生率 |
| Longevity | 寿命 |
| Producer X/Y/Z | 3D发生器位置 |
| Velocity | 速度 |
| Gravity | 重力 |
| Animation | 动画预设（Explosive/Directional/...） |
| Particle Type | 粒子类型 |
| Birth/Death Size | 出生/死亡大小 |
| Size Variation | 大小变化 |
| Max Opacity | 最大透明度 |
| Color Map | 颜色映射 |

#### CC Pixel Polly（CC像素碎裂）

将图层碎裂为像素碎片，模拟爆炸效果。

### 5.5 绘制效果

#### Paint（绘制）

基于笔刷的帧绘制系统，支持逐帧绘制动画。

#### Write-on（书写）

| 参数 | 说明 |
|------|------|
| Brush Position | 笔刷位置 |
| Color | 颜色 |
| Brush Size | 笔刷大小 |
| Brush Hardness | 笔刷硬度 |
| Spacing | 间距 |
| Paint Style | 绘制样式 |

#### Brush Strokes（笔触）

| 参数 | 说明 |
|------|------|
| Stroke Angle | 笔触角度 |
| Brush Size | 笔刷大小 |
| Stroke Length | 笔触长度 |
| Stroke Density | 笔触密度 |
| Stroke Randomness | 笔触随机性 |
| Paint Surface | 绘制表面 |
| Blend With Original | 混合度 |

#### Scribble（涂鸦）

| 参数 | 说明 |
|------|------|
| Scribble | 涂鸦类型 |
| Fill | 填充方式 |
| Edge Width | 边缘宽度 |
| Color | 颜色 |
| Opacity | 不透明度 |
| Angle | 角度 |
| Stroke Width | 笔划宽度 |
| Curviness | 弯曲度 |
| Spacing | 间距 |

#### Vegas（维加斯描边）

沿遮罩或图像边缘进行描边动画。

| 参数 | 说明 |
|------|------|
| Stroke | 描边类型（Image Contours/Mask/Path） |
| Image Contours | 图像轮廓设置 |
| Segments | 段数 |
| Length | 长度 |
| Rotation | 旋转 |
| Color | 颜色 |
| Width | 宽度 |
| Hardness | 硬度 |

---

## 6. 风格化滤镜

### 6.1 艺术风格效果

#### Brush Strokes（笔触风格化）

将画面转化为画笔笔触效果，模拟油画/水彩风格。

#### Cartoon（卡通）

| 参数 | 说明 |
|------|------|
| Fill | 填充细节级别 |
| Edge | 边缘检测灵敏度 |
| Edge Enhancement | 边缘增强（Stretch/Soften） |
| Black/White Threshold | 黑/白阈值 |
| Shading Steps | 着色步数 |
| Shading Smoothness | 着色平滑度 |

```javascript
// ExtendScript: Cartoon 效果
var cartoon = layer.Effects.addProperty("ADBE Cartoon");
cartoon.property(1).setValue(5);  // Fill Detail
cartoon.property(2).setValue(3);  // Edge Level
cartoon.property(3).setValue(1);  // Edge Enhancement = Stretch
```

#### Color Emboss（彩色浮雕）

| 参数 | 说明 |
|------|------|
| Direction | 浮雕方向 |
| Relief | 浮雕高度 |
| Contrast | 对比度 |
| Blend With Original | 混合度 |

#### Emboss（浮雕）

| 参数 | 说明 |
|------|------|
| Direction | 方向 |
| Relief | 浮雕高度 |
| Contrast | 对比度 |

#### Find Edges（查找边缘）

| 参数 | 说明 |
|------|------|
| Blend With Original | 与原始混合 |
| Invert | 反转 |

#### Mosaic（马赛克）

| 参数 | 说明 |
|------|------|
| Horizontal Blocks | 水平块数 |
| Vertical Blocks | 垂直块数 |
| Sharp Colors | 锐化颜色 |

```javascript
// ExtendScript: Mosaic 打码效果
var mosaic = layer.Effects.addProperty("ADBE Mosaic");
mosaic.property(1).setValue(30); // Horizontal
mosaic.property(2).setValue(30); // Vertical
mosaic.property(3).setValue(false);
```

#### Posterize Time（时间色调分离）

| 参数 | 说明 |
|------|------|
| Frame Rate | 帧率（2/4/6/8/10/12/15/24） |

> 常用于模拟电影帧率或游戏帧率效果。

#### Roughen Edges（粗糙边缘）

| 参数 | 说明 |
|------|------|
| Edge Type | 边缘类型（Roughen/Rust/Photocopy/...） |
| Edge Color | 边缘颜色 |
| Border | 边框宽度 |
| Edge Sharpness | 边缘锐度 |
| Fractal Influence | 分形影响 |
| Scale | 缩放 |
| Stretch Width/Height | 拉伸宽高 |
| Offset | 偏移 |
| Complexity | 复杂度 |
| Evolution | 演化 |

#### Scatter（散布）

| 参数 | 说明 |
|------|------|
| Scatter Amount | 散布量 |
| Grain | 颗粒方向 |
| Scatter Randomness | 随机性 |

#### Texturize（纹理化）

| 参数 | 说明 |
|------|------|
| Texture Layer | 纹理图层 |
| Light Direction | 光照方向 |
| Texture Contrast | 纹理对比度 |
| Texture Placement | 纹理放置方式 |

#### Threshold（阈值）

| 参数 | 说明 |
|------|------|
| Level | 阈值级别 0~255 |

### 6.2 电影风格效果

#### CC Vignette（CC暗角）

| 参数 | 说明 |
|------|------|
| Amount | 暗角强度 |
| Style | 样式（Standard/Wide/Light） |
| Center | 中心点 |
| Feather | 羽化 |

#### 模拟Film Grain（胶片颗粒）

通过Fractal Noise叠加实现胶片颗粒效果：

```javascript
// ExtendScript: 胶片颗粒模拟
function addFilmGrain(layer, intensity) {
    var fn = layer.Effects.addProperty("ADBE Fractal Noise");
    fn.property(1).setValue(3);     // Soft Linear
    fn.property(5).setValue(intensity); // Contrast
    fn.property(6).setValue(-10);   // Brightness
    fn.property(9).setValue(1);     // Complexity = 1
    // 叠加模式需在效果中设置
    fn.property("Blending Mode").setValue(8); // Overlay
}
```

#### Letterbox（信箱模式）

通过遮罩或Crop效果实现电影宽高比黑边。

### 6.3 故障风格效果

#### Data Glitch模拟

通过Turbulent Displace + Color Channels偏移模拟数据故障：

```javascript
// ExtendScript: Glitch效果链
function createGlitchEffect(layer, intensity) {
    // 1. RGB偏移 - 通过Shift Channels
    var shift = layer.Effects.addProperty("ADBE Shift Channels");
    
    // 2. 湍流位移 - 扭曲
    var turb = layer.Effects.addProperty("ADBE Turbulent Displace");
    turb.property(1).setValue(intensity * 30); // Displacement
    turb.property(2).setValue(50);              // Size
    turb.property(4).setValue(2);               // Complexity
    
    // 3. 添加Expression实现间歇性故障
    turb.property(1).expression = 
        'Math.random() > 0.9 ? ' + (intensity * 30) + ' : 0';
}
```

#### RGB Shift模拟

通过分离RGB通道位移实现色差效果：

```
工作流:
1. 复制图层3份
2. 第一份只保留Red通道 (Shift Channels)
3. 第二份只保留Green通道，水平偏移几个像素
4. 第三份只保留Blue通道，水平偏移更大
5. 设置Add混合模式
```

### 6.4 卡通风格效果

#### Cartoon + Posterize组合

```javascript
// ExtendScript: 卡通风格效果链
function createCartoonStyle(layer) {
    // 1. Cartoon效果
    var cartoon = layer.Effects.addProperty("ADBE Cartoon");
    cartoon.property(1).setValue(4);  // Fill Detail (低)
    cartoon.property(2).setValue(5);  // Edge Level (高)
    cartoon.property(3).setValue(1);  // Edge Enhancement = Stretch
    
    // 2. 色调分离
    var posterize = layer.Effects.addProperty("ADBE Posterize");
    posterize.property(1).setValue(6); // Level = 6 (少量色阶)
    
    // 3. 粗糙边缘
    var roughen = layer.Effects.addProperty("ADBE Roughen Edges");
    roughen.property(1).setValue(4);  // Rust边缘
    roughen.property(3).setValue(2);  // Border = 2
}
```

---

## 7. 模拟与过渡滤镜

### 7.1 粒子模拟效果

#### CC Particle Systems II（2D粒子系统）

| 子系统 | 参数 |
|--------|------|
| Producer | Position X/Y, Radius X/Y, Velocity, Direction, Direction Spread |
| Physics | Animation (Explosive/Directional/Rotating/Fractal Omni等), Velocity, Gravity, Extra |
| Particle | Type (Line/Dotted/Faded Sphere/Star/Bubble等), Birth/Death Color, Size, Max Opacity |

#### CC Particle World（3D粒子系统）

| 子系统 | 参数 |
|--------|------|
| Producer | Position X/Y/Z, Radius X/Y/Z, Velocity, Direction, Direction Spread |
| Physics | Animation, Velocity, Gravity, Extra |
| Particle | Type, Birth/Death Color, Birth/Death Size, Size Variation, Max Opacity, Color Map |

```javascript
// ExtendScript: CC Particle World - 烟花效果
function createFirework(layer) {
    var pw = layer.Effects.addProperty("CC Particle World");
    // Producer
    pw.property("Birth Rate").setValue(3);
    pw.property("Longevity").setValue(1.5);
    pw.property("Producer X").setValue(0);
    pw.property("Producer Y").setValue(0.2);
    // Physics
    pw.property("Animation").setValue(6); // Fractal Omni
    pw.property("Velocity").setValue(1.5);
    pw.property("Gravity").setValue(-0.3);
    // Particle
    pw.property("Particle Type").setValue(5); // Faded Sphere
    pw.property("Birth Color").setValue([1, 0.8, 0.2, 1]);
    pw.property("Death Color").setValue([1, 0.1, 0, 1]);
    pw.property("Birth Size").setValue(0.15);
    pw.property("Death Size").setValue(0.02);
}
```

#### CC Snow（CC下雪）

| 参数 | 说明 |
|------|------|
| Amount | 雪量 |
| Speed | 下落速度 |
| Wind | 风力 |
| Flake Size | 雪花大小 |
| Variation | 变化 |
| Opacity | 不透明度 |
| Scene | 场景深度 |

#### CC Rain（CC下雨）

| 参数 | 说明 |
|------|------|
| Amount | 雨量 |
| Speed | 下落速度 |
| Wind | 风力 |
| Drop Size | 雨滴大小 |
| Variation | 变化 |
| Opacity | 不透明度 |
| Scene | 场景深度 |

#### CC Bubbles（CC气泡）

| 参数 | 说明 |
|------|------|
| Amount | 气泡量 |
| Speed | 上升速度 |
| Wobble | 摆动 |
| Size | 大小 |
| Variation | 变化 |
| Refraction | 折射 |
| Opacity | 不透明度 |

### 7.2 过渡效果

AE内置过渡效果一览：

| 效果名 | 说明 |
|--------|------|
| Block Dissolve | 块状溶解过渡 |
| Card Wipe | 卡片擦除过渡 |
| Gradient Wipe | 渐变擦除过渡 |
| Iris Wipe | 光圈擦除过渡 |
| Linear Wipe | 线性擦除过渡 |
| Radial Wipe | 径向擦除过渡 |
| Venetian Blinds | 百叶窗过渡 |
| CC Grid Wipe | CC网格擦除 |
| CC Image Wipe | CC图像擦除 |
| CC Jaws | CC锯齿过渡 |
| CC Light Wipe | CC光线擦除 |
| CC Line Sweep | CC线扫描过渡 |
| CC Radial ScaleWipe | CC径向缩放擦除 |
| CC Scale Wipe | CC缩放擦除 |
| CC Twister | CC旋风过渡 |
| CC WarpoMatic | CC变形过渡 |

```javascript
// ExtendScript: 线性擦除过渡
function addLinearWipe(layer, transitionTime, angle) {
    var wipe = layer.Effects.addProperty("ADBE Linear Wipe");
    wipe.property(1).setValueAtTime(layer.inPoint, 0);          // 开始完整
    wipe.property(1).setValueAtTime(layer.inPoint + transitionTime, 100); // 结束擦除
    wipe.property(2).setValue(angle);  // 角度
    wipe.property(3).setValue(5);      // 羽化
}
```

---

## 8. 第三方滤镜系统

### 8.1 Trapcode Suite

Red Giant Trapcode Suite 是AE最知名的粒子与光效插件套件：

| 插件 | 类别 | 核心功能 | MatchName |
|------|------|---------|-----------|
| Particular | 粒子 | 3D粒子系统，支持自定义发射器/物理/渲染 | Trapcode Particular |
| Form | 粒子 | 3D网格粒子，永生粒子系统 | Trapcode Form |
| Mir | 3D几何 | 3D多边形网格生成器 | Trapcode Mir |
| Tao | 3D几何 | 沿路径生成3D几何体 | Trapcode Tao |
| Starglow | 光效 | 星光闪烁/光芒效果 | Trapcode Starglow |
| Shine | 光效 | 体积光线/上帝光线 | Trapcode Shine |
| 3D Stroke | 绘制 | 3D路径描边动画 | Trapcode 3DStroke |
| Lux | 光效 | 3D体积光照 | Trapcode Lux |
| Echospace | 空间 | 图层实例化/延迟动画 | Trapcode Echospace |
| Sound Keys | 音频 | 音频频谱分析关键帧生成 | Trapcode SoundKeys |
| Horizon | 3D | 3D天空/地平线生成 | Trapcode Horizon |

#### Particular 核心参数体系

| 子系统 | 参数组 | 关键参数 |
|--------|--------|---------|
| Emitter | 发射器 | Type/Position/Direction/Spread/Rate/Velocity |
| Particle | 粒子 | Life/Size/Opacity/Color/Type |
| Physics | 物理 | Gravity/Wind/Turbulence/Bounce/Air Resistance |
| Aux System | 辅助系统 | Emit/Probability/Life/Size/Color |
| Rendering | 渲染 | Motion Blur/Depth of Field/Orientation |
| World Transform | 世界变换 | Rotation X/Y/Z/Offset |

```javascript
// ExtendScript: Trapcode Particular 火焰效果
function createFireWithParticular(layer) {
    var p = layer.Effects.addProperty("Trapcode Particular");
    // Emitter
    p.property("Emitter Type").setValue(4);  // Box
    p.property("Particles/sec").setValue(200);
    p.property("Emitter Size X").setValue(100);
    p.property("Direction").setValue(90);     // 向上
    p.property("Velocity").setValue(150);
    p.property("Velocity Random").setValue(50);
    // Particle
    p.property("Life").setValue(1.5);
    p.property("Life Random").setValue(0.5);
    p.property("Particle Type").setValue(3);  // Smoke
    p.property("Size").setValue(30);
    p.property("Size over Life").setValue(/* 曲线 */);
    // Physics
    p.property("Gravity").setValue(-100);
    p.property("Air Resistance").setValue(5);
    p.property("Turbulence").setValue(50);
}
```

### 8.2 Sapphire (S_

Boris FX Sapphire 提供300+效果，是影视后期行业标准：

| 效果类别 | 前缀 | 代表效果 | 数量 |
|----------|------|---------|------|
| 过渡 | S_Transition | S_Dissolve, S_Wipe, S_SwishPan | 50+ |
| 扭曲 | S_Distort | S_Distort, S_Warp, S_Ripple | 30+ |
| 光效 | S_Light | S_Glow, S_LensFlare, S_Rays | 25+ |
| 渲染 | S_Render | S_ZDefocus, S_MotionBlur | 10+ |
| 风格化 | S_Stylize | S_EdgeRays, S_Damage | 20+ |
| 模糊 | S_Blur | S_Blur, S_Defocus, S_RackDefocus | 15+ |
| 色彩 | S_Color | S_ColorCorrect, S_MatteOps | 20+ |
| 生成 | S_Generate | S_Grain, S_Noise, S_Clouds | 15+ |
| 合成 | S_Composite | S_EdgeFlash, S_LightWrap | 10+ |
| 时间 | S_Time | S_TimeWarp, S_Freeze | 5+ |

#### Sapphire核心效果详解

**S_Glow** — 最常用的光晕效果：
| 参数 | 说明 |
|------|------|
| Threshold | 亮度阈值 |
| Width | 光晕宽度 |
| Brightness | 光晕亮度 |
| Color | 光晕颜色 |
| Threshold Width | 阈值宽度 |
| Glow From | 光晕来源（Alpha/Luminance/All） |

**S_RackDefocus** — 专业景深模糊：
| 参数 | 说明 |
|------|------|
| Defocus Width | 散焦宽度 |
| Dist | 模糊类型 |
| Depth Layer | 深度图层 |
| Focal Distance | 焦距 |
| Focal Range | 焦点范围 |

### 8.3 BCC (Boris Continuum Complete)

BCC提供250+效果，是AE另一个重要的第三方效果库：

| 效果类别 | 前缀 | 代表效果 | 数量 |
|----------|------|---------|------|
| 过渡 | BCC Transition | BCC Cross Glitch, BCC Swish Pan | 30+ |
| 扭曲 | BCC Distortion | BCC Lens Distortion, BCC Warp | 20+ |
| 光效 | BCC Light | BCC Light Leaks, BCC Glint | 15+ |
| 色彩 | BCC Color | BCC Color Grade, BCC DV Fixer | 20+ |
| 模糊 | BCC Blur | BCC Lens Blur, BCC Channel Blur | 10+ |
| 风格化 | BCC Stylize | BCC Cartoon, BCC Water Color | 15+ |
| 粒子 | BCC Particle | BCC Particle Array 3D | 5+ |
| 键控 | BCC Key & Matte | BCC Primatte Studio | 10+ |
| 3D | BCC 3D | BCC Extruded Text, BCC 3D Objects | 10+ |

### 8.4 Video Copilot

| 插件 | 功能 | 核心参数 |
|------|------|---------|
| Element 3D | 3D对象渲染 | Model/Particle Replicator/Scene/Appearance/Rendering |
| Optical Flares | 镜头光晕 | Position/Brightness/Scale/Color/Behavior/Rendering |
| Twitch | 故障效果 | Blur/Color/Slide/Scale/Time/Ops |

#### Element 3D 核心参数

| 参数组 | 关键参数 |
|--------|---------|
| Scene Setup | 导入3D模型/设置材质/灯光 |
| Particle Replicator | Shape/Count/Size/Position/Rotation/Distribution |
| Rendering | Ambient/Diffuse/Specular/Reflection/Shadow |
| Animation Engine | Mode/Distance/Size/Position/Rotation/Color |

### 8.5 Red Giant 其他套件

#### VFX Suite

| 插件 | 功能 |
|------|------|
| Supercomp | 高级合成与光效交互 |
| Primatte Keyer | 专业色度键控 |
| King Pin Tracker | 点跟踪器 |
| Shadow | 阴影生成 |
| Reflection | 反射生成 |
| Lens Distortion Matcher | 镜头畸变匹配 |
| Chromatic Displacement | 色差位移 |
| Glow | 高级光晕 |

#### Magic Bullet Suite

| 插件 | 功能 |
|------|------|
| Magic Bullet Looks | 调色/风格化 |
| Magic Bullet Colorista | 专业色彩校正 |
| Magic Bullet Denoiser | 降噪 |
| Magic Bullet Mojo | 快速电影调色 |
| Magic Bullet Cosmo | 皮肤润饰 |
| Magic Bullet Film | 胶片模拟 |

#### Universe

Red Giant Universe提供80+效果和过渡，覆盖：
- 过渡效果（30+）
- 风格化效果（20+）
- 文字效果（10+）
- 模糊与光效（15+）
- 实用工具（5+）

### 8.6 RE:Vision Effects

| 插件 | 功能 | 核心参数 |
|------|------|---------|
| Twixtor | 慢动作/时间重映射 | Speed/In/Out/Motion Sensitivity/Interpolation |
| ReelSmart Motion Blur | 自动运动模糊 | Motion Blur Amount/Shutter Angle/Auto/Manual |
| DE:Flicker | 闪烁消除 | Time Radius/Smoothness/Threshold |
| PV Feather | 羽化遮罩 | Inner/Outer Radius/Falloff |

---

## 9. 效果预设与表达式控制

### 9.1 效果预设库

AE内置200+效果预设，按类别分布在以下路径：

```
Windows: C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Presets\
macOS: /Applications/Adobe After Effects 2026/Presets/
```

#### 预设分类

| 类别 | 子类 | 预设数量 | 代表预设 |
|------|------|---------|---------|
| Backgrounds | - | 20+ | Clouds, Gradient, Noise |
| Image - Creative | - | 30+ | Film Look, Vintage, Warm |
| Image - Utilities | - | 15+ | Alpha Adjust, Color Profile |
| Shapes | - | 20+ | Rect, Ellipse, Rounded |
| Text | Animate In | 25+ | Fade In, Scale Up, Typewriter |
| Text | Animate Out | 20+ | Fade Out, Scale Down |
| Text | Blurs | 10+ | Camera Blur, Focus |
| Text | Curves | 10+ | Bounce, Elastic |
| Text | Fill & Stroke | 15+ | Color Shift, Outline |
| Text | Miscellaneous | 15+ | Tracking, Anchor Point |
| Text | Multiline | 10+ | Paragraph, Justify |
| Text | Paths | 10+ | Path Text, Wrap |
| Text | Rotation | 10+ | Spin, Tumble |
| Text | Scale | 10+ | Pop, Expand |
| Text | Tracking | 10+ | Spread, Condense |
| Transitions - Dissolves | - | 15+ | Cross Dissolve, Dip to Black |
| Transitions - Wipes | - | 15+ | Linear, Radial, Clock |

### 9.2 表达式控制效果

AE提供5种表达式控制效果，用于集中管理参数：

#### Slider Control（滑块控制）

| 参数 | 范围 | 默认值 |
|------|------|--------|
| Slider | 0~100（可自定义） | 0 |

#### Angle Control（角度控制）

| 参数 | 范围 | 默认值 |
|------|------|--------|
| Angle | 0×0°~360° | 0° |

#### Checkbox Control（复选框控制）

| 参数 | 范围 | 默认值 |
|------|------|--------|
| Checkbox | On/Off | Off |

#### Color Control（颜色控制）

| 参数 | 说明 |
|------|------|
| Color | RGBA颜色值 |

#### Point Control（点控制）

| 参数 | 说明 |
|------|------|
| Point | X/Y坐标 |

```javascript
// ExtendScript: 创建表达式控制系统
function createExpressionRig(layer) {
    // 添加滑块控制
    var slider = layer.Effects.addProperty("ADBE Slider Control");
    slider.name = "Blur Amount";
    slider.property(1).setValue(25);
    
    // 添加颜色控制
    var color = layer.Effects.addProperty("ADBE Color Control");
    color.name = "Tint Color";
    color.property(1).setValue([0.2, 0.4, 0.8, 1]);
    
    // 添加角度控制
    var angle = layer.Effects.addProperty("ADBE Angle Control");
    angle.name = "Rotation Speed";
    angle.property(1).setValue(45);
    
    // 添加复选框控制
    var checkbox = layer.Effects.addProperty("ADBE Checkbox Control");
    checkbox.name = "Enable Effect";
    checkbox.property(1).setValue(true);
    
    // 添加点控制
    var point = layer.Effects.addProperty("ADBE Point Control");
    point.name = "Effect Center";
    point.property(1).setValue([960, 540]);
}
```

### 9.3 效果模板系统

通过表达式控制效果构建可复用的效果模板：

```javascript
// 效果模板定义
var effectTemplates = {
    "Cinematic Look": {
        controls: [
            { type: "Slider", name: "Intensity", default: 50 },
            { type: "Color", name: "Shadow Tint", default: [0.1, 0.1, 0.3, 1] },
            { type: "Color", name: "Highlight Tint", default: [1, 0.9, 0.7, 1] },
            { type: "Checkbox", name: "Enable Vignette", default: true },
            { type: "Slider", name: "Vignette Amount", default: 30 }
        ],
        effects: [
            { name: "ADBE Lumetri Color", params: {} },
            { name: "ADBE Gaussian Blur 2", params: { 1: "link:Intensity" } },
            { name: "ADBE Tint", params: { 1: "link:Shadow Tint", 2: "link:Highlight Tint" } }
        ]
    },
    "Glitch Effect": {
        controls: [
            { type: "Slider", name: "Glitch Intensity", default: 50 },
            { type: "Slider", name: "RGB Shift", default: 10 },
            { type: "Checkbox", name: "Enable Scanlines", default: true }
        ],
        effects: [
            { name: "ADBE Turbulent Displace", params: { 1: "link:Glitch Intensity" } },
            { name: "ADBE Shift Channels", params: {} }
        ]
    }
};
```

---

## 10. ExtendScript代码实现

### 10.1 批量添加效果

```javascript
/**
 * 批量添加效果到多个图层
 * @param {Layer[]} layers - 图层数组
 * @param {string} effectName - 效果名称（MatchName或显示名称）
 * @param {Object} params - 参数对象 {参数索引: 值} 或 {参数名: 值}
 * @returns {Object[]} 添加的效果列表
 */
function batchAddEffect(layers, effectName, params) {
    var results = [];
    params = params || {};
    
    for (var i = 0; i < layers.length; i++) {
        try {
            var layer = layers[i];
            var effect = layer.Effects.addProperty(effectName);
            
            // 设置参数
            for (var key in params) {
                if (params.hasOwnProperty(key)) {
                    var prop;
                    // 尝试按索引或名称访问参数
                    if (!isNaN(parseInt(key))) {
                        prop = effect.property(parseInt(key));
                    } else {
                        prop = effect.property(key);
                    }
                    
                    if (prop && prop.canSetValue) {
                        var val = params[key];
                        
                        // 处理数组值（颜色/点）
                        if (val instanceof Array) {
                            if (prop.propertyValueType === PropertyValueType.COLOR) {
                                prop.setValue(val);
                            } else if (prop.propertyValueType === PropertyValueType.Twod || 
                                       prop.propertyValueType === PropertyValueType.Threed) {
                                prop.setValue(val);
                            }
                        } else {
                            prop.setValue(val);
                        }
                    }
                }
            }
            
            results.push({
                layer: layer.name,
                effect: effect.name,
                index: effect.index,
                success: true
            });
            
        } catch (e) {
            results.push({
                layer: layers[i].name,
                effect: effectName,
                success: false,
                error: e.toString()
            });
        }
    }
    
    return results;
}

// 使用示例
var comp = app.project.activeItem;
var selectedLayers = [];
for (var i = 0; i < comp.numLayers; i++) {
    if (comp.layer(i + 1).selected) {
        selectedLayers.push(comp.layer(i + 1));
    }
}

batchAddEffect(selectedLayers, "ADBE Gaussian Blur 2", {
    1: 25,    // Blurriness
    3: true   // Repeat Edge Pixels
});
```

### 10.2 效果参数设置

```javascript
/**
 * 设置图层效果的参数
 * @param {Layer} layer - 目标图层
 * @param {string} effectName - 效果名称
 * @param {Object} params - 参数对象
 * @param {number} effectIndex - 同名效果的索引（默认1）
 * @returns {boolean} 是否成功
 */
function setEffectParams(layer, effectName, params, effectIndex) {
    effectIndex = effectIndex || 1;
    var count = 0;
    
    // 查找效果
    var targetEffect = null;
    for (var i = 1; i <= layer.Effects.numProperties; i++) {
        var eff = layer.Effects.property(i);
        if (eff.name === effectName || eff.matchName === effectName) {
            count++;
            if (count === effectIndex) {
                targetEffect = eff;
                break;
            }
        }
    }
    
    if (!targetEffect) {
        $.writeln("效果未找到: " + effectName);
        return false;
    }
    
    // 设置参数
    for (var key in params) {
        if (params.hasOwnProperty(key)) {
            try {
                var prop;
                if (!isNaN(parseInt(key))) {
                    prop = targetEffect.property(parseInt(key));
                } else {
                    prop = targetEffect.property(key);
                }
                
                if (prop && prop.canSetValue) {
                    var paramValue = params[key];
                    
                    // 检查是否需要添加关键帧
                    if (paramValue instanceof Object && paramValue.keyframes) {
                        var kfs = paramValue.keyframes;
                        for (var k = 0; k < kfs.length; k++) {
                            prop.setValueAtTime(kfs[k].time, kfs[k].value);
                        }
                    } else if (paramValue instanceof Object && paramValue.expression) {
                        prop.expression = paramValue.expression;
                    } else {
                        prop.setValue(paramValue);
                    }
                }
            } catch (e) {
                $.writeln("参数设置失败: " + key + " -> " + e.toString());
            }
        }
    }
    
    return true;
}

// 使用示例 - 设置关键帧参数
setEffectParams(layer, "Gaussian Blur", {
    "Blurriness": {
        keyframes: [
            { time: 0, value: 0 },
            { time: 1, value: 50 },
            { time: 2, value: 0 }
        ]
    },
    "Repeat Edge Pixels": true
});

// 使用示例 - 设置表达式参数
setEffectParams(layer, "Opacity", {
    "Opacity": {
        expression: 'effect("Slider Control")("Slider") * 2'
    }
});
```

### 10.3 效果预设保存与加载

```javascript
/**
 * 保存效果预设到文件
 * @param {Layer} layer - 源图层
 * @param {string} presetName - 预设名称
 * @param {string} customPath - 自定义保存路径（可选）
 * @returns {string} 保存的文件路径
 */
function saveEffectPreset(layer, presetName, customPath) {
    // 确定保存路径
    var savePath;
    if (customPath) {
        savePath = customPath;
    } else {
        var userPresetFolder = Folder.myDocuments.fsName + 
            "/Adobe/After Effects/" + app.version.split(".")[0] + 
            "/UserPresets/";
        var folder = new Folder(userPresetFolder);
        if (!folder.exists) {
            folder.create();
        }
        savePath = userPresetFolder + presetName + ".ffx";
    }
    
    // 收集所有效果信息
    var effectData = {
        name: presetName,
        version: "1.0",
        created: new Date().toISOString(),
        effects: []
    };
    
    for (var i = 1; i <= layer.Effects.numProperties; i++) {
        var effect = layer.Effects.property(i);
        var effectInfo = {
            matchName: effect.matchName,
            name: effect.name,
            enabled: effect.enabled,
            params: {}
        };
        
        // 遍历效果属性
        for (var j = 1; j <= effect.numProperties; j++) {
            var prop = effect.property(j);
            if (prop && prop.canSetValue) {
                var paramInfo = {};
                
                // 保存当前值
                try {
                    if (prop.propertyValueType === PropertyValueType.COLOR) {
                        paramInfo.value = prop.value.toString();
                    } else if (prop.propertyValueType === PropertyValueType.Twod ||
                               prop.propertyValueType === PropertyValueType.Threed) {
                        paramInfo.value = prop.value.toString();
                    } else {
                        paramInfo.value = prop.value;
                    }
                } catch(e) {
                    paramInfo.value = null;
                }
                
                // 保存表达式
                if (prop.expression) {
                    paramInfo.expression = prop.expression;
                }
                
                // 保存关键帧信息
                if (prop.numKeys > 0) {
                    paramInfo.keyframes = [];
                    for (var k = 1; k <= prop.numKeys; k++) {
                        paramInfo.keyframes.push({
                            time: prop.keyTime(k),
                            value: prop.keyValue(k),
                            interpolation: prop.keyOutInterpolationType(k)
                        });
                    }
                }
                
                effectInfo.params[prop.name] = paramInfo;
            }
        }
        
        effectData.effects.push(effectInfo);
    }
    
    // 写入预设文件
    var presetFile = new File(savePath);
    presetFile.encoding = "UTF-8";
    presetFile.open("w");
    presetFile.write(JSON.stringify(effectData, null, 2));
    presetFile.close();
    
    return savePath;
}

/**
 * 加载效果预设到图层
 * @param {Layer} layer - 目标图层
 * @param {string} presetName - 预设名称
 * @param {string} customPath - 自定义预设路径（可选）
 * @returns {boolean} 是否成功
 */
function loadEffectPreset(layer, presetName, customPath) {
    // 确定预设路径
    var presetPath;
    if (customPath) {
        presetPath = customPath;
    } else {
        var userPresetFolder = Folder.myDocuments.fsName + 
            "/Adobe/After Effects/" + app.version.split(".")[0] + 
            "/UserPresets/";
        presetPath = userPresetFolder + presetName + ".ffx";
    }
    
    // 读取预设文件
    var presetFile = new File(presetPath);
    if (!presetFile.exists) {
        $.writeln("预设文件不存在: " + presetPath);
        return false;
    }
    
    presetFile.encoding = "UTF-8";
    presetFile.open("r");
    var content = presetFile.read();
    presetFile.close();
    
    var effectData;
    try {
        effectData = JSON.parse(content);
    } catch (e) {
        $.writeln("预设文件解析失败: " + e.toString());
        return false;
    }
    
    // 应用效果
    app.beginUndoGroup("Load Preset: " + presetName);
    
    for (var i = 0; i < effectData.effects.length; i++) {
        var effectInfo = effectData.effects[i];
        
        try {
            var effect = layer.Effects.addProperty(effectInfo.matchName);
            effect.enabled = effectInfo.enabled;
            
            // 设置参数
            for (var paramName in effectInfo.params) {
                if (effectInfo.params.hasOwnProperty(paramName)) {
                    var paramInfo = effectInfo.params[paramName];
                    var prop = effect.property(paramName);
                    
                    if (prop && prop.canSetValue) {
                        // 设置关键帧
                        if (paramInfo.keyframes && paramInfo.keyframes.length > 0) {
                            for (var k = 0; k < paramInfo.keyframes.length; k++) {
                                var kf = paramInfo.keyframes[k];
                                prop.setValueAtTime(kf.time, kf.value);
                            }
                        }
                        // 设置表达式
                        else if (paramInfo.expression) {
                            prop.expression = paramInfo.expression;
                        }
                        // 设置静态值
                        else if (paramInfo.value !== null) {
                            prop.setValue(paramInfo.value);
                        }
                    }
                }
            }
        } catch (e) {
            $.writeln("效果应用失败: " + effectInfo.name + " -> " + e.toString());
        }
    }
    
    app.endUndoGroup();
    return true;
}

// 使用示例
var comp = app.project.activeItem;
var layer = comp.selectedLayers[0];

// 保存预设
saveEffectPreset(layer, "MyCinematicLook");

// 加载预设到另一个图层
loadEffectPreset(comp.layer(2), "MyCinematicLook");
```

### 10.4 效果链构建

```javascript
/**
 * 在图层上构建效果链
 * @param {Layer} layer - 目标图层
 * @param {Array} effectList - 效果列表
 *   每个效果项: { name: "MatchName", params: {}, enabled: true }
 * @param {boolean} clearExisting - 是否清除已有效果（默认false）
 * @returns {Property[]} 添加的效果数组
 */
function buildEffectChain(layer, effectList, clearExisting) {
    clearExisting = clearExisting || false;
    var addedEffects = [];
    
    app.beginUndoGroup("Build Effect Chain");
    
    try {
        // 清除已有效果
        if (clearExisting) {
            while (layer.Effects.numProperties > 0) {
                layer.Effects.property(1).remove();
            }
        }
        
        for (var i = 0; i < effectList.length; i++) {
            var effectDef = effectList[i];
            var effectName = effectDef.name || effectDef.matchName;
            var params = effectDef.params || {};
            var enabled = effectDef.enabled !== undefined ? effectDef.enabled : true;
            
            // 添加效果
            var effect = layer.Effects.addProperty(effectName);
            effect.enabled = enabled;
            
            // 设置参数
            for (var key in params) {
                if (params.hasOwnProperty(key)) {
                    var prop;
                    if (!isNaN(parseInt(key))) {
                        prop = effect.property(parseInt(key));
                    } else {
                        prop = effect.property(key);
                    }
                    
                    if (prop && prop.canSetValue) {
                        var val = params[key];
                        
                        // 支持表达式
                        if (typeof val === "string" && val.indexOf("expr:") === 0) {
                            prop.expression = val.substring(6);
                        }
                        // 支持关键帧数组
                        else if (val instanceof Array && val.length > 0 && 
                                 val[0] instanceof Object && val[0].time !== undefined) {
                            for (var k = 0; k < val.length; k++) {
                                prop.setValueAtTime(val[k].time, val[k].value);
                            }
                        }
                        // 普通值
                        else {
                            prop.setValue(val);
                        }
                    }
                }
            }
            
            // 重命名效果（如果指定）
            if (effectDef.rename) {
                effect.name = effectDef.rename;
            }
            
            addedEffects.push(effect);
        }
        
    } catch (e) {
        $.writeln("效果链构建失败: " + e.toString());
    }
    
    app.endUndoGroup();
    return addedEffects;
}

// 使用示例 - 构建电影调色效果链
var cinematicChain = [
    {
        name: "ADBE Pro Levels2",
        rename: "Levels - Contrast Boost",
        params: {
            2: 10,   // Input Black
            3: 245,  // Input White
            4: 1.1   // Gamma
        }
    },
    {
        name: "ADBE HUE SATURATION",
        rename: "Hue/Sat - Teal & Orange",
        params: {
            3: 5,    // Master Hue
            4: -15   // Master Saturation
        }
    },
    {
        name: "ADBE Color Balance",
        rename: "Color Balance - Warm Shadows",
        params: {
            1: 10,   // Shadow Red
            3: -5,   // Shadow Blue
            7: 5,    // Highlight Red
            9: 5     // Highlight Blue
        }
    },
    {
        name: "ADBE Gaussian Blur 2",
        rename: "Glow - Soft Bloom",
        params: {
            1: 8,    // Blurriness
            3: true  // Repeat Edge Pixels
        },
        enabled: false  // 默认关闭，按需启用
    },
    {
        name: "ADBE Vignette",
        rename: "Vignette - Subtle",
        params: {
            1: 30,   // Amount
            2: 50    // Midpoint
        }
    }
];

buildEffectChain(layer, cinematicChain, true);
```

### 10.5 调整层效果系统

```javascript
/**
 * 创建带效果的调整图层
 * @param {CompItem} comp - 目标合成
 * @param {Array} effectList - 效果列表
 * @param {Object} options - 选项
 *   - name: 调整图层名称
 *   - duration: 持续时间（默认合成长度）
 *   - position: 在时间轴中的位置索引（默认最上层）
 *   - maskShape: 遮罩形状 ("rect"/"ellipse"）
 *   - maskFeather: 遮罩羽化
 *   - maskExpansion: 遮罩扩展
 * @returns {Layer} 创建的调整图层
 */
function createAdjustmentLayerEffect(comp, effectList, options) {
    options = options || {};
    
    app.beginUndoGroup("Create Adjustment Layer with Effects");
    
    try {
        // 创建调整图层
        var adjLayer = comp.layers.addSolid(
            [0, 0, 0],                              // 颜色（不影响）
            options.name || "Adjustment Layer",      // 名称
            comp.width,                              // 宽度
            comp.height,                             // 高度
            comp.pixelAspect                         // 像素宽高比
        );
        
        // 设置为调整图层
        adjLayer.adjustmentLayer = true;
        
        // 设置持续时间
        if (options.duration) {
            adjLayer.duration = options.duration;
        }
        
        // 设置位置
        if (options.position) {
            adjLayer.moveBefore(comp.layer(options.position));
        } else {
            adjLayer.moveToBeginning();
        }
        
        // 添加遮罩
        if (options.maskShape) {
            var mask;
            if (options.maskShape === "rect") {
                mask = adjLayer.Masks.addProperty("Mask");
                var shape = new Shape();
                shape.vertices = [
                    [0, 0],
                    [comp.width, 0],
                    [comp.width, comp.height],
                    [0, comp.height]
                ];
                shape.inTangents = shape.inTangents || [];
                shape.outTangents = shape.outTangents || [];
                shape.closed = true;
                mask.property("Mask Shape").setValue(shape);
            } else if (options.maskShape === "ellipse") {
                mask = adjLayer.Masks.addProperty("Mask");
                var ellipseShape = new Shape();
                var cx = comp.width / 2;
                var cy = comp.height / 2;
                var rx = comp.width * 0.4;
                var ry = comp.height * 0.4;
                // 近似椭圆
                var pts = [];
                var inT = [];
                var outT = [];
                for (var a = 0; a < 360; a += 15) {
                    var rad = a * Math.PI / 180;
                    pts.push([cx + rx * Math.cos(rad), cy + ry * Math.sin(rad)]);
                    inT.push([0, 0]);
                    outT.push([0, 0]);
                }
                ellipseShape.vertices = pts;
                ellipseShape.inTangents = inT;
                ellipseShape.outTangents = outT;
                ellipseShape.closed = true;
                mask.property("Mask Shape").setValue(ellipseShape);
            }
            
            if (mask) {
                mask.property("Mask Feather").setValue(options.maskFeather || [100, 100]);
                mask.property("Mask Expansion").setValue(options.maskExpansion || 0);
                mask.maskMode = MaskMode.ADD;
            }
        }
        
        // 构建效果链
        if (effectList && effectList.length > 0) {
            buildEffectChain(adjLayer, effectList, false);
        }
        
        app.endUndoGroup();
        return adjLayer;
        
    } catch (e) {
        app.endUndoGroup();
        $.writeln("调整图层创建失败: " + e.toString());
        return null;
    }
}

// 使用示例 - 创建色彩校正调整图层
var colorGradingEffects = [
    {
        name: "ADBE Pro Levels2",
        rename: "Levels - Base Correction",
        params: { 2: 5, 3: 250, 4: 1.05 }
    },
    {
        name: "ADBE HUE SATURATION",
        rename: "Hue - Teal Shift",
        params: { 3: -8, 4: -10 }
    },
    {
        name: "ADBE Color Balance",
        rename: "Color Balance - Cinematic",
        params: {
            1: 8,    // Shadow Red
            9: -8,   // Highlight Blue (Cool Highlights)
            10: true  // Preserve Luminosity
        }
    },
    {
        name: "ADBE Vignette",
        rename: "Vignette",
        params: { 1: 40, 2: 45 }
    }
];

var comp = app.project.activeItem;
var adjLayer = createAdjustmentLayerEffect(comp, colorGradingEffects, {
    name: "Color Grading - Cinematic",
    maskShape: "ellipse",
    maskFeather: [200, 200],
    position: 1
});

// 使用示例 - 创建模糊调整图层（带遮罩聚焦效果）
var focusBlurEffects = [
    {
        name: "ADBE Camera Lens Blur",
        rename: "Depth of Field Blur",
        params: {
            1: 25,   // Blurriness
            2: 4     // Iris Shape = Hexagon
        }
    }
];

var blurAdj = createAdjustmentLayerEffect(comp, focusBlurEffects, {
    name: "Focus Blur - Center Subject",
    maskShape: "rect",
    maskFeather: [150, 150]
});
```

### 10.6 综合工具函数集

```javascript
/**
 * AE效果系统工具集
 * 提供效果查找、复制、移除、重排序等实用功能
 */
var AEEffectUtils = {
    
    /**
     * 查找图层上的效果
     * @param {Layer} layer - 目标图层
     * @param {string} effectName - 效果名称
     * @returns {Property|null} 找到的效果
     */
    findEffect: function(layer, effectName) {
        for (var i = 1; i <= layer.Effects.numProperties; i++) {
            var eff = layer.Effects.property(i);
            if (eff.name === effectName || eff.matchName === effectName) {
                return eff;
            }
        }
        return null;
    },
    
    /**
     * 查找图层上所有同名效果
     * @param {Layer} layer - 目标图层
     * @param {string} effectName - 效果名称
     * @returns {Property[]} 找到的效果数组
     */
    findAllEffects: function(layer, effectName) {
        var results = [];
        for (var i = 1; i <= layer.Effects.numProperties; i++) {
            var eff = layer.Effects.property(i);
            if (eff.name === effectName || eff.matchName === effectName) {
                results.push(eff);
            }
        }
        return results;
    },
    
    /**
     * 复制效果（包含参数和关键帧）
     * @param {Property} sourceEffect - 源效果
     * @param {Layer} targetLayer - 目标图层
     * @returns {Property} 新效果
     */
    cloneEffect: function(sourceEffect, targetLayer) {
        var newEffect = targetLayer.Effects.addProperty(sourceEffect.matchName);
        newEffect.name = sourceEffect.name;
        newEffect.enabled = sourceEffect.enabled;
        
        // 复制所有参数
        for (var i = 1; i <= sourceEffect.numProperties; i++) {
            var srcProp = sourceEffect.property(i);
            var dstProp = newEffect.property(i);
            
            if (srcProp.canSetValue && dstProp.canSetValue) {
                try {
                    // 复制关键帧
                    if (srcProp.numKeys > 0) {
                        for (var k = 1; k <= srcProp.numKeys; k++) {
                            dstProp.setValueAtTime(
                                srcProp.keyTime(k),
                                srcProp.keyValue(k)
                            );
                            // 复制插值类型
                            try {
                                dstProp.setInterpolationTypeAtKey(
                                    k, srcProp.keyInInterpolationType(k)
                                );
                            } catch(e) {}
                        }
                    } else {
                        dstProp.setValue(srcProp.value);
                    }
                } catch(e) {}
                
                // 复制表达式
                try {
                    if (srcProp.expression) {
                        dstProp.expression = srcProp.expression;
                    }
                } catch(e) {}
            }
        }
        
        return newEffect;
    },
    
    /**
     * 移除图层上所有指定效果
     * @param {Layer} layer - 目标图层
     * @param {string} effectName - 效果名称
     * @returns {number} 移除的数量
     */
    removeAllEffects: function(layer, effectName) {
        var count = 0;
        // 从后向前遍历，避免索引问题
        for (var i = layer.Effects.numProperties; i >= 1; i--) {
            var eff = layer.Effects.property(i);
            if (eff.name === effectName || eff.matchName === effectName) {
                eff.remove();
                count++;
            }
        }
        return count;
    },
    
    /**
     * 移动效果位置
     * @param {Layer} layer - 目标图层
     * @param {number} fromIndex - 原位置
     * @param {number} toIndex - 目标位置
     */
    moveEffect: function(layer, fromIndex, toIndex) {
        var effect = layer.Effects.property(fromIndex);
        effect.moveTo(toIndex);
    },
    
    /**
     * 获取效果的所有参数信息（用于调试/日志）
     * @param {Property} effect - 目标效果
     * @returns {Object} 参数信息对象
     */
    getEffectInfo: function(effect) {
        var info = {
            name: effect.name,
            matchName: effect.matchName,
            enabled: effect.enabled,
            properties: []
        };
        
        for (var i = 1; i <= effect.numProperties; i++) {
            var prop = effect.property(i);
            var propInfo = {
                index: i,
                name: prop.name,
                matchName: prop.matchName,
                propertyValueType: prop.propertyValueType,
                canSetValue: prop.canSetValue,
                isTimeVarying: prop.isTimeVarying,
                numKeys: prop.numKeys
            };
            
            if (prop.canSetValue) {
                try {
                    propInfo.value = prop.value;
                } catch(e) {
                    propInfo.value = "[无法读取]";
                }
            }
            
            if (prop.expression) {
                propInfo.expression = prop.expression;
            }
            
            info.properties.push(propInfo);
        }
        
        return info;
    },
    
    /**
     * 切换效果启用/禁用
     * @param {Layer} layer - 目标图层
     * @param {string} effectName - 效果名称
     * @param {boolean} enabled - 是否启用
     */
    toggleEffect: function(layer, effectName, enabled) {
        var effect = this.findEffect(layer, effectName);
        if (effect) {
            effect.enabled = enabled;
        }
    },
    
    /**
     * 禁用图层上所有效果
     * @param {Layer} layer - 目标图层
     */
    disableAllEffects: function(layer) {
        for (var i = 1; i <= layer.Effects.numProperties; i++) {
            layer.Effects.property(i).enabled = false;
        }
    },
    
    /**
     * 启用图层上所有效果
     * @param {Layer} layer - 目标图层
     */
    enableAllEffects: function(layer) {
        for (var i = 1; i <= layer.Effects.numProperties; i++) {
            layer.Effects.property(i).enabled = true;
        }
    },
    
    /**
     * 在合成中所有图层上搜索效果
     * @param {CompItem} comp - 目标合成
     * @param {string} effectName - 效果名称
     * @returns {Array} 包含效果信息的数组
     */
    searchEffectInComp: function(comp, effectName) {
        var results = [];
        for (var i = 1; i <= comp.numLayers; i++) {
            var layer = comp.layer(i);
            for (var j = 1; j <= layer.Effects.numProperties; j++) {
                var eff = layer.Effects.property(j);
                if (eff.name === effectName || eff.matchName === effectName) {
                    results.push({
                        layerIndex: i,
                        layerName: layer.name,
                        effectIndex: j,
                        effectName: eff.name,
                        matchName: eff.matchName,
                        enabled: eff.enabled
                    });
                }
            }
        }
        return results;
    },
    
    /**
     * 将效果从一个图层复制到多个图层
     * @param {Layer} sourceLayer - 源图层
     * @param {number} effectIndex - 效果索引
     * @param {Layer[]} targetLayers - 目标图层数组
     */
    copyEffectToLayers: function(sourceLayer, effectIndex, targetLayers) {
        var sourceEffect = sourceLayer.Effects.property(effectIndex);
        for (var i = 0; i < targetLayers.length; i++) {
            this.cloneEffect(sourceEffect, targetLayers[i]);
        }
    }
};

// 使用示例
var comp = app.project.activeItem;
var layer = comp.selectedLayers[0];

// 查找效果
var blurEffect = AEEffectUtils.findEffect(layer, "Gaussian Blur");

// 获取效果参数信息
if (blurEffect) {
    var info = AEEffectUtils.getEffectInfo(blurEffect);
    $.writeln(JSON.stringify(info, null, 2));
}

// 在合成中搜索效果
var allBlurs = AEEffectUtils.searchEffectInComp(comp, "Gaussian Blur");
$.writeln("找到 " + allBlurs.length + " 个Gaussian Blur效果");

// 复制效果到其他图层
var selectedLayers = [];
for (var i = 0; i < comp.numLayers; i++) {
    if (comp.layer(i + 1).selected && comp.layer(i + 1) !== layer) {
        selectedLayers.push(comp.layer(i + 1));
    }
}
AEEffectUtils.copyEffectToLayers(layer, 1, selectedLayers);
```

### 10.7 高级效果模板应用器

```javascript
/**
 * 高级效果模板系统
 * 支持条件逻辑、随机化、表达式绑定
 */
var EffectTemplateEngine = {
    
    // 内置模板库
    templates: {
        // 电影调色模板
        "Cinematic Teal & Orange": function(layer, options) {
            options = options || {};
            var intensity = options.intensity || 100;
            var i = intensity / 100;
            
            var chain = [
                {
                    name: "ADBE Pro Levels2",
                    rename: "Levels - Crush Blacks",
                    params: { 2: 5 * i, 3: 250, 4: 1.0 + 0.2 * i }
                },
                {
                    name: "ADBE HUE SATURATION",
                    rename: "Hue - Teal & Orange Push",
                    params: { 3: -10 * i, 4: -15 * i }
                },
                {
                    name: "ADBE Color Balance",
                    rename: "Color Balance - Warm Shadows Cool Highlights",
                    params: {
                        1: 12 * i,   // Shadow Red
                        3: -8 * i,   // Shadow Blue
                        7: -5 * i,   // Highlight Red
                        9: 8 * i,    // Highlight Blue
                        10: true     // Preserve Luminosity
                    }
                },
                {
                    name: "ADBE Tint",
                    rename: "Tint - Subtle Color Shift",
                    params: {
                        1: [0.05, 0.08, 0.15, 1],  // Map Black To (teal)
                        2: [1, 0.92, 0.85, 1],      // Map White To (warm)
                        3: 20 * i                    // Amount
                    }
                },
                {
                    name: "ADBE Vignette",
                    rename: "Vignette - Cinematic",
                    params: { 1: 35 * i, 2: 40 }
                }
            ];
            
            return buildEffectChain(layer, chain, options.replace || false);
        },
        
        // 故障效果模板
        "Glitch Digital": function(layer, options) {
            options = options || {};
            var intensity = options.intensity || 100;
            var i = intensity / 100;
            
            var chain = [
                {
                    name: "ADBE Turbulent Displace",
                    rename: "Glitch - Displacement",
                    params: {
                        1: "expr:'Math.random() > 0.92 ? " + Math.round(40 * i) + " : 0'",
                        2: 50,
                        4: 3,
                        5: "expr:'time * " + (5 * i) + "'"
                    }
                },
                {
                    name: "ADBE Gaussian Blur 2",
                    rename: "Glitch - Blur Flash",
                    params: {
                        1: "expr:'Math.random() > 0.95 ? " + Math.round(15 * i) + " : 0'",
                        3: true
                    }
                },
                {
                    name: "ADBE Brightness and Contrast",
                    rename: "Glitch - Brightness Flash",
                    params: {
                        1: "expr:'Math.random() > 0.93 ? " + Math.round(30 * i) + " : 0'"
                    }
                }
            ];
            
            return buildEffectChain(layer, chain, options.replace || false);
        },
        
        // 柔光梦幻模板
        "Dreamy Soft Glow": function(layer, options) {
            options = options || {};
            var intensity = options.intensity || 100;
            var i = intensity / 100;
            
            var chain = [
                {
                    name: "ADBE Gaussian Blur 2",
                    rename: "Glow - Soft Bloom",
                    params: { 1: 8 * i, 3: true }
                },
                {
                    name: "ADBE Brightness and Contrast",
                    rename: "Glow - Brightness Lift",
                    params: { 1: 10 * i, 2: -5 * i }
                },
                {
                    name: "ADBE HUE SATURATION",
                    rename: "Glow - Pastel Shift",
                    params: { 4: 15 * i, 5: 8 * i }
                },
                {
                    name: "ADBE Color Balance",
                    rename: "Glow - Warm Shift",
                    params: {
                        1: 5 * i,
                        4: 5 * i,
                        7: 5 * i,
                        10: true
                    }
                }
            ];
            
            return buildEffectChain(layer, chain, options.replace || false);
        },
        
        // 复古胶片模板
        "Vintage Film": function(layer, options) {
            options = options || {};
            var intensity = options.intensity || 100;
            var i = intensity / 100;
            
            var chain = [
                {
                    name: "ADBE Color Balance",
                    rename: "Vintage - Warm Shadows",
                    params: {
                        1: 15 * i,
                        3: -10 * i,
                        4: 10 * i,
                        7: 8 * i,
                        9: -5 * i,
                        10: true
                    }
                },
                {
                    name: "ADBE Pro Levels2",
                    rename: "Vintage - Faded Blacks",
                    params: { 2: 0, 5: 15 * i, 4: 0.95 }
                },
                {
                    name: "ADBE HUE SATURATION",
                    rename: "Vintage - Desaturate",
                    params: { 4: -20 * i }
                },
                {
                    name: "ADBE Vignette",
                    rename: "Vintage - Heavy Vignette",
                    params: { 1: 50 * i, 2: 30 }
                },
                {
                    name: "ADBE Fractal Noise",
                    rename: "Vintage - Film Grain",
                    params: {
                        1: 3,
                        2: 1,
                        5: 30 * i,
                        6: -20,
                        9: 1,
                        14: "expr:'time * 0.5'"
                    }
                }
            ];
            
            return buildEffectChain(layer, chain, options.replace || false);
        }
    },
    
    /**
     * 应用模板
     * @param {string} templateName - 模板名称
     * @param {Layer} layer - 目标图层
     * @param {Object} options - 模板选项
     * @returns {Property[]|null} 添加的效果数组
     */
    apply: function(templateName, layer, options) {
        if (this.templates[templateName]) {
            return this.templates[templateName](layer, options);
        }
        $.writeln("模板未找到: " + templateName);
        return null;
    },
    
    /**
     * 获取所有可用模板名称
     * @returns {string[]} 模板名称数组
     */
    listTemplates: function() {
        var names = [];
        for (var key in this.templates) {
            if (this.templates.hasOwnProperty(key)) {
                names.push(key);
            }
        }
        return names;
    },
    
    /**
     * 注册自定义模板
     * @param {string} name - 模板名称
     * @param {Function} templateFunc - 模板函数 function(layer, options)
     */
    registerTemplate: function(name, templateFunc) {
        this.templates[name] = templateFunc;
    }
};

// 使用示例
var comp = app.project.activeItem;
var layer = comp.selectedLayers[0];

// 列出所有模板
var templates = EffectTemplateEngine.listTemplates();
$.writeln("可用模板: " + templates.join(", "));

// 应用电影调色模板
EffectTemplateEngine.apply("Cinematic Teal & Orange", layer, {
    intensity: 80,
    replace: true
});

// 应用故障效果模板
EffectTemplateEngine.apply("Glitch Digital", layer, {
    intensity: 60
});

// 注册自定义模板
EffectTemplateEngine.registerTemplate("My Custom Look", function(layer, options) {
    options = options || {};
    var i = (options.intensity || 100) / 100;
    
    return buildEffectChain(layer, [
        {
            name: "ADBE Colorama",
            rename: "Custom - Colorama",
            params: { 3: 50 * i }
        },
        {
            name: "ADBE Gaussian Blur 2",
            rename: "Custom - Soft Focus",
            params: { 1: 5 * i, 3: true }
        }
    ], false);
});
```

---

## 附录A：效果MatchName速查表

| 效果显示名 | MatchName | 类别 |
|-----------|-----------|------|
| Brightness & Contrast | ADBE Brightness and Contrast | 色彩校正 |
| Curves | ADBE Curves | 色彩校正 |
| Levels | ADBE Pro Levels2 | 色彩校正 |
| Hue/Saturation | ADBE HUE SATURATION | 色彩校正 |
| Color Balance | ADBE Color Balance | 色彩校正 |
| Exposure | ADBE Exposure | 色彩校正 |
| Lumetri Color | ADBE Lumetri Color | 色彩校正 |
| Tint | ADBE Tint | 色彩校正 |
| Fill | ADBE Fill | 生成 |
| Tritone | ADBE Tritone | 色彩校正 |
| Colorama | ADBE Colorama | 色彩校正 |
| Channel Mixer | ADBE Channel Mixer | 色彩校正 |
| Shift Channels | ADBE Shift Channels | 通道 |
| Gaussian Blur | ADBE Gaussian Blur 2 | 模糊锐化 |
| Fast Box Blur | ADBE Fast Box Blur | 模糊锐化 |
| Camera Lens Blur | ADBE Camera Lens Blur | 模糊锐化 |
| Unsharp Mask | ADBE Unsharp Mask | 模糊锐化 |
| Sharpen | ADBE Sharpen | 模糊锐化 |
| CC Force Motion Blur | CC Force Motion Blur | 模糊锐化 |
| Transform | ADBE Geometry2 | 扭曲 |
| Warp | ADBE Warp | 扭曲 |
| Bulge | ADBE Bulge | 扭曲 |
| Magnify | ADBE Magnify | 扭曲 |
| Displacement Map | ADBE Displacement Map | 扭曲 |
| Turbulent Displace | ADBE Turbulent Displace | 扭曲 |
| Mesh Warp | ADBE Mesh Warp | 扭曲 |
| Polar Coordinates | ADBE Polar Coordinates | 扭曲 |
| Spherize | ADBE Spherize | 扭曲 |
| Twirl | ADBE Twirl | 扭曲 |
| Wave Warp | ADBE Wave Warp | 扭曲 |
| 4-Color Gradient | ADBE 4-Color Gradient | 生成 |
| Gradient Ramp | ADBE Ramp | 生成 |
| Cell Pattern | ADBE Cell Pattern | 生成 |
| Fractal Noise | ADBE Fractal Noise | 生成 |
| Lens Flare | ADBE Lens Flare | 生成 |
| Radio Waves | ADBE Radio Waves | 生成 |
| Cartoon | ADBE Cartoon | 风格化 |
| Emboss | ADBE Emboss | 风格化 |
| Find Edges | ADBE Find Edges | 风格化 |
| Mosaic | ADBE Mosaic | 风格化 |
| Roughen Edges | ADBE Roughen Edges | 风格化 |
| Scatter | ADBE Scatter | 风格化 |
| Posterize | ADBE Posterize | 风格化 |
| Threshold | ADBE Threshold | 风格化 |
| Posterize Time | ADBE Posterize Time | 风格化 |
| Texturize | ADBE Texturize | 风格化 |
| Slider Control | ADBE Slider Control | 表达式控制 |
| Angle Control | ADBE Angle Control | 表达式控制 |
| Checkbox Control | ADBE Checkbox Control | 表达式控制 |
| Color Control | ADBE Color Control | 表达式控制 |
| Point Control | ADBE Point Control | 表达式控制 |
| Linear Wipe | ADBE Linear Wipe | 过渡 |
| Radial Wipe | ADBE Radial Wipe | 过渡 |
| Iris Wipe | ADBE Iris Wipe | 过渡 |
| Gradient Wipe | ADBE Gradient Wipe | 过渡 |
| Block Dissolve | ADBE Block Dissolve | 过渡 |

---

## 附录B：效果性能优化建议

| 优化策略 | 说明 |
|----------|------|
| 使用Fast Box Blur替代Gaussian Blur | 性能提升约30% |
| 优先使用GPU加速效果 | AE 2026中标记GPU图标的效果 |
| 减少Turbulent Displace的Complexity | Complexity每增加1，计算量指数增长 |
| 预合成静态效果链 | 将不需要动画的效果预合成烘焙 |
| 使用调整图层替代逐层效果 | 减少效果实例数量 |
| 关闭不需要的效果 | enabled=false比移除更灵活 |
| 避免过大的Blur值 | 超过100的模糊值严重影响性能 |
| 使用Proxy代理预览 | 低分辨率预览效果调整 |
| 分层渲染复杂效果 | 将重效果分配到不同预合成 |
| 缓存预合成 | 启用预合成缓存减少重复计算 |

---

> **版本信息**：本指南基于 After Effects 2026 (v24.x) 编写，涵盖最新效果和API变更。ExtendScript代码兼容 AE 2024+ 版本。

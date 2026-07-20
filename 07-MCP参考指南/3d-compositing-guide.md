# 3D 图层设计与合成深度指南

## AE 2024 3D 能力概览

After Effects 2024 (v24.5+) 引入了多项重大 3D 升级：

| 新特性 | 用途 | 版本 |
|--------|------|------|
| **Advanced 3D Renderer** | 高质量抗锯齿+透明+PBR材质 | v24.0+ |
| **Shadow Catcher** | 3D物体在2D背景投射真实阴影 | v24.5 |
| **Depth Map 提取** | 预合成后提取深度图→DOF/雾气/调色 | v24.5 |
| **GLB/GLTF 导入** | 含骨骼动画的3D模型，AE内重定时 | v24.5 |
| **HDR 环境光** | 基于图像照明(IBL)，即时重新打光 | v24.0+ |
| **Substance 3D 集成** | 20000+ 3D模型/材质/HDR直接使用 | v25.0 |
| **Color Shadows** | 彩色阴影，反映光源颜色 | v25.0 |

---

## 🏗️ 3D 场景层级结构

### 标准3D场景模板

```
Main Comp (1920×1080, 30fps, Advanced 3D Renderer)
│
├── Camera 1 (35mm, f/2.8, Focus Distance: 自动)
│   Position: [960, 540, -800] (初始)
│   Point of Interest: [960, 540, 0]
│
├── [LIGHT] Key Light (Point或Spot)
│   Position: [600, 200, -500]
│   Intensity: 100%, Color: 暖白 [1, 0.95, 0.85]
│   Cast Shadows: ON, Shadow Darkness: 60%, Shadow Diffusion: 20px
│
├── [LIGHT] Fill Light (Point或Ambient)
│   Position: [1300, 800, -300]
│   Intensity: 40%, Color: 冷色补光 [0.7, 0.8, 1]
│   Cast Shadows: OFF
│
├── [LIGHT] Rim Light (Point)
│   Position: [960, 300, 300] (从后方)
│   Intensity: 70%, Color: 白 [1, 1, 1]
│   Cast Shadows: OFF
│
├── [NULL] "3D_Controller"
│   (所有3D图层Parent到此 → 一键控制整体旋转/缩放)
│
│   ├── Text Layer "标题" (3D ON)
│   │   Position: [960, 480, 0]
│   │   Material Options: Accept Shadows ON
│   │
│   ├── Shape Layer "装饰" (3D ON)
│   │   Position: [960, 540, -100]
│   │
│   ├── E3D Layer "3D模型" (3D ON)
│   │   Position: [960, 540, 100]
│   │
│   └── Particular Layer "粒子" (3D ON)
│       (使用 Comp Camera + Comp Lights)
│
└── Shadow Catcher Layer (2D)
    接收3D物体投射的阴影→合成到2D背景
```

---

## 📷 摄像机系统

### 焦距选择指南

| 焦距 | 视角 | 空间感 | 适合 |
|------|------|--------|------|
| **24mm** | 广角 (~74°) | 夸张透视、前景大背景小 | 宏大场景、空间感 |
| **35mm** | 标准广角 (~54°) | 自然透视+适度深度 | 通用默认 |
| **50mm** | 标准 (~40°) | 接近人眼、压缩感适中 | 标题、人物 |
| **85mm** | 中长焦 (~24°) | 空间压缩、背景拉近 | 肖像、产品 |
| **135mm+** | 长焦 (~15°) | 强烈压缩、透视扁平 | 特写、极简 |

### 摄像机动画公式

```javascript
// 1. 慢推 (Slow Push) — 大气感
// 摄像机 Z 轴: 0 → 200 over 5秒
// 效果: 向画面深处缓缓推进

// 2. 轨道旋转 (Orbit) — 展示立体感
// 摄像机绕 Y 轴旋转，Point of Interest 固定在中心
// 用 Null + Parent 实现:
//   Null "Camera_Rig" (3D) — 绕 Y 旋转
//     └── Camera — 设好 Position offset

// 3. 手持晃动 — 真实感
// 在 Camera 的 Position 上:
wiggle(0.5, 8)  // 低频小幅抖动
// 在 Rotation 上:
wiggle(0.3, 1.5) // 更轻微的角度摆动

// 4. 焦点拉移 (Rack Focus)
// 在 Focus Distance 上设关键帧:
// 0s: 焦点在前景 (200)
// 3s: 焦点移到背景 (1200)
// Easy Ease 关键帧
```

### 景深 (Depth of Field) 参数

```
开启条件: Camera Options → Depth of Field → ON

Aperture (光圈):
  f/1.4  — 极浅景深，强烈虚化，梦幻/氛围
  f/2.8  — 浅景深，主体清晰背景虚，常见电影感
  f/5.6  — 中等景深，多元素清晰，通用
  f/8    — 深景深，大部分清晰，信息展示
  f/16   — 极深景深，全画面清晰，UI/文字

Focus Distance: 对焦距离 (到Camera的像素距离)
Blur Level: 100% (默认)
Iris Shape: 圆形/六边形/八边形 (影响光斑形状)
```

---

## 💡 灯光系统

### 灯光类型对比

| 类型 | 特点 | 用法 |
|------|------|------|
| **Point** | 点光源，全向发光 | 主光、灯泡、蜡烛 |
| **Spot** | 锥形光，有方向 | 舞台光、追光 |
| **Parallel** | 平行光，无衰减 | 太阳光 |
| **Ambient** | 环境光，均匀照亮 | 全局亮度提升 |
| **Environment** | HDR环境光 (2024) | 基于图像的照明 |

### 三点布光法

```
Key Light (主光):    45°侧前方，亮度100%
Fill Light (补光):   对面45°侧前方，亮度30-50%
Rim Light (轮廓光):  后方上方，亮度60-80%

目的:
  主光 → 塑造形体
  补光 → 减少暗部过黑
  轮廓光 → 分离主体与背景
```

### 灯光颜色对情绪的影响

| 配色 | 情绪 | 场景 |
|------|------|------|
| 暖Key + 冷Fill | 电影感、温暖 | 人物、叙事 |
| 冷暖均等 | 中性、专业 | 产品、企业 |
| 冷Key + 暖Rim | 科技、未来 | 科幻、HUD |
| 纯白Key + 无色Fill | 干净、极简 | UI、信息图 |
| 金色Key + 紫色Fill | 奢华、神秘 | 高端品牌 |

---

## 🎯 3D 文字设计

### 文字3D深度布局

```
前景层 (Z: -200 ~ 0):
  - 主要标题 (最大、最清晰、Aperture焦点)
  
中层 (Z: -400 ~ -200):
  - 副标题 / 次要文字
  
背景层 (Z: -600 ~ -400):
  - 装饰文字 / 标签 / 粒子源
  
远背景 (Z: -1000 ~ -600):
  - 模糊光斑 / 大气元素
```

### 3D 文字材质选项

```
Material Options (每个3D图层):
  Cast Shadows: ON/OFF
  Accept Shadows: ON/OFF
  Accept Lights: ON/OFF
  
  Diffuse: 50-80% (漫反射，表面亮度)
  Specular: 20-50% (镜面反射，高光)
  Shininess: 10-50% (高光锐度)
  Metal: 0-100% (金属质感)
  
文字常用:
  无光文字: Diffuse 80%, Specular 0%
  光泽文字: Diffuse 60%, Specular 30%, Shininess 20%
  金属文字: Diffuse 30%, Specular 80%, Shininess 60%, Metal 80%
```

---

## 🔍 3D 摄像机追踪

### 3D Camera Tracker 工作流

```
1. 选素材图层 → Effects → Perspective → 3D Camera Tracker
2. 等待分析 (彩色追踪点出现)
3. 框选一组稳定的共面追踪点
4. 右键选点 → Create Solid / Text / Camera / Null
5. 创建的图层自动匹配摄像机运动
6. 可多次选择不同平面创建多层元素
7. 配合 Shadow Catcher 投射阴影到追踪场景

追踪点颜色:
  红色: 低置信度 (不要用)
  黄色: 中等 (少用)
  绿色: 高置信度 (使用这些)
  
删除坏点:
  选中漂浮/跳动的点 → Delete
  可提高整体解算精度
```

### Mocha AE 平面追踪

```
适用场景: 屏幕替换、标志贴附、广告牌合成
优势: 处理旋转/缩放/透视 → 比点追踪更稳定

工作流:
1. Effects → Mocha AE → 启动
2. 画X-spline围绕追踪区域
3. 选择追踪方向 → Track Forward
4. 导出: Copy to Clipboard (Corner Pin)
5. 回AE → Paste → Corner Pin自动创建
```

---

## 🧩 深度合成技术

### Depth Map 使用 (2024新特性)

```
提取深度图:
  3D场景 → Pre-compose → 输出Depth通道

应用:
  1. DOF虚化: Camera Lens Blur + Depth Map
  2. 深度雾气: 根据Depth Map调整雾浓度
  3. 深度调色: 远处偏蓝/暗, 近处暖/亮
  4. 深度遮罩: 在特定深度范围插入元素

表达式示例 - 根据深度调整缩放:
  depth = thisComp.layer("Depth Map").sampleImage(position, [1,1])[0];
  linear(depth, 0, 1, 50, 150); // 越远越小
```

### Shadow Catcher (2024)

```
设置:
1. 创建3D图层 (文字/模型)
2. 设置 Cast Shadows: ON
3. 下方添加 Shadow Catcher 图层
   (右键 → New → Shadow Catcher Layer)
4. 调整灯光 Shadow Darkness / Diffusion

技巧:
- Color Shadows (v25+): 阴影颜色反映光源色温
- 多层 Shadow Catcher 可接收不同物体的阴影
- Shadow Catcher 本身不渲染，只接收阴影
```

### 视差深度 (Parallax)

```javascript
// 伪3D视差 — 2D图层模拟Z深度
// 放在图层的 Position 属性上:

zDepth = index * 80; // 每层间距80px
cameraX = thisComp.layer("Camera 1").transform.position[0];
centerX = thisComp.width / 2;
factor = zDepth / 1000;
value + [(cameraX - centerX) * factor, 0]

// 多层一起用:
// Layer 1 (zDepth=80):   前景，移动多
// Layer 2 (zDepth=160):  中景
// Layer 3 (zDepth=240):  后景，移动少
// 给 Camera 加X轴动画即可看到视差
```

---

## 🎬 3D 场景配方

### 产品展示旋转台

```
Camera: 50mm, 绕Y轴轨道旋转
  Null "Camera_Rig": 3D, Y Rotation: 0→360 over 8s
    └── Camera: Position [960, 540, -600]

产品: E3D模型层, Position [960, 540, 0]
背景: 柔和渐变 + 轻微Depth of Field
灯光:
  Key: Point [400, 300, -400], 暖白
  Fill: Ambient, 冷蓝 30%
  Rim: Point [960, -100, 200], 白 80%

景深: f/2.8, Focus Distance: 600 (产品位置)
```

### 太空/星云场景

```
Camera: 24mm广角, 慢推 Z: -1000→-200 over 10s

层级 (前→后):
1. Large dust particles (Particular): Z: -100, Size: 8-15px
2. 3D Text "标题": Z: -300
3. Medium stars (Particular): Z: -500, Size: 3-6px
4. Small stars (Particular): Z: -800, Size: 1-2px
5. Background nebula (渐变纯色层): Z: -1200

景深: f/1.8, Focus Distance随时间变化做Rack Focus
```

### 科技HUD 3D空间

```
Camera: 35mm, 微小手持晃动

层级:
1. 前景数据面板 (Shape Layer, 3D): Z: -150, 倾斜15°
2. 主要标题 (Text, 3D): Z: -300
3. 数据流网格 (Form): Z: -500
4. 点状数据星空 (Particular, 低密度): Z: -800

配色: 青/蓝 [0, 0.8, 1] / [0, 0.4, 0.8]
灯光: Key冷白 + Ambient深蓝 20%
混合: 全部 Screen/Add → 发光感
```

---

## ⚡ 3D 性能优化

```
1. 预览时 Draft 3D 模式 (Fast Previews → Draft)
2. 降低预览分辨率 (1/4 或 1/2)
3. Adaptive Resolution: 自动降分辨率保持实时
4. 关闭不需要的 Cast Shadows (阴影很吃资源)
5. 降低 Shadow Map Resolution (默认2048, 可降到1024)
6. 预合成重3D场景 → 渲染 → 替换
7. 用 2.5D (3D图层+2D摄像机) 而非全3D摄像机当不需要视差时
```

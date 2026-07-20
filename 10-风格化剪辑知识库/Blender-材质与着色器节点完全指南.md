# Blender 材质与着色器节点完全指南

> 版本: 2025-v1 | 适用: PBR材质/程序化纹理/Shader Editor

## 一、着色器编辑器基础

### 1.1 节点类型

| 类型 | 图标 | 用途 |
|------|------|------|
| Shader | 绿色 | 最终着色器(Principled BSDF) |
| Texture | 红色 | 纹理贴图 |
| Color | 紫色 | 颜色处理 |
| Vector | 浅绿 | 向量/坐标 |
| Converter | 灰色 | 数学转换 |
| Input | 黄色 | 输入数据 |
| Output | 灰色 | 输出 |

### 1.2 Principled BSDF

| 参数 | 范围 | 用途 |
|------|------|------|
| Base Color | 颜色 | 基础颜色 |
| Subsurface | 0-1 | 次表面散射 |
| Metallic | 0-1 | 金属度 |
| Roughness | 0-1 | 粗糙度 |
| Specular IOR | 0-1 | 高光反射 |
| Clearcoat | 0-1 | 清漆层 |
| Transmission | 0-1 | 透射(玻璃) |
| Emission | 颜色+强度 | 自发光 |
| Alpha | 0-1 | 透明度 |

## 二、PBR材质

### 2.1 PBR工作流

| 贴图类型 | 通道 | 用途 |
|----------|------|------|
| Albedo/Base | RGB | 基础颜色 |
| Normal | RGB(切线空间) | 法线细节 |
| Roughness | 灰度 | 粗糙度 |
| Metallic | 灰度 | 金属度 |
| AO | 灰度 | 环境遮蔽 |
| Height/Displacement | 灰度 | 位移 |
| Emission | RGB | 自发光 |

### 2.2 PBR材质节点设置

```
标准PBR设置:
Image Texture(Albedo) → Principled BSDF(Base Color)
Image Texture(Normal) → Normal Map → Principled BSDF(Normal)
Image Texture(Roughness) → Principled BSDF(Roughness)
Image Texture(Metallic) → Principled BSDF(Metallic)
Image Texture(AO) → Principled BSDF(AO) [Cycles]
```

### 2.3 常用PBR材质参数

| 材质 | Base Color | Metallic | Roughness | 特殊 |
|------|-----------|----------|-----------|------|
| 塑料 | 任意 | 0 | 0.3-0.5 | - |
| 金属(抛光) | 灰色 | 1.0 | 0.05 | 颜色=金属色 |
| 金属(磨砂) | 灰色 | 1.0 | 0.3-0.5 | - |
| 木材 | 棕色系 | 0 | 0.5-0.7 | Normal贴图 |
| 玻璃 | 白色 | 0 | 0.0 | Transmission=1 |
| 水 | 无色 | 0 | 0.0 | Transmission+IOR |
| 皮肤 | 肤色 | 0 | 0.4 | SSS=0.1-0.3 |
| 陶瓷 | 白色 | 0 | 0.2-0.3 | Clearcoat=0.5 |
| 橡胶 | 深灰 | 0 | 0.7-0.9 | - |
| 车漆 | 颜色 | 0 | 0.1 | Clearcoat=1.0 |

## 三、程序化纹理

### 3.1 生成纹理节点

| 节点 | 效果 | 用途 |
|------|------|------|
| Noise Texture | 噪声 | 通用随机纹理 |
| Musgrave Texture | 分形噪声 | 地形/岩石 |
| Voronoi Texture | 泰森多边形 | 细胞/裂纹 |
| Wave Texture | 波纹 | 条纹/环形 |
| Checker Texture | 棋盘格 | 测试/图案 |
| Brick Texture | 砖块 | 墙面 |
| Gradient Texture | 渐变 | 遮罩/过渡 |
| Environment Texture | HDRI环境 | 环境光照 |

### 3.2 程序化材质示例

```
大理石材质:
Noise Texture → ColorRamp(黑白对比) → Principled BSDF
Roughness: 0.1-0.2(光滑)
IOR: 1.5

金属磨损:
Noise Texture → ColorRamp(控制粗糙度变化)
→ Principled BSDF(Roughness)
Metallic=1.0, 局部Roughness变化

木材:
Wave Texture(Ring) → Noise Texture(扰动)
→ ColorRamp(木色渐变)
→ Principled BSDF

水面:
Noise Texture(大尺度) → Bump Node → Normal
Wave Texture(小波纹) → Bump Node → Normal
Principled BSDF: Transmission=1, Roughness=0
```

## 四、UV与纹理坐标

### 4.1 UV展开

```
UV展开流程:
1. 选择物体 → 编辑模式
2. 标记接缝(Mark Seam)
3. U → Unwrap
4. 检查UV布局(无拉伸/重叠)
5. 导出UV布局图(可选)
```

### 4.2 纹理坐标节点

| 输出 | 用途 |
|------|------|
| Generated | 自动生成(物体空间) |
| Normal | 法线方向 |
| UV | UV映射坐标 |
| Object | 物体空间坐标 |
| Camera | 摄像机空间 |
| Window | 窗口空间 |
| Reflection | 反射方向 |

## 五、节点组合技巧

### 5.1 节点组织

```
最佳实践:
1. 使用Frame节点分组
2. 颜色编码(右键→颜色)
3. 使用Reroute节点整理连线
4. 命名关键节点
5. 使用Group Node封装复杂逻辑
```

### 5.2 实用节点组合

| 组合 | 功能 |
|------|------|
| ColorRamp + 纹理 | 控制纹理对比度/颜色映射 |
| Mix Shader + 遮罩 | 混合两种材质 |
| Bump + Normal Map | 增强表面细节 |
| Fresnel + 材质 | 边缘效果 |
| Math(Multiply) + 纹理 | 控制纹理强度 |
| Mapping + Texture Coord | 纹理变换/平铺 |

## 六、Cycles vs Eevee

| 特性 | Cycles | Eevee |
|------|--------|-------|
| 类型 | 路径追踪 | 光栅化 |
| 速度 | 慢(物理精确) | 快(实时) |
| 全局光照 | 物理精确 | 近似(光照探针) |
| 折射 | 物理精确 | 屏幕空间 |
| 焦散 | 支持 | 不支持 |
| 体积 | 物理精确 | 近似 |
| 用途 | 最终渲染 | 预览/动画 |

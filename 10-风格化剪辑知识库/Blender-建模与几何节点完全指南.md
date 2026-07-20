# Blender 建模与几何节点完全指南

> 版本: 2025-v1 | 适用: 3D建模/程序化生成/几何节点

## 一、建模基础

### 1.1 建模方式

| 方式 | 适用 | 特点 |
|------|------|------|
| 多边形建模 | 通用 | 最灵活 |
| 曲线建模 | 有机形状 | 平滑曲面 |
| 雕刻 | 有机体/角色 | 自由塑形 |
| 布尔运算 | 硬表面 | 快速组合 |
| 几何节点 | 程序化 | 参数化生成 |

### 1.2 编辑模式操作

| 操作 | 快捷键 | 说明 |
|------|--------|------|
| 挤出 | E | 从面/边/点挤出 |
| 内插面 | I | 面内创建面 |
| 环切 | Ctrl+R | 添加边环 |
| 倒角 | Ctrl+B | 边/点倒角 |
| 合并 | M | 合并顶点 |
| 细分 | 右键→细分 | 细分面 |
| 桥接循环面 | 面→桥接 | 连接两个面环 |
| 填充 | F | 填充面 |

### 1.3 修改器

| 修改器 | 功能 | 用途 |
|--------|------|------|
| Subdivision Surface | 细分平滑 | 平滑模型 |
| Mirror | 镜像 | 对称建模 |
| Array | 阵列 | 重复元素 |
| Boolean | 布尔运算 | 切割/合并 |
| Bevel | 倒角 | 圆角边 |
| Solidify | 加厚 | 给平面厚度 |
| Displace | 置换 | 基于纹理变形 |
| Particle System | 粒子 | 毛发/草地 |
| Geometry Nodes | 几何节点 | 程序化 |

## 二、几何节点

### 2.1 核心节点

| 节点 | 功能 | 输入/输出 |
|------|------|----------|
| Group Input | 输入 | 外部参数 |
| Group Output | 输出 | 最终几何 |
| Instance on Points | 在点上实例化 | 点→实例 |
| Distribute Points on Faces | 面上分布点 | 面→点 |
| Set Position | 设置位置 | 偏移位置 |
| Noise Texture | 噪声纹理 | 随机值 |
| Random Value | 随机值 | 随机数 |
| Math | 数学运算 | 计算 |
| Switch | 条件切换 | 分支 |
| Join Geometry | 合并几何 | 组合 |

### 2.2 程序化生成示例

```
随机树木生成:
1. Group Input → Distribute Points on Faces
2. Distribute: Density=0.1, Random
3. Points → Instance on Points
4. Instance: 树模型(Collection)
5. Random Value(Scale) → Instance Scale
6. Noise Texture → Instance Rotation
7. Group Output

建筑生成:
1. Grid → 基础平面
2. Extrude Mesh → 楼层
3. Random Value → 每层高度变化
4. Instance on Points → 窗户
5. Array → 重复单元
```

### 2.3 几何节点动画

```
生长动画:
1. Curve → Trim Curve(Start: 0, End: 0→1动画)
2. Curve to Mesh → 沿曲线生成
3. 配合Instance on Points → 沿路径生长

波动效果:
1. Noise Texture(4D, W=time) → 扰动
2. Set Position → 应用扰动
3. 自动产生波动动画

消散效果:
1. Noise Texture → 随机值
2. Compare(>阈值) → 遮罩
3. Delete Geometry(遮罩外) → 消散
4. 阈值动画 → 消散过程
```

## 三、雕刻

### 3.1 雕刻笔刷

| 笔刷 | 功能 | 用途 |
|------|------|------|
| Draw | 推拉表面 | 基础塑形 |
| Clay Strips | 添加黏土 | 增加体积 |
| Clay | 平滑黏土 | 塑造形体 |
| Smooth | 平滑 | 柔化表面 |
| Flatten | 压平 | 创建平面 |
| Scrape | 刮削 | 刮平表面 |
| Fill | 填充 | 填充凹陷 |
| Pinch | 捏合 | 锐化边缘 |
| Inflate | 膨胀 | 膨胀区域 |
| Blob | 团块 | 有机形状 |
| Crease | 折痕 | 创建折痕 |
| Mask | 遮罩 | 保护区域 |

### 3.2 雕刻工作流

```
角色雕刻流程:
1. 基础球体 → 细分到足够面数
2. 大形体: Draw/Move笔刷 → 头部/身体比例
3. 五官: Clay Strips → 鼻子/眼睛/嘴巴
4. 细节: Draw笔刷 → 皱纹/纹理
5. 平滑: Smooth笔刷 → 过渡区域
6. 表面: Standard Surface材质
7. 细分: Multires修改器 → 增加细节层级
```

## 四、UV与纹理

### 4.1 UV展开方法

| 方法 | 适用 | 质量 |
|------|------|------|
| Unwrap | 通用 | 高 |
| Cube Projection | 立方体 | 中 |
| Cylinder Projection | 圆柱体 | 中 |
| Sphere Projection | 球体 | 中 |
| Smart UV Project | 自动 | 快速 |
| Lightmap Pack | 光照贴图 | 高(无重叠) |

### 4.2 纹理绘制

```
纹理绘制流程:
1. UV展开并标记接缝
2. 切换到Texture Paint模式
3. 创建新纹理(Image→New)
4. 选择笔刷和颜色
5. 直接在模型上绘制
6. 保存纹理
7. 在Shader Editor中连接到材质
```

## 五、Python脚本自动化

### 5.1 批量操作

```python
import bpy

# 批量应用修改器
for obj in bpy.context.selected_objects:
    for mod in obj.modifiers:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

# 批量设置材质
mat = bpy.data.materials["Gold"]
for obj in bpy.context.selected_objects:
    obj.data.materials.clear()
    obj.data.materials.append(mat)

# 批量导出FBX
import os
output_dir = "//export/"
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        filepath = os.path.join(output_dir, f"{obj.name}.fbx")
        bpy.ops.export_scene.fbx(filepath=filepath, use_selection=True)
```

### 5.2 程序化建模

```python
import bpy
import math

# 创建螺旋楼梯
steps = 20
radius = 2
height = 5

for i in range(steps):
    angle = (i / steps) * math.pi * 2
    x = math.cos(angle) * radius
    y = math.sin(angle) * radius
    z = (i / steps) * height
    
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    step = bpy.context.active_object
    step.rotation_euler.z = angle
    step.scale = (1, 0.3, 0.1)
```

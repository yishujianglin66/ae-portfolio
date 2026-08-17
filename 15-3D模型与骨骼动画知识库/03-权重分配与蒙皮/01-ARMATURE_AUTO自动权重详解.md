# ARMATURE_AUTO自动权重详解

## 问题场景

Blender的`ARMATURE_AUTO`（Automatic Weights）是最简单的蒙皮方式，但对非标准模型（如宽袍大袖的古风角色）效果很差。上官婉儿模型中，手臂顶点被错误分配到Spine/Chest骨骼，导致手臂旋转时网格不变形。

## 核心原理

### Heat Diffusion算法

Blender的自动权重使用**热扩散算法**（Heat Diffusion）：
1. 将每根骨骼视为"热源"
2. 热量从骨骼向网格表面扩散
3. 每个顶点的权重 = 该骨骼热量 / 所有骨骼热量总和

```
权重计算公式（简化）：
weight(vertex, bone_i) = heat(vertex, bone_i) / Σ heat(vertex, bone_j)

heat衰减与距离成反比，但受网格拓扑影响：
- 封闭网格内部热量传播慢
- 开放边缘热量泄漏
- 薄壁结构（如袍袖）热量穿透
```

### 使用方法

```python
import bpy

def auto_weight(mesh_objects, armature_obj):
    """自动权重分配"""
    # 1. 选择所有mesh
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        obj.select_set(True)
    
    # 2. 最后选择armature（必须是活动对象）
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    
    # 3. 执行自动parent
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    # 结果：
    # - 每个mesh自动添加Armature修改器
    # - 每个mesh自动创建vertex_groups（与骨骼同名）
    # - 权重自动分配
```

### 自动权重的局限性

| 模型特征 | 问题 | 原因 |
|----------|------|------|
| 宽袍/大袖 | 手臂顶点→Spine | 热量穿透薄壁 |
| 分离部件 | 部件无权重 | 热量无法跨越间隙 |
| 非流形网格 | 权重异常 | 热扩散假设封闭流形 |
| 极细结构 | 权重为0 | 热量衰减过快 |
| 密集区域 | 权重平滑过度 | 分辨率不足 |

### 上官婉儿的失败案例

```
问题现象：
- 旋转Hand_R骨骼 → 右手网格完全不动
- 旋转Spine骨骼 → 整个模型（包括手臂）一起动

诊断：
>>> for vg in mesh.vertex_groups:
...     if 'Hand' in vg.name or 'Arm' in vg.name:
...         weights = [g.weight for v in mesh.vertices for g in v.groups if g.group == vg.index]
...         print(f"{vg.name}: {len(weights)} vertices, avg={sum(weights)/max(len(weights),1):.3f}")

结果：
Hand_R: 0 vertices, avg=0.000  ← 没有顶点分配到Hand！
ForeArm_R: 3 vertices, avg=0.12  ← 极少
Spine: 4521 vertices, avg=0.65   ← 大部分顶点被Spine吸收

根因：宽袍覆盖手臂，热扩散将手臂区域的热量导向了Spine
```

## 替代方案

当ARMATURE_AUTO失败时，使用**距离反比权重**（见下一篇文档）。

## 本项目代码关联

`cel_shading.py` L930-940：
- 尝试ARMATURE_AUTO → 发现手臂权重为0
- 切换为距离反比权重方案

## 版本兼容性

- Blender 4.x/5.x: `parent_set(type='ARMATURE_AUTO')` API不变
- Blender 5.1.0 Alpha: 测试确认heat diffusion对宽袍模型失效

## 参考链接

- [Blender Manual: Automatic Weights](https://docs.blender.org/manual/en/latest/animation/armatures/skinning/parenting.html)
- [Heat Diffusion Skin Weights (论文)](https://graphics.ethz.ch/~cwallrab/heat-diffusion/)

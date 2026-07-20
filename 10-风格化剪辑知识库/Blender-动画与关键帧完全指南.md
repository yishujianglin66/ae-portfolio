# Blender 动画与关键帧完全指南

> 版本: 2025-v1 | 适用: 关键帧动画/曲线编辑/运动图形

## 一、动画基础

### 1.1 关键帧类型

| 类型 | 图标 | 说明 |
|------|------|------|
| 位置(Location) | 黄 | X/Y/Z位移 |
| 旋转(Rotation) | 绿 | 欧拉/四元数旋转 |
| 缩放(Scale) | 蓝 | X/Y/Z缩放 |
| 自定义属性 | 灰 | 任意属性可动画化 |

### 1.2 插入关键帧

| 操作 | 快捷键 | 说明 |
|------|--------|------|
| 插入关键帧 | I | 当前位置/旋转/缩放 |
| 自动关键帧 | 录制按钮 | 自动记录修改 |
| 删除关键帧 | Alt+I | 删除当前帧关键帧 |
| 清除所有动画 | Alt+A | 清除所有关键帧 |

### 1.3 时间线操作

| 操作 | 快捷键 | 说明 |
|------|--------|------|
| 播放/暂停 | Space | 播放动画 |
| 跳到开头 | Shift+Home | 第1帧 |
| 跳到结尾 | Shift+End | 最后一帧 |
| 前一帧 | ← | 后退1帧 |
| 后一帧 | → | 前进1帧 |
| 前一关键帧 | ↑ | 跳到前一个关键帧 |
| 后一关键帧 | ↓ | 跳到后一个关键帧 |

## 二、曲线编辑器(Graph Editor)

### 2.1 插值类型

| 类型 | 快捷键 | 效果 |
|------|--------|------|
| 贝塞尔 | C | 平滑曲线(默认) |
| 线性 | Shift+T → Linear | 匀速 |
| 常数 | Shift+T → Constant | 跳变 |
| 弹性 | - | 弹性过冲 |

### 2.2 曲线操作

| 操作 | 快捷键 | 说明 |
|------|--------|------|
| 选择所有 | A | 全选 |
| 框选 | B | 矩形选择 |
| 圈选 | C | 圆形选择 |
| 缩放 | S | 缩放关键帧 |
| 移动 | G | 移动关键帧 |
| 镜像 | Ctrl+M | 镜像翻转 |
| 平滑 | Shift+O | 平滑曲线 |
| 分离/合并 | Shift+D | 复制关键帧 |

### 2.3 常用曲线形状

| 曲线 | 效果 | 应用 |
|------|------|------|
| Ease In/Out | 缓入缓出 | 自然运动 |
| Overshoot | 过冲回弹 | 弹性效果 |
| Bounce | 弹跳 | 球体落地 |
| Step | 阶梯 | 定格动画 |
| Wave | 波动 | 循环运动 |

## 三、动画约束

### 3.1 约束类型

| 约束 | 功能 | 用途 |
|------|------|------|
| Copy Location | 复制位置 | 跟随 |
| Copy Rotation | 复制旋转 | 同步旋转 |
| Track To | 朝向目标 | 注视 |
| Follow Path | 沿路径运动 | 曲线运动 |
| Limit Location | 限制位置 | 范围约束 |
| Clamp To | 约束到轴 | 滑块 |
| Child Of | 父子关系(可混合) | 临时父子 |
| Armature | 骨骼驱动 | 角色动画 |

### 3.2 Follow Path 动画

```
1. 创建路径(Curve → Bezier/Nurbs)
2. 选择物体 → 添加约束 → Follow Path
3. 目标: 选择路径曲线
4. 点击"Animate Path"
5. 调整路径上的Evaluation Time
6. 勾选Follow Curve(跟随方向)
```

## 四、形状键(Blend Shapes)

### 4.1 创建形状键

```
1. 选择网格 → 形状键面板
2. 点击"+"添加Basis(基础形状)
3. 点击"+"添加新形状键
4. 进入编辑模式修改形状
5. 退出编辑模式
6. 调整Value(0-1)混合形状
```

### 4.2 形状键动画

```
1. 为形状键Value设置关键帧
2. 在不同帧设置不同Value
3. 曲线编辑器调整过渡
4. 多个形状键可叠加
```

## 五、几何节点动画

### 5.1 几何节点动画基础

```
几何节点可以实现程序化动画:
- 随机运动: Noise Texture → Position
- 波浪运动: Wave Texture → Offset
- 生长动画: Trim Curve → 渐进显示
- 粒子效果: Distribute Points → 动画化
- 变形动画: Set Position → 时间驱动
```

### 5.2 程序化动画示例

```
随机浮动:
Noise Texture(3D, 时间驱动) → Vector → Set Position
Scale: 0.5, 速度: 0.02

螺旋运动:
Value → Math(Sine/Cosine) → Set Position
X = sin(time * speed) * radius
Y = cos(time * speed) * radius
Z = time * vertical_speed
```

## 六、渲染动画设置

### 6.1 输出设置

| 参数 | 推荐 | 说明 |
|------|------|------|
| 帧率 | 24/25/30fps | 电影24, 电视25/30 |
| 格式 | PNG序列 | 可中断恢复 |
| 色深 | 16bit | 高质量 |
| 压缩 | ZIP/PNG | 无损 |

### 6.2 运动模糊

| 参数 | 值 | 说明 |
|------|-----|------|
| Shutter | 0.5 | 180°快门(标准) |
| Position | 开启 | 位置运动模糊 |
| Object | 开启 | 物体运动模糊 |
| Camera | 开启 | 摄像机运动模糊 |

### 6.3 渲染动画命令

```
# 命令行渲染(后台)
blender -b project.blend -a

# 指定帧范围
blender -b project.blend -f 1..100

# 指定输出路径
blender -b project.blend -o //renders/frame_####.png -a

# GPU渲染
blender -b project.blend --engine CYCLES -- --cycles-device OPTX -a
```

## 七、Python动画脚本

```python
import bpy

# 创建弹跳球动画
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 2))
ball = bpy.context.active_object

# 设置关键帧
fps = 24
for frame in range(0, 49, fps):
    ball.location.z = 2  # 最高点
    ball.keyframe_insert(data_path="location", frame=frame)
    
    ball.location.z = 0.5  # 最低点
    ball.keyframe_insert(data_path="location", frame=frame + fps//2)

# 设置曲线为弹性
for fcurve in ball.animation_data.action.fcurves:
    if fcurve.data_path == "location":
        for kf in fcurve.keyframe_points:
            kf.interpolation = 'BOUNCE'
```

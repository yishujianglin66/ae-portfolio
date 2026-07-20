# Silhouette 边缘优化与运动模糊

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 系统讲解 Silhouette 的边缘羽化、模糊、运动模糊机制与逐帧边缘精修技术，提供生产级参数配置与代码示例。

## 目录
1. [边缘处理体系总览](#一边缘处理体系总览)
2. [边缘羽化（Feather）](#二边缘羽化feather)
3. [边缘模糊（Blur）](#三边缘模糊blur)
4. [运动模糊（Motion Blur）](#四运动模糊motion-blur)
5. [逐帧边缘调整](#五逐帧边缘调整)
6. [帧间插值优化](#六帧间插值优化)
7. [代码示例](#七代码示例)
8. [常见问题与最佳实践](#八常见问题与最佳实践)

---

## 一、边缘处理体系总览

Silhouette 的 RotoNode 边缘质量由三层机制协同决定：

```
形状层 → 羽化（Feather）   边缘渐变范围
       → 模糊（Blur）       整体柔化
       → 抗锯齿（Antialias） 像素级平滑
节点层 → alpha.blur         Alpha 通道模糊
       → motionBlur         运动模糊
输出层 → channel processing  通道处理
```

### 1.1 三层差异

| 机制 | 作用层 | 作用对象 | 单位 | 典型范围 |
|------|--------|---------|------|---------|
| Feather | 形状 | 形状边缘 | 像素 | 0-20px |
| Blur | 形状 | 整个形状 | 像素 | 0-3px |
| alpha.blur | 节点 | Alpha 通道 | 标量 | 0-2.0 |
| Motion Blur | 节点/形状 | 时间方向 | 帧分数 | 0-1.0 |
| Antialias | 节点 | 像素边缘 | 标量 | 0-1.0 |

---

## 二、边缘羽化（Feather）

### 2.1 羽化原理

羽化在形状边缘创建从 100% 不透明到 0% 透明的渐变区域：

```
内部 ──→ 100% ──→ 50% ──→ 0% ──→ 外部
         |← feather 距离 →|
```

### 2.2 整体羽化

```python
from fx import *

roto = Node("RotoNode")
session.addNode(roto)

shape = roto.createObject("X-Spline")
shape.addPoint((100, 100))
shape.addPoint((400, 100))
shape.addPoint((400, 400))
shape.addPoint((100, 400))

# 整体羽化 3px
shape.property("feather").setValue(3.0, 0)

# 羽化衰减曲线（控制渐变形状）
shape.property("featherFalloff").setValue(0.5, 0)
# 0.0 = 线性渐变
# 0.5 = 平滑S曲线（默认）
# 1.0 = 锐利过渡
```

### 2.3 逐点羽化（仅 Bézier）

```python
bezier = roto.createObject("Bezier")
bezier.addPoint((100, 100))
bezier.addPoint((400, 100))
bezier.addPoint((400, 400))
bezier.addPoint((100, 400))

# 启用逐点羽化
bezier.property("perPointFeather").setValue(true, 0)

# 每个点独立羽化
bezier.points[0].feather = 0.0     # 角点 - 硬边
bezier.points[1].feather = 0.0     # 角点 - 硬边
bezier.points[2].feather = 8.0     # 底部 - 大羽化
bezier.points[3].feather = 8.0     # 底部 - 大羽化

# 羽化方向（0=向外, 180=向内, 90=向右）
bezier.points[2].featherAngle = 180  # 向内羽化
```

### 2.4 羽化参数对照

| feather 值 | 效果 | 适用场景 |
|-----------|------|---------|
| 0.0 | 完全硬边 | 产品、建筑、UI |
| 0.5-1.0 | 微羽化 | 锐利物体边缘 |
| 1.0-3.0 | 轻羽化 | 人物皮肤、衣物 |
| 3.0-8.0 | 中羽化 | 毛发、半透明物体 |
| 8.0-20.0 | 大羽化 | 烟雾、光晕、景深虚化 |

### 2.5 featherFalloff 曲线

```
featherFalloff = 0.0 (线性):    0.5 (平滑S):       1.0 (锐利):
1.0 ───╲                       1.0 ──╲              1.0 ─┐
        ╲                            ╲                  │
         ╲                             ╲                │
          ╲                              ╲              │
           ╲                               ╲            │
0.0       ╲                       0.0     ╲    0.0    ╲
   ←feather→                       ←feather→     ←feather→
```

---

## 三、边缘模糊（Blur）

### 3.1 形状级 blur

```python
# 整个形状均匀模糊（不同于羽化的渐变）
shape.property("blur").setValue(1.5, 0)
```

**blur vs feather 的区别**：
- **feather**：仅在边缘创建渐变，内部完全不透明。
- **blur**：对整个 Alpha 通道进行高斯模糊，会降低内部不透明度。

### 3.2 节点级 alpha.blur

```python
# 节点级 Alpha 模糊（影响所有形状的合成结果）
roto.property("alpha.blur").setValue(0.5, 0)

# Alpha 通道收缩/扩展
roto.property("alpha.shrink").setValue(1.0, 0)   # 收缩 1px
roto.property("alpha.grow").setValue(-1.0, 0)    # 负值扩展
```

### 3.3 alpha.blur 值参考

| alpha.blur 值 | 效果 | 适用场景 |
|--------------|------|---------|
| 0.0 | 无模糊 | 硬边物体 |
| 0.2-0.4 | 轻微柔化 | 标准抠像 |
| 0.5-1.0 | 明显柔化 | 毛发、半透明 |
| 1.0-2.0 | 强柔化 | 烟雾、光晕 |
| 2.0+ | 极强柔化 | 大气效果、景深 |

### 3.4 抗锯齿

```python
# 抗锯齿等级
roto.property("antialias").setValue(1.0, 0)
# 0.0 = 关闭（锯齿明显）
# 0.5 = 中等
# 1.0 = 完全抗锯齿（默认，推荐）
```

---

## 四、运动模糊（Motion Blur）

### 4.1 运动模糊原理

模拟真实摄影机快门在物体运动期间曝光产生的模糊：

```
帧 N-1        帧 N         帧 N+1
  ↓             ↓             ↓
  ┌────┐    ┌────────────┐    ┌────┐
  │位置│ →  │   模糊带    │ ←  │位置│
  └────┘    └────────────┘    └────┘
            |← shutter →|
```

### 4.2 节点级运动模糊

```python
# 启用节点运动模糊
roto.property("motionBlur").setValue(true, 0)

# 快门角度（0-1，对应 0-360°）
roto.property("motionBlur.shutter").setValue(0.5, 0)
# 0.0 = 无模糊
# 0.25 = 90°（电影默认）
# 0.5 = 180°（标准）
# 1.0 = 360°（最大）

# 快门相位（偏移）
roto.property("motionBlur.phase").setValue(0.0, 0)
# 0.0 = 中心曝光
# 0.5 = 起始曝光
# -0.5 = 结束曝光

# 采样数（质量）
roto.property("motionBlur.samples").setValue(8, 0)
# 4 = 草稿
# 8 = 标准（默认）
# 16 = 高质量
# 32 = 极高质量（慢）
```

### 4.3 形状级运动模糊

```python
# 单个形状独立控制运动模糊
shape.property("motionBlur").setValue(true, 0)
shape.property("motionBlur.shutter").setValue(0.7, 0)
shape.property("motionBlur.samples").setValue(12, 0)
```

### 4.4 运动模糊参数对照

| 参数 | 类型 | 默认 | 范围 | 说明 |
|------|------|------|------|------|
| motionBlur | bool | false | - | 启用开关 |
| motionBlur.shutter | float | 0.5 | 0-1 | 快门角度 |
| motionBlur.phase | float | 0 | -0.5~0.5 | 快门相位 |
| motionBlur.samples | int | 8 | 4-32 | 采样数 |
| motionBlur.detail | float | 1.0 | 0-2 | 模糊细节 |

### 4.5 不同场景的快门设置

| 场景 | shutter | samples | 说明 |
|------|---------|---------|------|
| 静态物体 | 0.0 | 1 | 无需运动模糊 |
| 缓慢运动 | 0.25 | 4 | 轻微模糊 |
| 正常运动 | 0.5 | 8 | 标准电影感 |
| 快速运动 | 0.75 | 16 | 强烈模糊 |
| 极速运动 | 1.0 | 32 | 最大模糊，慢动作镜头 |

---

## 五、逐帧边缘调整

### 5.1 何时需要逐帧调整

- 物体快速变形（衣物飘动、毛发飘散）
- 边缘与背景颜色相近，自动检测失效
- 关键帧之间插值产生明显偏差
- 复杂轮廓（手指、树枝）穿插

### 5.2 逐帧工作流

```
1. 在关键帧处创建基础形状
2. 启用 motionBlur
3. 跳到中间帧检查边缘
4. 若偏差 > 2px → 添加中间关键帧
5. 在新关键帧上微调控制点
6. 重复直到所有帧边缘合格
```

### 5.3 边缘检测辅助

```python
def check_edge_quality(shape, frame, reference_image=None):
    """检查指定帧的边缘质量"""
    # 获取形状在该帧的所有控制点
    points = []
    for point in shape.points:
        pos = point.getValue(frame)
        points.append(pos)

    # 计算形状边界框
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)

    bbox = (min_x, min_y, max_x, max_y)
    area = (max_x - min_x) * (max_y - min_y)

    # 与参考对比（如有）
    if reference_image:
        # 这里简化处理，实际可调用图像分析
        pass

    return {
        "frame": frame,
        "bbox": bbox,
        "area": area,
        "point_count": len(points)
    }
```

### 5.4 边缘微调技巧

| 技巧 | 操作 | 效果 |
|------|------|------|
| 单点微调 | 选中点 → 方向键 1px 移动 | 像素级精确 |
| 整段调整 | 框选多点 → 整体拖动 | 保持曲率 |
| 羽化微调 | Bézier 点 → 调 feather 值 | 局部柔化 |
| 临时关闭羽化 | feather=0 检查硬边 | 排查溢色 |
| Alpha 增益 | alpha.shrink 收紧 1px | 消除边缘杂色 |

---

## 六、帧间插值优化

### 6.1 插值质量问题

```
关键帧 A (frame 0)         关键帧 B (frame 24)
   ●──────╲                       ╱──────●
           ╲                     ╱
            ╲   插值产生鼓包    ╱
             ╲   ╱─╲          ╱
              ╲╱     ╲      ╱
                       ╲  ╱
                        ╲╱  ← 鼓包点（frame 12）
```

### 6.2 优化策略

#### 策略 1：增加中间关键帧

```python
# 在 frame 12 添加过渡关键帧
shape.points[0].setValue((250, 200), 12)  # 中间值
```

#### 策略 2：调整插值模式

```python
# 关键帧 A → B 使用线性插值
shape.points[0].setKeyInterpolationOut(0, "linear")
shape.points[0].setKeyInterpolationIn(1, "linear")
```

#### 策略 3：调整切线

```python
# 缩短切线长度，减少过冲
shape.points[0].setKeyTangents(0, inTangent=(-2, 0), outTangent=(2, 0))
```

### 6.3 自动插值优化脚本

```python
def optimize_interpolation(shape, max_deviation=2.0):
    """自动优化关键帧插值，减少鼓包"""
    for point in shape.points:
        if point.numKeys < 3:
            continue

        # 检查每个中间关键帧
        for i in range(1, point.numKeys - 1):
            prev_val = point.keyValue(i - 1)
            curr_val = point.keyValue(i)
            next_val = point.keyValue(i + 1)

            prev_time = point.keyTime(i - 1)
            curr_time = point.keyTime(i)
            next_time = point.keyTime(i + 1)

            # 计算线性插值的预期值
            t = (curr_time - prev_time) / (next_time - prev_time)
            expected_x = prev_val[0] + (next_val[0] - prev_val[0]) * t
            expected_y = prev_val[1] + (next_val[1] - prev_val[1]) * t

            deviation = abs(curr_val[0] - expected_x) + abs(curr_val[1] - expected_y)

            if deviation > max_deviation * 2:
                # 严重偏离，改为线性
                point.setKeyInterpolation(i, "linear")
            elif deviation > max_deviation:
                # 中度偏离，缩短切线
                point.setKeyTangents(
                    i,
                    inTangent=(-1, 0),
                    outTangent=(1, 0)
                )

    print("[OPTIMIZE] 插值优化完成")
```

### 6.4 边缘抖动检测

```python
def detect_edge_jitter(shape, start_frame, end_frame):
    """检测边缘抖动"""
    jitter_frames = []

    for frame in range(start_frame + 1, end_frame):
        # 获取上一帧、当前帧、下一帧的位置
        positions_prev = [p.getValue(frame - 1) for p in shape.points]
        positions_curr = [p.getValue(frame) for p in shape.points]
        positions_next = [p.getValue(frame + 1) for p in shape.points]

        # 计算速度变化（加速度）
        for i in range(len(positions_curr)):
            vel_prev = (
                positions_curr[i][0] - positions_prev[i][0],
                positions_curr[i][1] - positions_prev[i][1]
            )
            vel_next = (
                positions_next[i][0] - positions_curr[i][0],
                positions_next[i][1] - positions_curr[i][1]
            )

            # 加速度（速度差）
            accel = abs(vel_next[0] - vel_prev[0]) + abs(vel_next[1] - vel_prev[1])

            if accel > 5.0:  # 阈值
                jitter_frames.append({
                    "frame": frame,
                    "point": i,
                    "acceleration": accel
                })

    return jitter_frames
```

---

## 七、代码示例

### 7.1 完整边缘优化管线

```python
from fx import *

def create_optimized_roto(source_path, output_path, frame_rate=24.0):
    """创建边缘优化的 Roto 管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Edge_Optimized"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Optimized_Roto"
    session.addNode(roto)

    # === 节点级边缘参数 ===
    roto.property("alpha.blur").setValue(0.4, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("matte.mode").setValue("alpha", 0)

    # === 节点级运动模糊 ===
    roto.property("motionBlur").setValue(true, 0)
    roto.property("motionBlur.shutter").setValue(0.5, 0)
    roto.property("motionBlur.samples").setValue(8, 0)

    # === 创建形状 ===
    shape = roto.createObject("X-Spline")
    shape.name = "Main_Shape"
    shape.closed = true

    # 示例形状
    points = [
        (500, 300), (1400, 300),
        (1400, 800), (500, 800)
    ]
    for pt in points:
        shape.addPoint(pt)

    # === 形状级边缘参数 ===
    shape.property("feather").setValue(2.0, 0)
    shape.property("featherFalloff").setValue(0.5, 0)
    shape.property("blur").setValue(0.3, 0)

    # === 输出节点 ===
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    session.addNode(out_node)

    # === 连接 ===
    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 边缘优化管线已创建")
    print(f"  alpha.blur: 0.4")
    print(f"  motionBlur: shutter=0.5, samples=8")
    print(f"  feather: 2.0px, falloff=0.5")
    return roto, shape
```

### 7.2 多形状边缘分级

```python
def create_multi_edge_shapes(roto_node):
    """创建多形状，每个形状不同边缘处理"""
    # 主身体 - 中等羽化
    body = roto_node.createObject("X-Spline")
    body.name = "Body"
    body.property("feather").setValue(2.0, 0)
    body.property("blur").setValue(0.3, 0)

    # 毛发区 - 大羽化 + 运动模糊
    hair = roto_node.createObject("X-Spline")
    hair.name = "Hair"
    hair.property("feather").setValue(8.0, 0)
    hair.property("featherFalloff").setValue(0.7, 0)
    hair.property("motionBlur").setValue(true, 0)
    hair.property("motionBlur.shutter").setValue(0.7, 0)

    # 眼睛 - 硬边
    eye = roto_node.createObject("Bezier")
    eye.name = "Eye"
    eye.property("feather").setValue(0.0, 0)
    eye.property("blur").setValue(0.0, 0)

    # 嘴唇 - 微羽化
    mouth = roto_node.createObject("Bezier")
    mouth.name = "Mouth"
    mouth.property("feather").setValue(0.8, 0)

    return body, hair, eye, mouth
```

### 7.3 边缘质量评估

```python
def evaluate_edge_quality(roto_node, frame_range):
    """评估指定帧范围内的边缘质量"""
    results = []

    for frame in frame_range:
        # 获取节点在该帧的输出
        # 这里简化为检查形状属性
        shapes = roto_node.objects
        for shape in shapes:
            feather = shape.property("feather").getValue(frame)
            blur = shape.property("blur").getValue(frame) if shape.property("blur").numKeys > 0 else 0

            results.append({
                "frame": frame,
                "shape": shape.name,
                "feather": feather,
                "blur": blur,
                "status": "OK" if feather < 20 else "REVIEW"
            })

    return results
```

---

## 八、常见问题与最佳实践

### 8.1 问题诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 边缘"沸腾"（boiling） | 羽化太小 + 关键帧抖动 | 增大羽化 1-2px，清理冗余关键帧 |
| 边缘"溢色" | 羽化过大包含背景色 | 减小羽化，或 alpha.shrink 收紧 |
| 运动模糊闪烁 | samples 太低 | 提高到 8-16 |
| 运动模糊过冲 | shutter 太大 | 降到 0.5 以下 |
| 边缘锯齿 | antialias 关闭 | 设为 1.0 |
| 形状内部透明 | blur 过大 | blur 仅用于边缘，内部用 feather |
| 半透明区"丢失" | alpha.blur 过强 | 降到 0.3 以下 |

### 8.2 最佳实践

1. **分层边缘处理**：硬边物体与软边物体分形状，分别设置参数。
2. **运动模糊分层**：仅快速运动形状启用 motionBlur，静态形状关闭。
3. **羽化优先**：能用 feather 解决的不用 blur，feather 不影响内部。
4. **采样分级**：预览 samples=4，最终 samples=8-16。
5. **关键帧足够密**：快速运动时关键帧密度 > 1/4 帧，运动模糊更稳定。
6. **首尾帧检查**：循环动画首尾羽化必须一致，否则边缘闪烁。

### 8.3 性能优化

```python
# 代理模式预览
session.property("proxy").setValue(true, 0)
session.property("proxyScale").setValue(0.5, 0)  # 半分辨率

# 降低运动模糊采样（预览）
roto.property("motionBlur.samples").setValue(4, 0)

# 仅渲染当前帧
session.property("renderRange").setValue("current", 0)
```

### 8.4 质量检查清单

- [ ] 边缘无锯齿（antialias=1.0）
- [ ] 羽化随物体景深变化
- [ ] 运动模糊方向与运动一致
- [ ] 快门角度匹配源素材
- [ ] 关键帧之间无鼓包
- [ ] 边缘无"沸腾"
- [ ] 半透明区域保留完整
- [ ] 内部无杂色溢出

---

## 相关文档

- [Silhouette 硬边与柔边遮罩技巧](Silhouette%20硬边与柔边遮罩技巧.md)
- [Silhouette 毛发与半透明物体抠像](Silhouette%20毛发与半透明物体抠像.md)
- [Silhouette 形状层与关键帧动画](Silhouette%20形状层与关键帧动画.md)
- [Silhouette 遮罩质量检查与优化](Silhouette%20遮罩质量检查与优化.md)

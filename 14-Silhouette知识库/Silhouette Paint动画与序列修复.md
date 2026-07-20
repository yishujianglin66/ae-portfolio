# Silhouette Paint动画与序列修复

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: 序列帧修复完整指南，涵盖序列修复策略、自动传播、手动修正、时间插值与质量保证。

## 目录
1. [序列修复概述](#一序列修复概述)
2. [序列修复策略](#二序列修复策略)
3. [自动传播](#三自动传播)
4. [手动修正](#四手动修正)
5. [时间插值](#五时间插值)
6. [关键帧管理](#六关键帧管理)
7. [质量保证](#七质量保证)
8. [故障排查](#八故障排查)

---

## 一、序列修复概述

### 1.1 序列修复挑战

序列帧修复相比单帧修复面临更多挑战：

| 挑战 | 说明 | 解决方向 |
|------|------|----------|
| 时序一致性 | 帧间修复内容需一致 | 跟踪传播 |
| 运动匹配 | 修复内容需跟随运动 | 跟踪驱动 |
| 闪烁控制 | 避免帧间亮度跳变 | 时间平滑 |
| 遮挡处理 | 修复区域被遮挡时分段 | 分段修复 |
| 性能优化 | 大量帧处理效率 | 自动化+关键帧 |

### 1.2 序列修复方法

| 方法 | 说明 | 适用场景 |
|------|------|----------|
| 逐帧手动 | 每帧独立修复 | 高精度需求 |
| 跟踪传播 | 跟踪驱动自动传播 | 稳定运动 |
| 关键帧插值 | 关键帧间插值 | 平滑运动 |
| 光流传播 | 基于光流传播 | 无跟踪场景 |
| 混合方法 | 多方法结合 | 复杂场景 |

### 1.3 序列修复流程

```
1. 分析序列，确定修复策略
2. 选择参考帧
3. 在参考帧执行修复
4. 应用传播方法
5. 检查传播结果
6. 手动修正问题帧
7. 时间平滑（可选）
8. 渲染输出
9. 质量检查
```

---

## 二、序列修复策略

### 2.1 策略选择

```python
def choose_repair_strategy(scene_analysis):
    """根据场景分析选择修复策略"""

    if scene_analysis["motion_type"] == "stable":
        return "tracked_propagation"
    elif scene_analysis["motion_type"] == "complex":
        if scene_analysis["frame_count"] < 30:
            return "manual_frame_by_frame"
        else:
            return "hybrid"
    elif scene_analysis["has_occlusion"]:
        return "segmented_repair"
    else:
        return "optical_flow"
```

### 2.2 跟踪传播策略

适用于稳定运动的场景：

```python
from fx import *

# 完整跟踪传播修复
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Sequence_Tracked_Repair"
activate(session)
proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/sequence.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 跟踪节点
track = Node("TrackerNode")
track.label = "Sequence_Track"
track.property("trackType").setValue("planar", 0)
track.property("searchArea").setValue(21, 0)
track.property("accuracy").setValue("high", 0)
track.property("patternSize").setValue(11, 0)
track.property("motionModel").setValue("perspective", 0)
session.addNode(track)

# Paint 节点（跟踪驱动）
paint = Node("PaintNode")
paint.label = "Tracked_Sequence_Paint"
paint.property("mode").setValue("clone", 0)
paint.property("brush.size").setValue(30.0, 0)
paint.property("brush.hardness").setValue(0.3, 0)
paint.property("brush.flow").setValue(1.0, 0)
paint.property("propagation").setValue("tracked", 0)
paint.property("propagateMode").setValue("bidirectional", 0)
session.addNode(paint)

out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/sequence_repaired_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

src.outputs[0].connect(track.inputs[0])
track.outputs[0].connect(paint.inputs[0])
paint.outputs[0].connect(out_node.inputs[0])

print("[SILHOUETTE] Sequence tracked repair pipeline ready")
```

### 2.3 分段修复策略

对于有遮挡的序列，采用分段修复：

```python
def segmented_repair_strategy(occlusion_frames):
    """
    分段修复策略
    occlusion_frames: 遮挡帧列表
    """

    segments = []
    start = 0

    for occlusion in occlusion_frames:
        segments.append({
            "start": start,
            "end": occlusion - 1,
            "method": "tracked_propagation"
        })
        segments.append({
            "start": occlusion,
            "end": occlusion,  # 单帧
            "method": "manual"
        })
        start = occlusion + 1

    segments.append({
        "start": start,
        "end": "end",
        "method": "tracked_propagation"
    })

    return segments
```

---

## 三、自动传播

### 3.1 传播模式

```python
# 跟踪传播（最稳定）
paint.property("propagation").setValue("tracked", 0)

# 光流传播（无跟踪时）
paint.property("propagation").setValue("auto", 0)

# 手动模式（每帧独立）
paint.property("propagation").setValue("manual", 0)

# 插值模式（关键帧间插值）
paint.property("propagation").setValue("interpolate", 0)
```

### 3.2 传播方向

```python
# 向前传播（从参考帧向后）
paint.property("propagateMode").setValue("forward", 0)

# 向后传播（从参考帧向前）
paint.property("propagateMode").setValue("backward", 0)

# 双向传播（从中间帧向前后）
paint.property("propagateMode").setValue("bidirectional", 0)
```

### 3.3 传播范围

```python
# 设置传播帧范围
paint.property("propagateStart").setValue(0, 0)    # 从第0帧开始
paint.property("propagateEnd").setValue(120, 0)    # 到第120帧结束

# 或从中间帧双向传播
paint.property("propagateStart").setValue(30, 0)   # 从第30帧开始
paint.property("propagateEnd").setValue(90, 0)     # 到第90帧结束
```

### 3.4 传播质量检查

```python
def check_propagation_quality(paint, frame_range):
    """检查传播质量"""

    issues = []

    for frame in range(frame_range[0], frame_range[1] + 1):
        # 检查笔触是否存在
        stroke_count = paint.property("strokeCount").getValue(frame)

        if stroke_count == 0:
            issues.append({
                "frame": frame,
                "issue": "无笔触数据"
            })

        # 检查偏移量
        offset = paint.property("offsetCorrection").getValue(frame)
        offset_magnitude = (offset[0]**2 + offset[1]**2)**0.5

        if offset_magnitude > 10.0:
            issues.append({
                "frame": frame,
                "issue": f"偏移过大: {offset_magnitude:.1f}px"
            })

    return issues
```

---

## 四、手动修正

### 4.1 手动修正场景

| 场景 | 修正方法 |
|------|----------|
| 跟踪偏移 | 调整笔触位置 |
| 遮挡帧 | 手动修复 |
| 传播失败 | 重新绘制 |
| 闪烁 | 调整流量/不透明度 |
| 边缘错位 | 调整笔触边缘 |

### 4.2 关键帧修正

```python
def apply_keyframe_corrections(paint, corrections):
    """应用关键帧修正"""

    for frame, correction in corrections.items():
        # 位置修正
        if "position" in correction:
            paint.property("strokePosition").setValue(
                correction["position"], frame
            )

        # 偏移修正
        if "offset" in correction:
            paint.property("offsetCorrection").setValue(
                correction["offset"], frame
            )

        # 笔刷参数修正
        if "brush_size" in correction:
            paint.property("brush.size").setValue(
                correction["brush_size"], frame
            )

        print(f"[SILHOUETTE] 帧 {frame} 已修正")

# 示例修正
corrections = {
    15: {"offset": [2.0, 1.0], "brush_size": 35.0},
    30: {"offset": [-1.0, 2.0]},
    45: {"position": [100, 200], "brush_size": 40.0}
}
apply_keyframe_corrections(paint, corrections)
```

### 4.3 逐帧检查工作流

```
1. 从第 0 帧开始逐帧查看
2. 检查修复内容是否对齐
3. 检查修复区域是否自然
4. 标记问题帧
5. 在问题帧手动修正
6. 修正后重新检查相邻帧
7. 全部检查完成后渲染
```

### 4.4 问题帧标记

```python
def mark_problem_frames(paint, frame_range):
    """标记问题帧"""

    problem_frames = []

    for frame in range(frame_range[0], frame_range[1] + 1):
        # 这里应通过视觉检查判断
        # 伪代码：自动检测问题帧
        quality_score = evaluate_frame_quality(paint, frame)

        if quality_score < 0.7:
            problem_frames.append({
                "frame": frame,
                "quality": quality_score,
                "needs_correction": True
            })

    return problem_frames
```

---

## 五、时间插值

### 5.1 插值原理

在关键帧之间插值，生成中间帧的修复内容：

```
关键帧 A (帧 0) → 插值 → 关键帧 B (帧 10)
生成中间帧 1-9 的修复内容
```

### 5.2 线性插值

```python
def linear_interpolate_strokes(stroke_a, stroke_b, frame_a, frame_b):
    """线性插值笔触"""

    interpolated = {}

    for frame in range(frame_a, frame_b + 1):
        t = (frame - frame_a) / (frame_b - frame_a)

        # 位置插值
        pos_x = stroke_a["position"][0] * (1 - t) + stroke_b["position"][0] * t
        pos_y = stroke_a["position"][1] * (1 - t) + stroke_b["position"][1] * t

        # 大小插值
        size = stroke_a["size"] * (1 - t) + stroke_b["size"] * t

        interpolated[frame] = {
            "position": [pos_x, pos_y],
            "size": size
        }

    return interpolated
```

### 5.3 贝塞尔插值

```python
def bezier_interpolate(p0, p1, p2, p3, t):
    """贝塞尔曲线插值"""

    x = ((1-t)**3 * p0[0] +
         3*(1-t)**2*t * p1[0] +
         3*(1-t)*t**2 * p2[0] +
         t**3 * p3[0])

    y = ((1-t)**3 * p0[1] +
         3*(1-t)**2*t * p1[1] +
         3*(1-t)*t**2 * p2[1] +
         t**3 * p3[1])

    return [x, y]
```

### 5.4 时间平滑

```python
# 启用时间平滑
paint.property("timeSmooth").setValue(True, 0)
paint.property("smoothWindow").setValue(3, 0)  # 平滑窗口

# 时间平滑减少帧间闪烁
```

---

## 六、关键帧管理

### 6.1 关键帧策略

| 策略 | 关键帧间隔 | 适用场景 |
|------|-----------|----------|
| 密集 | 每 5 帧 | 复杂运动 |
| 标准 | 每 10-15 帧 | 一般运动 |
| 稀疏 | 每 30 帧 | 稳定运动 |
| 自适应 | 自动检测 | 混合场景 |

### 6.2 关键帧设置

```python
def set_keyframe_strategy(paint, strategy="standard"):
    """设置关键帧策略"""

    strategies = {
        "dense": {"interval": 5, "autoKeyframe": True},
        "standard": {"interval": 10, "autoKeyframe": True},
        "sparse": {"interval": 30, "autoKeyframe": False},
        "adaptive": {"interval": 1, "autoKeyframe": True}
    }

    config = strategies.get(strategy, strategies["standard"])

    paint.property("keyframeInterval").setValue(config["interval"], 0)
    paint.property("autoKeyframe").setValue(config["autoKeyframe"], 0)

    print(f"[SILHOUETTE] 关键帧策略: {strategy}")
```

### 6.3 关键帧优化

```python
def optimize_keyframes(paint, frame_range):
    """优化关键帧分布"""

    # 1. 检测过度密集的关键帧
    keyframes = get_all_keyframes(paint, frame_range)

    # 2. 移除冗余关键帧（相邻且相似）
    optimized = []
    for i, kf in enumerate(keyframes):
        if i == 0:
            optimized.append(kf)
        else:
            prev = optimized[-1]
            if is_significantly_different(kf, prev):
                optimized.append(kf)

    # 3. 应用优化
    apply_optimized_keyframes(paint, optimized)

    return optimized
```

---

## 七、质量保证

### 7.1 质量检查清单

- [ ] 参考帧修复效果自然
- [ ] 传播覆盖所有需要的帧
- [ ] 无明显闪烁
- [ ] 无边缘错位
- [ ] 修复内容跟随目标运动
- [ ] 遮挡帧已手动处理
- [ ] 首尾帧效果稳定
- [ ] 全序列回放检查通过

### 7.2 闪烁检测

```python
def detect_flicker(paint, frame_range):
    """检测帧间闪烁"""

    flicker_frames = []
    prev_brightness = None

    for frame in range(frame_range[0], frame_range[1] + 1):
        # 测量修复区域亮度（伪代码）
        brightness = measure_repair_brightness(paint, frame)

        if prev_brightness is not None:
            brightness_change = abs(brightness - prev_brightness)
            if brightness_change > 0.1:  # 10% 亮度变化
                flicker_frames.append({
                    "frame": frame,
                    "change": brightness_change
                })

        prev_brightness = brightness

    return flicker_frames
```

### 7.3 闪烁修复

```python
def fix_flicker(paint, flicker_frames):
    """修复闪烁"""

    for flicker in flicker_frames:
        frame = flicker["frame"]

        # 方法一：调整流量
        paint.property("brush.flow").setValue(0.7, frame)

        # 方法二：启用时间平滑
        paint.property("timeSmooth").setValue(True, frame)

        # 方法三：调整不透明度
        paint.property("brush.opacity").setValue(0.9, frame)

    print(f"[SILHOUETTE] 修复了 {len(flicker_frames)} 个闪烁帧")
```

### 7.4 一致性检查

```python
def check_temporal_consistency(paint, frame_range):
    """检查时序一致性"""

    issues = []

    # 检查笔触位置连续性
    positions = []
    for frame in range(frame_range[0], frame_range[1] + 1):
        pos = paint.property("strokePosition").getValue(frame)
        positions.append(pos)

    # 检查位置跳变
    for i in range(1, len(positions)):
        dx = positions[i][0] - positions[i-1][0]
        dy = positions[i][1] - positions[i-1][1]
        displacement = (dx**2 + dy**2)**0.5

        if displacement > 20.0:  # 超过20像素跳变
            issues.append({
                "frame": frame_range[0] + i,
                "issue": f"位置跳变 {displacement:.1f}px"
            })

    return issues
```

---

## 八、故障排查

### 8.1 传播不工作

**检查项**：
1. propagation 是否设置为 "tracked"
2. 跟踪数据是否存在
3. 参考帧是否设置了笔触
4. 帧范围是否正确

```python
# 验证传播设置
def verify_propagation_setup(paint, track):
    """验证传播设置"""

    checks = []

    # 检查传播模式
    prop_mode = paint.property("propagation").getValue(0)
    checks.append(("传播模式", prop_mode == "tracked"))

    # 检查跟踪数据
    track_data = track.property("trackData").getValue(0)
    checks.append(("跟踪数据", track_data is not None))

    # 检查参考帧笔触
    ref_frame = paint.property("referenceFrame").getValue(0)
    stroke_count = paint.property("strokeCount").getValue(ref_frame)
    checks.append(("参考帧笔触", stroke_count > 0))

    # 输出检查结果
    for name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")

    return all(passed for _, passed in checks)
```

### 8.2 修复内容闪烁

**解决方案**：
```python
# 增大笔刷
paint.property("brush.size").setValue(40.0, 0)

# 降低硬度
paint.property("brush.hardness").setValue(0.2, 0)

# 启用时间平滑
paint.property("timeSmooth").setValue(True, 0)
paint.property("smoothWindow").setValue(5, 0)

# 选择更稳定的克隆源
paint.property("sampleOffset").setValue([80, 0], 0)
```

### 8.3 修复内容偏移

**解决方案**：
```python
# 在偏移帧设置偏移修正
paint.property("offsetCorrection").setValue([2.0, 1.0], problem_frame)

# 或启用自动偏移修正
paint.property("autoOffsetCorrection").setValue(True, 0)
```

### 8.4 性能优化

```python
# 预览阶段：低质量快速预览
paint.property("previewMode").setValue(True, 0)
paint.property("previewQuality").setValue("low", 0)

# 最终渲染：高质量
paint.property("previewMode").setValue(False, 0)
paint.property("renderQuality").setValue("high", 0)
```

### 8.5 渲染优化

```python
def setup_render_optimization(out_node, frame_range):
    """设置渲染优化"""

    # 分段渲染
    segments = [(0, 30), (31, 60), (61, 90), (91, 120)]

    for start, end in segments:
        out_node.property("frameStart").setValue(start, 0)
        out_node.property("frameEnd").setValue(end, 0)
        # 渲染该段
        render_segment(out_node)

# 使用多线程渲染
out_node.property("multithreaded").setValue(True, 0)
out_node.property("threadCount").setValue(4, 0)
```

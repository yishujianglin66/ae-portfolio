# Silhouette 运动匹配与偏移修正

> 分类: 跟踪技术专题
> 更新日期: 2026-07-11
> 概述: 运动匹配原理与偏移修正技术深度解析，涵盖运动匹配算法、偏移量计算、手动修正与融合策略。

## 目录
1. [运动匹配原理](#一运动匹配原理)
2. [偏移量计算](#二偏移量计算)
3. [手动修正技术](#三手动修正技术)
4. [融合策略](#四融合策略)
5. [匹配工作流](#五匹配工作流)
6. [高级匹配技巧](#六高级匹配技巧)
7. [质量验证](#七质量验证)
8. [故障排查](#八故障排查)

---

## 一、运动匹配原理

### 1.1 什么是运动匹配

运动匹配（Motion Matching）是将一段素材的运动与另一段素材的运动对齐的过程，使两段素材看起来像在同一镜头中拍摄。

### 1.2 应用场景

| 场景 | 说明 |
|------|------|
| 元素合成 | 将 CG 元素匹配到实拍镜头 |
| 多素材对齐 | 对齐不同时间拍摄的素材 |
| 运动替换 | 替换素材的运动特征 |
| 稳定化 | 匹配稳定目标运动 |
| Paint 修复 | 修复内容匹配背景运动 |

### 1.3 匹配原理

运动匹配的核心是计算两个运动的变换关系：

```
运动 A（源）→ 变换 T → 运动 B（目标）
T = A^(-1) × B
```

### 1.4 匹配类型

| 类型 | 说明 | 参数数量 |
|------|------|----------|
| 位置匹配 | 仅匹配平移 | 2 |
| 位置+旋转 | 匹配平移和旋转 | 3 |
| 仿射匹配 | 匹配仿射变换 | 6 |
| 透视匹配 | 匹配透视变换 | 8 |

---

## 二、偏移量计算

### 2.1 偏移量定义

偏移量是指跟踪结果与真实运动之间的偏差，通常分为：

| 偏移类型 | 说明 | 修正方法 |
|----------|------|----------|
| 系统偏移 | 整体恒定偏差 | 整体偏移修正 |
| 漂移偏移 | 随时间累积的偏差 | 关键帧修正 |
| 周期偏移 | 周期性偏差 | 频域修正 |
| 随机偏移 | 无规律偏差 | 平滑滤波 |

### 2.2 系统偏移计算

```python
def compute_system_offset(tracked_points, reference_points):
    """计算系统偏移量"""

    offsets_x = []
    offsets_y = []

    for tracked, reference in zip(tracked_points, reference_points):
        offset_x = tracked[0] - reference[0]
        offset_y = tracked[1] - reference[1]
        offsets_x.append(offset_x)
        offsets_y.append(offset_y)

    # 平均偏移
    mean_offset_x = sum(offsets_x) / len(offsets_x)
    mean_offset_y = sum(offsets_y) / len(offsets_y)

    return [mean_offset_x, mean_offset_y]
```

### 2.3 漂移偏移计算

```python
def compute_drift_offset(tracked_points, reference_points):
    """计算漂移偏移"""

    drifts = []
    for i, (tracked, reference) in enumerate(zip(tracked_points, reference_points)):
        drift_x = tracked[0] - reference[0]
        drift_y = tracked[1] - reference[1]
        drifts.append({
            "frame": i,
            "drift": [drift_x, drift_y],
            "magnitude": (drift_x**2 + drift_y**2)**0.5
        })

    return drifts
```

### 2.4 偏移修正应用

```python
def apply_offset_correction(track_data, offset):
    """应用偏移修正"""

    corrected = []
    for point in track_data:
        corrected_point = [
            point[0] - offset[0],
            point[1] - offset[1]
        ]
        corrected.append(corrected_point)

    return corrected


def apply_keyframe_offsets(track_data, offsets):
    """应用关键帧偏移修正（带插值）"""

    if not offsets:
        return track_data

    # 按帧排序
    sorted_offsets = sorted(offsets.items())
    frames = [f for f, _ in sorted_offsets]
    offset_values = [v for _, v in sorted_offsets]

    corrected = []
    for i, point in enumerate(track_data):
        if i in offsets:
            # 关键帧：直接应用
            offset = offsets[i]
        else:
            # 非关键帧：插值
            offset = interpolate_offset(i, frames, offset_values)

        corrected.append([
            point[0] - offset[0],
            point[1] - offset[1]
        ])

    return corrected


def interpolate_offset(frame, keyframes, values):
    """线性插值偏移量"""

    if frame <= keyframes[0]:
        return values[0]
    if frame >= keyframes[-1]:
        return values[-1]

    for i in range(len(keyframes) - 1):
        if keyframes[i] <= frame <= keyframes[i + 1]:
            t = (frame - keyframes[i]) / (keyframes[i + 1] - keyframes[i])
            return [
                values[i][0] * (1 - t) + values[i + 1][0] * t,
                values[i][1] * (1 - t) + values[i + 1][1] * t
            ]

    return [0.0, 0.0]
```

---

## 三、手动修正技术

### 3.1 关键帧修正

在问题帧手动调整跟踪位置：

```python
# 伪代码：关键帧手动修正
def manual_keyframe_correction(track, frame, new_position):
    """在指定帧手动修正跟踪位置"""
    track.property("position").setValue(new_position, frame)
    print(f"[SILHOUETTE] 帧 {frame} 已修正到 {new_position}")
```

### 3.2 分段修正

将序列分为多段，每段独立修正：

```python
def segment_correction(track_data, segments):
    """
    分段修正
    segments: [(start, end, offset), ...]
    """
    corrected = list(track_data)

    for start, end, offset in segments:
        for i in range(start, end + 1):
            if i < len(corrected):
                corrected[i] = [
                    corrected[i][0] - offset[0],
                    corrected[i][1] - offset[1]
                ]

    return corrected
```

### 3.3 区域修正

对特定区域的跟踪数据进行修正：

```python
def region_correction(track_data, region, correction):
    """
    修正特定区域内的跟踪点
    region: [x_min, y_min, x_max, y_max]
    correction: [dx, dy]
    """
    corrected = []
    for point in track_data:
        if region[0] <= point[0] <= region[2] and region[1] <= point[1] <= region[3]:
            corrected.append([
                point[0] + correction[0],
                point[1] + correction[1]
            ])
        else:
            corrected.append(point)

    return corrected
```

### 3.4 交互式修正工作流

```
1. 全自动跟踪
2. 逐帧回放检查
3. 标记问题帧
4. 在问题帧手动调整
5. 重新跟踪问题帧附近
6. 验证修正效果
7. 迭代直到满意
```

---

## 四、融合策略

### 4.1 多跟踪结果融合

当有多个跟踪结果时，可融合以提高精度：

```python
def fuse_track_results(track_results, weights=None):
    """融合多个跟踪结果"""

    n_results = len(track_results)
    n_frames = len(track_results[0])

    if weights is None:
        weights = [1.0 / n_results] * n_results

    fused = []
    for frame_idx in range(n_frames):
        fused_x = sum(
            track_results[i][frame_idx][0] * weights[i]
            for i in range(n_results)
        )
        fused_y = sum(
            track_results[i][frame_idx][1] * weights[i]
            for i in range(n_results)
        )
        fused.append([fused_x, fused_y])

    return fused
```

### 4.2 加权融合

根据跟踪质量分配权重：

```python
def weighted_fuse(track_results, confidences):
    """根据置信度加权融合"""

    n_results = len(track_results)
    n_frames = len(track_results[0])

    fused = []
    for frame_idx in range(n_frames):
        total_weight = 0
        fused_x = 0
        fused_y = 0

        for i in range(n_results):
            weight = confidences[i][frame_idx]
            fused_x += track_results[i][frame_idx][0] * weight
            fused_y += track_results[i][frame_idx][1] * weight
            total_weight += weight

        fused.append([fused_x / total_weight, fused_y / total_weight])

    return fused
```

### 4.3 中值融合

中值融合对异常值具有鲁棒性：

```python
def median_fuse(track_results):
    """中值融合"""

    n_frames = len(track_results[0])

    fused = []
    for frame_idx in range(n_frames):
        x_values = [track_results[i][frame_idx][0] for i in range(len(track_results))]
        y_values = [track_results[i][frame_idx][1] for i in range(len(track_results))]

        x_values.sort()
        y_values.sort()

        median_x = x_values[len(x_values) // 2]
        median_y = y_values[len(y_values) // 2]

        fused.append([median_x, median_y])

    return fused
```

### 4.4 融合策略选择

| 策略 | 优势 | 适用场景 |
|------|------|----------|
| 平均融合 | 简单 | 跟踪质量相近 |
| 加权融合 | 精度高 | 跟踪质量差异大 |
| 中值融合 | 抗异常 | 个别跟踪不稳定 |
| 主从融合 | 一致性 | 有主跟踪参考 |

---

## 五、匹配工作流

### 5.1 完整匹配工作流

```
1. 分析两段素材的运动特征
2. 分别跟踪两段素材
3. 计算运动变换关系
4. 应用变换到目标素材
5. 检查匹配效果
6. 手动修正偏差
7. 渲染输出
```

### 5.2 元素合成匹配

将 CG 元素合成到实拍镜头：

```python
from fx import *

# 项目初始化
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Motion_Match"
activate(session)
proj.addItem(session)

# 实拍素材
src_live = Node("SourceNode")
src_live.property("mediaPath").setValue("D:/footage/live.mov", 0)
src_live.property("frameRate").setValue(24.0, 0)
session.addNode(src_live)

# 跟踪实拍素材
track = Node("TrackerNode")
track.label = "Live_Track"
track.property("trackType").setValue("planar", 0)
track.property("motionModel").setValue("perspective", 0)
track.property("accuracy").setValue("high", 0)
session.addNode(track)

# CG 元素
src_cg = Node("SourceNode")
src_cg.property("mediaPath").setValue("D:/footage/cg_element.mov", 0)
src_cg.property("frameRate").setValue(24.0, 0)
session.addNode(src_cg)

# 合成节点（应用跟踪变换）
composite = Node("CompositeNode")
composite.label = "Motion_Match"
session.addNode(composite)

# 连接
src_live.outputs[0].connect(track.inputs[0])
track.outputs[0].connect(composite.inputs[0])
src_cg.outputs[0].connect(composite.inputs[1])

print("[SILHOUETTE] Motion match pipeline ready")
```

### 5.3 匹配验证

```python
def verify_motion_match(source_motion, target_motion, threshold=1.0):
    """验证运动匹配质量"""

    errors = []
    for src, tgt in zip(source_motion, target_motion):
        error = ((src[0] - tgt[0])**2 + (src[1] - tgt[1])**2)**0.5
        errors.append(error)

    mean_error = sum(errors) / len(errors)
    max_error = max(errors)

    print(f"[SILHOUETTE] 匹配验证:")
    print(f"  平均误差: {mean_error:.2f} 像素")
    print(f"  最大误差: {max_error:.2f} 像素")

    if mean_error < threshold:
        print(f"  质量: 良好（< {threshold} 像素）")
        return True
    else:
        print(f"  质量: 需改进（> {threshold} 像素）")
        return False
```

---

## 六、高级匹配技巧

### 6.1 多点匹配

使用多点跟踪提高匹配精度：

```python
def multi_point_match(source_points, target_points):
    """多点运动匹配"""

    # 计算变换矩阵
    transform = compute_transform(source_points, target_points)

    return transform


def compute_transform(src_points, tgt_points):
    """计算从源到目标的变换矩阵"""

    if len(src_points) >= 4:
        # 四点：透视变换
        return compute_perspective_transform(src_points, tgt_points)
    elif len(src_points) >= 3:
        # 三点：仿射变换
        return compute_affine_transform(src_points, tgt_points)
    elif len(src_points) >= 2:
        # 两点：平移+旋转
        return compute_similarity_transform(src_points, tgt_points)
    else:
        # 单点：平移
        return compute_translation(src_points, tgt_points)
```

### 6.2 时序对齐

当两段素材时序不一致时，需先对齐时序：

```python
def align_temporal(source_motion, target_motion, offset_frames=0):
    """时序对齐"""

    if offset_frames > 0:
        # 源延后
        aligned_source = source_motion[offset_frames:]
    elif offset_frames < 0:
        # 源提前
        aligned_source = [source_motion[0]] * (-offset_frames) + source_motion
    else:
        aligned_source = source_motion

    return aligned_source
```

### 6.3 运动平滑匹配

匹配时保留原始运动的平滑性：

```python
def smooth_motion_match(source_motion, target_motion, smoothness=0.5):
    """平滑运动匹配"""

    # 直接匹配
    direct_match = target_motion

    # 平滑匹配
    smoothed = smooth_data(target_motion, window=5)

    # 混合
    matched = [
        [
            direct_match[i][0] * (1 - smoothness) + smoothed[i][0] * smoothness,
            direct_match[i][1] * (1 - smoothness) + smoothed[i][1] * smoothness
        ]
        for i in range(len(target_motion))
    ]

    return matched
```

---

## 七、质量验证

### 7.1 验证维度

| 维度 | 说明 | 评估方法 |
|------|------|----------|
| 位置精度 | 位置匹配程度 | 像素误差 |
| 运动一致性 | 运动曲线一致性 | 时序分析 |
| 边缘对齐 | 边缘对齐程度 | 视觉检查 |
| 透视正确 | 透视变换正确 | 几何验证 |
| 时序同步 | 时间对齐 | 帧对比 |

### 7.2 视觉验证

1. **A/B 对比**：交替查看源和匹配结果
2. **差值图**：查看差值，理想为 0
3. **边缘检查**：放大查看边缘对齐
4. **运动回放**：回放检查运动一致性

### 7.3 量化验证

```python
def comprehensive_verification(source, target):
    """综合量化验证"""

    # 位置误差
    position_errors = [
        ((s[0]-t[0])**2 + (s[1]-t[1])**2)**0.5
        for s, t in zip(source, target)
    ]
    mean_pos_error = sum(position_errors) / len(position_errors)

    # 运动一致性（速度差）
    velocity_errors = []
    for i in range(1, len(source)):
        src_vel = [source[i][0] - source[i-1][0], source[i][1] - source[i-1][1]]
        tgt_vel = [target[i][0] - target[i-1][0], target[i][1] - target[i-1][1]]
        vel_error = ((src_vel[0]-tgt_vel[0])**2 + (src_vel[1]-tgt_vel[1])**2)**0.5
        velocity_errors.append(vel_error)
    mean_vel_error = sum(velocity_errors) / len(velocity_errors)

    print(f"位置误差: {mean_pos_error:.2f} 像素")
    print(f"速度误差: {mean_vel_error:.2f} 像素/帧")

    return mean_pos_error, mean_vel_error
```

---

## 八、故障排查

### 8.1 匹配偏差大

| 原因 | 解决方案 |
|------|----------|
| 跟踪精度不足 | 提高跟踪精度 |
| 运动模型不匹配 | 切换运动模型 |
| 时序不对齐 | 调整时序偏移 |
| 坐标系不一致 | 转换坐标系 |

### 8.2 匹配抖动

| 原因 | 解决方案 |
|------|----------|
| 跟踪数据抖动 | 平滑跟踪数据 |
| 融合权重不当 | 调整融合权重 |
| 关键帧过密 | 减少关键帧 |

### 8.3 匹配漂移

| 原因 | 解决方案 |
|------|----------|
| 跟踪漂移 | 修正跟踪漂移 |
| 累积误差 | 定期关键帧修正 |
| 模板老化 | 更新跟踪模板 |

### 8.4 质量检查清单

- [ ] 位置误差 < 1.0 像素
- [ ] 运动曲线一致
- [ ] 边缘对齐良好
- [ ] 透视变换正确
- [ ] 时序同步
- [ ] 无抖动、无漂移
- [ ] 视觉效果自然

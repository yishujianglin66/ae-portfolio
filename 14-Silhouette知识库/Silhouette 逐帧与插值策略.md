# Silhouette 逐帧与插值策略

- **分类**: Roto抠像专题
- **更新日期**: 2026-07-11
- **概述**: 本文档系统阐述 Silhouette 中 Roto 形状的关键帧间隔选择、运动预测、复杂运动分解与循环动画处理策略。涵盖线性/贝塞尔/阶梯三种插值模式的适用场景，提供逐帧与稀疏关键帧的平衡方法论，以及针对高速运动、形变运动、遮挡场景的实战方案，帮助抠像工程师在精度与效率之间取得最优平衡。

## 目录

1. [关键帧间隔选择](#一关键帧间隔选择)
2. [插值模式详解](#二插值模式详解)
3. [运动预测与外推](#三运动预测与外推)
4. [复杂运动处理](#四复杂运动处理)
5. [循环动画处理](#五循环动画处理)
6. [关键帧优化策略](#六关键帧优化策略)
7. [代码示例](#七代码示例)
8. [常见问题与最佳实践](#八常见问题与最佳实践)
9. [相关文档](#九相关文档)

---

## 一、关键帧间隔选择

### 1.1 间隔选择原则

关键帧间隔直接决定 Roto 质量与工作效率的平衡。基本原则：**运动剧烈处加密，运动平缓处稀疏**。

| 运动类型 | 推荐间隔 | 适用场景 |
|---------|---------|---------|
| 静止/微动 | 每 10-20 帧 | 背景物体、站立人物 |
| 缓慢运动 | 每 5-10 帧 | 行走、缓慢转身 |
| 正常运动 | 每 2-5 帧 | 普通对话场景 |
| 快速运动 | 每 1-2 帧 | 跑步、打斗、运动镜头 |
| 高速运动 | 逐帧 | 抖动、爆炸、快镜头 |

### 1.2 间隔决策流程

```
分析素材运动 → 识别关键转折点 → 设置主关键帧 → 检查插值偏差 → 补充次关键帧
```

**关键转折点**识别特征：
- 运动方向改变处（如人物转身）
- 速度突变处（如起步、停止）
- 形状轮廓变化处（如肢体弯曲）
- 遮挡开始/结束处

### 1.3 智能间隔算法

```python
def calculate_keyframe_interval(motion_speed, object_size, fps):
    """根据运动速度、对象大小、帧率计算推荐关键帧间隔"""
    # motion_speed: 像素/帧
    # object_size: 对象在画面中的像素尺寸
    # fps: 帧率
    
    # 计算每帧运动占对象尺寸的比例
    motion_ratio = motion_speed / max(object_size, 1)
    
    # 最大容许偏差（像素）：通常为对象尺寸的 2%
    max_deviation = object_size * 0.02
    
    # 基础间隔：基于运动速度
    if motion_speed < 0.5:
        base_interval = 15
    elif motion_speed < 2.0:
        base_interval = 8
    elif motion_speed < 5.0:
        base_interval = 4
    elif motion_speed < 10.0:
        base_interval = 2
    else:
        base_interval = 1
    
    # 根据帧率调整
    fps_factor = fps / 24.0
    adjusted_interval = int(base_interval / fps_factor)
    
    return max(1, adjusted_interval)


def analyze_motion_segments(source_path, frame_start, frame_end):
    """分析素材运动分段，输出每段的关键帧间隔建议"""
    segments = []
    
    # 模拟运动分析（实际应调用 TrackerNode 或 AI 分析）
    # 假设将帧范围分为 5 段分析
    num_segments = 5
    seg_length = (frame_end - frame_start) / num_segments
    
    for i in range(num_segments):
        seg_start = int(frame_start + i * seg_length)
        seg_end = int(frame_start + (i + 1) * seg_length)
        
        # 模拟：实际中应通过跟踪数据计算
        avg_motion = 3.0 + i * 0.5  # 示例数据
        interval = calculate_keyframe_interval(avg_motion, 200, 30)
        
        segments.append({
            "start_frame": seg_start,
            "end_frame": seg_end,
            "avg_motion": avg_motion,
            "recommended_interval": interval
        })
    
    return segments
```

### 1.4 不同场景的间隔策略

**人物对话场景**：
- 头部：每 3-5 帧（说话时微动频繁）
- 肩膀：每 8-10 帧（相对稳定）
- 头发：每 1-2 帧（飘动明显）

**动作场景**：
- 主体轮廓：每 1-2 帧
- 快速运动部位（手脚）：逐帧
- 衣服飘动：每 2-3 帧

**产品广告**：
- 静态产品：每 20-30 帧
- 旋转产品：每 5-8 帧
- 反光/高光区域：每 3-5 帧

---

## 二、插值模式详解

### 2.1 三种插值模式

Silhouette 支持三种关键帧插值模式，各有适用场景：

| 模式 | 数学描述 | 适用场景 | 优点 | 缺点 |
|------|---------|---------|------|------|
| **Linear（线性）** | 直线连接 | 匀速运动、机械运动 | 计算快、可预测 | 转折生硬 |
| **Bezier（贝塞尔）** | 三次贝塞尔曲线 | 有机运动、人物运动 | 平滑自然 | 调整复杂 |
| **Step（阶梯）** | 保持上一帧值 | 突变、遮挡切换 | 精确控制 | 不连续 |

### 2.2 Linear 插值

```python
# 设置关键帧并使用线性插值
shape = roto.property("shapes").getValue(0)[0]
point = shape.points[0]

# 在帧 0、10、20 设置位置
point.property("position").setValue([100, 200], 0)
point.property("position").setValue([150, 220], 10)
point.property("position").setValue([200, 200], 20)

# 设置线性插值（默认）
point.property("position").setInterpolation("linear", 0)
point.property("position").setInterpolation("linear", 1)
```

**适用场景**：
- 机械臂、传送带等匀速运动
- 镜头平移中的静态物体
- 简单的 UI 元素动画

### 2.3 Bezier 插值（推荐）

```python
# 贝塞尔插值提供更自然的运动曲线
point.property("position").setValue([100, 200], 0)
point.property("position").setValue([150, 250], 10)
point.property("position").setValue([200, 200], 20)

# 设置贝塞尔插值
for i in range(3):
    point.property("position").setInterpolation("bezier", i)

# 调整切线手柄控制曲线形状
# inTangent: 进入关键帧的切线
# outTangent: 离开关键帧的切线
point.property("inTangent").setValue([10, 5], 10)
point.property("outTangent").setValue([-10, -5], 10)
```

**切线调整原则**：
- **平滑过渡**：手柄长度对称
- **急停效果**：手柄长度缩短为 0
- **缓入缓出**：手柄长度适当延长

### 2.4 Step 插值

```python
# 阶梯插值：值在关键帧之间保持不变
# 适用于突然切换的场景
roto.property("alpha.blur").setValue(0.5, 0)
roto.property("alpha.blur").setValue(1.2, 25)
roto.property("alpha.blur").setValue(0.5, 50)

for i in range(3):
    roto.property("alpha.blur").setInterpolation("step", i)

# 帧 0-24: alpha.blur = 0.5
# 帧 25-49: alpha.blur = 1.2
# 帧 50+: alpha.blur = 0.5
```

**适用场景**：
- 遮挡物突然出现/消失
- 镜头切换（cut）
- 形状层级突变

### 2.5 混合插值策略

实际项目中常需要混合使用多种插值模式：

```python
def apply_mixed_interpolation(shape, keyframes):
    """为形状的关键帧应用混合插值策略"""
    """
    keyframes: [
        {"frame": 0, "type": "linear", "reason": "起步"},
        {"frame": 5, "type": "bezier", "reason": "加速"},
        {"frame": 15, "type": "bezier", "reason": "匀速"},
        {"frame": 25, "type": "step", "reason": "遮挡切换"},
        {"frame": 26, "type": "bezier", "reason": "继续运动"}
    ]
    """
    for kf in keyframes:
        shape.property("position").setInterpolation(
            kf["type"], 
            kf["frame"]
        )
        print(f"帧 {kf['frame']}: {kf['type']} ({kf['reason']})")
```

---

## 三、运动预测与外推

### 3.1 运动预测原理

基于已有跟踪数据，预测未来帧的对象位置，减少关键帧设置工作量。

```python
def predict_next_position(history_positions, frames_ahead=1):
    """基于历史位置数据预测未来位置
    
    history_positions: [(frame, x, y), ...]
    frames_ahead: 预测帧数
    """
    if len(history_positions) < 2:
        return None
    
    # 取最近 5 帧数据
    recent = history_positions[-5:]
    
    # 计算平均速度
    velocities = []
    for i in range(1, len(recent)):
        dt = recent[i][0] - recent[i-1][0]
        if dt == 0:
            continue
        vx = (recent[i][1] - recent[i-1][1]) / dt
        vy = (recent[i][2] - recent[i-1][2]) / dt
        velocities.append((vx, vy))
    
    if not velocities:
        return None
    
    # 加权平均（最近的帧权重更高）
    total_weight = 0
    avg_vx, avg_vy = 0, 0
    for i, (vx, vy) in enumerate(velocities):
        weight = i + 1  # 越近权重越大
        avg_vx += vx * weight
        avg_vy += vy * weight
        total_weight += weight
    
    avg_vx /= total_weight
    avg_vy /= total_weight
    
    # 预测位置
    last_frame, last_x, last_y = recent[-1]
    predicted_x = last_x + avg_vx * frames_ahead
    predicted_y = last_y + avg_vy * frames_ahead
    
    return {
        "frame": last_frame + frames_ahead,
        "x": predicted_x,
        "y": predicted_y,
        "velocity": (avg_vx, avg_vy)
    }


def propagate_shape_forward(shape, start_frame, end_frame, step=2):
    """基于起始帧形状向前传播，自动生成预测关键帧"""
    # 获取起始帧所有点位置
    points = shape.points
    history = {}
    
    for point in points:
        pos = point.property("position").getValue(start_frame)
        history[point] = [(start_frame, pos[0], pos[1])]
    
    # 逐段预测并设置关键帧
    current_frame = start_frame
    while current_frame < end_frame:
        next_frame = min(current_frame + step, end_frame)
        
        for point in points:
            prediction = predict_next_position(
                history[point], 
                frames_ahead=next_frame - current_frame
            )
            if prediction:
                point.property("position").setValue(
                    [prediction["x"], prediction["y"]], 
                    next_frame
                )
                history[point].append(
                    (next_frame, prediction["x"], prediction["y"])
                )
        
        current_frame = next_frame
    
    print(f"[SILHOUETTE] 形状已从帧 {start_frame} 传播至 {end_frame}")
```

### 3.2 基于跟踪的运动预测

```python
def track_and_predict(source_node, roto_node, track_frame, predict_frames):
    """结合 TrackerNode 数据进行运动预测"""
    
    # 创建跟踪节点
    tracker = Node("TrackerNode")
    tracker.label = "Motion_Predictor"
    tracker.property("trackType").setValue("point", 0)
    tracker.property("accuracy").setValue("high", 0)
    tracker.property("forward").setValue(true, 0)
    
    # 连接：源 → 跟踪 → Roto obey_matte
    source_node.outputs[0].connect(tracker.inputs[0])
    tracker.outputs[0].connect(roto_node.inputs[4])  # data 输入
    
    # 获取跟踪数据
    track_data = tracker.property("trackingData").getValue(track_frame)
    
    # 基于跟踪数据预测
    predictions = []
    for f in predict_frames:
        if f < len(track_data):
            predictions.append({
                "frame": f,
                "position": track_data[f],
                "confidence": 0.9
            })
    
    return predictions
```

### 3.3 外推策略

当关键帧范围之外需要继续动画时，使用外推策略：

```python
def extrapolate_motion(shape, key_frames, extrapolate_type="constant"):
    """外推运动到关键帧范围之外
    
    extrapolate_type: 
        "constant" - 保持最后值
        "linear" - 线性外推
        "cycle" - 循环
    """
    if not key_frames:
        return
    
    last_frame = max(key_frames.keys())
    first_frame = min(key_frames.keys())
    
    if extrapolate_type == "constant":
        # 保持最后值
        for point in shape.points:
            last_pos = point.property("position").getValue(last_frame)
            point.property("position").setValue(last_pos, last_frame + 100)
    
    elif extrapolate_type == "linear":
        # 线性外推
        for point in shape.points:
            if last_frame - 1 in key_frames and last_frame in key_frames:
                prev_pos = point.property("position").getValue(last_frame - 1)
                last_pos = point.property("position").getValue(last_frame)
                velocity = [
                    last_pos[0] - prev_pos[0],
                    last_pos[1] - prev_pos[1]
                ]
                future_pos = [
                    last_pos[0] + velocity[0] * 50,
                    last_pos[1] + velocity[1] * 50
                ]
                point.property("position").setValue(future_pos, last_frame + 50)
    
    elif extrapolate_type == "cycle":
        # 循环外推
        cycle_length = last_frame - first_frame
        for point in shape.points:
            for offset in range(1, 5):
                target_frame = last_frame + offset * cycle_length
                for f in range(first_frame, last_frame + 1):
                    pos = point.property("position").getValue(f)
                    point.property("position").setValue(
                        pos, 
                        target_frame + (f - first_frame)
                    )
```

---

## 四、复杂运动处理

### 4.1 形变运动

形变运动指物体形状本身发生变化（如人物弯腰、衣物飘动）。

```python
def handle_deformation_motion(roto_node, shape, deformation_keyframes):
    """处理形变运动
    
    deformation_keyframes: [
        {"frame": 0, "point_indices": [0,1,2], "positions": [[x,y],...]},
        ...
    ]
    """
    for kf in deformation_keyframes:
        frame = kf["frame"]
        point_indices = kf["point_indices"]
        positions = kf["positions"]
        
        for i, point_idx in enumerate(point_indices):
            if point_idx < len(shape.points):
                point = shape.points[point_idx]
                point.property("position").setValue(positions[i], frame)
                # 形变运动使用贝塞尔插值
                point.property("position").setInterpolation("bezier", frame)
    
    print(f"[SILHOUETTE] 形变运动已设置 {len(deformation_keyframes)} 个关键帧")


def create_layered_deformation(roto_node):
    """创建分层形变结构（适用于人物弯腰等复杂动作）"""
    
    # 主轮廓层
    body_shape = createObject("X-Spline")
    body_shape.name = "Body_Main"
    body_shape.closed = True
    roto_node.property("shapes").setValue([body_shape], 0)
    
    # 子部位层（如手臂、腿）
    arm_shape = createObject("X-Spline")
    arm_shape.name = "Arm_Sub"
    arm_shape.closed = True
    arm_shape.parent = body_shape  # 设置父级
    
    leg_shape = createObject("X-Spline")
    leg_shape.name = "Leg_Sub"
    leg_shape.closed = True
    leg_shape.parent = body_shape
    
    return body_shape, arm_shape, leg_shape
```

### 4.2 旋转运动

```python
def handle_rotation_motion(shape, center_point, rotations):
    """处理旋转运动
    
    center_point: [x, y] 旋转中心
    rotations: [(frame, angle_degrees), ...]
    """
    import math
    
    # 获取初始位置
    initial_positions = []
    for point in shape.points:
        pos = point.property("position").getValue(0)
        initial_positions.append(pos)
    
    # 为每个旋转关键帧设置点位置
    for frame, angle in rotations:
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        
        for i, point in enumerate(shape.points):
            # 相对中心的初始位置
            dx = initial_positions[i][0] - center_point[0]
            dy = initial_positions[i][1] - center_point[1]
            
            # 旋转后的位置
            new_x = center_point[0] + dx * cos_a - dy * sin_a
            new_y = center_point[1] + dx * sin_a + dy * cos_a
            
            point.property("position").setValue([new_x, new_y], frame)
            # 旋转运动使用贝塞尔插值更平滑
            point.property("position").setInterpolation("bezier", frame)
```

### 4.3 遮挡处理

```python
def handle_occlusion(roto_node, occlusion_ranges):
    """处理遮挡场景
    
    occlusion_ranges: [(start_frame, end_frame, strategy), ...]
    strategy: "hold" | "predict" | "track"
    """
    for start, end, strategy in occlusion_ranges:
        if strategy == "hold":
            # 保持遮挡前的形状
            print(f"帧 {start}-{end}: 保持策略")
            # 获取遮挡前最后一帧的形状
            # 在整个遮挡期间保持该形状
            
        elif strategy == "predict":
            # 基于运动预测
            print(f"帧 {start}-{end}: 预测策略")
            # 使用运动预测算法
            
        elif strategy == "track":
            # 使用跟踪数据
            print(f"帧 {start}-{end}: 跟踪策略")
            # 连接 TrackerNode 提供位置数据
    
    # 设置 Step 插值以避免遮挡期间的不自然变化
    for start, end, _ in occlusion_ranges:
        roto_node.property("opacity").setValue(0.0, start)
        roto_node.property("opacity").setValue(0.0, end - 1)
        roto_node.property("opacity").setValue(1.0, end)
        roto_node.property("opacity").setInterpolation("step", start)
        roto_node.property("opacity").setInterpolation("step", end)
```

### 4.4 快速运动模糊

```python
def handle_fast_motion(roto_node, motion_speed):
    """处理快速运动，启用运动模糊"""
    
    # 根据运动速度调整运动模糊参数
    if motion_speed > 20:
        shutter = 1.0
        samples = 8
    elif motion_speed > 10:
        shutter = 0.7
        samples = 4
    else:
        shutter = 0.5
        samples = 2
    
    roto_node.property("motionBlur").setValue(True, 0)
    roto_node.property("motionBlur.shutter").setValue(shutter, 0)
    roto_node.property("motionBlur.samples").setValue(samples, 0)
    
    # 快速运动需要更密集的关键帧
    recommended_interval = max(1, int(10 / motion_speed))
    
    print(f"[SILHOUETTE] 快速运动配置:")
    print(f"  运动模糊: shutter={shutter}, samples={samples}")
    print(f"  推荐关键帧间隔: {recommended_interval}")
    
    return recommended_interval
```

---

## 五、循环动画处理

### 5.1 循环动画原理

循环动画指动作在特定帧数后重复（如行走、跑步、呼吸）。Silhouette 支持通过关键帧复制实现循环。

```python
def create_loop_animation(shape, loop_start, loop_end, repeat_count=3):
    """创建循环动画
    
    loop_start: 循环起始帧
    loop_end: 循环结束帧
    repeat_count: 重复次数
    """
    cycle_length = loop_end - loop_start
    
    # 保存原始关键帧数据
    original_keys = {}
    for point in shape.points:
        prop = point.property("position")
        keys = []
        for k in range(prop.numKeys):
            frame = prop.keyTime(k)
            if loop_start <= frame <= loop_end:
                value = prop.keyValue(k)
                keys.append((frame, value))
        original_keys[point] = keys
    
    # 复制关键帧到后续周期
    for cycle in range(1, repeat_count):
        offset = cycle * cycle_length
        for point, keys in original_keys.items():
            for frame, value in keys:
                new_frame = frame + offset
                point.property("position").setValue(value, new_frame)
    
    print(f"[SILHOUETTE] 循环动画已创建")
    print(f"  循环范围: {loop_start}-{loop_end} ({cycle_length} 帧)")
    print(f"  重复次数: {repeat_count}")
    print(f"  总帧数: {loop_start + cycle_length * repeat_count}")


def create_seamless_loop(shape, loop_frame):
    """创建无缝循环（首尾衔接）"""
    # 获取第一帧的所有点位置
    first_frame_positions = []
    for point in shape.points:
        pos = point.property("position").getValue(0)
        first_frame_positions.append(pos)
    
    # 在循环帧设置相同位置
    for i, point in enumerate(shape.points):
        point.property("position").setValue(first_frame_positions[i], loop_frame)
        # 使用贝塞尔插值确保平滑过渡
        point.property("position").setInterpolation("bezier", loop_frame)
    
    print(f"[SILHOUETTE] 无缝循环已创建，循环点：帧 {loop_frame}")
```

### 5.2 行走循环示例

```python
def create_walking_cycle(roto_node, character_shape, fps=30):
    """创建行走循环动画
    
    标准行走周期：约 1 秒（30 帧 @ 30fps）
    """
    # 行走周期：30 帧
    cycle_length = fps  # 1 秒一个周期
    
    # 关键帧：5 个关键姿势
    # 帧 0: 起步姿势
    # 帧 7: 第一接触
    # 帧 15: 中间姿势（反向）
    # 帧 22: 第二接触
    # 帧 30: 回到起步（循环）
    
    key_poses = [
        {"frame": 0, "description": "起步"},
        {"frame": 7, "description": "第一接触"},
        {"frame": 15, "description": "中间姿势"},
        {"frame": 22, "description": "第二接触"},
        {"frame": 30, "description": "循环点"}
    ]
    
    # 为每个关键姿势设置形状
    for pose in key_poses:
        # 实际应设置具体的点位置
        # 这里展示框架
        for point in character_shape.points:
            # 使用贝塞尔插值
            point.property("position").setInterpolation(
                "bezier", 
                pose["frame"]
            )
    
    # 复制循环 3 次（共 4 个周期）
    create_loop_animation(character_shape, 0, cycle_length, repeat_count=4)
    
    print(f"[SILHOUETTE] 行走循环已创建")
    print(f"  周期长度: {cycle_length} 帧 ({cycle_length/fps:.1f} 秒)")
    print(f"  关键姿势数: {len(key_poses)}")
    print(f"  总循环次数: 4")
```

### 5.3 往复运动

```python
def create_ping_pong_animation(shape, forward_keys, repeat_count=3):
    """创建往复运动（正向→反向→正向...）
    
    forward_keys: [(frame, position), ...] 正向关键帧
    """
    cycle_length = forward_keys[-1][0] - forward_keys[0][0]
    
    for cycle in range(repeat_count):
        # 正向阶段
        forward_offset = cycle * 2 * cycle_length
        for frame, pos in forward_keys:
            for point in shape.points:
                orig_pos = point.property("position").getValue(frame)
                point.property("position").setValue(
                    orig_pos, 
                    frame + forward_offset
                )
        
        # 反向阶段
        backward_offset = (cycle * 2 + 1) * cycle_length
        for frame, pos in reversed(forward_keys):
            reversed_frame = (cycle_length - (frame - forward_keys[0][0]))
            for point in shape.points:
                orig_pos = point.property("position").getValue(frame)
                point.property("position").setValue(
                    orig_pos,
                    reversed_frame + backward_offset
                )
    
    print(f"[SILHOUETTE] 往复运动已创建，重复 {repeat_count} 次")
```

---

## 六、关键帧优化策略

### 6.1 关键帧精简

```python
def optimize_keyframes(shape, tolerance=1.0):
    """精简冗余关键帧
    
    tolerance: 容许偏差（像素）
    """
    removed_count = 0
    
    for point in shape.points:
        prop = point.property("position")
        if prop.numKeys < 3:
            continue
        
        # 检查每个关键帧是否可以移除
        keys_to_remove = []
        for k in range(1, prop.numKeys - 1):
            frame = prop.keyTime(k)
            prev_frame = prop.keyTime(k - 1)
            next_frame = prop.keyTime(k + 1)
            
            # 获取实际值
            actual_value = prop.keyValue(k)
            
            # 计算线性插值预测值
            prev_value = prop.keyValue(k - 1)
            next_value = prop.keyValue(k + 1)
            t = (frame - prev_frame) / (next_frame - prev_frame)
            predicted_value = [
                prev_value[0] + (next_value[0] - prev_value[0]) * t,
                prev_value[1] + (next_value[1] - prev_value[1]) * t
            ]
            
            # 计算偏差
            deviation = (
                (actual_value[0] - predicted_value[0]) ** 2 +
                (actual_value[1] - predicted_value[1]) ** 2
            ) ** 0.5
            
            if deviation < tolerance:
                keys_to_remove.append(k)
        
        # 移除冗余关键帧（从后向前）
        for k in reversed(keys_to_remove):
            prop.removeKey(k)
            removed_count += 1
    
    print(f"[SILHOUETTE] 已移除 {removed_count} 个冗余关键帧")
    return removed_count


def adaptive_keyframe_density(shape, motion_threshold=2.0):
    """自适应关键帧密度：运动剧烈处加密，平缓处稀疏"""
    # 分析运动速度
    speeds = []
    for point in shape.points:
        prop = point.property("position")
        if prop.numKeys < 2:
            continue
        
        for k in range(1, prop.numKeys):
            prev_pos = prop.keyValue(k - 1)
            curr_pos = prop.keyValue(k)
            prev_frame = prop.keyTime(k - 1)
            curr_frame = prop.keyTime(k)
            
            dt = curr_frame - prev_frame
            if dt > 0:
                speed = (
                    (curr_pos[0] - prev_pos[0]) ** 2 +
                    (curr_pos[1] - prev_pos[1]) ** 2
                ) ** 0.5 / dt
                speeds.append((curr_frame, speed))
    
    # 识别需要加密的区域
    high_motion_frames = [
        f for f, s in speeds if s > motion_threshold
    ]
    
    print(f"[SILHOUETTE] 识别到 {len(high_motion_frames)} 个高运动帧")
    print(f"  建议在这些帧附近补充关键帧")
    
    return high_motion_frames
```

### 6.2 关键帧平滑

```python
def smooth_keyframes(shape, window_size=3):
    """平滑关键帧动画曲线
    
    window_size: 平滑窗口大小
    """
    for point in shape.points:
        prop = point.property("position")
        if prop.numKeys < window_size:
            continue
        
        # 收集所有关键帧值
        key_values = []
        for k in range(prop.numKeys):
            key_values.append(prop.keyValue(k))
        
        # 移动平均平滑
        smoothed_values = []
        half_window = window_size // 2
        for i in range(len(key_values)):
            start = max(0, i - half_window)
            end = min(len(key_values), i + half_window + 1)
            
            avg_x = sum(v[0] for v in key_values[start:end]) / (end - start)
            avg_y = sum(v[1] for v in key_values[start:end]) / (end - start)
            
            smoothed_values.append([avg_x, avg_y])
        
        # 应用平滑后的值
        for k in range(prop.numKeys):
            prop.setValue(smoothed_values[k], prop.keyTime(k))
    
    print(f"[SILHOUETTE] 关键帧已平滑，窗口大小: {window_size}")
```

---

## 七、代码示例

### 7.1 完整逐帧 Roto 流程

```python
from fx import *


def create_frame_by_frame_roto(source_path, output_path, frame_range, fps=30):
    """创建逐帧 Roto 流程
    
    适用于高速运动、复杂形变场景
    """
    # 创建项目和会话
    proj = activeProject() or Project()
    activate(proj)
    
    session = activeSession() or Session()
    session.label = "FrameByFrame_Roto"
    activate(session)
    proj.addItem(session)
    
    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(fps, 0)
    src.property("frameStart").setValue(frame_range[0], 0)
    src.property("frameEnd").setValue(frame_range[1], 0)
    session.addNode(src)
    
    # Roto 节点
    roto = Node("RotoNode")
    roto.label = "FrameByFrame_Main"
    roto.property("alpha.blur").setValue(0.5, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("motionBlur").setValue(True, 0)
    roto.property("motionBlur.shutter").setValue(0.5, 0)
    session.addNode(roto)
    
    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    session.addNode(out_node)
    
    # 连接节点
    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])
    
    print(f"[SILHOUETTE] 逐帧 Roto 流程已创建")
    print(f"  帧范围: {frame_range[0]}-{frame_range[1]}")
    print(f"  总帧数: {frame_range[1] - frame_range[0] + 1}")
    
    return roto


def setup_interpolation_strategy(roto_node, motion_analysis):
    """根据运动分析结果设置插值策略"""
    shape = roto_node.property("shapes").getValue(0)[0]
    
    for segment in motion_analysis:
        start = segment["start_frame"]
        end = segment["end_frame"]
        motion_type = segment["motion_type"]
        
        if motion_type == "linear":
            # 匀速运动：线性插值
            for f in range(start, end + 1, 2):
                for point in shape.points:
                    point.property("position").setInterpolation("linear", f)
        
        elif motion_type == "organic":
            # 有机运动：贝塞尔插值
            for f in range(start, end + 1, 3):
                for point in shape.points:
                    point.property("position").setInterpolation("bezier", f)
        
        elif motion_type == "sudden":
            # 突变：阶梯插值
            for f in range(start, end + 1):
                for point in shape.points:
                    point.property("position").setInterpolation("step", f)
    
    print(f"[SILHOUETTE] 插值策略已设置")
```

### 7.2 智能关键帧生成器

```python
def generate_smart_keyframes(roto_node, tracker_node, frame_range, density=0.3):
    """基于跟踪数据智能生成关键帧
    
    density: 关键帧密度（0-1，越高关键帧越多）
    """
    shape = roto_node.property("shapes").getValue(0)[0]
    
    # 获取跟踪数据
    track_data = tracker_node.property("trackingData")
    
    # 分析运动变化点
    change_points = []
    prev_velocity = None
    
    for f in range(frame_range[0], frame_range[1] + 1):
        if f < track_data.numKeys:
            pos = track_data.getValue(f)
            if f > 0:
                prev_pos = track_data.getValue(f - 1)
                velocity = (
                    pos[0] - prev_pos[0],
                    pos[1] - prev_pos[1]
                )
                
                if prev_velocity:
                    # 检测速度变化
                    accel = (
                        velocity[0] - prev_velocity[0],
                        velocity[1] - prev_velocity[1]
                    )
                    accel_mag = (accel[0]**2 + accel[1]**2) ** 0.5
                    
                    # 加速度超过阈值则标记为变化点
                    if accel_mag > 2.0 * density:
                        change_points.append(f)
                
                prev_velocity = velocity
    
    # 在变化点设置关键帧
    for f in change_points:
        for point in shape.points:
            # 根据跟踪数据设置点位置
            track_pos = track_data.getValue(f)
            point.property("position").setValue(track_pos, f)
            point.property("position").setInterpolation("bezier", f)
    
    print(f"[SILHOUETTE] 智能生成 {len(change_points)} 个关键帧")
    return change_points
```

### 7.3 循环动画工具集

```python
def create_breathing_animation(roto_node, breathe_rate=30, amplitude=2.0):
    """创建呼吸动画（适用于人物胸部区域）
    
    breathe_rate: 呼吸周期帧数
    amplitude: 呼吸幅度（像素）
    """
    import math
    
    shape = roto_node.property("shapes").getValue(0)[0]
    
    # 保存初始位置
    initial_positions = []
    for point in shape.points:
        pos = point.property("position").getValue(0)
        initial_positions.append(pos)
    
    # 生成呼吸循环
    cycle_count = 5
    for cycle in range(cycle_count):
        base_frame = cycle * breathe_rate
        
        # 4 个关键姿势：呼气→中间→吸气→中间
        phases = [
            (0, 0),  # 呼气结束
            (breathe_rate // 4, amplitude * 0.5),  # 吸气中
            (breathe_rate // 2, amplitude),  # 吸气结束
            (3 * breathe_rate // 4, amplitude * 0.5),  # 呼气中
        ]
        
        for phase_frame, scale in phases:
            target_frame = base_frame + phase_frame
            for i, point in enumerate(shape.points):
                # 简单的缩放模拟呼吸
                new_x = initial_positions[i][0]
                new_y = initial_positions[i][1] - scale  # 向上扩张
                point.property("position").setValue([new_x, new_y], target_frame)
                point.property("position").setInterpolation("bezier", target_frame)
    
    print(f"[SILHOUETTE] 呼吸动画已创建")
    print(f"  周期: {breathe_rate} 帧")
    print(f"  循环数: {cycle_count}")
    print(f"  幅度: {amplitude} 像素")
```

---

## 八、常见问题与最佳实践

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 插值导致形状漂移 | 关键帧间距过大 | 在转折点补充关键帧 |
| 循环动画接缝明显 | 首尾帧不一致 | 使用 `create_seamless_loop` |
| 快速运动出现重影 | 运动模糊设置不当 | 调整 shutter 至 0.3-0.5 |
| 形变动画不自然 | 关键帧过少或插值模式错误 | 改用贝塞尔插值，增加关键帧 |
| 预测偏差过大 | 运动模式变化 | 缩短预测范围，增加校准帧 |
| 阶梯插值闪烁 | 关键帧位置突变 | 检查帧间变化，使用过渡帧 |

### 8.2 最佳实践

**关键帧策略**：
1. **先稀后密**：先设置主关键帧（每 10 帧），再根据需要补充
2. **转折点优先**：运动方向/速度变化处必须有关键帧
3. **混合插值**：匀速段用线性，有机运动用贝塞尔，突变用阶梯
4. **循环检查**：设置完成后逐帧回放检查插值效果

**性能优化**：
1. **精简关键帧**：使用 `optimize_keyframes` 移除冗余
2. **分段处理**：长素材分段处理，避免一次性加载过多关键帧
3. **代理预览**：使用低分辨率代理预览动画效果
4. **批量操作**：对相似形状使用批量关键帧设置

**质量控制**：
1. **逐帧检查**：在关键帧之间逐帧检查形状贴合度
2. **边缘对比**：将遮罩边缘与原始素材对比
3. **运动测试**：在不同帧率下测试动画效果
4. **团队协作**：建立关键帧命名规范，便于交接

### 8.3 插值模式选择决策树

```
运动类型？
├── 机械/匀速 → Linear
├── 有机/人物 → Bezier
├── 突变/遮挡 → Step
└── 混合
    ├── 匀速段 → Linear
    ├── 加减速段 → Bezier
    └── 切换点 → Step
```

### 8.4 关键帧间隔速查表

| 场景 | 帧率 | 推荐间隔 | 插值模式 |
|------|------|---------|---------|
| 静态访谈 | 24fps | 8-12 帧 | Bezier |
| 动作片 | 24fps | 1-2 帧 | Bezier + 运动模糊 |
| 产品广告 | 30fps | 15-20 帧 | Linear |
| 体育运动 | 60fps | 1 帧 | Bezier + 运动模糊 |
| 动画参考 | 12fps | 1 帧 | Step |
| VFX 合成 | 24fps | 2-4 帧 | Bezier |

---

## 九、相关文档

- [Silhouette Roto遮罩完全指南](Silhouette%20Roto遮罩完全指南.md)
- [Silhouette 形状层与关键帧动画](Silhouette%20形状层与关键帧动画.md)
- [Silhouette 边缘优化与运动模糊](Silhouette%20边缘优化与运动模糊.md)
- [Silhouette 智能遮罩与AI辅助抠像](Silhouette%20智能遮罩与AI辅助抠像.md)
- [Silhouette Roto工作流最佳实践](Silhouette%20Roto工作流最佳实践.md)
- [Silhouette 遮罩质量检查与优化](Silhouette%20遮罩质量检查与优化.md)
- [Silhouette 跟踪技术实战手册](Silhouette%20跟踪技术实战手册.md)
- [Silhouette fx API 参数详解手册](Silhouette%20fx%20API%20参数详解手册.md)

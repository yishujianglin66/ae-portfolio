# Silhouette 逐帧修复策略

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: 逐帧修复的完整策略，包括关键帧规划、检查点设置、效率优化、质量控制等内容，适用于复杂场景和长序列的高质量修复任务。

## 目录

1. [逐帧修复概述](#一逐帧修复概述)
2. [关键帧规划](#二关键帧规划)
3. [检查点策略](#三检查点策略)
4. [效率优化技巧](#四效率优化技巧)
5. [质量控制流程](#五质量控制流程)
6. [常见问题处理](#六常见问题处理)
7. [长序列管理](#七长序列管理)
8. [输出与验收](#八输出与验收)

---

## 一、逐帧修复概述

### 1.1 逐帧修复的适用场景

| 场景 | 原因 | 修复策略 |
|------|------|---------|
| 复杂运动 | 自动跟踪失效 | 手动逐帧调整 |
| 遮挡频繁 | 物体频繁被遮挡 | 遮挡帧单独处理 |
| 背景变化大 | 背景纹理变化剧烈 | 每帧重新采样 |
| 高精度要求 | 4K/8K 修复 | 逐帧精细处理 |
| 短序列 | 序列太短不值得自动化 | 直接逐帧修复 |

### 1.2 逐帧修复的优势与劣势

**优势**：
- 精度最高，可控性最强
- 适用于任何复杂场景
- 可以处理自动化无法解决的情况

**劣势**：
- 耗时长，效率低
- 容易产生帧间不一致
- 对操作者技术要求高

### 1.3 工作流概览

```
分析序列 → 规划关键帧 → 设置检查点 → 逐帧修复 → 质量检查 → 微调修正
```

---

## 二、关键帧规划

### 2.1 关键帧密度策略

| 序列长度 | 关键帧间隔 | 关键帧数量 | 说明 |
|---------|-----------|-----------|------|
| 1-10帧 | 每帧 | 全部 | 全逐帧 |
| 10-50帧 | 每5帧 | 10个 | 密集关键帧 |
| 50-100帧 | 每10帧 | 10个 | 标准策略 |
| 100-500帧 | 每25帧 | 20个 | 稀疏关键帧 |
| 500+帧 | 每50帧 | 10+个 | 最少关键帧 |

### 2.2 关键帧选择原则

```python
# 关键帧选择策略
keyframe_strategy = {
    "motion_change": "运动方向变化点",
    "occlusion_start": "遮挡开始帧",
    "occlusion_end": "遮挡结束帧",
    "background_change": "背景显著变化帧",
    "lighting_change": "光照变化帧",
    "regular_interval": "固定间隔关键帧",
}

# 示例：100帧序列的关键帧规划
keyframes = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
# 额外关键帧（运动变化点）
extra_keyframes = [15, 35, 65, 85]
all_keyframes = sorted(keyframes + extra_keyframes)
```

### 2.3 关键帧优先级

| 优先级 | 关键帧类型 | 说明 |
|--------|-----------|------|
| P0 | 遮挡开始/结束 | 必须手动处理 |
| P1 | 运动方向变化 | 影响跟踪准确性 |
| P2 | 背景变化 | 影响采样源 |
| P3 | 光照变化 | 影响色彩匹配 |
| P4 | 固定间隔 | 常规关键帧 |

---

## 三、检查点策略

### 3.1 检查点设置

```python
# 检查点配置
checkpoint_config = {
    "interval": 10,           # 每10帧一个检查点
    "preview_range": 5,       # 前后5帧预览
    "auto_save": true,        # 自动保存
    "quality_check": true,    # 质量检查
}

# 检查点列表
checkpoints = list(range(0, 101, 10))  # [0, 10, 20, ..., 100]
```

### 3.2 检查内容

| 检查项 | 检查方法 | 通过标准 |
|--------|---------|---------|
| 位置准确 | 对比前后帧 | 无明显跳跃 |
| 色彩匹配 | 与周围对比 | 色差 < 5% |
| 边缘自然 | 放大查看 | 无硬边 |
| 纹理一致 | 细节对比 | 纹理连续 |
| 无闪烁 | 播放预览 | 平滑过渡 |

### 3.3 检查点工作流

```python
def checkpoint_workflow(frame, paint_node):
    """检查点工作流"""
    print(f"[CHECKPOINT] Frame {frame}")

    # 1. 播放预览前后5帧
    preview_range = range(frame - 5, frame + 6)

    # 2. 检查修复质量
    checks = {
        "position": check_position(paint_node, frame),
        "color": check_color(paint_node, frame),
        "edge": check_edge(paint_node, frame),
        "texture": check_texture(paint_node, frame),
        "flicker": check_flicker(paint_node, frame),
    }

    # 3. 记录问题
    issues = [k for k, v in checks.items() if not v]
    if issues:
        print(f"[ISSUE] Frame {frame}: {issues}")

    # 4. 自动保存
    if checkpoint_config["auto_save"]:
        save_progress(frame)

    return len(issues) == 0
```

---

## 四、效率优化技巧

### 4.1 快捷键配置

| 操作 | 快捷键 | 说明 |
|------|--------|------|
| 下一帧 | → / . | 前进一帧 |
| 上一帧 | ← / , | 后退一帧 |
| 下一个关键帧 | Shift + → | 跳到下一个关键帧 |
| 上一个关键帧 | Shift + ← | 跳到上一个关键帧 |
| 笔刷大小 | [ / ] | 减小/增大笔刷 |
| 撤销 | Ctrl + Z | 撤销上一步 |
| 重做 | Ctrl + Y | 重做 |

### 4.2 批量操作

```python
# 批量应用相同修复
def batch_apply_fix(paint_node, frames, params):
    """在多帧应用相同修复参数"""
    for frame in frames:
        for param, value in params.items():
            paint_node.property(param).setValue(value, frame)
        print(f"[BATCH] Applied to frame {frame}")

# 示例：在关键帧之间批量应用
batch_frames = [5, 15, 25, 35, 45]
batch_params = {
    "brush.size": 20.0,
    "brush.hardness": 0.5,
    "brush.flow": 0.8,
    "mode": "clone",
}
batch_apply_fix(paint, batch_frames, batch_params)
```

### 4.3 复制笔触到相邻帧

```python
# 复制当前帧笔触到相邻帧
def copy_stroke_to_frame(paint_node, source_frame, target_frames):
    """复制笔触到目标帧"""
    # 获取源帧的所有属性
    properties = ["brush.size", "brush.hardness", "brush.flow",
                  "brush.opacity", "sampleOffset", "strokePosition"]

    for prop in properties:
        value = paint_node.property(prop).getValue(source_frame)
        for target in target_frames:
            paint_node.property(prop).setValue(value, target)

    print(f"[COPY] Frame {source_frame} -> {target_frames}")
```

### 4.4 预计算与缓存

```python
# 预计算跟踪数据
def precompute_tracking(tracker_node, frame_range):
    """预计算所有帧的跟踪数据"""
    tracking_data = {}
    for frame in frame_range:
        tracking_data[frame] = {
            "position": tracker_node.property("position").getValue(frame),
            "transform": tracker_node.property("transform").getValue(frame),
        }
    return tracking_data

# 缓存修复结果
def cache_repair_result(frame, result_data):
    """缓存修复结果用于回溯"""
    import json
    cache_path = f"D:/cache/frame_{frame:04d}.json"
    with open(cache_path, "w") as f:
        json.dump(result_data, f)
```

---

## 五、质量控制流程

### 5.1 三级质量检查

```
一级检查（自检）→ 二级检查（抽查）→ 三级检查（全片）
```

### 5.2 一级检查：自检

```python
def self_check(frame_range):
    """操作者自检"""
    results = []
    for frame in frame_range:
        # 检查项目
        checks = {
            "frame": frame,
            "visual_ok": visual_inspection(frame),
            "color_ok": color_check(frame),
            "edge_ok": edge_check(frame),
            "temporal_ok": temporal_check(frame),
        }
        results.append(checks)
    return results
```

### 5.3 二级检查：抽查

| 抽查点 | 检查内容 | 抽查比例 |
|--------|---------|---------|
| 关键帧 | 完整检查 | 100% |
| 检查点 | 主要项目 | 50% |
| 普通帧 | 快速浏览 | 10% |

### 5.4 三级检查：全片

```python
def full_sequence_check(frame_range):
    """全片播放检查"""
    issues = []

    # 1. 正常速度播放
    for frame in frame_range:
        if not quick_check(frame):
            issues.append({"frame": frame, "type": "quick"})

    # 2. 慢速播放（0.5x）
    for frame in frame_range:
        if not slow_check(frame):
            issues.append({"frame": frame, "type": "slow"})

    # 3. 逐帧播放
    for frame in frame_range:
        if not frame_check(frame):
            issues.append({"frame": frame, "type": "frame"})

    return issues
```

---

## 六、常见问题处理

### 6.1 帧间闪烁

**原因**：
- 笔刷参数帧间不一致
- 采样源位置跳变
- 色彩匹配不稳定

**解决方案**：
```python
# 启用时间平滑
paint.property("temporalSmooth").setValue(true, 0)
paint.property("temporalRange").setValue(3, 0)

# 使用插值模式
paint.property("propagation").setValue("interpolate", 0)
```

### 6.2 位置跳变

**原因**：
- 跟踪数据丢失
- 手动调整误差

**解决方案**：
```python
# 检查并修正位置跳变
def fix_position_jumps(paint_node, frame_range, threshold=5.0):
    """修正位置跳变"""
    prev_pos = None
    for frame in frame_range:
        pos = paint_node.property("strokePosition").getValue(frame)
        if prev_pos is not None:
            distance = ((pos[0] - prev_pos[0])**2 + (pos[1] - prev_pos[1])**2)**0.5
            if distance > threshold:
                # 插值修正
                interp_pos = [(prev_pos[0] + pos[0])/2, (prev_pos[1] + pos[1])/2]
                paint_node.property("strokePosition").setValue(interp_pos, frame)
                print(f"[FIX] Frame {frame}: position interpolated")
        prev_pos = pos
```

### 6.3 色彩不匹配

**原因**：
- 光照变化
- 采样源不准确

**解决方案**：
```python
# 启用色彩匹配
paint.property("colorMatch").setValue(true, 0)
paint.property("colorRange").setValue(0.2, 0)

# 或使用 Repair 模式
paint.property("mode").setValue("repair", 0)
```

---

## 七、长序列管理

### 7.1 分段处理策略

```python
# 长序列分段处理
def segment_long_sequence(total_frames, segment_size=50):
    """将长序列分段"""
    segments = []
    for start in range(0, total_frames, segment_size):
        end = min(start + segment_size - 1, total_frames)
        segments.append({"start": start, "end": end})
    return segments

# 示例：500帧序列分为10段
segments = segment_long_sequence(500, 50)
# [{"start": 0, "end": 49}, {"start": 50, "end": 99}, ...]
```

### 7.2 进度管理

```python
# 进度追踪
class ProgressTracker:
    def __init__(self, total_frames):
        self.total = total_frames
        self.completed = 0
        self.issues = []

    def update(self, frame, status, issue=None):
        if status == "completed":
            self.completed += 1
        elif status == "issue" and issue:
            self.issues.append({"frame": frame, "issue": issue})

    def get_progress(self):
        return self.completed / self.total

    def get_report(self):
        return {
            "progress": f"{self.get_progress()*100:.1f}%",
            "completed": self.completed,
            "total": self.total,
            "issues": len(self.issues),
            "issue_frames": [i["frame"] for i in self.issues],
        }
```

### 7.3 版本管理

```python
# 版本控制
def save_version(frame, version_num):
    """保存版本快照"""
    version_path = f"D:/versions/v{version_num:03d}_frame{frame:04d}.exr"
    # 保存当前状态
    print(f"[VERSION] Saved: {version_path}")

def load_version(version_num):
    """加载历史版本"""
    version_path = f"D:/versions/v{version_num:03d}/"
    # 加载版本
    print(f"[VERSION] Loaded: {version_path}")
```

---

## 八、输出与验收

### 8.1 输出前检查清单

- [ ] 所有关键帧已修复
- [ ] 所有检查点通过
- [ ] 全片播放无闪烁
- [ ] 色彩一致性良好
- [ ] 边缘自然过渡
- [ ] 无残留瑕疵

### 8.2 输出配置

```python
# 高质量输出配置
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/final_repair.####.exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("compression").setValue("zip", 0)
out_node.property("depth").setValue("32f", 0)  # 32位浮点
out_node.property("channels").setValue("rgba", 0)
```

### 8.3 验收标准

| 维度 | 标准 | 检查方法 |
|------|------|---------|
| 完整性 | 所有帧已修复 | 帧计数对比 |
| 一致性 | 无闪烁 | 播放检查 |
| 自然度 | 无明显修复痕迹 | 视觉检查 |
| 色彩 | 色差 < 3% | 色彩分析 |
| 分辨率 | 满足项目要求 | 尺寸检查 |

### 8.4 交付文档

```python
# 生成交付文档
delivery_doc = {
    "project": "逐帧修复项目",
    "date": "2026-07-11",
    "operator": "Artist Name",
    "total_frames": 500,
    "keyframes": 25,
    "checkpoints": 50,
    "issues_fixed": 12,
    "quality_score": 95,
    "output": {
        "path": "D:/output/final_repair.####.exr",
        "format": "EXR",
        "depth": "32f",
        "resolution": [1920, 1080],
    },
    "notes": "所有关键帧和检查点已通过质量验证",
}
```

---

## 总结

逐帧修复是 Paint 修复中精度最高但效率最低的方式，关键要点：

1. **规划先行**: 合理规划关键帧和检查点
2. **效率优化**: 利用快捷键、批量操作、复制笔触提高效率
3. **质量控制**: 严格执行三级质量检查
4. **问题处理**: 及时发现并处理闪烁、跳变、色彩问题
5. **长序列管理**: 分段处理，做好进度和版本管理

通过系统化的工作流程和质量控制，可以在保证修复质量的同时提高工作效率，完成复杂的逐帧修复任务。

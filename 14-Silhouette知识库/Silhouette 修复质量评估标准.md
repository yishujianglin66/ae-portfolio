# Silhouette 修复质量评估标准

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: Paint 修复质量评估的完整标准体系，包括视觉评估、技术指标、自动化检测、验收流程等内容，确保修复结果达到专业级质量要求。

## 目录

1. [质量评估概述](#一质量评估概述)
2. [视觉评估标准](#二视觉评估标准)
3. [技术指标体系](#三技术指标体系)
4. [自动化检测工具](#四自动化检测工具)
5. [帧间一致性检查](#五帧间一致性检查)
6. [色彩与光影评估](#六色彩与光影评估)
7. [验收流程与标准](#七验收流程与标准)
8. [常见质量问题与改进](#八常见质量问题与改进)

---

## 一、质量评估概述

### 1.1 评估维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 视觉自然度 | 30% | 修复区域是否无明显痕迹 |
| 帧间一致性 | 25% | 多帧播放是否平滑无闪烁 |
| 色彩匹配 | 20% | 修复区域色彩是否与周围一致 |
| 边缘质量 | 15% | 边缘过渡是否自然 |
| 细节保留 | 10% | 原始细节是否得到保留 |

### 1.2 评估等级

| 等级 | 分数 | 说明 | 验收 |
|------|------|------|------|
| A | 90-100 | 优秀，无明显瑕疵 | 直接通过 |
| B | 80-89 | 良好，有微小瑕疵 | 通过，可优化 |
| C | 70-79 | 合格，有可见瑕疵 | 需修正后通过 |
| D | 60-69 | 不合格，有明显问题 | 必须修正 |
| F | <60 | 严重不合格 | 重新制作 |

### 1.3 评估流程

```
自检 → 互检 → 技术检测 → 客户验收
```

---

## 二、视觉评估标准

### 2.1 自然度评估

| 检查项 | 标准 | 检查方法 |
|--------|------|---------|
| 修复痕迹 | 无可见痕迹 | 100% 放大对比 |
| 纹理连续 | 纹理自然延续 | 200% 放大检查 |
| 细节合理 | 细节符合场景 | 视觉观察 |
| 整体协调 | 与周围协调 | 全画面浏览 |

### 2.2 边缘质量评估

```python
# 边缘质量检查清单
edge_checks = {
    "hard_edge": "检查是否有硬边",
    "blur_transition": "检查模糊过渡是否自然",
    "color_bleed": "检查是否有色彩溢出",
    "aliasing": "检查是否有锯齿",
    "feather": "检查羽化是否合适",
}

def evaluate_edge_quality(frame):
    """评估边缘质量"""
    scores = {}
    for check, description in edge_checks.items():
        score = manual_check(frame, check)
        scores[check] = score
    return scores
```

### 2.3 视觉评估方法

| 方法 | 说明 | 适用场景 |
|------|------|---------|
| 全屏播放 | 正常速度播放 | 整体感受 |
| 慢速播放 | 0.25x 速度 | 细节观察 |
| 逐帧检查 | 逐帧对比 | 精确检查 |
| A/B 对比 | 原始 vs 修复 | 效果对比 |
| 差异图 | 显示差异 | 技术分析 |

---

## 三、技术指标体系

### 3.1 像素级指标

```python
# 像素级质量指标
class PixelMetrics:
    def __init__(self, original, repaired):
        self.original = original
        self.repaired = repaired

    def psnr(self):
        """峰值信噪比（仅适用于有参考的场景）"""
        # PSNR > 30dB 为良好
        pass

    def ssim(self):
        """结构相似性"""
        # SSIM > 0.9 为良好
        pass

    def color_difference(self):
        """色差（Delta E）"""
        # Delta E < 3 为不可察觉
        pass

    def edge_gradient(self):
        """边缘梯度一致性"""
        # 梯度差异 < 10% 为良好
        pass
```

### 3.2 序列级指标

| 指标 | 计算方法 | 标准 |
|------|---------|------|
| 帧间差异 | 相邻帧像素差异 | < 5% |
| 闪烁指数 | 亮度变化标准差 | < 0.05 |
| 运动一致性 | 运动向量偏差 | < 2像素 |
| 色彩稳定性 | 色彩波动范围 | Delta E < 2 |

### 3.3 技术指标标准

```python
# 技术指标标准
quality_standards = {
    "psnr": {"min": 30, "unit": "dB", "description": "峰值信噪比"},
    "ssim": {"min": 0.9, "unit": "", "description": "结构相似性"},
    "delta_e": {"max": 3.0, "unit": "", "description": "色差"},
    "flicker": {"max": 0.05, "unit": "", "description": "闪烁指数"},
    "temporal_diff": {"max": 0.05, "unit": "", "description": "帧间差异"},
}

def evaluate_technical(metrics):
    """评估技术指标"""
    results = {}
    for name, value in metrics.items():
        standard = quality_standards[name]
        if "min" in standard:
            passed = value >= standard["min"]
        else:
            passed = value <= standard["max"]
        results[name] = {
            "value": value,
            "standard": standard,
            "passed": passed,
        }
    return results
```

---

## 四、自动化检测工具

### 4.1 差异检测节点

```python
from fx import *

# 创建差异检测节点
diff = Node("DifferenceNode")
diff.label = "Quality_Check"
diff.property("mode").setValue("absolute", 0)
diff.property("threshold").setValue(0.05, 0)  # 差异阈值
diff.property("showDifference").setValue(true, 0)
diff.property("highlightRange").setValue([0.02, 0.1], 0)
session.addNode(diff)
```

### 4.2 闪烁检测

```python
# 闪烁检测
flicker_check = Node("FlickerNode")
flicker_check.label = "Flicker_Detect"
flicker_check.property("windowSize").setValue(5, 0)  # 检测窗口
flicker_check.property("threshold").setValue(0.05, 0)
flicker_check.property("showChart").setValue(true, 0)
session.addNode(flicker_check)
```

### 4.3 自动化检测脚本

```python
def automated_quality_check(frame_range, paint_node):
    """自动化质量检测"""
    results = {
        "total_frames": len(frame_range),
        "issues": [],
        "scores": {},
    }

    for frame in frame_range:
        # 1. 检测修复区域
        repair_region = detect_repair_region(paint_node, frame)

        # 2. 检查色彩匹配
        color_score = check_color_match(repair_region, frame)

        # 3. 检查边缘质量
        edge_score = check_edge_quality(repair_region, frame)

        # 4. 检查纹理一致性
        texture_score = check_texture_consistency(repair_region, frame)

        # 5. 综合评分
        total_score = (color_score + edge_score + texture_score) / 3
        results["scores"][frame] = total_score

        if total_score < 0.8:
            results["issues"].append({
                "frame": frame,
                "score": total_score,
                "color": color_score,
                "edge": edge_score,
                "texture": texture_score,
            })

    return results
```

---

## 五、帧间一致性检查

### 5.1 闪烁检测方法

```python
def detect_flicker(frame_range, threshold=0.05):
    """检测帧间闪烁"""
    flicker_frames = []
    prev_brightness = None

    for frame in frame_range:
        # 计算修复区域平均亮度
        brightness = calculate_repair_brightness(frame)

        if prev_brightness is not None:
            diff = abs(brightness - prev_brightness)
            if diff > threshold:
                flicker_frames.append({
                    "frame": frame,
                    "difference": diff,
                    "brightness": brightness,
                })

        prev_brightness = brightness

    return flicker_frames
```

### 5.2 运动一致性检查

```python
def check_motion_consistency(frame_range, paint_node):
    """检查运动一致性"""
    motion_issues = []

    for i in range(1, len(frame_range)):
        prev_frame = frame_range[i - 1]
        curr_frame = frame_range[i]

        # 获取笔触位置
        prev_pos = paint_node.property("strokePosition").getValue(prev_frame)
        curr_pos = paint_node.property("strokePosition").getValue(curr_frame)

        # 计算运动距离
        distance = ((curr_pos[0] - prev_pos[0])**2 +
                    (curr_pos[1] - prev_pos[1])**2)**0.5

        # 检查是否异常跳跃
        if distance > 20:  # 超过20像素视为异常
            motion_issues.append({
                "frame": curr_frame,
                "distance": distance,
                "issue": "abnormal_jump",
            })

    return motion_issues
```

### 5.3 一致性评分

| 一致性维度 | 评分标准 | 权重 |
|-----------|---------|------|
| 亮度一致性 | 波动 < 5% | 30% |
| 色彩一致性 | Delta E < 2 | 30% |
| 位置一致性 | 跳跃 < 2px | 20% |
| 大小一致性 | 变化 < 10% | 20% |

---

## 六、色彩与光影评估

### 6.1 色彩匹配评估

```python
def evaluate_color_match(repair_region, surrounding_region):
    """评估色彩匹配度"""
    # 计算色彩统计
    repair_stats = {
        "mean_rgb": calculate_mean_rgb(repair_region),
        "std_rgb": calculate_std_rgb(repair_region),
        "histogram": calculate_histogram(repair_region),
    }

    surrounding_stats = {
        "mean_rgb": calculate_mean_rgb(surrounding_region),
        "std_rgb": calculate_std_rgb(surrounding_region),
        "histogram": calculate_histogram(surrounding_region),
    }

    # 计算 Delta E
    delta_e = calculate_delta_e(
        repair_stats["mean_rgb"],
        surrounding_stats["mean_rgb"]
    )

    # 计算直方图相似度
    hist_similarity = calculate_histogram_similarity(
        repair_stats["histogram"],
        surrounding_stats["histogram"]
    )

    return {
        "delta_e": delta_e,
        "histogram_similarity": hist_similarity,
        "passed": delta_e < 3.0 and hist_similarity > 0.9,
    }
```

### 6.2 光影一致性

| 检查项 | 标准 | 检查方法 |
|--------|------|---------|
| 亮度匹配 | 差异 < 5% | 直方图对比 |
| 对比度匹配 | 差异 < 10% | 标准差对比 |
| 高光保留 | 高光区域完整 | 视觉检查 |
| 阴影重建 | 阴影方向正确 | 视觉检查 |
| 反射处理 | 反射清除完整 | 视觉检查 |

### 6.3 色彩评估标准

```python
# 色彩评估标准
color_standards = {
    "delta_e": {
        "excellent": 1.0,  # 不可察觉
        "good": 3.0,       # 轻微察觉
        "acceptable": 5.0, # 可接受
        "poor": 10.0,      # 明显差异
    },
    "histogram_similarity": {
        "excellent": 0.95,
        "good": 0.90,
        "acceptable": 0.85,
        "poor": 0.80,
    },
}
```

---

## 七、验收流程与标准

### 7.1 验收流程

```
1. 自检（操作者）→ 提交验收
2. 互检（同事）→ 反馈意见
3. 技术检测（工具）→ 生成报告
4. 主管审核 → 决定通过/修正
5. 客户验收 → 最终确认
```

### 7.2 验收检查清单

```python
# 验收检查清单
acceptance_checklist = {
    "visual": {
        "no_repair_traces": "无可见修复痕迹",
        "natural_texture": "纹理自然",
        "smooth_edges": "边缘平滑",
        "color_matched": "色彩匹配",
    },
    "technical": {
        "no_flicker": "无闪烁",
        "no_jump": "无位置跳变",
        "temporal_stable": "时间稳定",
        "resolution_correct": "分辨率正确",
    },
    "delivery": {
        "all_frames_done": "所有帧已完成",
        "output_format_correct": "输出格式正确",
        "naming_convention": "命名规范",
        "documentation_complete": "文档完整",
    },
}

def run_acceptance_check(checklist):
    """执行验收检查"""
    results = {}
    for category, items in checklist.items():
        results[category] = {}
        for item, description in items.items():
            passed = manual_check(item)
            results[category][item] = {
                "description": description,
                "passed": passed,
            }
    return results
```

### 7.3 验收标准

| 等级 | 视觉评分 | 技术评分 | 处理方式 |
|------|---------|---------|---------|
| A级 | ≥95 | ≥95 | 直接通过 |
| B级 | 85-94 | 85-94 | 通过，建议优化 |
| C级 | 75-84 | 75-84 | 需修正后提交 |
| D级 | <75 | <75 | 必须重新制作 |

---

## 八、常见质量问题与改进

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 闪烁 | 帧间参数不一致 | 启用时间平滑 |
| 硬边 | 硬度过高 | 降低硬度，增加羽化 |
| 色差 | 色彩匹配不准 | 启用 colorMatch |
| 纹理丢失 | 过度平滑 | 启用 texturePreserve |
| 位置跳变 | 跟踪丢失 | 手动修正关键帧 |

### 8.2 改进策略

```python
# 质量改进策略
def improve_quality(issue_type, paint_node):
    """根据问题类型改进质量"""
    improvements = {
        "flicker": [
            ("temporalSmooth", True),
            ("temporalRange", 3),
            ("interpolation", "motion"),
        ],
        "hard_edge": [
            ("brush.hardness", 0.3),
            ("alpha.blur", 2.0),
        ],
        "color_mismatch": [
            ("colorMatch", True),
            ("colorRange", 0.2),
            ("mode", "repair"),
        ],
        "texture_loss": [
            ("texturePreserve", True),
            ("textureAmount", 0.5),
        ],
    }

    improvements_list = improvements.get(issue_type, [])
    for param, value in improvements_list:
        paint_node.property(param).setValue(value, 0)
        print(f"[IMPROVE] {param} = {value}")
```

### 8.3 持续改进

1. **记录问题**: 建立问题数据库
2. **分析原因**: 统计常见问题
3. **优化流程**: 根据问题调整工作流
4. **培训提升**: 针对性技能培训
5. **工具优化**: 改进检测工具

---

## 总结

质量评估是 Paint 修复工作流的重要组成部分，关键要点：

1. **多维度评估**: 视觉、技术、一致性多维度评估
2. **量化指标**: 使用 PSNR、SSIM、Delta E 等量化指标
3. **自动化检测**: 利用工具自动检测常见问题
4. **帧间一致**: 重点检查闪烁、跳变等帧间问题
5. **持续改进**: 建立问题数据库，持续优化流程

通过系统化的质量评估体系和标准化的验收流程，可以确保 Paint 修复结果达到专业级质量要求，满足影视后期制作的高标准需求。

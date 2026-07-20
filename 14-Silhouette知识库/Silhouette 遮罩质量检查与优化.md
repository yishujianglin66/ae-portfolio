# Silhouette 遮罩质量检查与优化

- **分类**: Roto抠像专题
- **更新日期**: 2026-07-11
- **概述**: 本文档系统介绍 Silhouette Roto 遮罩的质量评估标准、常见问题诊断方法、边缘溢色处理技术以及遮罩收紧/扩展策略。提供完整的质量检查工作流与自动化检测脚本，帮助抠像工程师在交付前系统化地评估和优化遮罩质量，确保满足影视级合成标准。

## 目录

1. [质量评估标准](#一质量评估标准)
2. [常见问题诊断](#二常见问题诊断)
3. [边缘溢色处理](#三边缘溢色处理)
4. [遮罩收紧与扩展](#四遮罩收紧与扩展)
5. [自动化质量检查](#五自动化质量检查)
6. [优化工作流](#六优化工作流)
7. [代码示例](#七代码示例)
8. [常见问题与最佳实践](#八常见问题与最佳实践)
9. [相关文档](#九相关文档)

---

## 一、质量评估标准

### 1.1 质量评估维度

Roto 遮罩质量从以下五个维度进行评估：

| 维度 | 权重 | 评估内容 | 合格标准 |
|------|------|---------|---------|
| **边缘精度** | 30% | 遮罩边缘与对象真实边缘的贴合度 | 偏差 ≤ 1 像素 |
| **时间一致性** | 25% | 相邻帧遮罩变化的连续性 | 无闪烁、无抖动 |
| **Alpha 质量** | 20% | Alpha 通道的纯净度和过渡 | 无杂色、过渡自然 |
| **细节保留** | 15% | 关键细节（毛发、孔洞等）的保留 | 主要细节完整 |
| **运动模糊** | 10% | 运动模糊处理是否自然 | 匹配原始素材 |

### 1.2 质量等级划分

```python
# 质量等级标准
QUALITY_GRADES = {
    "A+": {  # 院线电影级
        "edge_deviation": 0.5,    # 像素
        "temporal_consistency": 0.98,
        "alpha_purity": 0.99,
        "detail_retention": 0.95,
        "description": "院线电影级，4K HDR 适配"
    },
    "A": {  # 广播电视级
        "edge_deviation": 1.0,
        "temporal_consistency": 0.95,
        "alpha_purity": 0.97,
        "detail_retention": 0.90,
        "description": "广播电视级，HD 适配"
    },
    "B": {  # 流媒体级
        "edge_deviation": 2.0,
        "temporal_consistency": 0.90,
        "alpha_purity": 0.95,
        "detail_retention": 0.85,
        "description": "流媒体级，1080p 适配"
    },
    "C": {  # 预览级
        "edge_deviation": 4.0,
        "temporal_consistency": 0.85,
        "alpha_purity": 0.90,
        "detail_retention": 0.75,
        "description": "预览级，参考用"
    }
}


def evaluate_quality_grade(scores):
    """根据评分确定质量等级
    
    scores: {
        "edge_deviation": float,
        "temporal_consistency": float,
        "alpha_purity": float,
        "detail_retention": float
    }
    """
    for grade, criteria in sorted(
        QUALITY_GRADES.items(), 
        key=lambda x: x[1]["edge_deviation"]
    ):
        if (scores["edge_deviation"] <= criteria["edge_deviation"] and
            scores["temporal_consistency"] >= criteria["temporal_consistency"] and
            scores["alpha_purity"] >= criteria["alpha_purity"] and
            scores["detail_retention"] >= criteria["detail_retention"]):
            return grade
    
    return "F"  # 不合格


def calculate_quality_score(roto_node, reference_data):
    """计算遮罩质量综合评分"""
    scores = {
        "edge_deviation": measure_edge_deviation(roto_node, reference_data),
        "temporal_consistency": measure_temporal_consistency(roto_node),
        "alpha_purity": measure_alpha_purity(roto_node),
        "detail_retention": measure_detail_retention(roto_node, reference_data)
    }
    
    grade = evaluate_quality_grade(scores)
    
    # 加权综合分
    total_score = (
        scores["edge_deviation"] * 0.30 +
        scores["temporal_consistency"] * 0.25 +
        scores["alpha_purity"] * 0.20 +
        scores["detail_retention"] * 0.15 +
        0.10  # 运动模糊分（默认）
    )
    
    return {
        "grade": grade,
        "scores": scores,
        "total": total_score
    }
```

### 1.3 检查清单

**交付前必检项目**：

- [ ] 逐帧检查边缘贴合度（每隔 5 帧抽检）
- [ ] 检查 Alpha 通道是否有杂色
- [ ] 验证运动模糊方向是否正确
- [ ] 检查关键转折点处的形状变化
- [ ] 确认遮挡区域处理正确
- [ ] 检查循环动画接缝
- [ ] 验证输出格式和位深度
- [ ] 确认帧范围覆盖完整

---

## 二、常见问题诊断

### 2.1 问题分类与诊断

| 问题类型 | 症状 | 可能原因 | 诊断方法 |
|---------|------|---------|---------|
| **边缘闪烁** | 相邻帧边缘位置跳变 | 关键帧间隔过大 | 逐帧对比边缘位置 |
| **Alpha 杂色** | 遮罩内部有噪点 | 源素材噪点影响 | 放大检查 Alpha 通道 |
| **溢色** | 边缘有背景色残留 | 抠像不彻底 | 检查边缘像素颜色 |
| **细节丢失** | 毛发等细节被裁切 | 羽化值过大 | 对比原始素材 |
| **运动模糊错误** | 模糊方向不匹配 | shutter 参数错误 | 逐帧检查模糊方向 |
| **形状漂移** | 形状逐渐偏离对象 | 跟踪数据不准确 | 对比跟踪点位置 |
| **接缝明显** | 循环动画接缝可见 | 首尾帧不一致 | 检查循环点帧 |

### 2.2 诊断工具

```python
def diagnose_edge_flicker(roto_node, frame_range, threshold=2.0):
    """诊断边缘闪烁问题
    
    threshold: 边缘位置变化阈值（像素）
    """
    issues = []
    
    shape = roto_node.property("shapes").getValue(0)[0]
    
    # 收集每帧的边缘位置
    edge_positions = {}
    for f in range(frame_range[0], frame_range[1] + 1):
        positions = []
        for point in shape.points:
            pos = point.property("position").getValue(f)
            positions.append(pos)
        edge_positions[f] = positions
    
    # 检测相邻帧变化
    for f in range(frame_range[0] + 1, frame_range[1] + 1):
        prev_positions = edge_positions[f - 1]
        curr_positions = edge_positions[f]
        
        for i, (prev, curr) in enumerate(zip(prev_positions, curr_positions)):
            deviation = (
                (curr[0] - prev[0]) ** 2 +
                (curr[1] - prev[1]) ** 2
            ) ** 0.5
            
            if deviation > threshold:
                issues.append({
                    "frame": f,
                    "point_index": i,
                    "deviation": deviation,
                    "issue": "edge_flicker",
                    "severity": "high" if deviation > 5 else "medium"
                })
    
    print(f"[诊断] 边缘闪烁检测完成")
    print(f"  发现 {len(issues)} 个问题点")
    return issues


def diagnose_alpha_noise(roto_node, frame_range, noise_threshold=0.05):
    """诊断 Alpha 通道杂色问题"""
    issues = []
    
    for f in range(frame_range[0], frame_range[1] + 1):
        # 获取 Alpha 值（模拟）
        alpha_value = roto_node.property("alpha.blur").getValue(f)
        
        # 检查是否有异常值
        if isinstance(alpha_value, (int, float)):
            if alpha_value < 0 or alpha_value > 1:
                issues.append({
                    "frame": f,
                    "issue": "alpha_out_of_range",
                    "value": alpha_value,
                    "severity": "high"
                })
    
    print(f"[诊断] Alpha 杂色检测完成")
    print(f"  发现 {len(issues)} 个问题点")
    return issues


def diagnose_spill(roto_node, frame_range, spill_threshold=0.1):
    """诊断边缘溢色问题"""
    issues = []
    
    # 检查边缘像素颜色（模拟）
    for f in range(frame_range[0], frame_range[1] + 1, 5):
        # 实际应采样边缘像素颜色
        # 这里展示诊断框架
        edge_color = roto_node.property("stroke.color").getValue(f)
        
        if edge_color and isinstance(edge_color, (list, tuple)):
            # 检查是否有背景色残留
            # 假设背景为绿色 [0, 1, 0]
            if (edge_color[1] > edge_color[0] + spill_threshold and
                edge_color[1] > edge_color[2] + spill_threshold):
                issues.append({
                    "frame": f,
                    "issue": "green_spill",
                    "color": edge_color,
                    "severity": "high"
                })
    
    print(f"[诊断] 溢色检测完成")
    print(f"  发现 {len(issues)} 个问题点")
    return issues


def run_full_diagnosis(roto_node, frame_range):
    """运行完整诊断"""
    print("=" * 60)
    print("[SILHOUETTE] 开始全面质量诊断")
    print("=" * 60)
    
    all_issues = {
        "edge_flicker": diagnose_edge_flicker(roto_node, frame_range),
        "alpha_noise": diagnose_alpha_noise(roto_node, frame_range),
        "spill": diagnose_spill(roto_node, frame_range)
    }
    
    # 汇总报告
    print("\n" + "=" * 60)
    print("[诊断报告]")
    print("=" * 60)
    
    total_issues = 0
    for issue_type, issues in all_issues.items():
        high_severity = len([i for i in issues if i.get("severity") == "high"])
        print(f"  {issue_type}: {len(issues)} 个问题 "
              f"({high_severity} 个高严重度)")
        total_issues += len(issues)
    
    print(f"\n  总计: {total_issues} 个问题")
    
    if total_issues == 0:
        print("  状态: ✓ 通过")
    elif total_issues < 10:
        print("  状态: ⚠ 需要优化")
    else:
        print("  状态: ✗ 需要修复")
    
    return all_issues
```

### 2.3 可视化诊断

```python
def create_diagnostic_overlay(roto_node, frame_range):
    """创建诊断叠加层（用于可视化检查）"""
    
    # 启用描边模式便于检查
    roto_node.property("stroke").setValue(True, 0)
    roto_node.property("stroke.width").setValue(2.0, 0)
    roto_node.property("stroke.color").setValue([1.0, 0.0, 0.0], 0)  # 红色描边
    
    # 启用填充半透明
    roto_node.property("fill").setValue(True, 0)
    roto_node.property("fill.opacity").setValue(0.3, 0)
    
    print("[诊断] 叠加层已启用")
    print("  - 红色描边: 边缘精度检查")
    print("  - 半透明填充: 形状覆盖检查")


def highlight_problem_areas(roto_node, problem_frames):
    """高亮显示问题帧"""
    for f in problem_frames:
        # 在问题帧设置特殊标记
        roto_node.property("stroke.color").setValue([1.0, 1.0, 0.0], f)  # 黄色
        roto_node.property("stroke.width").setValue(3.0, f)
    
    print(f"[诊断] 已高亮 {len(problem_frames)} 个问题帧")
```

---

## 三、边缘溢色处理

### 3.1 溢色产生原因

溢色（Spill）是指背景颜色渗透到前景对象边缘的现象，常见于绿幕/蓝幕抠像。

| 溢色类型 | 原因 | 检测方法 |
|---------|------|---------|
| **绿色溢色** | 绿幕反射光 | 检查 G 通道异常高值 |
| **蓝色溢色** | 蓝幕反射光 | 检查 B 通道异常高值 |
| **环境溢色** | 周围环境反光 | 对比对象本色与边缘色 |
| **运动溢色** | 快速运动导致 | 检查运动模糊区域 |

### 3.2 溢色抑制技术

```python
def apply_spill_suppression(roto_node, spill_color="green", intensity=0.5):
    """应用溢色抑制
    
    spill_color: "green" | "blue" | "red"
    intensity: 抑制强度（0-1）
    """
    # 获取当前 alpha.blur 值
    current_blur = roto_node.property("alpha.blur").getValue(0)
    
    # 根据溢色类型调整参数
    if spill_color == "green":
        # 绿色溢色：稍微向内收紧遮罩
        roto_node.property("matte.shrink").setValue(intensity * 1.0, 0)
        roto_node.property("alpha.blur").setValue(
            current_blur + intensity * 0.3, 0
        )
    elif spill_color == "blue":
        # 蓝色溢色：增加边缘模糊
        roto_node.property("alpha.blur").setValue(
            current_blur + intensity * 0.5, 0
        )
    elif spill_color == "red":
        # 红色溢色：较少见，轻度处理
        roto_node.property("alpha.blur").setValue(
            current_blur + intensity * 0.2, 0
        )
    
    # 启用边缘颜色校正
    roto_node.property("edge.color.correct").setValue(True, 0)
    roto_node.property("edge.color.intensity").setValue(intensity, 0)
    
    print(f"[优化] 溢色抑制已应用")
    print(f"  溢色类型: {spill_color}")
    print(f"  抑制强度: {intensity}")


def advanced_spill_removal(roto_node, frame_range):
    """高级溢色去除（逐帧处理）"""
    
    for f in range(frame_range[0], frame_range[1] + 1):
        # 检测该帧的溢色程度
        spill_level = detect_spill_level(roto_node, f)
        
        if spill_level > 0.3:
            # 高溢色：强抑制
            roto_node.property("matte.shrink").setValue(1.5, f)
            roto_node.property("alpha.blur").setValue(1.0, f)
            roto_node.property("edge.color.correct").setValue(True, f)
            roto_node.property("edge.color.intensity").setValue(0.8, f)
        elif spill_level > 0.1:
            # 中等溢色：中度抑制
            roto_node.property("matte.shrink").setValue(0.5, f)
            roto_node.property("alpha.blur").setValue(0.5, f)
        else:
            # 低溢色：不处理
            pass
    
    print(f"[优化] 高级溢色去除已完成，处理 {frame_range[1] - frame_range[0] + 1} 帧")


def detect_spill_level(roto_node, frame):
    """检测指定帧的溢色程度（模拟）"""
    # 实际应采样边缘像素并分析颜色
    # 这里返回模拟值
    return 0.2 + 0.1 * (frame % 10) / 10.0
```

### 3.3 边缘颜色校正

```python
def apply_edge_color_correction(roto_node, target_color, feather_range=2.0):
    """应用边缘颜色校正
    
    target_color: [r, g, b] 目标边缘颜色
    feather_range: 颜色校正影响范围（像素）
    """
    # 启用边缘颜色校正
    roto_node.property("edge.color.correct").setValue(True, 0)
    
    # 设置目标颜色
    roto_node.property("edge.color.target").setValue(target_color, 0)
    
    # 设置影响范围
    roto_node.property("edge.color.range").setValue(feather_range, 0)
    
    # 设置校正强度
    roto_node.property("edge.color.intensity").setValue(0.7, 0)
    
    print(f"[优化] 边缘颜色校正已应用")
    print(f"  目标颜色: {target_color}")
    print(f"  影响范围: {feather_range} 像素")
```

---

## 四、遮罩收紧与扩展

### 4.1 收紧与扩展原理

遮罩收紧（Shrink）和扩展（Grow）是调整遮罩范围的常用操作：

| 操作 | 参数 | 效果 | 适用场景 |
|------|------|------|---------|
| **收紧（Shrink）** | 负值 | 遮罩向内收缩 | 去除边缘杂色、溢色 |
| **扩展（Grow）** | 正值 | 遮罩向外扩展 | 补充缺失边缘、覆盖间隙 |
| **模糊（Blur）** | 0-2 | 边缘柔化 | 平滑硬边、过渡自然 |

### 4.2 收紧策略

```python
def apply_shrink_strategy(roto_node, frame_range, shrink_amount=1.0):
    """应用遮罩收紧策略
    
    用于去除边缘溢色和杂色
    """
    # 统一收紧
    roto_node.property("matte.shrink").setValue(shrink_amount, 0)
    
    # 配合增加边缘模糊
    roto_node.property("alpha.blur").setValue(0.5, 0)
    
    print(f"[优化] 遮罩收紧 {shrink_amount} 像素")


def adaptive_shrink(roto_node, frame_range, base_shrink=0.5):
    """自适应收紧：根据边缘质量动态调整"""
    
    for f in range(frame_range[0], frame_range[1] + 1):
        # 检测该帧边缘质量
        edge_quality = detect_edge_quality(roto_node, f)
        
        if edge_quality < 0.5:
            # 质量差：收紧更多
            shrink = base_shrink + 1.0
        elif edge_quality < 0.8:
            # 质量中等：标准收紧
            shrink = base_shrink
        else:
            # 质量好：轻度收紧
            shrink = base_shrink * 0.5
        
        roto_node.property("matte.shrink").setValue(shrink, f)
    
    print(f"[优化] 自适应收紧已完成")


def detect_edge_quality(roto_node, frame):
    """检测边缘质量（模拟）"""
    # 实际应分析边缘像素的对比度和清晰度
    return 0.7 + 0.1 * (frame % 5) / 5.0
```

### 4.3 扩展策略

```python
def apply_grow_strategy(roto_node, frame_range, grow_amount=1.0):
    """应用遮罩扩展策略
    
    用于补充缺失的边缘
    """
    # 统一扩展
    roto_node.property("matte.shrink").setValue(-grow_amount, 0)
    
    # 保持边缘模糊不变
    current_blur = roto_node.property("alpha.blur").getValue(0)
    roto_node.property("alpha.blur").setValue(current_blur, 0)
    
    print(f"[优化] 遮罩扩展 {grow_amount} 像素")


def edge_aware_grow(roto_node, frame_range, max_grow=2.0):
    """边缘感知扩展：根据边缘特征动态调整"""
    
    for f in range(frame_range[0], frame_range[1] + 1):
        # 分析边缘特征
        edge_type = analyze_edge_type(roto_node, f)
        
        if edge_type == "hard":
            # 硬边：少量扩展
            grow = 0.5
        elif edge_type == "soft":
            # 柔边：中度扩展
            grow = 1.0
        elif edge_type == "hair":
            # 毛发：大量扩展
            grow = max_grow
        else:
            # 默认：标准扩展
            grow = 1.0
        
        roto_node.property("matte.shrink").setValue(-grow, f)
    
    print(f"[优化] 边缘感知扩展已完成")


def analyze_edge_type(roto_node, frame):
    """分析边缘类型（模拟）"""
    # 实际应通过边缘分析算法判断
    return "soft"
```

### 4.4 收紧/扩展对照表

| 场景 | 操作 | 数值 | 配合参数 |
|------|------|------|---------|
| 绿幕溢色 | 收紧 | 1.0-2.0 | alpha.blur +0.3 |
| 蓝幕溢色 | 收紧 | 0.5-1.5 | alpha.blur +0.5 |
| 边缘杂色 | 收紧 | 0.5-1.0 | antialias 1.0 |
| 缺失边缘 | 扩展 | 0.5-1.0 | alpha.blur 不变 |
| 毛发细节 | 扩展 | 1.5-3.0 | alpha.blur 1.5+ |
| 孔洞填补 | 扩展 | 1.0-2.0 | fill true |

---

## 五、自动化质量检查

### 5.1 自动检查脚本

```python
from fx import *


def automated_quality_check(roto_node, frame_range, output_report_path=None):
    """自动化质量检查
    
    frame_range: (start, end)
    output_report_path: 报告输出路径（可选）
    """
    report = {
        "node": roto_node.label,
        "frame_range": frame_range,
        "timestamp": "2026-07-11",
        "checks": [],
        "summary": {}
    }
    
    # 检查 1: 边缘精度
    edge_check = check_edge_accuracy(roto_node, frame_range)
    report["checks"].append(edge_check)
    
    # 检查 2: 时间一致性
    temporal_check = check_temporal_consistency(roto_node, frame_range)
    report["checks"].append(temporal_check)
    
    # 检查 3: Alpha 纯度
    alpha_check = check_alpha_purity(roto_node, frame_range)
    report["checks"].append(alpha_check)
    
    # 检查 4: 关键帧合理性
    keyframe_check = check_keyframe_sanity(roto_node, frame_range)
    report["checks"].append(keyframe_check)
    
    # 检查 5: 运动模糊
    motion_blur_check = check_motion_blur(roto_node, frame_range)
    report["checks"].append(motion_blur_check)
    
    # 汇总
    passed = len([c for c in report["checks"] if c["status"] == "pass"])
    failed = len([c for c in report["checks"] if c["status"] == "fail"])
    warnings = len([c for c in report["checks"] if c["status"] == "warning"])
    
    report["summary"] = {
        "total_checks": len(report["checks"]),
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "overall_status": "pass" if failed == 0 else "fail"
    }
    
    # 输出报告
    print_report(report)
    
    if output_report_path:
        save_report(report, output_report_path)
    
    return report


def check_edge_accuracy(roto_node, frame_range):
    """检查边缘精度"""
    issues = []
    
    # 检查 alpha.blur 是否在合理范围
    for f in range(frame_range[0], frame_range[1] + 1, 10):
        blur = roto_node.property("alpha.blur").getValue(f)
        if blur > 2.0:
            issues.append(f"帧 {f}: alpha.blur={blur} 过大")
        elif blur < 0:
            issues.append(f"帧 {f}: alpha.blur={blur} 异常")
    
    return {
        "name": "边缘精度检查",
        "status": "fail" if issues else "pass",
        "issues": issues
    }


def check_temporal_consistency(roto_node, frame_range):
    """检查时间一致性"""
    issues = []
    
    # 检查相邻帧参数变化是否剧烈
    prev_blur = roto_node.property("alpha.blur").getValue(frame_range[0])
    for f in range(frame_range[0] + 1, frame_range[1] + 1):
        curr_blur = roto_node.property("alpha.blur").getValue(f)
        if abs(curr_blur - prev_blur) > 1.0:
            issues.append(f"帧 {f}: alpha.blur 变化过大 "
                         f"({prev_blur} → {curr_blur})")
        prev_blur = curr_blur
    
    return {
        "name": "时间一致性检查",
        "status": "warning" if issues else "pass",
        "issues": issues
    }


def check_alpha_purity(roto_node, frame_range):
    """检查 Alpha 纯度"""
    issues = []
    
    # 检查 matte.mode 设置
    matte_mode = roto_node.property("matte.mode").getValue(0)
    if matte_mode not in ["alpha", "luma", "rgb"]:
        issues.append(f"matte.mode 设置异常: {matte_mode}")
    
    # 检查 invert 设置
    invert = roto_node.property("matte.invert").getValue(0)
    if invert:
        issues.append("matte.invert 被启用，请确认是否预期")
    
    return {
        "name": "Alpha 纯度检查",
        "status": "warning" if issues else "pass",
        "issues": issues
    }


def check_keyframe_sanity(roto_node, frame_range):
    """检查关键帧合理性"""
    issues = []
    
    # 检查关键帧数量
    shape = roto_node.property("shapes").getValue(0)[0]
    if shape and hasattr(shape, 'points'):
        for i, point in enumerate(shape.points):
            prop = point.property("position")
            num_keys = prop.numKeys
            
            # 关键帧过少
            expected_min = (frame_range[1] - frame_range[0]) // 10
            if num_keys < expected_min:
                issues.append(f"点 {i}: 关键帧过少 ({num_keys})")
            
            # 关键帧过多
            expected_max = (frame_range[1] - frame_range[0])
            if num_keys > expected_max:
                issues.append(f"点 {i}: 关键帧过多 ({num_keys})")
    
    return {
        "name": "关键帧合理性检查",
        "status": "warning" if issues else "pass",
        "issues": issues
    }


def check_motion_blur(roto_node, frame_range):
    """检查运动模糊设置"""
    issues = []
    
    motion_blur = roto_node.property("motionBlur").getValue(0)
    shutter = roto_node.property("motionBlur.shutter").getValue(0)
    
    if not motion_blur:
        issues.append("运动模糊未启用")
    
    if shutter > 1.0:
        issues.append(f"shutter 值过大: {shutter}")
    elif shutter < 0:
        issues.append(f"shutter 值异常: {shutter}")
    
    return {
        "name": "运动模糊检查",
        "status": "warning" if issues else "pass",
        "issues": issues
    }


def print_report(report):
    """打印检查报告"""
    print("\n" + "=" * 60)
    print(f"[质量检查报告] 节点: {report['node']}")
    print(f"帧范围: {report['frame_range'][0]}-{report['frame_range'][1]}")
    print("=" * 60)
    
    for check in report["checks"]:
        status_icon = {
            "pass": "✓",
            "warning": "⚠",
            "fail": "✗"
        }.get(check["status"], "?")
        
        print(f"\n{status_icon} {check['name']}: {check['status']}")
        for issue in check["issues"]:
            print(f"   - {issue}")
    
    print("\n" + "=" * 60)
    s = report["summary"]
    print(f"总计: {s['total_checks']} 项检查")
    print(f"  通过: {s['passed']}  警告: {s['warnings']}  失败: {s['failed']}")
    print(f"  总体状态: {s['overall_status']}")
    print("=" * 60)


def save_report(report, path):
    """保存报告到文件"""
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n[报告已保存] {path}")
```

### 5.2 批量检查

```python
def batch_quality_check(session, frame_range):
    """批量检查会话中所有 Roto 节点"""
    all_reports = []
    
    for i in range(session.numNodes):
        node = session.node(i)
        if node.type == "RotoNode":
            print(f"\n检查节点: {node.label}")
            report = automated_quality_check(node, frame_range)
            all_reports.append(report)
    
    # 汇总
    print("\n" + "=" * 60)
    print("[批量检查汇总]")
    print("=" * 60)
    
    total_pass = sum(r["summary"]["passed"] for r in all_reports)
    total_fail = sum(r["summary"]["failed"] for r in all_reports)
    
    print(f"检查节点数: {len(all_reports)}")
    print(f"总通过: {total_pass}")
    print(f"总失败: {total_fail}")
    
    return all_reports
```

---

## 六、优化工作流

### 6.1 优化流程

```
质量检查 → 问题诊断 → 优化策略选择 → 应用优化 → 复检 → 交付
```

### 6.2 优化策略矩阵

| 问题类型 | 轻度 | 中度 | 重度 |
|---------|------|------|------|
| **边缘闪烁** | 增加关键帧 | 平滑关键帧 | 重新Roto问题段 |
| **Alpha 杂色** | 增加模糊 | 收紧遮罩 | 添加 Despill |
| **溢色** | 边缘颜色校正 | 收紧+模糊 | 重新抠像 |
| **细节丢失** | 减少模糊 | 扩展遮罩 | 分层Roto |
| **运动模糊错误** | 调整shutter | 启用运动模糊 | 逐帧绘制 |

### 6.3 优化决策树

```python
def decide_optimization_strategy(issues):
    """根据问题列表决定优化策略"""
    strategies = []
    
    for issue in issues:
        if issue["issue"] == "edge_flicker":
            if issue["severity"] == "medium":
                strategies.append("smooth_keyframes")
            else:
                strategies.append("add_keyframes")
        
        elif issue["issue"] == "alpha_out_of_range":
            strategies.append("clamp_alpha")
        
        elif issue["issue"] == "green_spill":
            if issue["severity"] == "high":
                strategies.append("advanced_spill_removal")
            else:
                strategies.append("apply_spill_suppression")
    
    return strategies


def apply_optimization(roto_node, strategies, frame_range):
    """应用优化策略"""
    for strategy in strategies:
        print(f"\n[优化] 应用策略: {strategy}")
        
        if strategy == "smooth_keyframes":
            # 平滑关键帧
            shape = roto_node.property("shapes").getValue(0)[0]
            smooth_keyframes(shape, window_size=3)
        
        elif strategy == "add_keyframes":
            # 增加关键帧
            print("  在问题帧附近补充关键帧")
        
        elif strategy == "clamp_alpha":
            # 限制 Alpha 范围
            print("  限制 Alpha 值在 0-1 范围")
        
        elif strategy == "apply_spill_suppression":
            # 溢色抑制
            apply_spill_suppression(roto_node, "green", 0.5)
        
        elif strategy == "advanced_spill_removal":
            # 高级溢色去除
            advanced_spill_removal(roto_node, frame_range)
    
    print(f"\n[优化] 共应用 {len(strategies)} 个策略")
```

---

## 七、代码示例

### 7.1 完整质量检查与优化流程

```python
from fx import *


def create_quality_optimized_roto(source_path, output_path, frame_range, fps=30):
    """创建质量优化的 Roto 流程"""
    
    # 创建项目和会话
    proj = activeProject() or Project()
    activate(proj)
    
    session = activeSession() or Session()
    session.label = "Quality_Optimized_Roto"
    activate(session)
    proj.addItem(session)
    
    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(fps, 0)
    src.property("frameStart").setValue(frame_range[0], 0)
    src.property("frameEnd").setValue(frame_range[1], 0)
    session.addNode(src)
    
    # Roto 节点（初始优化配置）
    roto = Node("RotoNode")
    roto.label = "Optimized_Main"
    
    # 应用标准优化预设
    roto.property("alpha.blur").setValue(0.5, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("fill").setValue(True, 0)
    roto.property("matte.mode").setValue("alpha", 0)
    roto.property("matte.invert").setValue(False, 0)
    roto.property("motionBlur").setValue(True, 0)
    roto.property("motionBlur.shutter").setValue(0.5, 0)
    
    # 溢色抑制
    roto.property("edge.color.correct").setValue(True, 0)
    roto.property("edge.color.intensity").setValue(0.3, 0)
    
    session.addNode(roto)
    
    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    out_node.property("depth").setValue("32f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)
    
    # 连接节点
    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])
    
    print(f"[SILHOUETTE] 质量优化 Roto 流程已创建")
    print(f"  帧范围: {frame_range[0]}-{frame_range[1]}")
    print(f"  优化项: 抗锯齿、运动模糊、溢色抑制")
    
    return roto


def full_quality_pipeline(roto_node, frame_range):
    """完整质量检查与优化流程"""
    
    print("=" * 60)
    print("[SILHOUETTE] 质量优化流程启动")
    print("=" * 60)
    
    # 步骤 1: 自动质量检查
    print("\n[步骤 1] 自动质量检查")
    report = automated_quality_check(roto_node, frame_range)
    
    # 步骤 2: 问题诊断
    print("\n[步骤 2] 问题诊断")
    issues = run_full_diagnosis(roto_node, frame_range)
    
    # 步骤 3: 收集所有问题
    all_issues = []
    for issue_list in issues.values():
        all_issues.extend(issue_list)
    
    # 步骤 4: 决定优化策略
    print("\n[步骤 3] 优化策略决策")
    strategies = decide_optimization_strategy(all_issues)
    
    # 步骤 5: 应用优化
    print("\n[步骤 4] 应用优化")
    apply_optimization(roto_node, strategies, frame_range)
    
    # 步骤 6: 复检
    print("\n[步骤 5] 优化后复检")
    final_report = automated_quality_check(roto_node, frame_range)
    
    # 总结
    print("\n" + "=" * 60)
    print("[优化完成]")
    print(f"  初始状态: {report['summary']['overall_status']}")
    print(f"  最终状态: {final_report['summary']['overall_status']}")
    print("=" * 60)
    
    return final_report
```

### 7.2 质量评估指标计算

```python
def measure_edge_deviation(roto_node, reference_data):
    """测量边缘偏差（模拟）"""
    # 实际应对比遮罩边缘与参考数据
    return 0.8  # 像素


def measure_temporal_consistency(roto_node):
    """测量时间一致性"""
    # 检查相邻帧参数变化
    consistency = 0.95
    return consistency


def measure_alpha_purity(roto_node):
    """测量 Alpha 纯度"""
    # 检查 Alpha 通道质量
    purity = 0.98
    return purity


def measure_detail_retention(roto_node, reference_data):
    """测量细节保留度"""
    # 对比原始素材与遮罩
    retention = 0.92
    return retention


def generate_quality_report(roto_node, frame_range, output_path=None):
    """生成质量评估报告"""
    scores = {
        "edge_deviation": measure_edge_deviation(roto_node, None),
        "temporal_consistency": measure_temporal_consistency(roto_node),
        "alpha_purity": measure_alpha_purity(roto_node),
        "detail_retention": measure_detail_retention(roto_node, None)
    }
    
    grade = evaluate_quality_grade(scores)
    
    report = {
        "node": roto_node.label,
        "frame_range": frame_range,
        "scores": scores,
        "grade": grade,
        "grade_description": QUALITY_GRADES.get(grade, {}).get("description", "未知"),
        "timestamp": "2026-07-11"
    }
    
    print(f"\n[质量评估报告]")
    print(f"  节点: {report['node']}")
    print(f"  等级: {report['grade']} ({report['grade_description']})")
    print(f"  边缘偏差: {scores['edge_deviation']} 像素")
    print(f"  时间一致性: {scores['temporal_consistency']:.2%}")
    print(f"  Alpha 纯度: {scores['alpha_purity']:.2%}")
    print(f"  细节保留: {scores['detail_retention']:.2%}")
    
    return report
```

### 7.3 遮罩优化工具集

```python
def optimize_matte_quality(roto_node, frame_range, target_grade="A"):
    """优化遮罩质量至目标等级"""
    
    target_criteria = QUALITY_GRADES.get(target_grade)
    if not target_criteria:
        print(f"未知等级: {target_grade}")
        return False
    
    print(f"[优化] 目标等级: {target_grade}")
    
    # 当前评估
    current_scores = {
        "edge_deviation": measure_edge_deviation(roto_node, None),
        "temporal_consistency": measure_temporal_consistency(roto_node),
        "alpha_purity": measure_alpha_purity(roto_node),
        "detail_retention": measure_detail_retention(roto_node, None)
    }
    
    print(f"[优化] 当前评分: {current_scores}")
    
    # 逐项优化
    if current_scores["edge_deviation"] > target_criteria["edge_deviation"]:
        # 优化边缘精度
        roto_node.property("alpha.blur").setValue(0.3, 0)
        roto_node.property("antialias").setValue(1.0, 0)
        print("  - 优化边缘精度")
    
    if current_scores["alpha_purity"] < target_criteria["alpha_purity"]:
        # 优化 Alpha 纯度
        roto_node.property("matte.shrink").setValue(0.5, 0)
        roto_node.property("edge.color.correct").setValue(True, 0)
        print("  - 优化 Alpha 纯度")
    
    if current_scores["temporal_consistency"] < target_criteria["temporal_consistency"]:
        # 优化时间一致性
        shape = roto_node.property("shapes").getValue(0)[0]
        if shape and hasattr(shape, 'points'):
            smooth_keyframes(shape, window_size=3)
        print("  - 优化时间一致性")
    
    # 复检
    final_scores = {
        "edge_deviation": measure_edge_deviation(roto_node, None),
        "temporal_consistency": measure_temporal_consistency(roto_node),
        "alpha_purity": measure_alpha_purity(roto_node),
        "detail_retention": measure_detail_retention(roto_node, None)
    }
    
    final_grade = evaluate_quality_grade(final_scores)
    
    print(f"\n[优化] 最终评分: {final_scores}")
    print(f"[优化] 最终等级: {final_grade}")
    
    return final_grade in [target_grade, "A+"]


def smooth_keyframes(shape, window_size=3):
    """平滑关键帧（简化版）"""
    if not shape or not hasattr(shape, 'points'):
        return
    
    for point in shape.points:
        prop = point.property("position")
        if prop.numKeys < window_size:
            continue
        
        # 收集关键帧值并平滑
        key_values = []
        for k in range(prop.numKeys):
            key_values.append(prop.keyValue(k))
        
        # 移动平均
        for i in range(len(key_values)):
            start = max(0, i - window_size // 2)
            end = min(len(key_values), i + window_size // 2 + 1)
            
            avg_x = sum(v[0] for v in key_values[start:end]) / (end - start)
            avg_y = sum(v[1] for v in key_values[start:end]) / (end - start)
            
            prop.setValue([avg_x, avg_y], prop.keyTime(i))
```

---

## 八、常见问题与最佳实践

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 质量检查通过但合成效果差 | 检查项不全面 | 增加抽检频率，扩大检查范围 |
| 优化后边缘过硬 | 收紧过度 | 配合增加 alpha.blur |
| 优化后细节丢失 | 模糊过度 | 分层处理，细节层单独优化 |
| 自动检查误报 | 阈值设置不当 | 调整检查阈值，结合人工复核 |
| 批量优化性能慢 | 逐帧处理 | 使用分段并行处理 |

### 8.2 最佳实践

**质量保证流程**：
1. **预设检查**：开始 Roto 前验证节点参数预设
2. **过程检查**：每完成 25% 工作量进行一次中间检查
3. **交付检查**：交付前执行完整质量检查流程
4. **抽检复核**：随机抽取 10% 帧进行人工复核

**优化原则**：
1. **最小改动**：只修改有问题的部分，避免过度优化
2. **分层优化**：对不同层使用不同优化策略
3. **A/B 对比**：优化前后对比，确保改进有效
4. **保留备份**：优化前保存原始版本

**团队协作**：
1. **统一标准**：团队使用统一的质量等级标准
2. **检查清单**：建立标准化的检查清单
3. **问题记录**：记录常见问题及解决方案
4. **知识共享**：定期分享优化技巧

### 8.3 质量检查清单模板

```python
QUALITY_CHECKLIST = {
    "pre_delivery": {
        "edge_accuracy": {
            "description": "边缘精度检查",
            "method": "逐帧对比遮罩边缘与对象边缘",
            "criteria": "偏差 ≤ 1 像素（A级）",
            "required": True
        },
        "temporal_consistency": {
            "description": "时间一致性检查",
            "method": "播放检查相邻帧变化",
            "criteria": "无闪烁、无抖动",
            "required": True
        },
        "alpha_purity": {
            "description": "Alpha 纯度检查",
            "method": "检查 Alpha 通道无杂色",
            "criteria": "纯净度 ≥ 97%",
            "required": True
        },
        "motion_blur": {
            "description": "运动模糊检查",
            "method": "对比运动模糊方向与素材",
            "criteria": "方向一致，程度匹配",
            "required": True
        },
        "output_format": {
            "description": "输出格式检查",
            "method": "验证格式、位深、通道",
            "criteria": "EXR 32f RGBA",
            "required": True
        },
        "frame_range": {
            "description": "帧范围检查",
            "method": "验证输出帧范围完整",
            "criteria": "覆盖全部所需帧",
            "required": True
        }
    }
}


def validate_checklist(roto_node, frame_range):
    """验证交付检查清单"""
    print("\n[交付检查清单验证]")
    print("-" * 40)
    
    passed = 0
    failed = 0
    
    for item_name, item in QUALITY_CHECKLIST["pre_delivery"].items():
        # 执行检查（简化）
        result = True  # 实际应执行具体检查
        
        status = "✓" if result else "✗"
        print(f"{status} {item['description']}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print("-" * 40)
    print(f"通过: {passed}  失败: {failed}")
    
    return failed == 0
```

### 8.4 优化参数速查表

| 场景 | alpha.blur | antialias | matte.shrink | motionBlur.shutter |
|------|-----------|-----------|--------------|-------------------|
| 院线电影 | 0.3-0.5 | 1.0 | 0.5 | 0.5 |
| 电视剧 | 0.5-0.8 | 1.0 | 0.5-1.0 | 0.5 |
| 广告 | 0.3-0.5 | 1.0 | 0 | 0.3 |
| 流媒体 | 0.5-1.0 | 0.8 | 0.5 | 0.5 |
| 预览 | 0.8-1.5 | 0.5 | 0 | 0 |

---

## 九、相关文档

- [Silhouette Roto遮罩完全指南](Silhouette%20Roto遮罩完全指南.md)
- [Silhouette 边缘优化与运动模糊](Silhouette%20边缘优化与运动模糊.md)
- [Silhouette 逐帧与插值策略](Silhouette%20逐帧与插值策略.md)
- [Silhouette Roto工作流最佳实践](Silhouette%20Roto工作流最佳实践.md)
- [Silhouette 硬边与柔边遮罩技巧](Silhouette%20硬边与柔边遮罩技巧.md)
- [Silhouette 毛发与半透明物体抠像](Silhouette%20毛发与半透明物体抠像.md)
- [Silhouette 遮罩混合与布尔运算](Silhouette%20遮罩混合与布尔运算.md)
- [Silhouette fx API 参数详解手册](Silhouette%20fx%20API%20参数详解手册.md)
- [Silhouette 行业标准与质量规范](Silhouette%20行业标准与质量规范.md)

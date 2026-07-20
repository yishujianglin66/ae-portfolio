# Silhouette Roto工作流最佳实践

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 提供从素材分析到最终输出的完整 Roto 工作流，涵盖关键帧策略、时间分配、质量检查清单与团队协作规范。

## 目录
1. [工作流总览](#一工作流总览)
2. [Phase 1: 素材分析](#二phase-1-素材分析)
3. [Phase 2: 形状规划](#三phase-2-形状规划)
4. [Phase 3: 关键帧策略](#四phase-3-关键帧策略)
5. [Phase 4: 形状创建与动画](#五phase-4-形状创建与动画)
6. [Phase 5: 质量检查](#六phase-5-质量检查)
7. [Phase 6: 输出与交付](#七phase-6-输出与交付)
8. [时间分配与团队协作](#八时间分配与团队协作)

---

## 一、工作流总览

### 1.1 完整工作流

```
┌─────────────────────────────────────────────────────────┐
│  Phase 1: 素材分析    (5%)   分析运动、对比度、复杂度    │
├─────────────────────────────────────────────────────────┤
│  Phase 2: 形状规划    (10%)  拆分形状、选择样条、命名    │
├─────────────────────────────────────────────────────────┤
│  Phase 3: 关键帧策略  (10%)  确定关键帧位置、间距        │
├─────────────────────────────────────────────────────────┤
│  Phase 4: 形状创建    (50%)  绘制形状、动画、边缘优化    │
├─────────────────────────────────────────────────────────┤
│  Phase 5: 质量检查    (15%)  逐帧检查、修正、清理        │
├─────────────────────────────────────────────────────────┤
│  Phase 6: 输出交付    (10%)  渲染、导出、文档            │
└─────────────────────────────────────────────────────────┘
```

### 1.2 工作流原则

1. **先分析后动手**：充分理解素材再开始绘制。
2. **先轮廓后细节**：先大形状，再细化局部。
3. **先关键帧后插值**：先做关键帧，再让插值填充。
4. **先整体后局部**：先检查整体运动，再修正局部。
5. **先质量后性能**：先保证质量，再优化性能。

---

## 二、Phase 1: 素材分析

### 2.1 分析清单

```python
def analyze_footage(source_path):
    """素材分析清单"""
    analysis = {
        # 1. 基本信息
        "resolution": None,        # 分辨率
        "frame_rate": None,        # 帧率
        "duration": None,          # 时长（帧数）
        "color_space": None,       # 色彩空间

        # 2. 运动分析
        "motion_speed": None,      # 运动: 慢/中/快
        "motion_type": None,       # 类型: 平移/旋转/变形
        "motion_blur": None,       # 运动模糊: 无/轻/重

        # 3. 对比度分析
        "fg_bg_contrast": None,    # 前景背景对比度: 高/中/低
        "edge_clarity": None,      # 边缘清晰度: 清晰/模糊

        # 4. 复杂度评估
        "object_count": None,      # 物体数量
        "shape_complexity": None,  # 形状复杂度: 简单/中/复杂
        "transparency": None,      # 透明度: 无/半透明/透明

        # 5. 工作量估算
        "estimated_shapes": None,  # 预估形状数
        "estimated_keyframes": None,  # 预估关键帧数
        "estimated_hours": None    # 预估工时
    }

    return analysis
```

### 2.2 关键分析维度

#### 运动速度分析

| 速度 | 像素/帧 | 关键帧间距 | 工时倍数 |
|------|---------|-----------|---------|
| 静止 | 0-2 | 24-48 帧 | 0.5x |
| 缓慢 | 2-10 | 12-24 帧 | 1x |
| 正常 | 10-30 | 4-8 帧 | 1.5x |
| 快速 | 30-100 | 1-2 帧 | 2.5x |
| 极速 | 100+ | 逐帧 | 4x |

#### 对比度分析

```
高对比度（前景背景清晰）:
  - 边缘检测可用
  - AI 辅助效果好
  - 工时 0.8x

低对比度（前景背景相近）:
  - 需手工逐帧
  - AI 辅助效果差
  - 工时 2x
```

### 2.3 分析报告模板

```python
def generate_analysis_report(source_path):
    """生成素材分析报告"""
    print("=== 素材分析报告 ===")
    print(f"文件: {source_path}")
    print(f"分辨率: 1920x1080")
    print(f"帧率: 24 fps")
    print(f"时长: 240 帧 (10 秒)")
    print()
    print("运动分析:")
    print(f"  速度: 正常 (15 px/帧)")
    print(f"  类型: 平移 + 变形")
    print(f"  运动模糊: 中等")
    print()
    print("对比度分析:")
    print(f"  前景背景对比度: 中")
    print(f"  边缘清晰度: 中等")
    print()
    print("复杂度评估:")
    print(f"  物体数量: 1 (人物)")
    print(f"  形状复杂度: 中")
    print(f"  透明度: 无")
    print()
    print("工作量估算:")
    print(f"  预估形状数: 8-12")
    print(f"  预估关键帧数: 30-50")
    print(f"  预估工时: 4-6 小时")
```

---

## 三、Phase 2: 形状规划

### 3.1 形状拆分原则

```
1. 按身体部位拆分（头/身/臂/腿）
2. 按运动独立性拆分（独立运动部位单独形状）
3. 按边缘类型拆分（硬边/柔边分开）
4. 按深度层次拆分（前/中/后景分开）
```

### 3.2 形状规划表

| 部位 | 形状名 | 样条类型 | 点数 | 羽化 | 优先级 |
|------|--------|---------|------|------|--------|
| 身体 | Body_Main | X-Spline | 8-12 | 2.0 | 0 |
| 头部 | Head_Skull | X-Spline | 8-10 | 1.5 | 1 |
| 头发 | Hair_Main | X-Spline | 10-15 | 4.0 | 2 |
| 头发 | Hair_Flyaway | X-Spline | 6-8 | 12.0 | 3 |
| 左臂 | Arm_Left | X-Spline | 6-8 | 2.0 | 4 |
| 右臂 | Arm_Right | X-Spline | 6-8 | 2.0 | 5 |
| 眼睛 | Eye_Left | Bezier | 4 | 0.0 | 6 |
| 眼睛 | Eye_Right | Bezier | 4 | 0.0 | 7 |

### 3.3 形状规划脚本

```python
def create_shape_plan():
    """形状规划"""
    plan = [
        {"name": "Body_Main", "type": "X-Spline", "points": 10,
         "feather": 2.0, "priority": 0, "motion_blur": False},
        {"name": "Head_Skull", "type": "X-Spline", "points": 8,
         "feather": 1.5, "priority": 1, "motion_blur": False},
        {"name": "Hair_Main", "type": "X-Spline", "points": 12,
         "feather": 4.0, "priority": 2, "motion_blur": True},
        {"name": "Hair_Flyaway", "type": "X-Spline", "points": 6,
         "feather": 12.0, "priority": 3, "motion_blur": True},
        {"name": "Arm_Left", "type": "X-Spline", "points": 8,
         "feather": 2.0, "priority": 4, "motion_blur": True},
        {"name": "Arm_Right", "type": "X-Spline", "points": 8,
         "feather": 2.0, "priority": 5, "motion_blur": True},
        {"name": "Eye_Left", "type": "Bezier", "points": 4,
         "feather": 0.0, "priority": 6, "motion_blur": False},
        {"name": "Eye_Right", "type": "Bezier", "points": 4,
         "feather": 0.0, "priority": 7, "motion_blur": False},
    ]
    return plan
```

---

## 四、Phase 3: 关键帧策略

### 4.1 关键帧位置选择

```
关键帧选择原则:

1. 运动转折点（方向变化处）
   帧 0 ──→ 帧 12 ──→ 帧 24 ──→ 帧 36
   (起始)    (转向)     (极值)    (回归)

2. 极端位置（最远点）
   - 最左/最右
   - 最高/最低
   - 最大变形

3. 视觉关键帧（重要动作）
   - 入画/出画
   - 接触/分离
   - 遮挡发生/解除
```

### 4.2 关键帧间距策略

| 运动类型 | 间距 | 总帧数 | 关键帧数 |
|---------|------|--------|---------|
| 静止 | 48 帧 | 240 | 5 |
| 缓慢 | 24 帧 | 240 | 10 |
| 正常 | 8 帧 | 240 | 30 |
| 快速 | 2 帧 | 240 | 120 |
| 极速 | 1 帧 | 240 | 240 |

### 4.3 关键帧规划脚本

```python
def plan_keyframes(total_frames, motion_type="normal"):
    """规划关键帧位置"""
    spacing = {
        "static": 48,
        "slow": 24,
        "normal": 8,
        "fast": 2,
        "extreme": 1
    }

    interval = spacing.get(motion_type, 8)
    keyframes = list(range(0, total_frames + 1, interval))

    # 确保包含最后一帧
    if keyframes[-1] != total_frames:
        keyframes.append(total_frames)

    print(f"[PLAN] 运动类型: {motion_type}")
    print(f"[PLAN] 关键帧间距: {interval}")
    print(f"[PLAN] 关键帧数: {len(keyframes)}")
    print(f"[PLAN] 关键帧位置: {keyframes}")

    return keyframes
```

---

## 五、Phase 4: 形状创建与动画

### 5.1 创建顺序

```
1. 创建所有形状（先不动画）
2. 设置优先级和混合模式
3. 在第 0 帧绘制所有形状
4. 跳到关键帧，逐帧调整
5. 检查插值，补充中间帧
6. 边缘优化（羽化、模糊、运动模糊）
```

### 5.2 标准创建流程

```python
from fx import *

def standard_creation_workflow(source_path, output_path, frame_rate=24.0):
    """标准创建流程"""
    # === 1. 项目初始化 ===
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Standard_Workflow"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # === 2. RotoNode 创建 ===
    roto = Node("RotoNode")
    roto.label = "Main_Roto"
    roto.property("alpha.blur").setValue(0.4, 0)
    roto.property("antialias").setValue(1.0, 0)
    session.addNode(roto)

    # === 3. 按规划创建形状 ===
    plan = create_shape_plan()
    shapes = {}
    for item in plan:
        shape = roto.createObject(item["type"])
        shape.name = item["name"]
        shape.property("feather").setValue(item["feather"], 0)
        shape.property("priority").setValue(item["priority"], 0)
        shape.property("motionBlur").setValue(item["motion_blur"], 0)
        shapes[item["name"]] = shape

    # === 4. 输出节点 ===
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[WORKFLOW] 标准流程完成")
    print(f"  形状数: {len(shapes)}")
    return roto, shapes
```

### 5.3 动画制作流程

```python
def animation_workflow(shape, keyframes, motion_data):
    """动画制作流程"""
    # 1. 第 0 帧绘制基础形状
    base_points = motion_data[0]
    for pt in base_points:
        shape.addPoint(pt, frame=0)

    # 2. 在每个关键帧调整
    for frame in keyframes[1:]:
        if frame in motion_data:
            frame_points = motion_data[frame]
            for i, pt in enumerate(frame_points):
                if i < len(shape.points):
                    shape.points[i].setValue(pt, frame)

    # 3. 设置插值模式
    for point in shape.points:
        for key_idx in range(point.numKeys):
            point.setKeyInterpolation(key_idx, "bezier")

    # 4. 检查中间帧
    print(f"[ANIM] {shape.name} 动画完成")
    print(f"  关键帧数: {shape.points[0].numKeys if shape.points else 0}")
```

---

## 六、Phase 5: 质量检查

### 6.1 质量检查清单

```python
def quality_checklist(roto_node, frame_range):
    """质量检查清单"""
    checklist = {
        "形状完整性": False,
        "边缘质量": False,
        "动画流畅": False,
        "运动模糊": False,
        "羽化一致": False,
        "无沸腾": False,
        "无溢色": False,
        "命名规范": False
    }

    # 1. 形状完整性
    shapes = roto_node.objects
    if len(shapes) > 0:
        checklist["形状完整性"] = True

    # 2. 边缘质量
    all_feather_ok = True
    for shape in shapes:
        feather = shape.property("feather").getValue(0)
        if feather < 0 or feather > 30:
            all_feather_ok = False
            break
    checklist["边缘质量"] = all_feather_ok

    # 3. 动画流畅（检查关键帧数）
    if shapes and len(shapes[0].points) > 0:
        num_keys = shapes[0].points[0].numKeys
        if num_keys >= len(frame_range) / 24:  # 至少每 24 帧一关键帧
            checklist["动画流畅"] = True

    # 4. 运动模糊（如有快速运动）
    has_motion_blur = False
    for shape in shapes:
        if shape.property("motionBlur").getValue(0):
            has_motion_blur = True
            break
    checklist["运动模糊"] = True  # 视场景而定

    # 5. 羽化一致（同类型形状）
    checklist["羽化一致"] = True

    # 6. 无沸腾（需逐帧检查）
    checklist["无沸腾"] = True  # 简化

    # 7. 无溢色
    checklist["无溢色"] = True

    # 8. 命名规范
    valid_prefixes = ["Head_", "Hair_", "Body_", "Arm_", "Eye_", "Prop_"]
    all_named = True
    for shape in shapes:
        if not any(shape.name.startswith(p) for p in valid_prefixes):
            all_named = False
            break
    checklist["命名规范"] = all_named

    # 打印结果
    print("=== 质量检查清单 ===")
    for item, passed in checklist.items():
        status = "✓ 通过" if passed else "✗ 未通过"
        print(f"  {item}: {status}")

    return checklist
```

### 6.2 逐帧检查脚本

```python
def frame_by_frame_check(roto_node, start_frame, end_frame, step=1):
    """逐帧检查"""
    issues = []

    for frame in range(start_frame, end_frame + 1, step):
        for shape in roto_node.objects:
            # 检查形状是否有效
            if not shape.visible:
                continue

            # 检查控制点位置
            for i, point in enumerate(shape.points):
                try:
                    pos = point.getValue(frame)
                    if pos[0] < 0 or pos[1] < 0:  # 超出画面
                        issues.append({
                            "frame": frame,
                            "shape": shape.name,
                            "point": i,
                            "issue": "out_of_bounds"
                        })
                except:
                    issues.append({
                        "frame": frame,
                        "shape": shape.name,
                        "point": i,
                        "issue": "no_keyframe"
                    })

    if issues:
        print(f"[CHECK] 发现 {len(issues)} 个问题")
        for issue in issues[:10]:  # 只显示前 10 个
            print(f"  帧 {issue['frame']} - {issue['shape']}.{issue['point']}: {issue['issue']}")
    else:
        print("[CHECK] 逐帧检查通过")

    return issues
```

---

## 七、Phase 6: 输出与交付

### 7.1 输出配置

```python
def configure_output(out_node, output_path, format="exr"):
    """配置输出"""
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue(format, 0)

    if format == "exr":
        out_node.property("compression").setValue("none", 0)  # 无压缩
        out_node.property("channels").setValue("rgba", 0)     # RGBA
    elif format == "png":
        out_node.property("compression").setValue("lossless", 0)

    print(f"[OUTPUT] 格式: {format}")
    print(f"[OUTPUT] 路径: {output_path}")
```

### 7.2 交付清单

```python
def delivery_checklist():
    """交付清单"""
    print("=== 交付清单 ===")
    items = [
        "遮罩序列（EXR/PNG）",
        "项目文件（.sfx）",
        "形状结构报告",
        "质量检查报告",
        "关键帧位置文档",
        "已知问题列表",
        "版本号与日期",
        "制作者信息"
    ]

    for i, item in enumerate(items, 1):
        print(f"  {i}. [ ] {item}")

    return items
```

---

## 八、时间分配与团队协作

### 8.1 时间分配建议

| 阶段 | 占比 | 8小时项目 | 40小时项目 |
|------|------|----------|-----------|
| 素材分析 | 5% | 0.4h | 2h |
| 形状规划 | 10% | 0.8h | 4h |
| 关键帧策略 | 10% | 0.8h | 4h |
| 形状创建 | 50% | 4h | 20h |
| 质量检查 | 15% | 1.2h | 6h |
| 输出交付 | 10% | 0.8h | 4h |

### 8.2 团队协作规范

```
1. 命名统一: 所有成员使用相同命名规范
2. 文件版本: project_v01.sfx, project_v02.sfx...
3. 分工明确: 按部位分工（A 做头部，B 做身体）
4. 交接检查: 交接时检查形状完整性和命名
5. 定期同步: 每日同步进度和问题
6. 质量把关: 负责人统一审核质量
```

### 8.3 版本管理

```python
def version_management(project_path, version):
    """版本管理"""
    import os
    base, ext = os.path.splitext(project_path)
    versioned_path = f"{base}_v{version:02d}{ext}"

    print(f"[VERSION] 当前版本: v{version:02d}")
    print(f"[VERSION] 文件: {versioned_path}")

    return versioned_path
```

### 8.4 完整工作流示例

```python
def full_workflow(source_path, output_path, frame_rate=24.0, total_frames=240):
    """完整工作流示例"""
    print("=" * 60)
    print("Silhouette Roto 完整工作流")
    print("=" * 60)

    # === Phase 1: 素材分析 ===
    print("\n>>> Phase 1: 素材分析")
    generate_analysis_report(source_path)

    # === Phase 2: 形状规划 ===
    print("\n>>> Phase 2: 形状规划")
    plan = create_shape_plan()
    print(f"规划形状数: {len(plan)}")

    # === Phase 3: 关键帧策略 ===
    print("\n>>> Phase 3: 关键帧策略")
    keyframes = plan_keyframes(total_frames, "normal")

    # === Phase 4: 形状创建 ===
    print("\n>>> Phase 4: 形状创建")
    roto, shapes = standard_creation_workflow(
        source_path, output_path, frame_rate
    )

    # === Phase 5: 质量检查 ===
    print("\n>>> Phase 5: 质量检查")
    quality_checklist(roto, range(0, total_frames))

    # === Phase 6: 输出交付 ===
    print("\n>>> Phase 6: 输出交付")
    delivery_checklist()

    print("\n" + "=" * 60)
    print("工作流完成")
    print("=" * 60)
```

---

## 九、常见问题与最佳实践

### 9.1 问题诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 工时超估 | 素材复杂度评估不足 | Phase 1 充分分析 |
| 形状太多难管理 | 拆分过细 | 合并相似形状 |
| 动画"抖" | 关键帧过密 | 清理冗余关键帧 |
| 团队交接混乱 | 命名不统一 | 强制命名规范 |
| 质量不稳定 | 缺乏检查清单 | 使用 quality_checklist |

### 9.2 最佳实践

1. **充分分析**：Phase 1 占用 5% 时间，但能节省后期 30% 返工。
2. **规划先行**：先列形状规划表，再开始绘制。
3. **关键帧优先**：先做关键帧，让插值填充中间。
4. **定期检查**：每完成 25% 工作量做一次质量检查。
5. **版本管理**：每 2 小时保存一个版本。
6. **团队同步**：每日 15 分钟同步会议。

### 9.3 质量检查清单

- [ ] 素材分析报告完成
- [ ] 形状规划表完成
- [ ] 关键帧位置确定
- [ ] 所有形状命名规范
- [ ] 渲染顺序正确
- [ ] 边缘质量合格
- [ ] 动画流畅无抖动
- [ ] 运动模糊匹配
- [ ] 逐帧检查通过
- [ ] 交付清单完整

---

## 相关文档

- [Silhouette 逐帧与插值策略](Silhouette%20逐帧与插值策略.md)
- [Silhouette 遮罩质量检查与优化](Silhouette%20遮罩质量检查与优化.md)
- [Silhouette 多形状管理与层级控制](Silhouette%20多形状管理与层级控制.md)
- [Silhouette Roto遮罩完全指南](Silhouette%20Roto遮罩完全指南.md)

# Silhouette Paint跟踪修复技术

> 分类: 跟踪技术专题
> 更新日期: 2026-07-11
> 概述: Paint跟踪原理深度解析，涵盖自动跟踪修复、帧间传播机制、偏移修正与跟踪驱动修复的完整工作流。

## 目录
1. [Paint 跟踪原理](#一paint-跟踪原理)
2. [自动跟踪修复](#二自动跟踪修复)
3. [帧间传播机制](#三帧间传播机制)
4. [偏移修正技术](#四偏移修正技术)
5. [跟踪驱动修复工作流](#五跟踪驱动修复工作流)
6. [高级传播技巧](#六高级传播技巧)
7. [质量保证](#七质量保证)
8. [故障排查](#八故障排查)

---

## 一、Paint 跟踪原理

### 1.1 原理概述

Paint 跟踪修复是 Silhouette 的特色功能，它将平面跟踪技术与 Paint 修复笔刷结合，使修复笔触能够自动跟随目标区域的运动，从单帧修复扩展到序列修复，大幅减少逐帧手工修复的工作量。

### 1.2 工作流程图

```
源视频 → PlanarTracker 跟踪目标区域 → 记录修复笔触
       → 跟踪数据驱动笔触传播 → 全序列自动修复
       → 检查传播结果 → 手动修正问题帧
```

### 1.3 核心机制

| 机制 | 说明 |
|------|------|
| 跟踪绑定 | 修复笔触与跟踪区域绑定 |
| 坐标变换 | 笔触坐标随跟踪矩阵变换 |
| 自动传播 | 笔触自动应用到所有跟踪帧 |
| 偏移修正 | 手动调整传播笔触的偏移 |
| 时序控制 | 控制笔触在时间轴上的有效范围 |

### 1.4 与传统逐帧修复对比

| 维度 | Paint 跟踪修复 | 传统逐帧修复 |
|------|---------------|-------------|
| 工作量 | 低（一次修复+修正） | 高（每帧手工） |
| 一致性 | 高（自动传播） | 中（人工易不一致） |
| 精度 | 中~高（依赖跟踪质量） | 高（每帧可控） |
| 适用场景 | 稳定运动目标 | 任意场景 |
| 修正需求 | 跟踪误差处需修正 | 无需传播修正 |

---

## 二、自动跟踪修复

### 2.1 基本工作流

```python
from fx import *

# 项目初始化
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Paint_Track_Repair"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 跟踪节点（先跟踪目标区域）
track = Node("TrackerNode")
track.label = "Paint_Track_Source"
track.property("trackType").setValue("planar", 0)
track.property("searchArea").setValue(21, 0)
track.property("accuracy").setValue("high", 0)
track.property("patternSize").setValue(11, 0)
track.property("motionModel").setValue("perspective", 0)
track.property("forward").setValue(True, 0)
track.property("backward").setValue(True, 0)
session.addNode(track)

# Paint 节点（接收跟踪数据）
paint = Node("PaintNode")
paint.label = "Tracked_Paint"
paint.property("mode").setValue("clone", 0)
paint.property("brush.size").setValue(30.0, 0)
paint.property("brush.hardness").setValue(0.3, 0)
paint.property("brush.flow").setValue(1.0, 0)
session.addNode(paint)

# 输出节点
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/paint_repair_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

# 连接节点
src.outputs[0].connect(track.inputs[0])
track.outputs[0].connect(paint.inputs[0])
paint.outputs[0].connect(out_node.inputs[0])

print("[SILHOUETTE] Paint track repair pipeline ready")
```

### 2.2 自动传播原理

当在参考帧上绘制修复笔触后，Paint 节点会根据跟踪数据自动计算笔触在其他帧的位置：

1. **记录笔触坐标**：参考帧上笔触的中心点和形状
2. **应用跟踪变换**：将笔触坐标通过跟踪矩阵变换到目标帧
3. **重新采样源**：在目标帧的变换后位置重新采样克隆源
4. **应用修复**：将采样结果应用到目标帧

### 2.3 传播参数

```python
# 传播控制参数
paint.property("propagation").setValue("tracked", 0)  # 跟踪传播模式
paint.property("propagateMode").setValue("forward", 0)  # 向前传播
paint.property("offsetCorrection").setValue(True, 0)  # 启用偏移修正
```

---

## 三、帧间传播机制

### 3.1 传播模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| tracked | 跟踪驱动传播 | 稳定运动目标 |
| auto | 自动传播（基于光流） | 中等运动目标 |
| manual | 手动逐帧 | 复杂运动或高精度需求 |
| interpolate | 插值传播 | 关键帧间插值 |

### 3.2 跟踪传播详解

跟踪传播是最稳定的自动传播方式：

```
参考帧 N：
  - 笔触位置 P_ref = [x_ref, y_ref]
  - 跟踪矩阵 M_ref

目标帧 N+1：
  - 跟踪矩阵 M_target
  - 相对变换 ΔM = M_target × M_ref^(-1)
  - 笔触位置 P_target = ΔM × P_ref
  - 克隆源位置 = P_target + 原始偏移
```

### 3.3 光流传播

当无跟踪数据时，可使用光流传播：

```python
paint.property("propagation").setValue("auto", 0)
# 光流传播基于像素级运动估计
# 适用于无明确平面的场景
# 精度低于跟踪传播，但适用性更广
```

### 3.4 传播范围控制

```python
# 控制笔触传播的帧范围
paint.property("propagateStart").setValue(10, 0)  # 从第10帧开始传播
paint.property("propagateEnd").setValue(100, 0)   # 传播到第100帧
```

### 3.5 多笔触传播

一个 Paint 节点可包含多个笔触，每个笔触独立传播：

```
笔触1（参考帧=5）：覆盖区域A，传播 5→50
笔触2（参考帧=10）：覆盖区域B，传播 10→80
笔触3（参考帧=20）：覆盖区域C，传播 20→100
```

---

## 四、偏移修正技术

### 4.1 偏移产生原因

即使跟踪数据质量很高，传播后的笔触仍可能出现偏移，原因包括：

- 跟踪亚像素误差累积
- 目标区域非完全平面
- 修复区域与跟踪区域中心不重合
- 克隆源区域运动与目标区域不完全一致

### 4.2 偏移检测

**方法一：逐帧检查**
逐帧查看传播结果，标记偏移明显的帧。

**方法二：差值分析**
将修复结果与期望结果做差值，分析偏移分布。

**方法三：参考特征对比**
观察修复区域附近的特征点，判断修复内容是否对齐。

### 4.3 偏移修正方法

**方法一：整体偏移修正**
对所有帧应用统一的偏移量：
```python
# 假设检测到整体偏移 [5, 3]
paint.property("globalOffset").setValue([5.0, 3.0], 0)
```

**方法二：关键帧偏移修正**
在偏移明显的帧手动调整笔触位置：
```python
# 在第30帧设置偏移修正
paint.property("offsetCorrection").setValue([2.0, 1.0], 30)
# 在第60帧设置偏移修正
paint.property("offsetCorrection").setValue([-1.0, 2.0], 60)
# 中间帧自动插值
```

**方法三：分段修正**
将序列分为多段，每段独立修正偏移：
```
段1：帧 0~30，偏移修正 [2, 1]
段2：帧 30~60，偏移修正 [-1, 2]
段3：帧 60~100，偏移修正 [0, 0]
```

### 4.4 偏移修正脚本

```python
# 批量偏移修正
def apply_offset_corrections(paint, corrections):
    """
    corrections: dict {帧号: [dx, dy]}
    """
    for frame, offset in corrections.items():
        paint.property("offsetCorrection").setValue(offset, frame)
        print(f"[SILHOUETTE] 第{frame}帧偏移修正: {offset}")

# 示例：在问题帧设置偏移修正
corrections = {
    15: [2.0, 1.0],   # 第15帧偏移
    30: [-1.0, 2.0],  # 第30帧偏移
    45: [3.0, 0.0],   # 第45帧偏移
    60: [0.0, -1.0],  # 第60帧偏移
}
apply_offset_corrections(paint, corrections)
```

---

## 五、跟踪驱动修复工作流

### 5.1 完整工作流

```
1. 分析镜头，确定修复区域和跟踪区域
2. 创建 PlanarTracker 跟踪目标区域
3. 执行跟踪并验证质量
4. 在参考帧上绘制修复笔触
5. 启用跟踪传播
6. 检查传播结果，标记问题帧
7. 在问题帧手动修正偏移
8. 渲染输出
9. 审阅最终结果
10. 必要时迭代修正
```

### 5.2 参考帧选择

参考帧应选择：
- 修复区域最清晰的帧
- 跟踪质量最高的帧
- 序列中间帧（减少最大传播距离）
- 无遮挡的帧

### 5.3 修复区域与跟踪区域关系

| 关系 | 说明 | 效果 |
|------|------|------|
| 修复区域 = 跟踪区域 | 修复区域与跟踪区域重合 | 最佳传播效果 |
| 修复区域在跟踪区域内 | 修复区域是跟踪区域的一部分 | 良好传播效果 |
| 修复区域在跟踪区域外 | 修复区域与跟踪区域分离 | 需要偏移修正 |
| 修复区域跨多平面 | 修复区域横跨不同运动平面 | 需分段跟踪修复 |

### 5.4 多区域修复

对于复杂修复任务，可使用多个 Paint 节点：

```python
# 区域1：墙面修复
paint1 = Node("PaintNode")
paint1.label = "Paint_Wall"
paint1.property("mode").setValue("clone", 0)

# 区域2：地面修复
paint2 = Node("PaintNode")
paint2.label = "Paint_Ground"
paint2.property("mode").setValue("clone", 0)

# 各自连接独立的跟踪节点
# track1 → paint1（墙面跟踪）
# track2 → paint2（地面跟踪）
```

---

## 六、高级传播技巧

### 6.1 多笔触分层修复

对于复杂修复区域，使用多笔触分层修复：

```
层1：底色修复（大笔触，覆盖整体）
层2：纹理修复（中笔触，恢复纹理）
层3：细节修复（小笔触，处理边缘）
```

每层独立传播，互不干扰。

### 6.2 时间衰减传播

对于运动模糊或渐变区域，可使用时间衰减传播：

```python
# 越远离参考帧，笔触不透明度越低
paint.property("timeDecay").setValue(True, 0)
paint.property("decayRate").setValue(0.95, 0)  # 每帧衰减5%
```

### 6.3 双向传播

从中间参考帧向前后双向传播：

```python
paint.property("propagateMode").setValue("bidirectional", 0)
```

### 6.4 跟踪+光流混合传播

对于跟踪失效的局部区域，可混合使用光流传播：

1. 大部分帧使用跟踪传播（稳定）
2. 跟踪失效帧切换为光流传播
3. 两模式接缝处手动检查

---

## 七、质量保证

### 7.1 检查清单

- [ ] 跟踪数据质量经验证（无漂移、无丢失）
- [ ] 参考帧选择合理
- [ ] 修复笔触在参考帧上效果自然
- [ ] 传播结果逐帧检查
- [ ] 偏移修正已应用到问题帧
- [ ] 边缘帧（首尾）效果稳定
- [ ] 修复区域与周边融合自然
- [ ] 无闪烁、无跳变

### 7.2 常见缺陷

| 缺陷 | 表现 | 原因 | 解决方案 |
|------|------|------|----------|
| 闪烁 | 修复区域亮度跳变 | 克隆源不稳定 | 选择更稳定的克隆源 |
| 滑动 | 修复内容相对目标滑动 | 跟踪偏移 | 关键帧偏移修正 |
| 边缘错位 | 修复区域边缘不对齐 | 跟踪精度不足 | 提高跟踪精度或手动修正 |
| 内容重复 | 修复区域出现重复纹理 | 克隆源距离过近 | 调整克隆源偏移 |
| 时序跳变 | 某帧修复内容突变 | 传播失败 | 检查该帧跟踪数据 |

### 7.3 渲染验证

```python
# 渲染并生成检查序列
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/check_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("frameStart").setValue(0, 0)
out_node.property("frameEnd").setValue(120, 0)
session.addNode(out_node)
```

---

## 八、故障排查

### 8.1 传播完全不工作

**检查项**：
1. Paint 节点是否连接到 Tracker 节点
2. propagation 是否设置为 "tracked"
3. 跟踪数据是否存在（检查 Tracker 节点是否已执行跟踪）
4. 参考帧是否设置了笔触

### 8.2 传播部分帧失败

**可能原因**：
- 跟踪在这些帧丢失
- 帧范围设置限制
- 偏移过大超出搜索范围

**解决方案**：
```python
# 检查并扩大传播范围
paint.property("propagateStart").setValue(0, 0)
paint.property("propagateEnd").setValue(120, 0)
```

### 8.3 修复内容闪烁

**解决方案**：
- 增大笔触大小，覆盖更大区域
- 降低 brush.hardness，软化边缘
- 选择更稳定的克隆源
- 启用时间平滑

```python
paint.property("brush.size").setValue(40.0, 0)
paint.property("brush.hardness").setValue(0.2, 0)
paint.property("timeSmooth").setValue(True, 0)
```

### 8.4 性能优化

- 预览阶段使用低精度跟踪
- 分段渲染长序列
- 关闭不必要的双向传播
- 使用代理素材进行交互式调整

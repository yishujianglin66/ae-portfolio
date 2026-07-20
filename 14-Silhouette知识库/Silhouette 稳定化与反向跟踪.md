# Silhouette 稳定化与反向跟踪

> 分类: 跟踪技术专题
> 更新日期: 2026-07-11
> 概述: 稳定化技术与反向跟踪应用深度解析，涵盖稳定化参数、运动平滑、抖动去除与反向跟踪工作流。

## 目录
1. [稳定化原理](#一稳定化原理)
2. [稳定化参数详解](#二稳定化参数详解)
3. [抖动去除技术](#三抖动去除技术)
4. [运动平滑](#四运动平滑)
5. [反向跟踪应用](#五反向跟踪应用)
6. [稳定化工作流](#六稳定化工作流)
7. [高级技巧](#七高级技巧)
8. [故障排查](#八故障排查)

---

## 一、稳定化原理

### 1.1 什么是稳定化

稳定化（Stabilization）是通过跟踪画面中本应静止的参考点，计算摄像机抖动，然后反向应用该运动，使画面看起来稳定的过程。

### 1.2 稳定化的类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| 位置稳定 | 仅稳定平移 | 简单抖动 |
| 位置+旋转稳定 | 稳定平移和旋转 | 手持镜头 |
| 位置+旋转+缩放 | 稳定变换 | 变焦抖动 |
| 四点稳定 | 完全稳定透视 | 复杂抖动 |
| 子空间稳定 | 基于多点统计 | 高级稳定 |

### 1.3 稳定化流程

```
1. 跟踪画面中的静态参考点
2. 计算每帧相对参考帧的变换
3. 反向应用变换（抵消运动）
4. 输出稳定后的画面
5. 处理边缘问题（缩放/裁剪）
```

### 1.4 反向跟踪概念

反向跟踪（Reverse Tracking）是将跟踪数据反向应用的技术：
- 稳定化是反向跟踪的一种应用
- 也可用于将元素"粘贴"到运动物体上
- 还可用于运动匹配与偏移修正

---

## 二、稳定化参数详解

### 2.1 稳定化节点属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| stabilizeMode | string | "position" | 稳定模式 |
| referenceFrame | int | 0 | 参考帧 |
| smoothRadius | int | 5 | 平滑半径 |
| borderMode | string | "scale" | 边缘处理模式 |
| scale | float | 1.05 | 边缘缩放 |
| cropMargin | float | 0.0 | 裁剪边距 |
| jitterThreshold | float | 0.5 | 抖动阈值 |

### 2.2 稳定模式

```python
# 位置稳定（最常用）
stab.property("stabilizeMode").setValue("position", 0)

# 位置+旋转稳定
stab.property("stabilizeMode").setValue("positionRotation", 0)

# 位置+旋转+缩放稳定
stab.property("stabilizeMode").setValue("positionRotationScale", 0)

# 透视稳定（四点）
stab.property("stabilizeMode").setValue("perspective", 0)
```

### 2.3 参考帧选择

```python
# 参考帧：画面应稳定到的目标帧
stab.property("referenceFrame").setValue(0, 0)  # 稳定到第一帧

# 或选择中间帧
stab.property("referenceFrame").setValue(60, 0)  # 稳定到第60帧
```

**参考帧选择原则**：
- 选择画面构图最佳的帧
- 选择跟踪最稳定的帧
- 通常选择首帧或中间帧

### 2.4 平滑半径

```python
# 平滑半径控制运动平滑程度
stab.property("smoothRadius").setValue(5, 0)   # 轻度平滑
stab.property("smoothRadius").setValue(15, 0)  # 中度平滑
stab.property("smoothRadius").setValue(30, 0)  # 重度平滑（保留缓慢运动）
```

| 平滑半径 | 效果 | 适用场景 |
|----------|------|----------|
| 1~5 | 几乎无平滑 | 仅去除高频抖动 |
| 5~15 | 轻度平滑 | 去除手持抖动 |
| 15~30 | 中度平滑 | 保留缓慢运动 |
| 30+ | 重度平滑 | 完全锁定画面 |

### 2.5 边缘处理

```python
# 缩放模式：放大画面填补边缘
stab.property("borderMode").setValue("scale", 0)
stab.property("scale").setValue(1.05, 0)  # 放大5%

# 裁剪模式：裁剪掉边缘空白
stab.property("borderMode").setValue("crop", 0)
stab.property("cropMargin").setValue(0.02, 0)  # 裁剪2%

# 镜像模式：镜像边缘像素
stab.property("borderMode").setValue("mirror", 0)
```

---

## 三、抖动去除技术

### 3.1 抖动类型

| 抖动类型 | 频率 | 原因 | 处理方法 |
|----------|------|------|----------|
| 高频抖动 | > 10Hz | 手持震动 | 小平滑半径 |
| 中频抖动 | 1~10Hz | 步行、呼吸 | 中等平滑半径 |
| 低频漂移 | < 1Hz | 摄像机移动 | 大平滑半径 |
| 周期性抖动 | 固定频率 | 机械振动 | 频域滤波 |

### 3.2 抖动检测

```python
def detect_jitter(track_data, threshold=0.5):
    """检测跟踪数据中的抖动"""

    jitter_frames = []
    for i in range(1, len(track_data) - 1):
        prev = track_data[i - 1]
        curr = track_data[i]
        next_ = track_data[i + 1]

        # 计算二阶差分（加速度）
        accel_x = (next_[0] - 2 * curr[0] + prev[0])
        accel_y = (next_[1] - 2 * curr[1] + prev[1])

        accel = (accel_x**2 + accel_y**2) ** 0.5

        if accel > threshold:
            jitter_frames.append({
                "frame": i,
                "acceleration": accel
            })

    return jitter_frames
```

### 3.3 抖动去除策略

**策略一：平滑滤波**
```python
# 使用平滑半径去除抖动
stab.property("smoothRadius").setValue(10, 0)
```

**策略二：频域滤波**
分离运动的高频和低频成分，仅去除高频：
```python
# 伪代码：频域分离
def separate_motion(track_data, cutoff_freq=0.1):
    """
    分离运动为低频（缓慢）和高频（抖动）
    cutoff_freq: 截止频率
    """
    # 实际实现需要 FFT 或低通滤波
    low_freq = low_pass_filter(track_data, cutoff_freq)
    high_freq = [track_data[i] - low_freq[i] for i in range(len(track_data))]
    return low_freq, high_freq

# 仅去除高频抖动，保留低频运动
# stabilized = original - high_freq
```

**策略三：自适应抖动阈值**
```python
# 设置抖动阈值，仅处理超过阈值的运动
stab.property("jitterThreshold").setValue(0.5, 0)
# 小于 0.5 像素的运动视为抖动，予以去除
```

### 3.4 选择性稳定

对于"想保留摄像机运动但去除抖动"的场景：

1. 跟踪原始运动（含抖动）
2. 平滑跟踪数据得到"理想运动"
3. 计算差值（抖动成分）
4. 仅反向应用抖动成分

```python
# 伪代码：选择性稳定
def selective_stabilize(track_data, smooth_window=15):
    """保留主要运动，仅去除抖动"""
    smoothed = smooth_data(track_data, smooth_window)
    jitter = [track_data[i] - smoothed[i] for i in range(len(track_data))]
    stabilized = [track_data[i] - jitter[i] for i in range(len(track_data))]
    # stabilized = smoothed，但保留原始平滑后的运动
    return smoothed
```

---

## 四、运动平滑

### 4.1 平滑算法

**移动平均**：
```python
def moving_average(data, window=5):
    """移动平均平滑"""
    smoothed = []
    for i in range(len(data)):
        start = max(0, i - window // 2)
        end = min(len(data), i + window // 2 + 1)
        avg_x = sum(d[0] for d in data[start:end]) / (end - start)
        avg_y = sum(d[1] for d in data[start:end]) / (end - start)
        smoothed.append([avg_x, avg_y])
    return smoothed
```

**高斯平滑**：
```python
import math

def gaussian_smooth(data, sigma=3.0):
    """高斯平滑"""
    window = int(sigma * 3) * 2 + 1
    kernel = []
    for i in range(-window // 2, window // 2 + 1):
        weight = math.exp(-(i**2) / (2 * sigma**2))
        kernel.append(weight)
    kernel_sum = sum(kernel)

    smoothed = []
    for i in range(len(data)):
        avg_x = 0
        avg_y = 0
        for j, w in enumerate(kernel):
            idx = max(0, min(len(data) - 1, i + j - window // 2))
            avg_x += data[idx][0] * w
            avg_y += data[idx][1] * w
        smoothed.append([avg_x / kernel_sum, avg_y / kernel_sum])

    return smoothed
```

### 4.2 平滑参数选择

| 场景 | sigma/window | 效果 |
|------|-------------|------|
| 仅去高频抖动 | 1~3 | 保留大部分运动 |
| 去除手持抖动 | 3~7 | 平滑手持感 |
| 保留缓慢运动 | 7~15 | 去除所有快速运动 |
| 完全锁定 | 30+ | 画面静止 |

### 4.3 分段平滑

对于运动模式变化的镜头，可分段平滑：

```python
# 伪代码：分段平滑
def分段平滑(track_data, segments):
    """
    segments: [(start, end, smoothness), ...]
    """
    result = []
    for start, end, smoothness in segments:
        segment_data = track_data[start:end]
        smoothed = smooth_data(segment_data, smoothness)
        result.extend(smoothed)
    return result
```

---

## 五、反向跟踪应用

### 5.1 反向跟踪原理

反向跟踪是将跟踪数据反向应用的技术。稳定化是反向跟踪的一种应用，但反向跟踪还有更多用途：

| 应用 | 说明 |
|------|------|
| 稳定化 | 反向应用摄像机运动，使画面稳定 |
| 元素粘贴 | 正向应用运动，使元素跟随目标 |
| 运动匹配 | 匹配两段素材的运动 |
| 偏移修正 | 反向应用偏移，修正跟踪误差 |

### 5.2 元素粘贴

将一个元素"粘贴"到运动物体上：

```python
# 跟踪目标物体的运动
track.property("trackType").setValue("planar", 0)
track.property("motionModel").setValue("perspective", 0)

# 将跟踪数据正向应用到目标元素
# （通过 UI 的 "Apply Track" 功能实现）
```

### 5.3 运动匹配

匹配两段素材的运动，使它们看起来像同一镜头：

```python
# 1. 跟踪素材 A 的运动
track_a = Node("TrackerNode")
track_a.property("trackType").setValue("planar", 0)

# 2. 跟踪素材 B 的运动
track_b = Node("TrackerNode")
track_b.property("trackType").setValue("planar", 0)

# 3. 计算 A 到 B 的变换差
# 4. 将差值应用到素材 B
```

### 5.4 偏移修正

修正跟踪数据的系统性偏移：

```python
# 假设检测到跟踪数据有整体偏移
def apply_offset_correction(track_data, offset):
    """应用偏移修正"""
    corrected = []
    for point in track_data:
        corrected.append([
            point[0] - offset[0],
            point[1] - offset[1]
        ])
    return corrected
```

---

## 六、稳定化工作流

### 6.1 完整稳定化脚本

```python
from fx import *

# 项目初始化
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Stabilization"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/handheld.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 跟踪节点（跟踪静态参考点）
track = Node("TrackerNode")
track.label = "Stab_Reference"
track.property("trackType").setValue("point", 0)
track.property("searchArea").setValue(21, 0)
track.property("accuracy").setValue("high", 0)
track.property("patternSize").setValue(11, 0)
session.addNode(track)

# 稳定化节点
stab = Node("StabilizeNode")
stab.label = "Stabilizer"
stab.property("stabilizeMode").setValue("positionRotation", 0)
stab.property("referenceFrame").setValue(0, 0)
stab.property("smoothRadius").setValue(10, 0)
stab.property("borderMode").setValue("scale", 0)
stab.property("scale").setValue(1.05, 0)
stab.property("jitterThreshold").setValue(0.5, 0)
session.addNode(stab)

# 输出节点
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/stabilized_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

# 连接节点
src.outputs[0].connect(track.inputs[0])
track.outputs[0].connect(stab.inputs[0])
stab.outputs[0].connect(out_node.inputs[0])

print("[SILHOUETTE] Stabilization pipeline ready")
```

### 6.2 工作流步骤

1. **分析镜头**：确定抖动类型和参考点位置
2. **选择参考点**：选择画面中本应静止的静态点
3. **跟踪参考点**：执行跟踪，验证质量
4. **设置稳定参数**：选择稳定模式和平滑半径
5. **预览稳定效果**：检查是否满足需求
6. **调整参数**：必要时迭代调整
7. **处理边缘**：设置边缘处理模式
8. **渲染输出**：生成稳定后的素材

### 6.3 参考点选择

**优质参考点特征**：
- 静态物体上的特征点
- 高对比度、清晰锐利
- 全帧可见（不被遮挡）
- 远离画面边缘（避免被裁剪）

**避免的参考点**：
- 运动物体上的点
- 受阴影影响的点
- 高光反射点
- 画面边缘的点

---

## 七、高级技巧

### 7.1 多点稳定

使用多个参考点提高稳定质量：

```python
# 多点稳定（统计平均）
stab.property("stabilizeMode").setValue("multiPoint", 0)
# 多点稳定通过平均多个参考点的运动，提高稳定性
```

### 7.2 选择性稳定

仅对画面某区域稳定：

1. 创建 Roto 遮罩限定稳定区域
2. 稳定化节点应用遮罩
3. 仅遮罩内画面稳定

### 7.3 双向稳定

对于从中间帧开始的稳定：

```python
stab.property("referenceFrame").setValue(60, 0)  # 中间帧为参考
```

### 7.4 嵌套稳定

对于复杂抖动，可使用多级稳定：

```
原始素材 → 一级稳定（去高频抖动）→ 二级稳定（去低频漂移）→ 输出
```

### 7.5 稳定+反向应用

1. 稳定原始素材
2. 在稳定素材上进行修复
3. 反向应用稳定变换，恢复原始运动

```python
# 工作流：
# 1. 跟踪 → 稳定化 → 修复 → 反向稳定 → 输出
# 这样可以在稳定的画面上进行精细修复
```

---

## 八、故障排查

### 8.1 稳定效果不佳

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 仍有抖动 | 平滑半径过小 | 增大 smoothRadius |
| 运动过度平滑 | 平滑半径过大 | 减小 smoothRadius |
| 画面抖动加剧 | 参考点选择错误 | 选择真正的静态点 |
| 边缘出现黑边 | 缩放不足 | 增大 scale 或切换裁剪模式 |

### 8.2 参考点丢失

**原因**：参考点被遮挡或移出画面

**解决方案**：
- 选择全帧可见的点
- 使用多点稳定（单点丢失不影响）
- 分段稳定，每段使用不同参考点

### 8.3 稳定后画面不自然

**原因**：过度稳定或保留运动不当

**解决方案**：
```python
# 适度平滑，保留部分手持感
stab.property("smoothRadius").setValue(8, 0)
stab.property("jitterThreshold").setValue(1.0, 0)  # 仅去除明显抖动
```

### 8.4 性能优化

- 预览阶段使用低精度跟踪
- 分段处理长序列
- 使用代理素材进行参数调整
- 最终渲染时切换高精度

### 8.5 质量检查清单

- [ ] 参考点选择合理（静态、清晰、全帧可见）
- [ ] 跟踪质量验证（无丢失、无漂移）
- [ ] 稳定模式匹配抖动类型
- [ ] 平滑半径设置合理
- [ ] 边缘处理得当（无黑边）
- [ ] 全帧回放检查稳定效果
- [ ] 保留运动的程度符合需求
- [ ] 输出素材质量验证

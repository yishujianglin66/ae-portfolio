# Silhouette 点跟踪与多点跟踪

> 分类: 跟踪技术专题
> 更新日期: 2026-07-11
> 概述: PointTracker节点深度解析，涵盖单点/多点跟踪、参考帧选择、跟踪稳定性优化与多点数据融合。

## 目录
1. [PointTracker 节点概述](#一pointtracker-节点概述)
2. [单点跟踪](#二单点跟踪)
3. [多点跟踪](#三多点跟踪)
4. [参考帧选择策略](#四参考帧选择策略)
5. [跟踪稳定性优化](#五跟踪稳定性优化)
6. [多点数据融合](#六多点数据融合)
7. [应用场景](#七应用场景)
8. [故障排查](#八故障排查)

---

## 一、PointTracker 节点概述

### 1.1 节点定位

PointTracker（点跟踪器）基于单点特征匹配算法，对图像中具有显著特征的像素点进行逐帧跟踪，输出该点在每帧中的二维坐标。点跟踪是跟踪体系中最基础也最灵活的形式，广泛应用于跟踪点放置、运动分析、稳定化参考点采集等场景。

| 特性 | 说明 |
|------|------|
| 算法基础 | 单点特征匹配（NCC/SAD） |
| 输出数据 | 二维坐标 [x, y] |
| 单点精度 | 亚像素级（accuracy=high时） |
| 多点支持 | 原生支持任意数量点 |
| 计算开销 | 低（单点）~ 中（多点） |

### 1.2 节点端口

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | source | 源视频输入 |

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | output | 跟踪数据输出（含所有点坐标） |

### 1.3 核心属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| trackType | string | "point" | 跟踪类型，点跟踪固定为 "point" |
| searchArea | int | 21 | 搜索区域大小 |
| accuracy | string | "medium" | 精度等级 |
| patternSize | int | 11 | 特征块大小 |
| keyframes | int | 1 | 关键帧间隔 |
| forward | bool | true | 向前跟踪 |
| backward | bool | false | 向后跟踪 |
| autoKeyframe | bool | true | 自动关键帧 |
| pointCount | int | 0 | 已定义跟踪点数量 |

### 1.4 与平面跟踪的对比

| 维度 | PointTracker | PlanarTracker |
|------|--------------|---------------|
| 跟踪对象 | 离散点 | 连续区域 |
| 输出自由度 | 2 DOF（位置） | 2~8 DOF |
| 适用场景 | 跟踪点、运动分析 | 平面物体整体运动 |
| 遮挡容忍度 | 低 | 中~高 |
| 计算速度 | 快 | 中 |

---

## 二、单点跟踪

### 2.1 单点跟踪适用场景

- **跟踪点放置**：为后续合成放置跟踪点
- **稳定化参考**：采集稳定化所需的参考点
- **运动测量**：测量特定点的运动轨迹
- **威亚去除标记**：跟踪威亚端点
- **简单位置驱动**：驱动简单位置动画

### 2.2 单点跟踪脚本

```python
from fx import *

# 项目初始化
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Single_Point_Track"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/marker.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 单点跟踪节点
track = Node("TrackerNode")
track.label = "Single_Point"
track.property("trackType").setValue("point", 0)
track.property("searchArea").setValue(21, 0)
track.property("accuracy").setValue("medium", 0)
track.property("patternSize").setValue(11, 0)
track.property("keyframes").setValue(1, 0)
track.property("forward").setValue(True, 0)
track.property("backward").setValue(False, 0)
track.property("autoKeyframe").setValue(True, 0)
session.addNode(track)

src.outputs[0].connect(track.inputs[0])

print("[SILHOUETTE] Single point tracker ready")
print("[SILHOUETTE] 请在 Viewer 中放置跟踪点")
```

### 2.3 单点参数选择

| 场景 | searchArea | patternSize | accuracy |
|------|-----------|-------------|----------|
| 静态标记点 | 15 | 7 | medium |
| 移动标记点 | 21 | 11 | medium |
| 快速运动点 | 31 | 11 | high |
| 自然特征点 | 21 | 15 | high |

### 2.4 单点精度优化

```python
# 高精度单点跟踪（亚像素级）
track.property("accuracy").setValue("high", 0)
track.property("patternSize").setValue(11, 0)
track.property("searchArea").setValue(21, 0)
```

**精度技巧**：
- patternSize 应与特征点大小匹配
- accuracy=high 启用亚像素插值
- 选择具有强对比度的特征点
- 避免选择边缘点（易产生方向歧义）

---

## 三、多点跟踪

### 3.1 多点跟踪优势

多点跟踪通过同时跟踪多个特征点，可获得：
- **冗余性**：单点丢失不影响整体
- **变换推导**：通过多点组合推导旋转、缩放、透视
- **运动分析**：分析物体各部分的相对运动
- **稳定化基础**：提供多点稳定化所需数据

### 3.2 多点跟踪脚本

```python
from fx import *

proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Multi_Point_Track"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 多点跟踪节点
track = Node("TrackerNode")
track.label = "Multi_Point_4"
track.property("trackType").setValue("point", 0)
track.property("searchArea").setValue(25, 0)  # 多点稍大搜索区
track.property("accuracy").setValue("high", 0)
track.property("patternSize").setValue(11, 0)
track.property("keyframes").setValue(1, 0)
track.property("forward").setValue(True, 0)
track.property("backward").setValue(True, 0)
track.property("autoKeyframe").setValue(True, 0)
session.addNode(track)

src.outputs[0].connect(track.inputs[0])

# 多点配置说明（实际通过UI放置）
# 推荐四点配置：
# P1: 左上角特征点
# P2: 右上角特征点
# P3: 右下角特征点
# P4: 左下角特征点
# 形成四边形覆盖目标区域

print("[SILHOUETTE] Multi-point tracker ready (4 points recommended)")
```

### 3.3 多点布局策略

**策略一：四点矩形布局**
适用于平面物体整体跟踪，四点形成矩形覆盖目标区域。
- 优势：可直接推导透视变换
- 应用：屏幕替换、招牌替换、墙面贴图

**策略二：三点三角形布局**
适用于刚体跟踪，三点形成三角形。
- 优势：最少点数推导仿射变换
- 应用：刚体旋转跟踪、简单稳定化

**策略三：多点散布布局**
适用于复杂运动分析，多点散布在目标物体各处。
- 优势：捕捉局部运动差异
- 应用：人物表情跟踪、衣物运动分析

**策略四：特征点+辅助点**
主特征点跟踪目标，辅助点监控周边运动。
- 优势：增强鲁棒性，辅助判断遮挡
- 应用：复杂场景跟踪、遮挡检测

### 3.4 多点数量建议

| 应用 | 推荐点数 | 说明 |
|------|----------|------|
| 简单稳定化 | 1~2 | 单点稳定位置，双点稳定+旋转 |
| 仿射变换 | 3 | 三点推导仿射 |
| 透视变换 | 4+ | 四点推导透视 |
| 复杂运动分析 | 6~12 | 多点捕捉细节运动 |
| 摄像机解算 | 8+ | 提供解算所需特征点 |

---

## 四、参考帧选择策略

### 4.1 参考帧的重要性

参考帧（Reference Frame）是跟踪的起始帧，该帧上的特征点位置和外观作为后续匹配的基准。参考帧选择直接影响整个跟踪序列的质量。

### 4.2 选择原则

**原则一：特征最明显**
选择目标特征在该帧最清晰、最锐利、对比度最高的状态。

**原则二：运动中点**
对于双向跟踪，选择镜头中间帧作为参考，减少最大跟踪距离。

**原则三：避免遮挡帧**
确保参考帧上所有跟踪点都完全可见，无遮挡。

**原则四：避免运动模糊帧**
选择运动模糊最小的帧作为参考。

**原则五：代表性强**
参考帧的特征点外观应能代表整个序列的"平均"状态。

### 4.3 参考帧切换技巧

当单一参考帧无法覆盖整个序列时，可采用"分段参考"策略：

```
序列：[0]----[30]----[60]----[90]----[120]
参考帧：  0      30      60      90
段：     段1     段2     段3     段4
```

每段使用自己的参考帧独立跟踪，最后合并数据，在接缝处检查一致性。

### 4.4 关键帧作为次级参考

在跟踪过程中手动添加关键帧，相当于在问题帧重置"局部参考"：

```python
# 假设在第50帧手动修正点位置
# 该关键帧即成为后续跟踪的次级参考
track.property("autoKeyframe").setValue(True, 0)
# autoKeyframe 启用时，系统会在精度下降时自动添加关键帧
```

---

## 五、跟踪稳定性优化

### 5.1 特征点选择优化

**优质特征点特征**：
- 高对比度（明暗交界、色彩突变）
- 角点（L型、T型、X型交界）
- 孤立特征（周围无相似特征）
- 稳定外观（不随时间变化）
- 适中间距（与边界保持距离）

**避免的特征点**：
- 边缘上的点（易沿边缘滑动）
- 重复纹理中的点（易匹配到错误位置）
- 高光点（易随光照变化）
- 阴影中的点（易随阴影变化）
- 运动物体上的点（除非跟踪运动物体）

### 5.2 参数稳定性优化

```python
# 稳定性优先配置
def apply_stable_track(track):
    track.property("trackType").setValue("point", 0)
    track.property("searchArea").setValue(25, 0)
    track.property("accuracy").setValue("high", 0)
    track.property("patternSize").setValue(15, 0)  # 较大模板更稳定
    track.property("keyframes").setValue(1, 0)
    track.property("autoKeyframe").setValue(True, 0)
```

### 5.3 抖动抑制

点跟踪可能出现高频抖动，特别是在低纹理区域：

**方法一：增大 patternSize**
```python
track.property("patternSize").setValue(15, 0)
```

**方法二：后处理平滑**
对跟踪数据应用移动平均或高斯平滑：
```python
# 伪代码：跟踪数据后处理
def smooth_track_data(points, window=3):
    smoothed = []
    for i in range(len(points)):
        start = max(0, i - window)
        end = min(len(points), i + window + 1)
        avg_x = sum(p[0] for p in points[start:end]) / (end - start)
        avg_y = sum(p[1] for p in points[start:end]) / (end - start)
        smoothed.append([avg_x, avg_y])
    return smoothed
```

**方法三：降低 accuracy**
accuracy=medium 比 high 在某些场景下更稳定（容忍小范围抖动）。

### 5.4 漂移抑制

漂移是指跟踪点逐渐偏离真实位置的现象：

**原因**：
- 每帧匹配误差累积
- 特征点外观缓慢变化
- patternSize 过小

**对策**：
- 定期手动关键帧修正
- 使用 autoKeyframe 自动检测精度下降
- 增大 patternSize 增强匹配稳定性
- 考虑使用平面跟踪替代（漂移更小）

---

## 六、多点数据融合

### 6.1 从多点推导变换

多点跟踪的核心价值在于从多个点坐标推导整体变换：

**两点 → 平移+旋转**
```python
# 两点推导平移和旋转
def two_point_transform(p1_start, p2_start, p1_end, p2_end):
    # 平移：中点位移
    cx_start = (p1_start[0] + p2_start[0]) / 2
    cy_start = (p1_start[1] + p2_start[1]) / 2
    cx_end = (p1_end[0] + p2_end[0]) / 2
    cy_end = (p1_end[1] + p2_end[1]) / 2
    translate = [cx_end - cx_start, cy_end - cy_start]

    # 旋转：两点连线角度变化
    import math
    angle_start = math.atan2(p2_start[1] - p1_start[1], p2_start[0] - p1_start[0])
    angle_end = math.atan2(p2_end[1] - p1_end[1], p2_end[0] - p1_end[0])
    rotate = angle_end - angle_start

    return translate, rotate
```

**三点 → 仿射变换**
三点可推导完整的仿射变换（平移+旋转+缩放+剪切）。

**四点 → 透视变换**
四点可推导完整的透视变换（8 DOF）。

### 6.2 多点平均

对于冗余多点（如6点跟踪一个平面），可采用平均策略提高稳定性：

```python
# 伪代码：多点平均位置
def average_points(points_list):
    n = len(points_list)
    avg_x = sum(p[0] for p in points_list) / n
    avg_y = sum(p[1] for p in points_list) / n
    return [avg_x, avg_y]
```

### 6.3 异常点剔除

当某个点跟踪失败时，通过其他点的一致性检测并剔除：

```python
# 伪代码：异常点检测
def detect_outlier(points, threshold=10.0):
    # 计算各点与平均位置的距离
    avg = average_points(points)
    distances = [((p[0]-avg[0])**2 + (p[1]-avg[1])**2)**0.5 for p in points]
    max_dist = max(distances)
    if max_dist > threshold:
        outlier_idx = distances.index(max_dist)
        return outlier_idx  # 返回异常点索引
    return -1  # 无异常
```

---

## 七、应用场景

### 7.1 稳定化参考点

```python
# 单点稳定化：跟踪一个静态参考点
track.property("trackType").setValue("point", 0)
track.property("accuracy").setValue("high", 0)
# 该点应选择场景中本应静止但随镜头抖动的点
```

### 7.2 屏幕替换四点跟踪

```python
# 四点跟踪屏幕四角
track.property("trackType").setValue("point", 0)
track.property("searchArea").setValue(25, 0)
track.property("accuracy").setValue("high", 0)
# 在屏幕四角各放置一个跟踪点
```

### 7.3 威亚端点跟踪

```python
# 跟踪威亚两端
track.property("trackType").setValue("point", 0)
track.property("patternSize").setValue(7, 0)  # 小模板适应细线
track.property("searchArea").setValue(31, 0)  # 大搜索区适应快速运动
```

### 7.4 运动分析

```python
# 多点散布分析人物面部运动
track.property("trackType").setValue("point", 0)
track.property("accuracy").setValue("high", 0)
# 在眉毛、眼角、嘴角等关键点放置跟踪点
```

---

## 八、故障排查

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 单点丢失 | 特征不明显或遮挡 | 选择更强特征点，增大 searchArea |
| 多点中部分丢失 | 个别点特征弱 | 剔除失败点，补充新点 |
| 点沿边缘滑动 | 选择了边缘点 | 改选角点或孤立特征 |
| 高频抖动 | patternSize 过小 | 增大 patternSize |
| 持续漂移 | 误差累积 | 定期手动关键帧 |
| 双向跟踪不一致 | 两方向误差 | 以一向为主，手动修正接缝 |

### 8.2 跟踪点失效处理

当一个跟踪点完全失效时：

1. **删除失效点**：从跟踪数据中移除
2. **补充新点**：在同位置放置新跟踪点
3. **分段跟踪**：失效前用原点，失效后用新点
4. **插值填补**：对失效段进行位置插值
5. **借用其他点**：通过其他稳定点推导失效点位置

### 8.3 质量评估

跟踪完成后逐项检查：

- [ ] 所有点在整个序列中保持锁定
- [ ] 无明显抖动或跳变
- [ ] 多点间相对关系合理
- [ ] 边缘帧跟踪稳定
- [ ] 在目标应用中验证数据正确性

### 8.4 数据导出

```python
# 多点跟踪数据结构
track_data = {
    "version": "2026.0.2",
    "track_type": "point",
    "point_count": 4,
    "fps": 24.0,
    "points": [
        {
            "id": "P1",
            "label": "TopLeft",
            "frames": [
                {"frame": 0, "x": 100.0, "y": 200.0},
                {"frame": 1, "x": 101.2, "y": 200.5}
            ]
        }
    ]
}
```

点跟踪数据可导出为：
- JSON（通用）
- AE 关键帧（位置）
- NUKE track 文件（.nk）
- Boujou/3DEqualizer 格式（摄像机解算用）

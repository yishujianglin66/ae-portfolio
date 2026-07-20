# Silhouette 平面跟踪完全指南

> 分类: 跟踪技术专题
> 更新日期: 2026-07-11
> 概述: PlanarTracker节点深度解析，涵盖跟踪区域选择、精度参数调优、失败处理与高质量跟踪交付的完整工作流。

## 目录
1. [PlanarTracker 节点概述](#一planartracker-节点概述)
2. [跟踪区域选择策略](#二跟踪区域选择策略)
3. [精度参数详解](#三精度参数详解)
4. [跟踪流程与执行](#四跟踪流程与执行)
5. [失败处理与诊断](#五失败处理与诊断)
6. [高级跟踪技巧](#六高级跟踪技巧)
7. [导出与应用](#七导出与应用)
8. [最佳实践](#八最佳实践)

---

## 一、PlanarTracker 节点概述

### 1.1 节点定位

PlanarTracker（平面跟踪器）是 Silhouette 跟踪体系的核心节点，基于二维平面像素匹配算法，对一个平面区域的整体运动进行跟踪，输出变换矩阵（位置/旋转/缩放/透视），用于驱动 Roto、Paint、稳定化或导出到第三方合成软件。

与 PointTracker（点跟踪）的差异：

| 维度 | PlanarTracker | PointTracker |
|------|---------------|--------------|
| 算法基础 | 区域像素模板匹配 | 单点特征匹配 |
| 输出数据 | 4点透视/变换矩阵 | 单点坐标 |
| 抗遮挡能力 | 强（区域冗余） | 弱（点丢失即失败） |
| 适用场景 | 平面物体、屏幕、墙面、地面 | 标记点、特征点、跟踪点 |
| 精度可控性 | 高（多参数可调） | 中（参数较少） |

### 1.2 节点端口

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | source | 源视频输入 |

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | output | 跟踪数据输出（含变换矩阵） |

### 1.3 核心属性总览

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| trackType | string | "planar" | 跟踪类型，平面跟踪固定为 "planar" |
| searchArea | int | 21 | 搜索区域大小（像素） |
| accuracy | string | "medium" | 精度等级：low/medium/high |
| patternSize | int | 11 | 模板（特征块）大小 |
| keyframes | int | 1 | 关键帧间隔 |
| forward | bool | true | 向前跟踪 |
| backward | bool | false | 向后跟踪 |
| autoKeyframe | bool | true | 自动添加关键帧 |
| motionModel | string | "perspective" | 运动模型：translation/affine/perspective |
| occlusion | string | "none" | 遮挡处理策略 |

---

## 二、跟踪区域选择策略

跟踪区域是 PlanarTracker 成败的关键。区域选择不当，再精细的参数也无法挽救。

### 2.1 区域选择原则

**原则一：选择真实平面**
平面跟踪假设跟踪区域是物理平面或近似平面。选择有明显弧度、深度变化的区域会导致跟踪漂移。

- ✅ 适合：墙面、地面、桌面、屏幕、车身平整处
- ⚠️ 谨慎：人脸（近似平面但有曲度）、衣物平整处
- ❌ 避免：树木、波浪、人物动作幅度大的区域

**原则二：纹理丰富**
区域内应有足够多的稳定纹理特征（边缘、斑点、对比变化），纯色区域无法跟踪。

**原则三：避免动态区域**
区域内的像素应仅由摄像机运动产生变化，不应有物体自身运动（如水面波纹、行人走动）。

**原则四：区域大小适中**
- 过小：信息不足，易丢失
- 过大：包含非平面区域，引入误差
- 推荐：覆盖目标平面的 60%~90% 可见区域

### 2.2 形状选择

Silhouette 支持使用 X-Spline 或 Bezier 形状定义跟踪区域：

```python
from fx import *

# 创建平面跟踪节点
track = Node("TrackerNode")
track.label = "Planar_Wall"
track.property("trackType").setValue("planar", 0)
track.property("motionModel").setValue("perspective", 0)
session.addNode(track)

# 形状定义参考（实际通过 UI 绘制或 shape API 创建）
# 推荐使用 4~8 个控制点的封闭形状
```

### 2.3 多区域策略

对于复杂场景，可采用多区域跟踪策略：

| 策略 | 适用场景 | 注意事项 |
|------|----------|----------|
| 单区域主导 | 主要平面明显 | 区域内避免遮挡 |
| 主辅双区域 | 主区域可能被遮挡 | 辅助区域应在主区域遮挡时接管 |
| 多区域融合 | 多平面场景 | 各区域独立跟踪，分别应用 |

---

## 三、精度参数详解

### 3.1 searchArea（搜索区域）

搜索区域决定了在下一帧寻找匹配模板的像素范围。

| 值 | 行为 | 适用场景 |
|----|------|----------|
| 11~15 | 搜索范围小，速度快 | 慢速运动、稳定镜头 |
| 21（默认） | 平衡选择 | 大多数常规场景 |
| 31~41 | 搜索范围大，速度慢 | 快速运动、手持镜头 |

**调优原则**：searchArea 应大于相邻两帧间跟踪区域的最大位移。若运动过快导致 searchArea 需求过大，可考虑先做粗跟踪再精跟踪的两阶段策略。

```python
# 快速运动场景
track.property("searchArea").setValue(41, 0)

# 慢速稳定场景
track.property("searchArea").setValue(15, 0)
```

### 3.2 patternSize（模板大小）

模板大小定义了用于匹配的特征块尺寸。

| 值 | 行为 | 适用场景 |
|----|------|----------|
| 5~7 | 小模板，精确但易丢失 | 高频纹理、精细特征 |
| 11（默认） | 平衡选择 | 常规纹理 |
| 15~21 | 大模板，鲁棒但粗糙 | 低频纹理、大面积区域 |

**注意**：patternSize 过小会导致在纹理稀疏区域跟踪抖动；过大会导致跟踪结果"平均化"，丢失精细运动。

### 3.3 accuracy（精度等级）

| 等级 | 内部行为 | 速度 | 精度 |
|------|----------|------|------|
| low | 粗粒度匹配 | 快 | 低 |
| medium | 标准匹配 | 中 | 中 |
| high | 细粒度匹配 + 亚像素优化 | 慢 | 高 |

```python
# 影视级高精度
track.property("accuracy").setValue("high", 0)

# 预览级快速跟踪
track.property("accuracy").setValue("low", 0)
```

### 3.4 motionModel（运动模型）

运动模型决定了跟踪输出的变换类型，必须与实际运动匹配。

| 模型 | 输出自由度 | 适用场景 |
|------|-----------|----------|
| translation | 平移（2 DOF） | 纯平移运动，如轨道镜头 |
| affine | 平移+旋转+缩放+剪切（6 DOF） | 平面旋转、缩放变化 |
| perspective | 透视变换（8 DOF） | 任意平面运动，含视角变化 |

**推荐**：除非确定场景无透视变化，否则默认使用 perspective 模型，避免模型不足导致跟踪误差。

### 3.5 参数组合预设

```python
# 预设一：影视级高精度
def apply_cinematic_high(track):
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(31, 0)
    track.property("accuracy").setValue("high", 0)
    track.property("patternSize").setValue(15, 0)
    track.property("motionModel").setValue("perspective", 0)
    track.property("keyframes").setValue(1, 0)

# 预设二：常规平衡
def apply_balanced(track):
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(21, 0)
    track.property("accuracy").setValue("medium", 0)
    track.property("patternSize").setValue(11, 0)
    track.property("motionModel").setValue("perspective", 0)
    track.property("keyframes").setValue(1, 0)

# 预设三：快速预览
def apply_preview(track):
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(15, 0)
    track.property("accuracy").setValue("low", 0)
    track.property("patternSize").setValue(7, 0)
    track.property("motionModel").setValue("affine", 0)
    track.property("keyframes").setValue(3, 0)
```

---

## 四、跟踪流程与执行

### 4.1 标准工作流

```
1. 创建 SourceNode 加载素材
2. 创建 TrackerNode 并连接
3. 设置 trackType = "planar"
4. 选择 motionModel
5. 在 Viewer 中绘制跟踪形状
6. 设置参考帧（通常是运动起始帧）
7. 配置精度参数
8. 执行向前/向后跟踪
9. 检查跟踪结果
10. 必要时手动修正关键帧
11. 导出跟踪数据
```

### 4.2 完整脚本示例

```python
from fx import *

# 项目与会话初始化
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Planar_Track_Cinematic"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 平面跟踪节点
track = Node("TrackerNode")
track.label = "Planar_HighPrecision"
track.property("trackType").setValue("planar", 0)
track.property("searchArea").setValue(31, 0)
track.property("accuracy").setValue("high", 0)
track.property("patternSize").setValue(15, 0)
track.property("motionModel").setValue("perspective", 0)
track.property("keyframes").setValue(1, 0)
track.property("forward").setValue(True, 0)
track.property("backward").setValue(True, 0)
track.property("autoKeyframe").setValue(True, 0)
session.addNode(track)

src.outputs[0].connect(track.inputs[0])

print("[SILHOUETTE] Planar tracker ready for shape drawing")
```

### 4.3 双向跟踪策略

对于从中间帧开始跟踪的场景，启用双向跟踪：

```python
track.property("forward").setValue(True, 0)
track.property("backward").setValue(True, 0)
```

**注意**：双向跟踪在两方向相遇时可能产生不一致，需检查接缝处并在必要时手动修正。

---

## 五、失败处理与诊断

### 5.1 常见失败模式

| 失败模式 | 现象 | 可能原因 |
|----------|------|----------|
| 完全丢失 | 跟踪区域跳到错误位置 | 特征不足、searchArea 过小 |
| 持续漂移 | 跟踪区域缓慢偏移 | 非平面区域、运动模型错误 |
| 抖动 | 跟踪结果高频抖动 | patternSize 过小、噪声过大 |
| 突然跳变 | 某一帧后位置突变 | 遮挡、运动模糊、亮度突变 |
| 透视错误 | 4点形状严重扭曲 | 运动模型与实际不匹配 |

### 5.2 诊断流程

```
1. 检查跟踪区域是否覆盖正确平面
2. 检查 motionModel 是否匹配场景
3. 逐帧回放跟踪结果，定位问题帧
4. 在问题帧检查：
   - 是否有遮挡
   - 是否有运动模糊
   - 是否有亮度/色彩突变
5. 根据诊断结果调整参数或手动修正
```

### 5.3 修复策略

**策略一：增大搜索区域**
```python
track.property("searchArea").setValue(41, 0)
```

**策略二：切换运动模型**
当透视模型失败时，尝试降级到 affine：
```python
track.property("motionModel").setValue("affine", 0)
```

**策略三：手动关键帧修正**
在问题帧手动调整跟踪形状位置，让跟踪器从修正点重新开始。

**策略四：分段跟踪**
将镜头按遮挡/模糊分布切分为多段，每段独立跟踪，最后合并。

**策略五：替换跟踪区域**
当原区域完全失效时，选择同平面的另一区域重新跟踪，并通过偏移量传递到目标位置。

---

## 六、高级跟踪技巧

### 6.1 两阶段跟踪

对快速运动镜头采用"粗+精"两阶段策略：

```python
# 阶段一：粗跟踪（大 searchArea，低精度）
track.property("searchArea").setValue(41, 0)
track.property("accuracy").setValue("low", 0)
track.property("patternSize").setValue(7, 0)

# 阶段二：精跟踪（在粗跟踪基础上，小 searchArea，高精度）
track.property("searchArea").setValue(15, 0)
track.property("accuracy").setValue("high", 0)
track.property("patternSize").setValue(15, 0)
```

### 6.2 遮挡处理

当跟踪区域被部分遮挡时：

1. 缩小跟踪区域，避开遮挡部分
2. 启用 occlusion 处理（如可用）
3. 在遮挡帧前后分段跟踪
4. 使用辅助区域在遮挡期间接管

### 6.3 运动模糊场景

运动模糊会降低模板匹配精度：

- 增大 patternSize 以包含更多模糊信息
- 降低 accuracy 等级以容忍模糊
- 在模糊最严重的帧手动设置关键帧
- 考虑使用光流辅助跟踪

### 6.4 多通道跟踪

对色彩复杂的场景，可在特定通道上跟踪：

- 纹理明显的通道（如绿幕场景的 G 通道之外的 R/B）
- 亮度通道（避免色彩干扰）
- 差值通道（增强运动特征）

---

## 七、导出与应用

### 7.1 跟踪数据结构

```python
tracking_data = {
    "version": "2026.0.2",
    "track_type": "planar",
    "motion_model": "perspective",
    "source": "D:/footage/scene.mov",
    "fps": 24.0,
    "frame_range": [0, 120],
    "frames": [
        {
            "frame": 0,
            "transform": {
                "translate": [0.0, 0.0],
                "rotate": 0.0,
                "scale": [1.0, 1.0],
                "perspective": [[1,0,0],[0,1,0],[0,0,1]]
            },
            "corners": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        }
    ]
}
```

### 7.2 应用到 Roto

平面跟踪结果可直接驱动 Roto 形状：

```python
# Roto 节点接收跟踪数据
roto = Node("RotoNode")
roto.label = "Tracked_Roto"
session.addNode(roto)

# 通过跟踪数据驱动形状变换
# （实际操作中通过 UI 的 "Link to Tracker" 功能实现）
```

### 7.3 应用到 Paint

Paint 跟踪修复依赖平面跟踪数据：

```python
paint = Node("PaintNode")
paint.label = "Tracked_Paint"
paint.property("mode").setValue("clone", 0)
session.addNode(paint)

# Paint 节点使用跟踪数据自动传播修复笔触
```

---

## 八、最佳实践

### 8.1 参数选择决策树

```
镜头运动快速吗？
├── 是 → searchArea = 31~41
│        └── 需要高精度吗？
│            ├── 是 → accuracy = high, patternSize = 15
│            └── 否 → accuracy = medium, patternSize = 11
└── 否 → searchArea = 15~21
         └── 纹理丰富吗？
             ├── 是 → patternSize = 7~11
             └── 否 → patternSize = 15~21
```

### 8.2 质量检查清单

- [ ] 跟踪区域覆盖真实平面
- [ ] motionModel 与场景运动匹配
- [ ] 全帧范围回放检查无漂移
- [ ] 遮挡帧处理得当
- [ ] 边缘帧跟踪稳定
- [ ] 导出数据格式正确
- [ ] 在目标软件中验证应用效果

### 8.3 性能优化

- 预览阶段使用低精度快速迭代
- 确定参数后再切换到高精度最终跟踪
- 长镜头分段跟踪并行处理
- 关闭不必要的双向跟踪（仅在需要时启用 backward）

### 8.4 交付建议

- 提供原始跟踪数据与修正后版本
- 标注跟踪区域截图供审阅
- 记录关键参数与决策原因
- 保留中间关键帧用于后续微调

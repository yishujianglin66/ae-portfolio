# Silhouette 节点类型完全参数库

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 详细列出 Silhouette fx 模块中所有节点类型、属性参数、端口映射与示例代码

## 目录

- [一、节点系统总览](#一节点系统总览)
- [二、SourceNode 源节点](#二sourcenode-源节点)
- [三、RotoNode Roto遮罩节点](#三rotonode-roto遮罩节点)
- [四、TrackerNode 跟踪节点](#四trackernode-跟踪节点)
- [五、PaintNode Paint修复节点](#五paintnode-paint修复节点)
- [六、OutputNode 输出节点](#六outputnode-输出节点)
- [七、CompositeNode 合成节点](#七compositenode-合成节点)
- [八、ColorNode 颜色节点](#八colornode-颜色节点)
- [九、FilterNode 滤镜节点](#九filternode-滤镜节点)
- [十、MatteNode 遮罩节点](#十mattenode-遮罩节点)
- [十一、TransformNode 变换节点](#十一transformnode-变换节点)
- [十二、节点通用属性](#十二节点通用属性)
- [十三、最佳实践](#十三最佳实践)

---

## 一、节点系统总览

Silhouette 采用节点式工作流，所有处理通过节点连接成图（DAG）完成。

| 节点类型 | 中文名 | 主要用途 | 输入端口数 | 输出端口数 |
|----------|--------|----------|------------|------------|
| SourceNode | 源节点 | 加载媒体素材 | 0 | 1 |
| RotoNode | Roto遮罩节点 | 绘制遮罩形状 | 5 | 5 |
| TrackerNode | 跟踪节点 | 运动跟踪 | 1 | 1 |
| PaintNode | Paint修复节点 | 画笔修复 | 1 | 1 |
| OutputNode | 输出节点 | 渲染输出 | 1 | 0 |
| CompositeNode | 合成节点 | 图层合成 | 2 | 1 |
| ColorNode | 颜色节点 | 色彩校正 | 1 | 1 |
| FilterNode | 滤镜节点 | 模糊锐化 | 1 | 1 |
| MatteNode | 遮罩节点 | 生成遮罩 | 1 | 1 |
| TransformNode | 变换节点 | 几何变换 | 1 | 1 |

### 节点创建通用语法

```python
from fx import *

node = Node("RotoNode")
node.label = "MyRoto"
session.addNode(node)
```

### 节点连接通用语法

```python
# 将 source 的输出 0 连接到 roto 的输入 1
source.outputs[0].connect(roto.inputs[1])

# 断开连接
source.outputs[0].disconnect()
```

---

## 二、SourceNode 源节点

### 2.1 描述

加载视频、图像序列、EXR 等媒体素材作为节点图的输入源。是所有处理流程的起点。

### 2.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | - | - | 无输入端口 |
| 输出 | 0 | output | 主输出，提供原始媒体数据 |

### 2.3 属性参数

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| mediaPath | string | "" | 任意合法路径 | 媒体文件路径，支持 mov/exr/tiff/png 序列 |
| frameStart | int | 0 | 0 ~ 999999 | 起始帧号 |
| frameEnd | int | 100 | 1 ~ 999999 | 结束帧号 |
| frameRate | float | 24.0 | 1.0 ~ 120.0 | 帧率（fps） |
| loop | bool | false | true/false | 是否循环播放 |
| premultiplied | bool | false | true/false | 是否预乘 Alpha |
| colorSpace | string | "auto" | auto/sRGB/Linear/Rec709 | 颜色空间 |
| fieldOrder | string | "progressive" | progressive/upper/lower | 场序 |

### 2.4 示例代码

```python
from fx import *

src = Node("SourceNode")
src.label = "Footage"
src.property("mediaPath").setValue("D:/footage/scene_001.mov", 0)
src.property("frameRate").setValue(30.0, 0)
src.property("frameStart").setValue(0, 0)
src.property("frameEnd").setValue(240, 0)
src.property("colorSpace").setValue("sRGB", 0)
src.property("premultiplied").setValue(False, 0)
session.addNode(src)
```

---

## 三、RotoNode Roto遮罩节点

### 3.1 描述

Silhouette 的核心节点，用于绘制 X-Spline、Bezier 形状，生成 Alpha 遮罩。支持多形状叠加、运动模糊、边缘羽化等高级功能。

### 3.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | obey_matte | 遮罩服从（限制遮罩范围） |
| 输入 | 1 | foreground | **主输入，必须连接** |
| 输入 | 2 | background | 背景替换 |
| 输入 | 3 | occlusion | 遮挡层 |
| 输入 | 4 | data | 数据输入 |
| 输出 | 0 | output | 主输出（含 Alpha 通道） |
| 输出 | 1 | colorComp | 颜色合成 |
| 输出 | 2 | composite | 合成结果 |
| 输出 | 3 | channels | 通道数据 |
| 输出 | 4 | objects | 形状对象 |

### 3.3 属性参数

#### Alpha 与边缘

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| alpha.blur | float | 0.0 | 0.0 ~ 100.0 | 边缘模糊量 |
| alpha.invert | bool | false | true/false | 反转 Alpha |
| alpha.opacity | float | 1.0 | 0.0 ~ 1.0 | Alpha 不透明度 |
| antialias | float | 1.0 | 0.0 ~ 2.0 | 抗锯齿强度 |
| feather | float | 0.0 | 0.0 ~ 50.0 | 边缘羽化 |

#### 填充与描边

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| fill | bool | true | true/false | 是否填充 |
| fill.color | color | [1,1,1] | [0,0,0] ~ [1,1,1] | 填充颜色 |
| stroke | bool | false | true/false | 是否描边 |
| stroke.width | float | 1.0 | 0.0 ~ 20.0 | 描边宽度 |
| stroke.color | color | [1,1,1] | [0,0,0] ~ [1,1,1] | 描边颜色 |

#### 遮罩模式

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| matte.mode | string | "alpha" | alpha/luma/replace | 遮罩模式 |
| matte.invert | bool | false | true/false | 反转遮罩 |
| matte.combine | string | "over" | over/add/subtract/intersect/min/max | 遮罩组合方式 |

#### 运动模糊

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| motionBlur | bool | false | true/false | 启用运动模糊 |
| motionBlur.shutter | float | 0.5 | 0.0 ~ 2.0 | 快门时间（180°=0.5） |
| motionBlur.samples | int | 8 | 1 ~ 64 | 采样次数 |
| motionBlur.offset | float | 0.0 | -1.0 ~ 1.0 | 快门偏移 |

### 3.4 示例代码

```python
from fx import *

roto = Node("RotoNode")
roto.label = "Character_Roto"
roto.property("alpha.blur").setValue(0.3, 0)
roto.property("antialias").setValue(1.0, 0)
roto.property("fill").setValue(True, 0)
roto.property("matte.mode").setValue("alpha", 0)
roto.property("motionBlur").setValue(True, 0)
roto.property("motionBlur.shutter").setValue(0.7, 0)
roto.property("motionBlur.samples").setValue(16, 0)
session.addNode(roto)

# 连接主输入
src.outputs[0].connect(roto.inputs[1])
```

---

## 四、TrackerNode 跟踪节点

### 4.1 描述

提供平面跟踪、点跟踪、Paint 跟踪三种模式，用于获取画面中物体的运动数据。

### 4.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | source | 源输入 |
| 输出 | 0 | output | 跟踪数据输出 |

### 4.3 属性参数

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| trackType | string | "planar" | planar/point/paint-track | 跟踪类型 |
| searchArea | int | 21 | 7 ~ 101 | 搜索区域大小（像素） |
| accuracy | string | "medium" | low/medium/high | 跟踪精度 |
| patternSize | int | 11 | 5 ~ 51 | 模板匹配大小 |
| keyframes | int | 1 | 1 ~ 60 | 关键帧间隔 |
| forward | bool | true | true/false | 向前跟踪 |
| backward | bool | false | true/false | 向后跟踪 |
| autoKeyframe | bool | true | true/false | 自动关键帧 |
| motionModel | string | "affine" | translation/similarity/affine/perspective | 运动模型 |
| robustness | float | 0.5 | 0.0 ~ 1.0 | 鲁棒性阈值 |
| maxError | float | 5.0 | 0.0 ~ 50.0 | 最大允许误差 |

### 4.4 跟踪类型说明

| 类型 | 适用场景 | 精度 | 速度 |
|------|----------|------|------|
| planar | 平面物体、墙面、地面 | 高 | 中 |
| point | 点状特征、标记点 | 中 | 快 |
| paint-track | Paint 笔触跟随 | 中 | 慢 |

### 4.5 示例代码

```python
from fx import *

tracker = Node("TrackerNode")
tracker.label = "Face_Track"
tracker.property("trackType").setValue("planar", 0)
tracker.property("searchArea").setValue(31, 0)
tracker.property("accuracy").setValue("high", 0)
tracker.property("patternSize").setValue(15, 0)
tracker.property("motionModel").setValue("perspective", 0)
tracker.property("forward").setValue(True, 0)
tracker.property("backward").setValue(True, 0)
tracker.property("autoKeyframe").setValue(True, 0)
session.addNode(tracker)

src.outputs[0].connect(tracker.inputs[0])
```

---

## 五、PaintNode Paint修复节点

### 5.1 描述

提供克隆、修复、擦除等画笔工具，用于去除威亚、修复瑕疵、清理背景。

### 5.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | source | 源输入 |
| 输入 | 1 | cloneSource | 克隆源输入（可选） |
| 输出 | 0 | output | 修复后输出 |

### 5.3 属性参数

#### 笔刷

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| brush.size | float | 25.0 | 1.0 ~ 1000.0 | 笔刷大小 |
| brush.hardness | float | 0.5 | 0.0 ~ 1.0 | 笔刷硬度 |
| brush.flow | float | 1.0 | 0.0 ~ 1.0 | 笔刷流量 |
| brush.opacity | float | 1.0 | 0.0 ~ 1.0 | 笔刷不透明度 |
| brush.spacing | float | 0.1 | 0.01 ~ 1.0 | 笔刷间距 |

#### 模式

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| mode | string | "clone" | clone/repair/erase/reveal/paint | 绘制模式 |
| sampleOffset | point | [0,0] | 任意坐标 | 采样偏移 [x, y] |
| cloneSource | string | "current" | current/prev/next/custom | 克隆源帧 |
| cloneFrame | int | 0 | 任意帧号 | 自定义克隆帧 |
| timeOffset | int | 0 | -999 ~ 999 | 时间偏移帧数 |

#### 高级

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| aligned | bool | true | true/false | 对齐采样 |
| flipX | bool | false | true/false | 水平翻转 |
| flipY | bool | false | true/false | 垂直翻转 |
| rotate | float | 0.0 | -360.0 ~ 360.0 | 旋转角度 |
| scale | float | 1.0 | 0.01 ~ 10.0 | 缩放比例 |

### 5.4 示例代码

```python
from fx import *

paint = Node("PaintNode")
paint.label = "Wire_Removal"
paint.property("brush.size").setValue(35.0, 0)
paint.property("brush.hardness").setValue(0.8, 0)
paint.property("brush.flow").setValue(0.9, 0)
paint.property("mode").setValue("clone", 0)
paint.property("aligned").setValue(True, 0)
paint.property("timeOffset").setValue(-2, 0)
session.addNode(paint)

src.outputs[0].connect(paint.inputs[0])
```

---

## 六、OutputNode 输出节点

### 6.1 描述

将节点图的处理结果渲染输出为图像序列或视频文件。

### 6.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | input | 主输入 |
| 输出 | - | - | 无输出端口 |

### 6.3 属性参数

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| path | string | "" | 任意合法路径 | 输出路径，支持 [####] 通配符 |
| format | string | "exr" | exr/tiff/png/dpx/jpg | 输出格式 |
| compression | string | "none" | none/zip/piz/rle/dwaa | 压缩方式 |
| depth | string | "32f" | 8i/16i/16f/32f | 位深度 |
| channels | string | "rgba" | rgb/rgba/alpha/aov | 通道 |
| frameStart | int | 0 | 0 ~ 999999 | 起始帧 |
| frameEnd | int | 100 | 1 ~ 999999 | 结束帧 |
| frameRate | float | 24.0 | 1.0 ~ 120.0 | 输出帧率 |
| colorSpace | string | "linear" | linear/sRGB/Rec709 | 输出色彩空间 |
| premultiply | bool | true | true/false | 预乘 Alpha |

### 6.4 示例代码

```python
from fx import *

out_node = Node("OutputNode")
out_node.label = "Final_Output"
out_node.property("path").setValue("D:/output/matte_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("compression").setValue("piz", 0)
out_node.property("depth").setValue("32f", 0)
out_node.property("channels").setValue("rgba", 0)
out_node.property("frameStart").setValue(0, 0)
out_node.property("frameEnd").setValue(240, 0)
out_node.property("colorSpace").setValue("linear", 0)
session.addNode(out_node)

roto.outputs[0].connect(out_node.inputs[0])
```

---

## 七、CompositeNode 合成节点

### 7.1 描述

将两个输入按指定模式合成，支持 Over、Add、Screen、Multiply 等多种混合模式。

### 7.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | background | 背景输入 |
| 输入 | 1 | foreground | 前景输入 |
| 输出 | 0 | output | 合成结果 |

### 7.3 属性参数

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| mode | string | "over" | over/add/subtract/multiply/screen/overlay/softLight/hardLight/difference | 混合模式 |
| opacity | float | 1.0 | 0.0 ~ 1.0 | 前景不透明度 |
| maskInput | string | "none" | none/alpha/luma | 遮罩输入类型 |
| invertMask | bool | false | true/false | 反转遮罩 |
| premultiplied | bool | true | true/false | 预乘处理 |

### 7.4 示例代码

```python
from fx import *

comp = Node("CompositeNode")
comp.label = "Layer_Comp"
comp.property("mode").setValue("over", 0)
comp.property("opacity").setValue(0.85, 0)
session.addNode(comp)

src.outputs[0].connect(comp.inputs[0])  # 背景
roto.outputs[0].connect(comp.inputs[1])  # 前景
```

---

## 八、ColorNode 颜色节点

### 8.1 描述

提供基础色彩校正功能，包括亮度、对比度、色相、饱和度调整。

### 8.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | input | 主输入 |
| 输出 | 0 | output | 处理后输出 |

### 8.3 属性参数

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| brightness | float | 0.0 | -1.0 ~ 1.0 | 亮度偏移 |
| contrast | float | 0.0 | -1.0 ~ 1.0 | 对比度 |
| saturation | float | 1.0 | 0.0 ~ 3.0 | 饱和度 |
| hue | float | 0.0 | -180.0 ~ 180.0 | 色相偏移（度） |
| gamma | float | 1.0 | 0.01 ~ 10.0 | Gamma 值 |
| exposure | float | 0.0 | -10.0 ~ 10.0 | 曝光（stops） |
| gain | color | [1,1,1] | [0,0,0] ~ [10,10,10] | RGB 增益 |
| offset | color | [0,0,0] | [-1,-1,-1] ~ [1,1,1] | RGB 偏移 |

### 8.4 示例代码

```python
from fx import *

color_node = Node("ColorNode")
color_node.label = "Color_Correct"
color_node.property("brightness").setValue(0.05, 0)
color_node.property("contrast").setValue(0.15, 0)
color_node.property("saturation").setValue(1.2, 0)
color_node.property("gamma").setValue(0.9, 0)
session.addNode(color_node)

src.outputs[0].connect(color_node.inputs[0])
```

---

## 九、FilterNode 滤镜节点

### 9.1 描述

提供模糊、锐化、去噪等图像滤波操作。

### 9.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | input | 主输入 |
| 输出 | 0 | output | 处理后输出 |

### 9.3 属性参数

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| filterType | string | "blur" | blur/gaussian/box/sharpen/median/bilateral/denoise | 滤镜类型 |
| radius | float | 5.0 | 0.0 ~ 100.0 | 滤镜半径 |
| amount | float | 1.0 | 0.0 ~ 10.0 | 强度 |
| threshold | float | 0.0 | 0.0 ~ 1.0 | 阈值 |
| edgeAware | bool | false | true/false | 边缘感知 |
| iterations | int | 1 | 1 ~ 10 | 迭代次数 |

### 9.4 示例代码

```python
from fx import *

filt = Node("FilterNode")
filt.label = "Edge_Blur"
filt.property("filterType").setValue("gaussian", 0)
filt.property("radius").setValue(8.0, 0)
filt.property("edgeAware").setValue(True, 0)
session.addNode(filt)

src.outputs[0].connect(filt.inputs[0])
```

---

## 十、MatteNode 遮罩节点

### 10.1 描述

根据亮度或颜色信息生成遮罩，常用于抠像辅助。

### 10.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | input | 主输入 |
| 输出 | 0 | output | 生成的遮罩 |

### 10.3 属性参数

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| matteType | string | "luma" | luma/color/hue/saturation | 遮罩类型 |
| lowThreshold | float | 0.0 | 0.0 ~ 1.0 | 低阈值 |
| highThreshold | float | 1.0 | 0.0 ~ 1.0 | 高阈值 |
| softness | float | 0.1 | 0.0 ~ 1.0 | 软度 |
| invert | bool | false | true/false | 反转 |
| colorKey | color | [0,1,0] | [0,0,0] ~ [1,1,1] | 颜色键（color模式） |
| tolerance | float | 0.2 | 0.0 ~ 1.0 | 容差 |

### 10.4 示例代码

```python
from fx import *

matte = Node("MatteNode")
matte.label = "Luma_Matte"
matte.property("matteType").setValue("luma", 0)
matte.property("lowThreshold").setValue(0.3, 0)
matte.property("highThreshold").setValue(0.8, 0)
matte.property("softness").setValue(0.2, 0)
session.addNode(matte)

src.outputs[0].connect(matte.inputs[0])
```

---

## 十一、TransformNode 变换节点

### 11.1 描述

对图像进行平移、旋转、缩放、倾斜等几何变换。

### 11.2 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | input | 主输入 |
| 输出 | 0 | output | 变换后输出 |

### 11.3 属性参数

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| translate | point | [0,0] | 任意坐标 | 平移 [x, y] |
| rotate | float | 0.0 | -360.0 ~ 360.0 | 旋转角度 |
| scale | point | [1,1] | 0.01 ~ 100.0 | 缩放 [sx, sy] |
| skew | point | [0,0] | -100.0 ~ 100.0 | 倾斜 [x, y] |
| anchor | point | [0,0] | 任意坐标 | 锚点 [x, y] |
| filter | string | "bilinear" | nearest/bilinear/bicubic/lanczos | 重采样方式 |
| motionBlur | bool | false | true/false | 运动模糊 |
| motionBlur.shutter | float | 0.5 | 0.0 ~ 2.0 | 快门时间 |

### 11.4 示例代码

```python
from fx import *

transform = Node("TransformNode")
transform.label = "Stabilize"
transform.property("translate").setValue([10.5, -3.2], 0)
transform.property("rotate").setValue(-0.5, 0)
transform.property("scale").setValue([1.02, 1.02], 0)
transform.property("filter").setValue("bicubic", 0)
session.addNode(transform)

src.outputs[0].connect(transform.inputs[0])
```

---

## 十二、节点通用属性

所有节点共享以下通用属性和方法：

### 12.1 通用属性

| 属性名 | 类型 | 说明 |
|--------|------|------|
| label | string | 节点标签（显示名） |
| type | string | 节点类型（只读） |
| enabled | bool | 是否启用 |
| selected | bool | 是否选中 |
| position | point | 节点在图中的位置 [x, y] |

### 12.2 通用方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| property(name) | name: str | Property | 获取指定属性 |
| properties | 无 | list | 所有属性名列表 |
| addProperty(prop) | prop: Property | None | 添加自定义属性 |
| remove() | 无 | None | 删除节点 |
| clone() | 无 | Node | 克隆节点 |

---

## 十三、最佳实践

### 13.1 节点命名规范

```python
# 使用 label 而非 type 作为标识
roto.label = "Char_Body_Roto_v01"
# 格式: <对象>_<部位>_<节点类型>_<版本>
```

### 13.2 节点连接顺序

```
SourceNode → RotoNode → ColorNode → FilterNode → OutputNode
```

### 13.3 性能优化建议

- 高精度跟踪使用 `accuracy: "high"`，预览阶段使用 `medium`
- 运动模糊 `samples` 不超过 32，通常 8-16 足够
- 滤镜 `iterations` 尽量保持在 1-3
- 长序列渲染前先用短帧范围测试

### 13.4 完整流水线示例

```python
from fx import *

# 项目与会话
proj = activeProject() or Project()
activate(proj)
session = activeSession() or Session()
session.label = "Full_Pipeline"
activate(session)
proj.addItem(session)

# 节点链
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.mov", 0)
session.addNode(src)

roto = Node("RotoNode")
roto.property("motionBlur").setValue(True, 0)
session.addNode(roto)

paint = Node("PaintNode")
paint.property("mode").setValue("repair", 0)
session.addNode(paint)

color = Node("ColorNode")
color.property("saturation").setValue(1.1, 0)
session.addNode(color)

out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/final_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

# 连接
src.outputs[0].connect(roto.inputs[1])
roto.outputs[0].connect(paint.inputs[0])
paint.outputs[0].connect(color.inputs[0])
color.outputs[0].connect(out_node.inputs[0])

print("[SILHOUETTE] Full pipeline ready")
```

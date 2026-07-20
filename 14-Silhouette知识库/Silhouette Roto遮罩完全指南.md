# Silhouette Roto遮罩完全指南

## 一、RotoNode 核心概念

### 1.1 Roto 工作原理

Roto（Rotoscoping）是一种逐帧绘制遮罩的技术，用于精确分离前景和背景。

```
原始画面 → RotoNode绘制形状 → 生成Alpha遮罩 → 合成输出
```

### 1.2 RotoNode 端口映射

**输入端口索引**:
- `inputs[0]` - obey_matte（遮罩服从）
- `inputs[1]` - foreground（**主输入，必须连接**）
- `inputs[2]` - background（背景替换）
- `inputs[3]` - occlusion（遮挡层）
- `inputs[4]` - data（数据输入）

**输出端口索引**:
- `outputs[0]` - output（主输出，含Alpha通道）
- `outputs[1]` - colorComp（颜色合成）
- `outputs[2]` - composite（合成结果）
- `outputs[3]` - channels（通道数据）
- `outputs[4]` - objects（形状对象）

---

## 二、形状类型

### 2.1 X-Spline（推荐）

平滑曲线，适合有机形状。

```python
shape = createObject("X-Spline")
shape.name = "Body"
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| points | list | 控制点列表 |
| closed | bool | 是否闭合 |
| feather | float | 羽化值 |
| blur | float | 边缘模糊 |

### 2.2 Bezier（贝塞尔曲线）

精确控制曲线，适合硬边物体。

```python
shape = createObject("Bezier")
shape.name = "HardEdge"
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| points | list | 贝塞尔点（含手柄） |
| closed | bool | 是否闭合 |
| feather | float | 羽化值 |

### 2.3 Rectangle（矩形）

```python
shape = createObject("Rectangle")
```

### 2.4 Ellipse（椭圆）

```python
shape = createObject("Ellipse")
```

---

## 三、Roto 参数调优

### 3.1 边缘处理

```python
# 边缘模糊 - 控制羽化程度
roto.property("alpha.blur").setValue(0.8, 0)

# 抗锯齿 - 平滑边缘
roto.property("antialias").setValue(1.0, 0)
```

| alpha.blur 值 | 效果 | 适用场景 |
|--------------|------|----------|
| 0.0 | 硬边 | 锐利边缘物体 |
| 0.3-0.5 | 轻微模糊 | 正常抠像 |
| 0.8-1.5 | 明显模糊 | 毛发、半透明物体 |
| 2.0+ | 强模糊 | 大气效果 |

### 3.2 遮罩模式

```python
# 遮罩模式
roto.property("matte.mode").setValue("alpha", 0)

# 反转遮罩
roto.property("matte.invert").setValue(false, 0)
```

**matte.mode 选项**:
- "alpha" - 使用Alpha通道（默认）
- "luma" - 使用亮度遮罩
- "rgb" - 使用RGB通道

### 3.3 运动模糊

```python
# 启用运动模糊
roto.property("motionBlur").setValue(true, 0)
roto.property("motionBlur.shutter").setValue(0.5, 0)
```

---

## 四、完整 Roto 脚本模板

### 4.1 基础 Roto 抠图

```python
from fx import *

proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Roto_Example"
activate(session)
proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/input.mov", 0)
src.property("frameRate").setValue(30.0, 0)
session.addNode(src)

roto = Node("RotoNode")
roto.label = "Main_Roto"
roto.property("alpha.blur").setValue(0.5, 0)
roto.property("antialias").setValue(1.0, 0)
roto.property("fill").setValue(true, 0)
session.addNode(roto)

out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/matte_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("compression").setValue("none", 0)
session.addNode(out_node)

src.outputs[0].connect(roto.inputs[1])
roto.outputs[0].connect(out_node.inputs[0])

print("[SILHOUETTE] Roto pipeline ready")
```

### 4.2 多层 Roto 处理

```python
roto1 = Node("RotoNode")
roto1.label = "Body_Roto"
roto1.property("alpha.blur").setValue(0.3, 0)

roto2 = Node("RotoNode")
roto2.label = "Hair_Roto"
roto2.property("alpha.blur").setValue(1.2, 0)

src.outputs[0].connect(roto1.inputs[1])
roto1.outputs[0].connect(roto2.inputs[1])
roto2.outputs[0].connect(out_node.inputs[0])
```

---

## 五、常用预设配置

### 5.1 标准抠像预设

```python
def apply_standard_keying(roto):
    roto.property("alpha.blur").setValue(0.5, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("fill").setValue(true, 0)
    roto.property("stroke").setValue(false, 0)
    roto.property("matte.mode").setValue("alpha", 0)
    roto.property("matte.invert").setValue(false, 0)
```

### 5.2 毛发抠像预设

```python
def apply_hair_keying(roto):
    roto.property("alpha.blur").setValue(1.5, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("fill").setValue(true, 0)
    roto.property("motionBlur").setValue(true, 0)
    roto.property("motionBlur.shutter").setValue(0.7, 0)
```

### 5.3 硬边物体预设

```python
def apply_hard_edge_keying(roto):
    roto.property("alpha.blur").setValue(0.1, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("fill").setValue(true, 0)
    roto.property("matte.mode").setValue("alpha", 0)
```

---

## 六、故障排查

### 6.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 遮罩不生效 | 端口连接错误 | 确保连接到 inputs[1] foreground |
| 边缘锯齿 | antialias 值过低 | 设置为 1.0 |
| 边缘不干净 | alpha.blur 值过低 | 增加到 0.5-1.0 |
| 半透明区域丢失 | fill 设置错误 | 确保 fill=true |
| 运动模糊闪烁 | shutter 值过大 | 降低到 0.3-0.5 |

### 6.2 调试技巧

```python
# 输出属性列表
print("RotoNode properties:", roto.properties)

# 检查连接状态
print("Input connected:", roto.inputs[1].isConnected())

# 打印当前值
print("alpha.blur:", roto.property("alpha.blur").getValue(0))
```

---

## 七、与 AE 集成

### 7.1 Matte 序列导入

```python
# 在 AE 中导入 Matte 序列
importOptions = new ImportOptions(new File("D:/output/matte_[####].exr"))
importOptions.sequence = true
matteFootage = app.project.importFile(importOptions)
```

### 7.2 Track Matte 设置

```python
# 设置 Alpha Track Matte
mainLayer.trackMatteType = TrackMatteType.ALPHA
mainLayer.trackMatteLayer = matteLayer
matteLayer.enabled = false
```

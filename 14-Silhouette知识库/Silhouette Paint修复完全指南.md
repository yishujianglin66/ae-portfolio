# Silhouette Paint修复完全指南

## 一、PaintNode 核心概念

### 1.1 Paint 模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **Clone** | 克隆复制 | 移除水印、Logo |
| **Repair** | 智能修复 | 修复划痕、斑点 |
| **Erase** | 擦除 | 擦除不需要的元素 |

### 1.2 PaintNode 端口

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | source | 源视频输入 |

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | output | 修复后输出 |

---

## 二、Paint 参数详解

### 2.1 笔刷参数

```python
paint = Node("PaintNode")
paint.label = "Clone_Paint"

# 笔刷大小
paint.property("brush.size").setValue(25.0, 0)

# 笔刷硬度
paint.property("brush.hardness").setValue(0.5, 0)

# 笔刷流量
paint.property("brush.flow").setValue(1.0, 0)

# 模式
paint.property("mode").setValue("clone", 0)

# 采样偏移
paint.property("sampleOffset").setValue([0, 0], 0)

session.addNode(paint)
```

### 2.2 参数调优表

| 参数 | 值范围 | 效果 |
|------|--------|------|
| **brush.size** | 5-100 | 5=精细修复，100=大面积修复 |
| **brush.hardness** | 0-1 | 0=软边，1=硬边 |
| **brush.flow** | 0-1 | 0=透明，1=完全不透明 |

---

## 三、完整 Paint 脚本

### 3.1 Clone 修复

```python
from fx import *

proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Paint_Repair"
activate(session)
proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/video.mov", 0)
src.property("frameRate").setValue(30.0, 0)
session.addNode(src)

paint = Node("PaintNode")
paint.label = "Clone_Repair"
paint.property("brush.size").setValue(30.0, 0)
paint.property("brush.hardness").setValue(0.3, 0)
paint.property("brush.flow").setValue(1.0, 0)
paint.property("mode").setValue("clone", 0)
paint.property("sampleOffset").setValue([50, 0], 0)
session.addNode(paint)

out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/repair_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

src.outputs[0].connect(paint.inputs[0])
paint.outputs[0].connect(out_node.inputs[0])

print("[SILHOUETTE] Paint repair pipeline configured")
```

### 3.2 Repair 模式

```python
paint.property("mode").setValue("repair", 0)
paint.property("brush.size").setValue(20.0, 0)
paint.property("brush.hardness").setValue(0.2, 0)
```

---

## 四、常用预设

### 4.1 Clone 移除预设

```python
def apply_clone_removal(paint):
    paint.property("brush.size").setValue(30.0, 0)
    paint.property("brush.hardness").setValue(0.3, 0)
    paint.property("brush.flow").setValue(1.0, 0)
    paint.property("mode").setValue("clone", 0)
    paint.property("sampleOffset").setValue([50, 0], 0)
```

### 4.2 Repair 修复预设

```python
def apply_repair(paint):
    paint.property("brush.size").setValue(20.0, 0)
    paint.property("brush.hardness").setValue(0.2, 0)
    paint.property("brush.flow").setValue(0.8, 0)
    paint.property("mode").setValue("repair", 0)
```

### 4.3 Erase 擦除预设

```python
def apply_erase(paint):
    paint.property("brush.size").setValue(40.0, 0)
    paint.property("brush.hardness").setValue(0.8, 0)
    paint.property("brush.flow").setValue(1.0, 0)
    paint.property("mode").setValue("erase", 0)
```

---

## 五、故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 修复不自然 | brush.hardness 过大 | 降低硬度 |
| 边缘明显 | brush.size 过小 | 增大笔刷 |
| 复制区域错误 | sampleOffset 设置不当 | 调整偏移 |
| 修复不完全 | brush.flow 过小 | 增大流量 |

---

## 六、与 AE 集成

```javascript
var paintFootage = app.project.importFile(
    new ImportOptions(new File("D:/output/repair_[####].exr"))
);
paintFootage.sequence = true;

var layer = comp.layers.add(paintFootage);
layer.name = "Repaired_Layer";
```

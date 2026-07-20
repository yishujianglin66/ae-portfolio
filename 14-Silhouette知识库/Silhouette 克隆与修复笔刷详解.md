# Silhouette 克隆与修复笔刷详解

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: Clone/Repair/Erase笔刷深度解析，涵盖笔刷参数、笔刷形状、压力控制、源点设置与各种修复场景应用。

## 目录
1. [笔刷类型概述](#一笔刷类型概述)
2. [Clone 克隆笔刷](#二clone-克隆笔刷)
3. [Repair 修复笔刷](#三repair-修复笔刷)
4. [Erase 擦除笔刷](#四erase-擦除笔刷)
5. [笔刷形状与参数](#五笔刷形状与参数)
6. [压力控制](#六压力控制)
7. [源点设置](#七源点设置)
8. [应用场景](#八应用场景)

---

## 一、笔刷类型概述

### 1.1 三种核心笔刷

Silhouette Paint 提供三种核心笔刷类型，每种针对不同的修复场景：

| 笔刷类型 | 工作原理 | 适用场景 | 不适用场景 |
|----------|----------|----------|------------|
| **Clone** | 从源点复制像素到目标区域 | 移除水印、Logo、威亚 | 自然纹理修复 |
| **Repair** | 智能填充，基于周边像素 | 修复划痕、斑点、瑕疵 | 大面积移除 |
| **Erase** | 擦除已修复内容 | 修正过度修复 | 创建新内容 |

### 1.2 笔刷选择决策

```
需要移除物体吗？
├── 是 → 物体大小？
│        ├── 大面积 → Clone（复制背景覆盖）
│        └── 小面积 → Repair（智能填充）
└── 否 → 需要擦除已修复？
         ├── 是 → Erase
         └── 否 → 重新评估需求
```

### 1.3 笔刷通用属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| brush.size | float | 25.0 | 笔刷大小（像素） |
| brush.hardness | float | 0.5 | 笔刷硬度（0-1） |
| brush.flow | float | 1.0 | 笔刷流量（0-1） |
| brush.opacity | float | 1.0 | 不透明度（0-1） |
| brush.spacing | float | 0.25 | 笔刷间距 |
| brush.shape | string | "circle" | 笔刷形状 |
| mode | string | "clone" | 笔刷模式 |

---

## 二、Clone 克隆笔刷

### 2.1 Clone 工作原理

Clone 笔刷从一个源点（Source Point）复制像素到目标区域，是最基础的修复工具。

```
源点 → 复制像素 → 应用到目标区域
```

### 2.2 Clone 参数详解

```python
from fx import *

# 创建 Paint 节点
paint = Node("PaintNode")
paint.label = "Clone_Brush"

# 设置为 Clone 模式
paint.property("mode").setValue("clone", 0)

# 笔刷参数
paint.property("brush.size").setValue(30.0, 0)      # 笔刷大小
paint.property("brush.hardness").setValue(0.3, 0)   # 软边（自然融合）
paint.property("brush.flow").setValue(1.0, 0)       # 完全流量
paint.property("brush.opacity").setValue(1.0, 0)    # 完全不透明
paint.property("brush.spacing").setValue(0.25, 0)   # 标准间距

# 克隆源设置
paint.property("sampleOffset").setValue([50, 0], 0)  # 源点偏移 [dx, dy]
paint.property("cloneSource").setValue("current", 0)  # 从当前帧克隆
paint.property("cloneFrame").setValue(0, 0)           # 克隆帧（当 cloneSource="frame" 时）

session.addNode(paint)
```

### 2.3 Clone 源点设置

**源点偏移**：
```python
# 源点在目标点右侧 50 像素
paint.property("sampleOffset").setValue([50, 0], 0)

# 源点在目标点下方 30 像素
paint.property("sampleOffset").setValue([0, 30], 0)

# 源点在目标点左上方
paint.property("sampleOffset").setValue([-40, -40], 0)
```

**克隆源类型**：
```python
# 从当前帧克隆（最常用）
paint.property("cloneSource").setValue("current", 0)

# 从指定帧克隆
paint.property("cloneSource").setValue("frame", 0)
paint.property("cloneFrame").setValue(10, 0)  # 从第10帧克隆

# 从其他素材克隆
paint.property("cloneSource").setValue("external", 0)
paint.property("clonePath").setValue("D:/footage/source.mov", 0)
```

### 2.4 Clone 应用场景

| 场景 | 源点选择 | 参数建议 |
|------|----------|----------|
| 移除水印 | 附近相似背景 | hardness=0.3, size=20-50 |
| 移除 Logo | 附近相似纹理 | hardness=0.2, size=30-80 |
| 威亚去除 | 威亚两侧背景 | hardness=0.1, size=10-30 |
| 物体擦除 | 周边背景 | hardness=0.3, size=50-150 |
| 背景重建 | 相似背景区域 | hardness=0.2, size=100+ |

### 2.5 Clone 完整脚本

```python
from fx import *

# 项目初始化
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Clone_Removal"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/watermark.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# Clone 笔刷
paint = Node("PaintNode")
paint.label = "Watermark_Removal"
paint.property("mode").setValue("clone", 0)
paint.property("brush.size").setValue(40.0, 0)
paint.property("brush.hardness").setValue(0.3, 0)
paint.property("brush.flow").setValue(1.0, 0)
paint.property("brush.opacity").setValue(1.0, 0)
paint.property("sampleOffset").setValue([60, 0], 0)  # 源点偏移
paint.property("cloneSource").setValue("current", 0)
session.addNode(paint)

# 输出
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/clone_removed_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

# 连接
src.outputs[0].connect(paint.inputs[0])
paint.outputs[0].connect(out_node.inputs[0])

print("[SILHOUETTE] Clone removal pipeline ready")
```

---

## 三、Repair 修复笔刷

### 3.1 Repair 工作原理

Repair 笔刷基于周边像素智能填充目标区域，无需指定源点。算法分析周边纹理、色彩、光照，自动生成匹配的填充内容。

```
周边像素 → 分析纹理/色彩 → 智能填充 → 目标区域
```

### 3.2 Repair 参数详解

```python
paint = Node("PaintNode")
paint.label = "Repair_Brush"

# 设置为 Repair 模式
paint.property("mode").setValue("repair", 0)

# 笔刷参数（修复通常用软边）
paint.property("brush.size").setValue(20.0, 0)
paint.property("brush.hardness").setValue(0.2, 0)   # 更软的边缘
paint.property("brush.flow").setValue(0.8, 0)       # 稍低流量
paint.property("brush.opacity").setValue(1.0, 0)

# 修复特定参数
paint.property("repairMode").setValue("texture", 0)  # 纹理修复模式
paint.property("sampleRadius").setValue(50.0, 0)     # 采样半径
paint.property("blendMode").setValue("normal", 0)    # 混合模式

session.addNode(paint)
```

### 3.3 修复模式

| 修复模式 | 说明 | 适用场景 |
|----------|------|----------|
| texture | 纹理修复（默认） | 纹理区域 |
| smooth | 平滑修复 | 平滑区域 |
| detail | 细节修复 | 细节丰富区域 |
| color | 色彩修复 | 色彩区域 |

```python
# 纹理修复（默认）
paint.property("repairMode").setValue("texture", 0)

# 平滑修复（适合皮肤等平滑区域）
paint.property("repairMode").setValue("smooth", 0)

# 细节修复（适合细节丰富区域）
paint.property("repairMode").setValue("detail", 0)
```

### 3.4 Repair 应用场景

| 场景 | 修复模式 | 参数建议 |
|------|----------|----------|
| 划痕修复 | texture | size=10-20, hardness=0.2 |
| 斑点去除 | texture | size=5-15, hardness=0.1 |
| 皮肤瑕疵 | smooth | size=10-30, hardness=0.1 |
| 灰尘去除 | detail | size=3-10, hardness=0.3 |
| 裂缝修复 | texture | size=20-50, hardness=0.2 |

### 3.5 Repair 完整脚本

```python
from fx import *

proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Scratch_Repair"
activate(session)
proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scratched.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

paint = Node("PaintNode")
paint.label = "Scratch_Repair"
paint.property("mode").setValue("repair", 0)
paint.property("brush.size").setValue(15.0, 0)
paint.property("brush.hardness").setValue(0.2, 0)
paint.property("brush.flow").setValue(0.8, 0)
paint.property("repairMode").setValue("texture", 0)
paint.property("sampleRadius").setValue(40.0, 0)
session.addNode(paint)

out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/repaired_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

src.outputs[0].connect(paint.inputs[0])
paint.outputs[0].connect(out_node.inputs[0])

print("[SILHOUETTE] Scratch repair pipeline ready")
```

---

## 四、Erase 擦除笔刷

### 4.1 Erase 工作原理

Erase 笔刷擦除已应用的修复内容，恢复原始像素。常用于修正过度修复或擦除不需要的修复区域。

```
已修复区域 → 擦除 → 恢复原始像素
```

### 4.2 Erase 参数详解

```python
paint = Node("PaintNode")
paint.label = "Erase_Brush"

# 设置为 Erase 模式
paint.property("mode").setValue("erase", 0)

# 擦除参数
paint.property("brush.size").setValue(40.0, 0)
paint.property("brush.hardness").setValue(0.8, 0)   # 硬边（精确擦除）
paint.property("brush.flow").setValue(1.0, 0)
paint.property("brush.opacity").setValue(1.0, 0)
paint.property("eraseStrength").setValue(1.0, 0)     # 擦除强度

session.addNode(paint)
```

### 4.3 Erase 应用场景

| 场景 | 参数建议 |
|------|----------|
| 擦除过度修复 | hardness=0.8, size=20-50 |
| 精确擦除边缘 | hardness=1.0, size=5-20 |
| 部分擦除 | eraseStrength=0.5 |
| 完全擦除 | eraseStrength=1.0 |

### 4.4 Erase 使用技巧

**技巧一：配合遮罩使用**
先创建遮罩限定擦除区域，再使用 Erase 笔刷。

**技巧二：部分擦除**
```python
# 降低擦除强度，实现部分擦除
paint.property("eraseStrength").setValue(0.5, 0)
```

**技巧三：分层擦除**
对于复杂修复，分层擦除不同层级的修复内容。

---

## 五、笔刷形状与参数

### 5.1 笔刷形状

| 形状 | 说明 | 适用场景 |
|------|------|----------|
| circle | 圆形（默认） | 通用修复 |
| square | 方形 | 直线边缘 |
| soft_circle | 软圆形 | 自然融合 |
| custom | 自定义形状 | 特殊需求 |

```python
# 圆形笔刷（默认）
paint.property("brush.shape").setValue("circle", 0)

# 方形笔刷
paint.property("brush.shape").setValue("square", 0)

# 软圆形笔刷
paint.property("brush.shape").setValue("soft_circle", 0)
```

### 5.2 笔刷大小

```python
# 精细修复（小笔刷）
paint.property("brush.size").setValue(5.0, 0)    # 5像素

# 中等修复
paint.property("brush.size").setValue(25.0, 0)   # 25像素

# 大面积修复
paint.property("brush.size").setValue(80.0, 0)   # 80像素

# 超大面积
paint.property("brush.size").setValue(150.0, 0)  # 150像素
```

### 5.3 笔刷硬度

硬度控制笔刷边缘的软硬程度：

```python
# 极软边缘（自然融合）
paint.property("brush.hardness").setValue(0.1, 0)

# 软边缘（常用）
paint.property("brush.hardness").setValue(0.3, 0)

# 中等边缘
paint.property("brush.hardness").setValue(0.5, 0)

# 硬边缘（精确修复）
paint.property("brush.hardness").setValue(0.8, 0)

# 完全硬边
paint.property("brush.hardness").setValue(1.0, 0)
```

| 硬度 | 效果 | 适用场景 |
|------|------|----------|
| 0.0-0.2 | 极软，自然融合 | 自然纹理、皮肤 |
| 0.2-0.4 | 软边，多数修复 | 通用修复 |
| 0.4-0.6 | 中等边缘 | 一般物体 |
| 0.6-0.8 | 硬边 | 人造物体 |
| 0.8-1.0 | 完全硬边 | 精确边缘 |

### 5.4 笔刷流量与不透明度

```python
# 流量：每笔的涂抹量
paint.property("brush.flow").setValue(0.5, 0)    # 50% 流量
paint.property("brush.flow").setValue(1.0, 0)    # 100% 流量

# 不透明度：最终透明度
paint.property("brush.opacity").setValue(0.7, 0)  # 70% 不透明度
paint.property("brush.opacity").setValue(1.0, 0)  # 100% 不透明度
```

**流量 vs 不透明度**：
- 流量：控制每次笔触的涂抹量，多次涂抹可累积
- 不透明度：控制最终效果的最大透明度

### 5.5 笔刷间距

```python
# 间距控制笔触连续性
paint.property("brush.spacing").setValue(0.1, 0)   # 紧密（连续）
paint.property("brush.spacing").setValue(0.25, 0)  # 标准
paint.property("brush.spacing").setValue(0.5, 0)   # 稀疏（点状）
```

---

## 六、压力控制

### 6.1 压力感应

支持压感笔的压力输入，实现自然变化：

```python
# 启用压力感应
paint.property("pressureEnabled").setValue(True, 0)

# 压力控制大小
paint.property("pressureSize").setValue(True, 0)
paint.property("pressureSizeScale").setValue(1.0, 0)  # 压力影响程度

# 压力控制硬度
paint.property("pressureHardness").setValue(True, 0)

# 压力控制流量
paint.property("pressureFlow").setValue(True, 0)

# 压力控制不透明度
paint.property("pressureOpacity").setValue(True, 0)
```

### 6.2 压力曲线

```python
# 压力曲线（0-1 范围，控制压力响应）
paint.property("pressureCurve").setValue("linear", 0)      # 线性
paint.property("pressureCurve").setValue("ease_in", 0)     # 渐入
paint.property("pressureCurve").setValue("ease_out", 0)    # 渐出
paint.property("pressureCurve").setValue("ease_in_out", 0) # 渐入渐出
```

### 6.3 压力预设

```python
# 预设一：自然绘画感
def apply_natural_pressure(paint):
    paint.property("pressureEnabled").setValue(True, 0)
    paint.property("pressureSize").setValue(True, 0)
    paint.property("pressureOpacity").setValue(True, 0)
    paint.property("pressureCurve").setValue("ease_in_out", 0)

# 预设二：精确控制
def apply_precise_pressure(paint):
    paint.property("pressureEnabled").setValue(True, 0)
    paint.property("pressureFlow").setValue(True, 0)
    paint.property("pressureCurve").setValue("linear", 0)

# 预设三：关闭压力
def disable_pressure(paint):
    paint.property("pressureEnabled").setValue(False, 0)
```

---

## 七、源点设置

### 7.1 源点选择原则

**原则一：相似性**
源点区域的纹理、色彩应与目标区域相似。

**原则二：距离适中**
- 过近：源点与目标重叠
- 过远：可能不相似
- 推荐：距离 30-100 像素

**原则三：方向一致**
源点应与目标在同一光照方向上。

**原则四：避免重复**
源点不应与目标区域有重复纹理。

### 7.2 源点偏移设置

```python
# 水平偏移
paint.property("sampleOffset").setValue([50, 0], 0)

# 垂直偏移
paint.property("sampleOffset").setValue([0, 50], 0)

# 对角偏移
paint.property("sampleOffset").setValue([40, 40], 0)

# 负方向偏移
paint.property("sampleOffset").setValue([-50, -30], 0)
```

### 7.3 多源点克隆

对于复杂修复，可使用多个源点：

```python
# 源点1：主克隆源
paint.property("sampleOffset1").setValue([50, 0], 0)

# 源点2：辅助克隆源
paint.property("sampleOffset2").setValue([-50, 0], 0)

# 混合比例
paint.property("sourceBlend").setValue(0.5, 0)  # 50% 混合
```

### 7.4 源点对齐

对于精确修复，源点应对齐：

```python
# 启用源点对齐
paint.property("alignSource").setValue(True, 0)

# 对齐方式
paint.property("alignMode").setValue("grid", 0)    # 网格对齐
paint.property("alignMode").setValue("feature", 0)  # 特征对齐
```

---

## 八、应用场景

### 8.1 水印移除

```python
def setup_watermark_removal(paint):
    """水印移除设置"""
    paint.property("mode").setValue("clone", 0)
    paint.property("brush.size").setValue(40.0, 0)
    paint.property("brush.hardness").setValue(0.3, 0)
    paint.property("brush.flow").setValue(1.0, 0)
    paint.property("sampleOffset").setValue([60, 0], 0)
```

### 8.2 划痕修复

```python
def setup_scratch_repair(paint):
    """划痕修复设置"""
    paint.property("mode").setValue("repair", 0)
    paint.property("brush.size").setValue(15.0, 0)
    paint.property("brush.hardness").setValue(0.2, 0)
    paint.property("brush.flow").setValue(0.8, 0)
    paint.property("repairMode").setValue("texture", 0)
```

### 8.3 威亚去除

```python
def setup_wire_removal(paint):
    """威亚去除设置"""
    paint.property("mode").setValue("clone", 0)
    paint.property("brush.size").setValue(20.0, 0)
    paint.property("brush.hardness").setValue(0.1, 0)  # 极软边
    paint.property("brush.flow").setValue(0.8, 0)
    paint.property("sampleOffset").setValue([0, 30], 0)  # 上下偏移
```

### 8.4 物体擦除

```python
def setup_object_removal(paint):
    """物体擦除设置"""
    paint.property("mode").setValue("clone", 0)
    paint.property("brush.size").setValue(80.0, 0)
    paint.property("brush.hardness").setValue(0.3, 0)
    paint.property("brush.flow").setValue(1.0, 0)
    paint.property("sampleOffset").setValue([100, 0], 0)
```

### 8.5 皮肤修复

```python
def setup_skin_repair(paint):
    """皮肤瑕疵修复设置"""
    paint.property("mode").setValue("repair", 0)
    paint.property("brush.size").setValue(10.0, 0)
    paint.property("brush.hardness").setValue(0.1, 0)  # 极软
    paint.property("brush.flow").setValue(0.6, 0)
    paint.property("repairMode").setValue("smooth", 0)
```

### 8.6 笔刷预设总览

```python
# 笔刷预设库
BRUSH_PRESETS = {
    "watermark_removal": {
        "mode": "clone",
        "brush.size": 40.0,
        "brush.hardness": 0.3,
        "brush.flow": 1.0,
        "sampleOffset": [60, 0]
    },
    "scratch_repair": {
        "mode": "repair",
        "brush.size": 15.0,
        "brush.hardness": 0.2,
        "brush.flow": 0.8,
        "repairMode": "texture"
    },
    "wire_removal": {
        "mode": "clone",
        "brush.size": 20.0,
        "brush.hardness": 0.1,
        "brush.flow": 0.8,
        "sampleOffset": [0, 30]
    },
    "object_removal": {
        "mode": "clone",
        "brush.size": 80.0,
        "brush.hardness": 0.3,
        "brush.flow": 1.0,
        "sampleOffset": [100, 0]
    },
    "skin_repair": {
        "mode": "repair",
        "brush.size": 10.0,
        "brush.hardness": 0.1,
        "brush.flow": 0.6,
        "repairMode": "smooth"
    }
}

def apply_preset(paint, preset_name):
    """应用笔刷预设"""
    preset = BRUSH_PRESETS.get(preset_name)
    if preset:
        for prop, value in preset.items():
            paint.property(prop).setValue(value, 0)
        print(f"[SILHOUETTE] 已应用预设: {preset_name}")
    else:
        print(f"[SILHOUETTE] 预设不存在: {preset_name}")
```

### 8.7 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 修复不自然 | hardness 过大 | 降低 hardness |
| 边缘明显 | size 过小 | 增大 size |
| 复制区域错误 | sampleOffset 不当 | 调整 sampleOffset |
| 修复不完全 | flow 过小 | 增大 flow |
| 修复闪烁 | 源点不稳定 | 选择更稳定源点 |
| 纹理不匹配 | 源点不相似 | 重新选择源点 |

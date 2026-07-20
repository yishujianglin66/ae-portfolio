# Silhouette 遮罩节点与通道操作

> 分类: 节点与合成系统
> 更新日期: 2026-07-11
> 概述: MatteNode 详解、通道提取/合并、Alpha 生成、遮罩运算完整说明。

## 目录
1. [Matte 节点概述](#1-matte-节点概述)
2. [节点参数详解](#2-节点参数详解)
3. [通道提取](#3-通道提取)
4. [通道合并](#4-通道合并)
5. [Alpha 生成](#5-alpha-生成)
6. [遮罩运算](#6-遮罩运算)
7. [脚本化遮罩操作](#7-脚本化遮罩操作)
8. [最佳实践](#8-最佳实践)

---

## 1. Matte 节点概述

Matte 节点专门用于通道操作和遮罩运算,是合成工作流中的关键节点。

### 1.1 核心功能

| 功能 | 说明 |
|------|------|
| 通道提取 | 从 RGBA 中提取特定通道 |
| 通道合并 | 将多个单通道合并为多通道 |
| Alpha 生成 | 从亮度、色相等生成 Alpha |
| 遮罩运算 | 并集、交集、差集等布尔运算 |
| 通道交换 | R/G/B/A 通道互换 |

### 1.2 节点端口

```
inputs[0] — 主输入(待处理图像)
inputs[1] — Matte A(遮罩A)
inputs[2] — Matte B(遮罩B,用于运算)
inputs[3] — Matte C(遮罩C,可选)
         ↓
    [Matte Node]
         ↓
outputs[0] — 处理结果
```

## 2. 节点参数详解

### 2.1 参数列表

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `operation` | menu | "extract" | 遮罩运算类型 |
| `sourceChannel` | menu | "alpha" | 源通道选择 |
| `outputChannel` | menu | "alpha" | 输出通道 |
| `invert` | bool | false | 反转结果 |
| `threshold` | float | 0.5 | 阈值 |
| `contrast` | float | 1.0 | 对比度 |
| `brightness` | float | 0.0 | 亮度偏移 |
| `blur` | float | 0.0 | 边缘模糊 |
| `grow` | float | 0.0 | 边缘扩展 |
| `erode` | float | 0.0 | 边缘腐蚀 |

### 2.2 operation 选项

| 值 | 说明 |
|----|------|
| `extract` | 提取通道 |
| `merge` | 合并通道 |
| `union` | 遮罩并集(A OR B) |
| `intersect` | 遮罩交集(A AND B) |
| `difference` | 遮罩差集(A XOR B) |
| `subtract` | 遮罩相减(A - B) |
| `replace` | 替换通道 |
| `copy` | 复制通道 |

### 2.3 sourceChannel 选项

| 值 | 说明 |
|----|------|
| `red` | 红色通道 |
| `green` | 绿色通道 |
| `blue` | 蓝色通道 |
| `alpha` | Alpha 通道 |
| `luminance` | 亮度(Y) |
| `hue` | 色相 |
| `saturation` | 饱和度 |

## 3. 通道提取

### 3.1 从 RGBA 提取

```python
from fx import *

def extract_channel(session, source, channel="alpha"):
    """从源图像提取指定通道"""
    matte = Node("Matte")
    matte.label = f"Extract_{channel}"
    session.addNode(matte)
    matte.inputs[0].connect(source.outputs[0])
    
    matte.property("operation").setValue("extract", 0)
    matte.property("sourceChannel").setValue(channel, 0)
    matte.property("outputChannel").setValue("alpha", 0)
    
    return matte

# 示例:提取红色通道作为遮罩
red_matte = extract_channel(session, source, "red")
```

### 3.2 亮度提取

```python
def extract_luminance(session, source):
    """从亮度提取遮罩"""
    matte = Node("Matte")
    matte.label = "Luma_Matte"
    session.addNode(matte)
    matte.inputs[0].connect(source.outputs[0])
    
    matte.property("operation").setValue("extract", 0)
    matte.property("sourceChannel").setValue("luminance", 0)
    
    # 调整对比度增强遮罩
    matte.property("contrast").setValue(1.5, 0)
    matte.property("brightness").setValue(-0.1, 0)
    
    return matte
```

### 3.3 色相提取

```python
def extract_by_hue(session, source, target_hue=120, hue_range=30):
    """基于色相提取遮罩(如提取绿色)"""
    matte = Node("Matte")
    matte.label = "Hue_Key"
    session.addNode(matte)
    matte.inputs[0].connect(source.outputs[0])
    
    matte.property("operation").setValue("extract", 0)
    matte.property("sourceChannel").setValue("hue", 0)
    
    # 调整阈值和范围
    matte.property("threshold").setValue(target_hue / 360.0, 0)
    # hue_range 需要通过其他参数控制(概念性)
    
    return matte
```

## 4. 通道合并

### 4.1 合并多个单通道

```python
def merge_channels(session, r_source, g_source, b_source, a_source=None):
    """将多个单通道源合并为 RGBA"""
    matte = Node("Matte")
    matte.label = "Merge_Channels"
    session.addNode(matte)
    
    # 连接各通道源
    matte.inputs[0].connect(r_source.outputs[0])
    if len(matte.inputs) > 1:
        matte.inputs[1].connect(g_source.outputs[0])
    if len(matte.inputs) > 2:
        matte.inputs[2].connect(b_source.outputs[0])
    if a_source and len(matte.inputs) > 3:
        matte.inputs[3].connect(a_source.outputs[0])
    
    matte.property("operation").setValue("merge", 0)
    
    return matte
```

### 4.2 替换特定通道

```python
def replace_alpha(session, source, new_alpha_source):
    """用新遮罩替换源图像的 Alpha 通道"""
    matte = Node("Matte")
    matte.label = "Replace_Alpha"
    session.addNode(matte)
    
    matte.inputs[0].connect(source.outputs[0])
    matte.inputs[1].connect(new_alpha_source.outputs[0])
    
    matte.property("operation").setValue("replace", 0)
    matte.property("outputChannel").setValue("alpha", 0)
    
    return matte
```

### 4.3 通道交换

```python
def swap_channels(session, source, swap="rg"):
    """交换通道(如 R↔G)"""
    matte = Node("Matte")
    matte.label = f"Swap_{swap}"
    session.addNode(matte)
    matte.inputs[0].connect(source.outputs[0])
    
    # 根据交换类型配置
    swap_map = {
        "rg": ("red", "green"),
        "rb": ("red", "blue"),
        "gb": ("green", "blue"),
    }
    if swap in swap_map:
        ch1, ch2 = swap_map[swap]
        # 具体实现取决于 API 支持的通道操作
    
    return matte
```

## 5. Alpha 生成

### 5.1 从亮度生成 Alpha

```python
def generate_alpha_from_luma(session, source, threshold=0.5, contrast=1.5):
    """从亮度生成 Alpha 遮罩"""
    matte = Node("Matte")
    matte.label = "Alpha_From_Luma"
    session.addNode(matte)
    matte.inputs[0].connect(source.outputs[0])
    
    matte.property("operation").setValue("extract", 0)
    matte.property("sourceChannel").setValue("luminance", 0)
    matte.property("outputChannel").setValue("alpha", 0)
    matte.property("threshold").setValue(threshold, 0)
    matte.property("contrast").setValue(contrast, 0)
    
    return matte
```

### 5.2 从色相生成 Alpha

```python
def generate_alpha_from_hue(session, source, hue_center=120, tolerance=20):
    """从特定色相范围生成 Alpha(如绿幕抠像)"""
    matte = Node("Matte")
    matte.label = "Alpha_From_Hue"
    session.addNode(matte)
    matte.inputs[0].connect(source.outputs[0])
    
    matte.property("operation").setValue("extract", 0)
    matte.property("sourceChannel").setValue("hue", 0)
    matte.property("outputChannel").setValue("alpha", 0)
    matte.property("threshold").setValue(hue_center / 360.0, 0)
    
    return matte
```

### 5.3 Alpha 边缘处理

```python
def refine_alpha(matte_node, blur=0.5, grow=0.0, erode=0.0, contrast=1.2):
    """优化 Alpha 边缘"""
    matte_node.property("blur").setValue(blur, 0)
    matte_node.property("grow").setValue(grow, 0)
    matte_node.property("erode").setValue(erode, 0)
    matte_node.property("contrast").setValue(contrast, 0)
    return matte_node
```

## 6. 遮罩运算

### 6.1 布尔运算

```python
def matte_union(session, matte_a, matte_b):
    """遮罩并集(A OR B)"""
    matte = Node("Matte")
    matte.label = "Union"
    session.addNode(matte)
    matte.inputs[0].connect(matte_a.outputs[0])
    matte.inputs[1].connect(matte_b.outputs[0])
    matte.property("operation").setValue("union", 0)
    return matte

def matte_intersect(session, matte_a, matte_b):
    """遮罩交集(A AND B)"""
    matte = Node("Matte")
    matte.label = "Intersect"
    session.addNode(matte)
    matte.inputs[0].connect(matte_a.outputs[0])
    matte.inputs[1].connect(matte_b.outputs[0])
    matte.property("operation").setValue("intersect", 0)
    return matte

def matte_difference(session, matte_a, matte_b):
    """遮罩差集(A XOR B)"""
    matte = Node("Matte")
    matte.label = "Difference"
    session.addNode(matte)
    matte.inputs[0].connect(matte_a.outputs[0])
    matte.inputs[1].connect(matte_b.outputs[0])
    matte.property("operation").setValue("difference", 0)
    return matte

def matte_subtract(session, matte_a, matte_b):
    """遮罩相减(A - B)"""
    matte = Node("Matte")
    matte.label = "Subtract"
    session.addNode(matte)
    matte.inputs[0].connect(matte_a.outputs[0])
    matte.inputs[1].connect(matte_b.outputs[0])
    matte.property("operation").setValue("subtract", 0)
    return matte
```

### 6.2 运算图示

```
并集(Union):A ∪ B
  ┌─────┐
  │ A + B │  两个遮罩合并
  └─────┘

交集(Intersect):A ∩ B
  ┌─────┐
  │ A ∩ B │  仅重叠部分
  └─────┘

差集(Difference):A ⊕ B
  ┌─────┐
  │A XOR B│  非重叠部分
  └─────┘

相减(Subtract):A - B
  ┌─────┐
  │ A - B │  A 中减去 B
  └─────┘
```

### 6.3 组合运算

```python
def complex_matte_operation(session, matte_a, matte_b, matte_c):
    """
    复合运算:(A AND B) OR C
    即 A 与 B 的交集,再与 C 取并集
    """
    # 第一步:A AND B
    intersect = matte_intersect(session, matte_a, matte_b)
    
    # 第二步:result OR C
    final = matte_union(session, intersect, matte_c)
    
    return final

def hole_in_matte(session, outer_matte, inner_matte):
    """在遮罩中打孔(outer - inner)"""
    return matte_subtract(session, outer_matte, inner_matte)
```

## 7. 脚本化遮罩操作

### 7.1 创建完整遮罩管线

```python
def build_matte_pipeline(session, source):
    """
    构建遮罩处理管线:
    Source → Extract Luminance → Refine → Output
    """
    # 提取亮度
    extract = Node("Matte")
    extract.label = "Extract_Luma"
    session.addNode(extract)
    extract.inputs[0].connect(source.outputs[0])
    extract.property("operation").setValue("extract", 0)
    extract.property("sourceChannel").setValue("luminance", 0)
    
    # 优化边缘
    refine = Node("Matte")
    refine.label = "Refine_Edge"
    session.addNode(refine)
    refine.inputs[0].connect(extract.outputs[0])
    refine.property("blur").setValue(0.5, 0)
    refine.property("contrast").setValue(1.3, 0)
    refine.property("grow").setValue(1.0, 0)
    
    # 输出
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(refine.outputs[0])
    
    return extract, refine, output
```

### 7.2 多遮罩组合

```python
def combine_multiple_mattes(session, matte_nodes, operation="union"):
    """
    组合多个遮罩
    matte_nodes: [matte1, matte2, matte3, ...]
    """
    if not matte_nodes:
        return None
    
    if len(matte_nodes) == 1:
        return matte_nodes[0]
    
    result = matte_nodes[0]
    for matte in matte_nodes[1:]:
        combined = Node("Matte")
        combined.label = f"Combine_{operation}"
        session.addNode(combined)
        combined.inputs[0].connect(result.outputs[0])
        combined.inputs[1].connect(matte.outputs[0])
        combined.property("operation").setValue(operation, 0)
        result = combined
    
    return result
```

### 7.3 遮罩动画

```python
def animate_matte_threshold(matte_node, keyframes):
    """为遮罩阈值添加关键帧
    keyframes: [(frame, value), ...]
    """
    prop = matte_node.property("threshold")
    if not prop:
        return False
    for frame, value in keyframes:
        prop.setValue(value, frame)
    return True

def animate_matte_grow(matte_node, start_frame, duration, start_val=0, end_val=5):
    """遮罩边缘扩展动画"""
    prop = matte_node.property("grow")
    if not prop:
        return False
    prop.setValue(start_val, start_frame)
    prop.setValue(end_val, start_frame + duration)
    return True
```

### 7.4 遮罩诊断

```python
def diagnose_matte(matte_node):
    """诊断遮罩节点配置"""
    info = {
        "label": matte_node.label,
        "operation": matte_node.property("operation").value,
        "sourceChannel": matte_node.property("sourceChannel").value,
        "outputChannel": matte_node.property("outputChannel").value,
        "invert": matte_node.property("invert").value,
        "threshold": matte_node.property("threshold").value,
        "contrast": matte_node.property("contrast").value,
        "blur": matte_node.property("blur").value,
        "grow": matte_node.property("grow").value,
        "erode": matte_node.property("erode").value,
        "inputs_connected": sum(1 for p in matte_node.inputs if p.isConnected()),
    }
    return info
```

## 8. 最佳实践

### 8.1 遮罩生成策略

| 场景 | 推荐方法 | 说明 |
|------|----------|------|
| 高对比度对象 | 亮度提取 | 快速有效 |
| 特定颜色对象 | 色相提取 | 适合绿幕 |
| 复杂边缘 | Roto + 亮度组合 | 精确控制 |
| 运动对象 | 跟踪 + Roto | 跟随运动 |

### 8.2 边缘优化原则

1. **先模糊后阈值**:模糊可减少噪点
2. **适度扩展**:grow 1-2 像素可覆盖边缘瑕疵
3. **对比度调整**:增强遮罩对比度
4. **避免过度处理**:过度 blur/erode 会损失细节

### 8.3 遮罩运算顺序

```python
# 正确的运算顺序示例:
# (MatteA AND MatteB) - MatteC

# 第一步:先计算 A AND B
step1 = matte_intersect(session, matte_a, matte_b)

# 第二步:再减去 C
final = matte_subtract(session, step1, matte_c)

# 顺序很重要!
# 错误:先 A - C,再 AND B,结果不同
```

### 8.4 性能建议

```python
# 合并遮罩运算:能在一个节点完成的不要用多个
# 错误:提取亮度 → 单独模糊节点 → 单独对比度节点
# 正确:在 Matte 节点内同时设置 blur 和 contrast

# 缓存遮罩:静态遮罩渲染一次后缓存
# 避免在每帧重新计算相同的遮罩
```

### 8.5 调试技巧

```python
def temp_view_matte(matte_node, session):
    """临时查看遮罩节点输出"""
    # 创建临时 Output 节点
    temp_out = Node("Output")
    temp_out.label = "TEMP_View"
    session.addNode(temp_out)
    temp_out.inputs[0].connect(matte_node.outputs[0])
    return temp_out

def cleanup_temp_outputs(session, prefix="TEMP_"):
    """清理临时输出节点"""
    for i in range(session.numNodes - 1, -1, -1):
        n = session.node(i)
        if n.label.startswith(prefix):
            n.remove()
```

---

## 附录:遮罩运算速查表

| 运算 | 数学表示 | 结果范围 | 典型用途 |
|------|----------|----------|----------|
| Union | max(A, B) | [0, 1] | 扩大遮罩范围 |
| Intersect | min(A, B) | [0, 1] | 限制作用区域 |
| Difference | \|A - B\| | [0, 1] | 差异检测 |
| Subtract | max(A - B, 0) | [0, 1] | 打孔、排除区域 |
| Invert | 1 - A | [0, 1] | 反选 |
| Multiply | A × B | [0, 1] | 软交集 |

> **提示**:复杂遮罩组合时,先用简单形状测试运算逻辑,确认无误后再应用到实际遮罩。

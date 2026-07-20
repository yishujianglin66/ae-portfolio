# Silhouette 笔刷参数与压力感应

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: Paint 笔刷参数详解，包括大小、硬度、流量、不透明度等核心参数，以及数位板压力感应配置与自定义笔刷预设。

## 目录

1. [笔刷参数总览](#一笔刷参数总览)
2. [笔刷大小与形状](#二笔刷大小与形状)
3. [硬度与边缘控制](#三硬度与边缘控制)
4. [流量与不透明度](#四流量与不透明度)
5. [压力感应配置](#五压力感应配置)
6. [自定义笔刷预设](#六自定义笔刷预设)
7. [笔刷模式详解](#七笔刷模式详解)
8. [参数组合策略](#八参数组合策略)

---

## 一、笔刷参数总览

### 1.1 核心参数列表

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| brush.size | float | 25.0 | 1-500 | 笔刷大小（像素） |
| brush.hardness | float | 0.5 | 0.0-1.0 | 笔刷硬度 |
| brush.flow | float | 1.0 | 0.0-1.0 | 笔刷流量 |
| brush.opacity | float | 1.0 | 0.0-1.0 | 笔刷不透明度 |
| brush.shape | string | "circle" | circle/square/ellipse | 笔刷形状 |
| brush.angle | float | 0.0 | 0-360 | 笔刷角度 |
| brush.spacing | float | 0.25 | 0.01-1.0 | 笔刷间距 |

### 1.2 高级参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| mode | string | "clone" | 笔刷模式: clone/repair/erase |
| sampleOffset | [float, float] | [0,0] | 采样偏移 |
| cloneSource | string | "current" | 克隆源类型 |
| propagation | string | "tracked" | 传播模式 |
| colorMatch | bool | false | 色彩匹配 |
| texturePreserve | bool | false | 纹理保留 |
| motionBlur | bool | false | 运动模糊 |

### 1.3 参数关系图

```
brush.size (大小)
    ├── brush.hardness (边缘硬度)
    ├── brush.flow (单次流量)
    ├── brush.opacity (总体不透明度)
    └── brush.shape (形状)
         ├── brush.angle (角度)
         └── brush.spacing (间距)
```

---

## 二、笔刷大小与形状

### 2.1 笔刷大小

```python
# 设置笔刷大小
paint.property("brush.size").setValue(25.0, 0)  # 25像素

# 根据修复任务调整大小
size_presets = {
    "fine_detail": 3.0,     # 精细细节
    "small_flaw": 8.0,      # 小瑕疵
    "medium_repair": 20.0,  # 中等修复
    "large_area": 50.0,     # 大面积
    "broad_stroke": 100.0,  # 粗略笔触
}
```

### 2.2 笔刷形状

| 形状 | 适用场景 | 说明 |
|------|---------|------|
| circle | 通用 | 圆形笔刷，最常用 |
| square | 直线边缘 | 方形笔刷，适合规则边缘 |
| ellipse | 曲线修复 | 椭圆形，适合曲线区域 |

```python
# 设置笔刷形状
paint.property("brush.shape").setValue("circle", 0)
paint.property("brush.angle").setValue(45.0, 0)  # 椭圆角度
```

### 2.3 笔刷间距

```python
# 笔刷间距控制
paint.property("brush.spacing").setValue(0.25, 0)  # 默认间距
# 0.01 = 连续笔触（无间距）
# 0.25 = 标准间距
# 1.0 = 最大间距（点状效果）
```

---

## 三、硬度与边缘控制

### 3.1 硬度参数详解

硬度控制笔刷边缘的过渡程度：

| 硬度值 | 效果 | 适用场景 |
|--------|------|---------|
| 0.0-0.2 | 极软边缘 | 渐变背景、大面积融合 |
| 0.2-0.4 | 软边缘 | 自然过渡、皮肤修复 |
| 0.4-0.6 | 中等硬度 | 通用修复、多数场景 |
| 0.6-0.8 | 硬边缘 | 边缘清晰、物体擦除 |
| 0.8-1.0 | 极硬边缘 | 精确修复、细节处理 |

```python
# 不同硬度应用
paint.property("brush.hardness").setValue(0.3, 0)  # 软边缘
paint.property("brush.hardness").setValue(0.5, 0)  # 中等
paint.property("brush.hardness").setValue(0.8, 0)  # 硬边缘
```

### 3.2 边缘羽化

```python
# 通过低硬度实现边缘羽化
paint.property("brush.hardness").setValue(0.2, 0)
paint.property("brush.size").setValue(30.0, 0)
# 效果：边缘有20%的过渡区域
```

### 3.3 抗锯齿

```python
# 启用抗锯齿
paint.property("antialias").setValue(0.8, 0)  # 抗锯齿强度
```

---

## 四、流量与不透明度

### 4.1 流量 vs 不透明度

| 参数 | 说明 | 效果 |
|------|------|------|
| brush.flow | 单次绘制的流量 | 控制每次笔触的"湿润度" |
| brush.opacity | 总体不透明度 | 控制最终效果的最大强度 |

### 4.2 流量参数

```python
# 流量设置
paint.property("brush.flow").setValue(0.5, 0)  # 50%流量
# 低流量：多次叠加才能达到完整效果
# 高流量：一次绘制即达到完整效果
```

### 4.3 不透明度参数

```python
# 不透明度设置
paint.property("brush.opacity").setValue(0.8, 0)  # 80%不透明度
# 0.0 = 完全透明
# 0.5 = 半透明
# 1.0 = 完全不透明
```

### 4.4 组合应用

| 效果 | flow | opacity | 说明 |
|------|------|---------|------|
| 轻柔叠加 | 0.2 | 0.3 | 多次叠加，自然过渡 |
| 标准修复 | 0.8 | 1.0 | 一次到位 |
| 精细控制 | 0.3 | 0.6 | 适中，可调整 |
| 强力擦除 | 1.0 | 1.0 | 完全擦除 |

---

## 五、压力感应配置

### 5.1 数位板支持

Silhouette 支持主流数位板（Wacom、Huion 等）的压力感应：

```python
# 启用压力感应
paint.property("pressureSensitive").setValue(true, 0)
paint.property("pressureCurve").setValue("linear", 0)  # 压力曲线
paint.property("pressureMin").setValue(0.1, 0)  # 最小压力
paint.property("pressureMax").setValue(1.0, 0)  # 最大压力
```

### 5.2 压力映射参数

| 参数 | 控制内容 | 推荐值 |
|------|---------|--------|
| pressureSize | 笔刷大小 | true |
| pressureOpacity | 不透明度 | true |
| pressureFlow | 流量 | false |
| pressureHardness | 硬度 | false |

```python
# 压力映射配置
paint.property("pressureSize").setValue(true, 0)    # 压力控制大小
paint.property("pressureOpacity").setValue(true, 0)  # 压力控制不透明度
paint.property("pressureFlow").setValue(false, 0)    # 流量恒定
paint.property("pressureHardness").setValue(false, 0)  # 硬度恒定
```

### 5.3 压力曲线

| 曲线类型 | 效果 | 适用场景 |
|---------|------|---------|
| linear | 线性响应 | 通用 |
| ease-in | 轻压敏感 | 精细控制 |
| ease-out | 重压敏感 | 强力修复 |
| custom | 自定义曲线 | 特殊需求 |

```python
# 自定义压力曲线
paint.property("pressureCurve").setValue("custom", 0)
paint.property("pressureCurvePoints").setValue(
    [[0.0, 0.0], [0.3, 0.2], [0.7, 0.8], [1.0, 1.0]], 0
)
```

### 5.4 倾斜感应

```python
# 启用倾斜感应（支持的数位板）
paint.property("tiltSensitive").setValue(true, 0)
paint.property("tiltMax").setValue(60.0, 0)  # 最大倾斜角度
paint.property("tiltShape").setValue(true, 0)  # 倾斜影响笔刷形状
```

---

## 六、自定义笔刷预设

### 6.1 创建笔刷预设

```python
# 定义笔刷预设
brush_presets = {
    "soft_clone": {
        "brush.size": 30.0,
        "brush.hardness": 0.3,
        "brush.flow": 0.6,
        "brush.opacity": 0.8,
        "mode": "clone",
    },
    "hard_repair": {
        "brush.size": 10.0,
        "brush.hardness": 0.8,
        "brush.flow": 0.9,
        "brush.opacity": 1.0,
        "mode": "repair",
    },
    "fine_detail": {
        "brush.size": 3.0,
        "brush.hardness": 0.9,
        "brush.flow": 0.5,
        "brush.opacity": 0.7,
        "mode": "clone",
    },
}

# 应用预设
def apply_preset(paint_node, preset_name):
    preset = brush_presets.get(preset_name)
    if preset:
        for param, value in preset.items():
            paint_node.property(param).setValue(value, 0)
        print(f"[SILHOUETTE] Applied preset: {preset_name}")
```

### 6.2 常用预设组合

| 预设名称 | 大小 | 硬度 | 流量 | 不透明度 | 模式 | 用途 |
|---------|------|------|------|---------|------|------|
| 软克隆 | 30 | 0.3 | 0.6 | 0.8 | clone | 大面积修复 |
| 硬修复 | 10 | 0.8 | 0.9 | 1.0 | repair | 精确修复 |
| 细节笔 | 3 | 0.9 | 0.5 | 0.7 | clone | 细节处理 |
| 渐变融合 | 50 | 0.1 | 0.3 | 0.5 | repair | 渐变背景 |
| 强力擦除 | 25 | 0.5 | 1.0 | 1.0 | erase | 物体擦除 |
| 轻柔修饰 | 15 | 0.4 | 0.4 | 0.6 | repair | 皮肤修饰 |

### 6.3 保存和加载预设

```python
import json

def save_preset(preset_name, paint_node):
    """保存当前笔刷设置为预设"""
    preset = {
        "brush.size": paint_node.property("brush.size").value,
        "brush.hardness": paint_node.property("brush.hardness").value,
        "brush.flow": paint_node.property("brush.flow").value,
        "brush.opacity": paint_node.property("brush.opacity").value,
        "mode": paint_node.property("mode").value,
    }
    with open(f"D:/presets/{preset_name}.json", "w") as f:
        json.dump(preset, f, indent=2)
    print(f"[SILHOUETTE] Saved preset: {preset_name}")

def load_preset(preset_name, paint_node):
    """加载预设到笔刷"""
    with open(f"D:/presets/{preset_name}.json", "r") as f:
        preset = json.load(f)
    for param, value in preset.items():
        paint_node.property(param).setValue(value, 0)
    print(f"[SILHOUETTE] Loaded preset: {preset_name}")
```

---

## 七、笔刷模式详解

### 7.1 Clone 模式（克隆）

```python
paint.property("mode").setValue("clone", 0)
```

- **工作原理**: 从源位置复制像素到目标位置
- **适用场景**: 简单背景、规则纹理
- **关键参数**: sampleOffset（采样偏移）

### 7.2 Repair 模式（修复）

```python
paint.property("mode").setValue("repair", 0)
paint.property("colorMatch").setValue(true, 0)
```

- **工作原理**: 智能融合源像素与目标像素
- **适用场景**: 复杂纹理、需要色彩匹配
- **关键参数**: colorMatch、colorRange

### 7.3 Erase 模式（擦除）

```python
paint.property("mode").setValue("erase", 0)
```

- **工作原理**: 擦除已绘制的笔触
- **适用场景**: 修正错误、去除多余修复
- **关键参数**: brush.size、brush.opacity

### 7.4 模式对照

| 模式 | 优势 | 劣势 | 推荐场景 |
|------|------|------|---------|
| Clone | 速度快、效果可控 | 不适合复杂纹理 | 简单背景 |
| Repair | 自动融合、色彩匹配 | 计算量大 | 复杂场景 |
| Erase | 非破坏性擦除 | 仅擦除笔触 | 修正错误 |

---

## 八、参数组合策略

### 8.1 按任务类型选择参数

#### 威亚去除

```python
# 威亚去除参数组合
paint.property("brush.size").setValue(15.0, 0)
paint.property("brush.hardness").setValue(0.4, 0)
paint.property("brush.flow").setValue(0.7, 0)
paint.property("brush.opacity").setValue(0.9, 0)
paint.property("mode").setValue("clone", 0)
paint.property("propagation").setValue("tracked", 0)
```

#### 皮肤修复

```python
# 皮肤修复参数组合
paint.property("brush.size").setValue(8.0, 0)
paint.property("brush.hardness").setValue(0.6, 0)
paint.property("brush.flow").setValue(0.5, 0)
paint.property("brush.opacity").setValue(0.7, 0)
paint.property("mode").setValue("repair", 0)
paint.property("colorMatch").setValue(true, 0)
```

#### 物体擦除

```python
# 物体擦除参数组合
paint.property("brush.size").setValue(40.0, 0)
paint.property("brush.hardness").setValue(0.3, 0)
paint.property("brush.flow").setValue(0.8, 0)
paint.property("brush.opacity").setValue(1.0, 0)
paint.property("mode").setValue("clone", 0)
paint.property("propagation").setValue("tracked", 0)
```

### 8.2 参数调优建议

| 问题 | 调整方向 | 具体参数 |
|------|---------|---------|
| 边缘过硬 | 降低硬度 | brush.hardness ↓ |
| 效果太弱 | 提高不透明度 | brush.opacity ↑ |
| 一次过强 | 降低流量 | brush.flow ↓ |
| 边缘不齐 | 减小间距 | brush.spacing ↓ |
| 色彩不匹配 | 启用色彩匹配 | colorMatch=true |

### 8.3 工作流程建议

```
1. 选择合适的笔刷预设
2. 启用压力感应（如有数位板）
3. 先用低不透明度试探
4. 根据效果逐步调整参数
5. 多次叠加达到理想效果
6. 使用 Erase 模式修正错误
```

---

## 总结

笔刷参数是 Paint 修复的核心，关键要点：

1. **参数理解**: 理解大小、硬度、流量、不透明度的区别
2. **压力感应**: 启用数位板压力感应，实现自然笔触
3. **预设管理**: 创建并保存常用预设，提高工作效率
4. **模式选择**: 根据场景选择 Clone/Repair/Erase 模式
5. **参数调优**: 根据效果反馈逐步调整参数

通过合理组合笔刷参数，可以实现从精细细节修复到大面积擦除的各类任务，达到专业级修复效果。

# Silhouette X-Spline与Bézier曲线详解

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 深入对比 Silhouette 两大样条线体系（X-Spline 与 Bézier）的创建、编辑、参数与适用场景，给出代码示例与转换策略。

## 目录
1. [样条线体系总览](#一样条线体系总览)
2. [X-Spline 详解](#二x-spline-详解)
3. [Bézier 曲线详解](#三bézier-曲线详解)
4. [参数对比表](#四参数对比表)
5. [适用场景对比](#五适用场景对比)
6. [样条线转换方法](#六样条线转换方法)
7. [代码示例](#七代码示例)
8. [常见问题与最佳实践](#八常见问题与最佳实践)

---

## 一、样条线体系总览

Silhouette 的 RotoNode 支持多种形状类型，其中最核心、最常用的两种样条线为：

| 样条类型 | 数学基础 | 控制方式 | 主要用途 |
|---------|---------|---------|---------|
| **X-Spline** | 非均匀有理样条（类 NURBS） | 控制点 + 权重 | 有机形状、生物体、毛发边缘 |
| **Bézier** | 三次贝塞尔多项式 | 锚点 + 切线手柄 | 硬边物体、产品、建筑、机械 |

### 1.1 选择哲学

- **X-Spline** 强调"少点位、自然曲线"——通过权重调节影响范围，控制点数量通常是 Bézier 的 1/2 到 1/3。
- **Bézier** 强调"精确控制、可预测"——每个锚点的入/出手柄独立调节，适合需要像素级精度的硬边。
- 复杂物体可混用：身体用 X-Spline，硬边配件（手表、眼镜）用 Bézier。

---

## 二、X-Spline 详解

### 2.1 创建方式

```python
from fx import *

# 通过 RotoNode 创建 X-Spline 对象
roto = Node("RotoNode")
roto.label = "X_Spline_Demo"
session.addNode(roto)

# createObject 是 Silhouette 内建函数，在 RotoNode 上下文中创建形状
shape = roto.createObject("X-Spline")
shape.name = "Body"
```

### 2.2 控制点结构

X-Spline 每个控制点（Control Point）包含：
- **position**：二维坐标 `(x, y)`，单位像素
- **weight**：权重值 `0.0 ~ 1.0`
  - `1.0` —— 直角（紧贴控制点）
  - `0.5` —— 平滑（默认）
  - `0.0` —— 极度松弛（曲线远离控制点）

```python
# 添加控制点
shape.addPoint((100, 200))
shape.addPoint((300, 150))
shape.addPoint((450, 350))

# 修改权重（让中间点更平滑）
shape.points[1].weight = 0.3
```

### 2.3 关键参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `points` | list | [] | 控制点列表 |
| `closed` | bool | true | 是否闭合（Roto 通常闭合） |
| `feather` | float | 0.0 | 整体羽化（像素） |
| `featherFalloff` | float | 0.5 | 羽化衰减曲线 |
| `blur` | float | 0.0 | 边缘模糊 |
| `inverted` | bool | false | 反转该形状 |
| `opacity` | float | 1.0 | 形状不透明度 |
| `color` | tuple | (1,1,1) | 形状渲染色 |

### 2.4 编辑模式

- **Add Point**：在曲线上点击空白处自动插入，自动保持曲率连续。
- **Delete Point**：选中点按 Delete，曲线自动重连。
- **Weight 调节**：右键点 → Set Weight → 0/0.25/0.5/0.75/1。
- **Break Tangent**：Alt + 拖拽，打破平滑，形成尖角。

### 2.5 X-Spline 优势

1. **点位少**：复杂身体轮廓 8-15 点足够，Bézier 需 20-30 点。
2. **平滑度高**：权重机制天然产生 C2 连续曲线。
3. **动画稳定**：点少 → 关键帧少 → 形变抖动概率低。
4. **学习成本低**：无需手柄方向思维。

---

## 三、Bézier 曲线详解

### 3.1 创建方式

```python
shape = roto.createObject("Bezier")
shape.name = "HardEdge_Product"
```

### 3.2 控制点结构

每个 Bézier 锚点包含：
- **position**：锚点位置 `(x, y)`
- **inTangent**：入方向手柄向量 `(dx, dy)`
- **outTangent**：出方向手柄向量 `(dx, dy)`

```python
# 添加带手柄的锚点
shape.addPoint((100, 200), inTangent=(-30, 0), outTangent=(30, 0))
shape.addPoint((300, 150), inTangent=(-40, 10), outTangent=(40, -10))
```

### 3.3 关键参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `points` | list | [] | 锚点列表 |
| `closed` | bool | true | 闭合 |
| `feather` | float | 0.0 | 整体羽化 |
| `perPointFeather` | bool | false | 启用逐点羽化 |
| `blur` | float | 0.0 | 边缘模糊 |
| `smoothness` | float | 1.0 | 曲线平滑度 |

### 3.4 手柄操作模式

- **Smooth Point**：默认，入/出手柄对称联动。
- **Corner Point**：手柄长度为 0，形成尖角。
- **Bezier Corner**：入/出手柄独立调节（类似 Photoshop 钢笔）。

```python
# 角点（手表的方角）
shape.points[2].inTangent = (0, 0)
shape.points[2].outTangent = (0, 0)

# 独立手柄
shape.points[3].inTangent = (-20, 5)
shape.points[3].outTangent = (35, -15)
shape.points[3].linkHandles = False
```

### 3.5 逐点羽化

Bézier 独有的"per-point feather"允许每个锚点单独设置羽化距离与方向：

```python
shape.property("perPointFeather").setValue(true, 0)

# 第一个点向内羽化 5px
shape.points[0].feather = 5.0
shape.points[0].featherAngle = 0

# 第二个点向外羽化 12px（如毛发飘散区域）
shape.points[1].feather = 12.0
shape.points[1].featherAngle = 180
```

---

## 四、参数对比表

| 维度 | X-Spline | Bézier |
|------|----------|--------|
| 数学模型 | 类 NURBS，权重驱动 | 三次多项式，手柄驱动 |
| 控制点数 | 少（8-15） | 多（20-40） |
| 曲线平滑度 | 天然 C2 连续 | 取决于手柄配置 |
| 硬边能力 | 一般（权重=1 可硬） | 极佳（Corner Point） |
| 逐点羽化 | 不支持 | 支持 |
| 关键帧稳定性 | 高 | 中（点多多易抖） |
| 学习曲线 | 平缓 | 较陡 |
| 文件体积 | 小 | 大 |
| 与 AE/Mocha 互导 | 部分 | 完全兼容 |

---

## 五、适用场景对比

### 5.1 优先选 X-Spline

| 场景 | 原因 |
|------|------|
| 人物身体、面部 | 有机曲线，点位少利于动画 |
| 动物轮廓 | 毛发边缘不需要硬边 |
| 衣物褶皱 | 平滑过渡 |
| 云雾、烟雾轮廓 | 模糊边界 |
| 长时段跟踪 | 点少 → 关键帧少 → 效率高 |

### 5.2 优先选 Bézier

| 场景 | 原因 |
|------|------|
| 产品广告（手机、瓶身） | 需要绝对硬边和精确角点 |
| 建筑物 | 直线 + 直角 |
| 车辆 | 机械曲线 |
| UI 元素、Logo | 几何精度 |
| 需逐点羽化的混合边缘 | 仅 Bézier 支持 |
| 与 AE 钢笔工具互导 | AE 原生 Bézier |

### 5.3 混合使用建议

复杂角色（如戴眼镜的人物）：
- 头部轮廓 → X-Spline（8-10 点）
- 眼镜框 → Bézier（4 点角点）
- 衣领 → X-Spline
- 胸牌 → Bézier

---

## 六、样条线转换方法

### 6.1 X-Spline → Bézier

```python
# 转换为 Bézier（位置保留，手柄根据曲率自动生成）
shape.convertTo("Bezier")

# 转换后通常需要手工微调手柄，因为权重无法 1:1 映射到手柄
```

**注意事项**：
- 权重 `1.0` 的点 → 转为 Corner Point（手柄长度 0）。
- 权重 `0.0` 的点 → 手柄自动延长，可能过冲。
- 转换是**不可逆**的，建议先复制一份原始 X-Spline。

### 6.2 Bézier → X-Spline

```python
shape.convertTo("X-Spline")
```

- 锚点位置保留为控制点。
- 手柄长度被压缩为权重值（长手柄 → 低权重）。
- Corner Point → 权重 1.0。

### 6.3 批量转换脚本

```python
from fx import *

def convert_all_shapes(roto_node, target_type="Bezier"):
    """批量转换 RotoNode 中所有形状"""
    shapes = roto_node.objects  # 获取所有形状对象
    converted = 0
    for shape in shapes:
        if shape.type != target_type:
            # 备份原形状
            backup = shape.duplicate()
            backup.name = shape.name + "_backup"
            backup.visible = false

            shape.convertTo(target_type)
            converted += 1
            print(f"[CONVERT] {shape.name}: {shape.type} -> {target_type}")

    print(f"[CONVERT] 完成，共转换 {converted} 个形状")
    return converted
```

---

## 七、代码示例

### 7.1 X-Spline 人物头部轮廓

```python
from fx import *

proj = activeProject() or Project()
activate(proj)
session = activeSession() or Session()
session.label = "X_Spline_Head"
activate(session)
proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/character.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

roto = Node("RotoNode")
roto.label = "Head_Roto"
roto.property("alpha.blur").setValue(0.3, 0)
roto.property("antialias").setValue(1.0, 0)
session.addNode(roto)

# 创建 X-Spline 头部轮廓
head = roto.createObject("X-Spline")
head.name = "Head_Head"
head.closed = true

# 8 个控制点环绕头部
head_points = [
    (960, 200),   # 头顶
    (1100, 280),  # 右额
    (1150, 450),  # 右脸
    (1100, 620),  # 右下颌
    (960, 700),   # 下巴
    (820, 620),   # 左下颌
    (770, 450),   # 左脸
    (820, 280),   # 左额
]
for pt in head_points:
    head.addPoint(pt)

# 头顶和下巴略微收紧，脸部更平滑
head.points[0].weight = 0.7  # 头顶
head.points[4].weight = 0.6  # 下巴
head.points[2].weight = 0.3  # 右脸（更圆）
head.points[6].weight = 0.3  # 左脸

head.property("feather").setValue(1.5, 0)
head.property("blur").setValue(0.2, 0)

src.outputs[0].connect(roto.inputs[1])

print("[SILHOUETTE] X-Spline 头部轮廓已创建")
print(f"[SILHOUETTE] 控制点数: {len(head.points)}")
```

### 7.2 Bézier 产品硬边

```python
from fx import *

proj = activeProject() or Project()
activate(proj)
session = activeSession() or Session()
session.label = "Bezier_Product"
activate(session)
proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/product.mov", 0)
src.property("frameRate").setValue(30.0, 0)
session.addNode(src)

roto = Node("RotoNode")
roto.label = "Phone_Roto"
roto.property("alpha.blur").setValue(0.1, 0)
roto.property("antialias").setValue(1.0, 0)
session.addNode(roto)

# 手机轮廓 - 4 角硬边 Bézier
phone = roto.createObject("Bezier")
phone.name = "Phone_Body"
phone.closed = true

# 4 个角点，手柄为 0（纯硬边）
corners = [
    (400, 300),   # 左上
    (800, 300),   # 右上
    (800, 900),   # 右下
    (400, 900),   # 左下
]
for c in corners:
    phone.addPoint(c, inTangent=(0, 0), outTangent=(0, 0))

phone.property("feather").setValue(0.0, 0)
phone.property("perPointFeather").setValue(false, 0)

src.outputs[0].connect(roto.inputs[1])

print("[SILHOUETTE] Bézier 硬边产品轮廓已创建")
```

### 7.3 混合样条线复杂物体

```python
from fx import *

def create_mixed_character(session, src_node):
    """创建带眼镜的人物：头部 X-Spline + 眼镜 Bézier"""
    roto = Node("RotoNode")
    roto.label = "Character_Mixed"
    roto.property("alpha.blur").setValue(0.4, 0)
    session.addNode(roto)

    # === 头部：X-Spline ===
    head = roto.createObject("X-Spline")
    head.name = "Head"
    head_pts = [(960, 200), (1150, 450), (960, 720), (770, 450)]
    for pt in head_pts:
        head.addPoint(pt)
    for p in head.points:
        p.weight = 0.4
    head.property("feather").setValue(2.0, 0)

    # === 眼镜框：Bézier ===
    glasses = roto.createObject("Bezier")
    glasses.name = "Glasses_Frame"
    # 左镜片
    left_pts = [(820, 440), (900, 440), (900, 480), (820, 480)]
    for pt in left_pts:
        glasses.addPoint(pt, inTangent=(0, 0), outTangent=(0, 0))
    # 右镜片（同一形状内追加）
    right_pts = [(1020, 440), (1100, 440), (1100, 480), (1020, 480)]
    for pt in right_pts:
        glasses.addPoint(pt, inTangent=(0, 0), outTangent=(0, 0))
    glasses.property("feather").setValue(0.0, 0)

    # 眼镜优先级高于头部（渲染在上层）
    glasses.inverted = false
    head.inverted = false

    src_node.outputs[0].connect(roto.inputs[1])
    return roto, head, glasses
```

---

## 八、常见问题与最佳实践

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| X-Spline 边缘不够硬 | 权重过高变圆 | 将对应点权重设为 `1.0` |
| Bézier 手柄过冲 | 手柄太长 | 手柄长度 ≤ 相邻点距离的 1/3 |
| X-Spline 转 Bézier 后变形 | 权重映射不精确 | 转换后手工调整手柄 |
| Bézier 动画抖动 | 点太多 | 删除冗余点，保留关键转折 |
| 直线段弯曲 | 手柄不为 0 | 设为 Corner Point |
| 曲线鼓包 | 三个点近似共线 | 删除中间点或降低权重 |

### 8.2 最佳实践

1. **先 X-Spline 后 Bézier**：不确定时先用 X-Spline 起稿，需要硬边再转换。
2. **点位最小化**：能用 8 点完成的绝不用 12 点，动画更稳定。
3. **关键转折点优先**：在曲率最大变化处放点（下巴、肩膀、肘部）。
4. **混合分层**：同一物体的不同部位用不同样条类型，分层管理。
5. **转换前备份**：`shape.duplicate()` 保留原始形状，避免不可逆损失。
6. **权重档位化**：建立 0/0.25/0.5/0.75/1.0 五档标准，统一团队风格。

### 8.3 性能建议

- 单个 RotoNode 内形状数建议 ≤ 30，超过则拆分多 Node。
- Bézier 锚点总数建议 ≤ 200/Node，避免交互卡顿。
- 复杂项目启用 `session.property("proxy").setValue(true, 0)` 代理预览。

---

## 相关文档

- [Silhouette 形状层与关键帧动画](Silhouette%20形状层与关键帧动画.md)
- [Silhouette 边缘优化与运动模糊](Silhouette%20边缘优化与运动模糊.md)
- [Silhouette 硬边与柔边遮罩技巧](Silhouette%20硬边与柔边遮罩技巧.md)
- [Silhouette Roto遮罩完全指南](Silhouette%20Roto遮罩完全指南.md)

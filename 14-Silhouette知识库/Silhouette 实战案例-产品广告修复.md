# Silhouette 实战案例-产品广告修复

> 分类: 实战案例
> 更新日期: 2026-07-11
> 概述: 产品广告中的瑕疵修复、色彩校正与输出完整案例

## 目录
---

- [一、案例背景](#一案例背景)
- [二、素材分析](#二素材分析)
- [三、修复策略](#三修复策略)
- [四、Paint 修复执行](#四paint-修复执行)
- [五、色彩校正](#五色彩校正)
- [六、质量控制](#六质量控制)
- [七、输出与交付](#七输出与交付)
- [八、自动化脚本](#八自动化脚本)

---

## 一、案例背景

### 1.1 项目信息

- **项目名称**：某高端手表品牌广告
- **镜头编号**：AD_WATCH_001
- **时长**：15 秒（450 帧 @30fps）
- **分辨率**：4K（3840×2160）
- **交付格式**：ProRes 422 HQ
- **任务**：手表产品修复与美化

### 1.2 修复需求

1. **去除灰尘**：表盘上有微小灰尘颗粒（约 20 处）
2. **修复反光**：表盘玻璃有不需要的反光
3. **标签去除**：表带上有品牌标签需去除
4. **色彩统一**：不同镜头间色彩需统一
5. **皮肤美化**：模特手腕处皮肤瑕疵修复

### 1.3 团队与周期

- **Artist**：1 名 Senior Paint Artist
- **周期**：1 天（8 工时）

---

## 二、素材分析

### 2.1 素材清单

| 镜头 | 时长 | 内容 | 主要问题 |
|------|------|------|---------|
| SH001 | 3秒 | 手表特写 | 灰尘、反光 |
| SH002 | 4秒 | 模特佩戴 | 皮肤瑕疵、标签 |
| SH003 | 4秒 | 手表背面 | 轻微划痕 |
| SH004 | 4秒 | 多角度展示 | 色彩不一致 |

### 2.2 问题定位

```python
from fx import *

def analyze_issues(footage_path):
    """分析修复需求"""
    proj = Project()
    activate(proj)
    session = Session()
    session.label = "Analysis"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    session.addNode(src)

    issues = {
        "dust": [
            {"frame": 15, "x": 1200, "y": 800, "size": 5},
            {"frame": 32, "x": 1450, "y": 920, "size": 3},
            {"frame": 48, "x": 1100, "y": 750, "size": 4},
            # ... 更多
        ],
        "reflection": [
            {"frame": 20, "x": 1300, "y": 850, "size": 50}
        ],
        "label": [
            {"frame": 90, "x": 1600, "y": 1200, "size": 80}
        ],
        "skin": [
            {"frame": 105, "x": 1400, "y": 1100, "size": 15}
        ]
    }

    for category, items in issues.items():
        print(f"{category}: {len(items)} 处")

    return issues

issues = analyze_issues("D:/footage/AD_WATCH_001.exr")
```

---

## 三、修复策略

### 3.1 修复优先级

| 优先级 | 问题 | 原因 |
|--------|------|------|
| P0 | 灰尘去除 | 影响产品形象 |
| P0 | 标签去除 | 法律要求 |
| P1 | 反光修复 | 影响美观 |
| P1 | 皮肤美化 | 客户要求 |
| P2 | 色彩统一 | 整体质量 |

### 3.2 修复方法选择

| 问题 | 方法 | 工具 |
|------|------|------|
| 灰尘 | 克隆修复 | Clone Brush |
| 反光 | 频率分离 | Frequency Separate |
| 标签 | 内容填充 | AI Inpainting |
| 皮肤 | 频率分离 + 克隆 | Paint + AI |
| 色彩 | 色彩节点 | Color Node |

---

## 四、Paint 修复执行

### 4.1 灰尘去除

```python
from fx import *

def setup_dust_removal(session, src):
    """设置灰尘去除"""
    paint = Node("PaintNode")
    paint.label = "Dust_Removal"
    session.addNode(paint)

    # 克隆设置
    paint.property("cloneSource").setValue("frame_offset", 0)
    paint.property("cloneOffset").setValue(0, 0)  # 同帧克隆
    paint.property("brushSize").setValue(10, 0)
    paint.property("brushHardness").setValue(0.9, 0)  # 硬边

    src.outputs[0].connect(paint.inputs[1])
    return paint

def remove_dust(paint, dust_list):
    """批量去除灰尘"""
    session = activeSession()

    for dust in dust_list:
        frame = dust["frame"]
        x, y = dust["x"], dust["y"]
        size = dust["size"]

        session.currentFrame = frame

        # 创建修复笔触
        stroke = paint.createStroke()
        stroke.setPoint(0, x - size, y)
        stroke.setPoint(1, x + size, y)
        stroke.setSize(size * 2)
        stroke.setOpacity(1.0)
        stroke.setKeyframe(frame)

        print(f"第 {frame} 帧灰尘已去除 ({x}, {y})")

dust_paint = setup_dust_removal(session, src)
remove_dust(dust_paint, issues["dust"])
```

### 4.2 标签去除（AI Inpainting）

```python
def remove_label(session, src, label_info):
    """使用 AI 去除标签"""
    # 创建标签区域的遮罩
    roto = Node("RotoNode")
    roto.label = "Label_Mask"
    session.addNode(roto)

    # 绘制标签区域
    session.currentFrame = label_info["frame"]
    shape = roto.createShape()
    x, y = label_info["x"], label_info["y"]
    size = label_info["size"]
    shape.addPoint(x - size, y - size)
    shape.addPoint(x + size, y - size)
    shape.addPoint(x + size, y + size)
    shape.addPoint(x - size, y + size)
    shape.setKeyframe(label_info["frame"])

    # AI Inpainting
    try:
        from fx.ai import AIPaint
        ai = AIPaint()
        ai.setSource(src)
        ai.setMask(roto)
        ai.setMode("diffusion")
        ai.process(frameRange=[label_info["frame"], label_info["frame"] + 120])
        print("AI 标签去除完成")
    except Exception as e:
        print(f"AI 不可用，使用手动克隆: {e}")
        # 手动克隆...

remove_label(session, src, issues["label"][0])
```

### 4.3 反光修复

```python
def fix_reflection(session, src, reflection_info):
    """修复反光"""
    paint = Node("PaintNode")
    paint.label = "Reflection_Fix"
    session.addNode(paint)

    # 使用频率分离
    paint.property("mode").setValue("frequency_separate", 0)
    paint.property("frequencyRadius").setValue(10, 0)
    paint.property("brushSize").setValue(50, 0)
    paint.property("brushHardness").setValue(0.5, 0)

    src.outputs[0].connect(paint.inputs[1])

    # 修复反光区域
    session.currentFrame = reflection_info["frame"]
    stroke = paint.createStroke()
    x, y = reflection_info["x"], reflection_info["y"]
    size = reflection_info["size"]
    stroke.setPoint(0, x - size, y)
    stroke.setPoint(1, x + size, y)
    stroke.setSize(size * 2)
    stroke.setKeyframe(reflection_info["frame"])

    print("反光修复完成")

fix_reflection(session, src, issues["reflection"][0])
```

### 4.4 皮肤美化

```python
def beautify_skin(session, src, skin_info):
    """皮肤美化"""
    paint = Node("PaintNode")
    paint.label = "Skin_Beautify"
    session.addNode(paint)

    # 频率分离模式
    paint.property("mode").setValue("frequency_separate", 0)
    paint.property("frequencyRadius").setValue(15, 0)
    paint.property("brushSize").setValue(30, 0)
    paint.property("brushHardness").setValue(0.3, 0)
    paint.property("opacity").setValue(0.7, 0)  # 70% 不透明度

    # 时序跟踪
    paint.property("temporalTrack").setValue(True, 0)

    src.outputs[0].connect(paint.inputs[1])

    # 修复皮肤区域
    session.currentFrame = skin_info["frame"]
    stroke = paint.createStroke()
    x, y = skin_info["x"], skin_info["y"]
    size = skin_info["size"]
    stroke.setPoint(0, x - size, y)
    stroke.setPoint(1, x + size, y)
    stroke.setSize(size * 2)
    stroke.setKeyframe(skin_info["frame"])

    print("皮肤美化完成")

beautify_skin(session, src, issues["skin"][0])
```

---

## 五、色彩校正

### 5.1 色彩统一

```python
from fx import *

def setup_color_correction(session, paint_output):
    """设置色彩校正"""
    color = Node("ColorNode")
    color.label = "Color_Correction"
    session.addNode(color)

    # 基本调色
    color.property("brightness").setValue(0.0, 0)
    color.property("contrast").setValue(1.05, 0)  # 轻微提升对比度
    color.property("saturation").setValue(1.1, 0)  # 轻微提升饱和度

    # 色彩平衡
    color.property("shadow.red").setValue(0.0, 0)
    color.property("shadow.green").setValue(0.0, 0)
    color.property("shadow.blue").setValue(0.02, 0)  # 阴影偏冷

    color.property("highlight.red").setValue(0.02, 0)  # 高光偏暖
    color.property("highlight.green").setValue(0.0, 0)
    color.property("highlight.blue").setValue(-0.02, 0)

    # 连接
    paint_output.outputs[0].connect(color.inputs[0])

    return color

color_node = setup_color_correction(session, paint_node)
```

### 5.2 色彩匹配

```python
def match_color(session, target_color_values):
    """匹配目标色彩"""
    color = session.node("Color_Correction")

    # 设置目标色彩值
    for prop, value in target_color_values.items():
        color.property(prop).setValue(value, 0)

    print("色彩匹配完成")

# 目标色彩（参考镜头的色彩值）
target = {
    "brightness": 0.05,
    "contrast": 1.08,
    "saturation": 1.12,
    "gamma": 1.02
}
match_color(session, target)
```

---

## 六、质量控制

### 6.1 QC 检查清单

```python
def qc_product_ad(session):
    """产品广告 QC 检查"""
    checks = []

    # 检查修复完整性
    checks.append(check_all_issues_fixed(session))

    # 检查帧间一致性
    checks.append(check_temporal_consistency(session))

    # 检查色彩一致性
    checks.append(check_color_consistency(session))

    # 检查分辨率与帧率
    checks.append(check_technical_specs(session))

    # 生成报告
    report = "=== 产品广告 QC 报告 ===\n"
    for check in checks:
        status = "✅" if check["pass"] else "❌"
        report += f"{status} {check['name']}: {check['message']}\n"

    print(report)
    return all(c["pass"] for c in checks)

qc_product_ad(session)
```

### 6.2 重点检查项

- 灰尘去除后是否留痕
- 标签区域是否自然
- 反光修复是否影响表盘清晰度
- 皮肤美化是否过度
- 色彩是否与参考一致

---

## 七、输出与交付

### 7.1 输出设置

```python
from fx import *

def setup_output(session, color_node, output_path):
    """设置输出"""
    out = Node("OutputNode")
    out.label = "Final_Output"
    session.addNode(out)

    out.property("path").setValue(output_path.replace("\\", "/"), 0)

    # ProRes 422 HQ 格式
    out.property("format").setValue("mov", 0)
    out.property("codec").setValue("prores_422_hq", 0)

    # 4K 分辨率
    out.property("width").setValue(3840, 0)
    out.property("height").setValue(2160, 0)

    # 帧率
    out.property("frameRate").setValue(30, 0)

    # 帧范围
    out.property("startFrame").setValue(1, 0)
    out.property("endFrame").setValue(450, 0)

    # 色彩空间
    out.property("colorSpace").setValue("Rec.709", 0)

    # 连接
    color_node.outputs[0].connect(out.inputs[0])

    return out

output_node = setup_output(
    session,
    color_node,
    "D:/output/AD_WATCH_001/AD_WATCH_001_final_v002.mov"
)
```

---

## 八、自动化脚本

### 8.1 完整工作流

```python
"""
产品广告修复完整工作流
"""
from fx import *
import os

def create_product_ad_pipeline(
    footage_path,
    output_path,
    frame_rate=30.0
):
    """创建产品广告修复管线"""

    # 1. 创建项目
    print("=== 创建项目 ===")
    proj = Project()
    activate(proj)
    session = Session()
    session.label = "Product_Ad_Restore"
    activate(session)
    proj.addItem(session)

    # 2. 加载素材
    print("=== 加载素材 ===")
    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 3. 灰尘去除
    print("=== 灰尘去除 ===")
    dust_paint = Node("PaintNode")
    dust_paint.label = "Dust_Removal"
    dust_paint.property("cloneSource").setValue("frame_offset", 0)
    dust_paint.property("brushSize").setValue(10, 0)
    dust_paint.property("brushHardness").setValue(0.9, 0)
    session.addNode(dust_paint)
    src.outputs[0].connect(dust_paint.inputs[1])

    # 4. 标签去除
    print("=== 标签去除 ===")
    label_paint = Node("PaintNode")
    label_paint.label = "Label_Removal"
    label_paint.property("mode").setValue("ai_inpainting", 0)
    session.addNode(label_paint)
    dust_paint.outputs[0].connect(label_paint.inputs[1])

    # 5. 反光修复
    print("=== 反光修复 ===")
    reflection_paint = Node("PaintNode")
    reflection_paint.label = "Reflection_Fix"
    reflection_paint.property("mode").setValue("frequency_separate", 0)
    reflection_paint.property("frequencyRadius").setValue(10, 0)
    session.addNode(reflection_paint)
    label_paint.outputs[0].connect(reflection_paint.inputs[1])

    # 6. 皮肤美化
    print("=== 皮肤美化 ===")
    skin_paint = Node("PaintNode")
    skin_paint.label = "Skin_Beautify"
    skin_paint.property("mode").setValue("frequency_separate", 0)
    skin_paint.property("frequencyRadius").setValue(15, 0)
    skin_paint.property("temporalTrack").setValue(True, 0)
    session.addNode(skin_paint)
    reflection_paint.outputs[0].connect(skin_paint.inputs[1])

    # 7. 色彩校正
    print("=== 色彩校正 ===")
    color = Node("ColorNode")
    color.label = "Color_Correction"
    color.property("contrast").setValue(1.05, 0)
    color.property("saturation").setValue(1.1, 0)
    session.addNode(color)
    skin_paint.outputs[0].connect(color.inputs[0])

    # 8. 输出
    print("=== 配置输出 ===")
    out = Node("OutputNode")
    out.label = "Final_Output"
    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("mov", 0)
    out.property("codec").setValue("prores_422_hq", 0)
    out.property("colorSpace").setValue("Rec.709", 0)
    session.addNode(out)
    color.outputs[0].connect(out.inputs[0])

    print("\n=== 管线创建完成 ===")
    print(f"节点数: {session.numNodes}")
    print("下一步: 手动标记修复区域并执行")

    return proj, session

# 执行
if __name__ == "__main__":
    proj, session = create_product_ad_pipeline(
        "D:/footage/AD_WATCH_001.exr",
        "D:/output/AD_WATCH_001_final_v002.mov"
    )
```

---

## 九、总结

### 9.1 工时统计

| 任务 | 工时 |
|------|------|
| 素材分析 | 0.5h |
| 灰尘去除 | 2h |
| 标签去除 | 1.5h |
| 反光修复 | 1.5h |
| 皮肤美化 | 1h |
| 色彩校正 | 0.5h |
| QC | 1h |

### 9.2 关键经验

1. **频率分离**是产品修复的核心技术
2. **AI Inpainting**大幅提升大区域修复效率
3. **时序跟踪**保证帧间一致性
4. **色彩统一**需参考多个镜头
5. **QC 要逐项检查**：不能遗漏任何修复点

---

> 相关文档：
> - [[Silhouette 实战案例-人物抠像全流程]]
> - [[Silhouette Paint修复完全指南]]
> - [[Silhouette 行业标准与质量规范]]

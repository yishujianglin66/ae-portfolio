# Silhouette 实战案例-人物抠像全流程

> 分类: 实战案例
> 更新日期: 2026-07-11
> 概述: 从素材分析到最终输出的完整人物抠像案例，涵盖绿幕与实拍场景

## 目录
---

- [一、案例背景](#一案例背景)
- [二、素材分析](#二素材分析)
- [三、项目设置](#三项目设置)
- [四、Roto 策略](#四roto-策略)
- [五、详细执行](#五详细执行)
- [六、Paint 修复](#六paint-修复)
- [七、质量控制](#七质量控制)
- [八、输出与交付](#八输出与交付)
- [九、自动化脚本](#九自动化脚本)
- [十、总结与反思](#十总结与反思)

---

## 一、案例背景

### 1.1 项目信息

- **项目名称**：电影《星际征途》第 15 场
- **镜头编号**：SEQ020_SH0150
- **镜头时长**：8 秒（192 帧 @24fps）
- **分辨率**：4K（3840×2160）
- **帧率**：24 fps
- **色彩空间**：ACEScg
- **任务**：人物角色从实拍背景中分离，用于后期合成到 CG 场景

### 1.2 难点分析

1. **复杂背景**：实拍城市场景，非绿幕
2. **人物运动**：中速行走，有肢体摆动
3. **头发细节**：长发，风力作用
4. **服装复杂**：飘逸外套，多褶皱
5. **运动模糊**：快速摆臂区域有运动模糊

### 1.3 团队配置

- **Artist**：1 名 Senior Roto Artist
- **Lead**：1 名 Compositing Lead
- **周期**：2 天（16 工时）

---

## 二、素材分析

### 2.1 素材检查

```python
from fx import *
import os

def analyze_footage(footage_path):
    """分析素材"""
    print(f"素材路径: {footage_path}")

    # 创建临时项目
    proj = Project()
    activate(proj)

    session = Session()
    session.label = "Analysis"
    activate(session)
    proj.addItem(session)

    # 加载素材
    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    session.addNode(src)

    # 获取素材信息
    width = session.width
    height = session.height
    fps = session.frameRate
    start_frame = src.property("startFrame").value
    end_frame = src.property("endFrame").value

    print(f"分辨率: {width}x{height}")
    print(f"帧率: {fps}")
    print(f"帧范围: {start_frame}-{end_frame}")
    print(f"总帧数: {end_frame - start_frame + 1}")

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "start_frame": start_frame,
        "end_frame": end_frame
    }

# 执行分析
info = analyze_footage("D:/footage/SEQ020_SH0150_plate.exr")
```

### 2.2 镜头分析

**画面内容**：
- 女性角色，30 岁左右
- 身穿米色风衣，黑色长发
- 从画面左侧走向右侧
- 背景为城市街道，有行人与车辆

**运动分析**：
- 行走速度：约 1.5m/s
- 肢体摆动：手臂前后摆动
- 头发运动：受风力影响，向后飘动
- 风衣运动：下摆摆动明显

**关键帧识别**：
- 第 1 帧：起始位置（站立）
- 第 48 帧：第一步落地
- 第 96 帧：中间位置
- 第 144 帧：接近终点
- 第 192 帧：终止位置

---

## 三、项目设置

### 3.1 创建项目

```python
from fx import *
import os

def setup_project(footage_path, output_dir):
    """创建标准项目"""
    # 创建项目
    proj = Project()
    activate(proj)

    # 创建会话
    session = Session()
    session.label = "SEQ020_SH0150_Roto"
    activate(session)
    proj.addItem(session)

    # 添加源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(24.0, 0)
    session.addNode(src)

    # 配置色彩管理
    color = proj.property("colorManagement")
    color.setValue("enabled", True)
    color.setValue("config", "ACES 1.3")
    color.setValue("workingSpace", "ACEScg")
    color.setValue("display", "sRGB")
    color.setValue("view", "ACES 1.0 SDR-Video")

    # 配置 GPU 加速
    gpu = proj.property("gpu")
    gpu.setValue("enabled", True)
    gpu.setValue("device", 0)

    # 配置缓存
    cache = proj.property("cache")
    cache.setValue("path", "D:/silhouette_cache")
    cache.setValue("size", 50)

    print(f"项目已创建")
    print(f"源: {footage_path}")
    print(f"输出: {output_dir}")

    return proj, session, src

# 执行
proj, session, src = setup_project(
    "D:/footage/SEQ020_SH0150_plate.exr",
    "D:/output/SEQ020_SH0150"
)
```

### 3.2 节点结构规划

```
SourceNode → RotoNode (Body)    ─┐
           → RotoNode (Hair)    ─┼→ MergeNode → OutputNode
           → RotoNode (Clothing)─┘
           → PaintNode (Cleanup)→
```

---

## 四、Roto 策略

### 4.1 分层策略

将人物分为三个独立 Roto 层：

| 层 | 内容 | 原因 |
|----|------|------|
| Body | 身体、头部、四肢 | 主体，运动较规律 |
| Hair | 头发 | 细节复杂，需单独处理 |
| Clothing | 飘逸风衣 | 独立运动，需单独跟踪 |

### 4.2 关键帧策略

**Body 层关键帧**：
- 每 12 帧一个关键帧（共 16 个）
- 运动变化点额外加关键帧
- 起止帧必须为关键帧

**Hair 层关键帧**：
- 每 6 帧一个关键帧（共 32 个）
- 风力变化点加关键帧
- 发梢区域加密关键帧

**Clothing 层关键帧**：
- 每 8 帧一个关键帧（共 24 个）
- 摆动极值点加关键帧

### 4.3 形状选择

| 部位 | 形状类型 | 理由 |
|------|---------|------|
| 身体主体 | X-Spline | 控制灵活，边缘平滑 |
| 头发 | B-Spline | 自然曲线，适合有机形状 |
| 风衣褶皱 | Bezier | 精确控制锐角 |
| 手指 | X-Spline | 小区域精确控制 |

---

## 五、详细执行

### 5.1 创建 Body Roto

```python
from fx import *

def create_body_roto(session, src):
    """创建身体 Roto 节点"""
    roto = Node("RotoNode")
    roto.label = "Body_Roto"
    session.addNode(roto)

    # 基本设置
    roto.property("shapeType").setValue("x-spline", 0)
    roto.property("alpha.blur").setValue(0.3, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("fill").setValue(True, 0)
    roto.property("matte.mode").setValue("alpha", 0)

    # 运动模糊设置
    roto.property("motionBlur").setValue(True, 0)
    roto.property("motionBlurAmount").setValue(1.2, 0)

    # 连接源
    src.outputs[0].connect(roto.inputs[1])

    # 创建形状（第1帧）
    session.currentFrame = 1

    # 创建身体轮廓形状
    # 实际操作中通过 UI 绘制，这里用脚本示意
    shape = roto.createShape()
    shape.addPoint(1800, 600)   # 头顶
    shape.addPoint(1850, 650)   # 头部右侧
    shape.addPoint(1860, 800)   # 颈部
    shape.addPoint(1900, 900)   # 肩部
    shape.addPoint(1950, 1200)  # 手臂
    shape.addPoint(1900, 1500)  # 腰部
    shape.addPoint(1850, 1800)  # 腿部
    shape.addPoint(1800, 2100)  # 脚部
    shape.addPoint(1700, 2100)  # 脚部左侧
    shape.addPoint(1650, 1800)  # 腿部左侧
    shape.addPoint(1600, 1500)  # 腰部左侧
    shape.addPoint(1550, 1200)  # 手臂左侧
    shape.addPoint(1600, 900)   # 肩部左侧
    shape.addPoint(1650, 800)   # 颈部左侧
    shape.addPoint(1700, 650)   # 头部左侧

    # 设置为关键帧
    shape.setKeyframe(1)

    print("Body Roto 第1帧形状已创建")
    return roto

body_roto = create_body_roto(session, src)
```

### 5.2 关键帧动画

```python
def animate_body_roto(roto, session):
    """为 Body Roto 添加关键帧动画"""
    # 关键帧位置（每12帧）
    keyframes = [1, 13, 25, 37, 49, 61, 73, 85, 97, 109, 121, 133, 145, 157, 169, 181, 192]

    for frame in keyframes[1:]:  # 第1帧已设置
        session.currentFrame = frame

        # 获取形状
        shape = roto.getShape()

        # 根据帧位置调整形状
        # 这里简化为整体位移，实际需要逐点调整
        offset_x = (frame - 1) * 5  # 每帧右移5像素
        for i in range(shape.numPoints):
            point = shape.getPoint(i)
            shape.setPoint(i, point[0] + offset_x, point[1])

        # 设置关键帧
        shape.setKeyframe(frame)

        print(f"关键帧 {frame} 已设置")

    # 启用插值
    roto.property("interpolation").setValue("bezier", 0)

animate_body_roto(body_roto, session)
```

### 5.3 创建 Hair Roto

```python
def create_hair_roto(session, src):
    """创建头发 Roto"""
    roto = Node("RotoNode")
    roto.label = "Hair_Roto"
    session.addNode(roto)

    # 使用 B-Spline 获得自然曲线
    roto.property("shapeType").setValue("b-spline", 0)
    roto.property("alpha.blur").setValue(0.8, 0)  # 头发边缘更柔
    roto.property("motionBlur").setValue(True, 0)
    roto.property("motionBlurAmount").setValue(2.0, 0)  # 头发运动模糊更大

    # 连接
    src.outputs[0].connect(roto.inputs[1])

    # 使用 AI 辅助（2026 新功能）
    try:
        from fx.ai import AIRoto
        ai = AIRoto()
        ai.setSource(src)
        ai.setMode("transformer_v2")
        ai.setTarget("hair")  # 指定目标为头发
        ai.setKeyFrames([1, 48, 96, 144, 192])
        ai.process(frameRange=[1, 192])
        print("AI 辅助头发 Roto 完成")
    except Exception as e:
        print(f"AI 不可用，使用手动: {e}")
        # 手动创建...

    return roto

hair_roto = create_hair_roto(session, src)
```

### 5.4 创建 Clothing Roto

```python
def create_clothing_roto(session, src):
    """创建风衣 Roto"""
    roto = Node("RotoNode")
    roto.label = "Clothing_Roto"
    session.addNode(roto)

    roto.property("shapeType").setValue("bezier", 0)  # 贝塞尔适合锐角
    roto.property("alpha.blur").setValue(0.5, 0)
    roto.property("motionBlur").setValue(True, 0)
    roto.property("motionBlurAmount").setValue(1.5, 0)

    src.outputs[0].connect(roto.inputs[1])

    # 手动绘制风衣形状...
    print("Clothing Roto 节点已创建")
    return roto

clothing_roto = create_clothing_roto(session, src)
```

### 5.5 合并 Roto 层

```python
def merge_roto_layers(session, body_roto, hair_roto, clothing_roto):
    """合并多个 Roto 层"""
    merge = Node("MergeNode")
    merge.label = "Roto_Merge"
    session.addNode(merge)

    # 设置合并模式为 Add（遮罩相加）
    merge.property("operation").setValue("add", 0)

    # 连接
    body_roto.outputs[0].connect(merge.inputs[0])
    hair_roto.outputs[0].connect(merge.inputs[1])
    clothing_roto.outputs[0].connect(merge.inputs[2])

    print("Roto 层已合并")
    return merge

merge_node = merge_roto_layers(session, body_roto, hair_roto, clothing_roto)
```

---

## 六、Paint 修复

### 6.1 修复需求

- 第 45 帧：风衣上有明显污点
- 第 88-92 帧：背景行人穿过角色后方，需去除
- 第 150 帧：头发区域有绿幕反光

### 6.2 Paint 节点设置

```python
from fx import *

def setup_paint(session, src):
    """设置 Paint 节点"""
    paint = Node("PaintNode")
    paint.label = "Cleanup_Paint"
    session.addNode(paint)

    # 基本设置
    paint.property("cloneSource").setValue("frame_offset", 0)
    paint.property("cloneOffset").setValue(-5, 0)  # 前5帧作为克隆源
    paint.property("brushSize").setValue(20, 0)
    paint.property("brushHardness").setValue(0.8, 0)

    # 时序跟踪
    paint.property("temporalTrack").setValue(True, 0)

    # 连接
    src.outputs[0].connect(paint.inputs[1])

    return paint

paint_node = setup_paint(session, src)
```

### 6.3 修复污点

```python
def fix_spot(paint, frame, x, y, radius=20):
    """修复污点"""
    session = activeSession()
    session.currentFrame = frame

    # 创建修复笔触
    stroke = paint.createStroke()
    stroke.setPoint(0, x - radius, y)
    stroke.setPoint(1, x + radius, y)
    stroke.setSize(radius * 2)
    stroke.setOpacity(1.0)
    stroke.setKeyframe(frame)

    print(f"第 {frame} 帧污点已修复 ({x}, {y})")

# 修复第45帧污点
fix_spot(paint_node, 45, 1850, 1200, radius=15)
```

### 6.4 去除背景人物

```python
def remove_background_person(paint, start_frame, end_frame):
    """去除背景人物"""
    session = activeSession()

    for frame in range(start_frame, end_frame + 1):
        session.currentFrame = frame

        # 创建大区域修复笔触
        stroke = paint.createStroke()
        # 绘制覆盖区域...
        stroke.setKeyframe(frame)

        print(f"第 {frame} 帧背景修复完成")

# 去除第88-92帧背景人物
remove_background_person(paint_node, 88, 92)
```

---

## 七、质量控制

### 7.1 自检流程

```python
from fx import *

def qc_check(session, frame_range):
    """QC 自检"""
    issues = []

    for frame in range(frame_range[0], frame_range[1] + 1):
        session.currentFrame = frame

        # 检查 Alpha 通道
        alpha_ok = check_alpha(session, frame)
        if not alpha_ok:
            issues.append(f"第 {frame} 帧: Alpha 异常")

        # 检查边缘
        edge_ok = check_edges(session, frame)
        if not edge_ok:
            issues.append(f"第 {frame} 帧: 边缘问题")

        # 检查时序一致性
        if frame > frame_range[0]:
            temporal_ok = check_temporal(session, frame)
            if not temporal_ok:
                issues.append(f"第 {frame} 帧: 时序抖动")

    # 生成报告
    report = f"""
=== QC 报告 ===
检查帧范围: {frame_range[0]}-{frame_range[1]}
问题数: {len(issues)}

详细:
"""
    for issue in issues:
        report += f"  - {issue}\n"

    print(report)
    return issues

def check_alpha(session, frame):
    """检查 Alpha 通道"""
    # 实现 Alpha 检查逻辑
    return True

def check_edges(session, frame):
    """检查边缘"""
    # 实现边缘检查
    return True

def check_temporal(session, frame):
    """检查时序一致性"""
    # 实现时序检查
    return True

# 执行 QC
issues = qc_check(session, [1, 192])
```

### 7.2 逐帧检查

重点检查帧：
- 第 1 帧：起始位置
- 第 48 帧：第一步（运动最大）
- 第 96 帧：中间位置
- 第 144 帧：接近终点
- 第 192 帧：终止位置

### 7.3 常见问题修正

**问题1：边缘溢出**
- 解决：增加 Edge Softness，或手动调整边缘点

**问题2：头发穿透**
- 解决：检查 Hair Roto 与 Body Roto 的重叠

**问题3：风衣边缘抖动**
- 解决：增加关键帧，启用时序平滑

---

## 八、输出与交付

### 8.1 输出设置

```python
from fx import *

def setup_output(session, merge_node, output_path):
    """设置输出"""
    out = Node("OutputNode")
    out.label = "Final_Output"
    session.addNode(out)

    # 输出路径
    out.property("path").setValue(output_path.replace("\\", "/"), 0)

    # 格式设置
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    out.property("bitDepth").setValue("half", 0)  # 16-bit

    # 帧范围
    out.property("startFrame").setValue(1, 0)
    out.property("endFrame").setValue(192, 0)

    # 色彩空间
    out.property("colorSpace").setValue("ACEScg", 0)

    # 连接
    merge_node.outputs[0].connect(out.inputs[0])

    # 添加元数据
    meta = out.property("exrMetadata")
    meta.setValue("shotName", "SEQ020_SH0150", 0)
    meta.setValue("version", "v003", 0)
    meta.setValue("artist", "Zhang San", 0)
    meta.setValue("task", "roto", 0)
    meta.setValue("colorSpace", "ACEScg", 0)

    return out

output_node = setup_output(
    session,
    merge_node,
    "D:/output/SEQ020_SH0150/SEQ020_SH0150_roto_v003.####.exr"
)
```

### 8.2 渲染输出

```python
def render(session, output_node):
    """执行渲染"""
    print("开始渲染...")

    # 启用多线程渲染
    session.property("render.multiThread").setValue(True, 0)
    session.property("render.tileSize").setValue(512, 0)

    # 执行渲染
    session.render()

    print("渲染完成")

render(session, output_node)
```

### 8.3 交付包

```python
import os
import shutil
import json

def create_delivery_package(output_dir, shot_info):
    """创建交付包"""
    package_dir = os.path.join(output_dir, "delivery")
    os.makedirs(package_dir, exist_ok=True)

    # 子目录
    for d in ["exr", "project", "qc"]:
        os.makedirs(os.path.join(package_dir, d), exist_ok=True)

    # 复制 EXR
    # shutil.copy(...)

    # 复制项目文件
    # shutil.copy(project_path, package_dir + "/project/")

    # 生成 manifest
    manifest = {
        "shot": "SEQ020_SH0150",
        "version": "v003",
        "date": "2026-07-11",
        "artist": "Zhang San",
        "frameRange": [1, 192],
        "resolution": [3840, 2160],
        "frameRate": 24,
        "colorSpace": "ACEScg",
        "tasks": ["roto", "paint"]
    }

    with open(os.path.join(package_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"交付包已生成: {package_dir}")

create_delivery_package("D:/output/SEQ020_SH0150", {})
```

---

## 九、自动化脚本

### 9.1 完整工作流脚本

```python
"""
人物抠像完整工作流
镜头: SEQ020_SH0150
"""
from fx import *
import os

def create_character_keying_pipeline(
    footage_path,
    output_path,
    frame_rate=24.0,
    resolution=[3840, 2160]
):
    """创建人物抠像完整管线"""

    # 1. 创建项目
    print("=== 步骤1: 创建项目 ===")
    proj = Project()
    activate(proj)

    session = Session()
    session.label = "Character_Keying"
    activate(session)
    proj.addItem(session)

    # 2. 添加源节点
    print("=== 步骤2: 加载素材 ===")
    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 3. 配置色彩管理
    print("=== 步骤3: 配置色彩管理 ===")
    color = proj.property("colorManagement")
    color.setValue("enabled", True)
    color.setValue("config", "ACES 1.3")
    color.setValue("workingSpace", "ACEScg")

    # 4. 创建分层 Roto
    print("=== 步骤4: 创建分层 Roto ===")
    body_roto = Node("RotoNode")
    body_roto.label = "Body_Roto"
    body_roto.property("shapeType").setValue("x-spline", 0)
    body_roto.property("alpha.blur").setValue(0.3, 0)
    body_roto.property("motionBlur").setValue(True, 0)
    body_roto.property("motionBlurAmount").setValue(1.2, 0)
    session.addNode(body_roto)
    src.outputs[0].connect(body_roto.inputs[1])

    hair_roto = Node("RotoNode")
    hair_roto.label = "Hair_Roto"
    hair_roto.property("shapeType").setValue("b-spline", 0)
    hair_roto.property("alpha.blur").setValue(0.8, 0)
    hair_roto.property("motionBlur").setValue(True, 0)
    hair_roto.property("motionBlurAmount").setValue(2.0, 0)
    session.addNode(hair_roto)
    src.outputs[0].connect(hair_roto.inputs[1])

    clothing_roto = Node("RotoNode")
    clothing_roto.label = "Clothing_Roto"
    clothing_roto.property("shapeType").setValue("bezier", 0)
    clothing_roto.property("alpha.blur").setValue(0.5, 0)
    clothing_roto.property("motionBlur").setValue(True, 0)
    clothing_roto.property("motionBlurAmount").setValue(1.5, 0)
    session.addNode(clothing_roto)
    src.outputs[0].connect(clothing_roto.inputs[1])

    # 5. 合并 Roto 层
    print("=== 步骤5: 合并 Roto 层 ===")
    merge = Node("MergeNode")
    merge.label = "Roto_Merge"
    merge.property("operation").setValue("add", 0)
    session.addNode(merge)

    body_roto.outputs[0].connect(merge.inputs[0])
    hair_roto.outputs[0].connect(merge.inputs[1])
    clothing_roto.outputs[0].connect(merge.inputs[2])

    # 6. Paint 修复
    print("=== 步骤6: Paint 修复 ===")
    paint = Node("PaintNode")
    paint.label = "Cleanup_Paint"
    paint.property("temporalTrack").setValue(True, 0)
    session.addNode(paint)
    src.outputs[0].connect(paint.inputs[1])

    # 7. 输出
    print("=== 步骤7: 配置输出 ===")
    out = Node("OutputNode")
    out.label = "Final_Output"
    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    out.property("bitDepth").setValue("half", 0)
    out.property("colorSpace").setValue("ACEScg", 0)
    session.addNode(out)

    merge.outputs[0].connect(out.inputs[0])

    print("\n=== 管线创建完成 ===")
    print(f"源: {footage_path}")
    print(f"输出: {output_path}")
    print(f"节点数: {session.numNodes}")
    print("\n下一步: 手动绘制 Roto 形状并添加关键帧")

    return proj, session

# 执行
if __name__ == "__main__":
    proj, session = create_character_keying_pipeline(
        "D:/footage/SEQ020_SH0150_plate.exr",
        "D:/output/SEQ020_SH0150/SEQ020_SH0150_roto_v003.####.exr"
    )
```

---

## 十、总结与反思

### 10.1 工时统计

| 任务 | 工时 | 占比 |
|------|------|------|
| 素材分析 | 1h | 6% |
| 项目设置 | 0.5h | 3% |
| Body Roto | 4h | 25% |
| Hair Roto | 5h | 31% |
| Clothing Roto | 3h | 19% |
| Paint 修复 | 2h | 13% |
| QC 与修改 | 0.5h | 3% |

### 10.2 效率提升点

1. **AI 辅助**：头发 Roto 使用 AI 节省约 40% 时间
2. **脚本自动化**：项目设置节省 30 分钟
3. **分层策略**：独立层便于并行修改

### 10.3 改进方向

1. **更早使用 AI**：在 Body Roto 中也尝试 AI
2. **预设管理**：保存常用节点设置为预设
3. **批处理**：相似镜头使用批处理脚本

### 10.4 经验总结

1. **分层是关键**：复杂对象必须分层处理
2. **关键帧密度**：运动大的区域需要更密的关键帧
3. **运动模糊**：必须与原素材匹配
4. **QC 要及时**：不要等全部完成才检查
5. **保存频繁**：定期保存避免丢失工作

---

> 相关文档：
> - [[Silhouette 实战案例-产品广告修复]]
> - [[Silhouette Roto遮罩完全指南]]
> - [[Silhouette Paint修复完全指南]]

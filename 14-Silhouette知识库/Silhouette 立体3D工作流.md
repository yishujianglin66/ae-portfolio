# Silhouette 立体3D工作流

> 分类: 集成与导出
> 更新日期: 2026-07-11
> 概述: 立体3D Roto、左右眼同步、视差处理、收敛调整完整说明。

## 目录
1. [立体3D概述](#1-立体3d概述)
2. [立体 Roto 工作流](#2-立体-roto-工作流)
3. [左右眼同步](#3-左右眼同步)
4. [视差处理](#4-视差处理)
5. [收敛调整](#5-收敛调整)
6. [导出与交付](#6-导出与交付)
7. [脚本化立体工作流](#7-脚本化立体工作流)
8. [最佳实践](#8-最佳实践)

---

## 1. 立体3D概述

### 1.1 立体3D基础

立体3D(Stereoscopic 3D)通过为左右眼提供略有差异的图像,产生深度感。

| 概念 | 说明 |
|------|------|
| 左眼/右眼 | 两个视角的图像 |
| 视差(Parallax) | 左右眼图像的水平偏移 |
| 收敛(Convergence) | 左右眼视线交叉点 |
| 深度(Depth) | 物体在 Z 轴的位置 |
| 正视差 | 物体在屏幕后方 |
| 负视差 | 物体在屏幕前方 |

### 1.2 Silhouette 立体支持

| 功能 | 说明 |
|------|------|
| 立体 Session | 支持左右眼输入 |
| 同步 Roto | 左右眼形状同步 |
| 视差补偿 | 自动调整形状偏移 |
| 立体预览 | 红蓝/偏振/快门预览 |
| 立体导出 | 同时输出左右眼 |

### 1.3 立体格式

| 格式 | 说明 | 用途 |
|------|------|------|
| 左右并排(SBS) | 左右图像并排 | 存储/传输 |
| 上下(TB) | 上下图像堆叠 | 存储 |
| 帧序列 | 左右交替 | 播放 |
| 独立文件 | 左右分开 | 编辑 |

## 2. 立体 Roto 工作流

### 2.1 立体 Session 创建

```python
from fx import *

def create_stereo_session(width=1920, height=1080, frame_rate=24):
    """创建立体3D Session"""
    session = Session()
    session.label = "Stereo_Session"
    session.width = width
    session.height = height
    session.frameRate = frame_rate
    
    # 创建左右眼 Source 节点
    left_source = Node("Source")
    left_source.label = "SRC_Left_Eye"
    session.addNode(left_source)
    
    right_source = Node("Source")
    right_source.label = "SRC_Right_Eye"
    session.addNode(right_source)
    
    return session, left_source, right_source
```

### 2.2 立体 Roto 节点

```python
def create_stereo_roto(session, left_source, right_source):
    """创建立体 Roto 节点"""
    # 左眼 Roto
    left_roto = Node("RotoShape")
    left_roto.label = "ROTO_Left"
    session.addNode(left_roto)
    left_roto.inputs[0].connect(left_source.outputs[0])
    
    # 右眼 Roto(链接到左眼)
    right_roto = Node("RotoShape")
    right_roto.label = "ROTO_Right"
    session.addNode(right_roto)
    right_roto.inputs[0].connect(right_source.outputs[0])
    
    # 设置立体链接
    # (概念性:实际 API 可能不同)
    right_roto.property("stereoLink").setValue(True, 0)
    right_roto.property("stereoMode").setValue("mirror", 0)
    
    return left_roto, right_roto
```

### 2.3 立体 Roto 工作流

```
1. 在左眼绘制 Roto 形状
2. 切换到右眼视图
3. 检查形状是否对齐
4. 调整右眼形状(补偿视差)
5. 在立体预览模式下检查
6. 微调直到立体效果正确
```

## 3. 左右眼同步

### 3.1 同步策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| 镜像同步 | 右眼镜像左眼 | 对称对象 |
| 偏移同步 | 右眼水平偏移 | 简单视差 |
| 独立绘制 | 左右眼分别绘制 | 复杂场景 |
| 混合模式 | 部分镜像+手动调整 | 一般情况 |

### 3.2 视差计算

```python
def calculate_parallax(left_point, right_point):
    """计算视差
    left_point: (x, y) 左眼坐标
    right_point: (x, y) 右眼坐标
    """
    parallax_x = right_point[0] - left_point[0]
    parallax_y = right_point[1] - left_point[1]
    
    return {
        "horizontal": parallax_x,
        "vertical": parallax_y,
        "depth": "behind" if parallax_x > 0 else "in_front"
    }

# 示例
left = (100, 200)
right = (105, 200)
parallax = calculate_parallax(left, right)
# 水平视差: 5 像素(在屏幕后方)
```

### 3.3 批量视差应用

```python
def apply_parallax_to_shape(shape_points, parallax_x):
    """将视差应用到形状点"""
    return [(x + parallax_x, y) for x, y in shape_points]

def auto_align_right_roto(left_points, right_source, search_range=10):
    """
    自动对齐右眼 Roto
    通过在右眼图像中搜索匹配特征
    """
    aligned_points = []
    
    for x, y in left_points:
        # 在右眼图像中搜索匹配点
        best_x = x
        best_score = -1
        
        for offset in range(-search_range, search_range + 1):
            test_x = x + offset
            score = calculate_match_score(right_source, test_x, y)
            if score > best_score:
                best_score = score
                best_x = test_x
        
        aligned_points.append((best_x, y))
    
    return aligned_points

def calculate_match_score(source, x, y):
    """计算匹配分数(概念性)"""
    # 实际实现需要访问图像像素
    return 0.5  # 占位
```

## 4. 视差处理

### 4.1 视差类型

| 类型 | 视差值 | 效果 | 舒适度 |
|------|--------|------|--------|
| 零视差 | 0 | 在屏幕平面 | 最舒适 |
| 正视差 | > 0 | 在屏幕后方 | 舒适 |
| 负视差 | < 0 | 在屏幕前方 | 需谨慎 |
| 大视差 | > 50px | 强烈深度 | 可能不适 |

### 4.2 视差安全范围

```python
PARALLAX_SAFETY = {
    "comfortable": 30,    # 像素,舒适范围
    "acceptable": 50,     # 可接受范围
    "maximum": 70,        # 最大允许
    "warning": 100        # 超出警告
}

def check_parallax_safety(parallax):
    """检查视差是否在安全范围"""
    abs_parallax = abs(parallax)
    
    if abs_parallax <= PARALLAX_SAFETY["comfortable"]:
        return "safe", "视差在舒适范围内"
    elif abs_parallax <= PARALLAX_SAFETY["acceptable"]:
        return "ok", "视差在可接受范围"
    elif abs_parallax <= PARALLAX_SAFETY["maximum"]:
        return "warn", "视差接近最大值"
    else:
        return "danger", "视差超出安全范围"
```

### 4.3 视差调整

```python
def adjust_parallax(left_points, right_points, target_parallax):
    """
    调整视差到目标值
    target_parallax: 目标水平视差(像素)
    """
    adjusted_right = []
    
    for left, right in zip(left_points, right_points):
        current_parallax = right[0] - left[0]
        adjustment = target_parallax - current_parallax
        adjusted_right.append((right[0] + adjustment, right[1]))
    
    return adjusted_right
```

## 5. 收敛调整

### 5.1 什么是收敛

收敛(Convergence)是调整立体图像零视差平面的过程,改变物体在屏幕前后方的位置。

### 5.2 收敛调整方法

```python
def adjust_convergence(left_image, right_image, shift_amount):
    """
    调整收敛平面
    shift_amount: 水平偏移量(像素)
    正值:物体移向屏幕后方
    负值:物体移向屏幕前方
    """
    # 左眼图像向右移动
    # 右眼图像向左移动
    # (或反之,取决于约定)
    
    adjusted_left = shift_image(left_image, shift_amount, 0)
    adjusted_right = shift_image(right_image, -shift_amount, 0)
    
    return adjusted_left, adjusted_right

def shift_image(image, dx, dy):
    """平移图像"""
    # 实际实现使用 Silhouette API
    pass
```

### 5.3 收敛平面设置

```python
def set_convergence_at_object(left_roto, right_roto, object_left, object_right):
    """
    将收敛平面设置在指定物体上
    使该物体出现在屏幕平面(零视差)
    """
    current_parallax = object_right[0] - object_left[0]
    
    # 需要偏移的量
    shift = current_parallax / 2
    
    # 应用偏移
    # (实际通过图像变换节点实现)
    
    return shift
```

## 6. 导出与交付

### 6.1 立体导出配置

```python
def export_stereo(session, left_comp, right_comp, output_path, format="exr"):
    """导出立体3D结果"""
    # 左眼输出
    left_output = Node("Output")
    left_output.label = "OUT_Left"
    session.addNode(left_output)
    left_output.inputs[0].connect(left_comp.outputs[0])
    left_output.property("format").setValue(format, 0)
    left_output.property("outputPath").setValue(
        os.path.join(output_path, "left/"), 0
    )
    left_output.property("outputName").setValue("left_[####].exr", 0)
    
    # 右眼输出
    right_output = Node("Output")
    right_output.label = "OUT_Right"
    session.addNode(right_output)
    right_output.inputs[0].connect(right_comp.outputs[0])
    right_output.property("format").setValue(format, 0)
    right_output.property("outputPath").setValue(
        os.path.join(output_path, "right/"), 0
    )
    right_output.property("outputName").setValue("right_[####].exr", 0)
    
    return left_output, right_output
```

### 6.2 并排(SBS)导出

```python
def export_sbs(session, left_source, right_source, output_path):
    """导出左右并排格式"""
    # 创建 SBS 合成节点(概念性)
    sbs_comp = Node("Composite")
    sbs_comp.label = "CMP_SBS"
    session.addNode(sbs_comp)
    sbs_comp.inputs[0].connect(left_source.outputs[0])
    sbs_comp.inputs[1].connect(right_source.outputs[0])
    
    # 设置 SBS 布局
    sbs_comp.property("layout").setValue("side_by_side", 0)
    
    # 输出
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(sbs_comp.outputs[0])
    output.property("format").setValue("exr", 0)
    output.property("outputPath").setValue(output_path, 0)
    
    return output
```

### 6.3 交付格式

| 交付类型 | 格式 | 分辨率 | 说明 |
|----------|------|--------|------|
| 影院 3D | DCI-P3 | 2K/4K SBS | 影院标准 |
| 电视 3D | Rec.709 | 1080p SBS/TB | 家用电视 |
| VR/AR | 等距矩形 | 各种 | 头显 |
| Web 3D | sRGB | 1080p SBS | 在线平台 |

## 7. 脚本化立体工作流

### 7.1 完整立体处理脚本

```python
class StereoWorkflow:
    """立体3D工作流"""
    
    def __init__(self, left_path, right_path, output_path):
        self.left_path = left_path
        self.right_path = right_path
        self.output_path = output_path
    
    def setup(self, session):
        """设置立体项目"""
        # 创建左右 Source
        left = Node("Source")
        left.label = "SRC_Left"
        left.property("path").setValue(self.left_path, 0)
        session.addNode(left)
        
        right = Node("Source")
        right.label = "SRC_Right"
        right.property("path").setValue(self.right_path, 0)
        session.addNode(right)
        
        return left, right
    
    def create_stereo_roto(self, session, left, right):
        """创建立体 Roto"""
        left_roto = Node("RotoShape")
        left_roto.label = "ROTO_Left"
        session.addNode(left_roto)
        left_roto.inputs[0].connect(left.outputs[0])
        
        right_roto = Node("RotoShape")
        right_roto.label = "ROTO_Right"
        session.addNode(right_roto)
        right_roto.inputs[0].connect(right.outputs[0])
        
        return left_roto, right_roto
    
    def export(self, session, left_roto, right_roto, frame_range):
        """导出立体结果"""
        import os
        os.makedirs(self.output_path, exist_ok=True)
        
        # 导出左眼遮罩
        left_output = Node("Output")
        left_output.label = "OUT_Left_Matte"
        session.addNode(left_output)
        left_output.inputs[0].connect(left_roto.outputs[0])
        left_output.property("format").setValue("exr", 0)
        left_output.property("outputPath").setValue(
            os.path.join(self.output_path, "left/"), 0
        )
        left_output.property("outputName").setValue("left_matte_[####].exr", 0)
        left_output.property("startFrame").setValue(frame_range[0], 0)
        left_output.property("endFrame").setValue(frame_range[1], 0)
        
        # 导出右眼遮罩
        right_output = Node("Output")
        right_output.label = "OUT_Right_Matte"
        session.addNode(right_output)
        right_output.inputs[0].connect(right_roto.outputs[0])
        right_output.property("format").setValue("exr", 0)
        right_output.property("outputPath").setValue(
            os.path.join(self.output_path, "right/"), 0
        )
        right_output.property("outputName").setValue("right_matte_[####].exr", 0)
        right_output.property("startFrame").setValue(frame_range[0], 0)
        right_output.property("endFrame").setValue(frame_range[1], 0)
        
        return left_output, right_output
```

### 7.2 视差分析工具

```python
class ParallaxAnalyzer:
    """视差分析工具"""
    
    def __init__(self, width=1920):
        self.width = width
    
    def analyze_parallax_map(self, left_roto, right_roto):
        """分析 Roto 形状的视差"""
        parallax_data = []
        
        # 获取形状点(概念性)
        left_points = self.get_shape_points(left_roto)
        right_points = self.get_shape_points(right_roto)
        
        for left_pt, right_pt in zip(left_points, right_points):
            parallax = right_pt[0] - left_pt[0]
            parallax_data.append({
                "left": left_pt,
                "right": right_pt,
                "parallax": parallax,
                "depth": self.parallax_to_depth(parallax)
            })
        
        return parallax_data
    
    def parallax_to_depth(self, parallax):
        """视差转深度描述"""
        if parallax > 20:
            return "far_behind_screen"
        elif parallax > 5:
            return "behind_screen"
        elif parallax > -5:
            return "at_screen"
        elif parallax > -20:
            return "in_front_screen"
        else:
            return "far_in_front"
    
    def get_shape_points(self, roto_node):
        """获取 Roto 形状点"""
        # 实际实现需要访问 Roto 形状数据
        return [(100, 200), (150, 250), (200, 200)]
```

## 8. 最佳实践

### 8.1 立体 Roto 原则

1. **先左后右**:先在左眼完成 Roto,再调整右眼
2. **视差检查**:每帧检查视差是否合理
3. **边缘一致**:左右眼边缘羽化应一致
4. **避免大视差**:物体视差不超过安全范围
5. **定期预览**:在立体预览模式下检查

### 8.2 视差安全指南

| 内容类型 | 推荐视差 | 说明 |
|----------|----------|------|
| 主要对象 | 0-20px | 屏幕平面附近 |
| 背景元素 | 20-40px | 屏幕后方 |
| 前景元素 | -10 to 0px | 略出屏幕 |
| 字幕/标题 | 0px | 必须在屏幕平面 |
| 危险物体 | 避免大负视差 | 避免引起不适 |

### 8.3 收敛调整建议

```python
def get_recommended_convergence(scene_type):
    """获取推荐的收敛设置"""
    recommendations = {
        "dialogue": {"convergence": "on_subject", "parallax_range": (-10, 20)},
        "action": {"convergence": "mid_scene", "parallax_range": (-20, 30)},
        "landscape": {"convergence": "background", "parallax_range": (0, 50)},
        "title": {"convergence": "screen_plane", "parallax_range": (0, 0)},
        "horror": {"convergence": "variable", "parallax_range": (-30, 30)}
    }
    return recommendations.get(scene_type, recommendations["dialogue"])
```

### 8.4 质量检查

```python
def stereo_quality_check(left_matte, right_matte):
    """立体质量检查"""
    issues = []
    
    # 检查帧数一致
    left_frames = count_frames(left_matte)
    right_frames = count_frames(right_matte)
    if left_frames != right_frames:
        issues.append(f"帧数不一致: 左 {left_frames}, 右 {right_frames}")
    
    # 检查分辨率一致
    left_res = get_resolution(left_matte)
    right_res = get_resolution(right_matte)
    if left_res != right_res:
        issues.append(f"分辨率不一致: 左 {left_res}, 右 {right_res}")
    
    # 检查垂直视差(应该接近 0)
    vertical_parallax = calculate_vertical_parallax(left_matte, right_matte)
    if abs(vertical_parallax) > 2:
        issues.append(f"垂直视差过大: {vertical_parallax}px")
    
    return issues
```

### 8.5 文件组织

```
/stereo_project/
  /left/
    /source/       # 左眼原始素材
    /mattes/       # 左眼遮罩
    /renders/      # 左眼渲染
  /right/
    /source/       # 右眼原始素材
    /mattes/       # 右眼遮罩
    /renders/      # 右眼渲染
  /sbs/            # 并排格式
  /final/          # 最终交付
```

---

## 附录:立体3D速查表

| 概念 | 公式/值 | 说明 |
|------|---------|------|
| 视差 | right.x - left.x | 水平偏移 |
| 正视差 | > 0 | 屏幕后方 |
| 负视差 | < 0 | 屏幕前方 |
| 零视差 | = 0 | 屏幕平面 |
| 安全视差 | < 30px | 舒适范围 |
| 最大视差 | < 70px | 不适极限 |
| 垂直视差 | 应为 0 | 必须校正 |

> **提示**:立体 Roto 最重要的是左右眼同步。建议先在左眼完成完整 Roto,然后通过视差补偿生成右眼初版,最后手动微调。

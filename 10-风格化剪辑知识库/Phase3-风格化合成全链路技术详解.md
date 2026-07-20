# Phase 3 风格化合成 - 全链路技术详解

---

## 文档信息

| 项目 | 内容 |
|------|------|
| **阶段** | Phase 3 风格化合成 |
| **涉及引擎** | 10个（7商业 + 3开源） |
| **核心引擎** | AE + Silhouette + Blender + DaVinci Resolve |
| **处理时长** | 约为视频时长的 3-10倍（取决于风格复杂度） |

---

## 一、风格化流水线总览

### 1.1 10引擎能力矩阵

| 引擎 | 定位 | 核心能力 |
|------|------|---------|
| **After Effects** | 主合成引擎 | 8大风格化子系统、图层合成、效果动画、表达式 |
| **nexrender** | 批量渲染引擎 | 模板参数化、JSON驱动、批量渲染队列 |
| **ae-python-bridge** | 桥接层 | Python直接调用AE ExtendScript |
| **Blender** | 3D内容生成 | 木偶舞台、底座、灯光、摄像机、bpy自动化 |
| **Photoshop** | 材质/纹理制作 | 材质贴图、质感处理、PSD分层导入AE |
| **Illustrator** | 矢量路径 | 关节路径、提线、矢量图形 |
| **DaVinci Resolve** | 最终调色+Fusion | 电影级调色、Fusion节点特效、Fairlight音频 |
| **Premiere Pro** | 精剪+字幕 | 最终剪辑、多版本输出、字幕精修 |
| **Stable Diffusion** | AI纹理生成 | 木纹/陶瓷/布偶等无缝纹理批量生成 |
| **ffmpeg-python** | 素材转码 | AE前后素材格式转换、序列合成 |

### 1.2 流水线结构

```
Phase 2 输出
（蒙版+跟踪数据+相机位姿）
    │
    ▼
┌───────────────────────────────────────────────────────┐
│  素材准备层（并行）                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Blender │  │   PS    │  │   AI    │  │ Stable  │ │
│  │ 3D舞台  │  │ 材质    │  │ 矢量    │  │ Diff    │ │
│  │ 底座    │  │ 贴图    │  │ 路径    │  │ 纹理    │ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘ │
│       │            │            │            │       │
│       └────────────┴────────────┴────────────┘       │
│                         │                             │
│                         ▼                             │
│               素材库（素材标准化）                       │
└─────────────────────────┬─────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│  主合成层（AE核心）                                     │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │  nexrender 模板渲染                              │  │
│  │  JSON参数 → AE模板 → 自动合成                    │  │
│  └─────────────────────┬───────────────────────────┘  │
│                        │                              │
│  ┌─────────────────────────────────────────────────┐  │
│  │  8大风格化子系统（参数化调用）                      │  │
│  │  ① 材质质感 ② 关节化 ③ 定格动画 ④ 微缩场景      │  │
│  │  ⑤ 粒子系统 ⑥ 面部木偶化 ⑦ 3D舞台 ⑧ 风格调色    │  │
│  └─────────────────────┬───────────────────────────┘  │
│                        │                              │
│  ┌─────────────────────────────────────────────────┐  │
│  │  跟踪数据映射                                    │  │
│  │  关节点→位置/旋转、面部→变形、相机→3D层           │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────┬─────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│  精修层                                                 │
│  ┌───────────────┐  ┌─────────────────────────────┐  │
│  │ DaVinci Resolve│→│ 最终调色 + Fusion特效       │  │
│  │ 专业调色      │  │ + Fairlight音频混合          │  │
│  └───────────────┘  └─────────────────────────────┘  │
│  ┌───────────────┐  ┌─────────────────────────────┐  │
│  │ Premiere Pro  │→│ 精剪 + 字幕校对 + 多版本     │  │
│  │ 精剪输出      │  │ 输出准备                     │  │
│  └───────────────┘  └─────────────────────────────┘  │
└─────────────────────────┬─────────────────────────────┘
                          │
                          ▼
                  Phase 4 渲染输出
```

---

## 二、8大风格化子系统详解

### 子系统1：材质质感系统

**核心效果**：木质 / 陶瓷 / 布偶 / 金属 / 塑料 / 玻璃 / 石质 / 纸艺

#### 2.1.1 实现原理

```
输入视频 + 蒙版
    │
    ├──────────────────────────────────┐
    │                                  │
    ▼                                  ▼
┌──────────┐                    ┌──────────┐
│ 纹理叠加 │                    │ 光影处理 │
│ - 木纹/布纹│                    │ - 高光   │
│ - 陶瓷釉面│                    │ - 阴影   │
│ - 金属光泽│                    │ - AO环境光│
└────┬─────┘                    └────┬─────┘
     │                               │
     └─────────────┬─────────────────┘
                   │
                   ▼
            ┌──────────┐
            │ 边缘处理  │ → 接缝/磨损/厚度感
            │ 细节增强  │
            └──────────┘
```

#### 2.1.2 AE效果组合

| 材质类型 | 核心效果 | 关键参数 |
|---------|---------|---------|
| **木质** | CC木纹 + 渐变叠加 + 色相/饱和度 | 木纹大小、颜色深度、年轮密度 |
| **陶瓷** | 光泽 + 反射 + 斜面与浮雕 | 高光强度、反射率、边缘厚度 |
| **布偶** | 杂色 + 模糊 + 湍流置换 | 布料纹理、绒毛感、柔软度 |
| **金属** | 曲线 + 渐变 + CC金属 | 金属度、粗糙度、反射方向 |

#### 2.1.3 nexrender 模板片段

```json
{
  "name": "texture_wood",
  "composition": "MainComp",
  "assets": [
    {
      "src": "file:///templates/textures/wood_seamless_01.jpg",
      "type": "image",
      "name": "wood_texture"
    }
  ],
  "layers": [
    {
      "name": "WoodTexture",
      "type": "AVLayer",
      "sourceName": "wood_texture",
      "blendMode": "Multiply",
      "opacity": 40,
      "effects": [
        {
          "className": "ADBE Vectors",
          "name": "CC Glass",
          "properties": [
            {"name": "Displacement", "value": 15},
            {"name": "Softness", "value": 3}
          ]
        }
      ]
    }
  ]
}
```

---

### 子系统2：关节化处理系统

**核心效果**：关节接缝 / 提线 / 活动关节 / 挂钩 / 线轴

#### 2.2.1 关节点映射

```
MediaPipe 33点 → 木偶关节映射
┌─────────────────────────────────────────┐
│ 头部（0）  → 头关节（球形关节）          │
│ 肩膀（11/12）→ 肩关节（球窝关节）        │
│ 肘部（13/14）→ 肘关节（铰链关节）        │
│ 手腕（15/16）→ 腕关节（铰链关节）        │
│ 髋部（23/24）→ 髋关节（球窝关节）        │
│ 膝盖（25/26）→ 膝关节（铰链关节）        │
│ 脚踝（27/28）→ 踝关节（铰链关节）        │
└─────────────────────────────────────────┘
```

#### 2.2.2 AE自动生成关节接缝脚本

```javascript
// AE ExtendScript: 自动生成关节接缝图层
// 输入：关节点坐标数据（JSON）
// 输出：接缝图层（圆形/椭圆形，带立体效果）

function createJoints(jointData, comp) {
    var jointLayer = comp.layers.addShape();
    jointLayer.name = "Joints";
    
    var shapeGroup = jointLayer.property("Contents").addProperty("ADBE Vector Group");
    shapeGroup.name = "JointsGroup";
    
    // 为每个关节创建圆形接缝
    for (var i = 0; i < jointData.joints.length; i++) {
        var joint = jointData.joints[i];
        
        // 创建椭圆路径
        var ellipse = shapeGroup.addProperty("ADBE Vector Shape - Ellipse");
        ellipse.name = "Joint_" + joint.name;
        
        // 设置位置（绑定到关节点跟踪数据）
        var position = ellipse.property("ADBE Vector Transform Group")
                            .property("ADBE Vector Position");
        position.setValue([joint.x, joint.y]);
        
        // 设置大小
        var size = ellipse.property("ADBE Vector Ellipse Size");
        size.setValue([joint.size, joint.size]);
        
        // 添加填充（木质/陶瓷材质）
        var fill = shapeGroup.addProperty("ADBE Vector Fill");
        fill.property("Color").setValue(joint.color);
        
        // 添加斜面与浮雕效果（立体感）
        var bevel = jointLayer.effect.addProperty("ADBE Bevel Alpha");
        bevel.property("Edge Thickness").setValue(2);
        bevel.property("Light Angle").setValue(135);
    }
    
    return jointLayer;
}

// 创建提线（从顶部控制点到关节）
function createStrings(jointData, controlPoints, comp) {
    var stringLayer = comp.layers.addShape();
    stringLayer.name = "PuppetStrings";
    
    var pathGroup = stringLayer.property("Contents").addProperty("ADBE Vector Group");
    
    for (var i = 0; i < jointData.joints.length; i++) {
        var joint = jointData.joints[i];
        var control = controlPoints[joint.name];
        
        if (control) {
            // 创建路径（从控制点到关节）
            var path = pathGroup.addProperty("ADBE Vector Shape - Path");
            path.name = "String_" + joint.name;
            
            var pathProp = path.property("ADBE Vector Path");
            var points = [
                [control.x, control.y],
                [joint.x, joint.y]
            ];
            pathProp.setValue(points);
            
            // 描边
            var stroke = pathGroup.addProperty("ADBE Vector Stroke");
            stroke.property("ADBE Stroke Width").setValue(1);
            stroke.property("Color").setValue([0.9, 0.9, 0.9]);
        }
    }
    
    return stringLayer;
}
```

---

### 子系统3：定格动画效果

**核心效果**：降帧 / 逐帧微位移 / 曝光闪烁 / 抖动 / 跳帧

#### 2.3.1 效果组合

| 效果 | 实现方式 | 参数范围 |
|------|---------|---------|
| 降帧 | 时间重映射 / 抽帧 | 6-24fps |
| 微位移 | 位置Wiggle表达式 | 1-5像素 |
| 曝光闪烁 | 亮度Wiggle + 随机 | ±5-15% |
| 缩放呼吸 | 缩放Wiggle表达式 | ±0.5-2% |
| 跳帧 | 随机丢帧 | 2-5%概率 |

#### 2.3.2 AE表达式模板

```javascript
// 定格动画 - 位置微抖动
// 应用到位置属性
wiggle_freq = 8;       // 抖动频率
wiggle_amount = 2;     // 抖动幅度（像素）
pos = value;
wiggle(wiggle_freq, wiggle_amount)

// 定格动画 - 曝光闪烁
// 应用到不透明度属性
flash_freq = 4;
flash_amount = 10;     // 不透明度变化百分比
base_opacity = 100;
base_opacity + wiggle(flash_freq, flash_amount)[0]

// 定格动画 - 降帧（步进式）
// 应用到时间重映射
fps = 12;              // 目标帧率
t = time;
step = 1 / fps;
Math.floor(t / step) * step
```

---

### 子系统4：微缩场景感

**核心效果**：浅景深 / 移轴模糊 / 舞台光照 / 地面阴影 / 场景边界

#### 2.4.1 景深效果实现

```
两种实现方案：
┌───────────────────────────────────┐
│ 方案A：AE镜头模糊（2D模拟）        │
│ - 基于深度通道的景深               │
│ - 快速，适合批量                   │
└───────────────────────────────────┘
┌───────────────────────────────────┐
│ 方案B：Blender 3D景深（真实渲染）  │
│ - 真实光学景深                     │
│ - 质量更高，但渲染慢               │
└───────────────────────────────────┘
```

---

### 子系统5：粒子系统

**核心效果**：木纹粉尘 / 布料纤维 / 魔法粒子 / 灰尘 / 木屑飞溅

#### 2.5.1 粒子类型

| 粒子类型 | 适用场景 | 粒子数 |
|---------|---------|--------|
| 木纹粉尘 | 木质木偶 | 200-500 |
| 布料纤维 | 布偶风格 | 100-300 |
| 魔法粒子 | 奇幻风格 | 500-2000 |
| 灰尘飘浮 | 通用氛围 | 50-150 |

---

### 子系统6：面部木偶化

**核心效果**：五官夸张 / 表情映射 / 关节嘴型 / 木偶眼睛 / 腮红

#### 2.6.1 面部关键点 → 木偶表情映射

```
MediaPipe Face Mesh (468点) → 木偶面部控制器
┌─────────────────────────────────────────────┐
│ 眼睛区域（左右各 ~50点）                      │
│   → 眼睑开合 → 木偶眼睛大小                  │
│   → 视线方向 → 眼球位置偏移                  │
│                                               │
│ 嘴部区域（~80点）                             │
│   → 嘴巴开合度 → 木偶嘴部高度                │
│   → 嘴角高度 → 表情（笑/哭/平）              │
│                                               │
│ 眉毛区域（~20点）                             │
│   → 眉高 → 表情（惊讶/愤怒/悲伤）            │
│                                               │
│ OpenFace AU参数 → 精细表情控制               │
│   AU01 → 内侧眉抬高（惊讶/悲伤）             │
│   AU06 → 脸颊抬起（真笑）                    │
│   AU12 → 嘴角上扬（笑容）                    │
│   AU25 → 嘴唇分开（说话/惊讶）               │
└─────────────────────────────────────────────┘
```

---

### 子系统7：3D舞台系统

**核心效果**：木偶舞台 / 底座 / 幕布 / 灯光 / 3D摄像机

#### 2.7.1 Blender自动生成舞台

```python
# Blender bpy脚本：程序化生成木偶舞台
import bpy
import math

def create_puppet_stage(style: str = "classic",
                        size: float = 5.0):
    """
    生成木偶舞台场景
    
    Args:
        style: classic / modern / fantasy / minimal
        size: 舞台大小（米）
    """
    
    # 清除默认物体
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    stage_objects = []
    
    # 1. 创建舞台底座
    base = bpy.data.objects.new("StageBase", 
        bpy.data.meshes.new("BaseMesh"))
    bpy.context.collection.objects.link(base)
    
    # 建底座（矩形台座）
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(base.data)
    bm.free()
    
    base.scale = (1.0, 0.3, 0.8)
    base.location = (0, -size * 0.2, 0)
    
    # 材质
    base_material = create_wood_material()
    base.data.materials.append(base_material)
    stage_objects.append(base)
    
    # 2. 创建幕布
    curtain_left = create_curtain("CurtainLeft", -size * 0.6, size)
    curtain_right = create_curtain("CurtainRight", size * 0.6, size)
    stage_objects.extend([curtain_left, curtain_right])
    
    # 3. 创建灯光
    key_light = create_light("KeyLight", 
        type='SPOT', location=(0, size, size * 0.8))
    fill_light = create_light("FillLight", 
        type='AREA', location=(-size * 0.5, size * 0.5, size * 0.3))
    rim_light = create_light("RimLight",
        type='SPOT', location=(0, -size * 0.5, size))
    stage_objects.extend([key_light, fill_light, rim_light])
    
    # 4. 创建摄像机
    cam = bpy.data.cameras.new("StageCamera")
    cam_obj = bpy.data.objects.new("StageCamera", cam)
    cam_obj.location = (0, size * 1.5, size * 0.5)
    cam_obj.rotation_euler = (math.radians(60), 0, 0)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    
    return stage_objects, cam_obj

def create_wood_material():
    """创建木质材质"""
    mat = bpy.data.materials.new("WoodMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # 清除默认节点
    for node in nodes:
        nodes.remove(node)
    
    # Principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.6, 0.4, 0.2, 1)
    bsdf.inputs['Roughness'].default_value = 0.4
    bsdf.inputs['Metallic'].default_value = 0.0
    
    # 木纹纹理
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    mapping = nodes.new(type='ShaderNodeMapping')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 10.0
    
    # 输出
    output = nodes.new(type='ShaderNodeOutputMaterial')
    
    # 连接
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat

def create_curtain(name: str, x_pos: float, size: float):
    """创建幕布"""
    # 使用平面 + 布料修改器
    ...

def create_light(name: str, type: str, location: tuple):
    """创建灯光"""
    light_data = bpy.data.lights.new(name, type)
    light_obj = bpy.data.objects.new(name, light_data)
    light_obj.location = location
    
    if type == 'SPOT':
        light_data.energy = 1000
        light_data.spot_size = math.radians(45)
    elif type == 'AREA':
        light_data.energy = 500
    
    bpy.context.collection.objects.link(light_obj)
    return light_obj

# 渲染舞台背景图（供AE使用）
def render_stage(output_path: str, resolution: tuple = (1920, 1080)):
    """渲染舞台背景"""
    scene = bpy.context.scene
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    
    bpy.ops.render.render(write_still=True)
```

---

### 子系统8：风格化调色

**核心效果**：电影感 / 复古 / 卡通 / 暗黑 / 明亮 / 日系 / 赛博朋克

#### 2.8.1 DaVinci Resolve 自动调色

```python
# DaVinci Resolve Python脚本：自动应用LUT和调色节点
import DaVinciResolveScript as bmd

def apply_puppet_color_grade(timeline_name: str, 
                              style: str = "cinematic"):
    """
    应用木偶风格调色
    
    Args:
        timeline_name: 时间线名称
        style: cinematic / vintage / cartoon / warm
    """
    
    resolve = bmd.scriptapp("Resolve")
    project = resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetTimelineByName(timeline_name)
    
    if not timeline:
        return False
    
    # 获取调色页
    color_page = resolve.GetPage("Color")
    
    # 为每个剪辑添加调色节点
    clip_count = timeline.GetTrackCount("video")
    
    for track_idx in range(1, clip_count + 1):
        track = timeline.GetTrackName("video", track_idx)
        clip = timeline.GetClipByIndex(track_idx, 1)
        
        if clip:
            # 添加校正节点
            clip.AddNode()
            
            # 应用不同风格的调色参数
            if style == "cinematic":
                apply_cinematic_look(clip)
            elif style == "vintage":
                apply_vintage_look(clip)
            elif style == "cartoon":
                apply_cartoon_look(clip)
            elif style == "warm":
                apply_warm_look(clip)
            
            # 应用LUT
            clip.SetLUTs([f"Puppet_{style}.cube"])
    
    return True

def apply_cinematic_look(clip):
    """电影感调色"""
    # 降低饱和度
    clip.AdjustSaturation(-0.1)
    
    # 提高对比度
    clip.AdjustContrast(0.1)
    
    # 暗部偏蓝
    clip.AdjustLift([-0.02, -0.02, 0.03])
    
    # 高光偏暖
    clip.AdjustGain([1.02, 1.01, 0.98])
    
    # 压暗角
    clip.AddVignette()
```

---

## 三、nexrender 批量渲染系统

### 3.1 模板系统架构

```
模板仓库
├── base/
│   ├── puppet_base.aep           # 基础工程模板
│   └── puppet_base.json          # 基础参数
├── styles/
│   ├── wood/                     # 木质风格
│   │   ├── template.json
│   │   └── assets/
│   ├── ceramic/                  # 陶瓷风格
│   ├── cloth/                    # 布偶风格
│   └── ...
├── effects/
│   ├── stop_motion/              # 定格动画预设
│   ├── particles/                # 粒子预设
│   └── ...
└── output/
    ├── social/                   # 社交媒体输出预设
    ├── tv/                       # 电视输出预设
    └── ...
```

### 3.2 任务定义格式

```json
{
  "task_id": "puppet_001",
  "input_video": "/path/to/input.mp4",
  "style": {
    "type": "wood",
    "variant": "classic",
    "intensity": 0.8
  },
  "effects": {
    "stop_motion": { "enabled": true, "fps": 12 },
    "joints": { "enabled": true, "size": 15 },
    "strings": { "enabled": true, "visible": true },
    "particles": { "enabled": true, "count": 300 },
    "depth_of_field": { "enabled": true, "blur": 20 },
    "face_puppet": { "enabled": true, "exaggeration": 1.5 }
  },
  "stage": {
    "enabled": true,
    "type": "theater",
    "lighting": "warm"
  },
  "color_grade": {
    "style": "cinematic",
    "lut": "Puppet_Cinematic.cube"
  },
  "output": {
    "format": "mp4",
    "resolution": [1920, 1080],
    "fps": 30,
    "bitrate": "20M"
  },
  "tracking_data": "/path/to/tracking_data.json",
  "matte_sequence": "/path/to/matte/"
}
```

### 3.3 nexrender渲染流程

```python
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class RenderTask:
    """渲染任务"""
    task_id: str
    aep_path: str
    output_path: str
    comp_name: str = "MainComp"
    settings: dict = None

class NexrenderRenderer:
    """nexrender渲染器封装"""
    
    def __init__(self, nexrender_path: str = "nexrender",
                 ae_binary: str = None):
        self.nexrender_path = nexrender_path
        self.ae_binary = ae_binary
    
    def render(self, task: RenderTask) -> bool:
        """执行渲染任务"""
        
        # 构建nexrender的JSON任务
        job_config = self._build_job_config(task)
        
        # 保存为临时JSON
        config_path = f"/tmp/nexrender_{task.task_id}.json"
        with open(config_path, "w") as f:
            json.dump(job_config, f, indent=2)
        
        # 执行nexrender
        cmd = [
            self.nexrender_path,
            "--config", config_path,
        ]
        
        if self.ae_binary:
            cmd.extend(["--binary", self.ae_binary])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600 * 4  # 4小时超时
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
    
    def _build_job_config(self, task: RenderTask) -> dict:
        """构建nexrender任务配置"""
        return {
            "template": {
                "src": f"file:///{task.aep_path}",
                "composition": task.comp_name,
            },
            "output": {
                "module": "h264",
                "path": task.output_path,
            },
            "assets": [
                # 动态替换的素材
            ],
            "actions": {
                "predownload": [],
                "postdownload": [],
                "postrender": [],
            },
        }
    
    def batch_render(self, tasks: List[RenderTask],
                     max_concurrent: int = 2) -> dict:
        """批量渲染"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {}
            for task in tasks:
                future = executor.submit(self.render, task)
                futures[future] = task.task_id
            
            for future in as_completed(futures):
                task_id = futures[future]
                results[task_id] = future.result()
        
        return results
```

---

## 四、多引擎协同工作流

### 4.1 Blender → AE 素材流水线

```
Blender 3D场景
    │
    ├─→ 渲染舞台背景图（PNG序列）
    ├─→ 渲染木偶底座（带Alpha通道EXR）
    ├─→ 渲染灯光/阴影通道
    ├─→ 导出摄像机数据（JSON）
    └─→ 导出纹理贴图（用于AE叠加）
              │
              ▼
         AE合成
    ┌─────────────────┐
    │ 背景层（舞台）   │
    │ 3D层（摄像机）   │
    │ 木偶主体层      │
    │ 粒子/效果层     │
    │ 调色/输出层     │
    └─────────────────┘
```

### 4.2 AE → Resolve 调色工作流

```
AE渲染输出（高质量中间片）
    │
    ▼
Resolve导入
    │
    ├─→ 自动套用风格LUT
    ├─→ 节点调色（皮肤/背景/环境分离）
    ├─→ Fusion特效（光效/颗粒）
    └─→ Fairlight音频混合
              │
              ▼
         最终渲染输出
```

---

## 五、质量控制点

| 检查点 | 标准 | 检测方法 |
|--------|------|---------|
| 蒙版边缘质量 | 无锯齿、无闪烁、发丝级 | 逐帧检查 + 时序稳定性评分 |
| 关节对齐精度 | 关节位置误差 < 3像素 | 自动检测 + 人工抽检 |
| 风格一致性 | 全片风格统一度 > 90% | 色彩直方图 + 人工评审 |
| 跟踪稳定性 | 无跳变、无漂移 | 关键点轨迹平滑度分析 |
| 渲染质量 | 无压缩劣化、无丢帧 | VMAF > 90 + MediaInfo校验 |
| 表情自然度 | 面部木偶化无违和感 | 主观评分 + AU映射准确率 |

---

> **关联文档**：
> - [[Phase 2 抠像跟踪全链路技术详解]]
> - [[Phase 4 渲染输出全链路详解]]
> - [[nexrender批量渲染开发指南]]
> - [[Blender bpy自动化开发指南]]
> - [[木偶风格视频制作核心指南]]
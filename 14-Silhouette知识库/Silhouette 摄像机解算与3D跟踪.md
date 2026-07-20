# Silhouette 摄像机解算与3D跟踪

> 分类: 跟踪技术专题
> 更新日期: 2026-07-11
> 概述: CameraSolver节点深度解析，涵盖3D点云生成、解算精度优化、镜头类型适配与3D跟踪数据应用。

## 目录
1. [摄像机解算概述](#一摄像机解算概述)
2. [CameraSolver 节点](#二camerasolver-节点)
3. [3D 点云生成](#三3d-点云生成)
4. [解算精度优化](#四解算精度优化)
5. [镜头类型适配](#五镜头类型适配)
6. [解算结果验证](#六解算结果验证)
7. [3D 跟踪数据应用](#七3d-跟踪数据应用)
8. [故障排查](#八故障排查)

---

## 一、摄像机解算概述

### 1.1 什么是摄像机解算

摄像机解算（Camera Solving）是通过分析二维跟踪点在序列中的运动，反推摄像机在三维空间中的运动轨迹和内部参数（焦距、畸变等）的过程。这是从 2D 跟踪到 3D 跟踪的关键步骤。

### 1.2 解算的应用场景

| 应用 | 说明 |
|------|------|
| 3D 元素合成 | 将 3D 渲染元素匹配到实拍镜头 |
| 虚拟制片 | 实时摄像机跟踪驱动虚拟场景 |
| 运动捕捉 | 从视频提取摄像机运动数据 |
| 3D 重建 | 重建场景的 3D 几何 |
| 视差效果 | 利用 3D 深度信息创建视差 |

### 1.3 与 2D 跟踪的差异

| 维度 | 2D 跟踪 | 3D 摄像机解算 |
|------|---------|---------------|
| 输出维度 | 二维坐标 | 三维摄像机路径 + 3D 点云 |
| 跟踪需求 | 单点/区域 | 多点（通常 8+ 点） |
| 视差依赖 | 不需要 | 需要视差（摄像机运动） |
| 适用镜头 | 任意镜头 | 需要摄像机运动的镜头 |
| 复杂度 | 中 | 高 |

---

## 二、CameraSolver 节点

### 2.1 节点定位

CameraSolver 节点接收多点跟踪数据，通过束调整（Bundle Adjustment）算法解算摄像机参数和 3D 点位置。

### 2.2 节点端口

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | trackData | 多点跟踪数据输入 |

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | camera | 摄像机数据输出 |
| 1 | pointCloud | 3D 点云输出 |

### 2.3 核心属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| solveMode | string | "automatic" | 解算模式 |
| focalLength | float | 50.0 | 已知焦距（mm） |
| focalLengthMode | string | "fixed" | 焦距模式：fixed/variable/unknown |
| distortion | string | "none" | 畸变模式：none/brown1/brown3 |
| keyframeSpacing | int | 10 | 关键帧间距 |
| minTracks | int | 8 | 最小跟踪点数 |
| errorThreshold | float | 2.0 | 误差阈值（像素） |

### 2.4 解算模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| automatic | 自动选择关键帧 | 通用场景 |
| manual | 手动指定关键帧 | 复杂镜头 |
| survey | 基于测量数据 | 已知 3D 点位置 |
| nodal | 节点式（纯旋转） | 摄像机原地旋转 |

### 2.5 基础脚本

```python
from fx import *

# 项目初始化
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Camera_Solve"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.mov", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 多点跟踪节点
track = Node("TrackerNode")
track.label = "3D_Track_Points"
track.property("trackType").setValue("point", 0)
track.property("searchArea").setValue(25, 0)
track.property("accuracy").setValue("high", 0)
track.property("patternSize").setValue(11, 0)
session.addNode(track)

# 摄像机解算节点
solver = Node("CameraSolver")
solver.label = "Camera_Solver"
solver.property("solveMode").setValue("automatic", 0)
solver.property("focalLength").setValue(50.0, 0)
solver.property("focalLengthMode").setValue("fixed", 0)
solver.property("distortion").setValue("none", 0)
solver.property("keyframeSpacing").setValue(10, 0)
solver.property("minTracks").setValue(8, 0)
solver.property("errorThreshold").setValue(2.0, 0)
session.addNode(solver)

# 连接节点
src.outputs[0].connect(track.inputs[0])
track.outputs[0].connect(solver.inputs[0])

print("[SILHOUETTE] Camera solver pipeline ready")
print("[SILHOUETTE] 需要 8+ 个跟踪点进行解算")
```

---

## 三、3D 点云生成

### 3.1 点云生成原理

通过多视图几何（Multi-view Geometry）算法，从不同帧的同一 3D 点的二维投影反推其三维坐标：

1. **特征匹配**：在多帧中匹配同一 3D 点的投影
2. **三角测量**：通过两帧或多帧的投影射线求交点
3. **束调整**：联合优化所有 3D 点位置和摄像机参数
4. **点云输出**：输出所有成功解算的 3D 点

### 3.2 点云质量因素

| 因素 | 影响 | 优化方向 |
|------|------|----------|
| 跟踪点数量 | 多则密 | 至少 8 点，推荐 15+ |
| 跟踪点分布 | 均匀则好 | 避免聚集，覆盖全画面 |
| 跟踪精度 | 高则准 | accuracy=high |
| 视差大小 | 大则准 | 需要明显摄像机运动 |
| 帧跨度 | 长则稳 | 跨越多个关键帧 |

### 3.3 点云数据结构

```python
point_cloud = {
    "version": "2026.0.2",
    "point_count": 25,
    "points": [
        {
            "id": "P1",
            "position": [1.5, 2.3, -5.0],  # 3D 坐标
            "error": 0.8,  # 重投影误差（像素）
            "frames": [0, 1, 5, 10, 15]  # 可见帧
        }
    ],
    "camera": {
        "focal_length": 50.0,
        "frames": [
            {
                "frame": 0,
                "position": [0, 0, 0],
                "rotation": [[1,0,0],[0,1,0],[0,0,1]]
            }
        ]
    }
}
```

### 3.4 点云导出

```python
def export_point_cloud(solver_node, output_path):
    """导出 3D 点云数据"""

    point_cloud_data = {
        "version": "2026.0.2",
        "point_count": 0,
        "points": [],
        "camera": {
            "focal_length": solver_node.property("focalLength").getValue(0),
            "frames": []
        }
    }

    # 获取点云数据（实际通过 API）
    # ...

    import json
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(point_cloud_data, f, indent=2, ensure_ascii=False)

    print(f"[SILHOUETTE] Point cloud exported: {output_path}")
    return output_path
```

---

## 四、解算精度优化

### 4.1 精度影响因素

**跟踪点质量**：
- 跟踪点分布均匀（避免聚集）
- 跟踪点数量充足（15+ 点）
- 跟踪点精度高（accuracy=high）
- 跟踪点跨帧稳定（无丢失）

**镜头运动**：
- 摄像机运动明显（产生视差）
- 运动模式清晰（平移/旋转/组合）
- 避免纯变焦镜头（无视差）

**参数设置**：
- 焦距设置正确
- 畸变模式匹配
- 关键帧间距合理

### 4.2 精度优化策略

**策略一：增加跟踪点**
```python
solver.property("minTracks").setValue(15, 0)  # 提高最小点数
```

**策略二：选择优质跟踪点**
- 分布在画面不同区域
- 处于不同深度（前景、中景、远景）
- 跟踪稳定不丢失

**策略三：正确设置焦距**
```python
# 已知焦距
solver.property("focalLengthMode").setValue("fixed", 0)
solver.property("focalLength").setValue(35.0, 0)  # 35mm 镜头

# 未知焦距（让解算器估算）
solver.property("focalLengthMode").setValue("unknown", 0)
```

**策略四：启用畸变校正**
```python
solver.property("distortion").setValue("brown3", 0)  # 三阶布朗畸变
```

**策略五：调整关键帧间距**
```python
solver.property("keyframeSpacing").setValue(5, 0)  # 更密集的关键帧
```

### 4.3 误差评估

```python
def evaluate_solve_quality(solver_node):
    """评估解算质量"""

    # 重投影误差（应小于 2.0 像素）
    error = solver_node.property("reprojectionError").getValue(0)

    if error < 1.0:
        quality = "优秀"
    elif error < 2.0:
        quality = "良好"
    elif error < 3.0:
        quality = "可接受"
    else:
        quality = "需改进"

    print(f"[SILHOUETTE] 解算误差: {error:.2f} 像素")
    print(f"[SILHOUETTE] 解算质量: {quality}")

    return quality, error
```

---

## 五、镜头类型适配

### 5.1 镜头运动类型

| 运动类型 | 视差 | 解算难度 | 推荐 minTracks |
|----------|------|----------|---------------|
| 平移（推车） | 大 | 低 | 8 |
| 横移（轨道） | 大 | 低 | 8 |
| 升降 | 大 | 中 | 10 |
| 摇摄（三脚架） | 小 | 高 | 15 |
| 俯仰 | 小 | 高 | 15 |
| 自由运动（手持） | 中 | 中 | 12 |
| 变焦 | 无 | 极高 | 不推荐 |
| 旋转（节点式） | 无 | 高 | 20 |

### 5.2 平移镜头适配

```python
# 平移镜头（推车/轨道）：视差大，解算容易
solver.property("solveMode").setValue("automatic", 0)
solver.property("focalLengthMode").setValue("fixed", 0)
solver.property("minTracks").setValue(8, 0)
solver.property("keyframeSpacing").setValue(10, 0)
```

### 5.3 摇摄镜头适配

```python
# 摇摄镜头（三脚架）：视差小，解算困难
solver.property("solveMode").setValue("nodal", 0)  # 节点式解算
solver.property("focalLengthMode").setValue("fixed", 0)
solver.property("minTracks").setValue(15, 0)
solver.property("keyframeSpacing").setValue(5, 0)  # 更密集关键帧
```

### 5.4 手持镜头适配

```python
# 手持镜头：运动复杂，中等难度
solver.property("solveMode").setValue("automatic", 0)
solver.property("focalLengthMode").setValue("fixed", 0)
solver.property("distortion").setValue("brown3", 0)  # 启用畸变
solver.property("minTracks").setValue(12, 0)
solver.property("keyframeSpacing").setValue(8, 0)
```

### 5.5 变焦镜头适配

变焦镜头无视差，解算困难。建议：
- 使用固定焦距假设分段解算
- 手动指定焦距变化关键帧
- 考虑使用其他跟踪方法（2D 跟踪）

```python
# 变焦镜头：让解算器估算焦距变化
solver.property("focalLengthMode").setValue("variable", 0)
solver.property("minTracks").setValue(20, 0)
```

---

## 六、解算结果验证

### 6.1 验证方法

**方法一：重投影误差**
检查每个跟踪点的重投影误差，误差应小于 2.0 像素。

**方法二：3D 点云合理性**
检查 3D 点云是否符合场景几何（如地面点应在同一平面）。

**方法三：摄像机路径合理性**
检查摄像机运动路径是否平滑、是否符合实际拍摄方式。

**方法四：测试元素合成**
在解算结果上放置测试 3D 元素，检查是否"锁定"在场景中。

### 6.2 验证脚本

```python
def verify_solve(solver_node):
    """验证解算结果"""

    # 获取重投影误差
    error = solver_node.property("reprojectionError").getValue(0)

    # 获取有效点数
    valid_points = solver_node.property("validPointCount").getValue(0)
    total_points = solver_node.property("totalPointCount").getValue(0)

    # 获取解算帧范围
    solve_start = solver_node.property("solveStart").getValue(0)
    solve_end = solver_node.property("solveEnd").getValue(0)

    print("=" * 50)
    print("[SILHOUETTE] 解算结果验证")
    print("=" * 50)
    print(f"重投影误差: {error:.2f} 像素")
    print(f"有效点数: {valid_points}/{total_points}")
    print(f"解算范围: 帧 {solve_start} - {solve_end}")
    print("=" * 50)

    # 评估
    if error < 1.0 and valid_points / max(total_points, 1) > 0.8:
        print("[SILHOUETTE] 解算质量: 优秀")
        return True
    elif error < 2.0:
        print("[SILHOUETTE] 解算质量: 良好")
        return True
    else:
        print("[SILHOUETTE] 解算质量: 需改进")
        return False
```

### 6.3 常见问题

| 问题 | 现象 | 解决方案 |
|------|------|----------|
| 误差过大 | 重投影误差 > 3 像素 | 检查跟踪点质量，增加点数 |
| 摄像机路径抖动 | 路径不平滑 | 平滑跟踪数据，增加关键帧 |
| 点云散乱 | 3D 点位置不合理 | 检查视差，调整焦距 |
| 焦距估算错误 | 焦距偏差大 | 提供已知焦距，固定模式 |
| 解算失败 | 无法解算 | 检查视差是否足够，增加跟踪点 |

---

## 七、3D 跟踪数据应用

### 7.1 导出到 3D 软件

```python
def export_to_3d_software(solver_node, output_path, format="fbx"):
    """导出 3D 跟踪数据到 3D 软件"""

    export_data = {
        "format": format,
        "version": "2026.0.2",
        "camera": {
            "focal_length": solver_node.property("focalLength").getValue(0),
            "sensor_width": 36.0,  # 全画幅
            "frames": []
        },
        "point_cloud": {
            "points": []
        }
    }

    # 获取摄像机动画数据
    frame_start = solver_node.property("solveStart").getValue(0)
    frame_end = solver_node.property("solveEnd").getValue(0)

    for frame in range(frame_start, frame_end + 1):
        cam_data = {
            "frame": frame,
            "position": [0, 0, 0],
            "rotation": [[1,0,0],[0,1,0],[0,0,1]]
        }
        export_data["camera"]["frames"].append(cam_data)

    import json
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"[SILHOUETTE] 3D export completed: {output_path}")
    return output_path
```

### 7.2 与 Maya/Blender 集成

**步骤**：
1. 在 Silhouette 完成摄像机解算
2. 导出 FBX 或 Alembic 格式
3. 在 Maya/Blender 中导入
4. 检查摄像机动画和点云
5. 在 3D 场景中放置元素
6. 渲染并合成回实拍素材

### 7.3 与 AE 集成（3D 摄像机）

```python
def export_3d_camera_to_ae(solver_node, output_path, fps=24.0):
    """导出 3D 摄像机数据到 AE"""

    ae_camera_data = {
        "version": "2.0",
        "camera": {
            "name": "Silhouette_3D_Camera",
            "focal_length": solver_node.property("focalLength").getValue(0),
            "threeD": True
        },
        "keyframes": {
            "Position": [],
            "Rotation": [],
            "Zoom": []
        },
        "fps": fps
    }

    import json
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ae_camera_data, f, indent=2, ensure_ascii=False)

    print(f"[SILHOUETTE] AE 3D camera export: {output_path}")
```

---

## 八、故障排查

### 8.1 解算失败

**原因**：
- 跟踪点数量不足（< 8 点）
- 跟踪点分布不均（聚集在一处）
- 视差不足（摄像机静止）
- 跟踪数据质量差

**解决方案**：
```python
# 增加跟踪点
solver.property("minTracks").setValue(8, 0)

# 检查跟踪点分布
# 在画面四角和中心各放置点
# 包含前景、中景、远景的点
```

### 8.2 解算结果漂移

**原因**：
- 跟踪数据有累积漂移
- 焦距设置错误
- 畸变未校正

**解决方案**：
```python
# 修正焦距
solver.property("focalLengthMode").setValue("fixed", 0)
solver.property("focalLength").setValue(35.0, 0)  # 使用实际焦距

# 启用畸变校正
solver.property("distortion").setValue("brown3", 0)
```

### 8.3 摄像机路径抖动

**原因**：
- 跟踪数据高频噪声
- 关键帧间距过小

**解决方案**：
- 平滑跟踪数据
- 增大关键帧间距
```python
solver.property("keyframeSpacing").setValue(15, 0)
```

### 8.4 点云散乱

**原因**：
- 视差不足
- 跟踪点跨帧不一致
- 焦距估算错误

**解决方案**：
- 选择有明显视差的镜头段
- 确保跟踪点稳定
- 提供已知焦距

### 8.5 质量保证清单

- [ ] 跟踪点数量 ≥ 8（推荐 15+）
- [ ] 跟踪点分布均匀
- [ ] 跟踪点包含不同深度
- [ ] 焦距设置正确
- [ ] 畸变模式匹配
- [ ] 重投影误差 < 2.0 像素
- [ ] 摄像机路径平滑
- [ ] 点云符合场景几何
- [ ] 测试元素锁定良好

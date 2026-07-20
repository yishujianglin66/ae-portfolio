# Silhouette 与Nuke集成工作流

> 分类: 集成与导出
> 更新日期: 2026-07-11
> 概述: Nuke 集成、节点导出、EXR 交换、脚本桥接完整说明。

## 目录
1. [集成概述](#1-集成概述)
2. [数据交换格式](#2-数据交换格式)
3. [EXR 工作流](#3-exr-工作流)
4. [节点导出](#4-节点导出)
5. [脚本桥接](#5-脚本桥接)
6. [坐标系统一](#6-坐标系统一)
7. [实际工作流](#7-实际工作流)
8. [最佳实践](#8-最佳实践)

---

## 1. 集成概述

### 1.1 Silhouette 与 Nuke 的互补性

| 软件 | 优势 | 典型任务 |
|------|------|----------|
| Silhouette | Roto、Paint、跟踪 | 精细遮罩、图像修复 |
| Nuke | 合成、3D、特效 | 最终合成、视觉特效 |

### 1.2 集成方式

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| EXR 文件交换 | 通过中间文件传递 | 标准工作流 |
| 脚本桥接 | Python 脚本通信 | 自动化流程 |
| 节点导出 | 导出 Nuke 节点脚本 | 复杂节点图 |
| 共享数据库 | 共享跟踪数据 | 跟踪复用 |

### 1.3 工作流架构

```
[Silhouette]                  [Nuke]
    │                            │
    ├─ Roto 生成 Matte ──────────┤ → 用于合成
    ├─ Paint 修复图像 ───────────┤ → 替换原图
    ├─ 跟踪数据 ─────────────────┤ → 应用到图层
    └─ 节点图导出 ───────────────┤ → 重建节点
```

## 2. 数据交换格式

### 2.1 支持的交换格式

| 格式 | 用途 | Silhouette | Nuke |
|------|------|------------|------|
| EXR | 图像+多通道 | 读写 | 读写 |
| FBX | 3D 跟踪数据 | 导出 | 导入 |
| Alembic | 几何/点云 | 导出 | 导入 |
| JSON | 跟踪数据 | 读写 | 脚本读 |
| Python | 脚本桥接 | 支持 | 支持 |

### 2.2 EXR 作为交换核心

EXR 是 Silhouette 和 Nuke 之间的首选交换格式:

| 优势 | 说明 |
|------|------|
| 多通道 | 单文件传递 RGBA + Matte + Depth |
| 无损 | 16/32 位浮点 |
| 元数据 | 保留色彩空间等信息 |
| 压缩 | PIZ 压缩节省空间 |

## 3. EXR 工作流

### 3.1 Silhouette 端输出

```python
from fx import *

def export_exr_for_nuke(session, comp_node, matte_nodes=None, output_path="/output/"):
    """导出适合 Nuke 的 EXR"""
    output = Node("Output")
    output.label = "OUT_Nuke_EXR"
    session.addNode(output)
    output.inputs[0].connect(comp_node.outputs[0])
    
    # 配置 EXR
    output.property("format").setValue("exr", 0)
    output.property("compression").setValue("piz", 0)
    output.property("bitDepth").setValue(16, 0)
    output.property("colorspace").setValue("acescg", 0)
    output.property("premultiply").setValue(True, 0)
    
    # 添加 Matte 通道
    if matte_nodes:
        extra_channels = []
        for name, node in matte_nodes.items():
            extra_channels.extend([
                f"{name}.R", f"{name}.G", f"{name}.B", f"{name}.A"
            ])
        output.property("extraChannels").setValue(extra_channels, 0)
    
    # 命名规范
    output.property("outputName").setValue(
        "[project]_[shot]_v[version]_[####].exr", 0
    )
    output.property("outputPath").setValue(output_path, 0)
    
    return output
```

### 3.2 Nuke 端读取

```
# Nuke 节点图
Read [exr_sequence] 
    ↓
Shuffle (提取 matte 通道)
    ↓
Merge (应用到合成)
```

Nuke 中的操作:
1. 创建 Read 节点读取 EXR 序列
2. 创建 Shuffle 节点提取额外通道
3. 设置 Shuffle 的 `in` 参数为 `character_matte` 等
4. 将 Shuffle 输出连接到 Merge 的 mask 输入

### 3.3 通道命名对应

| Silhouette 导出 | Nuke 读取 |
|-----------------|-----------|
| `rgba.RGBA` | `rgba` (默认) |
| `matte.A` | `matte.alpha` (Shuffle 提取) |
| `character_matte.A` | `character_matte.alpha` |
| `depth.Z` | `depth.Z` |
| `motion.UV` | `motion.UV` |

## 4. 节点导出

### 4.1 导出 Nuke 节点脚本

```python
def export_to_nuke_script(session, output_file):
    """将 Silhouette 节点图导出为 Nuke 脚本"""
    nuke_nodes = []
    
    for i in range(session.numNodes):
        node = session.node(i)
        nuke_node = convert_silhouette_to_nuke_node(node)
        if nuke_node:
            nuke_nodes.append(nuke_node)
    
    # 生成 Nuke 脚本
    script = generate_nuke_script(nuke_nodes)
    
    with open(output_file, "w") as f:
        f.write(script)
    
    return output_file

def convert_silhouette_to_nuke_node(sil_node):
    """将 Silhouette 节点转换为 Nuke 节点"""
    converters = {
        "Source": convert_source,
        "RotoShape": convert_roto,
        "Color": convert_color,
        "Filter": convert_filter,
        "Composite": convert_composite,
        "Output": convert_output
    }
    
    converter = converters.get(sil_node.type)
    if converter:
        return converter(sil_node)
    return None

def convert_source(sil_node):
    """转换 Source 节点"""
    path = sil_node.property("path").value if sil_node.property("path") else ""
    return {
        "type": "Read",
        "name": sil_node.label,
        "file": path,
        "format": "1920 1080"
    }

def convert_roto(sil_node):
    """转换 RotoShape 节点为 Nuke Roto"""
    return {
        "type": "Roto",
        "name": sil_node.label,
        "output": "alpha"
    }

def convert_color(sil_node):
    """转换 Color 节点为 Nuke ColorCorrect"""
    lift = sil_node.property("lift").value if sil_node.property("lift") else (0,0,0)
    gamma = sil_node.property("gamma").value if sil_node.property("gamma") else 1.0
    gain = sil_node.property("gain").value if sil_node.property("gain") else (1,1,1)
    
    return {
        "type": "ColorCorrect",
        "name": sil_node.label,
        "lift": {"r": lift[0], "g": lift[1], "b": lift[2]},
        "gamma": gamma,
        "gain": {"r": gain[0], "g": gain[1], "b": gain[2]}
    }

def convert_filter(sil_node):
    """转换 Filter 节点"""
    filter_type = sil_node.property("filterType").value if sil_node.property("filterType") else ""
    radius = sil_node.property("radius").value if sil_node.property("radius") else 5
    
    if "blur" in filter_type:
        return {
            "type": "Blur",
            "name": sil_node.label,
            "size": radius
        }
    elif "sharpen" in filter_type:
        return {
            "type": "Sharpen",
            "name": sil_node.label,
            "size": radius
        }
    return None

def convert_composite(sil_node):
    """转换 Composite 节点为 Nuke Merge"""
    operation = sil_node.property("operation").value if sil_node.property("operation") else "over"
    opacity = sil_node.property("opacity").value if sil_node.property("opacity") else 1.0
    
    return {
        "type": "Merge",
        "name": sil_node.label,
        "operation": operation,
        "mix": opacity
    }

def convert_output(sil_node):
    """转换 Output 节点为 Nuke Write"""
    path = sil_node.property("outputPath").value if sil_node.property("outputPath") else ""
    format = sil_node.property("format").value if sil_node.property("format") else "exr"
    
    return {
        "type": "Write",
        "name": sil_node.label,
        "file": path,
        "file_type": format
    }
```

### 4.2 生成 Nuke 脚本

```python
def generate_nuke_script(nodes):
    """生成 Nuke 脚本"""
    lines = []
    
    for node in nodes:
        lines.append(generate_nuke_node_code(node))
    
    # 添加连接关系
    lines.append(generate_connections(nodes))
    
    return "\n".join(lines)

def generate_nuke_node_code(node):
    """生成单个 Nuke 节点代码"""
    props = []
    for key, value in node.items():
        if key in ["type", "name"]:
            continue
        props.append(f'{key} {format_nuke_value(value)}')
    
    props_str = " ".join(props)
    return f'{node["type"]} {{\n name {node["name"]}\n {props_str}\n}}'

def format_nuke_value(value):
    """格式化为 Nuke 值"""
    if isinstance(value, dict):
        return "{" + " ".join(f"{k} {v}" for k, v in value.items()) + "}"
    elif isinstance(value, str):
        return f'"{value}"'
    return str(value)
```

## 5. 脚本桥接

### 5.1 Python 桥接

```python
class NukeBridge:
    """Nuke 脚本桥接"""
    
    def __init__(self, nuke_executable="nuke"):
        self.nuke = nuke_executable
    
    def execute_nuke_script(self, script_path):
        """执行 Nuke 脚本"""
        import subprocess
        result = subprocess.run(
            [self.nuke, "-t", script_path],
            capture_output=True, text=True
        )
        return result.returncode, result.stdout, result.stderr
    
    def send_track_data(self, track_data, nuke_script_path):
        """发送跟踪数据到 Nuke"""
        # 保存数据为 JSON
        import json
        data_file = "/tmp/silhouette_track.json"
        with open(data_file, "w") as f:
            json.dump(track_data, f)
        
        # 执行 Nuke 脚本读取数据
        script = f"""
import json
import nuke

with open("{data_file}", "r") as f:
    data = json.load(f)

# 在 Nuke 中创建跟踪节点
for track in data["tracks"]:
    tracker = nuke.createNode("Tracker4")
    tracker.setName(track["name"])
    
    for frame_data in track["frames"]:
        tracker["track1"].setValueAt(
            frame_data["x"], 
            frame_data["frame"]
        )
        tracker["track1_y"].setValueAt(
            data["resolution"][1] - frame_data["y"],
            frame_data["frame"]
        )
"""
        with open(nuke_script_path, "w") as f:
            f.write(script)
        
        return self.execute_nuke_script(nuke_script_path)
```

### 5.2 数据同步

```python
class DataSynchronizer:
    """数据同步器"""
    
    def __init__(self, shared_dir):
        self.shared_dir = shared_dir
    
    def export_from_silhouette(self, session, track_data=None):
        """从 Silhouette 导出数据"""
        import json
        import os
        
        # 导出项目信息
        project_info = {
            "source": "silhouette",
            "session": session.label,
            "nodes": []
        }
        
        for i in range(session.numNodes):
            node = session.node(i)
            project_info["nodes"].append({
                "type": node.type,
                "label": node.label
            })
        
        # 保存到共享目录
        info_path = os.path.join(self.shared_dir, "silhouette_data.json")
        with open(info_path, "w") as f:
            json.dump(project_info, f, indent=2)
        
        if track_data:
            track_path = os.path.join(self.shared_dir, "track_data.json")
            with open(track_path, "w") as f:
                json.dump(track_data, f, indent=2)
    
    def import_from_nuke(self):
        """从 Nuke 导入数据"""
        import json
        import os
        
        nuke_data_path = os.path.join(self.shared_dir, "nuke_data.json")
        if not os.path.exists(nuke_data_path):
            return None
        
        with open(nuke_data_path, "r") as f:
            return json.load(f)
```

## 6. 坐标系统一

### 6.1 坐标系对比

| 软件 | 原点 | Y 轴 | 单位 |
|------|------|------|------|
| Silhouette | 左下角 | 向上 | 像素 |
| Nuke | 左下角 | 向上 | 像素 |

**好消息**:Silhouette 和 Nuke 的坐标系一致,无需翻转!

### 6.2 坐标转换

```python
def silhouette_to_nuke_coords(x, y):
    """Silhouette 坐标转 Nuke 坐标(相同)"""
    return x, y  # 坐标系一致

def nuke_to_silhouette_coords(x, y):
    """Nuke 坐标转 Silhouette 坐标(相同)"""
    return x, y  # 坐标系一致
```

### 6.3 变换矩阵转换

```python
def convert_transform_matrix(sil_matrix):
    """转换变换矩阵(由于坐标系一致,无需转换)"""
    return sil_matrix

# Nuke 2D 变换矩阵格式:
# | a  b  tx |
# | c  d  ty |
# | 0  0  1  |
# 与 Silhouette 相同
```

## 7. 实际工作流

### 7.1 标准 Silhouette→Nuke 工作流

```
1. Silhouette:
   a. 导入素材
   b. 进行 Roto/Paint/跟踪
   c. 导出 EXR(含多通道 Matte)
   d. 导出跟踪数据(JSON)

2. Nuke:
   a. Read 节点读取 EXR
   b. Shuffle 节点提取 Matte 通道
   c. 读取跟踪数据应用到图层
   d. 进行最终合成
   e. 输出最终结果
```

### 7.2 完整集成脚本

```python
def full_integration_workflow(session, source, roto_nodes, output_dir):
    """完整的 Silhouette→Nuke 集成工作流"""
    
    # 1. 创建合成
    comp = Node("Composite")
    session.addNode(comp)
    comp.inputs[0].connect(source.outputs[0])
    comp.inputs[1].connect(source.outputs[0])
    
    # 连接 Roto 作为遮罩
    if roto_nodes:
        first_roto = list(roto_nodes.values())[0]
        if len(comp.inputs) > 2:
            comp.inputs[2].connect(first_roto.outputs[0])
    
    # 2. 导出 EXR(含 Matte)
    matte_dict = {name: node for name, node in roto_nodes.items()}
    export_exr_for_nuke(session, comp, matte_dict, output_dir)
    
    # 3. 导出 Nuke 脚本
    nuke_script_path = output_dir + "/nuke_setup.nk"
    export_to_nuke_script(session, nuke_script_path)
    
    # 4. 生成 Nuke 读取脚本
    generate_nuke_read_script(output_dir, matte_dict.keys())
    
    print(f"集成文件已生成到: {output_dir}")
    return output_dir

def generate_nuke_read_script(output_dir, matte_names):
    """生成 Nuke 读取脚本"""
    script = f"""
# Nuke 脚本:读取 Silhouette 导出的 EXR
# 自动生成

# 读取主图像
Read1 = Read {{
    file "{output_dir}/plate_v01_####.exr"
    first 1
    last 100
}}

"""
    for name in matte_names:
        script += f"""
# 提取 {name} 通道
Shuffle_{name} = Shuffle {{
    inputs Read1
    in {name}
    out alpha
}}

"""
    
    script_path = output_dir + "/nuke_read.nk"
    with open(script_path, "w") as f:
        f.write(script)
    
    return script_path
```

### 7.3 Nuke→Silhouette 反向工作流

```python
def import_from_nuke(session, nuke_output_path):
    """从 Nuke 导入合成结果到 Silhouette"""
    source = Node("Source")
    source.label = "SRC_Nuke_Output"
    source.property("path").setValue(nuke_output_path + "/####.exr", 0)
    session.addNode(source)
    
    # 创建查看输出
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(source.outputs[0])
    
    return source
```

## 8. 最佳实践

### 8.1 文件组织

```
/project/
  /silhouette/
    /projects/     # Silhouette 项目文件
    /exports/      # 导出的 EXR
  /nuke/
    /scripts/      # Nuke 脚本
    /renders/      # Nuke 渲染输出
  /shared/
    /exr/          # 共享 EXR 文件
    /track/        # 跟踪数据
    /config/       # 配置文件
```

### 8.2 命名规范

```
Silhouette 导出:
  [project]_[shot]_SILH_[type]_v[version]_[####].exr

Nuke 输出:
  [project]_[shot]_NUKE_[type]_v[version]_[####].exr

示例:
  PROJ001_SH0100_SILH_MATTE_v01_0001.exr
  PROJ001_SH0100_NUKE_COMP_v01_0001.exr
```

### 8.3 版本控制

```python
def create_versioned_export(session, output_dir, version):
    """版本化导出"""
    import os
    
    version_dir = os.path.join(output_dir, f"v{version:02d}")
    os.makedirs(version_dir, exist_ok=True)
    
    # 导出 EXR
    export_exr_for_nuke(session, comp_node, matte_nodes, version_dir)
    
    # 导出元数据
    metadata = {
        "version": version,
        "created": "2026-07-11",
        "source": "silhouette",
        "session": session.label
    }
    
    import json
    with open(os.path.join(version_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    
    return version_dir
```

### 8.4 错误处理

```python
def validate_integration(output_dir):
    """验证集成文件"""
    import os
    issues = []
    
    # 检查 EXR 文件
    exr_files = [f for f in os.listdir(output_dir) if f.endswith(".exr")]
    if not exr_files:
        issues.append("没有 EXR 文件")
    
    # 检查 Nuke 脚本
    nuke_scripts = [f for f in os.listdir(output_dir) if f.endswith(".nk")]
    if not nuke_scripts:
        issues.append("没有 Nuke 脚本")
    
    # 检查元数据
    if not os.path.exists(os.path.join(output_dir, "metadata.json")):
        issues.append("缺少元数据文件")
    
    return issues
```

---

## 附录:节点对应表

| Silhouette | Nuke | 说明 |
|------------|------|------|
| Source | Read | 读取素材 |
| RotoShape | Roto | Roto 遮罩 |
| Paint | RotoPaint | 绘制修复 |
| Tracker | Tracker4 | 跟踪 |
| Color | ColorCorrect | 色彩校正 |
| Filter(Blur) | Blur | 模糊 |
| Filter(Sharpen) | Sharpen | 锐化 |
| Composite | Merge | 合成 |
| Output | Write | 输出 |
| Matte | Shuffle | 通道操作 |

> **提示**:Silhouette 和 Nuke 坐标系一致,无需 Y 轴翻转,大大简化了集成工作。但要注意色彩空间的一致性。

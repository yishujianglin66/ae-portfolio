# Silhouette 项目模板与预设系统

> 分类: 自动化与批处理
> 更新日期: 2026-07-11
> 概述: 项目模板创建、预设保存加载、参数继承机制完整说明。

## 目录
1. [模板系统概述](#1-模板系统概述)
2. [项目模板](#2-项目模板)
3. [节点预设](#3-节点预设)
4. [参数继承](#4-参数继承)
5. [模板管理](#5-模板管理)
6. [脚本化模板](#6-脚本化模板)
7. [模板库设计](#7-模板库设计)
8. [最佳实践](#8-最佳实践)

---

## 1. 模板系统概述

### 1.1 模板与预设的价值

| 价值 | 说明 |
|------|------|
| 一致性 | 确保团队成员使用相同配置 |
| 效率 | 避免重复设置,快速启动 |
| 标准化 | 统一输出格式和命名 |
| 可维护 | 修改模板即可影响所有新项目 |
| 知识沉淀 | 将最佳实践固化为模板 |

### 1.2 模板层级

```
项目模板(Project Template)
  └── Session 模板
        └── 节点预设(Node Preset)
              └── 参数预设(Parameter Preset)
```

## 2. 项目模板

### 2.1 项目模板结构

```json
{
    "template_name": "VFX_Standard",
    "version": "1.0",
    "description": "标准 VFX 项目模板",
    "project_settings": {
        "resolution": [1920, 1080],
        "frame_rate": 24,
        "colorspace": "acescg",
        "bit_depth": 16
    },
    "sessions": [
        {
            "name": "Main_Session",
            "nodes": [
                {
                    "type": "Source",
                    "label": "SRC_Plate",
                    "properties": {}
                },
                {
                    "type": "Tracker",
                    "label": "TRK_Main",
                    "properties": {
                        "trackerType": "planar"
                    }
                },
                {
                    "type": "RotoShape",
                    "label": "ROTO_Main",
                    "properties": {}
                },
                {
                    "type": "Output",
                    "label": "OUT_Final",
                    "properties": {
                        "format": "exr",
                        "compression": "piz"
                    }
                }
            ],
            "connections": [
                [0, 1, 0],
                [0, 2, 0],
                [2, 3, 0]
            ]
        }
    ]
}
```

### 2.2 创建项目模板

```python
from fx import *
import json

def create_project_template(name, resolution=(1920, 1080), frame_rate=24,
                             colorspace="acescg"):
    """创建项目模板"""
    template = {
        "template_name": name,
        "version": "1.0",
        "project_settings": {
            "resolution": list(resolution),
            "frame_rate": frame_rate,
            "colorspace": colorspace,
            "bit_depth": 16
        },
        "sessions": []
    }
    return template

def add_session_template(project_template, session_name, node_specs, connections):
    """添加 Session 模板"""
    session = {
        "name": session_name,
        "nodes": node_specs,
        "connections": connections
    }
    project_template["sessions"].append(session)
    return project_template

# 创建标准模板
template = create_project_template("VFX_Standard", (1920, 1080), 24, "acescg")

# 添加主 Session
add_session_template(template, "Main_Session",
    node_specs=[
        {"type": "Source", "label": "SRC_Plate"},
        {"type": "RotoShape", "label": "ROTO_Main"},
        {"type": "Output", "label": "OUT_Final",
         "properties": {"format": "exr", "compression": "piz"}}
    ],
    connections=[(0, 1, 0), (1, 2, 0)]
)
```

### 2.3 保存与加载模板

```python
def save_template(template, file_path):
    """保存模板到文件"""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

def load_template(file_path):
    """从文件加载模板"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# 保存
save_template(template, "/templates/vfx_standard.json")

# 加载
template = load_template("/templates/vfx_standard.json")
```

### 2.4 应用项目模板

```python
def apply_project_template(template):
    """应用项目模板创建新项目"""
    project = Project()
    
    settings = template["project_settings"]
    
    for session_template in template["sessions"]:
        session = Session()
        session.label = session_template["name"]
        project.addItem(session)
        session.activate()
        
        # 设置分辨率和帧率
        session.width = settings["resolution"][0]
        session.height = settings["resolution"][1]
        session.frameRate = settings["frame_rate"]
        
        # 创建节点
        nodes = []
        for node_spec in session_template["nodes"]:
            node = Node(node_spec["type"])
            node.label = node_spec.get("label", node_spec["type"])
            session.addNode(node)
            
            # 应用属性
            for prop_name, prop_value in node_spec.get("properties", {}).items():
                prop = node.property(prop_name)
                if prop:
                    prop.setValue(prop_value, 0)
            
            nodes.append(node)
        
        # 连接节点
        for src_idx, tgt_idx, input_idx in session_template["connections"]:
            nodes[tgt_idx].inputs[input_idx].connect(nodes[src_idx].outputs[0])
    
    return project
```

## 3. 节点预设

### 3.1 节点预设结构

```json
{
    "preset_name": "Roto_Hair",
    "node_type": "RotoShape",
    "description": "头发 Roto 预设",
    "properties": {
        "feather": 2.0,
        "motionBlur": true,
        "motionBlurShutter": 0.5,
        "motionBlurSamples": 8
    }
}
```

### 3.2 创建节点预设

```python
def create_node_preset(node, preset_name, description=""):
    """从现有节点创建预设"""
    preset = {
        "preset_name": preset_name,
        "node_type": node.type,
        "description": description,
        "properties": {}
    }
    
    # 收集所有属性
    for prop_name in node.properties:
        prop = node.property(prop_name)
        if prop:
            preset["properties"][prop_name] = prop.value
    
    return preset

# 从现有节点创建预设
roto_node = find_node_by_label(session, "ROTO_Hair_Template")
preset = create_node_preset(roto_node, "Roto_Hair", "头发 Roto 标准设置")
save_preset(preset, "/presets/roto_hair.json")
```

### 3.3 应用节点预设

```python
def apply_node_preset(node, preset):
    """应用预设到节点"""
    if node.type != preset["node_type"]:
        raise ValueError(f"节点类型不匹配: {node.type} vs {preset['node_type']}")
    
    for prop_name, prop_value in preset["properties"].items():
        prop = node.property(prop_name)
        if prop:
            prop.setValue(prop_value, 0)
    
    return node

# 应用预设
roto = Node("RotoShape")
session.addNode(roto)

preset = load_preset("/presets/roto_hair.json")
apply_node_preset(roto, preset)
```

### 3.4 预设库

```python
class PresetLibrary:
    """预设库管理"""
    
    def __init__(self, library_path):
        self.library_path = library_path
        self.presets = {}
        self._load_all()
    
    def _load_all(self):
        """加载所有预设"""
        import os
        if not os.path.exists(self.library_path):
            return
        
        for filename in os.listdir(self.library_path):
            if filename.endswith(".json"):
                preset = load_preset(os.path.join(self.library_path, filename))
                self.presets[preset["preset_name"]] = preset
    
    def get_preset(self, name):
        """获取预设"""
        return self.presets.get(name)
    
    def list_presets(self, node_type=None):
        """列出预设"""
        if node_type:
            return {k: v for k, v in self.presets.items()
                    if v["node_type"] == node_type}
        return self.presets
    
    def add_preset(self, preset):
        """添加预设"""
        self.presets[preset["preset_name"]] = preset
        save_preset(preset, os.path.join(
            self.library_path,
            f"{preset['preset_name']}.json"
        ))
    
    def remove_preset(self, name):
        """删除预设"""
        if name in self.presets:
            del self.presets[name]
            filepath = os.path.join(self.library_path, f"{name}.json")
            if os.path.exists(filepath):
                os.remove(filepath)

# 使用
library = PresetLibrary("/presets")
roto_presets = library.list_presets("RotoShape")
```

## 4. 参数继承

### 4.1 继承机制

参数继承允许子预设继承父预设的参数,并覆盖部分值。

```json
{
    "preset_name": "Roto_Hair_Fast",
    "parent": "Roto_Hair",
    "overrides": {
        "motionBlurSamples": 4,
        "feather": 1.0
    }
}
```

### 4.2 继承解析

```python
def resolve_preset(preset, library):
    """解析继承,返回完整预设"""
    if "parent" not in preset:
        return preset
    
    parent = library.get_preset(preset["parent"])
    if not parent:
        return preset
    
    # 递归解析父预设
    parent = resolve_preset(parent, library)
    
    # 合并:父预设 + 覆盖
    resolved = {
        "preset_name": preset["preset_name"],
        "node_type": parent["node_type"],
        "description": preset.get("description", parent.get("description", "")),
        "properties": {}
    }
    
    # 继承父属性
    resolved["properties"].update(parent["properties"])
    
    # 应用覆盖
    resolved["properties"].update(preset.get("overrides", {}))
    
    return resolved
```

### 4.3 多级继承

```python
# 基础预设
{
    "preset_name": "Roto_Base",
    "node_type": "RotoShape",
    "properties": {
        "feather": 1.0,
        "motionBlur": true,
        "motionBlurShutter": 0.5,
        "motionBlurSamples": 8
    }
}

# 中间预设
{
    "preset_name": "Roto_Hair",
    "parent": "Roto_Base",
    "overrides": {
        "feather": 2.0
    }
}

# 最终预设
{
    "preset_name": "Roto_Hair_Fast",
    "parent": "Roto_Hair",
    "overrides": {
        "motionBlurSamples": 4
    }
}

# 解析后:Roto_Hair_Fast
# feather: 2.0 (继承自 Roto_Hair)
# motionBlur: true (继承自 Roto_Base)
# motionBlurShutter: 0.5 (继承自 Roto_Base)
# motionBlurSamples: 4 (Roto_Hair_Fast 覆盖)
```

## 5. 模板管理

### 5.1 模板版本控制

```python
class VersionedTemplate:
    """版本化模板"""
    
    def __init__(self, template_dir):
        self.template_dir = template_dir
    
    def save_version(self, template, name):
        """保存新版本"""
        version = self._get_latest_version(name) + 1
        filepath = os.path.join(
            self.template_dir,
            f"{name}_v{version:03d}.json"
        )
        template["version"] = f"{version}.0"
        save_template(template, filepath)
        return filepath
    
    def _get_latest_version(self, name):
        """获取最新版本号"""
        import re
        versions = []
        if os.path.exists(self.template_dir):
            for f in os.listdir(self.template_dir):
                match = re.match(rf"^{name}_v(\d+)\.json$", f)
                if match:
                    versions.append(int(match.group(1)))
        return max(versions) if versions else 0
    
    def load_version(self, name, version=None):
        """加载指定版本(默认最新)"""
        if version is None:
            version = self._get_latest_version(name)
        filepath = os.path.join(
            self.template_dir,
            f"{name}_v{version:03d}.json"
        )
        return load_template(filepath)
```

### 5.2 模板对比

```python
def compare_templates(template_a, template_b):
    """对比两个模板的差异"""
    diff = {
        "added": {},
        "removed": {},
        "modified": {}
    }
    
    props_a = template_a.get("project_settings", {})
    props_b = template_b.get("project_settings", {})
    
    for key in set(props_a.keys()) | set(props_b.keys()):
        if key not in props_a:
            diff["added"][key] = props_b[key]
        elif key not in props_b:
            diff["removed"][key] = props_a[key]
        elif props_a[key] != props_b[key]:
            diff["modified"][key] = {"from": props_a[key], "to": props_b[key]}
    
    return diff
```

## 6. 脚本化模板

### 6.1 模板生成脚本

```python
def generate_template_from_project(project, template_name):
    """从现有项目生成模板"""
    template = {
        "template_name": template_name,
        "version": "1.0",
        "project_settings": {
            "resolution": [1920, 1080],
            "frame_rate": 24,
            "colorspace": "acescg"
        },
        "sessions": []
    }
    
    for i in range(project.numItems):
        item = project.item(i)
        if not isinstance(item, Session):
            continue
        
        session_template = {
            "name": item.label,
            "nodes": [],
            "connections": []
        }
        
        nodes = [item.node(j) for j in range(item.numNodes)]
        
        # 收集节点
        for node in nodes:
            node_spec = {
                "type": node.type,
                "label": node.label,
                "properties": {}
            }
            for prop_name in node.properties:
                prop = node.property(prop_name)
                if prop:
                    node_spec["properties"][prop_name] = prop.value
            session_template["nodes"].append(node_spec)
        
        # 收集连接
        for tgt_idx, node in enumerate(nodes):
            for input_idx, port in enumerate(node.inputs):
                if port.source:
                    src_idx = nodes.index(port.source)
                    session_template["connections"].append(
                        [src_idx, tgt_idx, input_idx]
                    )
        
        template["sessions"].append(session_template)
    
    return template
```

### 6.2 模板批量应用

```python
def batch_apply_template(template, shot_list):
    """批量应用模板到多个镜头"""
    results = []
    
    for shot in shot_list:
        # 应用模板
        project = apply_project_template(template)
        
        # 配置源素材
        session = project.item(0)
        source_node = find_node_by_type(session, "Source")
        if source_node:
            source_node.property("path").setValue(shot["source"], 0)
            source_node.property("startFrame").setValue(shot["start"], 0)
            source_node.property("endFrame").setValue(shot["end"], 0)
        
        # 配置输出
        output_node = find_node_by_type(session, "Output")
        if output_node:
            output_node.property("outputPath").setValue(shot["output"], 0)
        
        # 保存项目
        project.save(f"/projects/{shot['id']}.sfx")
        results.append(shot["id"])
    
    return results
```

## 7. 模板库设计

### 7.1 模板分类

```python
TEMPLATE_CATEGORIES = {
    "roto": {
        "description": "Roto 工作流模板",
        "templates": [
            "roto_basic",
            "roto_tracked",
            "roto_hair",
            "roto_stereo"
        ]
    },
    "paint": {
        "description": "Paint 修复模板",
        "templates": [
            "paint_cleanup",
            "paint_clone",
            "paint_wire_removal"
        ]
    },
    "vfx": {
        "description": "完整 VFX 工作流",
        "templates": [
            "vfx_standard",
            "vfx_full_pipeline",
            "vfx_green_screen"
        ]
    },
    "export": {
        "description": "导出模板",
        "templates": [
            "export_matte",
            "export_exr_multichannel",
            "export_ae_preset"
        ]
    }
}
```

### 7.2 模板搜索引擎

```python
class TemplateSearch:
    """模板搜索"""
    
    def __init__(self, template_dir):
        self.template_dir = template_dir
        self.index = {}
        self._build_index()
    
    def _build_index(self):
        """构建搜索索引"""
        import os
        for filename in os.listdir(self.template_dir):
            if filename.endswith(".json"):
                template = load_template(os.path.join(self.template_dir, filename))
                self.index[template["template_name"]] = {
                    "template": template,
                    "keywords": self._extract_keywords(template)
                }
    
    def _extract_keywords(self, template):
        """提取关键词"""
        keywords = set()
        keywords.add(template["template_name"].lower())
        
        for session in template.get("sessions", []):
            for node in session.get("nodes", []):
                keywords.add(node["type"].lower())
                keywords.add(node.get("label", "").lower())
        
        return keywords
    
    def search(self, query):
        """搜索模板"""
        query_words = set(query.lower().split())
        results = []
        
        for name, entry in self.index.items():
            if query_words & entry["keywords"]:
                results.append(entry["template"])
        
        return results
```

## 8. 最佳实践

### 8.1 模板设计原则

1. **单一职责**:每个模板解决一类问题
2. **参数化**:模板应支持参数覆盖
3. **可扩展**:便于添加新节点和连接
4. **文档化**:每个模板附带说明
5. **版本化**:重要模板应版本控制

### 8.2 命名规范

```
模板命名:[分类]_[任务]_[变体]_[版本]

示例:
  roto_hair_basic_v01
  paint_cleanup_markers_v02
  vfx_full_pipeline_v03
  export_matte_exr_v01
```

### 8.3 模板测试

```python
def validate_template(template):
    """验证模板有效性"""
    issues = []
    
    # 检查必要字段
    if "template_name" not in template:
        issues.append("缺少 template_name")
    
    if "sessions" not in template:
        issues.append("缺少 sessions")
        return issues
    
    # 检查每个 session
    for i, session in enumerate(template["sessions"]):
        if "nodes" not in session:
            issues.append(f"Session {i} 缺少 nodes")
            continue
        
        # 检查连接索引有效性
        num_nodes = len(session["nodes"])
        for conn in session.get("connections", []):
            src, tgt, inp = conn
            if src >= num_nodes or tgt >= num_nodes:
                issues.append(f"Session {i} 连接索引越界: {conn}")
    
    return issues
```

### 8.4 团队协作

```python
# 模板共享路径
SHARED_TEMPLATE_PATH = "/network/templates"

def sync_templates(local_path, remote_path):
    """同步本地与远程模板"""
    import shutil
    # 从远程拉取最新模板
    for filename in os.listdir(remote_path):
        if filename.endswith(".json"):
            shutil.copy2(
                os.path.join(remote_path, filename),
                os.path.join(local_path, filename)
            )

def publish_template(template, remote_path):
    """发布模板到共享路径"""
    name = template["template_name"]
    version = template.get("version", "1.0")
    filepath = os.path.join(remote_path, f"{name}_v{version}.json")
    save_template(template, filepath)
```

---

## 附录:模板结构速查

| 层级 | 字段 | 说明 |
|------|------|------|
| 项目 | `template_name` | 模板名称 |
| 项目 | `version` | 版本号 |
| 项目 | `project_settings` | 项目设置 |
| Session | `name` | Session 名称 |
| Session | `nodes` | 节点列表 |
| Session | `connections` | 连接关系 |
| 节点 | `type` | 节点类型 |
| 节点 | `label` | 节点标签 |
| 节点 | `properties` | 属性值 |
| 预设 | `preset_name` | 预设名称 |
| 预设 | `parent` | 父预设(继承) |
| 预设 | `overrides` | 覆盖参数 |

> **提示**:设计模板时,先用 GUI 手动搭建一个理想的项目结构,再用 `generate_template_from_project()` 自动生成模板,可大幅提高效率。

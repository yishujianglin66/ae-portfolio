# Silhouette 项目模板库

> 分类: 预设与配置
> 更新日期: 2026-07-11
> 概述: 项目模板分类、模板参数、使用方法、自定义模板完整说明。

## 目录
1. [模板库概述](#1-模板库概述)
2. [模板分类](#2-模板分类)
3. [模板参数](#3-模板参数)
4. [使用方法](#4-使用方法)
5. [自定义模板](#5-自定义模板)
6. [模板管理](#6-模板管理)
7. [脚本化模板](#7-脚本化模板)
8. [最佳实践](#8-最佳实践)

---

## 1. 模板库概述

### 1.1 什么是项目模板库

项目模板库是预定义的项目配置集合,针对不同场景提供优化起点,加速项目启动。

### 1.2 模板库价值

| 价值 | 说明 |
|------|------|
| 快速启动 | 无需从零配置 |
| 标准化 | 统一项目结构 |
| 最佳实践 | 内置经验积累 |
| 减少错误 | 预验证的配置 |
| 团队一致 | 所有人使用相同起点 |

### 1.3 模板 vs 预设

| 特性 | 模板 | 预设 |
|------|------|------|
| 范围 | 整个项目 | 单个节点/效果 |
| 用途 | 项目起点 | 参数复用 |
| 结构 | 完整节点图 | 参数集合 |
| 应用时机 | 创建项目时 | 任何时候 |

## 2. 模板分类

### 2.1 按任务分类

| 分类 | 模板名 | 说明 |
|------|--------|------|
| Roto | Roto_Basic | 基础 Roto 工作流 |
| Roto | Roto_Tracked | 跟踪驱动 Roto |
| Roto | Roto_Hair | 头发 Roto 专用 |
| Roto | Roto_Stereo | 立体3D Roto |
| Paint | Paint_Cleanup | 瑕疵修复 |
| Paint | Paint_Clone | 克隆修复 |
| Paint | Paint_WireRemoval | 威亚去除 |
| VFX | VFX_Standard | 标准 VFX 流程 |
| VFX | VFX_GreenScreen | 绿幕抠像 |
| VFX | VFX_FullPipeline | 完整 VFX 管线 |
| Export | Export_Matte | Matte 导出 |
| Export | Export_MultiChannel | 多通道导出 |
| Export | Export_AE_Preset | AE 集成导出 |

### 2.2 按项目类型分类

| 类型 | 模板 | 分辨率 | 帧率 | 色彩空间 |
|------|------|--------|------|----------|
| 电影 | Film_Standard | 4K | 24 | acescg |
| 电视剧 | TV_Standard | 1080p | 25/30 | rec709 |
| 网络 | Web_Standard | 1080p | 30 | srgb |
| 广告 | Commercial | 4K | 30 | rec709 |
| VR | VR_360 | 4K+ | 60 | srgb |
| 立体 | Stereo_3D | 2K×2 | 24 | rec709 |

### 2.3 按复杂度分类

| 级别 | 节点数 | 适用场景 |
|------|--------|----------|
| 简单 | 3-5 | 单一任务 |
| 中等 | 5-10 | 标准工作流 |
| 复杂 | 10-20 | 完整 VFX |
| 高级 | 20+ | 复杂合成 |

## 3. 模板参数

### 3.1 项目级参数

```json
{
    "project_settings": {
        "resolution": [1920, 1080],
        "frame_rate": 24,
        "colorspace": "acescg",
        "bit_depth": 16,
        "pixel_aspect": 1.0,
        "field_order": "progressive"
    }
}
```

### 3.2 节点级参数

```json
{
    "nodes": [
        {
            "type": "Source",
            "label": "SRC_Plate",
            "properties": {
                "path": "",
                "startFrame": 1,
                "endFrame": 100,
                "colorspace": "auto"
            }
        },
        {
            "type": "RotoShape",
            "label": "ROTO_Main",
            "properties": {
                "feather": 1.5,
                "motionBlur": true,
                "motionBlurShutter": 0.5,
                "motionBlurSamples": 8
            }
        }
    ]
}
```

### 3.3 输出参数

```json
{
    "output_settings": {
        "format": "exr",
        "compression": "piz",
        "bitDepth": 16,
        "colorspace": "acescg",
        "premultiply": true,
        "naming": "[project]_[shot]_[version]_[####].[ext]",
        "path": "/output/{project}/{shot}/"
    }
}
```

### 3.4 参数变量

```python
TEMPLATE_VARIABLES = {
    "{project}": "项目名称",
    "{shot}": "镜头编号",
    "{version}": "版本号",
    "{date}": "日期",
    "{artist}": "艺术家名",
    "{resolution}": "分辨率",
    "{framerate}": "帧率"
}

def resolve_variables(template_str, context):
    """解析模板变量"""
    for var, value in context.items():
        template_str = template_str.replace(f"{{{var}}}", str(value))
    return template_str
```

## 4. 使用方法

### 4.1 选择模板

```python
class TemplateSelector:
    """模板选择器"""
    
    def __init__(self, template_library):
        self.library = template_library
    
    def select_by_task(self, task_type):
        """按任务类型选择"""
        task_templates = {
            "roto": ["Roto_Basic", "Roto_Tracked", "Roto_Hair"],
            "paint": ["Paint_Cleanup", "Paint_Clone"],
            "vfx": ["VFX_Standard", "VFX_GreenScreen"],
            "export": ["Export_Matte", "Export_MultiChannel"]
        }
        
        return [self.library.get(t) for t in task_templates.get(task_type, [])]
    
    def select_by_project_type(self, project_type):
        """按项目类型选择"""
        project_templates = {
            "film": "Film_Standard",
            "tv": "TV_Standard",
            "web": "Web_Standard",
            "commercial": "Commercial"
        }
        
        template_name = project_templates.get(project_type)
        return self.library.get(template_name) if template_name else None
    
    def recommend(self, context):
        """智能推荐模板"""
        recommendations = []
        
        # 基于任务
        task = context.get("task")
        if task:
            templates = self.select_by_task(task)
            recommendations.extend(templates)
        
        # 基于项目类型
        project_type = context.get("project_type")
        if project_type:
            template = self.select_by_project_type(project_type)
            if template:
                recommendations.insert(0, template)
        
        return recommendations
```

### 4.2 应用模板

```python
def apply_template(template, context=None):
    """应用模板创建项目"""
    from fx import *
    
    if context is None:
        context = {}
    
    # 创建项目
    project = Project()
    
    # 应用项目设置
    settings = template.get("project_settings", {})
    if "resolution" in settings:
        project.resolution = settings["resolution"]
    if "frame_rate" in settings:
        project.frameRate = settings["frame_rate"]
    
    # 创建 Sessions
    for session_template in template.get("sessions", []):
        session = Session()
        session.label = session_template.get("name", "Session")
        project.addItem(session)
        session.activate()
        
        # 创建节点
        nodes = []
        for node_spec in session_template.get("nodes", []):
            node = Node(node_spec["type"])
            node.label = node_spec.get("label", node_spec["type"])
            session.addNode(node)
            
            # 应用属性
            for prop_name, prop_value in node_spec.get("properties", {}).items():
                prop = node.property(prop_name)
                if prop:
                    # 解析变量
                    if isinstance(prop_value, str):
                        prop_value = resolve_variables(prop_value, context)
                    prop.setValue(prop_value, 0)
            
            nodes.append(node)
        
        # 连接节点
        for conn in session_template.get("connections", []):
            src_idx, tgt_idx, input_idx = conn
            if src_idx < len(nodes) and tgt_idx < len(nodes):
                nodes[tgt_idx].inputs[input_idx].connect(
                    nodes[src_idx].outputs[0]
                )
    
    return project
```

## 5. 自定义模板

### 5.1 从现有项目创建模板

```python
def create_template_from_project(project, template_name, description=""):
    """从现有项目创建模板"""
    template = {
        "template_name": template_name,
        "version": "1.0",
        "description": description,
        "created": "2026-07-11",
        "project_settings": {
            "resolution": [project.width, project.height],
            "frame_rate": project.frameRate
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

### 5.2 模板定制

```python
class TemplateCustomizer:
    """模板定制器"""
    
    def customize(self, template, customizations):
        """定制模板"""
        # 修改项目设置
        if "project_settings" in customizations:
            template["project_settings"].update(
                customizations["project_settings"]
            )
        
        # 修改节点
        if "node_overrides" in customizations:
            for session in template.get("sessions", []):
                for node in session.get("nodes", []):
                    label = node.get("label")
                    if label in customizations["node_overrides"]:
                        node["properties"].update(
                            customizations["node_overrides"][label]
                        )
        
        # 添加额外节点
        if "additional_nodes" in customizations:
            for session in template.get("sessions", []):
                session["nodes"].extend(
                    customizations["additional_nodes"]
                )
        
        return template

# 使用
customizer = TemplateCustomizer()
customizations = {
    "project_settings": {
        "resolution": [3840, 2160],  # 改为 4K
        "frame_rate": 30
    },
    "node_overrides": {
        "ROTO_Main": {
            "feather": 3.0,
            "motionBlurSamples": 16
        }
    }
}
customized = customizer.customize(base_template, customizations)
```

## 6. 模板管理

### 6.1 模板库管理

```python
import os
import json

class TemplateLibrary:
    """模板库"""
    
    def __init__(self, library_path):
        self.library_path = library_path
        self.templates = {}
        self._load_all()
    
    def _load_all(self):
        """加载所有模板"""
        if not os.path.exists(self.library_path):
            return
        
        for filename in os.listdir(self.library_path):
            if filename.endswith(".json"):
                filepath = os.path.join(self.library_path, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    template = json.load(f)
                self.templates[template["template_name"]] = template
    
    def get(self, name):
        """获取模板"""
        return self.templates.get(name)
    
    def save(self, template):
        """保存模板"""
        name = template["template_name"]
        self.templates[name] = template
        
        filepath = os.path.join(self.library_path, f"{name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
    
    def delete(self, name):
        """删除模板"""
        if name in self.templates:
            del self.templates[name]
            filepath = os.path.join(self.library_path, f"{name}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def list_by_category(self, category):
        """按分类列出模板"""
        return [t for t in self.templates.values()
                if t.get("category") == category]
    
    def search(self, query):
        """搜索模板"""
        query = query.lower()
        return [t for t in self.templates.values()
                if query in t["template_name"].lower() or
                query in t.get("description", "").lower()]
```

### 6.2 版本管理

```python
class VersionedTemplateLibrary:
    """版本化模板库"""
    
    def __init__(self, library_path):
        self.library_path = library_path
    
    def save_version(self, template):
        """保存新版本"""
        name = template["template_name"]
        version = self._get_latest_version(name) + 1
        template["version"] = f"{version}.0"
        
        filepath = os.path.join(
            self.library_path,
            f"{name}_v{version:03d}.json"
        )
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
        
        return version
    
    def _get_latest_version(self, name):
        """获取最新版本"""
        import re
        versions = []
        
        if os.path.exists(self.library_path):
            for f in os.listdir(self.library_path):
                match = re.match(rf"^{name}_v(\d+)\.json$", f)
                if match:
                    versions.append(int(match.group(1)))
        
        return max(versions) if versions else 0
    
    def load_version(self, name, version=None):
        """加载指定版本"""
        if version is None:
            version = self._get_latest_version(name)
        
        filepath = os.path.join(
            self.library_path,
            f"{name}_v{version:03d}.json"
        )
        
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
```

## 7. 脚本化模板

### 7.1 批量创建项目

```python
def batch_create_projects(template, shot_list, output_dir):
    """批量从模板创建项目"""
    results = []
    
    for shot in shot_list:
        # 定制模板
        customizer = TemplateCustomizer()
        customizations = {
            "project_settings": {
                "resolution": shot.get("resolution", [1920, 1080]),
                "frame_rate": shot.get("frame_rate", 24)
            },
            "node_overrides": {
                "SRC_Plate": {
                    "path": shot["source_path"],
                    "startFrame": shot["start_frame"],
                    "endFrame": shot["end_frame"]
                },
                "OUT_Final": {
                    "outputPath": f"{output_dir}/{shot['id']}/"
                }
            }
        }
        
        customized = customizer.customize(template, customizations)
        
        # 创建项目
        project = apply_template(customized, shot)
        
        # 保存
        project_path = f"{output_dir}/{shot['id']}.sfx"
        project.save(project_path)
        
        results.append({
            "shot_id": shot["id"],
            "project_path": project_path,
            "status": "created"
        })
    
    return results
```

### 7.2 模板验证

```python
def validate_template(template):
    """验证模板"""
    issues = []
    
    # 检查必要字段
    if "template_name" not in template:
        issues.append("缺少 template_name")
    
    if "sessions" not in template:
        issues.append("缺少 sessions")
        return issues
    
    # 验证每个 session
    for i, session in enumerate(template["sessions"]):
        if "nodes" not in session:
            issues.append(f"Session {i} 缺少 nodes")
            continue
        
        # 检查连接索引
        num_nodes = len(session["nodes"])
        for conn in session.get("connections", []):
            if len(conn) != 3:
                issues.append(f"Session {i} 连接格式错误: {conn}")
                continue
            
            src, tgt, inp = conn
            if src >= num_nodes or tgt >= num_nodes:
                issues.append(f"Session {i} 连接索引越界: {conn}")
    
    # 检查节点类型
    valid_types = ["Source", "RotoShape", "Paint", "Tracker", "Color",
                   "Filter", "Composite", "Matte", "Output"]
    for session in template["sessions"]:
        for node in session.get("nodes", []):
            if node["type"] not in valid_types:
                issues.append(f"未知节点类型: {node['type']}")
    
    return issues
```

## 8. 最佳实践

### 8.1 模板设计原则

1. **通用性**:模板应适用于多种场景
2. **可定制**:支持参数覆盖和扩展
3. **简洁性**:避免过度复杂
4. **文档化**:附带使用说明
5. **测试验证**:创建后进行测试

### 8.2 标准模板集合

```python
STANDARD_TEMPLATES = {
    "Roto_Basic": {
        "description": "基础 Roto 工作流",
        "nodes": ["Source", "RotoShape", "Output"],
        "use_case": "简单遮罩生成"
    },
    "Roto_Tracked": {
        "description": "跟踪驱动 Roto",
        "nodes": ["Source", "Tracker", "RotoShape", "Output"],
        "use_case": "运动物体 Roto"
    },
    "VFX_Standard": {
        "description": "标准 VFX 工作流",
        "nodes": ["Source", "Tracker", "RotoShape", "Color", "Composite", "Output"],
        "use_case": "常规 VFX 镜头"
    },
    "Export_MultiChannel": {
        "description": "多通道导出",
        "nodes": ["Source", "Composite", "Output"],
        "use_case": "多通道 EXR 输出"
    }
}
```

### 8.3 模板文档

```python
def generate_template_documentation(template):
    """生成模板文档"""
    doc = f"""# 模板: {template['template_name']}

## 描述
{template.get('description', '无描述')}

## 版本
{template.get('version', '1.0')}

## 项目设置
"""
    
    settings = template.get("project_settings", {})
    for key, value in settings.items():
        doc += f"- **{key}**: {value}\n"
    
    doc += "\n## 节点结构\n"
    for session in template.get("sessions", []):
        doc += f"\n### Session: {session.get('name', 'Unnamed')}\n"
        for node in session.get("nodes", []):
            doc += f"- {node['type']}: {node.get('label', '')}\n"
    
    return doc
```

### 8.4 团队协作

```
模板共享流程:
1. 艺术家创建/修改模板
2. 提交到共享模板库
3. 团队负责人审核
4. 审核通过后发布
5. 团队成员拉取更新
6. 定期 review 和优化
```

---

## 附录:模板速查表

| 模板名 | 任务 | 节点数 | 适用场景 |
|--------|------|--------|----------|
| Roto_Basic | Roto | 3 | 简单遮罩 |
| Roto_Tracked | Roto+跟踪 | 4 | 运动物体 |
| Roto_Hair | 头发Roto | 3 | 头发遮罩 |
| Paint_Cleanup | 修复 | 3 | 瑕疵去除 |
| VFX_Standard | VFX | 6 | 标准镜头 |
| VFX_GreenScreen | 抠像 | 5 | 绿幕镜头 |
| Export_Matte | 导出 | 3 | Matte输出 |
| Export_MultiChannel | 多通道 | 3 | EXR多通道 |

> **提示**:建议每个团队维护一套标准模板库,定期更新优化。新成员入职时,先学习模板库,快速上手标准工作流。

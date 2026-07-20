# Silhouette 预设配置系统

> 分类: 预设与配置
> 更新日期: 2026-07-11
> 概述: 预设 JSON 结构、参数覆盖、场景匹配、自动加载完整说明。

## 目录
1. [预设系统概述](#1-预设系统概述)
2. [JSON 结构](#2-json-结构)
3. [参数覆盖](#3-参数覆盖)
4. [场景匹配](#4-场景匹配)
5. [自动加载](#5-自动加载)
6. [预设管理](#6-预设管理)
7. [脚本化预设](#7-脚本化预设)
8. [最佳实践](#8-最佳实践)

---

## 1. 预设系统概述

### 1.1 什么是预设

预设(Preset)是保存的参数配置集合,可快速应用到节点或项目,实现配置复用。

### 1.2 预设的价值

| 价值 | 说明 |
|------|------|
| 效率 | 避免重复设置参数 |
| 一致性 | 确保相同效果使用相同参数 |
| 知识沉淀 | 将最佳实践固化为预设 |
| 团队协作 | 共享配置给团队成员 |
| 快速实验 | 一键切换不同效果 |

### 1.3 预设分类

| 类型 | 范围 | 示例 |
|------|------|------|
| 节点预设 | 单个节点参数 | Roto 羽化预设 |
| 效果预设 | 效果链配置 | 模糊+锐化组合 |
| 项目预设 | 整个项目配置 | VFX 标准项目 |
| 输出预设 | 输出格式配置 | EXR PIZ 输出 |
| 工作流预设 | 完整工作流 | Roto→跟踪→导出 |

## 2. JSON 结构

### 2.1 基础结构

```json
{
    "preset_name": "Roto_Hair_Standard",
    "preset_type": "node",
    "version": "1.0",
    "description": "头发 Roto 标准预设",
    "node_type": "RotoShape",
    "created": "2026-07-11",
    "author": "artist_name",
    "properties": {
        "feather": 2.0,
        "motionBlur": true,
        "motionBlurShutter": 0.5,
        "motionBlurSamples": 8
    }
}
```

### 2.2 完整结构

```json
{
    "preset_name": "VFX_Standard_Pipeline",
    "preset_type": "workflow",
    "version": "2.0",
    "description": "标准 VFX 工作流预设",
    "created": "2026-07-11",
    "author": "team_lead",
    "tags": ["vfx", "roto", "standard"],
    
    "project_settings": {
        "resolution": [1920, 1080],
        "frame_rate": 24,
        "colorspace": "acescg",
        "bit_depth": 16
    },
    
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
                "trackerType": "planar",
                "searchSize": 50,
                "trackMode": "feature"
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
        },
        {
            "type": "Output",
            "label": "OUT_Final",
            "properties": {
                "format": "exr",
                "compression": "piz",
                "bitDepth": 16,
                "colorspace": "acescg"
            }
        }
    ],
    
    "connections": [
        [0, 1, 0],
        [0, 2, 0],
        [2, 3, 0]
    ],
    
    "output_settings": {
        "naming": "[project]_[shot]_[version]_[####].[ext]",
        "path_template": "/output/{project}/{shot}/"
    }
}
```

### 2.3 预设元数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `preset_name` | string | 预设名称(唯一) |
| `preset_type` | string | 预设类型 |
| `version` | string | 版本号 |
| `description` | string | 描述 |
| `created` | string | 创建日期 |
| `author` | string | 作者 |
| `tags` | array | 标签(用于搜索) |

## 3. 参数覆盖

### 3.1 覆盖机制

```python
class PresetApplier:
    """预设应用器"""
    
    def apply_to_node(self, node, preset):
        """应用预设到节点"""
        if node.type != preset.get("node_type"):
            raise ValueError(f"节点类型不匹配: {node.type} vs {preset['node_type']}")
        
        for prop_name, prop_value in preset.get("properties", {}).items():
            prop = node.property(prop_name)
            if prop:
                prop.setValue(prop_value, 0)
                print(f"设置 {prop_name} = {prop_value}")
        
        return node
    
    def apply_with_overrides(self, node, preset, overrides=None):
        """应用预设并覆盖部分参数"""
        # 先应用基础预设
        self.apply_to_node(node, preset)
        
        # 应用覆盖
        if overrides:
            for prop_name, prop_value in overrides.items():
                prop = node.property(prop_name)
                if prop:
                    prop.setValue(prop_value, 0)
                    print(f"覆盖 {prop_name} = {prop_value}")
        
        return node
```

### 3.2 覆盖示例

```python
# 基础预设
base_preset = {
    "preset_name": "Roto_Base",
    "node_type": "RotoShape",
    "properties": {
        "feather": 1.0,
        "motionBlur": true,
        "motionBlurShutter": 0.5,
        "motionBlurSamples": 8
    }
}

# 覆盖参数
overrides = {
    "feather": 3.0,  # 增加羽化
    "motionBlurSamples": 16  # 提高采样
}

# 应用
applier = PresetApplier()
applier.apply_with_overrides(roto_node, base_preset, overrides)
```

### 3.3 条件覆盖

```python
def apply_conditional_preset(node, preset, conditions):
    """根据条件应用预设"""
    for prop_name, prop_value in preset.get("properties", {}).items():
        # 检查是否有条件
        if prop_name in conditions:
            condition = conditions[prop_name]
            if not condition(node, prop_value):
                continue  # 跳过不满足条件的
        
        prop = node.property(prop_name)
        if prop:
            prop.setValue(prop_value, 0)

# 使用:只在低分辨率时降低采样
conditions = {
    "motionBlurSamples": lambda node, val: 
        val if session.width >= 1920 else max(4, val // 2)
}
```

## 4. 场景匹配

### 4.1 场景识别

```python
class SceneMatcher:
    """场景匹配器"""
    
    def __init__(self):
        self.scene_profiles = {
            "dialogue": {
                "indicators": ["face", "person", "indoor"],
                "recommended_presets": ["roto_face", "cc_warm"]
            },
            "action": {
                "indicators": ["fast_motion", "outdoor", "multiple_subjects"],
                "recommended_presets": ["roto_motion_blur", "track_fast"]
            },
            "vfx_green_screen": {
                "indicators": ["green_background", "uniform_color"],
                "recommended_presets": ["key_green", "spill_removal"]
            },
            "landscape": {
                "indicators": ["wide_shot", "nature", "sky"],
                "recommended_presets": ["cc_landscape", "sky_replacement"]
            }
        }
    
    def match_scene(self, scene_features):
        """根据场景特征匹配预设"""
        matches = []
        
        for scene_type, profile in self.scene_profiles.items():
            score = sum(1 for indicator in profile["indicators"]
                       if indicator in scene_features)
            
            if score > 0:
                matches.append({
                    "scene_type": scene_type,
                    "score": score,
                    "presets": profile["recommended_presets"]
                })
        
        # 按分数排序
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches
```

### 4.2 自动场景检测

```python
def detect_scene_type(source_node):
    """自动检测场景类型"""
    features = []
    
    # 分析图像特征(概念性)
    # 检查是否有大面积绿色(绿幕)
    if has_large_green_area(source_node):
        features.append("green_background")
        features.append("uniform_color")
    
    # 检查运动
    if has_fast_motion(source_node):
        features.append("fast_motion")
    
    # 检查画面类型
    if is_wide_shot(source_node):
        features.append("wide_shot")
    
    return features

def recommend_presets_for_scene(source_node):
    """为场景推荐预设"""
    features = detect_scene_type(source_node)
    matcher = SceneMatcher()
    matches = matcher.match_scene(features)
    
    if matches:
        return matches[0]["presets"]  # 返回最佳匹配的预设
    return ["default_roto"]  # 默认预设
```

## 5. 自动加载

### 5.1 自动加载机制

```python
class AutoLoader:
    """预设自动加载器"""
    
    def __init__(self, preset_library):
        self.library = preset_library
        self.auto_load_rules = []
    
    def add_rule(self, condition, preset_name, target="node"):
        """添加自动加载规则"""
        self.auto_load_rules.append({
            "condition": condition,
            "preset_name": preset_name,
            "target": target
        })
    
    def check_and_load(self, node):
        """检查并自动加载预设"""
        for rule in self.auto_load_rules:
            if rule["condition"](node):
                preset = self.library.get_preset(rule["preset_name"])
                if preset:
                    if rule["target"] == "node":
                        PresetApplier().apply_to_node(node, preset)
                        print(f"自动加载预设: {rule['preset_name']}")
                        return True
        return False

# 使用
loader = AutoLoader(preset_library)

# 规则:RotoShape 节点自动加载标准预设
loader.add_rule(
    lambda node: node.type == "RotoShape",
    "Roto_Standard"
)

# 规则:Output 节点自动加载 EXR 预设
loader.add_rule(
    lambda node: node.type == "Output",
    "Output_EXR_PIZ"
)
```

### 5.2 基于项目类型的自动加载

```python
def auto_load_for_project_type(project_type):
    """根据项目类型自动加载预设"""
    project_presets = {
        "feature_film": {
            "colorspace": "acescg",
            "bit_depth": 16,
            "compression": "piz",
            "format": "exr"
        },
        "tv_series": {
            "colorspace": "rec709",
            "bit_depth": 10,
            "compression": "zip",
            "format": "dpx"
        },
        "web_series": {
            "colorspace": "srgb",
            "bit_depth": 8,
            "compression": "zip",
            "format": "png"
        },
        "commercial": {
            "colorspace": "rec709",
            "bit_depth": 12,
            "compression": "piz",
            "format": "exr"
        }
    }
    
    return project_presets.get(project_type, project_presets["tv_series"])
```

## 6. 预设管理

### 6.1 预设库

```python
import os
import json

class PresetLibrary:
    """预设库管理"""
    
    def __init__(self, library_path):
        self.library_path = library_path
        self.presets = {}
        self._load_all()
    
    def _load_all(self):
        """加载所有预设"""
        if not os.path.exists(self.library_path):
            os.makedirs(self.library_path)
            return
        
        for filename in os.listdir(self.library_path):
            if filename.endswith(".json"):
                filepath = os.path.join(self.library_path, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    preset = json.load(f)
                self.presets[preset["preset_name"]] = preset
    
    def get_preset(self, name):
        """获取预设"""
        return self.presets.get(name)
    
    def save_preset(self, preset):
        """保存预设"""
        name = preset["preset_name"]
        self.presets[name] = preset
        
        filepath = os.path.join(self.library_path, f"{name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
    
    def delete_preset(self, name):
        """删除预设"""
        if name in self.presets:
            del self.presets[name]
            filepath = os.path.join(self.library_path, f"{name}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def list_presets(self, preset_type=None, node_type=None):
        """列出预设"""
        results = []
        for preset in self.presets.values():
            if preset_type and preset.get("preset_type") != preset_type:
                continue
            if node_type and preset.get("node_type") != node_type:
                continue
            results.append(preset)
        return results
    
    def search_presets(self, query):
        """搜索预设"""
        query = query.lower()
        results = []
        
        for preset in self.presets.values():
            # 搜索名称、描述、标签
            searchable_text = " ".join([
                preset.get("preset_name", ""),
                preset.get("description", ""),
                " ".join(preset.get("tags", []))
            ]).lower()
            
            if query in searchable_text:
                results.append(preset)
        
        return results
```

### 6.2 预设导入导出

```python
class PresetIO:
    """预设导入导出"""
    
    @staticmethod
    def export_preset(preset, filepath):
        """导出预设到文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def import_preset(filepath):
        """从文件导入预设"""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @staticmethod
    def export_library(library, output_dir):
        """导出整个预设库"""
        os.makedirs(output_dir, exist_ok=True)
        for name, preset in library.presets.items():
            filepath = os.path.join(output_dir, f"{name}.json")
            PresetIO.export_preset(preset, filepath)
    
    @staticmethod
    def import_library(library, input_dir):
        """导入预设库"""
        for filename in os.listdir(input_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(input_dir, filename)
                preset = PresetIO.import_preset(filepath)
                library.save_preset(preset)
```

## 7. 脚本化预设

### 7.1 从节点创建预设

```python
def create_preset_from_node(node, preset_name, description=""):
    """从现有节点创建预设"""
    preset = {
        "preset_name": preset_name,
        "preset_type": "node",
        "version": "1.0",
        "description": description,
        "node_type": node.type,
        "created": "2026-07-11",
        "properties": {}
    }
    
    for prop_name in node.properties:
        prop = node.property(prop_name)
        if prop:
            preset["properties"][prop_name] = prop.value
    
    return preset

# 使用
roto = find_node_by_label(session, "ROTO_Template")
preset = create_preset_from_node(roto, "Roto_Template_v01", "标准 Roto 模板")
library.save_preset(preset)
```

### 7.2 批量应用预设

```python
def apply_preset_to_all(session, preset_name, node_type=None):
    """批量应用预设到所有匹配的节点"""
    preset = library.get_preset(preset_name)
    if not preset:
        print(f"预设不存在: {preset_name}")
        return 0
    
    applier = PresetApplier()
    count = 0
    
    for i in range(session.numNodes):
        node = session.node(i)
        if node_type and node.type != node_type:
            continue
        
        if node.type == preset.get("node_type"):
            applier.apply_to_node(node, preset)
            count += 1
    
    print(f"已应用预设到 {count} 个节点")
    return count
```

### 7.3 预设验证

```python
def validate_preset(preset):
    """验证预设有效性"""
    issues = []
    
    # 检查必要字段
    required_fields = ["preset_name", "preset_type", "version"]
    for field in required_fields:
        if field not in preset:
            issues.append(f"缺少必要字段: {field}")
    
    # 检查节点预设
    if preset.get("preset_type") == "node":
        if "node_type" not in preset:
            issues.append("节点预设缺少 node_type")
        if "properties" not in preset:
            issues.append("节点预设缺少 properties")
    
    # 检查工作流预设
    if preset.get("preset_type") == "workflow":
        if "nodes" not in preset:
            issues.append("工作流预设缺少 nodes")
        if "connections" not in preset:
            issues.append("工作流预设缺少 connections")
    
    return issues
```

## 8. 最佳实践

### 8.1 预设设计原则

1. **单一职责**:每个预设解决一类问题
2. **参数最小化**:只保存必要的参数
3. **命名清晰**:预设名称反映用途
4. **版本管理**:预设变更时更新版本号
5. **文档说明**:附带使用说明

### 8.2 命名规范

```
预设命名:[类型]_[对象]_[特性]_[版本]

示例:
  Roto_Hair_Feather_v01
  Color_Warm_Cinematic_v02
  Output_EXR_PIZ_v01
  Workflow_VFX_Standard_v03
```

### 8.3 预设组织

```
/presets/
  /roto/
    Roto_Base.json
    Roto_Hair.json
    Roto_Face.json
  /color/
    Color_Warm.json
    Color_Cool.json
    Color_DayToNight.json
  /output/
    Output_EXR_PIZ.json
    Output_PNG.json
    Output_ProRes.json
  /workflow/
    Workflow_VFX.json
    Workflow_Cleanup.json
```

### 8.4 团队共享

```python
def sync_presets_with_team(local_path, shared_path):
    """与团队同步预设"""
    import shutil
    
    # 从共享路径拉取最新预设
    if os.path.exists(shared_path):
        for filename in os.listdir(shared_path):
            if filename.endswith(".json"):
                src = os.path.join(shared_path, filename)
                dst = os.path.join(local_path, filename)
                shutil.copy2(src, dst)
    
    # 推送本地新预设到共享路径
    if os.path.exists(local_path):
        for filename in os.listdir(local_path):
            if filename.endswith(".json"):
                src = os.path.join(local_path, filename)
                dst = os.path.join(shared_path, filename)
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
```

---

## 附录:预设类型速查

| 预设类型 | 适用场景 | 包含内容 |
|----------|----------|----------|
| node | 单节点配置 | 节点类型+属性 |
| effect | 效果链 | 多节点+连接 |
| project | 项目配置 | 设置+节点图 |
| output | 输出配置 | 格式+压缩+命名 |
| workflow | 完整工作流 | 全流程配置 |

> **提示**:建立预设库时,先从最常用的配置开始,逐步积累。定期 review 预设库,淘汰过时预设,保持精简有效。

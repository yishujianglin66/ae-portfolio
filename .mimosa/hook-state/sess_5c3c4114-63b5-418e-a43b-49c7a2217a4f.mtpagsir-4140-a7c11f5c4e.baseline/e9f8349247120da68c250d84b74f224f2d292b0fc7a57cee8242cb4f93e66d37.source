#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AE扩展脚本深度集成工具

整合AE-Knowledge-Vault知识库与MCP Bridge的Python接口，
提供效果matchName查询、脚本模板生成、MCP工具调用等功能。

Author: AE-Knowledge-Vault
Date: 2026-07-14
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Union


@dataclass
class EffectMapping:
    """效果映射数据结构"""
    match_name: str
    display_name: str
    category: str
    properties: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class MCPToolSchema:
    """MCP工具Schema"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None


class AEKnowledgeIntegrator:
    """AE扩展脚本知识检索与集成接口"""

    def __init__(self, vault_path: str = "."):
        self.vault_path = Path(vault_path)
        self.kb_path = self.vault_path / "10-风格化剪辑知识库"
        self.scripts_path = self.vault_path / "AE-Scripts"

        # 效果matchName缓存
        self._effect_cache: Dict[str, EffectMapping] = {}

        # MCP工具缓存
        self._mcp_tools: Dict[str, MCPToolSchema] = {}

        # 加载数据
        self._load_effect_mappings()
        self._load_mcp_schemas()

    def _load_effect_mappings(self) -> None:
        """加载效果映射数据"""
        # 核心效果matchName映射
        effects_data = {
            "Glow": EffectMapping(
                match_name="ADBE Glo2",
                display_name="Glow",
                category="Stylize",
                properties={
                    "Glow Threshold": {"index": 1, "type": "float", "range": [0, 100]},
                    "Glow Radius": {"index": 2, "type": "float", "range": [0, 500]},
                    "Color A": {"index": 3, "type": "color", "default": [1, 0.8, 0]},
                    "Color B": {"index": 4, "type": "color", "default": [0, 0, 0]},
                    "Glow Intensity": {"index": 5, "type": "float", "range": [0, 10]}
                }
            ),
            "Gaussian Blur": EffectMapping(
                match_name="ADBE Gaussian Blur",
                display_name="Gaussian Blur",
                category="Blur & Sharpen",
                properties={
                    "Blurriness": {"index": 1, "type": "float", "range": [0, 1000]}
                }
            ),
            "Hue/Saturation": EffectMapping(
                match_name="ADBE HUE SATURATION",
                display_name="Hue/Saturation",
                category="Color Correction",
                properties={
                    "Channel Control": {"index": 1, "type": "int", "range": [1, 6]},
                    "Channel Range": {"index": 2, "type": "array"},
                    "Master Hue": {"index": 3, "type": "float", "range": [-180, 180]},
                    "Master Saturation": {"index": 4, "type": "float", "range": [-100, 100]},
                    "Master Lightness": {"index": 5, "type": "float", "range": [-100, 100]}
                }
            ),
            "Levels": EffectMapping(
                match_name="ADBE Easy Levels2",
                display_name="Levels",
                category="Color Correction",
                properties={
                    "Input Black": {"index": 1, "type": "float", "range": [0, 255]},
                    "Input White": {"index": 2, "type": "float", "range": [0, 255]},
                    "Gamma": {"index": 3, "type": "float", "range": [0.01, 10]},
                    "Output Black": {"index": 4, "type": "float", "range": [0, 255]},
                    "Output White": {"index": 5, "type": "float", "range": [0, 255]},
                    "Input Black 2": {"index": 6, "type": "float", "range": [0, 255]}
                }
            ),
            "Drop Shadow": EffectMapping(
                match_name="ADBE Drop Shadow",
                display_name="Drop Shadow",
                category="Perspective",
                properties={
                    "Shadow Color": {"index": 1, "type": "color", "default": [0, 0, 0, 1]},
                    "Opacity": {"index": 2, "type": "float", "range": [0, 100]},
                    "Direction": {"index": 3, "type": "float", "range": [0, 360]},
                    "Distance": {"index": 4, "type": "float", "range": [0, 1000]},
                    "Softness": {"index": 5, "type": "float", "range": [0, 100]},
                    "Shadow Only": {"index": 6, "type": "boolean", "default": False}
                }
            ),
            "Fill": EffectMapping(
                match_name="ADBE Fill",
                display_name="Fill",
                category="Generate",
                properties={
                    "Color": {"index": 1, "type": "color", "default": [1, 1, 1, 1]},
                    "Opacity": {"index": 2, "type": "float", "range": [0, 100]}
                }
            ),
            "Fast Blur": EffectMapping(
                match_name="ADBE Camera Lens Blur",
                display_name="Camera Lens Blur",
                category="Blur & Sharpen",
                properties={
                    "Blur Radius": {"index": 1, "type": "float", "range": [0, 500]},
                    "Highlight Gain": {"index": 2, "type": "float", "range": [0, 100]},
                    "Highlight Threshold": {"index": 3, "type": "float", "range": [0, 255]},
                    "Use GPU": {"index": 4, "type": "boolean", "default": True}
                }
            ),
            "Noise": EffectMapping(
                match_name="ADBE Noise",
                display_name="Noise",
                category="Stylize",
                properties={
                    "Amount of Noise": {"index": 1, "type": "float", "range": [0, 100]},
                    "Noise Type": {"index": 2, "type": "int", "range": [1, 2]},
                    "Clipping": {"index": 3, "type": "boolean", "default": False}
                }
            ),
            "Curves": EffectMapping(
                match_name="ADBE CurvesCustom",
                display_name="Curves",
                category="Color Correction",
                properties={
                    "Channel": {"index": 1, "type": "int", "range": [1, 5]},
                    "Curve Data": {"index": 2, "type": "curve"}
                }
            ),
            "Motion Blur": EffectMapping(
                match_name="ADBE Motion Blur",
                display_name="Motion Blur",
                category="Obsolete",
                properties={}
            )
        }

        self._effect_cache = effects_data

    def _load_mcp_schemas(self) -> None:
        """加载MCP工具Schema"""
        # 22个MCP工具定义
        mcp_tools_data = {
            "create-composition": MCPToolSchema(
                name="create-composition",
                description="创建新合成",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "default": "Comp 1"},
                        "width": {"type": "number", "default": 1920},
                        "height": {"type": "number", "default": 1080},
                        "frameRate": {"type": "number", "default": 30},
                        "duration": {"type": "number", "default": 10},
                        "bgColor": {"type": "array", "items": {"type": "number"}, "default": [0, 0, 0]}
                    },
                    "required": []
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "compName": {"type": "string"},
                        "compId": {"type": "number"},
                        "duration": {"type": "number"},
                        "frameRate": {"type": "number"}
                    }
                }
            ),
            "create-text-layer": MCPToolSchema(
                name="create-text-layer",
                description="创建文字图层",
                input_schema={
                    "type": "object",
                    "properties": {
                        "compName": {"type": "string"},
                        "layerName": {"type": "string", "default": "Text"},
                        "text": {"type": "string", "default": "Sample Text"},
                        "fontSize": {"type": "number", "default": 72},
                        "position": {"type": "array", "items": {"type": "number"}, "default": [960, 540]}
                    },
                    "required": ["compName"]
                }
            ),
            "setLayerKeyframe": MCPToolSchema(
                name="setLayerKeyframe",
                description="设置图层关键帧",
                input_schema={
                    "type": "object",
                    "properties": {
                        "layerName": {"type": "string"},
                        "propertyPath": {"type": "string"},
                        "time": {"type": "number"},
                        "value": {"type": "array", "items": {"type": "number"}},
                        "easing": {"type": "string", "enum": ["linear", "easeIn", "easeOut", "easeInOut"]}
                    },
                    "required": ["layerName", "propertyPath", "time", "value"]
                }
            ),
            "add_effect": MCPToolSchema(
                name="add_effect",
                description="添加效果到图层",
                input_schema={
                    "type": "object",
                    "properties": {
                        "layerName": {"type": "string"},
                        "effectMatchName": {"type": "string"},
                        "properties": {"type": "object"}
                    },
                    "required": ["layerName", "effectMatchName"]
                }
            ),
            "set_effect_property": MCPToolSchema(
                name="set_effect_property",
                description="设置效果属性",
                input_schema={
                    "type": "object",
                    "properties": {
                        "layerName": {"type": "string"},
                        "effectIndex": {"type": "number"},
                        "propertyName": {"type": "string"},
                        "value": {}
                    },
                    "required": ["layerName", "effectIndex", "propertyName", "value"]
                }
            ),
            "beatedit_analyze": MCPToolSchema(
                name="beatedit_analyze",
                description="分析音频节拍",
                input_schema={
                    "type": "object",
                    "properties": {
                        "audioLayerName": {"type": "string"},
                        "sensitivity": {"type": "number", "default": 0.8},
                        "minBpm": {"type": "number", "default": 60},
                        "maxBpm": {"type": "number", "default": 180}
                    },
                    "required": ["audioLayerName"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "beats": {"type": "array", "items": {"type": "number"}},
                        "bpm": {"type": "number"},
                        "timeSignature": {"type": "string"}
                    }
                }
            )
        }

        self._mcp_tools = mcp_tools_data

    def search_effect_matchname(self, effect_name: str) -> Optional[EffectMapping]:
        """
        搜索效果的matchName

        Args:
            effect_name: 效果名称（如 "Glow"、"Gaussian Blur"）

        Returns:
            EffectMapping对象，如果未找到返回None
        """
        # 精确匹配
        if effect_name in self._effect_cache:
            return self._effect_cache[effect_name]

        # 模糊匹配
        effect_lower = effect_name.lower()
        for name, mapping in self._effect_cache.items():
            if effect_lower in name.lower() or name.lower() in effect_lower:
                return mapping

        return None

    def get_mcp_tool_schema(self, tool_name: str) -> Optional[MCPToolSchema]:
        """
        获取MCP工具Schema

        Args:
            tool_name: MCP工具名称

        Returns:
            MCPToolSchema对象，如果未找到返回None
        """
        return self._mcp_tools.get(tool_name)

    def generate_jsx_script(self, operation: str, params: Dict[str, Any]) -> str:
        """
        生成ExtendScript脚本

        Args:
            operation: 操作类型（如 "add_effect", "set_keyframe"）
            params: 参数字典

        Returns:
            ES3兼容的ExtendScript代码
        """
        if operation == "add_effect":
            return self._generate_add_effect_script(params)
        elif operation == "set_keyframe":
            return self._generate_set_keyframe_script(params)
        elif operation == "create_comp":
            return self._generate_create_comp_script(params)
        elif operation == "create_text_layer":
            return self._generate_create_text_layer_script(params)
        else:
            return f"// Unknown operation: {operation}"

    def _generate_add_effect_script(self, params: Dict[str, Any]) -> str:
        """生成添加效果脚本"""
        layer_name = params.get("layerName", "Layer 1")
        effect_match_name = params.get("effectMatchName", "ADBE Glo2")
        properties = params.get("properties", {})

        script = '''// Add Effect Script - ES3 Compatible
(function() {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        alert("Please open a composition first");
        return;
    }

    var layer = null;
    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).name === "''' + layer_name + '''") {
            layer = comp.layer(i);
            break;
        }
    }

    if (!layer) {
        alert("Layer not found: ''' + layer_name + '''");
        return;
    }

    app.beginUndoGroup("Add Effect");

    var effect = layer.Effects.addProperty("''' + effect_match_name + '''");
'''

        # 添加属性设置
        for prop_name, value in properties.items():
            if isinstance(value, list):
                value_str = "[" + ", ".join(str(v) for v in value) + "]"
            elif isinstance(value, str):
                value_str = f'"{value}"'
            else:
                value_str = str(value)

            script += f'    effect.property("{prop_name}").setValue({value_str});\n'

        script += '''
    app.endUndoGroup();
})();
'''
        return script

    def _generate_set_keyframe_script(self, params: Dict[str, Any]) -> str:
        """生成设置关键帧脚本"""
        layer_name = params.get("layerName", "Layer 1")
        property_path = params.get("propertyPath", "Transform/Position")
        time_sec = params.get("time", 0)
        value = params.get("value", [960, 540])
        easing = params.get("easing", "linear")

        value_str = "[" + ", ".join(str(v) for v in value) + "]" if isinstance(value, list) else str(value)

        script = f'''// Set Keyframe Script - ES3 Compatible
(function() {{
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {{
        alert("Please open a composition first");
        return;
    }}

    var layer = null;
    for (var i = 1; i <= comp.numLayers; i++) {{
        if (comp.layer(i).name === "{layer_name}") {{
            layer = comp.layer(i);
            break;
        }}
    }}

    if (!layer) {{
        alert("Layer not found: {layer_name}");
        return;
    }}

    app.beginUndoGroup("Set Keyframe");

    // Parse property path
    var pathParts = "{property_path}".split("/");
    var prop = layer;

    for (var i = 0; i < pathParts.length; i++) {{
        prop = prop.property(pathParts[i]);
        if (!prop) {{
            alert("Property not found: " + pathParts[i]);
            app.endUndoGroup();
            return;
        }}
    }}

    // Set keyframe
    prop.setValueAtTime({time_sec}, {value_str});

    // Apply easing
    var easingType = "{easing}";
    var easeIn, easeOut;

    if (easingType === "linear") {{
        easeIn = new KeyframeEase(0, 33);
        easeOut = new KeyframeEase(0, 33);
    }} else if (easingType === "easeIn") {{
        easeIn = new KeyframeEase(0.5, 33);
        easeOut = new KeyframeEase(0, 33);
    }} else if (easingType === "easeOut") {{
        easeIn = new KeyframeEase(0, 33);
        easeOut = new KeyframeEase(0.5, 33);
    }} else if (easingType === "easeInOut") {{
        easeIn = new KeyframeEase(0.5, 33);
        easeOut = new KeyframeEase(0.5, 33);
    }}

    var keyIndex = prop.nearestKeyIndex({time_sec});
    var numKeys = prop.numKeys;
    var keyTime = prop.keyTime(keyIndex);

    if (Math.abs(keyTime - {time_sec}) < 0.001) {{
        var dim = 2;  // Default for Position
        var inEases = [];
        var outEases = [];
        for (var d = 0; d < dim; d++) {{
            inEases.push(easeIn);
            outEases.push(easeOut);
        }}
        prop.setTemporalEaseAtKey(keyIndex, inEases, outEases);
    }}

    app.endUndoGroup();
}})();
'''
        return script

    def _generate_create_comp_script(self, params: Dict[str, Any]) -> str:
        """生成创建合成脚本"""
        name = params.get("name", "Comp 1")
        width = params.get("width", 1920)
        height = params.get("height", 1080)
        frame_rate = params.get("frameRate", 30)
        duration = params.get("duration", 10)

        script = f'''// Create Composition Script - ES3 Compatible
(function() {{
    app.beginUndoGroup("Create Composition");

    var comp = app.project.items.addComp(
        "{name}",
        {width},
        {height},
        1,
        {frame_rate},
        {duration}
    );

    comp.openInViewer();

    app.endUndoGroup();

    return {{
        compName: comp.name,
        compId: comp.id,
        duration: comp.duration,
        frameRate: comp.frameRate
    }};
}})();
'''
        return script

    def _generate_create_text_layer_script(self, params: Dict[str, Any]) -> str:
        """生成创建文字图层脚本"""
        comp_name = params.get("compName", "Comp 1")
        layer_name = params.get("layerName", "Text")
        text = params.get("text", "Sample Text")
        font_size = params.get("fontSize", 72)
        position = params.get("position", [960, 540])

        pos_str = "[" + ", ".join(str(p) for p in position) + "]"

        script = f'''// Create Text Layer Script - ES3 Compatible
(function() {{
    var comp = null;

    // Find composition
    for (var i = 1; i <= app.project.numItems; i++) {{
        if (app.project.item(i).name === "{comp_name}" && app.project.item(i) instanceof CompItem) {{
            comp = app.project.item(i);
            break;
        }}
    }}

    if (!comp) {{
        alert("Composition not found: {comp_name}");
        return;
    }}

    app.beginUndoGroup("Create Text Layer");

    var textLayer = comp.layers.addText("{text}");
    textLayer.name = "{layer_name}";

    var textProp = textLayer.property("Source Text");
    var textDoc = textProp.value;

    textDoc.fontSize = {font_size};
    textProp.setValue(textDoc);

    textLayer.property("Transform").property("Position").setValue({pos_str});

    app.endUndoGroup();

    return {{
        layerName: textLayer.name,
        index: textLayer.index
    }};
}})();
'''
        return script

    def list_available_scripts(self) -> List[str]:
        """列出所有可用的ScriptUI脚本"""
        scripts_dir = self.scripts_path / "ScriptUI Panels"
        if not scripts_dir.exists():
            return []

        scripts = []
        for jsx_file in scripts_dir.glob("*.jsx"):
            scripts.append(jsx_file.name)

        return sorted(scripts)

    def get_script_metadata(self, script_name: str) -> Dict[str, Any]:
        """获取脚本元数据"""
        script_path = self.scripts_path / "ScriptUI Panels" / script_name
        if not script_path.exists():
            return {}

        metadata = {
            "name": script_name,
            "path": str(script_path),
            "size": script_path.stat().st_size,
            "modified": script_path.stat().st_mtime
        }

        # 尝试读取文件头部注释
        try:
            with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(2000)
                # 提取注释中的描述
                desc_match = re.search(r"//\s*Description:\s*(.+)", content)
                if desc_match:
                    metadata["description"] = desc_match.group(1).strip()
        except Exception:
            pass

        return metadata


def main():
    """测试入口"""
    integrator = AEKnowledgeIntegrator()

    # 测试效果查询
    print("=== Effect Search Test ===")
    glow = integrator.search_effect_matchname("Glow")
    if glow:
        print(f"Found: {glow.display_name} -> {glow.match_name}")
        print(f"Properties: {list(glow.properties.keys())}")

    # 测试脚本生成
    print("\n=== Script Generation Test ===")
    script = integrator.generate_jsx_script("add_effect", {
        "layerName": "Layer 1",
        "effectMatchName": "ADBE Glo2",
        "properties": {
            "Glow Threshold": 50,
            "Glow Radius": 20
        }
    })
    print(script[:500] + "...")

    # 测试脚本列表
    print("\n=== Available Scripts ===")
    scripts = integrator.list_available_scripts()
    print(f"Found {len(scripts)} scripts")
    print(", ".join(scripts[:10]))

    # 测试MCP Schema
    print("\n=== MCP Tool Schema ===")
    schema = integrator.get_mcp_tool_schema("create-composition")
    if schema:
        print(f"Tool: {schema.name}")
        print(f"Description: {schema.description}")


if __name__ == "__main__":
    main()
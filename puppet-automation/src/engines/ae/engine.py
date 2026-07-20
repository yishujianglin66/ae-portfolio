"""After Effects engine - aerender CLI + ExtendScript execution."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


class AEEngine(BaseEngine):
    """Adobe After Effects engine via aerender CLI."""

    name = "after_effects"

    def __init__(self, executable_path: Optional[Path | str] = None):
        path = Path(executable_path) if executable_path else settings.aerender_path
        super().__init__(path)

    async def render_comp(
        self,
        project_path: Path | str,
        comp_name: str,
        output_path: Path | str,
        output_module: str = "H.264",
        render_settings: str = "Best Settings",
        multiprocess: Optional[int] = None,
        multi_machine: Optional[int] = None,
    ) -> EngineResult:
        """Render AE composition via aerender CLI.

        Args:
            project_path: Path to the .aep project file
            comp_name: Composition name to render
            output_path: Output file path
            output_module: Output module template (H.264, Lossless, etc.)
            render_settings: Render settings template (Best Settings, etc.)
            multiprocess: 多进程渲染进程数（同一台机器上使用多个进程并行渲染）。
                对应 aerender 的 -mp 参数（multiprocess rendering）。
            multi_machine: 多机渲染标识（跨多台机器分布式渲染）。
                对应 aerender 的 -PdM 参数。注意：AE 的多机渲染通常通过
                Watch Folder 模式实现，-PdM 标志的可用性取决于 AE 版本，
                如不支持可改用 Watch Folder 工作流。
        """
        project_path = Path(project_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.executable_path),
            "-project", str(project_path),
            "-comp", comp_name,
            "-output", str(output_path),
            "-OMtemplate", output_module,
            "-RStemplate", render_settings,
        ]
        # -mp：多进程渲染（单机多进程并行处理）
        if multiprocess:
            cmd.extend(["-mp", str(multiprocess)])
        # -PdM：多机渲染（跨机器分布式渲染，依赖 AE 版本支持）
        if multi_machine:
            cmd.extend(["-PdM", str(multi_machine)])

        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            metadata={
                "comp_name": comp_name,
                "output_module": output_module,
                "render_settings": render_settings,
            },
            error=stderr if code != 0 else None,
        )

    async def run_script(
        self,
        script_content: str,
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """Execute ExtendScript via aerender -s."""
        cmd = [str(self.executable_path)]
        if project_path:
            cmd.extend(["-project", str(project_path)])
        cmd.extend(["-s", script_content])

        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=3600
        )
        return EngineResult(
            success=code == 0,
            metadata={"stdout": stdout[:2000]},
            error=stderr if code != 0 else None,
        )

    # ==================== 高层操作 API ====================

    async def create_comp(
        self,
        name: str,
        width: int,
        height: int,
        fps: float,
        duration: float,
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """创建合成。

        Args:
            name: 合成名称
            width: 宽度（像素）
            height: 高度（像素）
            fps: 帧率
            duration: 时长（秒）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 compName
        """
        script = f'''
(function() {{
    var comp = app.project.items.addComp("{name}", {width}, {height}, 1, {duration}, {fps});
    return JSON.stringify({{
        success: true,
        compName: comp.name,
        width: comp.width,
        height: comp.height,
        duration: comp.duration,
        fps: comp.frameRate
    }});
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                result.metadata.update(data)
            except Exception:
                pass
        return result

    async def import_footage(
        self,
        footage_path: Path | str,
        comp_name: Optional[str] = None,
        as_sequence: bool = False,
        position: Optional[int] = None,
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """导入素材到项目，可选添加到合成。

        Args:
            footage_path: 素材文件路径
            comp_name: 目标合成名称（可选）
            as_sequence: 是否作为序列导入
            position: 在合成中的图层位置（1-based，可选）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 footageName, layerIndex
        """
        footage_path = Path(footage_path)
        if not footage_path.exists():
            return EngineResult(
                success=False,
                error=f"素材文件不存在: {footage_path}",
            )

        # 构建 JSON 参数（复用 MCP importFootage.jsx 逻辑）
        args = {
            "filePath": str(footage_path),
            "asSequence": as_sequence,
        }
        if comp_name:
            args["compName"] = comp_name
        if position is not None:
            args["position"] = position

        args_json = json.dumps(args, ensure_ascii=False)
        script = f'''
(function() {{
    var args = {args_json};
    try {{
        var file = new File(args.filePath);
        if (!file.exists) {{
            return JSON.stringify({{error: true, message: "文件不存在: " + args.filePath}});
        }}

        app.beginUndoGroup("Import Footage");
        var importOptions = new ImportOptions(file);
        importOptions.sequence = args.asSequence || false;
        var footage = app.project.importFile(importOptions);

        var result = {{
            success: true,
            footageName: footage.name,
            filePath: args.filePath
        }};

        if (args.compName) {{
            var comp = null;
            for (var i = 1; i <= app.project.numItems; i++) {{
                var item = app.project.item(i);
                if (item instanceof CompItem && item.name === args.compName) {{
                    comp = item;
                    break;
                }}
            }}
            if (comp) {{
                var addedLayer = comp.layers.add(footage);
                if (args.position && args.position > 0 && args.position <= comp.numLayers) {{
                    addedLayer.moveAfter(comp.layer(args.position));
                }}
                result.compName = args.compName;
                result.layerIndex = addedLayer.index;
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify(result);
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "导入失败")
                else:
                    result.metadata.update(data)
            except Exception:
                pass
        return result

    async def add_layer(
        self,
        comp_name: str,
        layer_type: str,
        name: str,
        position: Optional[int] = None,
        project_path: Optional[Path | str] = None,
        **kwargs: Any,
    ) -> EngineResult:
        """在合成中添加图层。

        Args:
            comp_name: 合成名称
            layer_type: 图层类型（solid, null, adjustment, text, shape）
            name: 图层名称
            position: 插入位置（1-based，可选）
            project_path: 项目路径（可选）
            **kwargs: 其他参数（如 color, width, height 等）

        Returns:
            EngineResult: 成功时 metadata 包含 layerIndex
        """
        layer_type = layer_type.lower()
        args = {
            "compName": comp_name,
            "layerType": layer_type,
            "name": name,
            "position": position,
            **kwargs,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到: " + args.compName}});
        }}

        app.beginUndoGroup("Add Layer");

        var layer = null;
        var layerType = args.layerType.toLowerCase();

        if (layerType === "solid") {{
            var color = args.color || [1, 1, 1];
            var width = args.width || comp.width;
            var height = args.height || comp.height;
            layer = comp.layers.addSolid(color, args.name, width, height, 1, comp.duration);
        }} else if (layerType === "null") {{
            layer = comp.layers.addNull(comp.duration);
            layer.name = args.name;
        }} else if (layerType === "adjustment") {{
            layer = comp.layers.addSolid([0, 0, 0], args.name, comp.width, comp.height, 1, comp.duration);
            layer.adjustmentLayer = true;
        }} else if (layerType === "text") {{
            layer = comp.layers.addText(args.name);
        }} else if (layerType === "shape") {{
            layer = comp.layers.addShape();
            layer.name = args.name;
        }} else {{
            app.endUndoGroup();
            return JSON.stringify({{error: true, message: "不支持的图层类型: " + layerType}});
        }}

        // 设置图层顺序（遵循 project_memory：moveToBeginning + moveAfter）
        if (args.position !== null && args.position !== undefined) {{
            var pos = parseInt(args.position);
            if (pos > 0 && pos <= comp.numLayers) {{
                layer.moveAfter(comp.layer(pos));
            }} else if (pos <= 0) {{
                layer.moveToBeginning();
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify({{
            success: true,
            layerIndex: layer.index,
            layerName: layer.name,
            layerType: layerType
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "添加图层失败")
                else:
                    result.metadata.update(data)
            except Exception:
                pass
        return result

    async def add_effect(
        self,
        comp_name: str,
        layer_index: int,
        effect_name: str,
        params: Optional[Dict[str, Any]] = None,
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """为图层添加效果。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            effect_name: 效果匹配名（如 "ADBE Gaussian Blur"）
            params: 效果参数字典（可选）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 effectIndex, effectName
        """
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "effectMatchName": effect_name,
            "settings": params or {},
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        app.beginUndoGroup("Add Effect");

        var layer = comp.layer(args.layerIndex);
        var effect = layer.Effects.addProperty(args.effectMatchName);

        // 应用参数
        if (args.settings) {{
            for (var key in args.settings) {{
                try {{
                    var prop = effect.property(key);
                    if (prop && prop.canSetValue) {{
                        prop.setValue(args.settings[key]);
                    }}
                }} catch (e) {{}}
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify({{
            success: true,
            effectIndex: effect.propertyIndex,
            effectName: effect.name
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "添加效果失败")
                else:
                    result.metadata.update(data)
            except Exception:
                pass
        return result

    async def set_keyframes(
        self,
        comp_name: str,
        layer_index: int,
        property_path: str,
        keyframes: List[Dict[str, Any]],
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """设置属性关键帧。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            property_path: 属性路径（如 "Transform/Position" 或 "Effects(1)/Blur"）
            keyframes: 关键帧列表，每项包含 time, value, easingType
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 keyframesAdded
        """
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "propertyPath": property_path,
            "keyframes": keyframes,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        app.beginUndoGroup("Set Keyframes");

        var layer = comp.layer(args.layerIndex);
        var prop = null;

        // 解析属性路径（简化版：仅支持 Transform/Prop 和 Effects(index)/Prop）
        var pathParts = args.propertyPath.split("/");
        if (pathParts[0] === "Transform") {{
            prop = layer.property(pathParts[1]);
        }} else if (pathParts[0].startsWith("Effects")) {{
            var match = pathParts[0].match(/Effects\\((\\d+)\\)/);
            if (match) {{
                var effectIndex = parseInt(match[1]);
                prop = layer.effect(effectIndex).property(pathParts[1]);
            }}
        }}

        if (!prop || !prop.canSetValue) {{
            app.endUndoGroup();
            return JSON.stringify({{error: true, message: "属性无效或不可设置"}});
        }}

        var keyframesAdded = 0;
        for (var k = 0; k < args.keyframes.length; k++) {{
            var kf = args.keyframes[k];
            try {{
                prop.setValueAtTime(kf.time, kf.value);

                // 缓动设置
                if (kf.easingType && kf.easingType !== "linear") {{
                    var kfIndex = prop.nearestKeyIndex(kf.time);
                    var inType = KeyframeInterpolationType.BEZIER;
                    var outType = KeyframeInterpolationType.BEZIER;
                    if (kf.easingType === "hold") {{
                        inType = KeyframeInterpolationType.HOLD;
                        outType = KeyframeInterpolationType.HOLD;
                    }} else if (kf.easingType === "easeIn") {{
                        outType = KeyframeInterpolationType.LINEAR;
                    }} else if (kf.easingType === "easeOut") {{
                        inType = KeyframeInterpolationType.LINEAR;
                    }}
                    prop.setInterpolationTypeAtKey(kfIndex, inType, outType);
                }}
                keyframesAdded++;
            }} catch (e) {{}}
        }}

        app.endUndoGroup();
        return JSON.stringify({{
            success: true,
            keyframesAdded: keyframesAdded
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "设置关键帧失败")
                else:
                    result.metadata.update(data)
            except Exception:
                pass
        return result

    async def apply_preset(
        self,
        comp_name: str,
        layer_index: int,
        preset_path: Path | str,
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """应用效果预设。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            preset_path: 预设文件路径（.ffx）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 操作结果
        """
        preset_path = Path(preset_path)
        if not preset_path.exists():
            return EngineResult(
                success=False,
                error=f"预设文件不存在: {preset_path}",
            )

        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "presetPath": str(preset_path),
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        app.beginUndoGroup("Apply Preset");

        var layer = comp.layer(args.layerIndex);
        var presetFile = new File(args.presetPath);
        if (!presetFile.exists) {{
            app.endUndoGroup();
            return JSON.stringify({{error: true, message: "预设文件不存在"}});
        }}

        layer.applyPreset(presetFile);

        app.endUndoGroup();
        return JSON.stringify({{success: true}});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "应用预设失败")
            except Exception:
                pass
        return result

    async def set_blend_mode(
        self,
        comp_name: str,
        layer_index: int,
        mode: str,
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """设置图层混合模式。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            mode: 混合模式（NONE, SCREEN, MULTIPLY, ADD, OVERLAY 等）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 操作结果
        """
        mode = mode.upper()
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "blendMode": mode,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        var blendModeMap = {{
            "NONE": BlendingMode.NONE,
            "DISSOLVE": BlendingMode.DISSOLVE,
            "MULTIPLY": BlendingMode.MULTIPLY,
            "SCREEN": BlendingMode.SCREEN,
            "OVERLAY": BlendingMode.OVERLAY,
            "SOFT_LIGHT": BlendingMode.SOFT_LIGHT,
            "HARD_LIGHT": BlendingMode.HARD_LIGHT,
            "ADD": BlendingMode.ADD,
            "COLOR_DODGE": BlendingMode.COLOR_DODGE,
            "COLOR_BURN": BlendingMode.COLOR_BURN,
            "DARKEN": BlendingMode.DARKEN,
            "LIGHTEN": BlendingMode.LIGHTEN,
            "DIFFERENCE": BlendingMode.DIFFERENCE,
            "EXCLUSION": BlendingMode.EXCLUSION,
            "HUE": BlendingMode.HUE,
            "SATURATION": BlendingMode.SATURATION,
            "COLOR": BlendingMode.COLOR,
            "LUMINOSITY": BlendingMode.LUMINOSITY
        }};

        if (!blendModeMap.hasOwnProperty(args.blendMode)) {{
            return JSON.stringify({{error: true, message: "不支持的混合模式: " + args.blendMode}});
        }}

        app.beginUndoGroup("Set Blend Mode");
        var layer = comp.layer(args.layerIndex);
        layer.blendingMode = blendModeMap[args.blendMode];
        app.endUndoGroup();

        return JSON.stringify({{success: true, blendMode: args.blendMode}});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "设置混合模式失败")
                else:
                    result.metadata.update(data)
            except Exception:
                pass
        return result

    async def set_track_matte(
        self,
        comp_name: str,
        layer_index: int,
        matte_type: str,
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """设置轨道遮罩类型。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            matte_type: 遮罩类型（NO_TRACK_MATTE, ALPHA_TRACK_MATTE, LUMA_TRACK_MATTE 等）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 操作结果
        """
        matte_type = matte_type.upper()
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "matteType": matte_type,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        var matteMap = {{
            "NO_TRACK_MATTE": TrackMatteType.NO_TRACK_MATTE,
            "ALPHA_TRACK_MATTE": TrackMatteType.ALPHA_TRACK_MATTE,
            "ALPHA_INVERTED_TRACK_MATTE": TrackMatteType.ALPHA_INVERTED_TRACK_MATTE,
            "LUMA_TRACK_MATTE": TrackMatteType.LUMA_TRACK_MATTE,
            "LUMA_INVERTED_TRACK_MATTE": TrackMatteType.LUMA_INVERTED_TRACK_MATTE
        }};

        if (!matteMap.hasOwnProperty(args.matteType)) {{
            return JSON.stringify({{error: true, message: "不支持的轨道遮罩类型: " + args.matteType}});
        }}

        app.beginUndoGroup("Set Track Matte");
        var layer = comp.layer(args.layerIndex);
        layer.trackMatteType = matteMap[args.matteType];
        app.endUndoGroup();

        return JSON.stringify({{success: true, matteType: args.matteType}});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "设置轨道遮罩失败")
                else:
                    result.metadata.update(data)
            except Exception:
                pass
        return result

    async def add_adjustment_layer(
        self,
        comp_name: str,
        name: str,
        effects: Optional[List[Dict[str, Any]]] = None,
        position: Optional[int] = None,
        project_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """添加调整图层。

        Args:
            comp_name: 合成名称
            name: 图层名称
            effects: 效果列表，每项包含 effectName, params
            position: 插入位置（1-based，可选）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 layerIndex, effectsAdded
        """
        args = {
            "compName": comp_name,
            "name": name,
            "effects": effects or [],
            "position": position,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        app.beginUndoGroup("Add Adjustment Layer");

        // 创建调整图层（黑色固态层）
        var adjLayer = comp.layers.addSolid([0, 0, 0], args.name, comp.width, comp.height, 1, comp.duration);
        adjLayer.adjustmentLayer = true;

        // 设置图层顺序（遵守 project_memory：moveToBeginning + moveAfter）
        if (args.position !== null && args.position !== undefined) {{
            var pos = parseInt(args.position);
            if (pos > 0 && pos <= comp.numLayers) {{
                adjLayer.moveAfter(comp.layer(pos));
            }} else if (pos <= 0) {{
                adjLayer.moveToBeginning();
            }}
        }}

        // 添加效果
        var effectsAdded = 0;
        if (args.effects && args.effects.length > 0) {{
            for (var e = 0; e < args.effects.length; e++) {{
                try {{
                    var effectInfo = args.effects[e];
                    var effect = adjLayer.Effects.addProperty(effectInfo.effectName);
                    if (effectInfo.params) {{
                        for (var key in effectInfo.params) {{
                            try {{
                                var prop = effect.property(key);
                                if (prop && prop.canSetValue) {{
                                    prop.setValue(effectInfo.params[key]);
                                }}
                            }} catch (err) {{}}
                        }}
                    }}
                    effectsAdded++;
                }} catch (ex) {{}}
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify({{
            success: true,
            layerIndex: adjLayer.index,
            effectsAdded: effectsAdded
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "添加调整图层失败")
                else:
                    result.metadata.update(data)
            except Exception:
                pass
        return result

    async def render_segment(
        self,
        comp_name: str,
        start_frame: int,
        end_frame: int,
        output_path: Path | str,
        project_path: Path | str,
        output_module: str = "H.264",
        render_settings: str = "Best Settings",
    ) -> EngineResult:
        """渲染合成片段。

        Args:
            comp_name: 合成名称
            start_frame: 起始帧
            end_frame: 结束帧
            output_path: 输出文件路径
            project_path: 项目路径
            output_module: 输出模块模板
            render_settings: 渲染设置模板

        Returns:
            EngineResult: 渲染结果
        """
        output_path = Path(output_path)
        project_path = Path(project_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用 aerender 的 -s 和 -e 参数指定帧范围
        cmd = [
            str(self.executable_path),
            "-project", str(project_path),
            "-comp", comp_name,
            "-s", str(start_frame),
            "-e", str(end_frame),
            "-output", str(output_path),
            "-OMtemplate", output_module,
            "-RStemplate", render_settings,
        ]

        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            metadata={
                "comp_name": comp_name,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "output_module": output_module,
            },
            error=stderr if code != 0 else None,
        )

    async def execute(self, **kwargs) -> EngineResult:
        action = kwargs.pop("action", "render_comp")
        handler = {
            "render_comp": self.render_comp,
            "run_script": self.run_script,
            # 高层操作 API
            "create_comp": self.create_comp,
            "import_footage": self.import_footage,
            "add_layer": self.add_layer,
            "add_effect": self.add_effect,
            "set_keyframes": self.set_keyframes,
            "apply_preset": self.apply_preset,
            "set_blend_mode": self.set_blend_mode,
            "set_track_matte": self.set_track_matte,
            "add_adjustment_layer": self.add_adjustment_layer,
            "render_segment": self.render_segment,
        }.get(action)
        if handler is None:
            return EngineResult(success=False, error=f"Unknown action: {action}")
        return await handler(**kwargs)

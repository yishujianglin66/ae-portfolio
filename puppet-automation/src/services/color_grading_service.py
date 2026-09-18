"""多段调色系统封装 - Color grading service for multi-segment video."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from loguru import logger

from ..config import settings
from ..engines.ae.engine import AEEngine
from ..engines.base import EngineResult


class ColorGradingService:
    """多段调色服务 - 为不同视频段落应用特定滤镜组合。

    根据音乐结构（Intro/Build/Drop/Break/Outro）自动创建独立的调色调整层，
    使用调整层而非纯色层，避免遮挡画面。

    滤镜组合方案：
        - Intro: ColorBalance + CC Toner（暖色调引入）
        - Build: ColorBalance + Photo Filter + Curves（递进增强）
        - Drop: ColorBalance + CC Toner + Vibrance（高潮强对比）
        - Break: ColorBalance + Hue-Sat + Tint（情绪过渡）
        - Outro: ColorBalance + Photo Filter + CC Toner（收尾柔和）

    AE调色工作流：
        AE（基础校正）→ ProRes 4444 XQ → DaVinci Resolve（专业调色）
    """

    SEGMENT_FILTERS = {
        "intro": ["ADBE Color Balance 2", "CC Toner"],
        "build": ["ADBE Color Balance 2", "ADBE PhotoFilterColor", "ADBE Curve"],
        "drop": ["ADBE Color Balance 2", "CC Toner", "ADBE Vibrance"],
        "break": ["ADBE Color Balance 2", "ADBE HUE SATURATION", "Tint"],
        "outro": ["ADBE Color Balance 2", "ADBE PhotoFilterColor", "CC Toner"],
    }

    FILTER_NAMES = {
        "ADBE Color Balance 2": "Color Balance 2",
        "ADBE Curve": "Curves",
        "ADBE Vibrance": "Vibrance",
        "ADBE HUE SATURATION": "Hue/Saturation",
        "ADBE PhotoFilterColor": "Photo Filter",
        "CC Toner": "CC Toner",
        "Tint": "Tint",
        "ADBE Lumetri": "Lumetri Color",
    }

    def __init__(self, ae_engine: AEEngine | None = None):
        """初始化调色服务。

        Args:
            ae_engine: AE引擎实例，如不提供则从设置创建
        """
        self.ae = ae_engine or AEEngine(settings.aerender_path)

    async def _resolve_lut_path(self, lut_name_or_path: str | Path) -> Path:
        """通过 resource_index_service 解析 LUT 名称到文件路径.

        解析顺序：
            1. 若传入的是已存在的文件路径，直接返回
            2. 否则当作 LUT 名称，调用 resource_index_service.find_lut() 查找
            3. resource_index_service 不可用时，降级到原 Path(lut_name_or_path) 逻辑

        Args:
            lut_name_or_path: LUT 文件路径或名称

        Returns:
            解析后的 LUT 文件 Path

        Raises:
            ValueError: 当 LUT 既不是已存在的文件，也无法在资源库中找到时
        """
        # 1. 若传入的是已存在的文件路径，直接返回
        lut_path = Path(lut_name_or_path)
        if lut_path.exists():
            return lut_path

        # 2. 当作 LUT 名称，通过 resource_index_service 查找
        try:
            from .resource_index_service import resource_index_service
        except ImportError as e:
            logger.warning(
                f"resource_index_service 不可用，LUT 解析降级到原 Path 逻辑: {e}"
            )
            return Path(lut_name_or_path)

        try:
            resolved = await resource_index_service.find_lut(str(lut_name_or_path))
        except Exception as e:
            logger.warning(f"resource_index_service 查找 LUT 失败: {e}")
            return Path(lut_name_or_path)

        if resolved is None:
            raise ValueError(
                f"LUT 未找到: '{lut_name_or_path}' "
                f"(既不是有效文件路径: {lut_path}，也不在资源库中)"
            )

        logger.debug(f"LUT '{lut_name_or_path}' 已解析到: {resolved}")
        return resolved

    async def create_segment_grade_layer(
        self,
        comp_name: str,
        segment_name: str,
        start_frame: int,
        end_frame: int,
        filter_preset: str = "cinematic",
    ) -> EngineResult:
        """创建段落专属调色调整层。

        Args:
            comp_name: 合成名称
            segment_name: 段落名称（intro/build/drop/break/outro）
            start_frame: 起始帧
            end_frame: 结束帧
            filter_preset: 预设风格（可选）

        Returns:
            EngineResult 包含创建的图层索引和效果列表
        """
        segment_lower = segment_name.lower()
        if segment_lower not in self.SEGMENT_FILTERS:
            return EngineResult(
                success=False,
                error=f"未知的段落类型: {segment_name}，支持: {list(self.SEGMENT_FILTERS.keys())}",
            )

        filters = self.SEGMENT_FILTERS[segment_lower]
        layer_name = f"Grade_{segment_name}"

        jsx_code = f"""
(function() {{
    var comp = null;
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === "{comp_name}") {{
            comp = item;
            break;
        }}
    }}
    if (!comp) {{
        return JSON.stringify({{"status": "error", "message": "合成未找到: {comp_name}"}});
    }}

    app.beginUndoGroup("Create Grade Layer: {segment_name}");

    // 创建调整层
    var adjLayer = comp.layers.addSolid([0.5, 0.5, 0.5], "{layer_name}", comp.width, comp.height, comp.pixelAspect);
    adjLayer.adjustmentLayer = true;
    adjLayer.moveToBeginning();

    // 设置入点出点
    adjLayer.inPoint = start_frame / comp.frameRate;
    adjLayer.outPoint = end_frame / comp.frameRate;
    adjLayer.startTime = adjLayer.inPoint;

    // 添加滤镜
    var appliedEffects = [];
    var filters = {json.dumps(filters)};
    for (var i = 0; i < filters.length; i++) {{
        try {{
            var effect = adjLayer.Effects.addProperty(filters[i]);
            appliedEffects.push({{
                "matchName": filters[i],
                "name": effect.name,
                "index": effect.propertyIndex
            }});
        }} catch (e) {{
            // 效果添加失败，记录警告
        }}
    }}

    app.endUndoGroup();

    return JSON.stringify({{
        "status": "success",
        "layerName": adjLayer.name,
        "layerIndex": adjLayer.index,
        "inPoint": adjLayer.inPoint,
        "outPoint": adjLayer.outPoint,
        "effects": appliedEffects,
        "segment": "{segment_name}",
        "preset": "{filter_preset}"
    }});
}})();
"""
        script_result = await self.ae.run_script(jsx_code)

        if not script_result.success:
            return EngineResult(
                success=False,
                error=f"ExtendScript执行失败: {script_result.error}",
            )

        try:
            result_data = json.loads(script_result.metadata.get("stdout", "{}"))
            if result_data.get("status") != "success":
                return EngineResult(
                    success=False,
                    error=result_data.get("message", "未知错误"),
                )
            return EngineResult(
                success=True,
                metadata=result_data,
            )
        except json.JSONDecodeError:
            return EngineResult(
                success=False,
                error=f"JSON解析失败: {script_result.metadata.get('stdout', '')[:200]}",
            )

    async def apply_filter_combination(
        self,
        comp_name: str,
        layer_index: int,
        combination: Literal["intro", "build", "drop", "break", "outro"],
    ) -> EngineResult:
        """应用预设滤镜组合到指定图层。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            combination: 滤镜组合类型

        Returns:
            EngineResult 包含应用的效果列表
        """
        combination_lower = combination.lower()
        if combination_lower not in self.SEGMENT_FILTERS:
            return EngineResult(
                success=False,
                error=f"未知的滤镜组合: {combination}",
            )

        filters = self.SEGMENT_FILTERS[combination_lower]

        jsx_code = f"""
(function() {{
    var comp = null;
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === "{comp_name}") {{
            comp = item;
            break;
        }}
    }}
    if (!comp) {{
        return JSON.stringify({{"status": "error", "message": "合成未找到: {comp_name}"}});
    }}

    if (layer_index < 1 || layer_index > comp.numLayers) {{
        return JSON.stringify({{"status": "error", "message": "图层索引无效: {layer_index}"}});
    }}

    var layer = comp.layer(layer_index);

    app.beginUndoGroup("Apply Filter Combination: {combination}");

    var appliedEffects = [];
    var filters = {json.dumps(filters)};
    for (var i = 0; i < filters.length; i++) {{
        try {{
            // 检查效果是否已存在（优先名称匹配）
            var existingEffect = null;
            for (var j = 1; j <= layer.Effects.numProperties; j++) {{
                var ef = layer.Effects.property(j);
                if (ef.matchName === filters[i] || ef.name === filters[i]) {{
                    existingEffect = ef;
                    break;
                }}
            }}

            if (!existingEffect) {{
                var effect = layer.Effects.addProperty(filters[i]);
                appliedEffects.push({{
                    "matchName": filters[i],
                    "name": effect.name,
                    "index": effect.propertyIndex,
                    "newlyAdded": true
                }});
            }} else {{
                appliedEffects.push({{
                    "matchName": filters[i],
                    "name": existingEffect.name,
                    "index": existingEffect.propertyIndex,
                    "newlyAdded": false
                }});
            }}
        }} catch (e) {{
            // 效果添加失败
        }}
    }}

    app.endUndoGroup();

    return JSON.stringify({{
        "status": "success",
        "layerIndex": layer_index,
        "layerName": layer.name,
        "effects": appliedEffects,
        "combination": "{combination}"
    }});
}})();
"""

        script_result = await self.ae.run_script(jsx_code)

        if not script_result.success:
            return EngineResult(
                success=False,
                error=f"ExtendScript执行失败: {script_result.error}",
            )

        try:
            result_data = json.loads(script_result.metadata.get("stdout", "{}"))
            if result_data.get("status") != "success":
                return EngineResult(
                    success=False,
                    error=result_data.get("message", "未知错误"),
                )
            return EngineResult(
                success=True,
                metadata=result_data,
            )
        except json.JSONDecodeError:
            return EngineResult(
                success=False,
                error="JSON解析失败",
            )

    async def apply_lut(
        self,
        comp_name: str,
        layer_index: int,
        lut_path: Path | str,
        intensity: float = 100.0,
    ) -> EngineResult:
        """应用 LUT 文件到图层（通过 Lumetri Color 效果）。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            lut_path: LUT 文件路径（.cube, .3dl 等）或 LUT 名称
                （将自动通过 resource_index_service 查找）
            intensity: 强度百分比（0-100）

        Returns:
            EngineResult 包含 LUT 应用信息
        """
        # 通过 resource_index_service 解析 LUT（支持名称查找）
        try:
            lut_path = await self._resolve_lut_path(lut_path)
        except ValueError as e:
            return EngineResult(
                success=False,
                error=str(e),
            )

        if not 0 <= intensity <= 100:
            return EngineResult(
                success=False,
                error=f"intensity必须在0-100之间，当前值: {intensity}",
            )

        lut_path_str = lut_path.as_posix().replace("\\", "/")

        jsx_code = f"""
(function() {{
    var comp = null;
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === "{comp_name}") {{
            comp = item;
            break;
        }}
    }}
    if (!comp) {{
        return JSON.stringify({{"status": "error", "message": "合成未找到: {comp_name}"}});
    }}

    if (layer_index < 1 || layer_index > comp.numLayers) {{
        return JSON.stringify({{"status": "error", "message": "图层索引无效: {layer_index}"}});
    }}

    var layer = comp.layer(layer_index);
    var lutFile = new File("{lut_path_str}");
    if (!lutFile.exists) {{
        return JSON.stringify({{"status": "error", "message": "LUT文件未找到: {lut_path_str}"}});
    }}

    app.beginUndoGroup("Apply LUT");

    // 添加 Lumetri Color 效果
    var effect = layer.Effects.addProperty("ADBE Lumetri");

    var lutApplied = false;
    try {{
        var lumetri = effect.property("ADBE Lumetri Setup");
        try {{
            // 切换到自定义 LUT 模式
            lumetri.property("ADBE Lumetri LUT Choice").setValue(2);
        }} catch (e) {{}}

        // 设置 LUT 文件路径
        var customLutProp = lumetri.property("ADBE Lumetri Custom LUT File");
        customLutProp.setValue("{lut_path_str}");
        lutApplied = true;
    }} catch (e) {{
        // 尝试备用属性路径
        try {{
            effect.property("ADBE Lumetri Setup").property("ADBE Lumetri Custom LUT File").setValue("{lut_path_str}");
            lutApplied = true;
        }} catch (e2) {{
            lutApplied = false;
        }}
    }}

    // 设置强度（通过效果不透明度）
    if (intensity < 100) {{
        try {{
            effect.property("ADBE Effect Opacity").setValue(intensity);
        }} catch (e) {{
            // 备用：使用图层不透明度
            try {{
                layer.property("ADBE Transform Group").property("ADBE Opacity").setValue(intensity);
            }} catch (e2) {{}}
        }}
    }}

    app.endUndoGroup();

    return JSON.stringify({{
        "status": "success",
        "effectName": effect.name,
        "effectIndex": effect.propertyIndex,
        "lutPath": "{lut_path_str}",
        "lutApplied": lutApplied,
        "intensity": intensity,
        "layerIndex": layer_index
    }});
}})();
"""

        script_result = await self.ae.run_script(jsx_code)

        if not script_result.success:
            return EngineResult(
                success=False,
                error=f"ExtendScript执行失败: {script_result.error}",
            )

        try:
            result_data = json.loads(script_result.metadata.get("stdout", "{}"))
            if result_data.get("status") != "success":
                return EngineResult(
                    success=False,
                    error=result_data.get("message", "未知错误"),
                )
            return EngineResult(
                success=True,
                metadata=result_data,
            )
        except json.JSONDecodeError:
            return EngineResult(
                success=False,
                error="JSON解析失败",
            )

    async def apply_lut_by_name(
        self,
        comp_name: str,
        layer_index: int,
        lut_name: str,
        intensity: float = 100.0,
    ) -> EngineResult:
        """按名称查找 LUT 并应用到图层（便捷方法）.

        通过 resource_index_service 在资源库中按名称查找 LUT，
        找到后调用 apply_lut 应用到指定图层。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            lut_name: LUT 名称（在资源库中查找，如 "cinematic"）
            intensity: 强度百分比（0-100）

        Returns:
            EngineResult 包含 LUT 应用信息
        """
        return await self.apply_lut(
            comp_name=comp_name,
            layer_index=layer_index,
            lut_path=lut_name,
            intensity=intensity,
        )

    async def create_full_grading_pipeline(
        self,
        comp_name: str,
        segments: list[dict[str, Any]],
    ) -> EngineResult:
        """一键创建多段调色管线。

        为每个段落创建独立的调整层，应用对应的滤镜组合。

        Args:
            comp_name: 合成名称
            segments: 段落列表，每个元素包含:
                - name: 段落名称（intro/build/drop/break/outro）
                - start_frame: 起始帧
                - end_frame: 结束帧
                - filter_preset: 预设风格（可选）

        Returns:
            EngineResult 包含所有创建的图层信息
        """
        if not segments:
            return EngineResult(
                success=False,
                error="段落列表不能为空",
            )

        results = []
        errors = []

        for i, seg in enumerate(segments):
            segment_name = seg.get("name", "")
            start_frame = seg.get("start_frame", 0)
            end_frame = seg.get("end_frame", 0)
            filter_preset = seg.get("filter_preset", "cinematic")

            if not segment_name:
                errors.append(f"段落{i}缺少name字段")
                continue

            if end_frame <= start_frame:
                errors.append(f"段落{segment_name}的end_frame必须大于start_frame")
                continue

            result = await self.create_segment_grade_layer(
                comp_name=comp_name,
                segment_name=segment_name,
                start_frame=start_frame,
                end_frame=end_frame,
                filter_preset=filter_preset,
            )

            if result.success:
                results.append(result.metadata)
            else:
                errors.append(f"段落{segment_name}创建失败: {result.error}")

        if errors and not results:
            return EngineResult(
                success=False,
                error="所有段落创建失败:\n" + "\n".join(errors),
            )

        return EngineResult(
            success=True,
            metadata={
                "created_layers": results,
                "total_segments": len(segments),
                "successful": len(results),
                "errors": errors if errors else None,
            },
        )

    async def set_effect_parameter(
        self,
        comp_name: str,
        layer_index: int,
        effect_match_name: str,
        parameter_name: str,
        value: Any,
    ) -> EngineResult:
        """设置效果参数值。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            effect_match_name: 效果的 matchName
            parameter_name: 参数名称
            value: 参数值

        Returns:
            EngineResult 包含设置结果
        """
        jsx_code = f"""
(function() {{
    var comp = null;
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === "{comp_name}") {{
            comp = item;
            break;
        }}
    }}
    if (!comp) {{
        return JSON.stringify({{"status": "error", "message": "合成未找到: {comp_name}"}});
    }}

    if (layer_index < 1 || layer_index > comp.numLayers) {{
        return JSON.stringify({{"status": "error", "message": "图层索引无效: {layer_index}"}});
    }}

    var layer = comp.layer(layer_index);

    // 查找效果（优先 matchName，其次名称）
    var targetEffect = null;
    for (var j = 1; j <= layer.Effects.numProperties; j++) {{
        var ef = layer.Effects.property(j);
        if (ef.matchName === "{effect_match_name}" || ef.name === "{effect_match_name}") {{
            targetEffect = ef;
            break;
        }}
    }}

    if (!targetEffect) {{
        return JSON.stringify({{"status": "error", "message": "效果未找到: {effect_match_name}"}});
    }}

    app.beginUndoGroup("Set Effect Parameter");

    try {{
        var param = targetEffect.property("{parameter_name}");
        param.setValue({json.dumps(value)});

        app.endUndoGroup();

        return JSON.stringify({{
            "status": "success",
            "effectName": targetEffect.name,
            "parameter": "{parameter_name}",
            "value": {json.dumps(value)}
        }});
    }} catch (e) {{
        app.endUndoGroup();
        return JSON.stringify({{"status": "error", "message": "参数设置失败: " + e.toString()}});
    }}
}})();
"""

        script_result = await self.ae.run_script(jsx_code)

        if not script_result.success:
            return EngineResult(
                success=False,
                error=f"ExtendScript执行失败: {script_result.error}",
            )

        try:
            result_data = json.loads(script_result.metadata.get("stdout", "{}"))
            if result_data.get("status") != "success":
                return EngineResult(
                    success=False,
                    error=result_data.get("message", "未知错误"),
                )
            return EngineResult(
                success=True,
                metadata=result_data,
            )
        except json.JSONDecodeError:
            return EngineResult(
                success=False,
                error="JSON解析失败",
            )

    def get_filter_combinations(self) -> dict[str, list[str]]:
        """获取所有滤镜组合方案。

        Returns:
            Dict 段落名称 -> 滤镜列表
        """
        return dict(self.SEGMENT_FILTERS)

    def get_filter_display_name(self, match_name: str) -> str:
        """获取效果的显示名称。

        Args:
            match_name: 效果的 matchName

        Returns:
            显示名称
        """
        return self.FILTER_NAMES.get(match_name, match_name)
"""AE 命令生成器 - 将规划结果转换为 AE 可执行的 JSON 命令序列"""
from typing import Any, Dict, List


class AECommandGenerator:
    def generate_create_comp(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        duration: float = 5,
        frame_rate: int = 30,
        bg_color: list[int] = None
    ) -> list[dict[str, Any]]:
        return [{
            "op": "createComposition",
            "params": {
                "name": name,
                "width": width,
                "height": height,
                "duration": duration,
                "frameRate": frame_rate,
                "backgroundColor": bg_color or [0, 0, 0]
            }
        }]

    def generate_import_footage(self, file_paths: list[str]) -> list[dict[str, Any]]:
        commands = []
        for path in file_paths:
            commands.append({
                "op": "importFootage",
                "params": {"filePath": path}
            })
        return commands

    def generate_place_footage(
        self,
        comp_name: str,
        layer_name: str,
        file_path: str,
        start_time: float = 0
    ) -> list[dict[str, Any]]:
        return [{
            "op": "placeFootageInComp",
            "params": {
                "compName": comp_name,
                "layerName": layer_name,
                "footagePath": file_path,
                "startTime": start_time
            }
        }]

    def generate_apply_effect(
        self,
        layer_name: str,
        effect_match_name: str,
        settings: dict[str, Any],
        comp_name: str = None
    ) -> list[dict[str, Any]]:
        params = {
            "layerName": layer_name,
            "effectMatchName": effect_match_name,
            "effectSettings": settings
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "applyEffect",
            "params": params
        }]

    def generate_set_keyframe(
        self,
        layer_name: str,
        property_name: str,
        time_in_seconds: float,
        value: Any,
        ease_type: str = "linear",
        comp_name: str = None
    ) -> list[dict[str, Any]]:
        params = {
            "layerName": layer_name,
            "propertyName": property_name,
            "timeInSeconds": time_in_seconds,
            "value": value,
            "easeType": ease_type
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "setLayerKeyframe",
            "params": params
        }]

    def generate_render(
        self,
        comp_name: str,
        output_path: str,
        format: str = "mp4",
        quality: str = "high"
    ) -> list[dict[str, Any]]:
        return [{
            "op": "renderComposition",
            "params": {
                "compName": comp_name,
                "outputPath": output_path,
                "format": format,
                "quality": quality
            }
        }]

    def generate_from_planning_result(self, planning_result: dict[str, Any]) -> list[dict[str, Any]]:
        commands = []
        comp_name = planning_result.get("composition", {}).get("name", "AI_Generated")

        if "composition" in planning_result:
            comp = planning_result["composition"]
            commands.extend(self.generate_create_comp(
                name=comp.get("name", comp_name),
                width=comp.get("width", 1920),
                height=comp.get("height", 1080),
                duration=comp.get("duration", 5),
                frame_rate=comp.get("frameRate", 30),
                bg_color=comp.get("backgroundColor")
            ))

        footage_files = []
        for layer in planning_result.get("layers", []):
            if layer.get("type") in ["footage", "audio"]:
                source = layer.get("source", "")
                if source:
                    footage_files.append(source)
        if footage_files:
            commands.extend(self.generate_import_footage(footage_files))

        for layer in planning_result.get("layers", []):
            if layer.get("type") in ["footage", "audio"]:
                commands.extend(self.generate_place_footage(
                    comp_name=comp_name,
                    layer_name=layer.get("name", ""),
                    file_path=layer.get("source", ""),
                    start_time=layer.get("startTime", 0)
                ))

        for effect in planning_result.get("effects", []):
            commands.extend(self.generate_apply_effect(
                layer_name=effect.get("layerName", ""),
                effect_match_name=effect.get("effectName", ""),
                settings=effect.get("settings", {}),
                comp_name=comp_name
            ))

        for keyframe in planning_result.get("keyframes", []):
            commands.extend(self.generate_set_keyframe(
                layer_name=keyframe.get("layerName", ""),
                property_name=keyframe.get("propertyName", ""),
                time_in_seconds=keyframe.get("time", 0),
                value=keyframe.get("value", 0),
                ease_type=keyframe.get("easeType", "linear"),
                comp_name=comp_name
            ))

        return commands

    def generate_e2e_music_video(
        self,
        comp_name: str = "E2E_音乐视频",
        frame_dir: str = "D:/AE-Work/视频素材库/frames",
        bgm_path: str = "",
        beat_times: list[float] = None,
        energy_peaks: list[float] = None,
        peak_values: list[float] = None,
        bpm: float = 0.0,
        width: int = 576,
        height: int = 768,
        duration: float = 12.0,
        fps: int = 30,
    ) -> list[dict[str, Any]]:
        return [{
            "op": "e2eMusicVideo",
            "params": {
                "compName": comp_name,
                "frameDir": frame_dir,
                "bgmPath": bgm_path,
                "beatTimes": beat_times or [],
                "energyPeaks": energy_peaks or [],
                "peakValues": peak_values or [],
                "bpm": bpm,
                "width": width,
                "height": height,
                "duration": duration,
                "fps": fps,
            }
        }]

    def generate_set_expression(
        self,
        layer_name: str,
        property_path: str,
        expression: str,
        comp_name: str = None
    ) -> list[dict[str, Any]]:
        # 生成 setExpression 命令：为指定属性设置表达式
        params = {
            "layerName": layer_name,
            "propertyPath": property_path,
            "expression": expression
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "setExpression",
            "params": params
        }]

    def generate_add_mask(
        self,
        layer_name: str,
        mask_path: list[Any],
        comp_name: str = None
    ) -> list[dict[str, Any]]:
        # 生成 addMask 命令：为图层添加遮罩
        params = {
            "layerName": layer_name,
            "maskPath": mask_path
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "addMask",
            "params": params
        }]

    def generate_set_blend_mode(
        self,
        layer_name: str,
        blend_mode: str,
        comp_name: str = None
    ) -> list[dict[str, Any]]:
        # 生成 setBlendMode 命令：设置图层混合模式
        params = {
            "layerName": layer_name,
            "blendMode": blend_mode
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "setBlendMode",
            "params": params
        }]

    def generate_set_parent(
        self,
        child_layer: str,
        parent_layer: str,
        comp_name: str = None
    ) -> list[dict[str, Any]]:
        # 生成 setParent 命令：设置图层父级
        params = {
            "layerName": child_layer,
            "parentLayerName": parent_layer
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "setParent",
            "params": params
        }]

    def generate_set_track_matte(
        self,
        layer_name: str,
        matte_layer_name: str,
        matte_type: str,
        comp_name: str = None
    ) -> list[dict[str, Any]]:
        # 生成 setTrackMatte 命令：设置轨道遮罩
        params = {
            "layerName": layer_name,
            "matteLayerName": matte_layer_name,
            "matteType": matte_type
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "setTrackMatte",
            "params": params
        }]

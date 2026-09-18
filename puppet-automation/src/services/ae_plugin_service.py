"""AE Plugin Service - Video Copilot & Trapcode 插件 Python API 封装。

封装 Saber、Optical Flares、Particular、Twitch、Element 3D 等插件的调用，
通过 AEEngine 的 run_script() 方法动态执行 ExtendScript。

project_memory 约束：
- Saber 用于文字发光，Core Color 可自定义
- Optical Flares 需支持音频驱动亮度绑定
- Particular 用于战斗场景粒子（灰尘、火花）
- Twitch 用于故障效果，支持 Scale + Slide + Color 算子
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

from ..engines.ae.engine import AEEngine
from ..engines.base import EngineResult


class AEPluginService:
    """Video Copilot & Trapcode 插件服务层。

    通过 AEEngine.run_script() 执行 ExtendScript 脚本，
    封装 Saber、Optical Flares、Particular、Twitch、Element 3D 的 Python API。
    """

    def __init__(self, ae_engine: AEEngine | None = None):
        """初始化插件服务。

        Args:
            ae_engine: AE 引擎实例，若不提供则自动创建。
        """
        self._engine = ae_engine

    @property
    def engine(self) -> AEEngine:
        """获取或创建 AEEngine 实例。"""
        if self._engine is None:
            self._engine = AEEngine()
        return self._engine

    # ==================== Saber ====================

    async def _resolve_preset_path(self, preset_file: str | Path) -> Path:
        """解析预设文件路径（支持名称查找）.

        解析顺序：
            1. 若传入的是已存在的文件路径，直接返回
            2. 否则当作预设名称，调用 resource_index_service.find_ae_preset() 查找
            3. resource_index_service 不可用时，降级到原 Path(preset_file) 逻辑

        Args:
            preset_file: 预设文件路径或名称（如 "Saber" / "neon.ffx"）

        Returns:
            解析后的预设文件 Path

        Raises:
            ValueError: 当预设既不是已存在的文件，也无法在资源库中找到时
        """
        # 1. 若传入的是已存在的文件路径，直接返回
        preset_path = Path(preset_file)
        if preset_path.exists():
            return preset_path

        # 2. 当作预设名称，通过 resource_index_service 查找 ae_presets 类别
        try:
            from .resource_index_service import resource_index_service
        except ImportError as e:
            logger.warning(
                f"resource_index_service 不可用，预设解析降级到原 Path 逻辑: {e}"
            )
            return Path(preset_file)

        try:
            resolved = await resource_index_service.find_ae_preset(str(preset_file))
        except Exception as e:
            logger.warning(f"resource_index_service 查找 AE 预设失败: {e}")
            return Path(preset_file)

        if resolved is None:
            raise ValueError(
                f"AE 预设未找到: '{preset_file}' "
                f"(既不是有效文件路径: {preset_path}，也不在资源库 presets_dir 中)"
            )

        logger.debug(f"AE 预设 '{preset_file}' 已解析到: {resolved}")
        return resolved

    async def apply_saber(
        self,
        comp_name: str,
        layer_index: int,
        core_color: str = "#FFFFFF",
        glow_intensity: float = 80,
        glow_width: float = 20,
        core_thickness: float = 8,
        glow_color: str | None = None,
        preset_type: str | None = None,
        text_glow: bool = False,
        flicker_intensity: float = 0,
        flicker_speed: float = 0,
        preset_file: str | Path | None = None,
        project_path: str | Path | None = None,
    ) -> EngineResult:
        """应用 Video Copilot Saber 发光效果。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            core_color: 核心颜色（十六进制，如 "#FFFFFF"）
            glow_intensity: 发光强度 (0-500)
            glow_width: 发光宽度 (px)
            core_thickness: 核心厚度 (px)
            glow_color: 发光颜色（十六进制，如 "#00CCFF"）
            preset_type: 预设类型：energy_sword, neon, ice_fire, electric, laser, glow, trail, plasma
            text_glow: 是否启用文字发光模式
            flicker_intensity: 闪烁强度 (0-100)
            flicker_speed: 闪烁速度 (0-10)
            preset_file: .ffx 预设文件路径或名称（支持通过 resource_index_service 查找）
            project_path: 项目文件路径（可选）

        Returns:
            EngineResult 包含执行结果
        """
        # 通过 resource_index_service 解析预设（支持名称查找）
        resolved_preset_file: Path | None = None
        if preset_file is not None:
            try:
                resolved_preset_file = await self._resolve_preset_path(preset_file)
            except ValueError as e:
                return EngineResult(
                    success=False,
                    error=str(e),
                )

        script = self._build_saber_script(
            comp_name=comp_name,
            layer_index=layer_index,
            core_color=core_color,
            glow_intensity=glow_intensity,
            glow_width=glow_width,
            core_thickness=core_thickness,
            glow_color=glow_color,
            preset_type=preset_type,
            text_glow=text_glow,
            flicker_intensity=flicker_intensity,
            flicker_speed=flicker_speed,
            preset_file=resolved_preset_file,
        )
        return await self.engine.run_script(script, project_path)

    def _build_saber_script(
        self,
        comp_name: str,
        layer_index: int,
        core_color: str,
        glow_intensity: float,
        glow_width: float,
        core_thickness: float,
        glow_color: str | None,
        preset_type: str | None,
        text_glow: bool,
        flicker_intensity: float,
        flicker_speed: float,
        preset_file: str | Path | None,
    ) -> str:
        """构建 Saber ExtendScript。"""
        glow_color_rgb = self._hex_to_rgb(glow_color) if glow_color else [0.2, 0.8, 1]
        core_color_rgb = self._hex_to_rgb(core_color)

        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "coreThickness": core_thickness,
            "glowIntensity": glow_intensity,
            "glowWidth": glow_width,
            "glowColor": glow_color_rgb,
            "coreColor": core_color_rgb,
            "textGlow": text_glow,
            "flickerIntensity": flicker_intensity,
            "flickerSpeed": flicker_speed,
            "presetType": preset_type,
            "presetFile": str(preset_file) if preset_file else None,
        }
        return self._generate_apply_script("Saber", args, ["VC Saber", "ADBE VC Saber", "ACP VC Saber"])

    # ==================== Optical Flares ====================

    async def apply_optical_flares(
        self,
        comp_name: str,
        layer_index: int,
        position: tuple[int, int] = None,
        brightness: float = 100,
        scale: float = 100,
        color: str = "#FFFFFF",
        flare_type: str = "standard",
        flicker: bool = False,
        flicker_speed: float = 0,
        audio_react: bool = False,
        audio_source: str | None = None,
        project_path: str | Path | None = None,
    ) -> EngineResult:
        """应用 Video Copilot Optical Flares 镜头光晕效果。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            position: 光晕位置 (x, y)，默认为合成中心
            brightness: 亮度 (0-300%)
            scale: 缩放 (0-500%)
            color: 颜色（十六进制）
            flare_type: 光效类型：standard, anamorphic, energy, sun, lens, streak
            flicker: 是否启用闪烁
            flicker_speed: 闪烁速度
            audio_react: 是否启用音频反应（project_memory: 音频驱动亮度绑定）
            audio_source: 音频源图层名称
            project_path: 项目文件路径

        Returns:
            EngineResult 包含执行结果
        """
        script = self._build_optical_flares_script(
            comp_name=comp_name,
            layer_index=layer_index,
            position=position,
            brightness=brightness,
            scale=scale,
            color=color,
            flare_type=flare_type,
            flicker=flicker,
            flicker_speed=flicker_speed,
            audio_react=audio_react,
            audio_source=audio_source,
        )
        return await self.engine.run_script(script, project_path)

    def _build_optical_flares_script(
        self,
        comp_name: str,
        layer_index: int,
        position: tuple[int, int] | None,
        brightness: float,
        scale: float,
        color: str,
        flare_type: str,
        flicker: bool,
        flicker_speed: float,
        audio_react: bool,
        audio_source: str | None,
    ) -> str:
        """构建 Optical Flares ExtendScript。"""
        color_rgb = self._hex_to_rgb(color)

        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "position": list(position) if position else None,
            "brightness": brightness,
            "scale": scale,
            "color": color_rgb,
            "flareType": flare_type,
            "flicker": flicker,
            "flickerSpeed": flicker_speed,
            "audioReact": audio_react,
            "audioSource": audio_source,
        }
        return self._generate_apply_script(
            "Optical Flares", args, ["Optical Flares", "VC Optical Flares", "ACP Optical Flares"]
        )

    # ==================== Particular ====================

    async def apply_particular(
        self,
        comp_name: str,
        layer_index: int,
        emitter_type: str = "point",
        particles_per_sec: int = 100,
        particle_size: float = 5,
        velocity: float = 100,
        velocity_random: float = 20,
        particle_life: float = 3,
        size_random: float = 50,
        opacity: float = 100,
        particle_color: str = "#FFFFFF",
        gravity: float = 0,
        wind_x: float = 0,
        wind_y: float = 0,
        wind_z: float = 0,
        air_resistance: float = 0,
        motion_blur: bool = False,
        project_path: str | Path | None = None,
    ) -> EngineResult:
        """应用 Trapcode Particular 粒子效果。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            emitter_type: 发射器类型：point, box, sphere, grid, light, layer
            particles_per_sec: 每秒粒子数
            particle_size: 粒子大小
            velocity: 速度
            velocity_random: 速度随机 (%)
            particle_life: 粒子生命周期 (秒)
            size_random: 大小随机 (%)
            opacity: 不透明度 (%)
            particle_color: 粒子颜色（十六进制）
            gravity: 重力
            wind_x/y/z: 风力 X/Y/Z
            air_resistance: 空气阻力
            motion_blur: 是否启用运动模糊
            project_path: 项目文件路径

        Returns:
            EngineResult 包含执行结果

        project_memory: Particular 用于战斗场景粒子（灰尘、火花）
        """
        script = self._build_particular_script(
            comp_name=comp_name,
            layer_index=layer_index,
            emitter_type=emitter_type,
            particles_per_sec=particles_per_sec,
            particle_size=particle_size,
            velocity=velocity,
            velocity_random=velocity_random,
            particle_life=particle_life,
            size_random=size_random,
            opacity=opacity,
            particle_color=particle_color,
            gravity=gravity,
            wind_x=wind_x,
            wind_y=wind_y,
            wind_z=wind_z,
            air_resistance=air_resistance,
            motion_blur=motion_blur,
        )
        return await self.engine.run_script(script, project_path)

    def _build_particular_script(
        self,
        comp_name: str,
        layer_index: int,
        emitter_type: str,
        particles_per_sec: int,
        particle_size: float,
        velocity: float,
        velocity_random: float,
        particle_life: float,
        size_random: float,
        opacity: float,
        particle_color: str,
        gravity: float,
        wind_x: float,
        wind_y: float,
        wind_z: float,
        air_resistance: float,
        motion_blur: bool,
    ) -> str:
        """构建 Particular ExtendScript。"""
        color_rgb = self._hex_to_rgb(particle_color)

        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "emitterType": emitter_type,
            "particlesPerSec": particles_per_sec,
            "particleSize": particle_size,
            "velocity": velocity,
            "velocityRandom": velocity_random,
            "particleLife": particle_life,
            "sizeRandom": size_random,
            "opacity": opacity,
            "particleColor": color_rgb,
            "gravity": gravity,
            "windX": wind_x,
            "windY": wind_y,
            "windZ": wind_z,
            "airResistance": air_resistance,
            "motionBlur": motion_blur,
        }
        return self._generate_apply_script(
            "Particular", args, ["Particular", "Trapcode Particular", "ACP Particular", "RG Particular"]
        )

    # ==================== Twitch ====================

    async def apply_twitch(
        self,
        comp_name: str,
        layer_index: int,
        operators: list[str] = None,
        amount: float = 20,
        speed: float = 5,
        random_seed: int | None = None,
        project_path: str | Path | None = None,
    ) -> EngineResult:
        """应用 Video Copilot Twitch 故障效果。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            operators: 启用的算子列表：shake, spin, scale, blur, color, brightness, glitch, slice
            amount: 效果强度 (0-100%)
            speed: 动画速度 (0-10)
            random_seed: 随机种子
            project_path: 项目文件路径

        Returns:
            EngineResult 包含执行结果

        project_memory: Twitch 用于故障效果，支持 Scale + Slide + Color 算子
        """
        if operators is None:
            operators = ["scale", "slide", "color"]

        script = self._build_twitch_script(
            comp_name=comp_name,
            layer_index=layer_index,
            operators=operators,
            amount=amount,
            speed=speed,
            random_seed=random_seed,
        )
        return await self.engine.run_script(script, project_path)

    def _build_twitch_script(
        self,
        comp_name: str,
        layer_index: int,
        operators: list[str],
        amount: float,
        speed: float,
        random_seed: int | None,
    ) -> str:
        """构建 Twitch ExtendScript。"""
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "operators": operators,
            "amount": amount,
            "speed": speed,
            "randomSeed": random_seed,
        }
        return self._generate_apply_script("Twitch", args, ["VC Twitch", "Twitch", "ACP Twitch"])

    # ==================== Element 3D ====================

    async def apply_element_3d(
        self,
        comp_name: str,
        layer_index: int,
        model_path: str | Path | None = None,
        diffuse_color: str = "#FFFFFF",
        metallic: float = 0.0,
        roughness: float = 0.5,
        emissive_color: str | None = None,
        emissive_intensity: float = 0.0,
        particle_replicator_shape: str | None = None,
        particles_count: int | None = None,
        position_offset: tuple[float, float, float] | None = None,
        rotation_offset: tuple[float, float, float] | None = None,
        scale: float = 1.0,
        project_path: str | Path | None = None,
    ) -> EngineResult:
        """应用 Video Copilot Element 3D 模型效果。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            model_path: 3D 模型文件路径（.obj, .c4d, .fbx）
            diffuse_color: 漫反射颜色（十六进制）
            metallic: 金属度 (0-1)
            roughness: 粗糙度 (0-1)
            emissive_color: 自发光颜色
            emissive_intensity: 自发光强度 (0-5)
            particle_replicator_shape: 粒子复制器形状：Sphere, Box, Grid, Layer, Line
            particles_count: 粒子数量
            position_offset: 位置偏移 (x, y, z)
            rotation_offset: 旋转偏移 (x, y, z) 度
            scale: 缩放
            project_path: 项目文件路径

        Returns:
            EngineResult 包含执行结果
        """
        script = self._build_element_3d_script(
            comp_name=comp_name,
            layer_index=layer_index,
            model_path=model_path,
            diffuse_color=diffuse_color,
            metallic=metallic,
            roughness=roughness,
            emissive_color=emissive_color,
            emissive_intensity=emissive_intensity,
            particle_replicator_shape=particle_replicator_shape,
            particles_count=particles_count,
            position_offset=position_offset,
            rotation_offset=rotation_offset,
            scale=scale,
        )
        return await self.engine.run_script(script, project_path)

    def _build_element_3d_script(
        self,
        comp_name: str,
        layer_index: int,
        model_path: str | Path | None,
        diffuse_color: str,
        metallic: float,
        roughness: float,
        emissive_color: str | None,
        emissive_intensity: float,
        particle_replicator_shape: str | None,
        particles_count: int | None,
        position_offset: tuple[float, float, float] | None,
        rotation_offset: tuple[float, float, float] | None,
        scale: float,
    ) -> str:
        """构建 Element 3D ExtendScript。"""
        diffuse_rgb = self._hex_to_rgb(diffuse_color)
        emissive_rgb = self._hex_to_rgb(emissive_color) if emissive_color else None

        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "modelPath": str(model_path) if model_path else None,
            "diffuseColor": diffuse_rgb,
            "metallic": metallic,
            "roughness": roughness,
            "emissiveColor": emissive_rgb,
            "emissiveIntensity": emissive_intensity,
            "particleReplicatorShape": particle_replicator_shape,
            "particlesCount": particles_count,
            "positionOffset": list(position_offset) if position_offset else None,
            "rotationOffset": list(rotation_offset) if rotation_offset else None,
            "scale": scale,
        }
        return self._generate_apply_script("Element", args, ["Element 3D", "VC Element", "Element"])

    # ==================== 辅助方法 ====================

    def _hex_to_rgb(self, hex_color: str) -> list[float]:
        """将十六进制颜色转换为 [0-1] 范围的 RGB 列表。

        Args:
            hex_color: 十六进制颜色字符串（如 "#FF0000" 或 "FF0000"）

        Returns:
            [r, g, b] 列表，范围 0-1
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return [round(r, 4), round(g, 4), round(b, 4)]

    def _generate_apply_script(
        self,
        effect_name: str,
        args: dict[str, Any],
        match_names: list[str],
    ) -> str:
        """生成通用的插件效果应用脚本。

        Args:
            effect_name: 效果名称
            args: 参数字典
            match_names: MatchName 候选列表

        Returns:
            ExtendScript 代码字符串
        """
        args_json = json.dumps(args, indent=2)

        # 生成 matchNames 尝试代码
        match_name_attempts = "\n        ".join([
            f'try {{ fx = layer.Effects.addProperty("{name}"); if (fx) {{ usedMatchName = "{name}"; break; }} }} catch (e) {{}}'
            for name in match_names
        ])

        return f'''(function() {{
    var args = {args_json};

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
        return JSON.stringify({{ status: "error", message: "E101: 合成未找到: " + args.compName }});
    }}

    if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
        return JSON.stringify({{ status: "error", message: "E102: 图层索引无效: " + args.layerIndex }});
    }}

    var layer = comp.layer(args.layerIndex);
    var fx = null;
    var usedMatchName = "";

    app.beginUndoGroup("Apply {effect_name}");

    // 尝试添加效果
    {match_name_attempts}

    if (!fx) {{
        app.endUndoGroup();
        return JSON.stringify({{ status: "error", message: "E201: {effect_name} 效果未安装" }});
    }}

    var applied = [];

    // 通用属性设置函数
    function setProp(propName, value) {{
        try {{
            var p = fx.property(propName);
            if (p) {{
                p.setValue(value);
                applied.push(propName);
            }}
        }} catch (e) {{}}
    }}

    // 设置参数（根据具体效果类型）
    {self._get_effect_param_setter(effect_name, args)}

    app.endUndoGroup();

    return JSON.stringify({{
        status: "success",
        message: "{effect_name} 效果应用成功",
        effectName: fx.name,
        effectIndex: fx.propertyIndex,
        matchName: usedMatchName,
        appliedProps: applied
    }});
}})()'''

    def _get_effect_param_setter(self, effect_name: str, args: dict[str, Any]) -> str:
        """获取特定效果类型的参数设置代码。

        Args:
            effect_name: 效果名称
            args: 参数字典

        Returns:
            ExtendScript 代码片段
        """
        if effect_name == "Saber":
            return '''
    // Saber 参数
    if (args.coreThickness !== undefined) setProp("Core Thickness", args.coreThickness);
    if (args.glowIntensity !== undefined) setProp("Glow Intensity", args.glowIntensity);
    if (args.glowWidth !== undefined) setProp("Glow Width", args.glowWidth);
    if (args.glowColor) setProp("Glow Color", args.glowColor);
    if (args.coreColor) setProp("Core Color", args.coreColor);
    if (args.textGlow) setProp("Text Mode", true);
    if (args.flickerIntensity > 0) setProp("Flicker Intensity", args.flickerIntensity);
    if (args.flickerSpeed > 0) setProp("Flicker Speed", args.flickerSpeed);'''

        elif effect_name == "Optical Flares":
            return '''
    // Optical Flares 参数
    if (args.position) setProp("Position XY", args.position);
    if (args.brightness !== undefined) setProp("Brightness", args.brightness);
    if (args.scale !== undefined) setProp("Scale", args.scale);
    if (args.color) setProp("Color", args.color);
    if (args.flicker) setProp("Flicker", true);
    if (args.flickerSpeed > 0) setProp("Flicker Speed", args.flickerSpeed);
    if (args.audioReact) {{
        setProp("Audio React", true);
        if (args.audioSource) {{
            // 查找音频源图层
            for (var li = 1; li <= comp.numLayers; li++) {{
                if (comp.layer(li).name === args.audioSource) {{
                    setProp("Audio Source", li);
                    break;
                }}
            }}
        }}
    }}'''

        elif effect_name == "Particular":
            return '''
    // Particular 参数 - 通过分组设置
    var emitterGroup = null, particleGroup = null, physGroup = null;
    try { emitterGroup = fx.property("Emitter"); } catch (e) {}
    try { particleGroup = fx.property("Particle"); } catch (e) {}
    try { physGroup = fx.property("Physics"); } catch (e) {}

    // Emitter
    if (emitterGroup) {
        var emitterTypeMap = {point: 1, box: 2, sphere: 3, grid: 4, light: 5, layer: 6};
        if (args.emitterType && emitterTypeMap[args.emitterType]) {
            try { emitterGroup.property("Emitter Type").setValue(emitterTypeMap[args.emitterType]); applied.push("Emitter Type"); } catch (e) {}
        }
        if (args.particlesPerSec !== undefined) {
            try { emitterGroup.property("Particles/sec").setValue(args.particlesPerSec); applied.push("Particles/sec"); } catch (e) {}
        }
        if (args.velocity !== undefined) {
            try { emitterGroup.property("Velocity").setValue(args.velocity); applied.push("Velocity"); } catch (e) {}
        }
    }

    // Particle
    if (particleGroup) {
        if (args.particleLife !== undefined) {
            try { particleGroup.property("Life [sec]").setValue(args.particleLife); applied.push("Life"); } catch (e) {}
        }
        if (args.particleSize !== undefined) {
            try { particleGroup.property("Size").setValue(args.particleSize); applied.push("Size"); } catch (e) {}
        }
        if (args.opacity !== undefined) {
            try { particleGroup.property("Opacity").setValue(args.opacity); applied.push("Opacity"); } catch (e) {}
        }
        if (args.particleColor) {
            try { particleGroup.property("Color").setValue(args.particleColor); applied.push("Color"); } catch (e) {}
        }
    }

    // Physics
    if (physGroup) {
        if (args.gravity !== undefined) {
            try { physGroup.property("Gravity").setValue(args.gravity); applied.push("Gravity"); } catch (e) {}
        }
    }

    // Motion Blur
    if (args.motionBlur) {
        try { comp.motionBlur = true; layer.motionBlur = true; applied.push("Motion Blur"); } catch (e) {}
    }'''

        elif effect_name == "Twitch":
            return '''
    // Twitch 参数
    if (args.amount !== undefined) setProp("Amount", args.amount);
    if (args.speed !== undefined) setProp("Speed", args.speed);
    if (args.randomSeed !== undefined) setProp("Random Seed", args.randomSeed);

    // 根据算子启用对应参数
    if (args.operators) {
        for (var i = 0; i < args.operators.length; i++) {
            var op = args.operators[i].toLowerCase();
            if (op === "shake") setProp("Shake", args.amount);
            else if (op === "scale") setProp("Scale", args.amount);
            else if (op === "color") setProp("Color Split", args.amount / 2);
            else if (op === "blur") setProp("Blur", args.amount / 3);
            else if (op === "slice") setProp("Slice", args.amount / 2);
            else if (op === "slide") {
                // Slide 通过 Shake X/Y 实现
                setProp("Shake", args.amount * 0.8);
            }
        }
    }'''

        elif effect_name == "Element":
            return '''
    // Element 3D 参数
    if (args.diffuseColor) setProp("Diffuse Color", args.diffuseColor);
    if (args.metallic !== undefined) setProp("Metallic", args.metallic);
    if (args.roughness !== undefined) setProp("Roughness", args.roughness);
    if (args.emissiveColor) setProp("Emissive Color", args.emissiveColor);
    if (args.emissiveIntensity > 0) setProp("Emissive Intensity", args.emissiveIntensity);
    if (args.scale !== undefined) setProp("Scale", args.scale);

    // 粒子复制器
    if (args.particleReplicatorShape && args.particlesCount) {
        try {
            var replicator = fx.property("Particle Replicator");
            if (replicator) {
                var shapeMap = {Sphere: 1, Box: 2, Grid: 3, Layer: 4, Line: 5};
                if (shapeMap[args.particleReplicatorShape]) {
                    replicator.property("Shape").setValue(shapeMap[args.particleReplicatorShape]);
                }
                replicator.property("Particles All").setValue(args.particlesCount);
                applied.push("Particle Replicator");
            }
        } catch (e) {}
    }

    // 位置/旋转偏移
    if (args.positionOffset) setProp("Position Offset", args.positionOffset);
    if (args.rotationOffset) setProp("Rotation Offset", args.rotationOffset);'''

        return ""

    # ==================== 高级功能 ====================

    async def apply_saber_preset(
        self,
        comp_name: str,
        layer_index: int,
        preset_name: str,
        project_path: str | Path | None = None,
    ) -> EngineResult:
        """应用 Saber 预设效果。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引
            preset_name: 预设名称：lightsaber, neon, electric, laser, plasma
            project_path: 项目路径

        Returns:
            EngineResult
        """
        presets = {
            "lightsaber": {"core_thickness": 4, "glow_intensity": 80, "glow_width": 20, "core_color": "#FFFFFF"},
            "neon": {"core_thickness": 2, "glow_intensity": 60, "glow_width": 40, "core_color": "#FFFFFF"},
            "electric": {"core_thickness": 1, "glow_intensity": 50, "glow_width": 15, "core_color": "#FFFFFF"},
            "laser": {"core_thickness": 3, "glow_intensity": 100, "glow_width": 25, "core_color": "#FFFFFF"},
            "plasma": {"core_thickness": 5, "glow_intensity": 70, "glow_width": 30, "core_color": "#FFFFFF"},
        }

        preset = presets.get(preset_name.lower(), presets["lightsaber"])
        return await self.apply_saber(
            comp_name=comp_name,
            layer_index=layer_index,
            core_color=preset["core_color"],
            glow_intensity=preset["glow_intensity"],
            glow_width=preset["glow_width"],
            core_thickness=preset["core_thickness"],
            project_path=project_path,
        )

    async def apply_particular_battle_particles(
        self,
        comp_name: str,
        layer_index: int,
        particle_type: str = "dust",
        intensity: str = "medium",
        project_path: str | Path | None = None,
    ) -> EngineResult:
        """应用战斗场景粒子预设（project_memory: 战斗场景粒子）。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引
            particle_type: 粒子类型：dust（灰尘）, sparks（火花）, debris（碎片）
            intensity: 强度：light, medium, heavy
            project_path: 项目路径

        Returns:
            EngineResult
        """
        presets = {
            "dust": {"color": "#8B7355", "size": 3, "life": 4, "gravity": 50, "velocity": 80},
            "sparks": {"color": "#FFAA00", "size": 2, "life": 1, "gravity": -20, "velocity": 200},
            "debris": {"color": "#555555", "size": 8, "life": 3, "gravity": 200, "velocity": 150},
        }

        intensity_multipliers = {"light": 0.5, "medium": 1.0, "heavy": 2.0}

        preset = presets.get(particle_type, presets["dust"])
        mult = intensity_multipliers.get(intensity, 1.0)

        return await self.apply_particular(
            comp_name=comp_name,
            layer_index=layer_index,
            particles_per_sec=int(100 * mult),
            particle_size=preset["size"],
            particle_color=preset["color"],
            gravity=preset["gravity"],
            particle_life=preset["life"],
            velocity=preset["velocity"],
            motion_blur=True,
            project_path=project_path,
        )
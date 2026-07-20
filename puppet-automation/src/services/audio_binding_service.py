"""Audio-Effect Binding Service - 音频效果绑定自动化系统.

实现音频频段与 AE 效果属性的自动绑定，支持：
1. Audio Controller 调整层（4 频段滑块：Global/Low/Mid/High）
2. 效果属性频段绑定（表达式自动生成）
3. 音频关键帧生成（librosa 频谱分析）
4. 节拍关键帧模板（强拍 5 关键帧、弱拍 2 关键帧）

集成点：
- 扩展 audio_analyzer_enhanced.py 的频段分析能力
- 调用 AEEngine.run_script() 应用表达式和关键帧
"""
from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..engines.ae.engine import AEEngine
from ..engines.base import EngineResult


@dataclass
class FrequencyBand:
    """频段定义."""
    name: str
    freq_min: float  # Hz
    freq_max: float  # Hz
    slider_name: str  # AE 滑块名称


# 预定义频段配置
FREQUENCY_BANDS = {
    "global": FrequencyBand("global", 20, 20000, "Global"),
    "low": FrequencyBand("low", 20, 250, "Low"),
    "mid": FrequencyBand("mid", 250, 4000, "Mid"),
    "high": FrequencyBand("high", 4000, 20000, "High"),
}


@dataclass
class BeatKeyframeTemplate:
    """节拍关键帧模板."""
    beat_type: str  # strong_beat | weak_beat
    keyframes: List[Dict[str, Any]]  # [{time_offset, value, ease_type}, ...]


class AudioBindingService:
    """音频效果绑定服务 - 实现音频驱动效果参数变化."""

    def __init__(self, ae_engine: AEEngine, analyzer_path: Optional[Path] = None):
        """初始化音频绑定服务.

        Args:
            ae_engine: AE 引擎实例
            analyzer_path: audio_analyzer_enhanced.py 路径（可选）
        """
        self.ae_engine = ae_engine
        self.analyzer_path = analyzer_path or Path(__file__).parent.parent.parent.parent / "audio_analyzer_enhanced.py"
        self._librosa = None
        self._numpy = None

    def _ensure_librosa(self):
        """延迟加载 librosa."""
        if self._librosa is None:
            try:
                import librosa
                import numpy
                self._librosa = librosa
                self._numpy = numpy
            except ImportError:
                raise ImportError("librosa 未安装，请执行: pip install librosa numpy")
        return self._librosa, self._numpy

    async def create_audio_controller(self, comp_name: str) -> EngineResult:
        """创建 Audio Controller 调整层，包含 4 个频段滑块：Global/Low/Mid/High.

        Args:
            comp_name: 目标合成名称

        Returns:
            EngineResult: 执行结果
        """
        logger.info(f"[AudioBinding] 创建 Audio Controller 调整层: {comp_name}")

        # ExtendScript: 创建调整层 + 添加 4 个滑块效果
        script = f'''
var compName = "{comp_name}";
var comp = null;

// 查找目标合成
for (var i = 1; i <= app.project.numItems; i++) {{
    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {{
        comp = app.project.item(i);
        break;
    }}
}}

if (!comp) {{
    "ERROR: Comp not found: " + compName;
}} else {{
    // 创建调整层
    var adjustmentLayer = comp.layers.addSolid([0.5, 0.5, 0.5], "Audio Controller", comp.width, comp.height, comp.pixelAspect, comp.duration);
    adjustmentLayer.adjustmentLayer = true;

    // 添加 4 个滑块效果
    var sliderNames = ["Global", "Low", "Mid", "High"];
    var sliders = [];

    for (var j = 0; j < sliderNames.length; j++) {{
        var effect = adjustmentLayer.Effects.addProperty("ADBE Slider Control");
        effect.name = sliderNames[j];
        sliders.push(effect);
    }}

    "SUCCESS: Audio Controller created with 4 sliders";
}}
'''
        result = await self.ae_engine.run_script(script)

        if result.success:
            logger.success(f"[AudioBinding] Audio Controller 创建成功")
        else:
            logger.error(f"[AudioBinding] Audio Controller 创建失败: {result.error}")

        return result

    async def bind_effect_to_frequency(
        self,
        comp_name: str,
        layer_index: int,
        effect_name: str,
        property_name: str,
        frequency_band: str,
        expression_modifiers: Optional[Dict[str, Any]] = None,
    ) -> EngineResult:
        """将效果属性绑定到指定频段.

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（从 1 开始）
            effect_name: 效果名称
            property_name: 属性名称
            frequency_band: 频段名称 (global/low/mid/high)
            expression_modifiers: 表达式修饰符（可选）
                - scale: 缩放系数
                - offset: 偏移量
                - clamp_min: 最小值
                - clamp_max: 最大值
                - sine_freq: 正弦波频率调制

        Returns:
            EngineResult: 执行结果
        """
        logger.info(
            f"[AudioBinding] 绑定 {effect_name}.{property_name} 到 {frequency_band} 频段"
        )

        # 验证频段
        if frequency_band not in FREQUENCY_BANDS:
            return EngineResult(
                success=False,
                error=f"无效频段: {frequency_band}，可选值: global/low/mid/high"
            )

        band = FREQUENCY_BANDS[frequency_band]
        modifiers = expression_modifiers or {}

        # 生成表达式
        expression = self._generate_binding_expression(
            band.slider_name, modifiers
        )

        # ExtendScript: 应用表达式
        script = f'''
var compName = "{comp_name}";
var layerIdx = {layer_index};
var effectName = "{effect_name}";
var propName = "{property_name}";
var expr = "{expression}";

var comp = null;
for (var i = 1; i <= app.project.numItems; i++) {{
    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {{
        comp = app.project.item(i);
        break;
    }}
}}

if (!comp) {{
    "ERROR: Comp not found";
}} else {{
    var layer = comp.layer(layerIdx);
    if (!layer) {{
        "ERROR: Layer not found at index: " + layerIdx;
    }} else {{
        var effect = layer.effect(effectName);
        if (!effect) {{
            "ERROR: Effect not found: " + effectName;
        }} else {{
            var prop = effect.property(propName);
            if (!prop) {{
                "ERROR: Property not found: " + propName;
            }} else {{
                prop.expression = expr;
                "SUCCESS: Expression applied to " + effectName + "." + propName;
            }}
        }}
    }}
}}
'''
        result = await self.ae_engine.run_script(script)

        if result.success:
            logger.success(
                f"[AudioBinding] 绑定成功: {effect_name}.{property_name} → {frequency_band}"
            )
        else:
            logger.error(f"[AudioBinding] 绑定失败: {result.error}")

        return result

    def _generate_binding_expression(
        self,
        slider_name: str,
        modifiers: Dict[str, Any]
    ) -> str:
        """生成效果绑定表达式.

        表达式路径格式: thisComp.layer("Audio Controller").effect("Slider Name")("Slider")

        Args:
            slider_name: 滑块名称
            modifiers: 修饰符配置

        Returns:
            str: ExtendScript 表达式字符串
        """
        # 基础表达式：读取滑块值
        base_expr = f'thisComp.layer("Audio Controller").effect("{slider_name}")("Slider")'

        # 应用修饰符
        expr_parts = [f"sliderVal = {base_expr};"]

        # 缩放
        scale = modifiers.get("scale", 1.0)
        if scale != 1.0:
            expr_parts.append(f"sliderVal = sliderVal * {scale};")

        # 偏移
        offset = modifiers.get("offset", 0)
        if offset != 0:
            expr_parts.append(f"sliderVal = sliderVal + {offset};")

        # 正弦波调制（用于 Opacity/Rotation）
        sine_freq = modifiers.get("sine_freq")
        if sine_freq:
            expr_parts.append(f"sliderVal = sliderVal + Math.sin(time * {sine_freq} * 2 * Math.PI) * 10;")

        # Clamp 范围
        clamp_min = modifiers.get("clamp_min")
        clamp_max = modifiers.get("clamp_max")
        if clamp_min is not None or clamp_max is not None:
            clamp_expr = "sliderVal"
            if clamp_min is not None:
                clamp_expr = f"Math.max({clamp_min}, {clamp_expr})"
            if clamp_max is not None:
                clamp_expr = f"Math.min({clamp_max}, {clamp_expr})"
            expr_parts.append(f"sliderVal = {clamp_expr};")

        expr_parts.append("sliderVal;")

        return " ".join(expr_parts)

    async def generate_audio_keyframes(
        self,
        audio_path: Path,
        frequency_band: str = "global",
        frame_rate: float = 30.0,
        smooth_window: int = 5,
    ) -> List[Dict[str, Any]]:
        """从音频文件生成指定频段的关键帧数据.

        Args:
            audio_path: 音频文件路径
            frequency_band: 频段名称 (global/low/mid/high)
            frame_rate: 帧率（用于关键帧时间点）
            smooth_window: 平滑窗口大小

        Returns:
            List[Dict]: 关键帧数据列表 [{time, value, normalized_value}, ...]
        """
        logger.info(f"[AudioBinding] 生成关键帧: {audio_path.name} → {frequency_band}")

        if not audio_path.exists():
            logger.error(f"[AudioBinding] 音频文件不存在: {audio_path}")
            return []

        # 验证频段
        if frequency_band not in FREQUENCY_BANDS:
            logger.error(f"[AudioBinding] 无效频段: {frequency_band}")
            return []

        band = FREQUENCY_BANDS[frequency_band]

        # 延迟加载 librosa
        librosa, np = self._ensure_librosa()

        # 异步执行音频分析
        loop = asyncio.get_event_loop()
        keyframes = await loop.run_in_executor(
            None,
            lambda: self._analyze_frequency_band(
                str(audio_path), band, frame_rate, smooth_window, librosa, np
            )
        )

        logger.success(
            f"[AudioBinding] 关键帧生成完成: {len(keyframes)} 帧, 频段={band.name}"
        )
        return keyframes

    def _analyze_frequency_band(
        self,
        audio_path: str,
        band: FrequencyBand,
        frame_rate: float,
        smooth_window: int,
        librosa,
        np,
    ) -> List[Dict[str, Any]]:
        """分析指定频段能量（内部同步方法）.

        Args:
            audio_path: 音频文件路径
            band: 频段定义
            frame_rate: 帧率
            smooth_window: 平滑窗口
            librosa: librosa 模块
            np: numpy 模块

        Returns:
            List[Dict]: 关键帧数据
        """
        # 加载音频
        y, sr = librosa.load(audio_path, sr=22050)
        duration = librosa.get_duration(y=y, sr=sr)

        # STFT 频谱分析
        n_fft = 2048
        hop_length = 512
        D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # 找到目标频段的频率索引
        freq_mask = (freqs >= band.freq_min) & (freqs <= band.freq_max)
        if not np.any(freq_mask):
            logger.warning(f"[AudioBinding] 频段 {band.name} 无有效频率")
            return []

        # 提取频段能量
        band_energy = np.abs(D[freq_mask, :]).mean(axis=0)

        # 平滑处理
        if smooth_window > 1:
            kernel = np.ones(smooth_window) / smooth_window
            band_energy = np.convolve(band_energy, kernel, mode="same")

        # 归一化到 0-100
        min_energy = np.min(band_energy)
        max_energy = np.max(band_energy)
        energy_range = max_energy - min_energy

        if energy_range > 0:
            normalized = (band_energy - min_energy) / energy_range * 100
        else:
            normalized = np.ones_like(band_energy) * 50

        # 转换为帧时间关键帧
        frame_times = librosa.frames_to_time(range(len(band_energy)), sr=sr, hop_length=hop_length)

        keyframes = []
        for i, (t, val) in enumerate(zip(frame_times, normalized)):
            keyframes.append({
                "time": round(float(t), 3),
                "frame": int(t * frame_rate),
                "value": round(float(val), 2),
                "normalized_value": round(float(normalized[i]) / 100, 4),
                "raw_energy": round(float(band_energy[i]), 6),
            })

        return keyframes

    async def apply_beat_keyframe_template(
        self,
        comp_name: str,
        layer_index: int,
        property_path: str,
        beat_type: str,
        beat_times: List[float],
        base_value: float = 100.0,
        amplitude: float = 20.0,
    ) -> EngineResult:
        """应用节拍关键帧模板.

        强拍模板（strong_beat）: 5 关键帧
            - prep: 准备帧（beat_time - 0.05s）
            - impact: 冲击帧（beat_time）
            - bounce: 回弹帧（beat_time + 0.03s）
            - release: 释放帧（beat_time + 0.1s）
            - restore: 恢复帧（beat_time + 0.2s）

        弱拍模板（weak_beat）: 2 关键帧
            - breathing: 呼吸式关键帧（beat_time, beat_time + beat_interval/2）

        Args:
            comp_name: 合成名称
            layer_index: 图层索引
            property_path: 属性路径（如 "Transform.Scale" 或 "Effects.Glow.Intensity"）
            beat_type: 节拍类型 (strong_beat | weak_beat)
            beat_times: 节拍时间点列表
            base_value: 基准值
            amplitude: 振幅

        Returns:
            EngineResult: 执行结果
        """
        logger.info(
            f"[AudioBinding] 应用节拍模板: {beat_type} → {property_path}, "
            f"{len(beat_times)} beats"
        )

        if beat_type not in ["strong_beat", "weak_beat"]:
            return EngineResult(
                success=False,
                error=f"无效节拍类型: {beat_type}，可选值: strong_beat/weak_beat"
            )

        # 生成关键帧数据
        keyframes = self._generate_beat_keyframes(
            beat_type, beat_times, base_value, amplitude
        )

        # ExtendScript: 应用关键帧
        script = self._build_keyframe_script(
            comp_name, layer_index, property_path, keyframes
        )

        result = await self.ae_engine.run_script(script)

        if result.success:
            logger.success(
                f"[AudioBinding] 节拍关键帧应用成功: {len(keyframes)} 帧"
            )
        else:
            logger.error(f"[AudioBinding] 节拍关键帧应用失败: {result.error}")

        return result

    def _generate_beat_keyframes(
        self,
        beat_type: str,
        beat_times: List[float],
        base_value: float,
        amplitude: float,
    ) -> List[Dict[str, Any]]:
        """生成节拍关键帧数据.

        Args:
            beat_type: 节拍类型
            beat_times: 节拍时间点
            base_value: 基准值
            amplitude: 振幅

        Returns:
            List[Dict]: 关键帧数据
        """
        keyframes = []

        if beat_type == "strong_beat":
            # 强拍：5 关键帧模板
            for beat_time in beat_times:
                # 1. prep: 准备帧（略微收缩）
                keyframes.append({
                    "time": round(beat_time - 0.05, 3),
                    "value": round(base_value - amplitude * 0.2, 2),
                    "ease_type": "easeIn",
                })

                # 2. impact: 冲击帧（峰值）
                keyframes.append({
                    "time": round(beat_time, 3),
                    "value": round(base_value + amplitude, 2),
                    "ease_type": "easeOut",
                })

                # 3. bounce: 回弹帧
                keyframes.append({
                    "time": round(beat_time + 0.03, 3),
                    "value": round(base_value + amplitude * 0.7, 2),
                    "ease_type": "easeInOut",
                })

                # 4. release: 释放帧
                keyframes.append({
                    "time": round(beat_time + 0.1, 3),
                    "value": round(base_value - amplitude * 0.1, 2),
                    "ease_type": "easeInOut",
                })

                # 5. restore: 恢复帧
                keyframes.append({
                    "time": round(beat_time + 0.2, 3),
                    "value": round(base_value, 2),
                    "ease_type": "easeOut",
                })

        elif beat_type == "weak_beat":
            # 弱拍：2 关键帧呼吸模板
            for beat_time in beat_times:
                # 呼吸式动画：上升 → 下降
                keyframes.append({
                    "time": round(beat_time, 3),
                    "value": round(base_value + amplitude * 0.3, 2),
                    "ease_type": "easeOut",
                })

                # 计算下一个节拍时间（假设 120 BPM，间隔 0.5s）
                next_beat = beat_time + 0.25  # 半拍间隔
                keyframes.append({
                    "time": round(next_beat, 3),
                    "value": round(base_value, 2),
                    "ease_type": "easeIn",
                })

        # 按时间排序
        keyframes.sort(key=lambda x: x["time"])

        return keyframes

    def _build_keyframe_script(
        self,
        comp_name: str,
        layer_index: int,
        property_path: str,
        keyframes: List[Dict[str, Any]],
    ) -> str:
        """构建关键帧应用脚本.

        Args:
            comp_name: 合成名称
            layer_index: 图层索引
            property_path: 属性路径
            keyframes: 关键帧数据

        Returns:
            str: ExtendScript 脚本
        """
        # 解析属性路径
        path_parts = property_path.split(".")
        if len(path_parts) == 1:
            # Transform 属性（Scale/Rotation/Opacity）
            prop_access = f'layer.property("{path_parts[0]}")'
        else:
            # 效果属性（Effects.Glow.Intensity）
            effect_name = path_parts[1] if len(path_parts) > 1 else path_parts[0]
            prop_name = path_parts[-1]
            prop_access = f'layer.effect("{effect_name}").property("{prop_name}")'

        # 构建 JSON 数据
        kf_json = json.dumps(keyframes)

        script = f'''
var compName = "{comp_name}";
var layerIdx = {layer_index};
var kfData = {kf_json};

var comp = null;
for (var i = 1; i <= app.project.numItems; i++) {{
    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {{
        comp = app.project.item(i);
        break;
    }}
}}

if (!comp) {{
    "ERROR: Comp not found";
}} else {{
    var layer = comp.layer(layerIdx);
    if (!layer) {{
        "ERROR: Layer not found";
    }} else {{
        var prop = {prop_access};
        if (!prop) {{
            "ERROR: Property not found: {property_path}";
        }} else {{
            var written = 0;
            for (var k = 0; k < kfData.length; k++) {{
                var kf = kfData[k];
                prop.setValueAtTime(kf.time, kf.value);

                // 应用缓动
                if (kf.ease_type !== "linear") {{
                    var idx = prop.nearestKeyIndex(kf.time);
                    if (idx > 0) {{
                        var eIn = new KeyframeEase(0, 33);
                        var eOut = new KeyframeEase(0, 33);

                        if (kf.ease_type === "easeIn") {{
                            eIn = new KeyframeEase(0, 75);
                        }} else if (kf.ease_type === "easeOut") {{
                            eOut = new KeyframeEase(0, 75);
                        }} else if (kf.ease_type === "easeInOut") {{
                            eIn = new KeyframeEase(0, 75);
                            eOut = new KeyframeEase(0, 75);
                        }}

                        try {{
                            prop.setTemporalEaseAtKey(idx, [eIn], [eOut]);
                        }} catch(ex) {{}}
                    }}
                }}
                written++;
            }}
            "SUCCESS: Written " + written + " keyframes to " + "{property_path}";
        }}
    }}
}}
'''
        return script

    async def create_v4_binding_preset(self, comp_name: str) -> Dict[str, EngineResult]:
        """创建 V4 推荐绑定预设.

        V4 推荐绑定规则：
        - Glow → 高频能量（High 频段）
        - Opacity → 全局能量 + 正弦波调制（Global 频段）
        - Rotation → 全局能量 + 正弦波调制（Global 频段）

        Args:
            comp_name: 合成名称

        Returns:
            Dict[str, EngineResult]: 各绑定结果
        """
        logger.info(f"[AudioBinding] 创建 V4 绑定预设: {comp_name}")

        results = {}

        # 1. 创建 Audio Controller
        controller_result = await self.create_audio_controller(comp_name)
        results["audio_controller"] = controller_result

        if not controller_result.success:
            logger.error("[AudioBinding] Audio Controller 创建失败，终止预设绑定")
            return results

        # 2. Glow → 高频能量
        glow_result = await self.bind_effect_to_frequency(
            comp_name=comp_name,
            layer_index=1,  # 假设目标图层为第 1 层
            effect_name="Glow",
            property_name="Glow Intensity",
            frequency_band="high",
            expression_modifiers={"scale": 100, "clamp_min": 0, "clamp_max": 200}
        )
        results["glow_to_high"] = glow_result

        # 3. Opacity → 全局能量 + 正弦波
        opacity_result = await self.bind_effect_to_frequency(
            comp_name=comp_name,
            layer_index=1,
            effect_name="Transform",
            property_name="Opacity",
            frequency_band="global",
            expression_modifiers={"scale": 0.3, "offset": 70, "sine_freq": 2.0, "clamp_min": 50, "clamp_max": 100}
        )
        results["opacity_to_global"] = opacity_result

        # 4. Rotation → 全局能量 + 正弦波
        rotation_result = await self.bind_effect_to_frequency(
            comp_name=comp_name,
            layer_index=1,
            effect_name="Transform",
            property_name="Rotation",
            frequency_band="global",
            expression_modifiers={"scale": 0.2, "sine_freq": 1.5, "clamp_min": -30, "clamp_max": 30}
        )
        results["rotation_to_global"] = rotation_result

        logger.success(f"[AudioBinding] V4 预设绑定完成: {len([r for r in results.values() if r.success])} 成功")
        return results

    async def analyze_and_generate_all_bands(
        self,
        audio_path: Path,
        frame_rate: float = 30.0,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """分析音频并生成所有频段的关键帧数据.

        Args:
            audio_path: 音频文件路径
            frame_rate: 帧率

        Returns:
            Dict[str, List]: 各频段关键帧数据 {global: [...], low: [...], mid: [...], high: [...]}
        """
        logger.info(f"[AudioBinding] 分析所有频段: {audio_path.name}")

        results = {}
        for band_name in FREQUENCY_BANDS.keys():
            keyframes = await self.generate_audio_keyframes(
                audio_path=audio_path,
                frequency_band=band_name,
                frame_rate=frame_rate
            )
            results[band_name] = keyframes

        logger.success(
            f"[AudioBinding] 全频段分析完成: {', '.join(f'{k}={len(v)}帧' for k, v in results.items())}"
        )
        return results
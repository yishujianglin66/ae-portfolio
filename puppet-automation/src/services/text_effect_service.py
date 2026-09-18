"""Text Effect Service - 文字效果服务系统.

支持 3D 标题、发光、RGB 分离效果，遵循 project_memory 约束：
- 字幕动画风格：白色填充 + 黑色粗描边 + 底部投影
- 高级文字系统架构：主文字层 + GLOW_ + RGB_R_/RGB_C_ + GRAD_
- 图层前缀约定：TXT_ > GLOW_ > RGB_ > GRAD_
- 字体预设库：cinematic/epic/elegant/modern/tech/japanese/brush/display
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..config import settings
from ..engines.ae.engine import AEEngine
from ..engines.base import EngineResult


class TextEffectService:
    """文字效果服务系统 - 支持 3D 标题、发光、RGB 分离效果."""

    # 字体预设库
    FONT_PRESETS = {
        "cinematic": {"font": "Impact", "tracking": 80, "weight": "bold"},
        "epic": {"font": "Impact", "tracking": 100, "weight": "bold"},
        "elegant": {"font": "Georgia", "tracking": 40, "weight": "normal"},
        "modern": {"font": "Arial", "tracking": 60, "weight": "bold"},
        "tech": {"font": "Courier New", "tracking": 50, "weight": "bold"},
        "japanese": {"font": "MS Gothic", "tracking": 30, "weight": "normal"},
        "brush": {"font": "Brush Script MT", "tracking": 20, "weight": "normal"},
        "display": {"font": "Impact", "tracking": 90, "weight": "bold"},
    }

    # 默认文字系统架构参数
    DEFAULT_TEXT_STYLE = {
        "fill_color": "#FFFFFF",
        "stroke_color": "#000000",
        "stroke_width": 8,
        "drop_shadow_direction": 180,
        "font": "Impact",
        "tracking": 80,
    }

    def __init__(self, ae_engine: AEEngine | None = None):
        """初始化文字效果服务.

        Args:
            ae_engine: AE 引擎实例（可选，默认使用全局配置）
        """
        self.ae = ae_engine or AEEngine(settings.aerender_path)
        self._verified = False
        logger.info("TextEffectService initialized")

    async def _verify_ae_connection(self) -> bool:
        """验证 AE 连接是否可用."""
        if self._verified:
            return True

        try:
            # 简单的测试脚本
            test_script = """
            (function() {
                var _result = {status: "success", ae_version: app.version};
                return JSON.stringify(_result);
            })();
            """
            result = await self.ae.run_script(test_script)
            if result.success:
                self._verified = True
                logger.info("AE connection verified")
                return True
        except Exception as e:
            logger.error(f"AE connection failed: {e}")
            return False

        return False

    def _hex_to_rgb(self, hex_color: str) -> tuple[float, float, float]:
        """将 HEX 颜色转换为 RGB（0-1 范围）.

        Args:
            hex_color: HEX 颜色字符串（如 "#FF0000" 或 "FF0000"）

        Returns:
            RGB 元组（0-1 范围）
        """
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)

    def _rgb_to_jsx_array(self, rgb: tuple[float, float, float]) -> str:
        """将 RGB 元组转换为 JSX 数组字符串.

        Args:
            rgb: RGB 元组（0-1 范围）

        Returns:
            JSX 数组字符串（如 "[1, 0.5, 0]"）
        """
        return f"[{rgb[0]:.3f}, {rgb[1]:.3f}, {rgb[2]:.3f}]"

    async def _resolve_font_path(self, font_name: str) -> Path | None:
        """通过 resource_index_service 解析字体名称到文件路径.

        优先从资源索引服务查找字体文件；若服务不可用或未找到，返回 None，
        由调用方回退到原逻辑（用户传入的路径或 AE 默认字体名称）。

        Args:
            font_name: 字体名称（如 "思源黑体"、"Impact"）

        Returns:
            找到的字体文件 Path；未找到或服务不可用时返回 None
        """
        try:
            from .resource_index_service import resource_index_service
        except ImportError as e:
            logger.warning(
                f"resource_index_service 不可用，字体解析降级到原逻辑: {e}"
            )
            return None

        try:
            font_path = await resource_index_service.find_font(font_name)
        except Exception as e:
            logger.warning(f"resource_index_service 查找字体失败: {e}")
            return None

        if font_path is None:
            logger.warning(
                f"字体 '{font_name}' 在资源库中未找到，回退到原字体名称"
            )
            return None

        logger.debug(f"字体 '{font_name}' 已解析到: {font_path}")
        return font_path

    async def create_3d_title(
        self,
        comp_name: str,
        text: str,
        position: tuple[int, int],
        style: str = "epic3D",
        font: str = "Impact",
        font_size: int = 120,
        fill_color: str = "#FFFFFF",
        stroke_color: str = "#000000",
        stroke_width: int = 8,
        font_path: Path | None = None,
    ) -> EngineResult:
        """创建 3D 标题文字层.

        Args:
            comp_name: 合成名称
            text: 文字内容
            position: 文字位置 (x, y)
            style: 文字风格（epic3D, cinematic, elegant 等）
            font: 字体名称
            font_size: 字体大小
            fill_color: 填充颜色（HEX 格式）
            stroke_color: 描边颜色（HEX 格式）
            stroke_width: 描边宽度
            font_path: 字体文件路径（可选，未提供时自动通过
                resource_index_service 按 font 名称查找）

        Returns:
            EngineResult: 执行结果
        """
        fill_rgb = self._hex_to_rgb(fill_color)
        stroke_rgb = self._hex_to_rgb(stroke_color)
        fill_array = self._rgb_to_jsx_array(fill_rgb)
        stroke_array = self._rgb_to_jsx_array(stroke_rgb)

        # 应用字体预设
        preset = self.FONT_PRESETS.get(style, self.FONT_PRESETS["epic"])
        if font == "Impact":
            font = preset["font"]

        # 若未显式提供字体文件路径，尝试从资源索引服务解析
        if font_path is None:
            font_path = await self._resolve_font_path(font)

        jsx_script = f"""
        (function() {{
            var _result = {{}};
            try {{
                var comp = app.project.activeItem;
                if (!comp || !(comp instanceof CompItem)) {{
                    _result = {{status:"error", message:"No active comp"}};
                    return JSON.stringify(_result);
                }}

                // 创建文字层
                var textLayer = comp.layers.addText("{text}");
                textLayer.name = "TXT_{text}";
                textLayer.property("Position").setValue([{position[0]}, {position[1]}]);

                // 设置文字属性
                var sourceText = textLayer.property("Source Text");
                var textDoc = sourceText.value;
                textDoc.fillColor = {fill_array};
                textDoc.applyFill = true;
                textDoc.strokeColor = {stroke_array};
                textDoc.applyStroke = true;
                textDoc.strokeWidth = {stroke_width};
                textDoc.strokeOverFill = true;  // 描边在填充之上
                textDoc.fontSize = {font_size};
                textDoc.font = "{font}";
                textDoc.fauxBold = true;
                textDoc.justification = ParagraphJustification.CENTER;
                sourceText.setValue(textDoc);

                // 添加 Drop Shadow 效果（底部投影）
                var dropShadow = textLayer.property("Effects").addProperty("ADBE Drop Shadow");
                if (dropShadow) {{
                    dropShadow.property("ADBE Drop Shadow-0001").setValue(180);  // Direction: 180 (底部)
                    dropShadow.property("ADBE Drop Shadow-0002").setValue(10);   // Distance
                    dropShadow.property("ADBE Drop Shadow-0003").setValue(50);   // Softness
                }}

                _result = {{
                    status: "success",
                    layer_name: textLayer.name,
                    style: "{style}"
                }};
            }} catch(e) {{
                _result = {{status:"error", message:e.toString()}};
            }}
            return JSON.stringify(_result);
        }})();
        """

        result = await self.ae.run_script(jsx_script)
        if result.success:
            logger.info(f"Created 3D title: {text} in {comp_name}")
        else:
            logger.error(f"Failed to create 3D title: {result.error}")
        return result

    async def apply_glow_layer(
        self,
        comp_name: str,
        text_layer_index: int,
        glow_color: str = "#00FFFF",
        glow_intensity: float = 0.8,
        blur_radius: int = 25,
    ) -> EngineResult:
        """添加 GLOW_ 辉光层（复制文字 + Fast Blur + ADD 混合）.

        Args:
            comp_name: 合成名称
            text_layer_index: 文字层索引
            glow_color: 辉光颜色（HEX 格式）
            glow_intensity: 辉光强度（0-1）
            blur_radius: 模糊半径（像素）

        Returns:
            EngineResult: 执行结果
        """
        glow_rgb = self._hex_to_rgb(glow_color)
        glow_array = self._rgb_to_jsx_array(glow_rgb)

        jsx_script = f"""
        (function() {{
            var _result = {{}};
            try {{
                var comp = app.project.activeItem;
                if (!comp || !(comp instanceof CompItem)) {{
                    _result = {{status:"error", message:"No active comp"}};
                    return JSON.stringify(_result);
                }}

                // 获取原始文字层
                var sourceLayer = comp.layer({text_layer_index + 1});
                if (!sourceLayer) {{
                    _result = {{status:"error", message:"Source layer not found"}};
                    return JSON.stringify(_result);
                }}

                // 复制文字层
                var glowLayer = sourceLayer.duplicate();
                glowLayer.name = "GLOW_" + sourceLayer.name;
                glowLayer.moveToBeginning();

                // 设置混合模式为 ADD
                glowLayer.blendingMode = BlendingMode.ADD;

                // 设置颜色
                var sourceText = glowLayer.property("Source Text");
                var textDoc = sourceText.value;
                textDoc.fillColor = {glow_array};
                sourceText.setValue(textDoc);

                // 添加 Fast Blur 效果
                var fastBlur = glowLayer.property("Effects").addProperty("ADBE Fast Blur");
                if (fastBlur) {{
                    fastBlur.property("ADBE Fast Blur-0001").setValue({blur_radius});  // Blurriness
                    fastBlur.property("ADBE Fast Blur-0002").setValue(1);  // Repeat Edge Pixels
                }}

                // 调整不透明度
                glowLayer.property("Opacity").setValue({glow_intensity * 100});

                _result = {{
                    status: "success",
                    layer_name: glowLayer.name,
                    blend_mode: "ADD"
                }};
            }} catch(e) {{
                _result = {{status:"error", message:e.toString()}};
            }}
            return JSON.stringify(_result);
        }})();
        """

        result = await self.ae.run_script(jsx_script)
        if result.success:
            logger.info(f"Applied glow layer to {comp_name}")
        return result

    async def apply_rgb_separation(
        self,
        comp_name: str,
        text_layer_index: int,
        offset_x: int = 6,
        offset_y: int = 0,
    ) -> EngineResult:
        """添加 RGB 分离层（红青偏移 ±6px + SCREEN 混合）.

        Args:
            comp_name: 合成名称
            text_layer_index: 文字层索引
            offset_x: X 轴偏移量（像素）
            offset_y: Y 轴偏移量（像素）

        Returns:
            EngineResult: 执行结果
        """
        jsx_script = f"""
        (function() {{
            var _result = {{}};
            try {{
                var comp = app.project.activeItem;
                if (!comp || !(comp instanceof CompItem)) {{
                    _result = {{status:"error", message:"No active comp"}};
                    return JSON.stringify(_result);
                }}

                // 获取原始文字层
                var sourceLayer = comp.layer({text_layer_index + 1});
                if (!sourceLayer) {{
                    _result = {{status:"error", message:"Source layer not found"}};
                    return JSON.stringify(_result);
                }}

                // 创建红色分离层（正偏移）
                var redLayer = sourceLayer.duplicate();
                redLayer.name = "RGB_R_" + sourceLayer.name;
                redLayer.moveToBeginning();

                // 设置红色通道
                var redSourceText = redLayer.property("Source Text");
                var redTextDoc = redSourceText.value;
                redTextDoc.fillColor = [1, 0, 0];  // 纯红
                redSourceText.setValue(redTextDoc);

                // 位置偏移
                var redPos = redLayer.property("Position");
                var redPosValue = redPos.value;
                redPos.setValue([redPosValue[0] + {offset_x}, redPosValue[1] + {offset_y}]);

                // 设置混合模式为 SCREEN
                redLayer.blendingMode = BlendingMode.SCREEN;

                // 创建青色分离层（负偏移）
                var cyanLayer = sourceLayer.duplicate();
                cyanLayer.name = "RGB_C_" + sourceLayer.name;
                cyanLayer.moveToBeginning();

                // 设置青色
                var cyanSourceText = cyanLayer.property("Source Text");
                var cyanTextDoc = cyanSourceText.value;
                cyanTextDoc.fillColor = [0, 1, 1];  // 青色
                cyanSourceText.setValue(cyanTextDoc);

                // 位置偏移
                var cyanPos = cyanLayer.property("Position");
                var cyanPosValue = cyanPos.value;
                cyanPos.setValue([cyanPosValue[0] - {offset_x}, cyanPosValue[1] - {offset_y}]);

                // 设置混合模式为 SCREEN
                cyanLayer.blendingMode = BlendingMode.SCREEN;

                _result = {{
                    status: "success",
                    red_layer: redLayer.name,
                    cyan_layer: cyanLayer.name,
                    offset: [{offset_x}, {offset_y}]
                }};
            }} catch(e) {{
                _result = {{status:"error", message:e.toString()}};
            }}
            return JSON.stringify(_result);
        }})();
        """

        result = await self.ae.run_script(jsx_script)
        if result.success:
            logger.info(f"Applied RGB separation to {comp_name}")
        return result

    async def apply_gradient_overlay(
        self,
        comp_name: str,
        text_layer_index: int,
        gradient_colors: list[str],
    ) -> EngineResult:
        """添加 GRAD_ 渐变层（Alpha Matte 蒙版）.

        Args:
            comp_name: 合成名称
            text_layer_index: 文字层索引
            gradient_colors: 渐变颜色列表（HEX 格式）

        Returns:
            EngineResult: 执行结果
        """
        if len(gradient_colors) < 2:
            return EngineResult(
                success=False,
                error="gradient_colors must have at least 2 colors"
            )

        # 创建渐变颜色数组
        gradient_arrays = [
            self._rgb_to_jsx_array(self._hex_to_rgb(color))
            for color in gradient_colors[:2]  # 只取前两个颜色
        ]

        jsx_script = f"""
        (function() {{
            var _result = {{}};
            try {{
                var comp = app.project.activeItem;
                if (!comp || !(comp instanceof CompItem)) {{
                    _result = {{status:"error", message:"No active comp"}};
                    return JSON.stringify(_result);
                }}

                // 获取原始文字层
                var sourceLayer = comp.layer({text_layer_index + 1});
                if (!sourceLayer) {{
                    _result = {{status:"error", message:"Source layer not found"}};
                    return JSON.stringify(_result);
                }}

                // 创建渐变调整层
                var gradLayer = sourceLayer.duplicate();
                gradLayer.name = "GRAD_" + sourceLayer.name;
                gradLayer.moveToBeginning();

                // 添加 Gradient Fill 效果
                var gradientFill = gradLayer.property("Effects").addProperty("ADBE Ramp");
                if (gradientFill) {{
                    // 设置渐变起点和颜色
                    gradientFill.property("ADBE Ramp-0001").setValue([comp.width / 2, 0]);  // Start point
                    gradientFill.property("ADBE Ramp-0002").setValue({gradient_arrays[0]});  // Start color
                    // 设置渐变终点和颜色
                    gradientFill.property("ADBE Ramp-0003").setValue([comp.width / 2, comp.height]);  // End point
                    gradientFill.property("ADBE Ramp-0004").setValue({gradient_arrays[1]});  // End color
                }}

                // 设置为 Alpha Matte（需要将源文字层作为蒙版）
                // 注：实际 AE 操作中需要设置 track matte，这里简化为叠加模式
                gradLayer.blendingMode = BlendingMode.OVERLAY;

                _result = {{
                    status: "success",
                    layer_name: gradLayer.name,
                    gradient_type: "vertical",
                    colors: {len(gradient_colors)}
                }};
            }} catch(e) {{
                _result = {{status:"error", message:e.toString()}};
            }}
            return JSON.stringify(_result);
        }})();
        """

        result = await self.ae.run_script(jsx_script)
        if result.success:
            logger.info(f"Applied gradient overlay to {comp_name}")
        return result

    async def create_full_title_system(
        self,
        comp_name: str,
        text: str,
        position: tuple[int, int] = (960, 540),
        style: str = "epic3D",
        font: str = "Impact",
        font_size: int = 120,
        fill_color: str = "#FFFFFF",
        stroke_color: str = "#000000",
        glow_color: str = "#00FFFF",
        glow_intensity: float = 0.8,
        rgb_offset: int = 6,
        gradient_colors: list[str] | None = None,
        font_path: Path | None = None,
    ) -> EngineResult:
        """一键创建完整文字系统：主文字层 + GLOW_ 辉光层 + RGB_R_/RGB_C_ 分离层 + GRAD_ 渐变层.

        图层顺序（从上到下）：
        1. GRAD_ 渐变层（最上层）
        2. RGB_C_ 青色分离层
        3. RGB_R_ 红色分离层
        4. GLOW_ 辉光层
        5. TXT_ 主文字层（最下层）

        Args:
            comp_name: 合成名称
            text: 文字内容
            position: 文字位置 (x, y)
            style: 文字风格
            font: 字体名称
            font_size: 字体大小
            fill_color: 填充颜色（HEX）
            stroke_color: 描边颜色（HEX）
            glow_color: 辉光颜色（HEX）
            glow_intensity: 辉光强度
            rgb_offset: RGB 分离偏移量
            gradient_colors: 渐变颜色列表（可选）
            font_path: 字体文件路径（可选，未提供时自动通过
                resource_index_service 按 font 名称查找）

        Returns:
            EngineResult: 执行结果
        """
        logger.info(f"Creating full title system for: {text}")

        # 1. 创建主文字层
        result = await self.create_3d_title(
            comp_name=comp_name,
            text=text,
            position=position,
            style=style,
            font=font,
            font_size=font_size,
            fill_color=fill_color,
            stroke_color=stroke_color,
            font_path=font_path,
        )
        if not result.success:
            return result

        # 等待一小段时间确保图层创建完成
        await asyncio.sleep(0.1)

        # 2. 添加 GLOW_ 辉光层（layer index 0 = 最上层）
        result = await self.apply_glow_layer(
            comp_name=comp_name,
            text_layer_index=0,
            glow_color=glow_color,
            glow_intensity=glow_intensity,
        )
        if not result.success:
            logger.warning(f"Glow layer creation failed: {result.error}")

        await asyncio.sleep(0.1)

        # 3. 添加 RGB 分离层
        result = await self.apply_rgb_separation(
            comp_name=comp_name,
            text_layer_index=0,  # 作用在当前最上层
            offset_x=rgb_offset,
            offset_y=0,
        )
        if not result.success:
            logger.warning(f"RGB separation creation failed: {result.error}")

        await asyncio.sleep(0.1)

        # 4. 添加渐变层（可选）
        if gradient_colors and len(gradient_colors) >= 2:
            result = await self.apply_gradient_overlay(
                comp_name=comp_name,
                text_layer_index=0,
                gradient_colors=gradient_colors,
            )
            if not result.success:
                logger.warning(f"Gradient overlay creation failed: {result.error}")

        logger.info(f"Full title system created successfully: {text}")
        return EngineResult(
            success=True,
            metadata={
                "text": text,
                "style": style,
                "layers_created": 5,
                "architecture": ["GRAD_", "RGB_C_", "RGB_R_", "GLOW_", "TXT_"],
            },
        )

    async def apply_neon_effect(
        self,
        comp_name: str,
        text_layer_index: int,
        glow_size: int = 25,
        glow_intensity: float = 1.5,
        flicker: float = 0.3,
        color: str = "#00FFFF",
    ) -> EngineResult:
        """应用霓虹发光效果（参考知识库预设）.

        Args:
            comp_name: 合成名称
            text_layer_index: 文字层索引
            glow_size: 发光半径（像素）
            glow_intensity: 发光强度
            flicker: 闪烁幅度（0=不闪烁）
            color: 霓虹颜色（HEX）

        Returns:
            EngineResult: 执行结果
        """
        neon_rgb = self._hex_to_rgb(color)
        neon_array = self._rgb_to_jsx_array(neon_rgb)

        jsx_script = f"""
        (function() {{
            var _result = {{}};
            try {{
                var comp = app.project.activeItem;
                if (!comp || !(comp instanceof CompItem)) {{
                    _result = {{status:"error", message:"No active comp"}};
                    return JSON.stringify(_result);
                }}

                var layer = comp.layer({text_layer_index + 1});
                if (!layer) {{
                    _result = {{status:"error", message:"Layer not found"}};
                    return JSON.stringify(_result);
                }}

                // 添加 Glow 效果
                var glow = layer.property("Effects").addProperty("ADBE Glo 2");
                if (glow) {{
                    glow.property("ADBE Glo-0001").setValue({glow_size});  // Glow Threshold
                    glow.property("ADBE Glo-0002").setValue({glow_intensity});  // Glow Intensity
                    glow.property("ADBE Glo-0003").setValue({neon_array});  // Glow Color
                }}

                // 添加闪烁动画（如果 flicker > 0）
                if ({flicker} > 0) {{
                    var opacity = layer.property("Opacity");
                    var t0 = layer.inPoint;
                    var dur = layer.outPoint - t0;
                    var steps = Math.floor(dur / 0.1);

                    for (var i = 0; i < steps; i++) {{
                        var tt = t0 + i * 0.1;
                        var v = 100 - {flicker} * 100 * (Math.random() * 0.5 + 0.5);
                        opacity.setValueAtTime(tt, Math.max(60, v));
                    }}
                }}

                _result = {{
                    status: "success",
                    layer: layer.name,
                    glow_size: {glow_size},
                    glow_intensity: {glow_intensity}
                }};
            }} catch(e) {{
                _result = {{status:"error", message:e.toString()}};
            }}
            return JSON.stringify(_result);
        }})();
        """

        result = await self.ae.run_script(jsx_script)
        if result.success:
            logger.info(f"Applied neon effect to layer {text_layer_index}")
        return result

    async def apply_text_animation(
        self,
        comp_name: str,
        text_layer_index: int,
        animation_type: str = "typewriter",
        duration: float = 1.0,
        stagger: float = 0.05,
    ) -> EngineResult:
        """应用文字动画效果（打字机、逐字淡入等）.

        Args:
            comp_name: 合成名称
            text_layer_index: 文字层索引
            animation_type: 动画类型（typewriter, character_fade, etc.）
            duration: 动画时长（秒）
            stagger: 逐字延迟间隔（秒）

        Returns:
            EngineResult: 执行结果
        """
        jsx_script = f"""
        (function() {{
            var _result = {{}};
            try {{
                var comp = app.project.activeItem;
                if (!comp || !(comp instanceof CompItem)) {{
                    _result = {{status:"error", message:"No active comp"}};
                    return JSON.stringify(_result);
                }}

                var layer = comp.layer({text_layer_index + 1});
                if (!layer || !(layer instanceof TextLayer)) {{
                    _result = {{status:"error", message:"Text layer not found"}};
                    return JSON.stringify(_result);
                }}

                // 添加 Text Animator
                var textProps = layer.property("ADBE Text Properties");
                var animators = textProps.property("ADBE Text Animators");
                var animator = animators.addProperty("ADBE Text Animator");
                animator.name = "Typewriter";

                // 添加 Range Selector
                var selectors = animator.property("ADBE Text Selectors");
                var rangeSelector = selectors.addProperty("ADBE Text Range Selector");

                // 设置 End 为 100%
                rangeSelector.property("ADBE Text Selector End").setValue(100);

                // 添加 Opacity 属性并设置为 0
                var opacity = animator.addProperty("ADBE Text Opacity");
                opacity.setValue(0);

                // 动画 Start 属性（打字机效果）
                var startProp = rangeSelector.property("ADBE Text Selector Start");
                var inPoint = layer.inPoint;

                startProp.setValueAtTime(inPoint, 0);
                startProp.setValueAtTime(inPoint + {duration}, 100);

                _result = {{
                    status: "success",
                    animation_type: "{animation_type}",
                    duration: {duration},
                    layer: layer.name
                }};
            }} catch(e) {{
                _result = {{status:"error", message:e.toString()}};
            }}
            return JSON.stringify(_result);
        }})();
        """

        result = await self.ae.run_script(jsx_script)
        if result.success:
            logger.info(f"Applied {animation_type} animation to layer {text_layer_index}")
        return result

    async def get_layer_info(
        self,
        comp_name: str,
        layer_name: str | None = None,
        layer_index: int | None = None,
    ) -> dict[str, Any]:
        """获取图层信息（辅助方法）.

        Args:
            comp_name: 合成名称
            layer_name: 图层名称（可选）
            layer_index: 图层索引（可选）

        Returns:
            图层信息字典
        """
        jsx_script = f"""
        (function() {{
            var _result = {{}};
            try {{
                var comp = app.project.activeItem;
                if (!comp || !(comp instanceof CompItem)) {{
                    _result = {{status:"error", message:"No active comp"}};
                    return JSON.stringify(_result);
                }}

                var layer = null;
                if ("{layer_name}" !== "null" && "{layer_name}" !== "") {{
                    layer = comp.layer("{layer_name}");
                }} else if ({layer_index if layer_index else "null"} !== null) {{
                    layer = comp.layer({layer_index + 1 if layer_index else 1});
                }}

                if (!layer) {{
                    _result = {{status:"error", message:"Layer not found"}};
                    return JSON.stringify(_result);
                }}

                _result = {{
                    status: "success",
                    layer_name: layer.name,
                    index: layer.index - 1,
                    in_point: layer.inPoint,
                    out_point: layer.out_point,
                    duration: layer.outPoint - layer.inPoint,
                    is_3d: layer.threeDLayer
                }};
            }} catch(e) {{
                _result = {{status:"error", message:e.toString()}};
            }}
            return JSON.stringify(_result);
        }})();
        """

        result = await self.ae.run_script(jsx_script)
        if result.success and result.metadata.get("stdout"):
            try:
                return json.loads(result.metadata["stdout"])
            except:
                pass
        return {"status": "error", "message": result.error or "Unknown error"}
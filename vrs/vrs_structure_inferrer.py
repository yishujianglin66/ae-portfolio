#!/usr/bin/env python3
"""
VRS 合成结构推断引擎 v2.0
========================

基于 THINKING 模型推理视频的图层堆栈结构，是 VRS (Video Reverse-engineering System)
v2.0 项目的核心模块之一。

核心能力：
1. 接收视频效果分析结果（含调色、运动、节奏、视觉特效）
2. 通过 core.llm_gateway 调用 EFFECT_PLANNING 任务，路由到 PRO/THINKING 模型
3. 输出完整的合成结构蓝图（图层、预合成、摄像机、灯光）
4. 将蓝图转换为原子操作序列（create_comp / add_layer / set_blend_mode 等）

使用示例：
    from vrs.vrs_structure_inferrer import CompositionStructureInferrer

    inferrer = CompositionStructureInferrer()
    blueprint = await inferrer.infer_structure(analysis_result)
    operations = blueprint["operations"]

依赖：
- core.llm_gateway （LLM 网关）
- loguru （日志）
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# 项目内导入（带降级）
try:
    from core.llm_gateway import LLMResponse, TaskType, chat_with_routing
    _LLM_AVAILABLE = True
except ImportError:
    logger.warning("core.llm_gateway 不可用，结构推断将降级为规则模式")
    _LLM_AVAILABLE = False

    class TaskType:  # type: ignore[no-redef]
        """降级占位 TaskType"""
        EFFECT_PLANNING = "effect_planning"

    class LLMResponse:  # type: ignore[no-redef]
        """降级占位 LLMResponse"""
        pass


# =============================================================================
# 常量定义
# =============================================================================

# 支持的图层类型（共 7 种）
SUPPORTED_LAYER_TYPES: set[str] = {
    "footage",      # 素材层
    "adjustment",   # 调整层
    "precomp",      # 预合成层
    "text",         # 文字层
    "shape",        # 形状层
    "null",         # 空对象层
    "solid",        # 固态层
}

# 支持的混合模式（与 mcp-extension/new-tools-inline.ts 对齐）
SUPPORTED_BLEND_MODES: set[str] = {
    "NONE", "NORMAL", "DISSOLVE", "MULTIPLY", "SCREEN", "OVERLAY",
    "SOFT_LIGHT", "HARD_LIGHT", "ADD", "COLOR_DODGE", "COLOR_BURN",
    "DARKEN", "LIGHTEN", "DIFFERENCE", "EXCLUSION",
    "HUE", "SATURATION", "COLOR", "LUMINOSITY",
}

# 默认合成参数
DEFAULT_COMP: dict[str, Any] = {
    "name": "复现_参考视频",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "duration": 10.0,
}

# 系统提示词（写入 LLM 上下文，包含结构推断方法论）
SYSTEM_PROMPT: str = """你是 AE 合成结构推断专家，擅长从视频效果分析结果反向推导出 After Effects 工程的图层堆栈结构。

【分层原则】
- 全局调色 → 调整层（通常位于图层堆栈顶部）
- 局部效果 → 直接挂在素材层上
- 光效叠加 → 独立层 + SCREEN/ADD 混合模式
- 粒子系统 → 预合成
- 文字内容 → 文字层
- 暗角/压暗 → 调整层 + MULTIPLY
- 多图层共同运动 → 父子链接到空对象

【混合模式规则】
- 发光/光效 → SCREEN 或 ADD
- 暗角/压暗 → MULTIPLY
- 对比增强 → OVERLAY
- 色调统一 → COLOR 或 LUMINOSITY

【遮罩规则】
- 文字发光：文字层做 Alpha 遮罩给发光层
- 局部调色：亮度遮罩（LUMA_TRACK_MATTE）限制作用范围

【预合成规则】
- 粒子系统（Trapcode Particular 等）必须预合成
- 复杂文字动画必须预合成
- 3D 场景必须预合成

【3D 图层规则】
- 有摄像机运动时启用 3D
- 主体层 + 摄像机 + 可能的灯光
- 3D 空对象作为父级控制器

【输出要求】
必须输出严格的 JSON 格式，结构如下：
{
  "composition": {"name": "...", "width": 1920, "height": 1080, "fps": 30, "duration": 10.0},
  "layers": [...],
  "precomps": [...],
  "cameras": [...],
  "lights": [...],
  "reasoning": "推理过程说明（200字以内）"
}

每个 layer 必须包含字段：
- index: 整数，1 表示顶层
- name: 图层名称
- type: footage / adjustment / precomp / text / shape / null / solid
- blend_mode: NONE / SCREEN / ADD / MULTIPLY / OVERLAY 等
- opacity: 0-100
- effects: [{"matchName": "ADBE Lumetri", "params": {...}}]
- track_matte: null 或 {"type": "ALPHA_TRACK_MATTE", "matte_layer": <index>}
- parent: null 或父图层 index
- is_3d: true/false
"""


# =============================================================================
# 核心类
# =============================================================================

class CompositionStructureInferrer:
    """合成结构推断器 - 基于 THINKING 模型推理视频图层堆栈

    工作流程：
        infer_structure()
            ↓
        build_inference_prompt()  → 构建提示词
            ↓
        chat_with_routing(TaskType.EFFECT_PLANNING)  → 调用 LLM
            ↓
        parse_structure_blueprint()  → 解析 JSON 蓝图
            ↓
        optimize_structure()  → 优化（合并、预合成、混合模式规范化）
            ↓
        generate_layer_operations()  → 转换为原子操作序列

    所有 LLM 调用失败的场景都会降级为简化结构（1 个调色调整层 + 1 个主体层），
    保证调用方总能拿到可执行的结构蓝图。
    """

    def __init__(self, output_dir: Path | str | None = None) -> None:
        """初始化结构推断器

        Args:
            output_dir: 输出目录（用于测试模式保存蓝图）
        """
        self._output_dir: Path = Path(output_dir) if output_dir else Path("output")
        self._logger = logger.bind(module="VRS.StructureInferrer")

    # ------------------------------------------------------------------
    # 1. 主入口
    # ------------------------------------------------------------------

    async def infer_structure(
        self,
        analysis_result: dict,
        vision_result: dict | None = None,
    ) -> dict:
        """推断合成结构蓝图

        Args:
            analysis_result: 视频效果分析结果
                推荐字段：basic_info / color_grading / motion_analysis
                / rhythm_analysis / visual_effects / transitions / ae_parameters
                （兼容 saitama_analysis.json 的 stages 格式）
            vision_result: VISION 模型分析结果（可选）
                包含 stages.visual_analysis.frames[*].consensus 字段，
                用于增强视觉细节推断精度

        Returns:
            完整的合成结构蓝图，包含字段：
            - composition: 合成参数
            - layers: 图层列表
            - precomps: 预合成列表
            - cameras: 摄像机列表
            - lights: 灯光列表
            - reasoning: 推理过程说明
            - operations: 原子操作序列
            - metadata: 元信息（版本、图层统计）
        """
        self._logger.info("开始合成结构推断")

        # 1. 合并 vision 结果到分析上下文
        merged_analysis = self._merge_vision_context(analysis_result, vision_result)

        # 2. 构建 LLM 提示词
        prompt = self.build_inference_prompt(merged_analysis)

        # 3. 调用 LLM 推断（带降级）
        blueprint: dict
        if _LLM_AVAILABLE:
            try:
                response: LLMResponse = await chat_with_routing(
                    prompt,
                    task_type=TaskType.EFFECT_PLANNING,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.5,
                    max_tokens=8192,
                )
                if response.success and response.content:
                    blueprint = self.parse_structure_blueprint(response.content)
                    self._logger.info(
                        f"LLM 推断成功 model={response.model} "
                        f"tokens_in={response.tokens_input} "
                        f"tokens_out={response.tokens_output} "
                        f"latency={response.latency_ms:.0f}ms"
                    )
                else:
                    self._logger.warning(
                        f"LLM 调用失败: {response.error}，降级为简化结构"
                    )
                    blueprint = self._build_fallback_blueprint(merged_analysis)
            except Exception as e:
                self._logger.error(
                    f"LLM 推断异常: {type(e).__name__}: {e}，降级为简化结构"
                )
                blueprint = self._build_fallback_blueprint(merged_analysis)
        else:
            self._logger.warning("LLM 网关不可用，使用规则降级结构")
            blueprint = self._build_fallback_blueprint(merged_analysis)

        # 4. 优化结构（合并相似层、规范化混合模式、粒子预合成）
        blueprint = self.optimize_structure(blueprint)

        # 5. 生成原子操作序列并附加到蓝图
        blueprint["operations"] = self.generate_layer_operations(blueprint)
        blueprint["metadata"] = {
            "inferrer_version": "2.0",
            "llm_available": _LLM_AVAILABLE,
            "layer_count": len(blueprint.get("layers", [])),
            "layer_types": sorted({
                l.get("type", "unknown") for l in blueprint.get("layers", [])
            }),
            "operation_count": len(blueprint["operations"]),
        }

        self._logger.info(
            f"结构推断完成 layers={len(blueprint.get('layers', []))} "
            f"precomps={len(blueprint.get('precomps', []))} "
            f"operations={len(blueprint['operations'])}"
        )
        return blueprint

    # ------------------------------------------------------------------
    # 2. 构建提示词
    # ------------------------------------------------------------------

    def build_inference_prompt(self, analysis_result: dict) -> str:
        """构建结构推断提示词

        Args:
            analysis_result: 视频效果分析结果

        Returns:
            发送给 LLM 的完整提示词，包含：视频基本信息、检测到的效果列表
            、调色参数、运动分析、节奏分析、VISION 共识，并要求模型输出
            JSON 格式的结构蓝图
        """
        basic = analysis_result.get("basic_info", {})
        color = analysis_result.get("color_grading", {})
        motion = analysis_result.get("motion_analysis", {})
        rhythm = analysis_result.get("rhythm_analysis", {})
        vfx = analysis_result.get("visual_effects", {})
        transitions = analysis_result.get("transitions", [])
        ae_params = analysis_result.get("ae_parameters", {})
        vision_consensus = analysis_result.get("vision_consensus", {})

        # 兼容 saitama_analysis.json 格式：从 video_path 提取 filename
        filename = basic.get("filename") or analysis_result.get("filename")
        if not filename and analysis_result.get("video_path"):
            try:
                filename = Path(analysis_result["video_path"]).name
            except Exception:
                filename = "未知"

        sections: list[str] = []

        # 1. 视频基本信息
        sections.append("【视频基本信息】")
        sections.append(f"- 分辨率: {basic.get('width', 1920)}x{basic.get('height', 1080)}")
        sections.append(f"- 帧率: {basic.get('fps', 30)} fps")
        sections.append(f"- 时长: {basic.get('duration', 10.0)} 秒")
        sections.append(f"- 文件名: {filename or '未知'}")

        # 2. 调色参数
        if color:
            sections.append("\n【调色分析】")
            sections.append(f"- 风格: {color.get('grading_style', '未知')}")
            sections.append(f"- 色温: {color.get('color_temperature', '中性')}")
            sections.append(f"- 饱和度: {color.get('saturation_style', '中等')}")
            sections.append(f"- 对比度: {color.get('contrast_style', '中等')}")
            if color.get("ae_lumetri_params"):
                lp = color["ae_lumetri_params"]
                sections.append(
                    f"- Lumetri 参数: {json.dumps(lp, ensure_ascii=False)}"
                )

        # 3. 视觉效果列表
        if vfx:
            sections.append("\n【视觉特效】")
            detected = vfx.get("detected_effects", [])
            if detected:
                for eff in detected:
                    name = eff.get("name", "未知效果")
                    ae_effect = eff.get("ae_effect", "")
                    confidence = eff.get("confidence", 0)
                    sections.append(
                        f"- {name} (AE: {ae_effect}, 置信度: {confidence:.2f})"
                    )
            else:
                sections.append("- 未检测到显著视觉特效")

        # 4. 转场
        if transitions:
            sections.append("\n【转场】")
            for t in transitions[:10]:  # 限制数量避免 token 膨胀
                sections.append(
                    f"- {t.get('time_sec', 0):.1f}s {t.get('type', '未知')} "
                    f"(AE: {t.get('ae_effect', 'N/A')})"
                )

        # 5. 运动分析
        if motion:
            sections.append("\n【运动分析】")
            sections.append(f"- 相机运动: {motion.get('camera_motion', '固定')}")
            sections.append(f"- 主体运动: {motion.get('subject_motion', '未知')}")
            speed_changes = motion.get("speed_changes", [])
            if speed_changes:
                sections.append(f"- 速度变化: {len(speed_changes)} 处")
                for sc in speed_changes[:5]:
                    sections.append(
                        f"  • {sc.get('time_sec', 0):.1f}s "
                        f"{sc.get('type', '未知')}"
                    )

        # 6. 节奏分析
        if rhythm:
            sections.append("\n【节奏分析】")
            sections.append(f"- 节奏: {rhythm.get('rhythm', '中等')}")
            sections.append(
                f"- 平均镜头时长: {rhythm.get('avg_shot_duration', 0):.2f}s"
            )
            sections.append(f"- 场景数: {rhythm.get('scene_count', 0)}")

        # 7. AE 参数（已生成的 AE 参数表，作为参考）
        if ae_params:
            sections.append("\n【已生成的 AE 参数参考】")
            adj_layers = ae_params.get("adjustment_layers", [])
            effects_list = ae_params.get("effects", [])
            sections.append(f"- 调整层数量: {len(adj_layers)}")
            sections.append(f"- 效果数量: {len(effects_list)}")
            for adj in adj_layers[:5]:
                sections.append(
                    f"  • {adj.get('name', '')} -> {adj.get('effect', '')}"
                )

        # 8. VISION 共识（如果存在）
        if vision_consensus:
            sections.append("\n【VISION 视觉共识】")
            sections.append(
                f"- 置信度: {vision_consensus.get('confidence', 0):.2f}"
            )
            for ve in vision_consensus.get("visual_effects", [])[:8]:
                sections.append(f"- 视效: {ve}")
            for pe in vision_consensus.get("post_effects", [])[:8]:
                sections.append(f"- 后期: {pe}")
            for plugin in vision_consensus.get("possible_plugins", [])[:8]:
                sections.append(f"- 可能插件: {plugin}")

        # 9. 输出要求
        sections.append("\n【输出要求】")
        sections.append("1. 基于上述分析，推断出 AE 合成的完整图层堆栈结构")
        sections.append(
            "2. 输出严格的 JSON 格式，包含 composition / layers / precomps "
            "/ cameras / lights / reasoning"
        )
        sections.append(
            "3. 每个 layer 必须有 index / name / type / blend_mode / opacity "
            "/ effects / track_matte / parent / is_3d"
        )
        sections.append(
            "4. layer.type 可选: footage / adjustment / precomp / text "
            "/ shape / null / solid"
        )
        sections.append(
            "5. 全局调色必须放在 adjustment 层，光效用 SCREEN/ADD，"
            "暗角用 MULTIPLY"
        )
        sections.append("6. 粒子、复杂文字动画、3D 场景必须预合成")
        sections.append(
            "7. reasoning 字段简要说明推断逻辑（200字以内）"
        )
        sections.append("\n请直接输出 JSON，不要包裹在 markdown 代码块中。")

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # 3. 解析结构蓝图
    # ------------------------------------------------------------------

    def parse_structure_blueprint(self, llm_response: str) -> dict:
        """解析 LLM 返回的结构蓝图 JSON

        Args:
            llm_response: LLM 返回的原始文本

        Returns:
            解析后的结构蓝图 dict，字段缺失时补充默认值。
            解析失败时返回降级简化结构。
        """
        if not llm_response:
            self._logger.warning("LLM 返回空响应，使用降级结构")
            return self._build_fallback_blueprint({})

        # 尝试直接解析
        blueprint: dict | None = None
        try:
            blueprint = json.loads(llm_response)
        except json.JSONDecodeError:
            # 尝试正则提取 JSON 片段
            json_str = self._extract_json_block(llm_response)
            if json_str:
                try:
                    # 清理 JSON 中的非法控制字符（LLM 输出常含 \x00-\x1f）
                    import re
                    json_str_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', json_str)
                    blueprint = json.loads(json_str_clean)
                except json.JSONDecodeError as e:
                    self._logger.warning(f"JSON 片段解析失败: {e}")
                    # 降级尝试：逐行清理后重新拼接
                    try:
                        lines_clean = []
                        for line in json_str.split('\n'):
                            line_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', line)
                            lines_clean.append(line_clean)
                        blueprint = json.loads('\n'.join(lines_clean))
                    except json.JSONDecodeError as e2:
                        self._logger.warning(f"JSON 二次清理仍失败: {e2}")
            else:
                self._logger.warning("未在响应中找到 JSON 块")

        if not blueprint or not isinstance(blueprint, dict):
            self._logger.warning("解析失败，降级为简化结构")
            return self._build_fallback_blueprint({})

        # 验证并补全字段
        blueprint = self._validate_and_complete_blueprint(blueprint)
        return blueprint

    # ------------------------------------------------------------------
    # 4. 优化结构
    # ------------------------------------------------------------------

    def optimize_structure(self, blueprint: dict) -> dict:
        """优化结构蓝图

        优化规则：
        1. 调色效果 → 调整层
        2. 光效 → 独立层 + SCREEN 混合
        3. 粒子 → 预合成
        4. 合并相似的相邻调整层
        5. 调整图层顺序（按 AE 规范：顶部为调整层）

        Args:
            blueprint: 原始结构蓝图

        Returns:
            优化后的结构蓝图
        """
        if not blueprint or "layers" not in blueprint:
            return blueprint

        layers: list[dict] = blueprint.get("layers", [])
        if not layers:
            return blueprint

        # 1. 规范化混合模式（光效→SCREEN/ADD，暗角→MULTIPLY）
        layers = [self._normalize_layer_blend_mode(layer) for layer in layers]

        # 2. 合并相似调整层（同名且同混合模式的连续调整层）
        layers = self._merge_similar_adjustment_layers(layers)

        # 3. 粒子/复杂效果强制预合成
        layers, new_precomps = self._enforce_precomp_for_particles(
            layers, blueprint.get("precomps", [])
        )
        if new_precomps:
            blueprint["precomps"] = new_precomps

        # 4. 重新编号图层索引
        for i, layer in enumerate(layers, start=1):
            layer["index"] = i

        blueprint["layers"] = layers
        return blueprint

    # ------------------------------------------------------------------
    # 5. 生成原子操作序列
    # ------------------------------------------------------------------

    def generate_layer_operations(self, blueprint: dict) -> list[dict]:
        """将结构蓝图转换为原子操作序列

        操作类型：
        - create_comp: 创建合成
        - add_layer: 添加素材层
        - add_adjustment_layer: 添加调整层
        - add_precomp: 添加预合成
        - add_precomp_layer: 添加预合成图层引用
        - add_text_layer: 添加文字层
        - add_shape_layer: 添加形状层
        - add_null_layer: 添加空对象层
        - add_solid_layer: 添加固态层
        - add_effect: 添加效果
        - set_blend_mode: 设置混合模式
        - set_track_matte: 设置轨道遮罩
        - set_parent_layer: 设置父子关系
        - add_camera: 添加摄像机
        - add_light: 添加灯光

        Args:
            blueprint: 结构蓝图

        Returns:
            操作序列列表，按 AE 执行顺序排序
        """
        operations: list[dict] = []
        comp = blueprint.get("composition", {})
        comp_name = comp.get("name", DEFAULT_COMP["name"])

        # 1. 创建合成
        operations.append({
            "op": "create_comp",
            "name": comp_name,
            "width": comp.get("width", DEFAULT_COMP["width"]),
            "height": comp.get("height", DEFAULT_COMP["height"]),
            "fps": comp.get("fps", DEFAULT_COMP["fps"]),
            "duration": comp.get("duration", DEFAULT_COMP["duration"]),
            "pixel_aspect": 1.0,
        })

        # 2. 先创建独立预合成（非图层引用的预合成）
        for precomp in blueprint.get("precomps", []):
            operations.append({
                "op": "add_precomp",
                "comp_name": comp_name,
                "name": precomp.get("name", "Precomp"),
                "layer_indices": [],
                "move_all_attributes": True,
            })

        # 3. 按 index 升序添加图层（AE 中 index=1 是最顶层）
        layers_sorted = sorted(
            blueprint.get("layers", []),
            key=lambda l: l.get("index", 0),
        )

        for layer in layers_sorted:
            layer_index = layer.get("index", 1)
            layer_op = self._layer_to_operation(layer, comp_name)
            operations.append(layer_op)

            # 添加效果（在图层创建后立即添加）
            for eff in layer.get("effects", []):
                if not isinstance(eff, dict):
                    continue
                match_name = eff.get("matchName", "")
                if not match_name:
                    continue
                operations.append({
                    "op": "add_effect",
                    "comp_name": comp_name,
                    "layer_index": layer_index,
                    "match_name": match_name,
                    "params": eff.get("params", {}) if isinstance(
                        eff.get("params"), dict
                    ) else {},
                })

            # 设置混合模式（NONE/NORMAL 跳过）
            blend = layer.get("blend_mode", "NONE")
            if blend and blend not in ("NONE", "NORMAL"):
                operations.append({
                    "op": "set_blend_mode",
                    "comp_name": comp_name,
                    "layer_index": layer_index,
                    "blend_mode": blend,
                })

            # 设置轨道遮罩
            matte = layer.get("track_matte")
            if (
                isinstance(matte, dict)
                and matte.get("type")
                and matte["type"] != "NO_TRACK_MATTE"
            ):
                operations.append({
                    "op": "set_track_matte",
                    "comp_name": comp_name,
                    "layer_index": layer_index,
                    "matte_type": matte["type"],
                })

            # 设置父子关系
            parent = layer.get("parent")
            if isinstance(parent, int) and parent > 0:
                operations.append({
                    "op": "set_parent_layer",
                    "comp_name": comp_name,
                    "layer_index": layer_index,
                    "parent_index": parent,
                })

        # 4. 创建摄像机
        for cam in blueprint.get("cameras", []):
            operations.append({
                "op": "add_camera",
                "comp_name": comp_name,
                "name": cam.get("name", "Main Camera"),
                "type": cam.get("type", "one_node"),
                "focal_length": cam.get("focal_length", 35),
            })

        # 5. 创建灯光
        for light in blueprint.get("lights", []):
            operations.append({
                "op": "add_light",
                "comp_name": comp_name,
                "name": light.get("name", "Light"),
                "type": light.get("type", "parallel"),
                "intensity": light.get("intensity", 100),
                "color": light.get("color", [1, 1, 1]),
            })

        return operations

    # ==================================================================
    # 内部辅助方法
    # ==================================================================

    def _merge_vision_context(
        self,
        analysis_result: dict,
        vision_result: dict | None,
    ) -> dict:
        """将 VISION 结果合并到分析上下文

        优先使用显式传入的 vision_result；若未提供，尝试从 analysis_result
        的 stages.visual_analysis.frames 中提取首帧 consensus。

        Args:
            analysis_result: 视频效果分析结果
            vision_result: VISION 模型分析结果（可选）

        Returns:
            合并后的分析上下文（添加 vision_consensus 字段）
        """
        merged = dict(analysis_result)

        # 优先使用显式传入的 vision_result
        vision_source = vision_result if vision_result else analysis_result

        if not isinstance(vision_source, dict):
            return merged

        # 兼容 saitama_analysis.json 的 stages 格式
        stages = vision_source.get("stages", {})
        if isinstance(stages, dict):
            visual = stages.get("visual_analysis", {})
            if isinstance(visual, dict):
                frames = visual.get("frames", [])
                if frames and isinstance(frames[0], dict):
                    first_consensus = frames[0].get("consensus", {})
                    if first_consensus:
                        merged["vision_consensus"] = first_consensus

        return merged

    def _extract_json_block(self, text: str) -> str | None:
        """从文本中提取 JSON 片段

        依次尝试：
        1. ```json ... ``` 代码块
        2. ``` ... ``` 代码块
        3. 裸 { ... }（贪婪匹配最外层）

        Args:
            text: 原始文本

        Returns:
            提取到的 JSON 字符串，未找到返回 None
        """
        # 1. ```json ... ``` 代码块
        match = re.search(r"```json\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 2. 通用 ``` ... ``` 代码块
        match = re.search(r"```\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            if candidate.startswith("{") or candidate.startswith("["):
                return candidate

        # 3. 裸 { ... }（贪婪到最外层）
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)

        return None

    def _validate_and_complete_blueprint(self, blueprint: dict) -> dict:
        """验证字段完整性，补充默认值

        Args:
            blueprint: 原始蓝图

        Returns:
            字段完整的蓝图
        """
        # composition
        comp = blueprint.get("composition", {})
        if not isinstance(comp, dict):
            comp = {}
        blueprint["composition"] = {
            "name": comp.get("name", DEFAULT_COMP["name"]),
            "width": comp.get("width", DEFAULT_COMP["width"]),
            "height": comp.get("height", DEFAULT_COMP["height"]),
            "fps": comp.get("fps", DEFAULT_COMP["fps"]),
            "duration": comp.get("duration", DEFAULT_COMP["duration"]),
        }

        # layers
        layers = blueprint.get("layers", [])
        if not isinstance(layers, list):
            layers = []
        normalized_layers: list[dict] = []
        for i, layer in enumerate(layers, start=1):
            if not isinstance(layer, dict):
                continue
            normalized = self._normalize_layer(layer, i)
            normalized_layers.append(normalized)
        blueprint["layers"] = normalized_layers

        # precomps
        if not isinstance(blueprint.get("precomps"), list):
            blueprint["precomps"] = []

        # cameras
        if not isinstance(blueprint.get("cameras"), list):
            blueprint["cameras"] = []

        # lights
        if not isinstance(blueprint.get("lights"), list):
            blueprint["lights"] = []

        # reasoning
        if not isinstance(blueprint.get("reasoning"), str):
            blueprint["reasoning"] = "结构推断完成，无推理过程说明"

        return blueprint

    def _normalize_layer(self, layer: dict, default_index: int) -> dict:
        """规范化单个图层字段

        Args:
            layer: 原始图层字典
            default_index: 默认索引（当 layer.index 缺失时使用）

        Returns:
            字段完整的图层字典
        """
        layer_type = layer.get("type", "footage")
        if layer_type not in SUPPORTED_LAYER_TYPES:
            layer_type = "footage"

        blend = layer.get("blend_mode", "NONE")
        if blend not in SUPPORTED_BLEND_MODES:
            blend = "NONE"

        # 规范化 effects 列表
        effects = layer.get("effects", [])
        if not isinstance(effects, list):
            effects = []
        norm_effects: list[dict] = []
        for eff in effects:
            if isinstance(eff, dict) and eff.get("matchName"):
                params = eff.get("params", {})
                if not isinstance(params, dict):
                    params = {}
                norm_effects.append({
                    "matchName": eff["matchName"],
                    "params": params,
                })

        # 规范化 track_matte
        matte = layer.get("track_matte")
        if not isinstance(matte, dict):
            matte = None

        # 规范化 parent
        parent = layer.get("parent")
        if not isinstance(parent, int):
            parent = None

        return {
            "index": layer.get("index", default_index),
            "name": layer.get("name", f"Layer_{default_index}"),
            "type": layer_type,
            "source": layer.get("source", ""),
            "blend_mode": blend,
            "opacity": self._clamp(layer.get("opacity", 100), 0, 100),
            "effects": norm_effects,
            "track_matte": matte,
            "parent": parent,
            "is_3d": bool(layer.get("is_3d", False)),
        }

    @staticmethod
    def _clamp(value: Any, low: float, high: float) -> float:
        """数值钳制

        Args:
            value: 输入值
            low: 下界
            high: 上界

        Returns:
            钳制后的浮点数
        """
        try:
            v = float(value)
        except (TypeError, ValueError):
            return low
        return max(low, min(high, v))

    def _normalize_layer_blend_mode(self, layer: dict) -> dict:
        """根据图层类型与效果规范化混合模式

        仅当当前混合模式为 NONE/NORMAL 时才进行覆盖，
        避免覆盖 LLM 显式设置的混合模式。

        规则：
        - 发光/光效 → SCREEN
        - 粒子 → ADD
        - 暗角/压暗 → MULTIPLY
        - 对比增强 → OVERLAY

        Args:
            layer: 图层字典

        Returns:
            规范化后的图层字典
        """
        name = layer.get("name", "").lower()
        effects = layer.get("effects", [])
        effect_names = " ".join(
            e.get("matchName", "").lower() for e in effects if isinstance(e, dict)
        )
        current_blend = layer.get("blend_mode", "NONE")

        # 仅在未显式设置时应用规则
        if current_blend not in ("NONE", "NORMAL"):
            return layer

        # 按名称关键词判断
        if any(kw in name for kw in ["发光", "光", "glow", "flare", "light"]):
            layer["blend_mode"] = "SCREEN"
        elif any(kw in name for kw in ["粒子", "particular", "particle"]):
            layer["blend_mode"] = "ADD"
        elif any(kw in name for kw in ["暗角", "vignette", "压暗"]):
            layer["blend_mode"] = "MULTIPLY"
        elif any(kw in name for kw in ["对比", "contrast"]):
            layer["blend_mode"] = "OVERLAY"
        # 按效果 matchName 进一步判断
        elif "ADBE Glo2" in effect_names or "ADBE Glow" in effect_names:
            layer["blend_mode"] = "SCREEN"
        elif "CC Vignette" in effect_names:
            layer["blend_mode"] = "MULTIPLY"
        elif "Trapcode Particular" in effect_names:
            layer["blend_mode"] = "ADD"

        return layer

    def _merge_similar_adjustment_layers(
        self, layers: list[dict]
    ) -> list[dict]:
        """合并相似的相邻调整层

        合并条件：
        - 连续两个 adjustment 层
        - 同名
        - 同混合模式

        合并方式：保留前者，合并 effects 列表（按 matchName 去重）

        Args:
            layers: 图层列表

        Returns:
            合并后的图层列表
        """
        if len(layers) <= 1:
            return layers

        merged: list[dict] = []
        for layer in layers:
            if not merged:
                merged.append(layer)
                continue

            prev = merged[-1]
            # 仅合并连续的、同名的、同混合模式的调整层
            if (
                prev.get("type") == "adjustment"
                and layer.get("type") == "adjustment"
                and prev.get("blend_mode") == layer.get("blend_mode")
                and prev.get("name") == layer.get("name")
            ):
                prev_effects = prev.get("effects", [])
                curr_effects = layer.get("effects", [])
                existing = {
                    e.get("matchName") for e in prev_effects
                    if isinstance(e, dict)
                }
                for eff in curr_effects:
                    if isinstance(eff, dict) and eff.get("matchName") not in existing:
                        prev_effects.append(eff)
                        existing.add(eff.get("matchName"))
                prev["effects"] = prev_effects
                self._logger.debug(
                    f"合并相似调整层: {layer.get('name')}"
                )
            else:
                merged.append(layer)

        return merged

    def _enforce_precomp_for_particles(
        self,
        layers: list[dict],
        existing_precomps: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """对粒子层强制使用预合成

        检测粒子系统（Trapcode Particular 或名称包含"粒子/particular"），
        将其升级为 precomp 类型并创建对应的预合成条目。

        Args:
            layers: 图层列表
            existing_precomps: 已存在的预合成列表

        Returns:
            (更新后的 layers, 更新后的 precomps)
        """
        new_precomps: list[dict] = list(existing_precomps)
        new_layers: list[dict] = []

        for layer in layers:
            effects = layer.get("effects", [])
            effect_names = " ".join(
                e.get("matchName", "") for e in effects if isinstance(e, dict)
            )
            name_lower = layer.get("name", "").lower()

            is_particle = (
                "Trapcode Particular" in effect_names
                or "particular" in name_lower
                or "粒子" in layer.get("name", "")
            )

            if is_particle and layer.get("type") != "precomp":
                precomp_name = layer.get("name", "粒子预合成")
                # 仅在预合成不存在时添加
                if not any(
                    p.get("name") == precomp_name for p in new_precomps
                ):
                    new_precomps.append({
                        "name": precomp_name,
                        "layers": [layer],  # 保留原层信息作为内部图层
                    })
                # 替换为预合成层引用
                new_layer = dict(layer)
                new_layer["type"] = "precomp"
                new_layer["source"] = precomp_name
                new_layer["effects"] = []  # 效果移入预合成内部
                new_layers.append(new_layer)
                self._logger.debug(
                    f"粒子层升级为预合成: {precomp_name}"
                )
            else:
                new_layers.append(layer)

        return new_layers, new_precomps

    def _layer_to_operation(
        self, layer: dict, comp_name: str
    ) -> dict:
        """将单个图层转换为创建操作

        根据 layer.type 映射到对应的原子操作：
        - footage → add_layer
        - adjustment → add_adjustment_layer
        - precomp → add_precomp_layer
        - text → add_text_layer
        - shape → add_shape_layer
        - null → add_null_layer
        - solid → add_solid_layer

        Args:
            layer: 图层字典
            comp_name: 目标合成名称

        Returns:
            操作字典
        """
        layer_type = layer.get("type", "footage")
        layer_index = layer.get("index", 1)
        opacity = layer.get("opacity", 100)
        is_3d = layer.get("is_3d", False)

        if layer_type == "adjustment":
            return {
                "op": "add_adjustment_layer",
                "comp_name": comp_name,
                "name": layer.get("name", "Adjustment Layer"),
                "position": layer_index,
                "opacity": opacity,
                "is_3d": is_3d,
            }
        elif layer_type == "precomp":
            return {
                "op": "add_precomp_layer",
                "comp_name": comp_name,
                "name": layer.get("name", "Precomp Layer"),
                "source": layer.get("source", ""),
                "position": layer_index,
                "opacity": opacity,
                "is_3d": is_3d,
            }
        elif layer_type == "text":
            return {
                "op": "add_text_layer",
                "comp_name": comp_name,
                "name": layer.get("name", "Text Layer"),
                "text_content": layer.get("text", ""),
                "position": layer_index,
                "opacity": opacity,
                "is_3d": is_3d,
            }
        elif layer_type == "shape":
            return {
                "op": "add_shape_layer",
                "comp_name": comp_name,
                "name": layer.get("name", "Shape Layer"),
                "shape_type": layer.get("shape_type", "rectangle"),
                "position": layer_index,
                "opacity": opacity,
                "is_3d": is_3d,
            }
        elif layer_type == "null":
            return {
                "op": "add_null_layer",
                "comp_name": comp_name,
                "name": layer.get("name", "Null Layer"),
                "position": layer_index,
            }
        elif layer_type == "solid":
            return {
                "op": "add_solid_layer",
                "comp_name": comp_name,
                "name": layer.get("name", "Solid Layer"),
                "color": layer.get("color", [0, 0, 0]),
                "position": layer_index,
                "opacity": opacity,
                "is_3d": is_3d,
            }
        else:  # footage
            return {
                "op": "add_layer",
                "comp_name": comp_name,
                "name": layer.get("name", "Footage Layer"),
                "source": layer.get("source", "main_video.mp4"),
                "position": layer_index,
                "opacity": opacity,
                "is_3d": is_3d,
            }

    def _build_fallback_blueprint(self, analysis_result: dict) -> dict:
        """构建降级简化结构（1 个调色调整层 + 1 个主体层）

        当 LLM 不可用或解析失败时使用，保证调用方总能拿到可执行结构。

        Args:
            analysis_result: 分析结果（用于提取合成基本信息）

        Returns:
            最小化结构蓝图
        """
        basic = analysis_result.get("basic_info", {})
        color = analysis_result.get("color_grading", {})

        comp = {
            "name": DEFAULT_COMP["name"],
            "width": basic.get("width", DEFAULT_COMP["width"]),
            "height": basic.get("height", DEFAULT_COMP["height"]),
            "fps": basic.get("fps", DEFAULT_COMP["fps"]),
            "duration": basic.get("duration", DEFAULT_COMP["duration"]),
        }

        layers: list[dict] = [
            {
                "index": 1,
                "name": "调色调整层",
                "type": "adjustment",
                "source": "",
                "blend_mode": "NONE",
                "opacity": 100,
                "effects": self._build_color_effects(color),
                "track_matte": None,
                "parent": None,
                "is_3d": False,
            },
            {
                "index": 2,
                "name": "主体素材层",
                "type": "footage",
                "source": "main_video.mp4",
                "blend_mode": "NONE",
                "opacity": 100,
                "effects": [],
                "track_matte": None,
                "parent": None,
                "is_3d": False,
            },
        ]

        return {
            "composition": comp,
            "layers": layers,
            "precomps": [],
            "cameras": [],
            "lights": [],
            "reasoning": (
                "降级模式：LLM 不可用，仅生成最小结构"
                "（调色调整层 + 主体素材层）"
            ),
            "fallback": True,
        }

    def _build_color_effects(self, color: dict) -> list[dict]:
        """根据调色分析构建 Lumetri 效果列表

        Args:
            color: 调色分析结果

        Returns:
            效果列表，至少包含一个 Lumetri 效果
        """
        if not color:
            return [{"matchName": "ADBE Lumetri", "params": {}}]

        lp = color.get("ae_lumetri_params", {})
        if not lp:
            return [{"matchName": "ADBE Lumetri", "params": {}}]

        return [{"matchName": "ADBE Lumetri", "params": lp}]


# =============================================================================
# 命令行入口
# =============================================================================

async def _run_test(test_input: str) -> None:
    """运行 --test 模式

    Args:
        test_input: 输入 JSON 文件路径
    """
    inferrer = CompositionStructureInferrer()
    input_path = Path(test_input)
    if not input_path.exists():
        logger.error(f"输入文件不存在: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        analysis_result = json.load(f)

    logger.info(f"加载分析结果: {input_path}")
    blueprint = await inferrer.infer_structure(analysis_result)

    # 输出结构蓝图
    output_path = Path("output") / "vrs_structure_blueprint.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(blueprint, f, ensure_ascii=False, indent=2)

    logger.info(f"结构蓝图已输出: {output_path}")
    logger.info(
        f"合成: {blueprint['composition']['name']} "
        f"{blueprint['composition']['width']}x{blueprint['composition']['height']}@{blueprint['composition']['fps']}fps"
    )
    logger.info(f"图层总数: {len(blueprint.get('layers', []))}")
    logger.info(f"预合成数: {len(blueprint.get('precomps', []))}")
    logger.info(f"操作数: {len(blueprint.get('operations', []))}")
    logger.info(f"是否降级: {blueprint.get('fallback', False)}")

    # 图层类型分布
    type_dist: dict[str, int] = {t: 0 for t in SUPPORTED_LAYER_TYPES}
    for layer in blueprint.get("layers", []):
        t = layer.get("type", "unknown")
        type_dist[t] = type_dist.get(t, 0) + 1
    logger.info(f"图层类型分布: {type_dist}")


def main() -> None:
    """命令行入口

    用法：
        python vrs_structure_inferrer.py --test output/saitama_analysis.json
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="VRS 合成结构推断引擎 v2.0"
    )
    parser.add_argument(
        "--test",
        default="output/saitama_analysis.json",
        help="输入分析结果 JSON 文件路径（默认 output/saitama_analysis.json）",
    )
    args = parser.parse_args()

    # 初始化 LLM 网关配置（从环境变量）
    try:
        from core.llm_gateway import configure_from_env
        configure_from_env()
        logger.info("LLM 网关已从环境变量配置")
    except ImportError:
        logger.warning("core.llm_gateway 不可用，将使用降级模式")
    except Exception as e:
        logger.warning(f"LLM 网关配置失败: {e}")

    asyncio.run(_run_test(args.test))


if __name__ == "__main__":
    main()

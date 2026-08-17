#!/usr/bin/env python3
"""
ai_scheduler.py
Phase 4 - AI 智能调度引擎主入口 (Python 版)

对齐 TypeScript 端 compiler/src/phase4/ai-scheduler.ts。

核心职责：
  1. 整合 NLU 解析、参数生成、参数优化和操作序列生成
  2. 实现自然语言→效果参数→AE 操作的完整管线编排
  3. 提供统一的调度 API 供上层 (ae_agent_pipeline) 调用

调度流程：
  用户输入 → NLUParser → Intent + EffectDescription
                      → IntentRouter (路由决策)
                      → ParameterMapper / EffectGeneratorFactory
                      → ParameterOptimizer
                      → Operations (供 pipeline execute() 消费)

设计要点：
  - 不复制 TS 端的 validate/buildIR/generateCode 编译链
    （Python pipeline 已有自己的 JSX 生成逻辑）
  - 输出 operations (List[Dict]) 供 pipeline.execute() 消费
  - 对齐 Python 现有模块 API（NLUParser/EffectDescriptionParser/
    ParameterMapper/EffectGeneratorFactory/ParameterOptimizer/IntentRouter）
  - 支持 needsClarification 追问机制
  - 支持 Silhouette 任务生成（roto/track/paint/export）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import re

# 现有 Python 模块
from nlu_parser import (
    NLUParser, Intent, IntentType, IntentSlots, ProjectContext,
    ConfidenceThresholds,
)
from effect_description_parser import (
    EffectDescriptionParser, EffectDescription,
    VocabRef, ColorRef, IntensityRef, TemporalRef,
)
from parameter_mapper import ParameterMapper, ParameterMapping, MapperContext
from effect_generators import (
    EffectGeneratorFactory, EffectParams, GeneratorContext,
    effect_generator_factory,
)
from parameter_optimizer import (
    ParameterOptimizer, ParameterContext, OptimizedParameters,
)
from intent_router import IntentRouter, TaskRoute
from vocabulary_map import scan_vocab, scan_colors, scan_intensity, scan_temporal


# ============================================================================
# 效果名规范化映射（对齐 TS EFFECT_NAME_MAPPING）
# ============================================================================

EFFECT_NAME_MAPPING: Dict[str, str] = {
    "发光": "glow",
    "辉光": "glow",
    "glow": "glow",
    "霓虹": "glow",
    "红色发光": "glow",
    "模糊": "blur",
    "高斯模糊": "blur",
    "blur": "blur",
    "运动模糊": "directionalblur",
    "方向模糊": "directionalblur",
    "directionalblur": "directionalblur",
    "径向模糊": "radialblur",
    "radialblur": "radialblur",
    "粒子": "ccparticleworld",
    "粒子世界": "ccparticleworld",
    "particle": "ccparticleworld",
    "colorkey": "colorkey",
    "颜色键": "colorkey",
    "抠像": "colorkey",
    "绿幕": "colorkey",
    "噪波": "fractalnoise",
    "分形噪波": "fractalnoise",
    "fractalnoise": "fractalnoise",
    "渐变": "ramp",
    "ramp": "ramp",
    "adbeglo2": "glow",
    "adbeglo": "glow",
    "adbecolorkey": "colorkey",
    "adbefractalnoise": "fractalnoise",
    "adberamp": "ramp",
    "ccparticleworld": "ccparticleworld",
    "色彩平衡": "colorbalance",
    "colorbalance": "colorbalance",
    "色阶": "levels",
    "levels": "levels",
    "投影": "dropshadow",
    "阴影": "dropshadow",
    "dropshadow": "dropshadow",
    "填充": "fill",
    "fill": "fill",
    "描边": "stroke",
    "stroke": "stroke",
    "暗角": "vignette",
    "vignette": "vignette",
    "粗糙边缘": "roughenedges",
    "roughenedges": "roughenedges",
}

# 风格关键词列表（用于从 effectName 中提取 style）
_STYLE_KEYWORDS = [
    "霓虹", "柔和", "强烈", "赛博朋克", "梦幻", "电影感",
    "复古", "极简", "fire", "snow", "stars", "clouds",
    "water", "electric", "smoke", "sunset", "cyberpunk",
    "gradient", "radial", "warmcool", "neon",
]


def map_effect_name(effect_name: str) -> Optional[str]:
    """将用户输入的效果名规范化为生成器可识别的名称

    对齐 TS mapEffectName。
    """
    if not effect_name:
        return None
    normalized = re.sub(r"\s", "", effect_name.lower())
    # 去除常见前后缀
    normalized = re.sub(r"^做[个一]?", "", normalized)
    normalized = re.sub(r"[个一]$", "", normalized)
    normalized = re.sub(r"效果$", "", normalized)
    normalized = re.sub(r"特效$", "", normalized)

    if normalized in EFFECT_NAME_MAPPING:
        return EFFECT_NAME_MAPPING[normalized]

    # 模糊包含匹配
    for key, value in EFFECT_NAME_MAPPING.items():
        if key in normalized:
            return value

    return None


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class SchedulerOptions:
    """调度器选项"""
    project_context: Optional[ProjectContext] = None
    target_layer_ref: str = "selected"
    enable_optimization: bool = True
    performance_mode: bool = False
    target_style: Optional[str] = None


@dataclass
class NLUPipelineResult:
    """NLU 管线结果"""
    intent: Intent
    effect_description: EffectDescription
    understood: bool
    needs_clarification: bool
    clarification_question: Optional[str] = None
    clarification_options: Optional[List[str]] = None


@dataclass
class SchedulerResult:
    """调度器最终结果"""
    success: bool
    intent: Optional[Intent] = None
    effect_description: Optional[EffectDescription] = None
    mappings: List[ParameterMapping] = field(default_factory=list)
    generated_effects: List[EffectParams] = field(default_factory=list)
    optimizations: List[OptimizedParameters] = field(default_factory=list)
    operations: List[Dict[str, Any]] = field(default_factory=list)
    silhouette_operations: List[Dict[str, Any]] = field(default_factory=list)
    route: Optional[TaskRoute] = None
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: Optional[List[str]] = None
    error: Optional[str] = None


# ============================================================================
# AIScheduler 主类
# ============================================================================

class AIScheduler:
    """AI 智能调度引擎

    聚合 NLUParser + EffectDescriptionParser + ParameterMapper +
    EffectGeneratorFactory + ParameterOptimizer + IntentRouter，
    提供从自然语言到 AE 操作序列的完整管线编排。
    """

    def __init__(self, options: SchedulerOptions = None) -> None:
        options = options or SchedulerOptions()
        ctx = options.project_context

        self.nlu_parser = NLUParser()
        self.description_parser = EffectDescriptionParser()

        # ParameterMapper 上下文
        mapper_context = MapperContext(
            compWidth=ctx.compResolution[0] if ctx and ctx.compResolution else None,
            compHeight=ctx.compResolution[1] if ctx and ctx.compResolution else None,
            frameRate=ctx.compFrameRate if ctx else None,
            duration=ctx.compDuration if ctx else None,
        )
        self.parameter_mapper = ParameterMapper(mapper_context)

        # EffectGeneratorFactory 上下文
        gen_context = GeneratorContext(
            compWidth=ctx.compResolution[0] if ctx and ctx.compResolution else None,
            compHeight=ctx.compResolution[1] if ctx and ctx.compResolution else None,
            frameRate=ctx.compFrameRate if ctx else None,
            duration=ctx.compDuration if ctx else None,
        )
        self.generator_factory = EffectGeneratorFactory(gen_context)

        self.parameter_optimizer = ParameterOptimizer()
        self.intent_router = IntentRouter()

        self._target_style = options.target_style
        self._performance_mode = options.performance_mode

    # ------------------------------------------------------------------
    # NLU 管线
    # ------------------------------------------------------------------

    def run_nlu_pipeline(
        self, input_text: str, context: Optional[ProjectContext] = None
    ) -> NLUPipelineResult:
        """运行 NLU 管线：NLUParser + EffectDescriptionParser

        对齐 TS runNLUPipeline。
        """
        intent = self.nlu_parser.parse(input_text, context)
        effect_description = self.description_parser.parse(
            input_text, intent.type
        )
        needs_clarification = self.nlu_parser.needs_clarification(intent)

        clarification_question = None
        clarification_options = None

        if needs_clarification:
            clarification_question = self._generate_clarification_question(
                intent, effect_description
            )
            clarification_options = self._generate_clarification_options(intent)

        understood = (
            intent.type != IntentType.UNKNOWN and not needs_clarification
        )

        return NLUPipelineResult(
            intent=intent,
            effect_description=effect_description,
            understood=understood,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
            clarification_options=clarification_options,
        )

    def _generate_clarification_question(
        self, intent: Intent, description: EffectDescription
    ) -> str:
        """生成追问问题"""
        if intent.type == IntentType.ADD_EFFECT and not intent.slots.effectName:
            return "您想添加什么效果？"
        if intent.type == IntentType.STYLE_COMBO and not intent.slots.styleName:
            return "您想要什么风格？"
        if intent.type == IntentType.CREATE_ANIM and not intent.slots.animType:
            return "您想创建什么类型的动画？"
        if description.colorKeywords and len(description.colorKeywords) == 0 \
                and intent.confidence < 0.6:
            return "是否需要指定颜色？"
        return "请明确您想要的效果"

    def _generate_clarification_options(self, intent: Intent) -> List[str]:
        """生成追问选项"""
        if intent.type == IntentType.ADD_EFFECT:
            return ["发光", "模糊", "粒子", "调色", "扭曲"]
        if intent.type == IntentType.STYLE_COMBO:
            return ["赛博朋克", "电影感", "梦幻", "复古", "极简"]
        if intent.type == IntentType.CREATE_ANIM:
            return ["弹入", "淡入", "滑入", "缩放", "旋转"]
        return ["确认", "取消"]

    # ------------------------------------------------------------------
    # 参数生成
    # ------------------------------------------------------------------

    def generate_parameters(
        self, nlu_result: NLUPipelineResult
    ) -> tuple:
        """生成参数映射和效果参数

        对齐 TS generateParameters。返回 (mappings, generated_effects)。

        流程：
          1. 如果是 ADD_EFFECT 且 slots.effectName 存在，
             用 generator_factory 直接生成
          2. 如果 effect_description 有 effectKeywords，
             用 parameter_mapper 映射
          3. 对每个 mapping，若未在步骤1生成过，用 generator_factory 补充
        """
        mappings: List[ParameterMapping] = []
        generated_effects: List[EffectParams] = []
        seen_match_names: set = set()

        # 1. 从 intent.slots.effectName 直接生成
        if nlu_result.intent.type == IntentType.ADD_EFFECT:
            effect_name = (nlu_result.intent.slots.effectName or "").lower()
            if effect_name:
                mapped_name = map_effect_name(effect_name)
                if mapped_name:
                    modifiers = self._extract_modifiers(nlu_result)
                    try:
                        generated = self.generator_factory.generate_effect(
                            mapped_name, modifiers
                        )
                        if generated:
                            generated_effects.append(generated)
                            seen_match_names.add(generated.matchName)
                    except (ValueError, KeyError) as e:
                        # 生成器不存在时静默跳过
                        pass

        # 2. 从 effect_description.effectKeywords 映射
        if nlu_result.effect_description.effectKeywords:
            mapped = self.parameter_mapper.map(
                nlu_result.effect_description
            )
            mappings.extend(mapped)

        # 3. 对未生成的 mapping 补充生成
        for mapping in mappings:
            if mapping.matchName not in seen_match_names:
                modifiers = self._extract_modifiers(nlu_result)
                try:
                    generated = (
                        self.generator_factory.generate_effect_by_match_name(
                            mapping.matchName, modifiers
                        )
                    )
                    if generated:
                        generated_effects.append(generated)
                        seen_match_names.add(generated.matchName)
                except (ValueError, KeyError):
                    pass

        return mappings, generated_effects

    def _extract_modifiers(self, nlu_result: NLUPipelineResult) -> Dict:
        """从 NLU 结果中提取修饰词上下文

        对齐 TS extractModifiers。
        """
        style = nlu_result.intent.slots.styleName

        # 如果没有显式 style，从 effectName 中提取
        if not style and nlu_result.intent.slots.effectName:
            effect_name = nlu_result.intent.slots.effectName.lower()
            for keyword in _STYLE_KEYWORDS:
                if keyword.lower() in effect_name:
                    style = keyword
                    break

        return {
            "intensity": nlu_result.effect_description.intensityKeywords,
            "color": nlu_result.effect_description.colorKeywords,
            "temporal": nlu_result.effect_description.temporalKeywords,
            "style": style,
        }

    # ------------------------------------------------------------------
    # Silhouette 操作生成
    # ------------------------------------------------------------------

    def generate_silhouette_operations(
        self, intent: Intent, user_input: str = ""
    ) -> List[Dict[str, Any]]:
        """生成 Silhouette 操作序列

        对齐 TS generateSilhouetteOperations。
        使用与 pipeline 兼容的 {command, params} 结构。
        """
        operations: List[Dict[str, Any]] = []
        task_type = self._detect_silhouette_task_type(intent, user_input)

        if not task_type:
            return operations

        if task_type == "roto":
            operations.append({
                "command": "silhouette_roto",
                "params": {
                    "source_path": "",
                    "shape_type": "x-spline",
                    "tracking": "planar",
                    "tolerance": 1.0,
                    "keyframes": 5,
                    "output_format": "exr",
                },
            })
        elif task_type == "track":
            operations.append({
                "command": "silhouette_track",
                "params": {
                    "source_path": "",
                    "track_type": "planar",
                    "search_area": 21,
                    "accuracy": "medium",
                    "output_format": "ae",
                },
            })
        elif task_type == "paint":
            operations.append({
                "command": "silhouette_paint",
                "params": {
                    "source_path": "",
                    "paint_mode": "clone",
                    "brush_size": 25,
                    "brush_hardness": 0.5,
                    "output_format": "png",
                },
            })
        elif task_type == "export":
            operations.append({
                "command": "silhouette_export",
                "params": {
                    "output_format": "ae",
                },
            })

        return operations

    def _detect_silhouette_task_type(
        self, intent: Optional[Intent], user_input: str
    ) -> Optional[str]:
        """从 intent 和用户输入中检测 Silhouette 任务类型"""
        # 优先从 user_input 检测；intent 为 None 时（纯 Silhouette 路由）
        # 仅依赖 user_input
        text = user_input
        if not text and intent is not None:
            text = intent.rawInput
        if not text:
            return None
        if re.search(r"扣|抠|遮罩|蒙版|mask|roto", text, re.IGNORECASE):
            return "roto"
        if re.search(r"跟踪|追踪|track", text, re.IGNORECASE):
            return "track"
        if re.search(r"修|擦|paint|修复|去除|擦除", text, re.IGNORECASE):
            return "paint"
        if re.search(r"export|导出", text, re.IGNORECASE):
            return "export"
        return None

    # ------------------------------------------------------------------
    # 参数优化
    # ------------------------------------------------------------------

    def optimize_parameters(
        self, effects: List[EffectParams]
    ) -> List[OptimizedParameters]:
        """优化参数

        对齐 TS optimizeParameters。
        Python ParameterOptimizer.optimize 接收 ParameterContext，
        所以需要从 EffectParams 构建上下文。
        """
        results: List[OptimizedParameters] = []
        for effect in effects:
            context = self._build_optimizer_context(effect)
            try:
                optimized = self.parameter_optimizer.optimize(context)
                results.append(optimized)
            except Exception:
                # 优化失败时回退到原始参数
                results.append(OptimizedParameters(
                    effect_name=effect.matchName,
                    settings=dict(effect.settings),
                    confidence=effect.confidence,
                    adjustments=[],
                ))
        return results

    def _build_optimizer_context(self, effect: EffectParams) -> ParameterContext:
        """从 EffectParams 构建 ParameterContext"""
        # 从 settings 推断 intensity (0-1)
        # 简化策略：用 effect.confidence 作为 intensity 基线
        intensity = 0.5  # 默认适中
        if effect.confidence > 0.8:
            intensity = 0.7
        elif effect.confidence < 0.6:
            intensity = 0.3

        return ParameterContext(
            effect_name=effect.matchName,
            intensity=intensity,
            style_name=self._target_style,
        )

    # ------------------------------------------------------------------
    # 操作序列构建
    # ------------------------------------------------------------------

    def build_operations(
        self,
        effects: List[EffectParams],
        layer_ref: str = "selected",
        context: Optional[ProjectContext] = None,
    ) -> List[Dict[str, Any]]:
        """构建 AE 操作序列

        对齐 TS buildOperations。
        输出格式与 pipeline.execute() 消费的操作格式一致。
        """
        operations: List[Dict[str, Any]] = []

        # 如果目标是 "selected"，创建基础合成和图层
        if layer_ref == "selected":
            comp_ref = "comp_main"
            target_layer_ref = "layer_text"

            # 创建合成
            width = 1920
            height = 1080
            frame_rate = 30
            duration = 5
            if context:
                if context.compResolution:
                    width, height = context.compResolution[0], context.compResolution[1]
                frame_rate = context.compFrameRate
                duration = int(context.compDuration)

            operations.append({
                "op": "createComp",
                "ref": comp_ref,
                "name": "AI生成合成",
                "width": width,
                "height": height,
                "frameRate": frame_rate,
                "duration": duration,
                "bgColor": [0, 0, 0],
            })

            # 创建文字图层
            operations.append({
                "op": "addLayer",
                "ref": target_layer_ref,
                "compRef": comp_ref,
                "layerType": "text",
                "name": "文本图层",
                "text": "AI效果",
                "fontSize": 72,
                "fillColor": [1, 1, 1],
                "position": [width / 2, height / 2],
            })

            # 添加效果到目标图层
            for i, effect in enumerate(effects):
                ref = f"fx_{effect.matchName.replace(' ', '_')}_{i}"
                operations.append({
                    "op": "addEffect",
                    "ref": ref,
                    "layerRef": target_layer_ref,
                    "matchName": effect.matchName,
                    "name": effect.displayName,
                    "settings": dict(effect.settings),
                })
        else:
            # 直接添加效果到指定图层
            for i, effect in enumerate(effects):
                ref = f"fx_{effect.matchName.replace(' ', '_')}_{i}"
                operations.append({
                    "op": "addEffect",
                    "ref": ref,
                    "layerRef": layer_ref,
                    "matchName": effect.matchName,
                    "name": effect.displayName,
                    "settings": dict(effect.settings),
                })

        return operations

    # ------------------------------------------------------------------
    # 主执行入口
    # ------------------------------------------------------------------

    def execute(
        self,
        input_text: str,
        options: SchedulerOptions = None,
    ) -> SchedulerResult:
        """主执行入口

        对齐 TS execute。完整调度流程：
          1. NLU 管线解析
          2. 路由决策
          3. 根据路由类型生成 Silhouette/AE 操作
          4. 参数优化
          5. 构建 operations
        """
        options = options or SchedulerOptions()
        context = options.project_context
        layer_ref = options.target_layer_ref or "selected"

        # 1. 路由决策（优先于 NLU，因为纯 Silhouette 任务无需 NLU 理解）
        route = self.intent_router.route(input_text, context)

        # 2. 纯 Silhouette 任务：直接生成 Silhouette 操作，无需 NLU
        if route.type == "silhouette_only":
            silhouette_ops = self.generate_silhouette_operations(
                None, input_text
            )
            return SchedulerResult(
                success=len(silhouette_ops) > 0,
                route=route,
                silhouette_operations=silhouette_ops,
                confidence=route.confidence,
                error=None if silhouette_ops
                else "未能生成 Silhouette 操作",
            )

        # 3. NLU 管线（AE / hybrid / unknown 任务需要 NLU 理解）
        nlu_result = self.run_nlu_pipeline(input_text, context)

        if not nlu_result.understood:
            return SchedulerResult(
                success=False,
                intent=nlu_result.intent,
                effect_description=nlu_result.effect_description,
                confidence=nlu_result.intent.confidence,
                needs_clarification=nlu_result.needs_clarification,
                clarification_question=nlu_result.clarification_question,
                clarification_options=nlu_result.clarification_options,
            )

        # 4. 混合任务：Silhouette + AE
        if route.type == "hybrid":
            silhouette_ops = self.generate_silhouette_operations(
                nlu_result.intent, input_text
            )

            # 混合任务：同时生成 AE 操作
            if route.ae_operations:
                mappings, generated_effects = self.generate_parameters(
                    nlu_result
                )
                optimizations: List[OptimizedParameters] = []
                optimized_effects = generated_effects

                if options.enable_optimization:
                    optimizations = self.optimize_parameters(
                        generated_effects
                    )
                    optimized_effects = [
                        OptimizedParameters(
                            effect_name=o.effect_name,
                            settings=o.settings,
                            confidence=o.confidence,
                        ) for o in optimizations
                    ]
                    # 如果优化成功，用优化后的参数更新 effects
                    if len(optimizations) == len(generated_effects):
                        updated_effects = []
                        for orig, opt in zip(generated_effects, optimizations):
                            updated_effects.append(EffectParams(
                                matchName=orig.matchName,
                                displayName=orig.displayName,
                                settings=opt.settings,
                                confidence=opt.confidence,
                            ))
                        optimized_effects = updated_effects

                operations = self.build_operations(
                    optimized_effects, layer_ref, context
                )

                return SchedulerResult(
                    success=len(silhouette_ops) > 0 and len(operations) > 0,
                    intent=nlu_result.intent,
                    effect_description=nlu_result.effect_description,
                    mappings=mappings,
                    generated_effects=generated_effects,
                    optimizations=optimizations,
                    operations=operations,
                    silhouette_operations=silhouette_ops,
                    route=route,
                    confidence=nlu_result.intent.confidence,
                    needs_clarification=False,
                )

            # 纯 Silhouette 任务
            return SchedulerResult(
                success=len(silhouette_ops) > 0,
                intent=nlu_result.intent,
                effect_description=nlu_result.effect_description,
                silhouette_operations=silhouette_ops,
                route=route,
                confidence=nlu_result.intent.confidence,
                needs_clarification=False,
                error=None if silhouette_ops else "未能生成 Silhouette 操作",
            )

        # 4. 纯 AE 任务
        mappings, generated_effects = self.generate_parameters(nlu_result)

        optimizations: List[OptimizedParameters] = []
        optimized_effects = generated_effects

        if options.enable_optimization:
            optimizations = self.optimize_parameters(generated_effects)
            if len(optimizations) == len(generated_effects):
                updated_effects = []
                for orig, opt in zip(generated_effects, optimizations):
                    updated_effects.append(EffectParams(
                        matchName=orig.matchName,
                        displayName=orig.displayName,
                        settings=opt.settings,
                        confidence=opt.confidence,
                    ))
                optimized_effects = updated_effects

        operations = self.build_operations(
            optimized_effects, layer_ref, context
        )

        if not operations:
            return SchedulerResult(
                success=False,
                intent=nlu_result.intent,
                effect_description=nlu_result.effect_description,
                mappings=mappings,
                generated_effects=generated_effects,
                optimizations=optimizations,
                route=route,
                confidence=nlu_result.intent.confidence,
                needs_clarification=False,
                error="未能生成任何操作",
            )

        return SchedulerResult(
            success=True,
            intent=nlu_result.intent,
            effect_description=nlu_result.effect_description,
            mappings=mappings,
            generated_effects=generated_effects,
            optimizations=optimizations,
            operations=operations,
            route=route,
            confidence=nlu_result.intent.confidence,
            needs_clarification=False,
        )

    # ------------------------------------------------------------------
    # 上下文管理
    # ------------------------------------------------------------------

    def set_context(self, options: SchedulerOptions) -> None:
        """更新调度器上下文

        对齐 TS setContext。
        """
        if options.project_context:
            ctx = options.project_context
            self.parameter_mapper = ParameterMapper(MapperContext(
                compWidth=ctx.compResolution[0] if ctx.compResolution else None,
                compHeight=ctx.compResolution[1] if ctx.compResolution else None,
                frameRate=ctx.compFrameRate,
                duration=ctx.compDuration,
            ))
            self.generator_factory = EffectGeneratorFactory(GeneratorContext(
                compWidth=ctx.compResolution[0] if ctx.compResolution else None,
                compHeight=ctx.compResolution[1] if ctx.compResolution else None,
                frameRate=ctx.compFrameRate,
                duration=ctx.compDuration,
            ))
        if options.target_style:
            self._target_style = options.target_style
        if options.performance_mode is not None:
            self._performance_mode = options.performance_mode

    # ------------------------------------------------------------------
    # 查询 API
    # ------------------------------------------------------------------

    def list_supported_effects(self) -> List[str]:
        """列出所有支持的效果名"""
        return self.generator_factory.list_available_generators()

    def get_effect_count(self) -> int:
        """返回支持的效果总数"""
        return self.generator_factory.get_effect_count()

    def get_generator_info(
        self, effect_name: str
    ) -> Optional[Dict[str, str]]:
        """获取效果生成器信息"""
        name_map = {
            "glow": {"displayName": "Glow", "matchName": "ADBE Glo2"},
            "colorkey": {"displayName": "Color Key",
                         "matchName": "ADBE Color Key"},
            "ccparticleworld": {"displayName": "CC Particle World",
                                "matchName": "CC Particle World"},
            "fractalnoise": {"displayName": "Fractal Noise",
                             "matchName": "ADBE Fractal Noise"},
            "ramp": {"displayName": "Ramp", "matchName": "ADBE Ramp"},
            "blur": {"displayName": "Gaussian Blur",
                     "matchName": "ADBE Gaussian Blur 2"},
            "directionalblur": {"displayName": "Directional Blur",
                                "matchName": "ADBE Directional Blur"},
            "colorbalance": {"displayName": "Color Balance",
                             "matchName": "ADBE Color Balance"},
            "levels": {"displayName": "Levels",
                       "matchName": "ADBE Protractor2"},
            "dropshadow": {"displayName": "Drop Shadow",
                           "matchName": "ADBE Drop Shadow"},
            "fill": {"displayName": "Fill", "matchName": "ADBE Fill"},
            "stroke": {"displayName": "Stroke", "matchName": "ADBE Stroke"},
            "vignette": {"displayName": "Vignette",
                         "matchName": "CC Vignette"},
            "roughenedges": {"displayName": "Roughen Edges",
                             "matchName": "ADBE Roughen Edges"},
        }
        return name_map.get(effect_name.lower())


# ============================================================================
# 模块级默认实例
# ============================================================================

ai_scheduler = AIScheduler()


# ============================================================================
# 模块自测
# ============================================================================

if __name__ == "__main__":
    print("=== AI Scheduler 自测 ===")

    scheduler = AIScheduler()
    print(f"支持效果数: {scheduler.get_effect_count()}")

    # 测试 1：纯 AE 任务
    print("\n--- 测试 1: 纯 AE 任务 ---")
    result = scheduler.execute("加发光")
    print(f"success: {result.success}")
    print(f"intent.type: {result.intent.type if result.intent else None}")
    print(f"route.type: {result.route.type if result.route else None}")
    print(f"operations: {len(result.operations)}")
    print(f"generated_effects: {len(result.generated_effects)}")
    if result.generated_effects:
        fx = result.generated_effects[0]
        print(f"  第一个效果: {fx.displayName} ({fx.matchName})")
        print(f"  settings keys: {list(fx.settings.keys())}")
    if result.error:
        print(f"error: {result.error}")

    # 测试 2：混合任务
    print("\n--- 测试 2: 混合任务 ---")
    result2 = scheduler.execute("扣掉埙玉然后加发光")
    print(f"success: {result2.success}")
    print(f"route.type: {result2.route.type if result2.route else None}")
    print(f"silhouette_ops: {len(result2.silhouette_operations)}")
    print(f"ae_operations: {len(result2.operations)}")
    if result2.silhouette_operations:
        print(f"  sil cmd: {result2.silhouette_operations[0]['command']}")

    # 测试 3：纯 Silhouette 任务
    print("\n--- 测试 3: 纯 Silhouette 任务 ---")
    result3 = scheduler.execute("抠像")
    print(f"success: {result3.success}")
    print(f"route.type: {result3.route.type if result3.route else None}")
    print(f"silhouette_ops: {len(result3.silhouette_operations)}")

    print("\n=== 自测完成 ===")

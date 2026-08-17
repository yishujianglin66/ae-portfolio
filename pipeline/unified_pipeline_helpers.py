"""pipeline/unified_pipeline_helpers.py — 学习/特效栈/阶段运行 (从 unified_pipeline 拆出)

2026-08-14 从 pipeline/unified_pipeline.py 拆出的三个大方法体:
  - run_learn(self)                        (_run_learn, 369 行)
  - build_effect_stack_from_vrs(self, ...) (_build_effect_stack_from_vrs, 354 行)
  - run_stage(self, ...)                   (_run_stage, 178 行)

原方法均变薄委托, 行为等价。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional



def run_learn(self) -> Dict:
    """学习阶段 (v2 新增)：将反馈写入 KB + 生成迭代建议

    S4闭环: 消费VMAF worst_segment信号，生成精准时间点修复建议
    - worst_segment.timestamp_sec → 下一轮execute在该时间点插入关键帧/增强效果
    - worst_segment.frame_index → 标记问题帧，供FeedbackExecutor精准修复
    """
    verify = self._results.get("verify", StageResult(stage="verify", status=StageStatus.FAILED))
    if verify.status != StageStatus.DONE:
        return {"learned": False, "reason": "No verification data"}

    # S4: 提取VMAF worst_segment信号，生成精准修复建议
    worst_segment_adjustments = []
    vmaf_data = verify.data.get("vmaf", {})
    worst_segment = vmaf_data.get("worst_segment", {})
    if worst_segment and worst_segment.get("timestamp_sec", 0) > 0:
        ts = worst_segment["timestamp_sec"]
        frame_idx = worst_segment.get("frame_index", 0)
        self._log(
            f"[S4] VMAF worst segment at t={ts:.2f}s (frame={frame_idx}), "
            f"generating targeted repair adjustment"
        )
        worst_segment_adjustments = [
            {
                "stage": "execute",
                "param": "keyframe_insert",
                "value": ts,
                "reason": f"VMAF worst segment at {ts:.2f}s, insert keyframe for stability",
                "frame_index": frame_idx,
            },
            {
                "stage": "execute",
                "param": "effect_intensity_boost",
                "value": ts,
                "reason": f"Enhance effects near {ts:.2f}s to mask quality drop",
                "frame_index": frame_idx,
            },
        ]

    # S5: 持久化学习闭环 - 将本次执行记录写入学习样本库
    # 修复历史缺陷：原 _run_learn 只调 FeedbackLoop（写质检报告），从不调
    # learning.PersistentLearningLoop（真正学习）。此处补齐接线，让 170+ 次
    # 渲染的经验能自动沉淀为参数模板 + 置信度调整 + 执行记录。
    learning_stats: Optional[Dict] = None
    try:
        from learning.persistent_learning_loop import PersistentLearningLoop
        from learning.learning_loop import (
            ExpectedParameters,
            ExpectedProperty,
            ExecutionResult as LLExecutionResult,
            VerificationResult as LLVerificationResult,
        )

        # 构建 ExpectedParameters（从 plan 阶段提取效果栈）
        plan_data_for_learn = self._results.get(
            "plan", StageResult(stage="plan", status=StageStatus.DONE)
        ).data or {}
        effect_stack = plan_data_for_learn.get("effect_stack", [])
        primary_effect = effect_stack[0] if effect_stack else {}
        expected = ExpectedParameters(
            comp_name=self.run_id,
            layer_index=0,
            effect_match_name=primary_effect.get("matchName")
            or primary_effect.get("id", ""),
            effect_name=primary_effect.get("name", ""),
            properties=[
                ExpectedProperty(name=k, value=v)
                for k, v in primary_effect.get("params", {}).items()
            ],
        )

        # 构建 ExecutionResult（从 execute 阶段提取）
        exec_stage = self._results.get(
            "execute", StageResult(stage="execute", status=StageStatus.FAILED)
        )
        exec_success = exec_stage.status == StageStatus.DONE
        execution = LLExecutionResult(
            success=exec_success,
            error_code=None if exec_success else "EXECUTE_FAILED",
            error_message=None
            if exec_success
            else (exec_stage.error or "execute stage failed"),
            effect_name=primary_effect.get("name", ""),
            execution_time_ms=exec_stage.data.get("execution_time_ms")
            if exec_stage.data
            else None,
        )

        # 构建 VerificationResult（从 verify.data 提取）
        # 【H级修复P2-2-A#1b】如果 QA 结果本身是异常样本，跳过写 PersistentLearningLoop
        # （score=None 或 is_error_sample=True），避免垃圾数据污染模板/置信度
        is_error_sample = verify.data.get("is_error_sample", False)
        raw_score = verify.data.get("score")
        if is_error_sample or raw_score is None:
            self._log(
                f"[S5] QA result is error sample (score={raw_score!r}), "
                "SKIPPING PersistentLearningLoop write to prevent contamination",
                "WARN",
            )
            raise RuntimeError("verify_is_error_sample")  # 进入外层 except，不影响主管线
        score = float(raw_score)
        recommendations = verify.data.get("recommendations", []) or []
        verification = LLVerificationResult(
            passed=score >= 60,
            deviation_score=max(0.0, (100 - score) / 100),
            reason=recommendations[0] if recommendations else None,
        )

        # 推理路径（从 plan 阶段提取，若有）
        reasoning_path = plan_data_for_learn.get("reasoning_path") or [
            plan_data_for_learn.get("strategy", "default")
        ]

        # 用户输入（从配置提取）
        user_input = self.config.input_topic or self.run_id

        # 调用持久化学习循环（失败不影响主管线）
        learner = PersistentLearningLoop()
        learner.record_execution(
            user_input=user_input,
            intent_type=getattr(self.config, "mode", "pipeline"),
            expected=expected,
            execution=execution,
            verification=verification,
            user_feedback=None,  # 后续可接前端评分
            reasoning_path=reasoning_path,
        )
        learning_stats = learner.get_stats()
        self._log(
            f"[S5] LearningLoop recorded: "
            f"{learning_stats.get('execution_records_count', 0)} total records, "
            f"{learning_stats.get('templates_count', 0)} templates"
        )
    except Exception as e:
        self._log(f"[S5] PersistentLearningLoop failed: {e}", "WARN")

    # S7: BayesianParameterOptimizer 观测写入
    # 闭合贝叶斯优化器写侧断点：让 verify 阶段的质量分数、渲染时间、文件大小
    # 真正被 observe() 消化，下次 recommend() 才能基于真实数据拟合 GP 模型。
    bayesian_observed: Optional[Dict[str, Any]] = None
    try:
        from core.bayesian_optimizer import get_optimizer, PARAMETER_SPACES
        from learning.learning_bridge import LearningBridge

        optimizer = get_optimizer()
        raw_score = verify.data.get("score")
        is_error_sample = verify.data.get("is_error_sample", False)
        # 【H级修复P2-2-A#1c】异常样本不写贝叶斯优化器（score=None或标记为error）
        if is_error_sample or raw_score is None:
            self._log(
                f"[S7] QA is error sample (score={raw_score!r}), "
                "SKIPPING Bayesian observe to prevent GP model corruption",
                "WARN",
            )
            raise RuntimeError("verify_is_error_sample")  # 进入外层 except，不影响主管线
        score = float(raw_score)
        render_stage = self._results.get(
            "render", StageResult(stage="render", status=StageStatus.FAILED)
        )
        render_time_sec = 0.0
        file_size_mb = 0.0
        if render_stage and render_stage.data:
            render_time_sec = float(render_stage.data.get("render_time_sec", 0) or 0)
            output_path = render_stage.data.get("output_path", "")
            if output_path:
                try:
                    p = Path(output_path)
                    if p.exists():
                        file_size_mb = p.stat().st_size / (1024 * 1024)
                except Exception:
                    pass

        exec_stage = self._results.get(
            "execute", StageResult(stage="execute", status=StageStatus.FAILED)
        )
        exec_success = exec_stage.status == StageStatus.DONE

        plan_data_for_bo = self._results.get(
            "plan", StageResult(stage="plan", status=StageStatus.DONE)
        ).data or {}
        effect_stack_bo = plan_data_for_bo.get("effect_stack", [])

        observed_effects: List[str] = []
        for effect in effect_stack_bo:
            effect_name = effect.get("name", "") or effect.get("effectName", "")
            match_name = effect.get("matchName", "") or effect.get("id", "")
            params = effect.get("params", {}) or {}
            if not params:
                continue

            # 映射到 PARAMETER_SPACES 的 key
            effect_key = effect_name if effect_name in PARAMETER_SPACES else None
            if not effect_key:
                short = LearningBridge._extract_short_effect_name(match_name, effect_name)
                if short and short in PARAMETER_SPACES:
                    effect_key = short

            if not effect_key:
                continue  # 不在参数空间中，跳过

            # 只保留在参数空间中定义的参数（避免维度不匹配）
            spec_names = {p.name for p in PARAMETER_SPACES[effect_key]}
            raw_valid = {k: v for k, v in params.items() if k in spec_names}
            if not raw_valid:
                continue
            # 【H级修复P2-2-A#3】强制所有参数值转 float：
            # - enum字符串不转（如 "From Behind"）→ 单个skip；其余合格参数照常
            # - 数字字符串 → float
            # - None → skip；int→float；其他类型兜底0.0
            valid_params: Dict[str, float] = {}
            for _k, _v in raw_valid.items():
                if _v is None:
                    continue
                if isinstance(_v, (int, float)):
                    valid_params[_k] = float(_v)
                elif isinstance(_v, str):
                    try:
                        valid_params[_k] = float(_v)
                    except ValueError:
                        self._log(
                            f"[LEARN/S7] effect={effect_key} param={_k} semantic_str="
                            f"{_v!r} (non-numeric), SKIP param (not entire effect)",
                            "DEBUG",
                        )
                        continue
                else:
                    valid_params[_k] = 0.0
            if not valid_params:
                self._log(
                    f"[LEARN/S7] effect={effect_key}: ALL params are non-numeric, "
                    "SKIP this effect observe()",
                    "DEBUG",
                )
                continue

            optimizer.observe(
                effect_name=effect_key,
                params=valid_params,
                quality=float(score),
                render_time=render_time_sec,
                file_size=file_size_mb,
                success=exec_success,
            )
            observed_effects.append(effect_key)

        if observed_effects:
            bayesian_observed = {
                "observed_effects": observed_effects,
                "quality": float(score),
                "render_time_sec": render_time_sec,
                "file_size_mb": file_size_mb,
            }
            self._log(
                f"[S7] BayesianOptimizer observed: effects={observed_effects}, "
                f"quality={score:.1f}, render_time={render_time_sec:.1f}s, "
                f"size={file_size_mb:.1f}MB"
            )
    except Exception as e:
        self._log(f"[S7] BayesianOptimizer observe failed: {e}", "WARN")

    # S8: MemoryStore 经验写入
    # 闭合记忆库写侧断点：将本次渲染经验以 effect_params 类别写入 MemoryStore，
    # 供下次 plan 阶段通过 LearningBridge._apply_memory_experience() 查询复用。
    memory_written: Optional[Dict[str, Any]] = None
    try:
        from core.memory_store import MemoryStore

        ms = MemoryStore()
        plan_data_for_mem = self._results.get(
            "plan", StageResult(stage="plan", status=StageStatus.DONE)
        ).data or {}
        effect_stack_mem = plan_data_for_mem.get("effect_stack", [])
        score_mem = verify.data.get("score", 0)

        written_keys: List[str] = []
        for effect in effect_stack_mem:
            effect_name = effect.get("name", "") or effect.get("effectName", "")
            match_name = effect.get("matchName", "") or effect.get("id", "")
            params = effect.get("params", {}) or {}
            if not effect_name:
                continue

            mem_key = f"{effect_name}_{match_name}" if match_name else effect_name
            ms.remember(
                category="effect_params",
                key=mem_key,
                content={
                    "params": params,
                    "last_quality_score": float(score_mem),
                    "last_run_id": self.run_id,
                    "match_name": match_name,
                    "user_input": self.config.input_topic,
                },
                tags=["effect", effect_name.lower(), "rendering_experience"],
                confidence=max(0.3, min(0.9, float(score_mem) / 100.0)),
            )
            written_keys.append(mem_key)

        if written_keys:
            memory_written = {"written_keys": written_keys}
            self._log(
                f"[S8] MemoryStore wrote {len(written_keys)} effect_params entries"
            )
    except Exception as e:
        self._log(f"[S8] MemoryStore write failed: {e}", "WARN")

    # 使用 FeedbackLoop 处理质检结果
    try:
        from pipeline.feedback_loop import FeedbackLoop
        fb_loop = FeedbackLoop()

        # 构建管线上下文
        plan_data = self._results.get("plan", StageResult(stage="plan", status=StageStatus.DONE)).data
        context = {
            "style": self._vrs_result.get("style", {}).get("name", ""),
            "effects": [e.get("name", "") for e in plan_data.get("effect_stack", [])],
            "transitions": [t.get("type", "") for t in plan_data.get("transition_plan", [])],
        }

        # 处理反馈
        feedback_result = fb_loop.process(
            run_id=self.run_id,
            quality_result=verify.data,
            pipeline_context=context,
        )

        # S4: 合并worst_segment精准修复建议
        all_adjustments = [
            {"stage": a.target_stage, "param": a.parameter, "reason": a.reason}
            for a in feedback_result.adjustments
        ] + worst_segment_adjustments

        return {
            "learned": True,
            "feedback_id": self.run_id,
            "quality_score": feedback_result.overall_score,
            "issues_found": len(feedback_result.issues),
            "adjustments": all_adjustments,
            "should_retry": feedback_result.should_retry,
            "worst_segment": worst_segment if worst_segment else None,
            "learning_stats": learning_stats,
            "bayesian_observed": bayesian_observed,
            "memory_written": memory_written,
        }
    except Exception as e:
        self._log(f"FeedbackLoop failed: {e}, using basic feedback", "WARN")
        # 降级: 基础反馈写入
        feedback = {
            "quality_score": verify.data.get("score", 0),
            "recommendations": verify.data.get("recommendations", []),
            "style": self._vrs_result.get("style", {}).get("name", ""),
            "effects": [e.get("name", "") for e in self._results.get("plan", StageResult(stage="plan", status=StageStatus.DONE)).data.get("effect_stack", [])],
        }
        self._kb.write_feedback(self.run_id, feedback)
        return {
            "learned": True,
            "feedback_id": self.run_id,
            "quality_score": feedback["quality_score"],
            "adjustments": worst_segment_adjustments,
            "worst_segment": worst_segment if worst_segment else None,
            "learning_stats": learning_stats,
            "bayesian_observed": bayesian_observed,
            "memory_written": memory_written,
        }

# ----------------------------------------------------------------
#  多智能体执行 (v2 新增)
# ----------------------------------------------------------------


def build_effect_stack_from_vrs(
    self, vrs: Dict[str, Any]
) -> tuple:
    """把 VRS 真分析字段直接转换为 effect_stack 条目。

    转换规则（任务规范）：
      - color_grade_cool → name="color_grade", params {temperature:"cool", blue_boost:0.15, red_reduce:0.1}
      - color_grade_warm → name="color_grade", params {temperature:"warm", red_boost:0.15, blue_reduce:0.1}
      - saturation_boost → name="saturation", params {amount:0.8}
      - high_contrast_grade → name="contrast", params {amount:0.4}
      - motion_energy → name="motion_blur", params {intensity:0.5, samples:16}
      - transition_* → name="transition_<type>", params {time, type, confidence}

    然后由 color_palette/rhythm/motion/style_tags 进一步调整：
      - color_palette.temperature 调色温偏移
      - color_palette.saturation/contrast 调饱和度/对比度
      - rhythm.tempo 调转场节奏（fast→fade_in/out 短，slow→长）
      - motion.intensity 调运动模糊强度
      - style_tags 整体调整（vibrant→饱和+10%, dark→亮度+5%, cool_tone→蓝+5%）

    Returns:
        (effect_stack_list, vrs_to_effects_mapping_list)
        mapping 条目形如:
          {"vrs_field":"effects[0].effect_name=color_grade_cool",
           "vrs_value":"color_grade_cool",
           "effect_name":"color_grade",
           "param_path":"params.temperature=cool, params.blue_boost=0.15",
           "reason":"VRS 检测冷色调，注入冷色分级"}
    """
    mapping: List[Dict[str, Any]] = []
    stack: List[Dict[str, Any]] = []

    color_palette = vrs.get("color_palette", {}) or {}
    rhythm = vrs.get("rhythm", {}) or {}
    motion = vrs.get("motion", {}) or {}
    style_tags = vrs.get("style_tags", []) or []
    effects = vrs.get("effects", []) or []

    # ---- 1. VRS effects 直接映射为 effect_stack 条目（高优先级，注入前列）----
    seg_idx = 0
    for eff in effects:
        eff_name = (eff.get("effect_name") or eff.get("name") or "").strip()
        if not eff_name:
            continue
        cat = eff.get("category", "")
        intensity = float(eff.get("intensity", 0.5) or 0.5)
        confidence = float(eff.get("confidence", 0.5) or 0.5)
        eff_lower = eff_name.lower()

        entry: Optional[Dict[str, Any]] = None
        reason = ""

        if eff_lower.startswith("color_grade_"):
            tone = eff_lower.replace("color_grade_", "")  # cool / warm / neutral
            if tone == "cool":
                entry = {
                    "name": "color_grade",
                    "description": f"VRS 检测冷色调 (intensity={intensity:.2f})",
                    "params": {
                        "temperature": "cool",
                        "blue_boost": 0.15,
                        "red_reduce": 0.10,
                        "saturation": 1.20,
                        "contrast": 1.10,
                        "brightness": 0.0,
                    },
                    "duration": 4.0,
                    "timing": f"segment_{seg_idx}",
                    "vrs_source": eff_name,
                    "vrs_confidence": confidence,
                }
                reason = "VRS color_grade_cool → 冷色分级（蓝增红减）"
            elif tone == "warm":
                entry = {
                    "name": "color_grade",
                    "description": f"VRS 检测暖色调 (intensity={intensity:.2f})",
                    "params": {
                        "temperature": "warm",
                        "red_boost": 0.15,
                        "blue_reduce": 0.10,
                        "saturation": 1.20,
                        "contrast": 1.10,
                        "brightness": 0.0,
                    },
                    "duration": 4.0,
                    "timing": f"segment_{seg_idx}",
                    "vrs_source": eff_name,
                    "vrs_confidence": confidence,
                }
                reason = "VRS color_grade_warm → 暖色分级（红增蓝减）"
            else:
                entry = {
                    "name": "color_grade",
                    "description": f"VRS 检测中性色调",
                    "params": {
                        "temperature": "neutral",
                        "saturation": 1.10,
                        "contrast": 1.05,
                        "brightness": 0.0,
                    },
                    "duration": 4.0,
                    "timing": f"segment_{seg_idx}",
                    "vrs_source": eff_name,
                    "vrs_confidence": confidence,
                }
                reason = "VRS color_grade_neutral → 中性分级"

        elif eff_lower == "saturation_boost":
            # amount 映射 intensity 到 0.5~1.0 区间
            amount = max(0.5, min(1.0, intensity))
            entry = {
                "name": "saturation",
                "description": f"VRS 检测高饱和 (saturation={intensity:.2f})",
                "params": {
                    "amount": round(amount, 3),
                    "saturation": 1.30,
                },
                "duration": 4.0,
                "timing": f"segment_{seg_idx}",
                "vrs_source": eff_name,
                "vrs_confidence": confidence,
            }
            reason = "VRS saturation_boost → 饱和度增强"

        elif eff_lower == "high_contrast_grade":
            amount = max(0.3, min(0.6, intensity))
            entry = {
                "name": "contrast",
                "description": f"VRS 检测高对比 (contrast={intensity:.2f})",
                "params": {
                    "amount": round(amount, 3),
                    "contrast": 1.25,
                },
                "duration": 4.0,
                "timing": f"segment_{seg_idx}",
                "vrs_source": eff_name,
                "vrs_confidence": confidence,
            }
            reason = "VRS high_contrast_grade → 对比度增强"

        elif eff_lower == "motion_energy":
            # 运动模糊强度按 motion.intensity 折算
            mi = float(motion.get("intensity", intensity) or intensity)
            blur_strength = max(0.2, min(0.8, mi * 2.0))
            entry = {
                "name": "motion_blur",
                "description": f"VRS 检测高运动能量 (motion={mi:.2f})",
                "params": {
                    "intensity": round(blur_strength, 3),
                    "samples": 16,
                },
                "duration": 4.0,
                "timing": f"segment_{seg_idx}",
                "vrs_source": eff_name,
                "vrs_confidence": confidence,
            }
            reason = "VRS motion_energy → 运动模糊"

        elif eff_lower.startswith("transition_"):
            ttype = eff_lower.replace("transition_", "")
            t_time = eff.get("time", 0.0)
            entry = {
                "name": f"transition_{ttype}",
                "description": f"VRS 检测转场: {ttype} @ {t_time}s",
                "params": {
                    "type": ttype,
                    "time": t_time,
                    "duration": 0.4,
                },
                "duration": 0.4,
                "timing": f"segment_{seg_idx}",
                "vrs_source": eff_name,
                "vrs_confidence": confidence,
            }
            reason = f"VRS transition_{ttype} → 转场效果"

        if entry is not None:
            stack.append(entry)
            mapping.append({
                "vrs_field": f"effects[{seg_idx}].effect_name={eff_name}",
                "vrs_value": eff_name,
                "effect_name": entry["name"],
                "param_path": ", ".join(
                    f"params.{k}={v}" for k, v in entry["params"].items()
                ),
                "reason": reason,
            })
            seg_idx += 1

    # ---- 2. 由 color_palette 调整调色参数（无 color_grade 效果时补一条）----
    has_color_grade = any(e.get("name") == "color_grade" for e in stack)
    if not has_color_grade and color_palette:
        temperature = color_palette.get("temperature", "neutral")
        sat = float(color_palette.get("saturation", 0.4))
        contrast = float(color_palette.get("contrast", 0.2))
        brightness = float(color_palette.get("avg_brightness", 0.5))
        params: Dict[str, Any] = {
            "saturation": round(1.0 + sat * 0.5, 3),
            "contrast": round(1.0 + contrast * 1.0, 3),
            "brightness": round((0.5 - brightness) * 0.1, 3),
        }
        if temperature == "cool":
            params["temperature"] = "cool"
            params["blue_boost"] = 0.10
            params["red_reduce"] = 0.05
        elif temperature == "warm":
            params["temperature"] = "warm"
            params["red_boost"] = 0.10
            params["blue_reduce"] = 0.05
        else:
            params["temperature"] = "neutral"
        entry = {
            "name": "color_grade",
            "description": f"VRS color_palette 驱动 (temp={temperature}, sat={sat:.2f})",
            "params": params,
            "duration": 4.0,
            "timing": f"segment_{seg_idx}",
            "vrs_source": "color_palette",
            "vrs_confidence": 0.6,
        }
        stack.append(entry)
        mapping.append({
            "vrs_field": "color_palette.temperature/saturation/contrast",
            "vrs_value": f"temp={temperature}, sat={sat:.3f}, contrast={contrast:.3f}",
            "effect_name": "color_grade",
            "param_path": ", ".join(f"params.{k}={v}" for k, v in params.items()),
            "reason": "VRS color_palette 无显式 color_grade_* effect，补一条调色",
        })
        seg_idx += 1

    # ---- 3. 由 rhythm.tempo 调整转场/节奏效果 ----
    tempo = (rhythm or {}).get("tempo", "")
    if tempo in ("fast", "slow"):
        if tempo == "fast":
            trans_dur = 0.2
            seg_dur = 1.5
            desc = "VRS tempo=fast → 快速转场+短镜头"
        else:
            trans_dur = 0.6
            seg_dur = 4.0
            desc = "VRS tempo=slow → 慢速转场+长镜头"
        entry = {
            "name": "rhythm_transition",
            "description": desc,
            "params": {
                "tempo": tempo,
                "transition_duration": trans_dur,
                "segment_duration": seg_dur,
            },
            "duration": seg_dur,
            "timing": f"segment_{seg_idx}",
            "vrs_source": "rhythm.tempo",
            "vrs_confidence": 0.7,
        }
        stack.append(entry)
        mapping.append({
            "vrs_field": "rhythm.tempo",
            "vrs_value": tempo,
            "effect_name": "rhythm_transition",
            "param_path": f"params.transition_duration={trans_dur}, params.segment_duration={seg_dur}",
            "reason": desc,
        })
        seg_idx += 1

    # ---- 4. 由 motion.intensity 调整运动模糊（无 motion_energy 时补）----
    has_motion_blur = any(e.get("name") == "motion_blur" for e in stack)
    if not has_motion_blur and motion:
        mi = float(motion.get("intensity", 0.0))
        if mi > 0.05:
            blur_strength = max(0.15, min(0.6, mi * 2.0))
            entry = {
                "name": "motion_blur",
                "description": f"VRS motion.intensity={mi:.3f} → 运动模糊",
                "params": {
                    "intensity": round(blur_strength, 3),
                    "samples": 12,
                },
                "duration": 4.0,
                "timing": f"segment_{seg_idx}",
                "vrs_source": "motion.intensity",
                "vrs_confidence": 0.7,
            }
            stack.append(entry)
            mapping.append({
                "vrs_field": "motion.intensity",
                "vrs_value": round(mi, 4),
                "effect_name": "motion_blur",
                "param_path": f"params.intensity={blur_strength:.3f}, params.samples=12",
                "reason": "VRS motion.intensity 较高，补运动模糊",
            })
            seg_idx += 1

    # ---- 5. 由 style_tags 整体微调效果强度 ----
    if style_tags:
        style_adjustments: Dict[str, Any] = {}
        if "vibrant" in style_tags:
            style_adjustments["saturation_boost_pct"] = 10
        if "dark" in style_tags:
            style_adjustments["brightness_boost_pct"] = 5
        if "cool_tone" in style_tags:
            style_adjustments["blue_boost_pct"] = 5
        if "warm_tone" in style_tags:
            style_adjustments["red_boost_pct"] = 5
        if "high_contrast" in style_tags:
            style_adjustments["contrast_boost_pct"] = 8
        if style_adjustments:
            # 应用到 stack 中已有的 color_grade / saturation / contrast 效果
            for entry in stack:
                n = entry.get("name", "")
                p = entry.get("params", {}) or {}
                if n == "color_grade" and "saturation" in p:
                    if "saturation_boost_pct" in style_adjustments:
                        p["saturation"] = round(
                            float(p["saturation"]) * (1 + style_adjustments["saturation_boost_pct"] / 100), 3)
                    if "brightness_boost_pct" in style_adjustments:
                        p["brightness"] = round(
                            float(p.get("brightness", 0.0)) + style_adjustments["brightness_boost_pct"] / 100, 3)
                    if "blue_boost_pct" in style_adjustments and "blue_boost" in p:
                        p["blue_boost"] = round(
                            float(p["blue_boost"]) * (1 + style_adjustments["blue_boost_pct"] / 100), 3)
                    if "red_boost_pct" in style_adjustments and "red_boost" in p:
                        p["red_boost"] = round(
                            float(p["red_boost"]) * (1 + style_adjustments["red_boost_pct"] / 100), 3)
                    if "contrast_boost_pct" in style_adjustments and "contrast" in p:
                        p["contrast"] = round(
                            float(p["contrast"]) * (1 + style_adjustments["contrast_boost_pct"] / 100), 3)
                elif n == "saturation" and "amount" in p:
                    if "saturation_boost_pct" in style_adjustments:
                        p["amount"] = round(
                            float(p["amount"]) * (1 + style_adjustments["saturation_boost_pct"] / 100), 3)
                elif n == "contrast" and "amount" in p:
                    if "contrast_boost_pct" in style_adjustments:
                        p["amount"] = round(
                            float(p["amount"]) * (1 + style_adjustments["contrast_boost_pct"] / 100), 3)
            mapping.append({
                "vrs_field": "style_tags",
                "vrs_value": style_tags,
                "effect_name": "* (color_grade/saturation/contrast)",
                "param_path": ", ".join(f"{k}={v}%" for k, v in style_adjustments.items()),
                "reason": "VRS style_tags 全局微调效果强度",
            })

    # 保证至少 2 条
    if len(stack) < 2:
        for eff in self._build_default_effect_stack():
            if len(stack) >= 2:
                break
            n = (eff.get("name") or "").lower()
            if not any(n in (m.get("name") or "").lower() for m in stack):
                eff["vrs_source"] = "default_padding"
                stack.append(eff)

    return stack, mapping


def run_stage(self, stage_name: str) -> StageResult:
    """运行单个阶段 (增强版: P0错误记忆 + P3自适应降级)"""
    handlers = {
        "perceive": self._run_perceive,
        "analyze": self._run_analyze,
        "plan": self._run_plan,
        "execute": self._run_execute,
        "render": self._run_render,
        "verify": self._run_verify,
        "learn": self._run_learn,
    }
    handler = handlers.get(stage_name)
    if not handler:
        return StageResult(stage=stage_name, status=StageStatus.FAILED,
                           error=f"Unknown stage: {stage_name}")

    # 检查阶段依赖
    deps = {"execute": ["plan"], "render": ["execute"], "verify": ["render"], "learn": ["verify"]}
    for dep in deps.get(stage_name, []):
        dep_result = self._results.get(dep)
        if dep_result and dep_result.status == StageStatus.FAILED:
            return StageResult(stage=stage_name, status=StageStatus.SKIPPED,
                               error=f"Skipped: dependency '{dep}' failed")

    self._log(f"Stage [{stage_name}] START")
    start = time.time()
    max_retries = 2 if stage_name in ("execute", "render") else 1
    last_error = ""
    last_exception = None

    # P4: 启动阶段 span
    stage_span = None
    if self.trace_prop and self._root_span:
        stage_span = self.trace_prop.start_span(
            stage=stage_name,
            parent=self._root_span,
            attributes={"iteration": self._iteration, "retries": max_retries},
        )

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                self._log(f"Stage [{stage_name}] retry {attempt}/{max_retries}")
                
                # P0: 重试前查询错误记忆，获取已知修复方案
                if last_exception:
                    fix = self._query_error_memory(last_exception, stage_name)
                    if fix:
                        self._log(f"[P0] Found known fix: {fix.get('fix_applied', 'unknown')} "
                                  f"(confidence: {fix.get('confidence', 0):.0%})")
                        # 将修复建议注入上下文
                        self._results[f"_fix_hint_{stage_name}"] = StageResult(
                            stage=f"_fix_hint_{stage_name}",
                            status=StageStatus.DONE,
                            data={"fix": fix}
                        )
                    else:
                        # P1: 错误记忆无匹配时，尝试LLM辅助诊断
                        diag = self._llm_diagnose_error(last_exception, stage_name)
                        if diag and diag.get("confidence", 0) >= 0.5:
                            self._log(f"[P1] LLM diagnosis: {diag.get('fix_description', '')} "
                                      f"(confidence: {diag.get('confidence', 0):.0%})")
                            self._results[f"_fix_hint_{stage_name}"] = StageResult(
                                stage=f"_fix_hint_{stage_name}",
                                status=StageStatus.DONE,
                                data={"diagnosis": diag}
                            )
            
            data = handler()
            dur = time.time() - start
            self._log(f"Stage [{stage_name}] DONE ({dur:.1f}s)")
            
            # P3: 记录成功
            if attempt > 1:
                get_fallback_selector().update_success_rate(f"{stage_name}_retry", success=True)
            
            # P4: 结束阶段 span（成功）
            if stage_span and self.trace_prop:
                stage_span.attributes["attempts"] = attempt
                stage_span.attributes["duration_sec"] = dur
                self.trace_prop.end_span(stage_span, status="success")

            # P2.1/P4.3/P4.5: 记录引擎执行 + 注册产物血缘 + 记录性能基线
            self._record_stage_success(stage_name, data, dur)

            return StageResult(stage=stage_name, status=StageStatus.DONE,
                               data=data, duration_sec=dur)
        except Exception as e:
            last_error = str(e)
            last_exception = e
            dur = time.time() - start
            self._log(f"Stage [{stage_name}] attempt {attempt} failed: {e}", "ERROR")
            
            # P0: 记录错误模式
            self._record_error_pattern(e, stage_name, attempt)
            
            # P3: 记录失败
            if attempt > 1:
                get_fallback_selector().update_success_rate(f"{stage_name}_retry", success=False, error=e)
            
            if attempt < max_retries:
                # M1: 因果引擎跨引擎诊断
                causal_hint = self._query_causal_engine(e, stage_name)
                if causal_hint:
                    self._log(f"[M1] Causal engine hint: {causal_hint.get('reasoning', '')}")
                    self._results[f"_causal_hint_{stage_name}"] = StageResult(
                        stage=f"_causal_hint_{stage_name}",
                        status=StageStatus.DONE,
                        data={"causal_hint": causal_hint}
                    )

                # S5: 消费上一轮的causal_hint，根据因果效应决定重试策略
                prev_hint_result = self._results.get(f"_causal_hint_{stage_name}")
                if prev_hint_result and prev_hint_result.status == StageStatus.DONE:
                    hint_data = (prev_hint_result.data or {}).get("causal_hint", {})
                    causal_effect = hint_data.get("causal_effect", "")
                    recommended_engine = hint_data.get("recommended_engine", "")
                    confidence = hint_data.get("confidence", 0)

                    if confidence > 0.5 and recommended_engine:
                        self._log(
                            f"[S5] Causal hint recommends switching to '{recommended_engine}' "
                            f"(effect={causal_effect}, confidence={confidence:.2f})"
                        )
                        # 标记引擎切换，供handler读取
                        self._results[f"_engine_switch_{stage_name}"] = StageResult(
                            stage=f"_engine_switch_{stage_name}",
                            status=StageStatus.DONE,
                            data={
                                "recommended_engine": recommended_engine,
                                "reason": causal_effect,
                                "confidence": confidence,
                            }
                        )
                        # 对于execute/render阶段，标记降级
                        if stage_name in ("execute", "render") and recommended_engine in ("ffmpeg", "moviepy"):
                            self._log(f"[S5] Switching {stage_name} to {recommended_engine} based on causal hint")
                            self._results["_strategy_fallback"] = StageResult(
                                stage="_strategy_fallback", status=StageStatus.DONE,
                                data={"prefer_ffmpeg": True, "source": "causal_hint"}
                            )

                # P3: 使用自适应降级选择器决定重试策略
                selector = get_fallback_selector()
                fallback_path = selector.select_fallback(
                    failed_stage=stage_name,
                    error=e,
                    available_paths=["retry", "delayed_retry", "skip"]
                )

                if fallback_path == "skip":
                    self._log(f"[P3] Fallback selector suggests skip for {stage_name}")
                    break
                elif fallback_path == "delayed_retry":
                    time.sleep(2)  # 延迟重试
                else:
                    time.sleep(1)  # 普通重试

    self._log(f"Stage [{stage_name}] FAILED after {max_retries} attempts", "ERROR")

    # P1-3: 失败复盘 — 自动根因分析 + 教训蒸馏
    self._trigger_failure_postmortem(stage_name, last_error, last_exception)

    # P2.1: 记录引擎失败执行
    self._record_stage_failure(stage_name, last_error, time.time() - start)

    # P4: 结束阶段 span（失败）
    if stage_span and self.trace_prop:
        stage_span.attributes["attempts"] = max_retries
        stage_span.attributes["error"] = last_error
        self.trace_prop.end_span(
            stage_span, status="error",
            error=Exception(last_error) if last_error else None,
        )
    
    return StageResult(stage=stage_name, status=StageStatus.FAILED,
                       error=last_error, duration_sec=time.time() - start)


# ── 宿主符号接入 (2026-08-14): 拆分后本模块运行时需要 unified_pipeline
# 定义的 StageResult/StageStatus。底部导入两种加载路径均安全
# (unified_pipeline 尾部 import 本模块时宿主名字已定义; 直接 import 时
# 触发宿主加载, 其薄委托在本模块函数定义完成后才执行)。
try:
    from pipeline.unified_pipeline import StageResult, StageStatus  # noqa: E402
except ImportError:  # 极端兜底
    StageResult = StageStatus = None  # type: ignore

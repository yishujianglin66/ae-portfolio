"""pipeline/unified_pipeline_verify.py — 质检阶段 (从 unified_pipeline 拆出)

2026-08-14 从 pipeline/unified_pipeline.py (5394 行) 拆出的 _run_verify
方法体 (255 行)。原方法变薄委托: UnifiedPipeline._run_verify() ->
run_verify(self), 行为等价。
"""
from __future__ import annotations

from typing import Any, Dict



def run_verify(self) -> Dict:
    """质检阶段 (v2 新增)：VideoQualityAssessor 真实评分 + VMAF 感知质量评估
        + FeedbackExecutor.execute_multi_pass 多轮自动优化

    【P0-1修复】原实现调用不存在的 QualityAgent，导致 score 永远为 None。
    现在优先使用 VideoQualityAssessor (ffprobe + OpenCV) 输出真实分数。

    【P1-多轮优化】当初始分数 < min_quality_score 且 enable_feedback_loop=True 时，
    自动调用 FeedbackExecutor.execute_multi_pass 对 render 输出做多轮 FFmpeg 增强，
    直到达标或用尽 max_quality_iterations (上限5)。优化后若分数提升则替换 render 输出；
    若分数反而下降则保留原始视频。返回 optimization_history 分数曲线。
    """
    render_result = self._results.get("render", StageResult(stage="render", status=StageStatus.FAILED))
    if render_result.status != StageStatus.DONE:
        return {"verified": False, "reason": "No render output"}

    output_path = render_result.data.get("output_path", "")
    if not output_path or not Path(output_path).exists():
        return {"verified": False, "reason": "Output file not found"}

    # 项目2集成: VMAF 感知质量评估
    vmaf_result = self._assess_vmaf_quality(output_path)

    # 【P0-1】优先使用 VideoQualityAssessor (ffprobe + OpenCV 真实分析)
    qa_result: Dict[str, Any]
    try:
        from pipeline.video_quality_assessor import VideoQualityAssessor
        assessor = VideoQualityAssessor(
            ffmpeg_bin=self._cfg("ffmpeg_bin", "") or _paths_ffmpeg()
        )
        result = assessor.assess(
            video_path=output_path,
            reference_path=self.config.reference_video or "",
            min_score=float(self.config.min_quality_score),
        )
        qa_result = {
            "verified": bool(result.get("passed", False)),
            "score": float(result.get("overall_score", 0)),
            "checks": result.get("checks", {}),
            "recommendations": result.get("recommendations", []),
            "assessor": "VideoQualityAssessor",
        }
        self._log(
            f"[VERIFY] VQA score={qa_result['score']:.1f} passed={qa_result['verified']} "
            f"checks={list(qa_result['checks'].keys())}"
        )
    except Exception as e:
        # 【H级修复P2-2-A#1】明确标记异常样本：score置None + is_error_sample=True
        # 防止 _run_learn 把 score=50 这种假值喂给贝叶斯/记忆系统，污染学习数据
        qa_result = {
            "verified": False,
            "score": None,
            "is_error_sample": True,
            "reason": f"VQA failed: {type(e).__name__}: {str(e)[:200]}",
        }
        self._log(f"[VERIFY] VQA failed: {e}", "WARN")

    # 合并 VMAF 结果
    if vmaf_result:
        qa_result["vmaf"] = vmaf_result
        # 如果 VMAF 分数可用，且 verify 本身不是异常样本，则修正总分
        if vmaf_result.get("score", 0) > 0 and not qa_result.get("is_error_sample", False):
            try:
                base = float(qa_result.get("score", 0) or 0)
                vmaf_s = float(vmaf_result["score"])
                qa_result["score"] = round((base + vmaf_s) / 2, 1)
            except (TypeError, ValueError):
                pass  # 保持原值
        # 异常样本但 VMAF 有值时，仅记录原始VMAF数据，不产出合成 score（仍保持 None）

    # 【P1-多轮自动优化】初始分不达标 + 反馈闭环启用 → 触发 execute_multi_pass
    optimization_history: List[Dict[str, Any]] = []
    optimization_applied = False
    optimization_reasoning = ""
    error_code = ""
    try:
        raw_initial = qa_result.get("score")
        initial_score = 0.0 if raw_initial is None else float(raw_initial)
    except (TypeError, ValueError):
        initial_score = 0.0

    threshold = float(self.config.min_quality_score)
    # 异常样本 (VQA 失败) 不进入多轮优化，避免在不可评分视频上反复 FFmpeg
    should_optimize = (
        self.config.enable_feedback_loop
        and not qa_result.get("is_error_sample", False)
        and initial_score < threshold
    )
    if should_optimize:
        self._log(
            f"[VERIFY] score={initial_score:.1f} < threshold={threshold:.1f}, "
            f"triggering FeedbackExecutor.execute_multi_pass"
        )
        try:
            from pipeline.feedback_executor import FeedbackExecutor
            from pipeline.video_quality_assessor import VideoQualityAssessor as _VQA

            executor = FeedbackExecutor(self.config.ffmpeg_bin or "")
            if executor.engine is None:
                raise RuntimeError("FFmpegEditEngine unavailable")

            vqa_for_pass = _VQA(
                ffmpeg_bin=self._cfg("ffmpeg_bin", "") or _paths_ffmpeg()
            )
            ref_path = self.config.reference_video or ""

            def _quality_report_fn(video_path: str) -> Dict[str, Any]:
                """execute_multi_pass 期望的质检回调: (filepath) -> report dict
                report 需含 score/checks/suggestions, VQA.assess 已兼容。"""
                return vqa_for_pass.assess(
                    video_path=video_path,
                    reference_path=ref_path,
                    min_score=threshold,
                )

            # max_passes 上限 5, 防止无限循环
            max_passes = max(1, min(int(self.config.max_quality_iterations), 5))

            mp_result = executor.execute_multi_pass(
                input_video=output_path,
                quality_report_fn=_quality_report_fn,
                max_passes=max_passes,
                threshold=threshold,
            )

            optimization_history = list(mp_result.get("history", []))
            final_file = mp_result.get("final_file", output_path)
            final_score_mp = float(mp_result.get("final_score", initial_score))
            optimization_reasoning = mp_result.get("reasoning", "")
            passes_used = int(mp_result.get("passes", 0))

            # 关键约束: 优化后分数反而下降 → 保留原始视频不替换
            # 仅当 final_file 存在、final_score > initial_score 时才替换 render 输出
            replaced = False
            if (
                final_file
                and final_file != output_path
                and Path(final_file).exists()
                and final_score_mp > initial_score
            ):
                render_result.data["output_path"] = final_file
                render_result.data["optimization_replaced"] = True
                render_result.data["original_output_path"] = output_path
                # 同步更新本方法后续使用的局部变量
                output_path = final_file
                replaced = True
                self._log(
                    f"[VERIFY] render output replaced -> {final_file} "
                    f"(initial={initial_score:.1f} → final={final_score_mp:.1f})"
                )
            else:
                keep_reason = (
                    "score did not improve" if final_score_mp <= initial_score
                    else "final file missing"
                )
                self._log(
                    f"[VERIFY] keep original render output "
                    f"(reason={keep_reason}, initial={initial_score:.1f}, "
                    f"final={final_score_mp:.1f}, passes={passes_used})"
                )

            optimization_applied = True
            # 用最终分数覆盖 qa_result.score (仅在提升时)
            if replaced:
                qa_result["score"] = round(final_score_mp, 1)
                qa_result["verified"] = final_score_mp >= threshold
            qa_result["optimization_passes"] = passes_used
            qa_result["optimization_replaced"] = replaced

        except Exception as opt_e:
            # 降级路径: 优化失败不影响管线继续运行, 保留原始视频与初始评分
            error_code = f"OPT_FAILED:{type(opt_e).__name__}"
            optimization_reasoning = (
                f"execute_multi_pass error: {type(opt_e).__name__}: {str(opt_e)[:200]}"
            )
            self._log(
                f"[VERIFY] multi-pass optimization failed (degraded): {opt_e}",
                "WARN",
            )
    else:
        if not self.config.enable_feedback_loop:
            optimization_reasoning = "feedback_loop disabled"
        elif qa_result.get("is_error_sample", False):
            optimization_reasoning = "VQA error sample, skip optimization"
        else:
            optimization_reasoning = (
                f"initial score {initial_score:.1f} >= threshold {threshold:.1f}"
            )

    # 必须返回 optimization_history / optimization_applied / final_score
    try:
        raw_final = qa_result.get("score")
        final_score_val = 0.0 if raw_final is None else float(raw_final)
    except (TypeError, ValueError):
        final_score_val = 0.0
    qa_result["optimization_history"] = optimization_history
    qa_result["optimization_applied"] = optimization_applied
    qa_result["final_score"] = round(final_score_val, 1)
    qa_result["optimization_reasoning"] = optimization_reasoning
    if error_code:
        qa_result["error_code"] = error_code

    # P4.2: QualityGate 质量规则校验 (VMAF/时长/分辨率/音频/文件大小/阶段成功)
    self._run_quality_gate(output_path, qa_result)

    # P4.4: 目视验收 — VisualInspector 关键帧提取 + HTML报告
    # 当自动评分处于边界区间(70-85)时触发人工验收; >85自动PASS; <70自动FAIL
    try:
        from core.visual_inspector import VisualInspector
        inspector = VisualInspector()
        auto_score = float(qa_result.get("score") or qa_result.get("final_score") or 0)
        vi_report = inspector.inspect(
            video_path=output_path,
            auto_score=auto_score,
            score_threshold_low=70.0,
            score_threshold_high=85.0,
        )
        qa_result["visual_inspection"] = {
            "needs_human_review": vi_report.needs_human_review,
            "review_reason": vi_report.review_reason,
            "keyframe_count": len(vi_report.keyframes),
            "report_path": vi_report.report_path or "",
            "duration_sec": vi_report.duration_sec,
            "resolution": list(vi_report.resolution) if vi_report.resolution else [],
        }
        if vi_report.report_path:
            self._log(
                f"[VERIFY] VisualInspector: {len(vi_report.keyframes)} keyframes, "
                f"human_review={vi_report.needs_human_review}, "
                f"report={vi_report.report_path}"
            )
            # 注册HTML报告为产物
            if hasattr(self, 'artifact_mgr') and self.artifact_mgr:
                try:
                    self.artifact_mgr.register(
                        run_id=self.run_id, stage="verify",
                        artifact_type="visual_report",
                        path=vi_report.report_path,
                        metadata={"keyframes": len(vi_report.keyframes),
                                  "needs_review": vi_report.needs_human_review},
                    )
                except Exception:
                    pass  # 产物注册失败不阻塞管线
    except ImportError:
        self._log("[VERIFY] VisualInspector not available (import failed)", "DEBUG")
    except Exception as vi_e:
        self._log(f"[VERIFY] VisualInspector skipped: {vi_e}", "WARN")

    # P4.3b: 产物血缘追溯 — 汇总本 run 全部登记产物，闭合"只写不读"断点
    manifest = self._trace_artifact_manifest()
    if manifest:
        qa_result["artifact_manifest"] = manifest

    return qa_result

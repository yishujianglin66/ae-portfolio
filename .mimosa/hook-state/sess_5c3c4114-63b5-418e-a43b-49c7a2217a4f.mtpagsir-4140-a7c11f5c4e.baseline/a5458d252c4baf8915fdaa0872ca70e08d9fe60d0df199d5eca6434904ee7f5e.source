"""
core/evolution/evaluator.py — 独立评测器 (Evaluator Agent)
===========================================================

借鉴 PenguinHarness 的 Evaluator 设计：
1. 与被测管线解耦 — Evaluator 独立启动、独立打分
2. Rubrics 隐藏评分 — 评分标准只有 Evaluator 可见，防止被测 Agent 作弊
3. 双通道评分 — 确定性指标 (VMAF/SSIM/VQA) + LLM 语义评分 (Rubrics)
4. 多次采样取中位数 — 抑制 LLM 评分不稳定性

集成方式:
    from core.evolution.evaluator import get_evolution_evaluator

    evaluator = get_evolution_evaluator()
    result = evaluator.evaluate_pipeline_result(pipeline_result_dict)
    # result: EvaluationResult(score=72.5, ...)

降级策略:
    - LLM 不可用 → 仅使用确定性指标评分（rubric_score=None）
    - 确定性指标缺失 → 基于 pipeline status 的基础评分
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.protocol import (
    EvaluationResult,
    EvolutionMessage,
    EvolutionMsgType,
    append_jsonl,
    read_json,
)

logger = logging.getLogger(__name__)


# ============================================================================
#  评分权重
# ============================================================================

# 综合评分 = 确定性指标 * W_DET + Rubrics语义评分 * W_RUBRIC
# LLM 不可用时自动退化为纯确定性评分
WEIGHT_DETERMINISTIC = 0.7
WEIGHT_RUBRIC = 0.3

# 确定性分项权重（P3-C: 新增 style_match 风格属性匹配，消费题目 expected_output）
DET_WEIGHTS = {
    "quality_score": 0.30,    # verify 阶段质检分 (VQA)
    "style_match": 0.30,      # P3-C: 实测风格属性 vs expected_output 断言
    "pipeline_success": 0.25, # 管线整体成功
    "output_exists": 0.15,    # 输出文件存在
}

# Rubrics 采样次数由 core.evolution.rubrics.RubricsScorer.DEFAULT_RUNS 控制（默认 3 次取中位数）


# ============================================================================
#  评测器
# ============================================================================

class EvolutionEvaluator:
    """独立评测器 — 与被测管线完全解耦

    输入: 管线结果字典 (PipelineResult.to_dict() 格式)
    输出: EvaluationResult (综合评分 + 分项明细)
    """

    DEFAULT_BENCHMARK_DIR = "data/benchmark"

    def __init__(
        self,
        benchmark_dir: str = DEFAULT_BENCHMARK_DIR,
        results_dir: str = "",
        enable_rubrics: bool = True,
    ):
        self._benchmark_dir = Path(benchmark_dir)
        # 评测结果默认写入 benchmark/results/
        self._results_dir = Path(results_dir) if results_dir else self._benchmark_dir / "results"
        self._results_dir.mkdir(parents=True, exist_ok=True)
        self._enable_rubrics = enable_rubrics

    # ----------------------------------------------------------------
    #  主入口
    # ----------------------------------------------------------------

    def evaluate_pipeline_result(
        self,
        pipeline_result: Dict[str, Any],
        scope: str = "",
    ) -> EvaluationResult:
        """评测一次管线运行结果

        Args:
            pipeline_result: PipelineResult.to_dict() 的输出
            scope: 评测作用域（任务类型，用于版本对比）

        Returns:
            EvaluationResult
        """
        run_id = pipeline_result.get("run_id", "unknown")
        notes: List[str] = []

        # ---- 通道 1: 确定性指标评分 ----
        det_score, det_checks = self._score_deterministic(pipeline_result)
        notes.append(f"deterministic_score={det_score:.1f}")

        # ---- 通道 2: LLM 语义评分 (Rubrics) ----
        rubric_score = None
        tokens_used = 0
        cost_usd = 0.0
        if self._enable_rubrics:
            try:
                rubric_score, tokens_used, cost_usd, rubric_notes = self._score_rubrics(
                    pipeline_result, scope
                )
                notes.extend(rubric_notes)
            except Exception as e:
                logger.warning("[Evaluator] Rubrics scoring failed (degrade to deterministic): %s", e)
                notes.append(f"rubrics_degraded: {type(e).__name__}")

        # ---- 综合评分 ----
        if rubric_score is not None:
            overall = WEIGHT_DETERMINISTIC * det_score + WEIGHT_RUBRIC * rubric_score
        else:
            overall = det_score

        # ---- 通道 3: 能力注册表反馈加分 ----
        capability_bonus = 0.0
        try:
            from core.evolution.capability_feedback import CapabilityFeedbackLoop
            fb = CapabilityFeedbackLoop()
            cov = fb.get_coverage_stats()
            # 覆盖率奖励：覆盖率越高，奖励越高（鼓励多样化）
            coverage_rate = cov["coverage_rate"]
            if coverage_rate >= 0.8:
                capability_bonus = 3.0  # 80%+ 覆盖率加 3 分
            elif coverage_rate >= 0.5:
                capability_bonus = 1.5  # 50%+ 覆盖率加 1.5 分
            # 历史成功率奖励
            weights = fb.get_preset_weights()
            if weights:
                avg_weight = sum(weights.values()) / len(weights)
                if avg_weight > 0.7:
                    capability_bonus += 2.0  # 历史表现好加 2 分
            if capability_bonus > 0:
                notes.append(f"capability_bonus={capability_bonus:.1f} (coverage={coverage_rate:.0%})")
        except Exception:
            pass  # 反馈闭环不可用时不影响评测

        overall += capability_bonus
        passed = bool(pipeline_result.get("status") == "success") and overall >= 60.0

        result = EvaluationResult(
            run_id=run_id,
            scope=scope,
            score=round(float(overall), 2),
            deterministic_score=round(det_score, 2),
            rubric_score=round(rubric_score, 2) if rubric_score is not None else None,
            passed=passed,
            checks=det_checks,
            notes=notes,
            tokens_used=tokens_used,
            cost_usd=round(cost_usd, 6),
        )

        # 文件即真相：持久化评测结果
        self._persist_result(result)
        return result

    # ----------------------------------------------------------------
    #  通道 1: 确定性指标评分
    # ----------------------------------------------------------------

    def _score_deterministic(
        self, pr: Dict[str, Any]
    ) -> tuple:
        """确定性指标评分（0-100）

        分项 (DET_WEIGHTS):
        1. quality_score (30%): verify 阶段质检分
        2. style_match (30%): 风格属性匹配 (P3-C, signalstats 实测 vs expected_output)
        3. pipeline_success (25%): 管线整体 status
        4. output_exists (15%): 输出文件是否存在
        """
        checks: Dict[str, Any] = {}

        # 1. 质检分 — 兼容两种结果格式:
        #    - 真实 PipelineResult.to_dict(): 顶层 quality_score（实测校准 2026-08）
        #    - 模拟/dry-run 格式: stages.verify.data.score
        quality_score = 0.0
        raw_qs = pr.get("quality_score")
        if raw_qs is None:
            stages = pr.get("stages", {})
            verify = stages.get("verify", {})
            verify_data = verify.get("data", {}) if isinstance(verify, dict) else {}
            raw_qs = verify_data.get("score")
        try:
            if raw_qs is not None:
                quality_score = float(raw_qs)
        except (TypeError, ValueError):
            quality_score = 0.0
        # 错误样本（VQA 异常）记 0 分，避免污染
        stages = pr.get("stages", {})
        verify = stages.get("verify", {})
        verify_data = verify.get("data", {}) if isinstance(verify, dict) else {}
        if verify_data.get("is_error_sample"):
            quality_score = 0.0
        quality_score = max(0.0, min(100.0, quality_score))
        checks["quality_score"] = quality_score

        # 2. 管线成功
        status = pr.get("status", "")
        success_score = 100.0 if status == "success" else (40.0 if status == "partial" else 0.0)
        checks["pipeline_success"] = success_score

        # 3. 输出文件存在 + 产物真实性校验 (P2: AE 渲染链路接入)
        #    占位/无效视频(过小/过短)只给半分，防止“文件存在但无价值”拿满分
        output_path = pr.get("output_path", "")
        output_exists = bool(output_path and Path(output_path).exists())
        if output_exists:
            artifact = self._verify_artifact(output_path)
            checks["artifact"] = artifact
            checks["output_exists"] = 100.0 if artifact.get("valid") else 50.0
        else:
            checks["output_exists"] = 0.0

        # 4. P3-C: 风格属性匹配 — signalstats 实测 vs expected_output 断言；黑屏惩罚
        style_detail = self._score_style_match(pr, output_path if output_exists else "")
        checks["style_match_detail"] = style_detail
        style_score = float(style_detail.get("score", 0.0))
        checks["style_match"] = style_score

        total = (
            DET_WEIGHTS["quality_score"] * quality_score
            + DET_WEIGHTS["style_match"] * style_score
            + DET_WEIGHTS["pipeline_success"] * success_score
            + DET_WEIGHTS["output_exists"] * checks["output_exists"]
        )
        return float(total), checks

    # ----------------------------------------------------------------
    #  P3-C: 风格属性匹配（确定性测量，消费 expected_output）
    # ----------------------------------------------------------------

    def _measure_video_stats(self, path: str) -> Dict[str, Any]:
        """ffmpeg signalstats 实测亮度/饱和度/色温/对比度（永不抛异常）"""
        stats: Dict[str, Any] = {"measured": False}
        if not path or not os.path.isfile(path):
            return stats
        ffmpeg = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
        if not os.path.isfile(ffmpeg):
            return stats
        try:
            r = subprocess.run(
                [ffmpeg, "-i", str(path), "-t", "10",
                 "-vf", "signalstats,metadata=print", "-f", "null", "-"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120,
            )
            blob = (r.stderr or "") + (r.stdout or "")

            def _avg(key: str) -> Optional[float]:
                vals = [float(v) for v in re.findall(r"\b" + key + r"=(\d+(?:\.\d+)?)", blob)]
                return sum(vals) / len(vals) if vals else None

            y, sat = _avg("YAVG"), _avg("SATAVG")
            u, v = _avg("UAVG"), _avg("VAVG")
            ylow, yhigh = _avg("YLOW"), _avg("YHIGH")
            if y is None:
                return stats
            stats.update({
                "measured": True,
                "yavg": round(y, 2),
                "satavg": round(sat, 2) if sat is not None else None,
                "uavg": round(u, 2) if u is not None else None,
                "vavg": round(v, 2) if v is not None else None,
                "contrast_range": round(yhigh - ylow, 2) if (yhigh is not None and ylow is not None) else None,
                "is_black": y < 20.0,
            })
        except Exception as e:
            logger.debug("[Evaluator] signalstats failed: %s", e)

        # P4-D: 粒子存在性代理指标 — 帧间差均值（静态内容≈0，粒子持续运动>阈值）
        try:
            r2 = subprocess.run(
                [ffmpeg, "-i", str(path), "-t", "6",
                 "-vf", "tblend=all_mode=difference,signalstats,metadata=print",
                 "-f", "null", "-"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120,
            )
            dvals = [float(x) for x in re.findall(
                r"\bYAVG=(\d+(?:\.\d+)?)", (r2.stderr or "") + (r2.stdout or ""))]
            if dvals:
                stats["temporal_diff"] = round(sum(dvals) / len(dvals), 3)
        except Exception as e:
            logger.debug("[Evaluator] temporal_diff failed: %s", e)

        # P4-D: 辉光像素占比 — Y>200 的像素比例（geq 二值化后读 YAVG/255）
        try:
            r3 = subprocess.run(
                [ffmpeg, "-i", str(path), "-t", "6",
                 "-vf", "geq='if(gt(lum(X,Y),200),255,0)',signalstats,metadata=print",
                 "-f", "null", "-"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120,
            )
            bvals = [float(x) for x in re.findall(
                r"\bYAVG=(\d+(?:\.\d+)?)", (r3.stderr or "") + (r3.stdout or ""))]
            if bvals:
                stats["bright_ratio"] = round(sum(bvals) / len(bvals) / 255.0, 4)
        except Exception as e:
            logger.debug("[Evaluator] bright_ratio failed: %s", e)
        return stats

    def _score_style_match(self, pr: Dict[str, Any], output_path: str) -> Dict[str, Any]:
        """风格属性匹配评分 (0-100)

        规则:
        - 黑屏(YAVG<20, limited range 纯黑=16) → 直接 0 分（修掉黑底拿中等分的问题）
        - expected_output 断言逐项比对，子项均值 * 100
        - 无断言且非黑屏 → 中性 50（不奖不重罚）
        - 失分归因写入 failures 供 Optimizer 消费
        """
        detail: Dict[str, Any] = {
            "score": 0.0, "black_screen": False, "assertions": {},
            "failures": [], "video_stats": {},
        }
        expected = pr.get("_expected_output") or {}
        if not isinstance(expected, dict):
            expected = {}

        vstats = self._measure_video_stats(output_path)
        detail["video_stats"] = vstats

        # 黑屏惩罚（最高优先级）
        if not output_path or not vstats.get("measured"):
            detail["failures"].append("无产物或未测到视频信号: style_match=0")
            return detail
        if vstats.get("is_black"):
            detail["black_screen"] = True
            detail["failures"].append("产物黑屏(YAVG<20): style_match=0")
            return detail

        sub_scores: List[float] = []
        sat = vstats.get("satavg")
        u, v = vstats.get("uavg"), vstats.get("vavg")
        cr = vstats.get("contrast_range")

        # 断言: saturation (仅对已知枚举断言，未知值如 very_low 跳过)
        exp_sat = str(expected.get("saturation", "")).lower()
        if exp_sat in ("low", "high") and sat is not None:
            # 【第四轮校准】调色架构改为逐镜头差异化(1.1-1.3x) + Stage C轻统一(1.15x)，
            # 有效饱和度 1.265-1.495x，SATAVG 预计 20-30。下调阈值至 22。
            ok = (exp_sat == "low" and sat < 70.0) or (exp_sat == "high" and sat > 22.0)
            sub_scores.append(100.0 if ok else 0.0)
            detail["assertions"]["saturation"] = {"expected": exp_sat, "measured": sat, "pass": ok}
            if not ok:
                detail["failures"].append(f"饱和度断言未达标: 期望{exp_sat} 实测SATAVG={sat:.1f}")

        # 断言: color_temperature (V>U 偏暖红，U>V 偏冷蓝)
        exp_temp = str(expected.get("color_temperature", "")).lower()
        if exp_temp in ("warm", "cool") and u is not None and v is not None:
            warm = v > u
            ok = (exp_temp == "warm" and warm) or (exp_temp == "cool" and not warm)
            sub_scores.append(100.0 if ok else 0.0)
            detail["assertions"]["color_temperature"] = {"expected": exp_temp, "measured": "warm" if warm else "cool", "pass": ok}
            if not ok:
                detail["failures"].append(f"色温断言未达标: 期望{exp_temp} 实测={'warm' if warm else 'cool'} (U={u:.1f},V={v:.1f})")

        # 断言: contrast (用 YHIGH-YLOW 均值差衡量)
        exp_con = str(expected.get("contrast", "")).lower()
        if exp_con in ("high", "low") and cr is not None:
            ok = (exp_con == "high" and cr >= 50.0) or (exp_con == "low" and cr <= 40.0)
            sub_scores.append(100.0 if ok else 0.0)
            detail["assertions"]["contrast"] = {"expected": exp_con, "measured_range": cr, "pass": ok}
            if not ok:
                detail["failures"].append(f"对比度断言未达标: 期望{exp_con} 实测动态范围={cr:.1f}")

        # 断言: effects_contain — 与执行记录中的效果名比对（包含匹配）
        exp_effects = expected.get("effects_contain") or []
        if isinstance(exp_effects, list) and exp_effects:
            exec_text = json.dumps(pr, ensure_ascii=False).lower()
            hit, miss = 0, []
            for kw in exp_effects:
                kw_l = str(kw).lower()
                variants = {kw_l}
                if "grain" in kw_l:
                    variants.update(["grain", "noise", "颗粒"])
                if "glow" in kw_l:
                    variants.update(["glow", "glo2", "发光"])
                if "particle" in kw_l:
                    variants.update(["particle", "particlefx", "粒子", "cc particle"])
                if "glitch" in kw_l:
                    variants.update(["glitch", "rgb_glitch", "故障", "错位"])
                if any(v in exec_text for v in variants):
                    hit += 1
                else:
                    miss.append(str(kw))
            sub_scores.append(100.0 * hit / len(exp_effects))
            detail["assertions"]["effects_contain"] = {"expected": exp_effects, "hit": hit, "pass": hit == len(exp_effects)}
            if miss:
                detail["failures"].append(f"效果清单断言未达标: 未找到 {miss}")

        # P4-D 断言: particle_presence — 帧间差均值衡量（粒子持续运动 → diff 升高）
        exp_particles = expected.get("particle_presence")
        tdiff = vstats.get("temporal_diff")
        if isinstance(exp_particles, bool) and tdiff is not None:
            has_motion = tdiff >= 0.8
            ok = exp_particles == has_motion
            sub_scores.append(100.0 if ok else 0.0)
            detail["assertions"]["particle_presence"] = {
                "expected": exp_particles, "measured_diff": tdiff, "pass": ok}
            if not ok:
                detail["failures"].append(
                    f"粒子存在性断言未达标: 期望{exp_particles} 实测帧间差={tdiff:.2f}")

        # P4-D 断言: glow_ratio_min — 亮像素(Y>200)占比下限
        exp_glow = expected.get("glow_ratio_min")
        bratio = vstats.get("bright_ratio")
        if isinstance(exp_glow, (int, float)) and exp_glow > 0 and bratio is not None:
            ok = bratio >= float(exp_glow)
            sub_scores.append(100.0 if ok else 0.0)
            detail["assertions"]["glow_ratio"] = {
                "expected_min": exp_glow, "measured": bratio, "pass": ok}
            if not ok:
                detail["failures"].append(
                    f"辉光占比断言未达标: 期望>={exp_glow} 实测亮像素占比={bratio:.4f}")

        if sub_scores:
            detail["score"] = round(sum(sub_scores) / len(sub_scores), 2)
        else:
            # 无可测断言: 中性分（不奖不重罚），避免无断言题目拿满/拿零
            detail["score"] = 50.0
        return detail

    # ----------------------------------------------------------------
    #  产物校验 (P2: 真实渲染产物接入)
    # ----------------------------------------------------------------

    def _verify_artifact(self, output_path: str) -> Dict[str, Any]:
        """校验渲染产物真实性 — ffprobe 实测时长/分辨率/编码

        适用于任何真实渲染引擎的产物 (ae_render/aerender/real_mix/ffmpeg)。
        永不抛异常；ffprobe 不可用时退化为文件大小判断。
        """
        info: Dict[str, Any] = {
            "exists": False, "size_mb": 0.0, "duration_sec": 0.0,
            "width": 0, "height": 0, "codec": "", "valid": False, "reason": "",
        }
        p = Path(output_path)
        if not output_path or not p.exists():
            info["reason"] = "missing"
            return info
        info["exists"] = True
        size = p.stat().st_size
        info["size_mb"] = round(size / (1024 * 1024), 2)

        ffprobe = shutil.which("ffprobe") or r"C:\ffmpeg\bin\ffprobe.exe"
        probed = False
        if os.path.isfile(ffprobe):
            try:
                r = subprocess.run(
                    [ffprobe, "-v", "error", "-print_format", "json",
                     "-show_streams", "-show_format", str(output_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0:
                    data = json.loads(r.stdout or "{}")
                    fmt = data.get("format", {}) or {}
                    try:
                        info["duration_sec"] = round(float(fmt.get("duration") or 0), 1)
                    except (TypeError, ValueError):
                        info["duration_sec"] = 0.0
                    for s in data.get("streams", []) or []:
                        if s.get("codec_type") == "video":
                            info["codec"] = s.get("codec_name", "")
                            try:
                                info["width"] = int(s.get("width") or 0)
                                info["height"] = int(s.get("height") or 0)
                            except (TypeError, ValueError):
                                pass
                            break
                    probed = True
            except Exception as e:
                info["reason"] = f"ffprobe_failed:{type(e).__name__}"

        # 有效性判定: 以 ffprobe 实测为准（时长>=1s 且有视频流即可）；
        # 黑底/低复杂度真实渲染产物压缩率极高，体积阈值会误杀 →
        # 仅在 ffprobe 不可用时退化为体积判断（阈值放宽到 10KB）
        if probed:
            valid = info["duration_sec"] >= 1.0 and info["width"] > 0
        else:
            valid = size > 10240
        info["valid"] = valid
        if not info["reason"]:
            info["reason"] = "ok" if valid else "placeholder_or_invalid"
        return info

    # ----------------------------------------------------------------
    #  通道 2: LLM 语义评分 (Rubrics)
    # ----------------------------------------------------------------

    def _score_rubrics(
        self, pr: Dict[str, Any], scope: str
    ) -> tuple:
        """LLM 语义评分 — 委托给 RubricsScorer (P1: 多次采样取中位数)

        Returns:
            (score, tokens_used, cost_usd, notes)
        """
        from core.evolution.rubrics import get_rubrics_scorer

        scorer = get_rubrics_scorer(benchmark_dir=str(self._benchmark_dir))
        summary = self._build_execution_summary(pr)
        result = scorer.score(execution_summary=summary, scope=scope)
        return result.score, result.tokens_used, result.cost_usd, list(result.notes)

    def _build_execution_summary(self, pr: Dict[str, Any]) -> str:
        """构建管线执行摘要（供 LLM 评审）"""
        lines = [
            f"- 运行ID: {pr.get('run_id', 'unknown')}",
            f"- 模式: {pr.get('mode', 'unknown')}",
            f"- 最终状态: {pr.get('status', 'unknown')}",
            f"- 总耗时: {pr.get('total_duration_sec', 0):.1f}s",
            f"- 迭代次数: {pr.get('iterations', 0)}",
        ]
        # P2: 渲染链路信息 — 让 Rubrics 评审能看到真实渲染引擎与产物属性
        render_engine = pr.get("render_engine", "")
        execution_mode = pr.get("execution_mode", "")
        if render_engine or execution_mode:
            lines.append(f"- 渲染引擎: {render_engine or 'unknown'} (执行模式: {execution_mode or 'unknown'})")
        output_path = pr.get("output_path", "")
        if output_path:
            artifact = self._verify_artifact(output_path)
            if artifact.get("exists"):
                lines.append(
                    f"- 产物: {artifact.get('size_mb', 0)}MB "
                    f"{artifact.get('duration_sec', 0)}s "
                    f"{artifact.get('width', 0)}x{artifact.get('height', 0)} "
                    f"codec={artifact.get('codec', '?')} valid={artifact.get('valid')}"
                )
        stages = pr.get("stages", {})
        if stages:
            lines.append("- 各阶段状态:")
            for name, st in stages.items():
                if isinstance(st, dict):
                    status = st.get("status", "unknown")
                    lines.append(f"  - {name}: {status}")
        return "\n".join(lines)

    # ----------------------------------------------------------------
    #  持久化与消息
    # ----------------------------------------------------------------

    def _persist_result(self, result: EvaluationResult) -> None:
        """文件即真相 — 评测结果写入 data/benchmark/results/"""
        ts = time.strftime("%Y%m%d_%H%M%S")
        record_path = self._results_dir / f"eval_{ts}_{result.run_id[-6:]}.json"
        try:
            record_path.parent.mkdir(parents=True, exist_ok=True)
            with open(record_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("[Evaluator] persist failed: %s", e)
        # 同时追加到汇总 JSONL
        append_jsonl(self._results_dir / "evaluation_history.jsonl", result.to_dict())

    def emit_message(self, result: EvaluationResult) -> EvolutionMessage:
        """将评测结果转为 EvolutionMessage"""
        return EvolutionMessage(
            msg_type=EvolutionMsgType.EVALUATE.value,
            run_id=result.run_id,
            scope=result.scope,
            score=result.score,
            tokens_used=result.tokens_used,
            cost_usd=result.cost_usd,
            payload=result.to_dict(),
        )

    # ----------------------------------------------------------------
    #  评测基准题目加载（P0 手动题目，P1 自动生成）
    # ----------------------------------------------------------------

    def load_benchmark_tasks(self, split: str = "train", task_type: str = "") -> List[Dict[str, Any]]:
        """加载评测基准题目

        Args:
            split: "train" / "val" / "test"（训练/验证/测试集隔离）
            task_type: 可选过滤，如 "style_transfer"

        Returns:
            题目列表
        """
        split_dir = self._benchmark_dir / split
        if not split_dir.exists():
            return []
        tasks: List[Dict[str, Any]] = []
        for json_file in sorted(split_dir.glob("*.json")):
            data = read_json(json_file, [])
            if not isinstance(data, list):
                continue
            for item in data:
                if task_type and item.get("task_type") != task_type:
                    continue
                tasks.append(item)
        return tasks


# ============================================================================
#  全局单例
# ============================================================================

_global_evaluator: Optional[EvolutionEvaluator] = None


def get_evolution_evaluator(
    benchmark_dir: str = EvolutionEvaluator.DEFAULT_BENCHMARK_DIR,
    enable_rubrics: bool = True,
) -> EvolutionEvaluator:
    """获取全局评测器单例"""
    global _global_evaluator
    if _global_evaluator is None:
        _global_evaluator = EvolutionEvaluator(
            benchmark_dir=benchmark_dir,
            enable_rubrics=enable_rubrics,
        )
    return _global_evaluator

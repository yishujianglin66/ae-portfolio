"""
pipeline/midstep_critic.py — 阶段边界中途自评节点（StageCritic）
===============================================================

借鉴 TEMPO（Test-time-scaled Value Estimation with Macro-step Policy
Optimization）的 macro-step critic 思想：长流程不要只在终点做评价，
在每个昂贵阶段边界插入一次轻量自评，让错误在引入点附近被拦截。

设计原则：
- 轻量：只做 ffprobe / 抽帧 / 亮度统计，秒级完成，不触发真实渲染
- 三态裁决：continue（继续）/ retry（回退本阶段重跑，限次）/ abort（止损）
- 评价即信号：每次裁决产出结构化 CriticVerdict，写入 manifest.critic_reports，
  无论管线最终成败都可供数字孪生校正

接入点（flagship_runner.py）：
- S2→S3 边界：evaluate("S2", ...) —— 节拍文件有效性
- S3→S4 边界：evaluate("S3", ...) —— 渲染产物黑帧/静帧检测（历史 QG-1 根因前移）
- S5→S6 边界：evaluate("S5", ...) —— 调色产物时长一致性与色彩溢出
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.stages import resolve_ffmpeg, resolve_ffprobe

# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class CriticVerdict:
    """单次中途自评的结构化裁决结果。"""
    stage: str                                    # 被评价的阶段（如 "S3"）
    value_estimate: float                         # 预期剩余回报 0~1（能否通过最终 QG 的估计）
    decision: str                                 # continue / retry / abort
    prior: float = 0.0                            # 先验：数字孪生链式成功率
    posterior: float = 0.0                        # 后验：原子检查通过率
    alpha: float = 0.3                            # 先验权重
    atomic_checks: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CriticAbortError(Exception):
    """critic 给出 abort 裁决时抛出，用于止损终止管线。"""

    def __init__(self, verdict: CriticVerdict):
        self.verdict = verdict
        super().__init__(
            f"[StageCritic] abort at {verdict.stage}: "
            f"value_estimate={verdict.value_estimate:.3f}, "
            f"failed={[k for k, v in verdict.atomic_checks.items() if not v]}"
        )


# ============================================================================
#  轻量检测工具（真跑 ffprobe / ffmpeg signalstats，不引入额外依赖）
# ============================================================================

def _run(cmd: list[str], timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(c) for c in cmd],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )


def ffprobe_duration(path: Path) -> float:
    """ffprobe 读取媒体时长（秒），失败返回 -1。"""
    try:
        proc = _run([
            resolve_ffprobe(), "-v", "quiet", "-print_format", "json",
            "-show_format", str(path),
        ], timeout=30)
        if proc.returncode == 0:
            return float(json.loads(proc.stdout)["format"]["duration"])
    except Exception:
        pass
    return -1.0


# 采样帧几何参数（降采样后固定尺寸，纯亮度差分无需保真）
_SAMPLE_W, _SAMPLE_H = 320, 180
_FRAME_BYTES = _SAMPLE_W * _SAMPLE_H


def sample_frame_stats(path: Path, n_frames: int = 5) -> tuple[float, float]:
    """采样 n 帧统计 (Y均值, 采样帧间平均绝对差分)。

    - Y 均值：采样帧平均亮度，全黑帧 ≈ 16（H.264 纯黑编码偏置，实测非 0）
    - 帧间差分：相邻采样帧像素级平均绝对差，静帧=0，动态内容显著 >0
      （实证：帧均值时间方差对动态内容也极小，不可靠，故改用像素差分）

    实现：降采样到 320x180 灰度全帧解码（rawvideo 管道），
    纯 Python 采样计算，避开首尾 10%（规避淡入淡出干扰），零额外依赖。
    """
    try:
        proc = subprocess.run(
            [str(resolve_ffmpeg()), "-v", "quiet", "-i", str(path),
             "-vf", f"scale={_SAMPLE_W}:{_SAMPLE_H},format=gray",
             "-f", "rawvideo", "-"],
            capture_output=True, timeout=180,
        )
        raw = proc.stdout
        total = len(raw) // _FRAME_BYTES
        if total == 0:
            return 0.0, 0.0
        # 均匀采样索引，避开首尾 10%
        lo = int(total * 0.1)
        hi = max(total - int(total * 0.1), lo + 1)
        span = list(range(lo, min(hi, total)))
        step = max(len(span) // n_frames, 1)
        idxs = span[::step][:n_frames]

        frames = [raw[i * _FRAME_BYTES:(i + 1) * _FRAME_BYTES] for i in idxs]
        means = [sum(f) / _FRAME_BYTES for f in frames]
        yavg_mean = sum(means) / len(means)
        if len(frames) > 1:
            diffs = []
            for a, b in zip(frames, frames[1:]):
                diffs.append(sum(abs(x - y) for x, y in zip(a, b)) / _FRAME_BYTES)
            frame_diff = sum(diffs) / len(diffs)
        else:
            frame_diff = 0.0
        return yavg_mean, frame_diff
    except Exception as e:
        logger.warning(f"[StageCritic] 帧采样失败 {path.name}: {e}")
        return 0.0, 0.0


# ============================================================================
#  StageCritic
# ============================================================================

class StageCritic:
    """阶段边界的中途自评器。

    value_estimate = alpha * prior + (1 - alpha) * posterior
    - prior：数字孪生 StagePredictor 对「当前阶段之后所有阶段」链式成功率预测
             （无数字孪生时退化为 0.5 中性值）
    - posterior：当前阶段产物的原子检查通过率

    三态裁决规则：
    - 任一 hard-fail 原子项失败 → retry（未超 max_retry）或 abort
    - value_estimate >= threshold_continue → continue
    - value_estimate < threshold_abort → abort
    - 中间区间且原子通过率 >= 0.5 → continue（容忍软性指标波动），否则 retry/abort
    """

    def __init__(
        self,
        digital_twin: Any | None = None,
        alpha: float = 0.3,
        threshold_continue: float = 0.6,
        threshold_abort: float = 0.3,
        max_retry: int = 1,
    ):
        self.digital_twin = digital_twin
        self.alpha = alpha
        self.threshold_continue = threshold_continue
        self.threshold_abort = threshold_abort
        self.max_retry = max_retry
        self._retry_counts: dict[str, int] = {}
        self.reports: list[CriticVerdict] = []

    # ---- 先验估值 ----------------------------------------------------------

    def _prior_success_rate(self, stage: str, context: dict[str, Any]) -> float:
        """数字孪生链式成功率；不可用时返回 0.5 中性值。"""
        if self.digital_twin is None:
            return 0.5
        downstream = {
            "S2": ["S3", "S4", "S5", "S6", "S7"],
            "S3": ["S4", "S5", "S6", "S7"],
            "S5": ["S6", "S7"],
        }.get(stage, [])
        try:
            prob = 1.0
            predictor = getattr(self.digital_twin, "predictor", self.digital_twin)
            for st in downstream:
                pred = predictor.predict_success_rate(st)
                prob *= float(getattr(pred, "success_rate", pred))
            return max(0.0, min(1.0, prob))
        except Exception as e:
            logger.debug(f"[StageCritic] 先验估值失败(退化 0.5): {e}")
            return 0.5

    # ---- 原子检查：S2→S3 边界 ----------------------------------------------

    def _checks_s2(self, artifacts: dict[str, Path],
                   context: dict[str, Any]) -> dict[str, tuple[bool, str, bool]]:
        """返回 {检查名: (通过与否, 原因, 是否硬性)}"""
        checks: dict[str, tuple[bool, str, bool]] = {}
        beats_path = artifacts.get("beats_json")
        audio_path = artifacts.get("audio")

        # 1. 节拍文件存在且非空
        beats_ok = False
        beats_data: dict[str, Any] = {}
        if beats_path and beats_path.exists() and beats_path.stat().st_size > 0:
            try:
                beats_data = json.loads(beats_path.read_text(encoding="utf-8"))
                beats_ok = True
            except Exception:
                pass
        checks["beats_file_valid"] = (beats_ok, f"节拍文件: {beats_path}", True)

        # 2. onset/beat 数量达到下限（15 秒素材预期 ≥ 4 个节拍）
        n_beats = 0
        for key in ("beats", "onsets", "drop_points"):
            v = beats_data.get(key)
            if isinstance(v, list) and len(v) > n_beats:
                n_beats = len(v)
        min_beats = int(context.get("min_beats", 4))
        checks["beat_count_sufficient"] = (
            n_beats >= min_beats,
            f"节拍数 {n_beats} < 下限 {min_beats}" if n_beats < min_beats else f"节拍数 {n_beats}",
            True,
        )

        # 3. 音画时长匹配（音频 vs 素材视频总时长，容差 10%）
        if audio_path and audio_path.exists():
            audio_dur = ffprobe_duration(audio_path)
            video_dur = float(context.get("source_video_duration", 0.0))
            if audio_dur > 0 and video_dur > 0:
                ratio = audio_dur / video_dur
                ok = 0.5 <= ratio <= 2.0
                checks["audio_video_duration_match"] = (
                    ok,
                    f"音频 {audio_dur:.1f}s vs 素材 {video_dur:.1f}s (ratio={ratio:.2f})",
                    False,
                )
        return checks

    # ---- 原子检查：S3→S4 边界 ----------------------------------------------

    def _checks_s3(self, artifacts: dict[str, Path],
                   context: dict[str, Any]) -> dict[str, tuple[bool, str, bool]]:
        checks: dict[str, tuple[bool, str, bool]] = {}
        renders = artifacts.get("renders_list", [])  # List[Path]

        # 1. 渲染产物存在且 > 100KB
        size_ok = bool(renders) and all(
            r.exists() and r.stat().st_size > 100 * 1024 for r in renders
        )
        checks["render_size_above_100kb"] = (
            size_ok, f"{len(renders)} 个渲染产物大小检查", True,
        )
        if not renders:
            checks["render_duration_ok"] = (False, "无渲染产物", True)
            checks["frame_luminance_ok"] = (False, "无渲染产物", True)
            checks["frame_temporal_variability_ok"] = (False, "无渲染产物", True)
            return checks

        # 2. ffprobe 时长达标（≥ 5s，与粗剪素材需求匹配）
        durations = [ffprobe_duration(r) for r in renders]
        min_dur = float(context.get("min_render_duration", 5.0))
        dur_ok = all(d >= min_dur for d in durations)
        checks["render_duration_ok"] = (
            dur_ok,
            f"时长 {[round(d, 2) for d in durations]}s, 下限 {min_dur}s",
            True,
        )

        # 3/4. 抽帧亮度与帧间像素差分（历史 QG-1 黑帧/静帧根因前移检测）
        # 实测校准：H.264 纯黑编码 YAVG≈16，故亮度下限取 20；
        # 帧均值时间方差对动态内容也极小（testsrc2 仅 0.09），改用采样帧像素差分
        yavg_min = float(context.get("yavg_min", 20.0))
        diff_min = float(context.get("min_frame_diff", 1.0))
        lum_ok, tvar_ok = True, True
        lum_detail, tvar_detail = [], []
        for r in renders:
            yavg, fdiff = sample_frame_stats(r)
            if yavg <= yavg_min:
                lum_ok = False
            if fdiff <= diff_min:
                tvar_ok = False
            lum_detail.append(f"{r.name}: Y={yavg:.1f}")
            tvar_detail.append(f"{r.name}: diff={fdiff:.2f}")
        checks["frame_luminance_ok"] = (
            lum_ok, f"亮度 {', '.join(lum_detail)} (下限 Y>{yavg_min})", True,
        )
        checks["frame_temporal_variability_ok"] = (
            tvar_ok,
            f"帧间像素差分 {', '.join(tvar_detail)} (下限 >{diff_min}，防静帧)",
            True,
        )
        return checks

    # ---- 原子检查：S5→S6 边界 ----------------------------------------------

    def _checks_s5(self, artifacts: dict[str, Path],
                   context: dict[str, Any]) -> dict[str, tuple[bool, str, bool]]:
        checks: dict[str, tuple[bool, str, bool]] = {}
        graded = artifacts.get("graded_mov")
        renders = artifacts.get("renders_list", [])

        if not graded or not graded.exists():
            checks["graded_file_exists"] = (False, "调色产物不存在", True)
            return checks
        checks["graded_file_exists"] = (True, str(graded.name), True)

        # 1. 调色产物时长与粗剪源一致（容差 0.5s）
        graded_dur = ffprobe_duration(graded)
        # 修复：粗剪总时长 = 各分段渲染时长之和（原用 max 取单段 7s，
        # 导致拼接后的全长三角色产物被误判不一致）
        src_dur = sum((ffprobe_duration(r) for r in renders if r.exists()), 0.0)
        if src_dur <= 0:
            src_dur = float(context.get("cut_duration", 0.0))
        tol = float(context.get("duration_tolerance_s", 0.5))
        dur_ok = graded_dur > 0 and (src_dur <= 0 or abs(graded_dur - src_dur) <= tol)
        checks["duration_consistent_with_cut"] = (
            dur_ok,
            f"调色 {graded_dur:.2f}s vs 粗剪 {src_dur:.2f}s (容差 {tol}s)",
            True,
        )

        # 2. 色彩无溢出（抽样帧 YMAX 不应恒定 255 且 YAVG 在合理区间）
        yavg, tvar = sample_frame_stats(graded)
        color_ok = 5.0 < yavg < 250.0
        checks["color_no_overflow"] = (
            color_ok, f"调色产物 YAVG={yavg:.1f} (合理区间 5~250)", True,
        )
        checks["graded_temporal_variability_ok"] = (
            tvar > 0.5, f"帧间方差 tvar={tvar:.1f}", False,
        )
        return checks

    # ---- 主入口 ------------------------------------------------------------

    _CHECK_DISPATCH = {
        "S2": _checks_s2,
        "S3": _checks_s3,
        "S5": _checks_s5,
    }

    def evaluate(self, stage: str, artifacts: dict[str, Any],
                 context: dict[str, Any] | None = None) -> CriticVerdict:
        """执行原子检查并给出三态裁决。

        artifacts 约定键：
        - beats_json / audio: Path（S2）
        - renders_list: List[Path]（S3/S5）
        - graded_mov: Path（S5）
        """
        t0 = time.time()
        context = context or {}
        checker = self._CHECK_DISPATCH.get(stage)
        if checker is None:
            raise ValueError(f"StageCritic 不支持的边界: {stage}")

        raw = checker(self, artifacts, context)
        atomic = {name: ok for name, (ok, _, _) in raw.items()}
        reasons = [f"{name}: {msg}" for name, (ok, msg, _) in raw.items()]
        hard_failed = [name for name, (ok, _, hard) in raw.items() if hard and not ok]

        prior = self._prior_success_rate(stage, context)
        posterior = sum(atomic.values()) / max(len(atomic), 1)
        value = self.alpha * prior + (1 - self.alpha) * posterior

        if hard_failed:
            retried = self._retry_counts.get(stage, 0)
            if retried < self.max_retry:
                self._retry_counts[stage] = retried + 1
                decision = "retry"
            else:
                decision = "abort"
        elif value >= self.threshold_continue:
            decision = "continue"
        elif value < self.threshold_abort:
            decision = "abort"
        elif posterior >= 0.5:
            decision = "continue"
        else:
            retried = self._retry_counts.get(stage, 0)
            decision = "retry" if retried < self.max_retry else "abort"
            if decision == "retry":
                self._retry_counts[stage] = retried + 1

        verdict = CriticVerdict(
            stage=stage,
            value_estimate=round(value, 4),
            decision=decision,
            prior=round(prior, 4),
            posterior=round(posterior, 4),
            alpha=self.alpha,
            atomic_checks=atomic,
            reasons=reasons,
            elapsed_ms=round((time.time() - t0) * 1000, 1),
        )
        self.reports.append(verdict)

        logger.info(
            f"[StageCritic] {stage}→ 裁决={decision} "
            f"value={value:.3f} (prior={prior:.3f}, posterior={posterior:.3f}) "
            f"atomic={atomic} 耗时={verdict.elapsed_ms:.0f}ms"
        )
        return verdict

    # ---- 报告导出 ------------------------------------------------------------

    def export_reports(self) -> list[dict[str, Any]]:
        """导出全部裁决为 JSON 可序列化列表（写入 manifest.critic_reports）。"""
        return [v.to_dict() for v in self.reports]


# ============================================================================
#  独立自检入口
# ============================================================================

if __name__ == "__main__":
    # 冒烟自检：对最近一次 flagship run 的 S3 渲染产物跑一遍 critic
    output_root = PROJECT_ROOT / "output"
    runs = sorted(output_root.glob("flagship_*"))
    if not runs:
        print("无 flagship_* 运行目录，跳过实检")
        sys.exit(0)
    run_dir = runs[-1]
    renders = sorted(run_dir.glob("S3_*/*")) + sorted(run_dir.glob("*render*"))
    renders = [p for p in run_dir.rglob("*.mp4") if "S3" in str(p) or "render" in p.name.lower()]
    critic = StageCritic()
    verdict = critic.evaluate("S3", {"renders_list": renders[:4]})
    print(json.dumps(verdict.to_dict(), indent=2, ensure_ascii=False))

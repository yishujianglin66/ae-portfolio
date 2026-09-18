"""pipeline/visual_semantic_judge.py — 渲染输出语义级视觉评判器 (Loop Engineering 闭环)

现有 verify 阶段的 VideoQualityAssessor/VMAF 只做信号级打分，无法发现
"黑帧陷阱、特效没生效、转场突兀、风格跑偏"等语义问题。本模块提供双后端评判:

  - rule 后端: OpenCV + ffprobe 规则检测 (永远可用, 离线兜底)
  - vlm 后端: 本地 Qwen2.5-VL-3B-Instruct 语义打分 (8GB 显存可跑, 效果上限主力)

统一接口:
    judge = VisualSemanticJudge(backend="auto", model_path=...)
    report = judge.judge(video_path, context={"effect_stack": [...], "style": {...}})
    # report: JudgeReport(score, passed, issues, recommendations, backend, hard_veto)

降级链: vlm 不可用(无权重/无transformers/推理异常) → rule 后端; rule 后端失败 →
抛出由调用方捕获的异常, 调用方应跳过语义评判继续管线 (不阻塞渲染产物交付)。
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

from core.torch_runtime import infer_ctx

# 沿用既有渲染验证标准: 输出文件必须大于 100KB 才判定内容可见
MIN_FILE_SIZE_BYTES = 100 * 1024

# VLM 评分维度权重 (0-10 分制, 10 为最好)
_DIMENSION_WEIGHTS = {
    "black_frame": 0.25,       # 黑帧/空画面
    "color_anomaly": 0.15,     # 色彩异常 (过曝/失真)
    "effect_presence": 0.25,   # 特效是否生效
    "transition_quality": 0.15,  # 转场流畅度
    "style_coherence": 0.20,   # 风格契合度
}

# 硬性否决阈值 (rule 后端): 命中任一 → hard_veto=True
HARD_VETO_BLACK_RATIO = 0.30    # 黑帧占比 > 30%
HARD_VETO_SOLID_RATIO = 0.85    # 纯色/纯白帧占比 > 85%
HARD_VETO_MIN_DURATION = 0.5    # 时长 < 0.5s


@dataclass
class JudgeReport:
    """语义评判结果"""
    score: float = 100.0                       # 0-100, 100 为最好
    passed: bool = True
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    backend: str = "rule"                      # rule / vlm
    hard_veto: bool = False                    # 灾难性问题, 无论信号分多高都应否决
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "issues": list(self.issues),
            "recommendations": list(self.recommendations),
            "backend": self.backend,
            "hard_veto": self.hard_veto,
            "metrics": dict(self.metrics),
            "error": self.error,
        }


# ============================================================================
#  规则后端: OpenCV + ffprobe 检测灾难性/统计性问题
# ============================================================================

class RuleJudge:
    """规则后端 — 黑帧/纯色/糊帧/卡死/无声/时长/分辨率/文件大小"""

    def __init__(self, ffmpeg_bin: str = "", ffprobe_bin: str = ""):
        self.ffmpeg_bin = ffmpeg_bin or "ffmpeg"
        self.ffprobe_bin = ffprobe_bin or "ffprobe"

    def judge(self, video_path: str, context: dict | None = None) -> JudgeReport:
        path = Path(video_path)
        if not path.exists():
            return JudgeReport(
                score=0.0, passed=False, backend="rule", hard_veto=True,
                issues=["输出文件不存在"],
                recommendations=["检查 render 阶段输出路径"],
            )

        issues: list[str] = []
        recommendations: list[str] = []
        hard_veto = False
        metrics: dict[str, Any] = {}

        # 检查0: 文件大小 (沿用既有渲染验证标准 >100KB)
        size = path.stat().st_size
        metrics["file_size_bytes"] = size
        if size < MIN_FILE_SIZE_BYTES:
            issues.append(f"文件过小({size // 1024}KB < 100KB)，内容可能为空")
            recommendations.append("重新渲染: 文件过小判定内容不可见")
            hard_veto = True

        try:
            import cv2  # 延迟导入, 缺失时仍可给出文件大小结论
        except ImportError:
            metrics["opencv"] = "unavailable"
            score = 30.0 if hard_veto else 70.0
            return JudgeReport(
                score=score, passed=not hard_veto, issues=issues,
                recommendations=recommendations, backend="rule",
                hard_veto=hard_veto, metrics=metrics,
                error="opencv unavailable, file-size check only",
            )

        # 检查1: 帧统计 (均匀采样 32 帧)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            issues.append("视频无法打开 (编码损坏或格式不支持)")
            recommendations.append("重新渲染: 视频文件损坏")
            return JudgeReport(
                score=0.0, passed=False, issues=issues,
                recommendations=recommendations, backend="rule",
                hard_veto=True, metrics=metrics,
            )

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        metrics.update({"frame_count": total, "fps": fps,
                        "width": width, "height": height})

        n_sample = 32 if total > 32 else max(total, 1)
        indices = (
            [int(i * (total - 1) / (n_sample - 1)) for i in range(n_sample)]
            if total > 1 else [0]
        )

        black_cnt = solid_cnt = blur_cnt = 0
        prev_small = None
        frozen_cnt = 0
        sampled = 0
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            sampled += 1
            small = cv2.resize(frame, (160, 90))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            mean_val = float(gray.mean())
            std_val = float(gray.std())
            # 黑帧: 均值极低
            if mean_val < 12.0:
                black_cnt += 1
            # 纯色帧: 方差极低且均值高 (纯白/纯色)
            if std_val < 3.0 and mean_val > 200.0:
                solid_cnt += 1
            elif std_val < 1.0:
                solid_cnt += 1
            # 糊帧: Laplacian 方差过低
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if lap_var < 20.0:
                blur_cnt += 1
            # 卡死帧: 相邻采样帧完全一致
            if prev_small is not None:
                try:
                    diff = cv2.absdiff(small, prev_small)
                    if float(diff.mean()) < 0.5:
                        frozen_cnt += 1
                except Exception:
                    pass
            prev_small = small
        cap.release()

        if sampled == 0:
            issues.append("无法读取任何视频帧")
            recommendations.append("重新渲染: 帧读取失败")
            return JudgeReport(
                score=0.0, passed=False, issues=issues,
                recommendations=recommendations, backend="rule",
                hard_veto=True, metrics=metrics,
            )

        black_ratio = black_cnt / sampled
        solid_ratio = solid_cnt / sampled
        blur_ratio = blur_cnt / sampled
        frozen_ratio = frozen_cnt / max(sampled - 1, 1)
        metrics.update({
            "sampled_frames": sampled,
            "black_ratio": round(black_ratio, 3),
            "solid_ratio": round(solid_ratio, 3),
            "blur_ratio": round(blur_ratio, 3),
            "frozen_ratio": round(frozen_ratio, 3),
        })

        if black_ratio > HARD_VETO_BLACK_RATIO:
            issues.append(f"黑帧占比 {black_ratio:.0%}，疑似渲染黑帧陷阱")
            recommendations.append("重新渲染: 黑帧率过高，检查AE渲染输出与图层可见性")
            hard_veto = True
        elif black_ratio > 0.1:
            issues.append(f"黑帧占比 {black_ratio:.0%} 偏高")

        if solid_ratio > HARD_VETO_SOLID_RATIO:
            issues.append(f"纯色/纯白帧占比 {solid_ratio:.0%}，画面无内容")
            recommendations.append("重新渲染: 纯色帧过多，检查素材导入与合成尺寸")
            hard_veto = True

        if blur_ratio > 0.5:
            issues.append(f"糊帧占比 {blur_ratio:.0%}，清晰度不足")
            recommendations.append("增加锐化或提升渲染分辨率")

        if frozen_ratio > 0.6 and sampled >= 8:
            issues.append(f"静止卡死帧占比 {frozen_ratio:.0%}，视频疑似静帧")
            recommendations.append("检查时间线关键帧与素材时长")

        # 检查2: 时长/分辨率
        duration = (total / fps) if fps > 0 else 0.0
        metrics["duration_sec"] = round(duration, 2)
        if duration < HARD_VETO_MIN_DURATION:
            issues.append(f"时长 {duration:.2f}s 过短")
            recommendations.append("重新渲染: 输出时长不足")
            hard_veto = True
        if width < 320 or height < 240:
            issues.append(f"分辨率 {width}x{height} 过低")
            recommendations.append("提升渲染分辨率")

        # 检查3: 无声检测 (best-effort, ffprobe 不可用则跳过)
        try:
            audio_info = self._probe_audio_energy(str(path))
            if audio_info is not None:
                metrics["audio_energy"] = audio_info
                if audio_info < 1e-4:
                    issues.append("音频近乎静音")
                    recommendations.append("检查音频轨道是否混入")
        except Exception as e:  # 音频检测失败不影响画面判分
            logger.debug(f"[RuleJudge] audio probe skipped: {e}")

        # 汇总评分: 从 100 起扣
        score = 100.0
        score -= min(60.0, black_ratio * 120.0)
        score -= min(40.0, solid_ratio * 60.0)
        score -= min(20.0, blur_ratio * 30.0)
        score -= min(15.0, frozen_ratio * 25.0)
        if hard_veto:
            score = min(score, 40.0)
        score = max(0.0, min(100.0, score))

        return JudgeReport(
            score=round(score, 1),
            passed=(not hard_veto) and score >= 60.0,
            issues=issues,
            recommendations=recommendations,
            backend="rule",
            hard_veto=hard_veto,
            metrics=metrics,
        )

    def _probe_audio_energy(self, video_path: str) -> float | None:
        """ffprobe 采样音频均方能量; 无音频流/工具缺失返回 None"""
        cmd = [
            self.ffprobe_bin, "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0", video_path,
        ]
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            if "audio" not in (out.stdout or ""):
                return None  # 无音频流, 不作为扣分项
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

        cmd2 = [
            self.ffmpeg_bin, "-i", video_path, "-af",
            "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
            "-f", "null", "-",
        ]
        try:
            out2 = subprocess.run(
                cmd2, capture_output=True, text=True, timeout=60
            )
            levels = re.findall(r"RMS_level=(-?[\d.]+)", out2.stderr or "")
            vals = [float(v) for v in levels if float(v) > -100.0]
            if not vals:
                return 0.0
            # dB → 线性近似能量
            avg_db = sum(vals) / len(vals)
            return round(10.0 ** (avg_db / 20.0), 6)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None


# ============================================================================
#  VLM 后端: 本地 Qwen VL 语义打分
# ============================================================================

# 【提速】模块级模型缓存: 同 (权重路径, 量化策略, 设备) 的已加载模型/processor 常驻,
# 质量迭代多轮 verify 不再重复加载 8B 权重 (首次 ~60-90s → 后续复用近 0)。
# 显存仅 8GB, 只保留 1 个模型; 换路径/量化策略时自动替换旧的。
_VLM_CACHE: dict[str, Any] = {}

_VLM_PROMPT_TEMPLATE = """你是专业视频后期质检员。请观看这段自动生成的混剪视频片段，从以下5个维度打分，每项0-10分（10分为最好）：
1. black_frame 黑帧/空画面情况（10=完全没有黑帧，画面始终有内容）
2. color_anomaly 色彩正常度（10=色彩自然，无过曝/失真/偏色）
3. effect_presence 特效是否生效（10=特效明显可见）
4. transition_quality 转场流畅度（10=转场自然不突兀）
5. style_coherence 风格契合度（10=完全符合预期风格）

{context_line}

只输出JSON，不要任何其他文字，格式：
{{"black_frame": n, "color_anomaly": n, "effect_presence": n, "transition_quality": n, "style_coherence": n, "issues": ["问题1", "问题2"]}}"""


class VLMJudge:
    """本地 Qwen VL 语义评判后端 (兼容 Qwen3-VL / Qwen2.5-VL 架构)"""

    def __init__(self, model_path: str = "", device: str = "cuda",
                 quantize: str = "auto"):
        self.model_path = model_path
        self.device = device
        # quantize: none=强制bf16 / 4bit=强制4bit量化 / auto=bf16优先,OOM时自动降4bit或CPU分片
        self.quantize = quantize if quantize in ("none", "4bit", "auto") else "auto"
        self.model = None
        self.processor = None
        self._load_error = ""

    @staticmethod
    def _bnb_available() -> bool:
        try:
            import bitsandbytes  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def _load_4bit(model_cls, model_path: str, torch):
        """bitsandbytes nf4 量化加载 (~5-6GB 显存跑 8B 模型)"""
        from transformers import BitsAndBytesConfig
        qconfig = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
        )
        return model_cls.from_pretrained(
            model_path, quantization_config=qconfig, device_map="cuda"
        )

    @staticmethod
    def is_available(model_path: str) -> bool:
        """权重目录与 transformers 均存在才可用 (不加载模型, 快速判断)"""
        if not model_path or not Path(model_path).exists():
            return False
        try:
            import transformers  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def _model_class(model_path: str):
        """按 config.json 的 architectures 选择模型类 (Qwen3-VL 优先, 兼容 2.5-VL);
        读不到配置时回退通用多模态入口"""
        try:
            cfg_path = Path(model_path) / "config.json"
            if cfg_path.exists():
                archs = json.loads(cfg_path.read_text(encoding="utf-8")).get(
                    "architectures", []
                )
                import transformers
                for arch in archs:
                    cls = getattr(transformers, arch, None)
                    if cls is not None:
                        return cls
        except Exception as e:  # 配置损坏等 → 走通用入口
            logger.debug(f"[VLMJudge] arch detection failed: {e}")
        from transformers import AutoModelForImageTextToVideo
        return AutoModelForImageTextToVideo

    def load(self) -> bool:
        """加载模型; 失败记录原因并返回 False (由调用方降级到规则后端)"""
        if self.model is not None:
            return True
        # 【提速】命中缓存: 同路径+同量化策略+同设备的模型直接复用, 免重新加载
        cache_key = f"{self.model_path}|{self.quantize}|{self.device}"
        cached = _VLM_CACHE.get(cache_key)
        if cached is not None:
            self.model, self.processor = cached
            logger.info("[VLMJudge] reuse cached model (skip reload)")
            return True
        try:
            import torch
            from transformers import AutoProcessor

            model_cls = self._model_class(self.model_path)
            use_cuda = self.device == "cuda" and torch.cuda.is_available()
            if use_cuda:
                # 加载策略: 显式4bit → 量化加载; 否则 bf16 全装GPU →
                # OOM 时优先 4bit 量化 (有bitsandbytes), 无则 device_map="auto" CPU分片
                if self.quantize == "4bit":
                    self.model = self._load_4bit(model_cls, self.model_path, torch)
                else:
                    try:
                        self.model = model_cls.from_pretrained(
                            self.model_path, torch_dtype=torch.bfloat16,
                            device_map="cuda",
                        )
                    except (torch.cuda.OutOfMemoryError, RuntimeError):
                        if self.quantize != "none" and self._bnb_available():
                            logger.info("[VLMJudge] GPU OOM, retrying with 4bit quantization")
                            self.model = self._load_4bit(model_cls, self.model_path, torch)
                        else:
                            logger.info("[VLMJudge] GPU OOM, retrying with device_map='auto'")
                            self.model = model_cls.from_pretrained(
                                self.model_path, torch_dtype=torch.bfloat16,
                                device_map="auto",
                            )
            else:
                self.model = model_cls.from_pretrained(
                    self.model_path, torch_dtype=torch.float32
                )
                self.device = "cpu"
            self.processor = AutoProcessor.from_pretrained(self.model_path)
            self.model.eval()
            # 【提速】写入缓存: 显存紧张只留一个模型, 新配置进来时替换旧的释放引用
            _VLM_CACHE.clear()
            _VLM_CACHE[cache_key] = (self.model, self.processor)
            return True
        except Exception as e:
            self._load_error = f"{type(e).__name__}: {str(e)[:200]}"
            logger.warning(f"[VLMJudge] model load failed: {self._load_error}")
            return False

    @staticmethod
    def extract_frames(video_path: str, n_frames: int = 8) -> list[Any]:
        """均匀抽帧 (RGB), 写法与 models/camera_classifier/vlm_expert_3class.py 一致"""
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < n_frames:
            frames = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            cap.release()
            if not frames:
                raise ValueError("No frames decoded")
            while len(frames) < n_frames:
                frames.append(frames[-1])
            return frames[:n_frames]
        indices = np.linspace(0, total - 1, n_frames, dtype=int)
        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if ret:
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cap.release()
        if not frames:
            raise ValueError("No frames decoded")
        while len(frames) < n_frames:
            frames.append(frames[-1])
        return frames

    @staticmethod
    def build_prompt(context: dict | None = None) -> str:
        """根据 plan 上下文构造打分 prompt (供测试与推理共用)"""
        context_line = ""
        if context:
            effects = context.get("effect_stack") or []
            style = context.get("style_params") or context.get("style") or {}
            parts = []
            if effects:
                names = [e.get("name", e.get("type", "?")) for e in effects[:5]]
                parts.append(f"预期应用的特效: {', '.join(map(str, names))}")
            if isinstance(style, dict) and style:
                style_desc = style.get("style") or style.get("name") or ""
                if style_desc:
                    parts.append(f"预期风格: {style_desc}")
            if parts:
                context_line = "创作意图信息(用于判断特效是否生效、风格是否契合): " + "; ".join(parts)
        return _VLM_PROMPT_TEMPLATE.format(context_line=context_line or "（无附加创作意图信息）")

    def judge(self, video_path: str, context: dict | None = None) -> JudgeReport:
        if not self.load():
            raise RuntimeError(f"VLM unavailable: {self._load_error}")

        import torch

        frames_rgb = self.extract_frames(video_path, n_frames=8)
        prompt = self.build_prompt(context)
        messages = [
            {"role": "user", "content": [
                # 注意: 不传 fps 字段 — processor 拒绝 list 型 fps (已知陷阱)
                {"type": "video", "video": frames_rgb},
                {"type": "text", "text": prompt},
            ]}
        ]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=[text], videos=[frames_rgb], padding=True, return_tensors="pt"
        )
        # device_map="auto" 分片时, 输入张量跟随模型首参数设备 (避免CPU/GPU不匹配)
        try:
            in_device = next(self.model.parameters()).device
        except StopIteration:
            in_device = self.device
        inputs = {
            k: v.to(in_device) if hasattr(v, "to") else v
            for k, v in inputs.items()
        }
        with infer_ctx():
            output_ids = self.model.generate(
                **inputs, max_new_tokens=300, do_sample=False
            )
        output_text = self.processor.batch_decode(
            output_ids[:, inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )[0].strip()

        dims, vlm_issues = self._parse_output(output_text)
        if dims is None:
            raise RuntimeError(f"VLM output unparsable: {output_text[:120]}")

        # 维度加权 → 0-100
        total_weight = sum(_DIMENSION_WEIGHTS[k] for k in dims)
        score = sum(dims[k] * w for k, w in _DIMENSION_WEIGHTS.items() if k in dims)
        score = score / total_weight * 10.0 if total_weight > 0 else 50.0
        score = max(0.0, min(100.0, score))

        issues = list(vlm_issues)
        recommendations: list[str] = []
        if dims.get("black_frame", 10) <= 3:
            issues.append("VLM检出黑帧/空画面")
            recommendations.append("重新渲染: VLM检出黑帧，检查图层可见性与渲染范围")
        if dims.get("effect_presence", 10) <= 3:
            recommendations.append("特效疑似未生效: 检查effect_stack下发与AE效果参数")
        if dims.get("transition_quality", 10) <= 3:
            recommendations.append("转场突兀: 下轮切换转场类型并延长转场时长")
        if dims.get("color_anomaly", 10) <= 3:
            recommendations.append("色彩异常: 降低调色强度或检查色彩空间")

        return JudgeReport(
            score=round(score, 1),
            passed=score >= 60.0 and dims.get("black_frame", 10) > 3,
            issues=issues,
            recommendations=recommendations,
            backend="vlm",
            hard_veto=dims.get("black_frame", 10) <= 1,
            metrics={"dimensions": dims, "raw_output": output_text[:500]},
        )

    @staticmethod
    def _parse_output(text: str):
        """解析 VLM 输出: 先 JSON, 失败降级为逐项正则; 再失败返回 (None, [])"""
        issues: list[str] = []
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                dims = {}
                for k in _DIMENSION_WEIGHTS:
                    v = data.get(k)
                    try:
                        dims[k] = max(0.0, min(10.0, float(v)))
                    except (TypeError, ValueError):
                        continue
                raw_issues = data.get("issues")
                if isinstance(raw_issues, list):
                    issues = [str(x) for x in raw_issues][:5]
                if dims:
                    return dims, issues
            except (json.JSONDecodeError, TypeError):
                pass
        # 降级: 逐项正则
        dims = {}
        for k in _DIMENSION_WEIGHTS:
            km = re.search(rf'"{k}"\s*:\s*(\d+(?:\.\d+)?)', text)
            if km:
                dims[k] = max(0.0, min(10.0, float(km.group(1))))
        if dims:
            return dims, issues
        return None, issues


# ============================================================================
#  统一入口
# ============================================================================

class VisualSemanticJudge:
    """语义评判统一入口 — backend: vlm / rule / auto(vlm优先,自动降级)"""

    def __init__(
        self,
        backend: str = "auto",
        model_path: str = "",
        min_score: float = 60.0,
        ffmpeg_bin: str = "",
        ffprobe_bin: str = "",
        device: str = "cuda",
        quantize: str = "auto",
    ):
        self.backend_pref = (backend or "auto").lower()
        if self.backend_pref not in ("auto", "vlm", "rule"):
            self.backend_pref = "auto"
        self.model_path = model_path
        self.min_score = float(min_score)
        self.rule = RuleJudge(ffmpeg_bin=ffmpeg_bin, ffprobe_bin=ffprobe_bin)
        self.vlm = VLMJudge(model_path=model_path, device=device, quantize=quantize)

    def judge(self, video_path: str, context: dict | None = None) -> JudgeReport:
        # 规则检测永远执行: 硬性否决不依赖 VLM
        rule_report = self.rule.judge(video_path, context)

        use_vlm = (
            self.backend_pref in ("auto", "vlm")
            and VLMJudge.is_available(self.model_path)
        )
        if not use_vlm:
            if self.backend_pref == "vlm":
                # 显式要求 vlm 但权重/依赖缺失: 记录原因仍返回规则结果 (不阻塞管线)
                rule_report.error = (
                    "vlm backend requested but unavailable: "
                    "weights or transformers missing"
                )
            rule_report.passed = rule_report.passed and rule_report.score >= self.min_score
            return rule_report

        try:
            vlm_report = self.vlm.judge(video_path, context)
        except Exception as e:
            logger.warning(f"[VisualSemanticJudge] VLM failed, degraded to rule: {e}")
            if self.backend_pref == "vlm":
                # 显式要求 vlm 但不可用: 记录错误仍返回规则结果 (不阻塞管线)
                rule_report.error = f"vlm backend requested but unavailable: {e}"
            rule_report.passed = rule_report.passed and rule_report.score >= self.min_score
            return rule_report

        # 硬性否决取并集, 但 VLM 单独否决需规则证据佐证 (防模型误报否决好视频):
        # VLM 称黑帧严重, 但规则检测黑帧占比极低 → 不信 VLM 的硬否决, 只降语义分
        rule_black_ratio = float(rule_report.metrics.get("black_ratio", 0.0))
        vlm_veto = vlm_report.hard_veto and rule_black_ratio > 0.1
        merged = JudgeReport(
            score=vlm_report.score,
            passed=vlm_report.passed and not rule_report.hard_veto,
            issues=vlm_report.issues + rule_report.issues,
            recommendations=vlm_report.recommendations + rule_report.recommendations,
            backend="vlm",
            hard_veto=vlm_veto or rule_report.hard_veto,
            metrics={"vlm": vlm_report.metrics, "rule": rule_report.metrics},
        )
        if merged.hard_veto:
            merged.score = min(merged.score, 40.0)
            merged.passed = False
        else:
            merged.passed = merged.score >= self.min_score
        return merged

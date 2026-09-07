# -*- coding: utf-8 -*-
"""VisualEvalGateway — 视觉评估闭环网关（M2，[AE-sync] 对侧模块）

职责（与主会话 M1c 真机 demo 并行，不依赖 AE Bridge）：
  1. 帧采样：视频/图像 → JPEG base64 帧（供多模态模型评分）
  2. 多模态评分：复用 core.llm_gateway 的 vision 通道（Qwen3.8-Max / 其他
     VISION 档位 Provider），按 Rubric 逐维度打 1-5 分 + 一句话理由
  3. 参数变体优选：同一 prompt 的 N 个参数变体渲染结果 → 加权总分排序 →
     最优变体 + 逐维度均值对照（喂给 M1c demo 后的调参迭代）
  4. 离线降级：无 key / 调用失败 / JSON 解析失败 → 启发式图像指标
     （亮度/对比/饱和/清晰度/结构网格），结果带 offline=True 诚实标注
  5. 磁盘缓存：图片 md5 → 评分 JSON（cache/visual_eval/），重复评估零成本

标准接口:
    gw = VisualEvalGateway()
    report = gw.compare_variants_sync([
        {"label": "glow_r30", "image_paths": ["out/r30/f1.jpg", "out/r30/f2.jpg"],
         "params": {"radius": 30}},
        {"label": "glow_r45", "image_paths": ["out/r45/f1.jpg", "out/r45/f2.jpg"],
         "params": {"radius": 45}},
    ])
    print(report.best.label, report.best.total)

设计原则：
  - honest degradation：无论走模型还是启发式，结果都标注 backend/offline，
    绝不用启发式分数冒充模型分数
  - 只读复用 llm_gateway / frame_extractor，不修改主会话当日已提交文件
  - 全部异步接口 + _sync 薄包装，缓存按 md5 幂等
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("visual_eval_gateway")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CACHE_DIR = _PROJECT_ROOT / "cache" / "visual_eval"

# Rubric 预设 id
RUBRIC_AE_DEFAULT = "ae_default"
RUBRIC_TEXT_FOCUS = "ae_text_focus"

# 打分上下界（统一 1-5，总分加权归一到 0-100）
SCORE_MIN = 1.0
SCORE_MAX = 5.0


# ── 数据模型 ─────────────────────────────────────────────────────────
@dataclass
class RubricDimension:
    """评分维度"""
    name: str                 # 维度名（英文 key，prompt 对齐用）
    label: str                # 中文名
    weight: float = 1.0       # 加权权重
    desc: str = ""            # 打分指引（进 prompt）


@dataclass
class Rubric:
    """评分量表"""
    id: str
    dimensions: List[RubricDimension] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dimensions": [
                {"name": d.name, "label": d.label, "weight": d.weight, "desc": d.desc}
                for d in self.dimensions
            ],
        }

    def dim_names(self) -> List[str]:
        return [d.name for d in self.dimensions]

    def weights(self) -> Dict[str, float]:
        return {d.name: d.weight for d in self.dimensions}


@dataclass
class DimensionScore:
    """单维度得分"""
    name: str
    score: float = 3.0        # 1-5
    weight: float = 1.0
    comment: str = ""


@dataclass
class ImageScore:
    """单张帧/图的评分结果"""
    image_ref: str                 # 路径或 "frame@3.2s"
    md5: str = ""
    total: float = 0.0             # 加权总分（0-100）
    dimensions: List[DimensionScore] = field(default_factory=list)
    model: str = ""                # 实际使用的模型名
    provider: str = ""             # 实际 Provider
    backend: str = "heuristic"     # "vlm" | "heuristic"
    offline: bool = True           # 是否离线降级
    fallback_reason: str = ""      # 降级原因
    from_cache: bool = False
    latency_ms: float = 0.0
    raw: str = ""

    def dim(self, name: str) -> Optional[DimensionScore]:
        for d in self.dimensions:
            if d.name == name:
                return d
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_ref": self.image_ref, "md5": self.md5, "total": self.total,
            "model": self.model, "provider": self.provider, "backend": self.backend,
            "offline": self.offline, "fallback_reason": self.fallback_reason,
            "from_cache": self.from_cache, "latency_ms": self.latency_ms,
            "raw": self.raw,
            "dimensions": [
                {"name": d.name, "score": d.score, "weight": d.weight,
                 "comment": d.comment}
                for d in self.dimensions
            ],
        }


@dataclass
class VariantScore:
    """单参数变体的评分（多帧聚合）"""
    label: str
    params: Dict[str, Any] = field(default_factory=dict)
    total: float = 0.0             # 帧均总分（0-100）
    per_dim_avg: Dict[str, float] = field(default_factory=dict)
    temporal_energy: float = 0.0   # 帧间差异代理（节奏感，启发式后端才有意义）
    image_scores: List[ImageScore] = field(default_factory=list)


@dataclass
class VisualEvalReport:
    """变体优选报告"""
    variants: List[VariantScore] = field(default_factory=list)
    best: Optional[VariantScore] = None
    ranking: List[Tuple[str, float]] = field(default_factory=list)  # (label, total) 降序
    backend: str = "heuristic"
    offline: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend, "offline": self.offline,
            "best": self.best.label if self.best else None,
            "ranking": [[l, round(t, 2)] for l, t in self.ranking],
            "variants": [
                {"label": v.label, "params": v.params, "total": v.total,
                 "per_dim_avg": v.per_dim_avg,
                 "temporal_energy": v.temporal_energy,
                 "images": [s.to_dict() for s in v.image_scores]}
                for v in self.variants
            ],
        }


# ── Rubric 预设 ─────────────────────────────────────────────────────
def default_ae_rubric() -> Rubric:
    """AE 合成默认评分量表：冲击力/构图/色彩/特效/文字/风格/节拍"""
    return Rubric(id=RUBRIC_AE_DEFAULT, dimensions=[
        RubricDimension("impact", "视觉冲击力", 1.2, "画面是否抓眼、动势是否强烈"),
        RubricDimension("composition", "构图与层级", 1.0, "主体与背景层次、留白与重心是否合理"),
        RubricDimension("color", "色彩和谐", 1.0, "配色是否统一、饱和与明度是否协调"),
        RubricDimension("fx_quality", "特效完成度", 1.2, "发光/粒子/分色等特效是否自然无穿帮"),
        RubricDimension("text_readability", "文字可读性", 1.0, "文字是否清晰、字号对比是否合适"),
        RubricDimension("style_consistency", "风格一致性", 0.8, "整体是否贴合指定风格卡"),
        RubricDimension("beat_sync", "节拍同步感", 0.8, "画面冲击是否与音乐节拍对齐（单帧难判可给3）"),
    ])


def text_focus_rubric() -> Rubric:
    """文字动效专项量表"""
    return Rubric(id=RUBRIC_TEXT_FOCUS, dimensions=[
        RubricDimension("impact", "视觉冲击力", 1.0, "文字入场是否抓眼"),
        RubricDimension("text_readability", "文字可读性", 1.5, "字形清晰、对比足够、不被特效吞掉"),
        RubricDimension("animation_smoothness", "动画流畅度", 1.2, "入场/出场/循环是否顺滑无跳变"),
        RubricDimension("fx_quality", "特效完成度", 1.0, "发光/分色/抖动等是否自然"),
        RubricDimension("color", "色彩和谐", 0.8, "文字与背景配色协调"),
    ])


RUBRIC_PRESETS = {
    RUBRIC_AE_DEFAULT: default_ae_rubric,
    RUBRIC_TEXT_FOCUS: text_focus_rubric,
}


def get_rubric(preset: str = RUBRIC_AE_DEFAULT) -> Rubric:
    if preset not in RUBRIC_PRESETS:
        raise ValueError(f"未知 Rubric 预设 {preset}，可选 {list(RUBRIC_PRESETS)}")
    return RUBRIC_PRESETS[preset]()


# ── 多模态评分 ──────────────────────────────────────────────────────
_AE_SCORE_SYSTEM = (
    "你是后期特效合成质量评审。对渲染帧按维度打 1-5 分（1=差，5=优秀），"
    "每个维度给一句简短中文理由。只输出一个 JSON 对象，不要输出任何其他文字或代码块标记。"
)


def build_score_prompt(rubric: Rubric, context: str = "") -> str:
    dims = ", ".join(
        f'"{d.name}"({d.label}, {d.desc})' for d in rubric.dimensions)
    out_fmt = ", ".join(
        f'"{d.name}": {{"score": 1-5, "comment": "一句话理由"}}'
        for d in rubric.dimensions)
    ctx = f" 渲染上下文：{context}\n" if context else ""
    return (
        f"请对这张渲染帧评分。{ctx}"
        f"评分维度：{dims}\n"
        f"输出格式：{{\"dims\": {{{out_fmt}}}}}\n"
        f"只输出 JSON。"
    )


def parse_score_json(text: str, rubric: Rubric) -> List[DimensionScore]:
    """从模型输出中稳健提取评分 JSON（容忍代码块/前后缀散文）。

    失败抛 ValueError，由调用方降级启发式。
    """
    if not text:
        raise ValueError("空响应")
    # 提取第一个 '{' 到最后一个 '}' 的片段，容忍 ```json 围栏与前后缀
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"响应中无 JSON 对象: {text[:120]!r}")
    snippet = text[start:end + 1]
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e} | {snippet[:120]!r}")
    dims_raw = data.get("dims", data) if isinstance(data, dict) else {}
    if not isinstance(dims_raw, dict):
        raise ValueError(f"dims 字段类型异常: {type(dims_raw)}")
    weights = rubric.weights()
    scores: List[DimensionScore] = []
    for d in rubric.dimensions:
        raw = dims_raw.get(d.name)
        val = None
        comment = ""
        if isinstance(raw, dict):
            val = raw.get("score")
            comment = str(raw.get("comment", ""))[:200]
        elif isinstance(raw, (int, float)):
            val = raw
        try:
            val = float(val) if val is not None else None
        except (TypeError, ValueError):
            val = None
        if val is None or not (SCORE_MIN <= val <= SCORE_MAX):
            # 单维度缺失不炸整体，给中性分并标注
            comment = (comment + " [缺省3.0]").strip()
            val = 3.0
        scores.append(DimensionScore(name=d.name, score=float(val),
                                     weight=weights[d.name], comment=comment))
    return scores


def weighted_total(scores: Sequence[DimensionScore]) -> float:
    """加权总分归一到 0-100"""
    if not scores:
        return 0.0
    sw = sum(s.score * s.weight for s in scores)
    w = sum(s.weight for s in scores)
    if w <= 0:
        return 0.0
    return round((sw / w - SCORE_MIN) / (SCORE_MAX - SCORE_MIN) * 100.0, 2)


# ── 启发式离线指标（honest degradation 弱代理）───────────────────────
def heuristic_dimension_scores(bgr) -> List[Tuple[str, float, str]]:
    """从单帧图像算启发式指标，映射到 AE 默认量表的 (name, score1-5, comment)。

    明确声明：这是弱代理（弱于 VLM 人眼近似），仅用于离线兜底与单元测试。
    """
    import cv2
    import numpy as np

    small = cv2.resize(bgr, (320, 180), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV).astype(np.float32)

    brightness = float(gray.mean()) / 255.0
    contrast = float(gray.std()) / 64.0
    saturation = float(hsv[:, :, 1].mean()) / 255.0
    # 清晰度：拉普拉斯方差，归一 ~ [0, 1]（500 为经验饱和点）
    lap_var = float(cv2.Laplacian(gray, cv2.CV_32F).var())
    sharpness = min(lap_var / 500.0, 1.0)
    # 结构感：3x3 网格 Sobel 边缘密度标准差（构图/层级代理）
    sobel = cv2.Sobel(gray, cv2.CV_32F, 1, 1, ksize=3)
    edge = np.abs(sobel)
    h, w = edge.shape
    densities = []
    for gy in range(3):
        for gx in range(3):
            cell = edge[gy * h // 3:(gy + 1) * h // 3, gx * w // 3:(gx + 1) * w // 3]
            densities.append(float(cell.mean()))
    structure = min(float(np.std(densities)) / 30.0, 1.0)
    # 上三分之一清晰度（文字通常在上部）
    top_lap = float(cv2.Laplacian(gray[0:h // 3, :], cv2.CV_32F).var())
    text_sharp = min(top_lap / 500.0, 1.0)

    def to5(x: float) -> float:
        return round(1.0 + 4.0 * min(max(x, 0.0), 1.0), 2)

    # 亮度适中加分（过曝/死黑扣分）
    bright_balance = 1.0 - min(abs(brightness - 0.45) * 2.2, 1.0)
    return [
        ("impact", to5(0.5 * contrast + 0.5 * sharpness), "对比+清晰度代理"),
        ("composition", to5(0.5 * structure + 0.5 * bright_balance), "网格结构+亮度平衡代理"),
        ("color", to5(0.6 * saturation + 0.4 * bright_balance), "饱和+亮度平衡代理"),
        ("fx_quality", to5(sharpness), "清晰度代理"),
        ("text_readability", to5(text_sharp), "上部清晰度代理"),
        ("style_consistency", 3.0, "单帧不可判，中性分"),
        ("beat_sync", 3.0, "单帧不可判，中性分"),
    ]


def temporal_energy_proxy(frames_bgr: Sequence[Any]) -> float:
    """帧间灰度差均值 → 节奏感代理 [0,1]。帧数 <2 时返回 0。"""
    if len(frames_bgr) < 2:
        return 0.0
    import cv2
    import numpy as np
    diffs = []
    prev = None
    for f in frames_bgr:
        g = cv2.cvtColor(cv2.resize(f, (160, 90), interpolation=cv2.INTER_AREA),
                         cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None:
            diffs.append(float(np.abs(g - prev).mean()))
        prev = g
    mean_diff = float(np.mean(diffs)) if diffs else 0.0
    return round(min(mean_diff / 20.0, 1.0), 3)


# ── 主类 ────────────────────────────────────────────────────────────
class VisualEvalGateway:
    """视觉评估网关（M2）

    Parameters:
        backend:  "auto"（默认，先 VLM 后启发式）| "vlm"（只用模型，失败抛错）
                  | "heuristic"（强制离线）
        model:    显式模型名；None 时交给 llm_gateway 按 VISION 档位路由
        rubric:   Rubric 或预设 id
        cache_dir: 评分缓存目录；None 禁用缓存
        concurrency: 多帧评分的并发上限
        context:  打进 prompt 的渲染上下文（如 "AMV 高燃模板 glow_r30 变体"）
    """

    def __init__(self, backend: str = "auto", model: Optional[str] = None,
                 rubric: Any = RUBRIC_AE_DEFAULT,
                 cache_dir: Optional[str] = None,
                 concurrency: int = 2, context: str = ""):
        if backend not in ("auto", "vlm", "heuristic"):
            raise ValueError(f"backend 非法: {backend}")
        self.backend = backend
        self.model = model
        self.rubric = rubric if isinstance(rubric, Rubric) else get_rubric(rubric)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.concurrency = max(1, int(concurrency))
        self.context = context
        self._vlm_broken = False          # 进程内粘性降级：一次失败后全部走启发式
        self._vlm_broken_reason = ""

    # ── 帧采样 ───────────────────────────────────────────────────
    def load_image_b64(self, image_path: str, quality: int = 85) -> Tuple[str, str]:
        """读图 → (base64_jpeg, md5)。md5 对编码后的 JPEG 计算。"""
        import cv2
        import numpy as np
        p = Path(image_path)
        if not p.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")
        img = cv2.imread(str(p))
        if img is None:
            raise ValueError(f"无法解码图片: {image_path}")
        return self.encode_frame(img, quality)

    @staticmethod
    def encode_frame(frame_bgr: Any, quality: int = 85) -> Tuple[str, str]:
        """BGR ndarray → (base64_jpeg, md5)。md5 对编码后 JPEG 字节计算（内容寻址）。"""
        import cv2
        ok, buf = cv2.imencode(".jpg", frame_bgr,
                               [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        if not ok:
            raise ValueError("JPEG 编码失败")
        raw = buf.tobytes()
        return base64.b64encode(raw).decode("ascii"), hashlib.md5(raw).hexdigest()

    def frames_from_video(self, video_path: str, times: Optional[Sequence[float]] = None,
                          max_frames: int = 8, resize: Any = None) -> List[Tuple[float, Any]]:
        """视频 → [(t_sec, BGR帧)]。times 指定时间点；None 时均匀采样 max_frames 帧。"""
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频: {video_path}")
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            duration = total / fps if fps > 0 else 0.0
            if times is None:
                n = max(1, int(max_frames))
                if duration <= 0:
                    times = [0.0]
                else:
                    times = [duration * (i + 0.5) / n for i in range(n)]
            out: List[Tuple[float, Any]] = []
            for t in times:
                cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000.0)
                ok, frame = cap.read()
                if not ok:
                    continue
                if resize is not None:
                    frame = cv2.resize(frame, resize, interpolation=cv2.INTER_AREA)
                out.append((float(t), frame))
            return out
        finally:
            cap.release()

    # ── 缓存 ─────────────────────────────────────────────────────
    def _cache_path(self, md5: str) -> Optional[Path]:
        if not self.cache_dir:
            return None
        return self.cache_dir / f"{md5[:24]}.json"

    def _cache_load(self, md5: str) -> Optional[ImageScore]:
        p = self._cache_path(md5)
        if not p or not p.exists():
            return None
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("rubric_id") != self.rubric.id:
                return None
            dims = [DimensionScore(name=d["name"], score=d["score"],
                                   weight=d["weight"], comment=d["comment"])
                    for d in data.get("dimensions", [])]
            return ImageScore(
                image_ref=data.get("image_ref", ""), md5=md5,
                total=data.get("total", 0.0), dimensions=dims,
                model=data.get("model", ""), provider=data.get("provider", ""),
                backend=data.get("backend", "heuristic"),
                offline=data.get("offline", True),
                fallback_reason=data.get("fallback_reason", ""),
                from_cache=True, raw=data.get("raw", ""))
        except Exception as e:
            logger.warning(f"评分缓存读取失败: {e}")
            return None

    def _cache_save(self, score: ImageScore) -> None:
        p = self._cache_path(score.md5)
        if not p:
            return
        try:
            payload = score.to_dict()
            payload["rubric_id"] = self.rubric.id
            with open(p, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"评分缓存写入失败: {e}")

    # ── 核心评分 ─────────────────────────────────────────────────
    async def score_b64(self, b64: str, md5: str = "", image_ref: str = "") -> ImageScore:
        """对一张 base64 帧评分（含缓存命中与离线降级）"""
        md5 = md5 or hashlib.md5(b64.encode("ascii")).hexdigest()
        cached = self._cache_load(md5)
        if cached is not None:
            cached.image_ref = image_ref or cached.image_ref
            return cached

        t0 = time.perf_counter()
        score: Optional[ImageScore] = None
        if self.backend in ("auto", "vlm") and not self._vlm_broken:
            try:
                score = await self._score_vlm(b64, md5, image_ref)
            except Exception as e:
                self._vlm_broken = True
                self._vlm_broken_reason = str(e)[:200]
                logger.warning(f"VLM 评分失败，降级启发式: {e}")
                if self.backend == "vlm":
                    raise
        if score is None:
            score = self._score_heuristic(b64, md5, image_ref,
                                          self._vlm_broken_reason)
        score.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        self._cache_save(score)
        return score

    async def _score_vlm(self, b64: str, md5: str, image_ref: str) -> ImageScore:
        """走 llm_gateway vision 通道评分（Qwen3-VL-30B-A3B 或 VISION 档位 Provider）"""
        from core.llm_gateway import llm_gateway, TaskType  # 惰性导入，离线环境不拖累

        # 强制重装配 Provider：网关单例可能在本进程更早的导入期以空配置初始化
        # （真机实测：不 force 时 providers 为空 → "LLM 网关未配置" 降级启发式）
        try:
            llm_gateway.ensure_configured(force=True)
        except Exception as e:
            logger.warning(f"llm_gateway 重装配失败: {e}")

        prompt = build_score_prompt(self.rubric, self.context)
        response = await llm_gateway.chat_with_routing(
            message=prompt,
            task_type=TaskType.VISION_UNDERSTANDING,
            system_prompt=_AE_SCORE_SYSTEM,
            temperature=0.2,
            max_tokens=800,
            images=[b64],
        )
        if not getattr(response, "success", False) or not getattr(response, "content", ""):
            raise RuntimeError(f"VLM 响应失败: {getattr(response, 'error', 'no content')}")
        dims = parse_score_json(response.content, self.rubric)
        return ImageScore(
            image_ref=image_ref, md5=md5, total=weighted_total(dims),
            dimensions=dims, model=response.model or "", provider=response.provider or "",
            backend="vlm", offline=False, raw=response.content[:2000])

    def _score_heuristic(self, b64: str, md5: str, image_ref: str,
                         reason: str = "") -> ImageScore:
        import cv2
        import numpy as np
        buf = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("启发式解码失败")
        weights = self.rubric.weights()
        dims: List[DimensionScore] = []
        known = {n: (s, c) for n, s, c in heuristic_dimension_scores(img)}
        for d in self.rubric.dimensions:
            s, comment = known.get(d.name, (3.0, "无代理指标，中性分"))
            dims.append(DimensionScore(name=d.name, score=s,
                                       weight=weights.get(d.name, 1.0),
                                       comment=f"[heuristic] {comment}"))
        return ImageScore(
            image_ref=image_ref, md5=md5, total=weighted_total(dims),
            dimensions=dims, backend="heuristic", offline=True,
            fallback_reason=reason or "backend=heuristic",
            raw="heuristic")

    async def score_path(self, image_path: str) -> ImageScore:
        b64, md5 = self.load_image_b64(image_path)
        return await self.score_b64(b64, md5, image_ref=str(image_path))

    async def score_video(self, video_path: str, times: Optional[Sequence[float]] = None,
                          max_frames: int = 8) -> List[ImageScore]:
        frames = self.frames_from_video(video_path, times, max_frames)
        sem = asyncio.Semaphore(self.concurrency)

        async def _one(t: float, frame: Any) -> ImageScore:
            b64, md5 = self.encode_frame(frame)
            async with sem:
                return await self.score_b64(b64, md5, image_ref=f"{video_path}@{t:.2f}s")

        return await asyncio.gather(*[_one(t, f) for t, f in frames])

    async def compare_variants(self, variants: List[Dict[str, Any]],
                               rubric: Any = None) -> VisualEvalReport:
        """参数变体优选：评分 → 帧均聚合 → 排序。

        variants: [{"label": str, "image_paths": List[str], "params": Dict}, ...]
        """
        if rubric is not None:
            saved = self.rubric
            self.rubric = rubric if isinstance(rubric, Rubric) else get_rubric(rubric)
        try:
            report = await self._compare_variants_inner(variants)
        finally:
            if rubric is not None:
                self.rubric = saved
        return report

    async def _compare_variants_inner(self, variants: List[Dict[str, Any]]) -> VisualEvalReport:
        vs: List[VariantScore] = []
        offline = True
        backends: List[str] = []
        for v in variants:
            label = str(v.get("label", ""))
            paths = list(v.get("image_paths", []) or [])
            params = dict(v.get("params", {}) or {})
            if not paths:
                raise ValueError(f"变体 {label} 无 image_paths")
            sem = asyncio.Semaphore(self.concurrency)

            async def _one(p: str) -> ImageScore:
                b64, md5 = self.load_image_b64(p)
                async with sem:
                    return await self.score_b64(b64, md5, image_ref=str(p))

            scores = await asyncio.gather(*[_one(p) for p in paths])
            total = sum(s.total for s in scores) / len(scores)
            per_dim: Dict[str, List[float]] = {}
            for s in scores:
                for d in s.dimensions:
                    per_dim.setdefault(d.name, []).append(d.score)
            per_dim_avg = {k: round(sum(x) / len(x), 2) for k, x in per_dim.items()}
            # 节奏感代理：帧序列（离线后端尤其有用，VLM 后端仅作参考）
            frames = []
            for p in paths:
                try:
                    import cv2
                    f = cv2.imread(p)
                    if f is not None:
                        frames.append(f)
                except Exception:
                    pass
            vs.append(VariantScore(
                label=label, params=params, total=round(total, 2),
                per_dim_avg=per_dim_avg,
                temporal_energy=temporal_energy_proxy(frames),
                image_scores=scores))
            for s in scores:
                if not s.offline:
                    offline = False
                backends.append(s.backend)

        vs.sort(key=lambda x: x.total, reverse=True)
        return VisualEvalReport(
            variants=vs, best=vs[0] if vs else None,
            ranking=[(v.label, v.total) for v in vs],
            backend=("vlm" if "vlm" in backends else "heuristic"),
            offline=offline)

    # ── 同步薄包装 ───────────────────────────────────────────────
    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def score_path_sync(self, image_path: str) -> ImageScore:
        return self._run(self.score_path(image_path))

    def score_b64_sync(self, b64: str, md5: str = "",
                       image_ref: str = "") -> ImageScore:
        """base64 帧同步评分（无 asyncio 环境下用）"""
        return self._run(self.score_b64(b64, md5, image_ref))

    def score_frame_sync(self, frame_bgr: Any, image_ref: str = "") -> ImageScore:
        """BGR ndarray 帧同步评分（M1c 渲染帧直评入口）"""
        b64, md5 = self.encode_frame(frame_bgr)
        return self.score_b64_sync(b64, md5, image_ref=image_ref)

    def score_video_sync(self, video_path: str, times: Optional[Sequence[float]] = None,
                         max_frames: int = 8) -> List[ImageScore]:
        return self._run(self.score_video(video_path, times, max_frames))

    def compare_variants_sync(self, variants: List[Dict[str, Any]],
                              rubric: Any = None) -> VisualEvalReport:
        return self._run(self.compare_variants(variants, rubric))


__all__ = [
    "VisualEvalGateway", "Rubric", "RubricDimension", "DimensionScore",
    "ImageScore", "VariantScore", "VisualEvalReport",
    "get_rubric", "default_ae_rubric", "text_focus_rubric",
    "build_score_prompt", "parse_score_json", "weighted_total",
    "heuristic_dimension_scores", "temporal_energy_proxy",
    "RUBRIC_AE_DEFAULT", "RUBRIC_TEXT_FOCUS",
]

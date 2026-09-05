"""ai/camera_decision.py - 决策层强化 (T3 Step 2)

导演感知素材运镜: 让导演知道每段素材已有什么运镜, 做出更好的叠加决策。

三大能力:
  1. SourceCameraInventory — 素材运镜库存 (分析 + 缓存 + 互补推荐)
  2. transition_compatibility — 运镜衔接平滑度 (0-1, 越高越平滑)
  3. emotion_camera_suggest — 情绪→运镜推荐

综合入口: suggest_camera_for_shot(mood, source_camera, prev_camera)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from core.camera_movement_classifier import (
    CAMERA_LABELS,
    classify_video,
    batch_classify,
)

logger = logging.getLogger(__name__)

# 运镜库存磁盘缓存目录: 按 (路径, mtime, 大小) 键控, 避免每次渲染
# 重跑 4K 光流分析 (实测单素材 31.5s, 7素材≈3-5分钟, 且结果不变)
_CAM_INV_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cache", "camera_inventory")


# ============================================================
# 1. SourceCameraInventory — 素材运镜库存
# ============================================================

# 互补运镜表: 素材已有运镜 → 推荐的叠加运镜 (避免同质化)
_COMPLEMENT_MAP: Dict[str, str] = {
    "static":   "zoom_in",
    "pan_left": "zoom_in",
    "pan_right": "zoom_out",
    "zoom_in":  "pan_left",
    "zoom_out": "pan_right",
    "tilt_up":  "zoom_in",
    "tilt_down": "zoom_out",
    "diag_pan": "zoom_in",
    "zoom_back": "static",
    "orbit":    "static",
    "push":     "zoom_out",
    "complex":  "static",
    "unknown":  "zoom_in",
}


class SourceCameraInventory:
    """素材运镜库存: 分析每段素材的运镜, 缓存结果, 提供互补推荐。

    用法:
        inv = SourceCameraInventory()
        inv.analyze("素材A.mp4")       # → {"label": "pan_left", "confidence": 0.8, ...}
        inv.complementary("pan_left")  # → "zoom_in" (互补运镜)
        inv.inject("素材B.mp4", label="zoom_in", confidence=0.95)  # 人工标注
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lora_clf = None  # 懒加载 LoRA 分类器 (A5)
        self._hier_clf = None  # 懒加载分层 CNN+VLM (L0.5, 2026-08-27 接入)

    def _get_lora_clf(self):
        """懒加载动漫运镜 LoRA 分类器 (GPU 可用时优先, 失败返回 None 走规则)。"""
        if self._lora_clf is False:
            return None
        if self._lora_clf is not None:
            return self._lora_clf
        try:
            from models.anime_camera_classifier import AnimeCameraClassifier
            self._lora_clf = AnimeCameraClassifier()
            logger.info("LoRA 运镜分类器就绪 (A5)")
            return self._lora_clf
        except Exception as exc:  # noqa: BLE001
            logger.warning("LoRA 分类器不可用, 降级光流规则: %s", exc)
            self._lora_clf = False
            return None

    def _get_hier_clf(self):
        """懒加载分层 CNN+VLM 分类器 (2026-08-27 生产接入)。

        CNN 2 分类 (动/静, 秒级) → 动作类交给 VLM 专家 (zoom/tilt-orbit,
        4bit 5.82GB 本地)。AEKV_HIER_CAM=0 可关闭。三角验证表明 AMV 域
        3 类标签置信度有限 → confidence 透传下游自行取舍。
        """
        import os as _os
        if _os.environ.get("AEKV_HIER_CAM", "1") != "1":
            return None
        if self._hier_clf is False:
            return None
        if self._hier_clf is not None:
            return self._hier_clf
        try:
            from models.camera_classifier.camera_classifier_hierarchical                 import HierarchicalCameraClassifier
            self._hier_clf = HierarchicalCameraClassifier()
            logger.info("分层 CNN+VLM 运镜分类器就绪 (L0.5)")
            return self._hier_clf
        except Exception as exc:  # noqa: BLE001
            logger.warning("分层分类器不可用, 走光流规则: %s", exc)
            self._hier_clf = False
            return None

    def unload(self) -> None:
        """释放懒加载的 LoRA/分层分类器与其显存 (运镜标注完成后调用)。

        分层 VLM 4bit ~5.8GB + VideoMAE 常驻会挤爆阶段⑤成片评分的 8GB 卡
        (2026-09-05 OOM 根治: 引用置空 → gc → empty_cache)。
        """
        import gc
        self._lora_clf = None
        self._hier_clf = None
        try:
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass

    def analyze(self, video_path: str) -> Dict[str, Any]:
        """分析单个素材的运镜。双层缓存:
          L0 LoRA 动漫运镜分类器 (A5, 高精度) → L1 整文件缓存 → L2 分段光流
        """
        if video_path in self._cache:
            return self._cache[video_path]

        # 磁盘缓存命中
        try:
            _st = os.stat(video_path)
            _h = hashlib.md5(
                (video_path + "|" + str(int(_st.st_mtime)) + "|" + str(_st.st_size))
                .encode()).hexdigest()[:12]
            _cache_file = os.path.join(_CAM_INV_CACHE_DIR, f"{_h}.json")
            if os.path.exists(_cache_file):
                with open(_cache_file, encoding="utf-8") as _f:
                    _entry = json.load(_f)
                self._cache[video_path] = _entry
                return _entry
        except (OSError, ValueError, json.JSONDecodeError):
            pass

        # L0.5: 分层 CNN+VLM (LoRA 不可用时的升级路径; 2026-08-27)
        if os.environ.get("AEKV_NO_LORA", "0") == "1":
            _lora_bypass = True
        else:
            _lora_bypass = False
        clf = None if _lora_bypass else self._get_lora_clf()
        if clf is None:
            hier = self._get_hier_clf()
            if hier is not None:
                try:
                    _COARSE2FINE = {"zoom": "zoom_in", "tilt-orbit": "orbit",
                                    "static": "static", "motion": "complex"}
                    pred, conf, method, desc = hier.predict(video_path, use_vlm=True)
                    entry = {
                        "label": _COARSE2FINE.get(pred, "complex"),
                        "confidence": round(float(conf), 3),
                        "source": f"hier_{method}",
                        "coarse": pred,
                        "description": desc,
                        "flow_stats": {},
                        "per_segment": [],
                    }
                    self._cache[video_path] = entry
                    return self._disk_cache_put(video_path, entry)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("分层分类失败, 降级光流规则: %s", exc)

        # L0: LoRA 分类器优先 (A5 接入点)
        clf = self._get_lora_clf()
        if clf is not None:
            try:
                r = clf.classify_video(video_path)
                if r.get("source") not in (None, "unknown"):
                    entry = {
                        "label": r["label"],
                        "confidence": r["confidence"],
                        "source": r.get("source", "videomae-lora"),
                        "coarse": r.get("coarse"),
                        "flow_stats": {},
                        "per_segment": [],
                    }
                    self._cache[video_path] = entry
                    try:
                        os.makedirs(_CAM_INV_CACHE_DIR, exist_ok=True)
                        with open(_cache_file, "w", encoding="utf-8") as _f:
                            json.dump(entry, _f, ensure_ascii=False)
                    except (OSError, UnboundLocalError):
                        pass
                    return entry
            except Exception as exc:  # noqa: BLE001
                logger.warning("LoRA 分类失败, 降级光流规则: %s", exc)

        try:
            # L1 miss → L2 分段缓存 (裁切素材复用未变块, 冷启动与整文件等价)
            try:
                from core.camera_movement_classifier import classify_video_cached
                result = classify_video_cached(video_path)
            except Exception as _seg_e:
                logger.warning("分段分类失败, 降级整文件: %s", _seg_e)
                result = classify_video(video_path)
            entry = {
                "label": result["dominant"],
                "confidence": result["confidence"],
                "source": "flow_rule",
                "flow_stats": result["flow_stats"],
                "per_segment": result.get("per_segment", []),
            }
        except Exception:
            logger.warning("素材运镜分析失败: %s", video_path, exc_info=True)
            entry = {"label": "unknown", "confidence": 0.0,
                     "flow_stats": {}, "per_segment": []}

        self._cache[video_path] = entry
        # 写磁盘缓存 (失败不阻断)
        try:
            os.makedirs(_CAM_INV_CACHE_DIR, exist_ok=True)
            with open(_cache_file, "w", encoding="utf-8") as _f:
                json.dump(entry, _f, ensure_ascii=False)
        except (OSError, UnboundLocalError):
            pass
        return entry


    def _disk_cache_put(self, video_path: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        """L0.5 分层分类结果的磁盘缓存 (键与 L1 读侧一致, 失败不阻断)。"""
        try:
            _st = os.stat(video_path)
            _h = hashlib.md5(
                (video_path + "|" + str(int(_st.st_mtime)) + "|" + str(_st.st_size))
                .encode()).hexdigest()[:12]
            os.makedirs(_CAM_INV_CACHE_DIR, exist_ok=True)
            with open(os.path.join(_CAM_INV_CACHE_DIR, f"{_h}.json"), "w",
                      encoding="utf-8") as _f:
                json.dump(entry, _f, ensure_ascii=False)
        except (OSError, ValueError):
            pass
        return entry

    def batch_analyze(self, video_paths: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        """批量分析。"""
        return {vp: self.analyze(vp) for vp in video_paths}

    def inject(self, video_path: str, *, label: str, confidence: float) -> None:
        """外部注入运镜标签 (人工标注 / MovieShots 预训练结果)。"""
        if label not in CAMERA_LABELS:
            logger.warning("注入未知标签 '%s', 忽略", label)
            return
        self._cache[video_path] = {
            "label": label, "confidence": confidence,
            "flow_stats": {}, "per_segment": [],
            "source": "injected",
        }

    def complementary(self, source_label: str) -> str:
        """给定素材运镜, 返回互补的叠加运镜 (避免同质化)。

        原则: 素材已有的运镜不再叠加, 选视觉差异最大的。
        """
        return _COMPLEMENT_MAP.get(source_label, "zoom_in")


# ============================================================
# 2. transition_compatibility — 运镜衔接平滑度
# ============================================================

# 衔接兼容矩阵 (0.0=生硬, 1.0=极平滑)
# 对称矩阵, 键排序后查表
_TRANSITION_COMPAT: Dict[tuple, float] = {}


def _init_transition_matrix() -> None:
    """初始化衔接矩阵。"""
    if _TRANSITION_COMPAT:
        return

    labels = CAMERA_LABELS
    # 默认: 中等兼容
    for a in labels:
        for b in labels:
            _TRANSITION_COMPAT[(a, b)] = 0.5

    # 同类运镜 → 高兼容
    for l in labels:
        _TRANSITION_COMPAT[(l, l)] = 0.85

    # static 与任何运镜 → 高兼容 (cut 即可)
    for l in labels:
        _TRANSITION_COMPAT[("static", l)] = 0.7
        _TRANSITION_COMPAT[(l, "static")] = 0.7

    # 反向平移 → 生硬
    _TRANSITION_COMPAT[("pan_left", "pan_right")] = 0.15
    _TRANSITION_COMPAT[("pan_right", "pan_left")] = 0.15
    _TRANSITION_COMPAT[("tilt_up", "tilt_down")] = 0.15
    _TRANSITION_COMPAT[("tilt_down", "tilt_up")] = 0.15

    # 反向 zoom → 中等生硬 (zoom_back 本身就是这个效果)
    _TRANSITION_COMPAT[("zoom_in", "zoom_out")] = 0.35
    _TRANSITION_COMPAT[("zoom_out", "zoom_in")] = 0.35

    # zoom ↔ pan → 常见组合, 高兼容
    for z in ("zoom_in", "zoom_out"):
        for p in ("pan_left", "pan_right"):
            _TRANSITION_COMPAT[(z, p)] = 0.65
            _TRANSITION_COMPAT[(p, z)] = 0.65

    # push 与 zoom_in → 高兼容 (都是推近)
    _TRANSITION_COMPAT[("push", "zoom_in")] = 0.75
    _TRANSITION_COMPAT[("zoom_in", "push")] = 0.75

    # orbit 与 pan → 高兼容
    for p in ("pan_left", "pan_right"):
        _TRANSITION_COMPAT[("orbit", p)] = 0.6
        _TRANSITION_COMPAT[(p, "orbit")] = 0.6

    # complex 与任何 → 低兼容 (接什么都奇怪)
    _TRANSITION_COMPAT[("complex", "static")] = 0.4
    _TRANSITION_COMPAT[("static", "complex")] = 0.4


def transition_compatibility(camera_a: str, camera_b: str) -> float:
    """两个运镜的衔接平滑度。0.0=生硬, 1.0=极平滑。

    用于导演在相邻镜头间选择运镜时, 惩罚生硬切换。
    """
    _init_transition_matrix()
    key = (camera_a, camera_b)
    if key in _TRANSITION_COMPAT:
        return _TRANSITION_COMPAT[key]
    # 未知标签: 中等兼容
    return 0.5


# ============================================================
# 3. emotion_camera_suggest — 情绪→运镜推荐
# ============================================================

# 情绪弧段 → 推荐运镜列表 (按优先级排序)
_EMOTION_CAMERA_MAP: Dict[str, List[str]] = {
    "intro":  ["static", "zoom_in", "zoom_out"],
    "build":  ["pan_left", "pan_right", "diag_pan"],
    "drop":   ["zoom_in", "push", "zoom_back"],
    "climax": ["zoom_in", "push", "orbit", "pan_left", "pan_right"],
    "break":  ["static", "zoom_out", "diag_pan"],
    "outro":  ["zoom_out", "static", "pan_left"],
}

# 默认运镜池 (未知情绪)
_DEFAULT_CAMERA_SUGGESTIONS: List[str] = [
    "pan_left", "pan_right", "zoom_in", "zoom_out", "static",
]


def emotion_camera_suggest(mood: str) -> List[str]:
    """根据情绪弧段推荐运镜列表 (按优先级排序)。

    Args:
        mood: 情绪弧段名 (intro/build/drop/climax/break/outro)

    Returns:
        运镜标签列表, 按推荐优先级排序
    """
    if mood in _EMOTION_CAMERA_MAP:
        return _EMOTION_CAMERA_MAP[mood][:]
    return _DEFAULT_CAMERA_SUGGESTIONS[:]


# ============================================================
# 4. suggest_camera_for_shot — 综合决策入口
# ============================================================

def suggest_camera_for_shot(
    mood: str,
    source_camera: str = "unknown",
    prev_camera: str = "unknown",
    recent: Sequence[str] = (),
    max_repeat: int = 2,
) -> str:
    """综合决策: 情绪 + 素材运镜 + 前一镜运镜 → 最终推荐运镜。

    决策逻辑:
      1. 从情绪推荐池获取候选
      2. 排除与素材运镜重复的 (避免同质化)
      3. 排除最近 max_repeat 镜已用过的运镜 (反锁死: 修复"同运镜
         衔接 0.85 高分导致整段同一种运镜"的问题, 实测 v23 build 段
         23 镜全 pan_left 即此缺陷)
      4. 排除与前一镜生硬衔接的 (避免跳切感)
      5. 从剩余候选中选衔接分数最高的

    Args:
        mood: 情绪弧段
        source_camera: 素材已有的运镜标签
        prev_camera: 前一镜的运镜标签
        recent: 最近几镜的运镜序列 (新→旧或旧→新均可, 取尾部窗口)
        max_repeat: 同一运镜最多允许在最近几镜内重复出现的窗口大小

    Returns:
        推荐的运镜标签
    """
    candidates = emotion_camera_suggest(mood)

    # 排除与素材运镜重复
    if source_camera and source_camera != "unknown":
        candidates = [c for c in candidates if c != source_camera]

    # 保留未加窗口约束的原始候选 (生硬兜底放宽时用)
    _origin = list(candidates)

    # 反锁死: 排除最近窗口内已用过的运镜 (候选池有剩余时才排除,
    # 避免过度约束导致降级到互补表)
    _window: List[str] = []
    if recent:
        _window = list(recent)[-max_repeat:]
        _fresh = [c for c in candidates if c not in _window]
        if _fresh:
            candidates = _fresh

    if not candidates:
        # 情绪池耗尽 → 用互补运镜
        return _COMPLEMENT_MAP.get(source_camera, "zoom_in")

    # 若有前一镜: 优先不与前一镜重复 (同类衔接虽"平滑"但产生单调感,
    # 反锁死原则下同类只作为耗尽后的兜底)
    if prev_camera and prev_camera != "unknown":
        _others = [c for c in candidates if c != prev_camera]
        if _others:
            candidates = _others
        candidates.sort(
            key=lambda c: transition_compatibility(prev_camera, c),
            reverse=True,
        )
        best = candidates[0]
        if transition_compatibility(prev_camera, best) < 0.2:
            # 生硬 → 尝试互补运镜, 但互补候选必须: 不在反锁死窗口内、
            # 不等于前一镜、且在原始候选池内; 否则接受当前选择
            # (反锁死优先于反生硬, 避免兜底又把刚用过的运镜找回来)
            _comp = _COMPLEMENT_MAP.get(source_camera, best)
            if _comp not in _window and _comp != prev_camera and _comp in _origin:
                return _comp
            return best
        return best

    return candidates[0]

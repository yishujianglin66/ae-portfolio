# -*- coding: utf-8 -*-
"""BeatLock — 节拍锚定特效（M3，[AE-sync] 对侧模块）

把 OpenMontage beatgrid（kick/strong/weak/rolls/moments/hard_stops）锚定到
CompositionTree 图层上，生成节拍驱动的 JSX 关键帧片段，通过契约注入点合并进
JsxProjectBuilder（M1b）产出的主工程脚本后执行。

不依赖 AE 真机：本模块只做 信号解析 → 锚点规划 → JSX 文本生成，
真机执行交给主会话 M1c 链路（Bridge 单槽防冲突）。

数据流:
    BGM ──analyze-beatgrid.py──▶ audiomap.json ──▶ BeatGrid
    BeatGrid + CompositionTree ──▶ BeatLock.plan ──▶ List[BeatAnchor]
    BeatLock.emit_jsx(anchors) ──▶ JSX 关键帧片段
    merge_jsx(base_jsx, fragment) ──▶ 合并后的工程脚本（M1c 直接 execute）

风格自适应动作表（beat_type → action）:
    amv/cyberpunk:  kick→punch(缩放冲击)  strong→flash(透明度闪光)
                    weak→pulse(轻微脉冲)  roll→shake(抖动)
                    hard_stop→flash+freeze 标记（timeRemap 待 M1c 后接入）
    ambient:        全部→pulse/跳过，保持抒情氛围不炸场

与主会话的边界:
  - 只读复用 core.composition_tree / core.synthesis_orchestrator，不修改其文件
  - 复用 production_director._load_beatgrid 的 audiomap 缓存键（tmp/audiomap_{h}.json），
    同一 BGM 的节拍网格两边共享，不重复跑分析
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.composition_tree import (  # noqa: E402
    CompositionTree,
    LayerSpec,
    validate_composition_tree,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_OM_BEATGRID_SCRIPT = (
    _PROJECT_ROOT / "external" / "OpenMontage" / ".agents" / "skills"
    / "music-to-video" / "scripts" / "analyze-beatgrid.py"
)
_DEFAULT_CACHE_DIR = _PROJECT_ROOT / "tmp"

# 节拍类型集合（与 OpenMontage audiomap 语义对齐）
BEAT_TYPES = ("kick", "strong", "weak")
GRID_EVENT_TYPES = ("kick", "strong", "weak")
ACTION_TYPES = ("punch", "flash", "pulse", "shake", "freeze")

# 模板 beat_event 与网格拍点匹配容差（秒）
_HINT_TOLERANCE = 0.12
# beat_events 去重容差（秒）
_MERGE_TOLERANCE = 0.05


# ── 数据模型 ─────────────────────────────────────────────────────────
@dataclass
class BeatGrid:
    """节拍网格（鼓类型/网格语义，与 production_director._load_beatgrid 对齐）"""
    kick: list[float] = field(default_factory=list)      # 低频重音 <150Hz（撞拍核心）
    strong: list[float] = field(default_factory=list)    # 强拍（正拍，排除 hihat）
    weak: list[float] = field(default_factory=list)      # 弱拍（排除 hihat）
    rolls: list[dict[str, Any]] = field(default_factory=list)      # 连击段
    moments: list[dict[str, Any]] = field(default_factory=list)    # 关键时刻
    hard_stops: list[float] = field(default_factory=list)          # 突然停止
    bpm: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    # ── 构造器 ─────────────────────────────────────────────────
    @classmethod
    def from_mapping(cls, d: dict[str, Any]) -> "BeatGrid":
        """从 production_director._load_beatgrid 返回的 dict 构建"""
        return cls(
            kick=sorted(set(float(t) for t in d.get("kick", []))),
            strong=sorted(set(float(t) for t in d.get("strong", []))),
            weak=sorted(set(float(t) for t in d.get("weak", []))),
            rolls=list(d.get("rolls", []) or []),
            moments=list(d.get("moments", []) or []),
            hard_stops=sorted(set(float(t) for t in d.get("hard_stops", []))),
            bpm=float(d["bpm"]) if d.get("bpm") else None,
            meta=dict(d.get("meta", {}) or {}),
        )

    @classmethod
    def from_beat_strength(cls, result: Any) -> "BeatGrid":
        """从 core.beat_strength_engine.BeatClassificationResult 构建（无 BGM 路径时）"""
        strong = [b.time_sec for b in getattr(result, "strong_beats", [])]
        medium = [b.time_sec for b in getattr(result, "medium_beats", [])]
        weak = [b.time_sec for b in getattr(result, "weak_beats", [])]
        return cls(kick=[], strong=sorted(set(strong)),
                   weak=sorted(set(medium + weak)),
                   bpm=float(getattr(result, "bpm", 0.0) or 0.0) or None)

    @classmethod
    def load(cls, bgm_path: str, cache_dir: str | None = None,
             timeout: int = 180) -> "BeatGrid" | None:
        """加载 OpenMontage beatgrid（与主会话共用 audiomap 缓存键）。

        失败返回 None（调用方回退），不阻断渲染。
        """
        try:
            import os
            import subprocess
            import sys as _sys
            if not _OM_BEATGRID_SCRIPT.exists():
                return None
            cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
            cache_dir.mkdir(parents=True, exist_ok=True)
            h = hashlib.md5(os.path.basename(str(bgm_path)).encode()).hexdigest()[:8]
            cache = cache_dir / f"audiomap_{h}.json"
            if not cache.exists():
                r = subprocess.run(
                    [_sys.executable, str(_OM_BEATGRID_SCRIPT), str(bgm_path),
                     "-o", str(cache)],
                    capture_output=True, timeout=timeout)
                if r.returncode != 0:
                    return None
            with open(cache, encoding="utf-8") as f:
                raw = json.load(f)
            return cls.from_audiomap(raw)
        except Exception as e:  # noqa: BLE001 — 加载失败必须静默回退
            print(f"      [BeatLock] beatgrid 加载失败(回退): {e}")
            return None

    @classmethod
    def from_audiomap(cls, raw: dict[str, Any]) -> "BeatGrid":
        """解析 audiomap.json（纯函数，便于单测）"""
        events = raw.get("events", []) or []
        kicks = [float(e["t"]) for e in events if e.get("drum") == "kick"]
        # 铁律：strong/weak 排除 hihat（镲片不"撞"），与 production_director 一致
        strongs = [float(e["t"]) for e in events
                   if e.get("grid") == "strong" and e.get("drum") != "hihat"]
        weaks = [float(e["t"]) for e in events
                 if e.get("grid") == "weak" and e.get("drum") != "hihat"]

        def _times(xs: Any) -> list[float]:
            """v2 audiomap 事件可为 {t,kind,...} 字典，也可为裸秒数（[AE-sync] 主会话修复）"""
            out: list[float] = []
            for x in xs or []:
                if isinstance(x, dict):
                    x = x.get("t")
                try:
                    out.append(float(x))
                except (TypeError, ValueError):
                    continue
            return out

        bpm = raw.get("bpm")
        if not bpm and kicks:
            # kick 间隔中位数估 BPM
            ks = sorted(set(kicks))
            if len(ks) >= 2:
                gaps = [b - a for a, b in zip(ks, ks[1:]) if b - a > 0.15]
                if gaps:
                    gaps.sort()
                    mid = len(gaps) // 2
                    med = (gaps[mid] + gaps[~mid]) / 2.0 if gaps else 0.0
                    bpm = 60.0 / med if med > 0 else None
        return cls(
            kick=sorted(set(kicks)), strong=sorted(set(strongs)),
            weak=sorted(set(weaks)),
            rolls=raw.get("rolls", []) or [],
            moments=raw.get("key_moments", []) or [],
            hard_stops=sorted(set(_times(raw.get("hard_stops", [])))),
            bpm=float(bpm) if bpm else None,
            meta={k: v for k, v in raw.items()
                  if k not in ("events", "rolls", "key_moments", "hard_stops", "bpm")},
        )

    # ── 查询 ───────────────────────────────────────────────────
    def events(self) -> list[tuple]:
        """拍点统一序列 [(time, beat_type)]，按时间排序"""
        out = [(t, "kick") for t in self.kick] + \
              [(t, "strong") for t in self.strong] + \
              [(t, "weak") for t in self.weak]
        return sorted(out, key=lambda x: x[0])

    def is_empty(self) -> bool:
        return not (self.kick or self.strong or self.weak
                    or self.rolls or self.hard_stops)


# ── 锚点 ─────────────────────────────────────────────────────────────
@dataclass
class BeatAnchor:
    """单个节拍锚点：某图层在节拍时刻执行某动作"""
    time: float
    beat_type: str                 # kick/strong/weak/hard_stop/roll
    action: str                    # ACTION_TYPES
    layer_id: str = ""
    layer_index: int = 0           # AE 图层索引（1=顶层），emit_jsx 用 comp.layer(i)
    params: dict[str, Any] = field(default_factory=dict)  # amp/dur_ms 等


@dataclass
class BeatLockResult:
    """锚定结果：富化的合成树副本 + 锚点 + JSX 片段"""
    tree: CompositionTree | None = None
    anchors: list[BeatAnchor] = field(default_factory=list)
    jsx_fragment: str = ""
    warnings: list[str] = field(default_factory=list)
    dropped: int = 0               # 越界/无目标被丢弃的拍点数


# ── 风格自适应动作表 ─────────────────────────────────────────────────
# beat_type → action（style_card 维度）
_STYLE_ACTION_MAP: dict[str, dict[str, str]] = {
    "amv": {"kick": "punch", "strong": "flash", "weak": "pulse",
            "hard_stop": "flash", "roll": "shake"},
    "cyberpunk": {"kick": "punch", "strong": "flash", "weak": "pulse",
                  "hard_stop": "flash", "roll": "shake"},
    "ambient": {"kick": "pulse", "strong": "pulse", "weak": "",
                "hard_stop": "pulse", "roll": ""},
}

# 动作默认参数
_ACTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "punch": {"amp": 1.12, "dur_ms": 160},
    "flash": {"opacity_low": 45, "dur_ms": 140},
    "pulse": {"amp": 1.05, "dur_ms": 120},
    "shake": {"amp_px": 8.0, "step_ms": 40, "dur_ms": 400},
    "freeze": {},
}


class BeatLock:
    """节拍锚定器

    Parameters:
        fps:         合成帧率（仅用于 JSX 时间格式化，不影响锚点时间）
        intensity:   全局强度系数 0.5-2.0（放大 punch/flash 幅度）
    """

    def __init__(self, fps: int = 30, intensity: float = 1.0):
        self.fps = int(fps)
        self.intensity = float(intensity)

    # ── 图层工具 ───────────────────────────────────────────────
    @staticmethod
    def _sorted_layers(tree: CompositionTree) -> list[LayerSpec]:
        """z_index 升序 = AE 从底到顶"""
        return sorted(tree.layers, key=lambda l: l.z_index)

    @staticmethod
    def _layer_index(tree: CompositionTree, layer: LayerSpec) -> int:
        """图层 → AE 索引（1=顶层）。JsxProjectBuilder 按 z 升序添加，
        故底层(z最小)索引 = len(layers)。"""
        ordered = BeatLock._sorted_layers(tree)
        pos = ordered.index(layer) if layer in ordered else 0
        return len(ordered) - pos

    def _default_target(self, tree: CompositionTree, beat_type: str) -> LayerSpec | None:
        """无模板提示时的默认锚定图层。

        kick/strong/hard_stop → 最顶层文字图层（主体），无文字则最顶层非背景；
        weak → breath 类调整层（脉冲呼吸），否则背景；
        roll → 最顶层非背景。
        """
        ordered = self._sorted_layers(tree)
        texts = [l for l in ordered if l.type == "text"]
        if beat_type in ("kick", "strong", "hard_stop"):
            if texts:
                return texts[-1]
        elif beat_type == "weak":
            for l in reversed(ordered):
                if l.type == "adjustment" or l.id in ("breath", "bg"):
                    return l
        non_bg = [l for l in ordered if l.type != "solid" or l.id != "bg"]
        for l in reversed(non_bg):
            return l
        return ordered[-1] if ordered else None

    def _resolve_target(self, tree: CompositionTree, beat_type: str,
                        t: float) -> LayerSpec | None:
        """模板 beat_events 提示优先（同类型+时间容差内），否则默认目标"""
        for ev in tree.beat_events:
            ev_bt = ev.get("beat_type")
            if ev_bt == "snare":  # 模板用 snare 语义，对齐网格 strong
                ev_bt = "strong"
            if ev_bt == beat_type and \
               abs(float(ev.get("time", -1)) - t) <= _HINT_TOLERANCE:
                lid = ev.get("layer_id")
                for layer in tree.layers:
                    if layer.id == lid:
                        return layer
        return self._default_target(tree, beat_type)

    # ── 锚点规划 ───────────────────────────────────────────────
    def plan(self, tree: CompositionTree, grid: BeatGrid) -> list[BeatAnchor]:
        """网格拍点 → 锚点列表（不修改 tree）"""
        style = tree.style_card
        action_map = _STYLE_ACTION_MAP.get(style, _STYLE_ACTION_MAP["amv"])
        anchors: list[BeatAnchor] = []
        ordered = self._sorted_layers(tree)

        def _add(t: float, beat_type: str, action: str) -> BeatAnchor | None:
            if not action:
                return None
            if not (0.0 <= t <= tree.duration + 1e-6):
                return None
            target = self._resolve_target(tree, beat_type, t)
            if target is None:
                return None
            params = dict(_ACTION_DEFAULTS[action])
            if action in ("punch", "pulse"):
                params["amp"] = 1.0 + (params["amp"] - 1.0) * self.intensity
            elif action == "flash":
                params["opacity_low"] = max(10.0, params["opacity_low"] / max(0.5, self.intensity))
            elif action == "shake":
                params["amp_px"] = float(params["amp_px"]) * self.intensity
            return BeatAnchor(time=float(t), beat_type=beat_type, action=action,
                              layer_id=target.id,
                              layer_index=self._layer_index(tree, target),
                              params=params)

        for t in grid.kick:
            a = _add(t, "kick", action_map.get("kick", ""))
            if a:
                anchors.append(a)
        for t in grid.strong:
            a = _add(t, "strong", action_map.get("strong", ""))
            if a:
                anchors.append(a)
        for t in grid.weak:
            a = _add(t, "weak", action_map.get("weak", ""))
            if a:
                anchors.append(a)
        for t in grid.hard_stops:
            a = _add(t, "hard_stop", action_map.get("hard_stop", ""))
            if a:
                anchors.append(a)
        # rolls → 连击段抖动（以 roll 起止时间的起点锚定）
        for roll in grid.rolls:
            try:
                t0 = float(roll.get("start", roll.get("t", 0)))
                t1 = float(roll.get("end", t0))
            except (TypeError, ValueError):
                continue
            action = action_map.get("roll", "")
            a = _add(t0, "roll", action)
            if a:
                a.params["dur_ms"] = max(a.params["dur_ms"],
                                         int((t1 - t0) * 1000) if t1 > t0 else a.params["dur_ms"])
                anchors.append(a)
        anchors.sort(key=lambda a: a.time)
        return anchors

    # ── 应用到合成树副本 ─────────────────────────────────────────
    def apply(self, tree: CompositionTree, grid: BeatGrid) -> BeatLockResult:
        """返回富化后的合成树副本 + 锚点（原 tree 不变）"""
        warnings: list[str] = []
        res = validate_composition_tree(tree)
        if not res["ok"]:
            raise ValueError(f"合成树校验失败: {res['errors']}")
        warnings.extend(res["warnings"])

        anchors = self.plan(tree, grid)
        new_tree = copy.deepcopy(tree)

        # 合并 beat_events：模板事件 + 锚点事件（去重、时间钳制）
        events: list[dict[str, Any]] = list(new_tree.beat_events)
        dropped = 0
        for a in anchors:
            if any(abs(float(e.get("time", -1)) - a.time) <= _MERGE_TOLERANCE
                   and e.get("beat_type") == a.beat_type for e in events):
                continue
            if not (0.0 <= a.time <= new_tree.duration + 1e-6):
                dropped += 1
                continue
            events.append({"time": round(a.time, 4), "beat_type": a.beat_type,
                           "layer_id": a.layer_id, "action": a.action})
        events.sort(key=lambda e: float(e.get("time", 0)))
        new_tree.beat_events = events

        for a in anchors:
            if a.beat_type == "hard_stop":
                warnings.append(
                    f"hard_stop@{a.time:.2f}s：timeRemap 定格(freeze) 待 M1c 后接入，"
                    f"当前降级为 {a.action}")

        result = BeatLockResult(tree=new_tree, anchors=anchors, warnings=warnings,
                                dropped=dropped)
        result.jsx_fragment = self.emit_jsx(result)
        return result

    # ── JSX 片段生成 ────────────────────────────────────────────
    def emit_jsx(self, result: BeatLockResult) -> str:
        """锚点 → JSX 关键帧片段（引用 comp.layer(i)，可在 JsxProjectBuilder
        生成的函数作用域内直接执行）"""
        tree = result.tree
        lines: list[str] = ["    // ── BeatLock 节拍锚定关键帧（M3）──"]
        for a in result.anchors:
            lines.append(f"    // beat {a.beat_type}@{a.time:.3f}s "
                         f"→ {a.layer_id}(layer{a.layer_index}) {a.action}")
            lines.extend(self._anchor_jsx(a, tree))
        return "\n".join(lines)

    def _anchor_jsx(self, a: BeatAnchor, tree: CompositionTree | None) -> list[str]:
        li = a.layer_index
        scale_prop = (f'comp.layer({li}).property("ADBE Transform Group")'
                      f'.property("ADBE Scale")')
        op_prop = (f'comp.layer({li}).property("ADBE Transform Group")'
                   f'.property("ADBE Opacity")')
        pos_prop = (f'comp.layer({li}).property("ADBE Transform Group")'
                    f'.property("ADBE Position")')
        t = a.time
        out: list[str] = []
        if a.action == "punch":
            amp = float(a.params.get("amp", 1.12)) * 100.0
            dur = float(a.params.get("dur_ms", 160)) / 1000.0
            out.append(f'    {scale_prop}.setValueAtTime({t:.4f}, [100,100]);')
            out.append(f'    {scale_prop}.setValueAtTime({t + dur * 0.3:.4f}, [{amp:.1f},{amp:.1f}]);')
            out.append(f'    {scale_prop}.setValueAtTime({t + dur:.4f}, [100,100]);')
        elif a.action == "pulse":
            amp = float(a.params.get("amp", 1.05)) * 100.0
            dur = float(a.params.get("dur_ms", 120)) / 1000.0
            out.append(f'    {scale_prop}.setValueAtTime({t:.4f}, [100,100]);')
            out.append(f'    {scale_prop}.setValueAtTime({t + dur * 0.5:.4f}, [{amp:.1f},{amp:.1f}]);')
            out.append(f'    {scale_prop}.setValueAtTime({t + dur:.4f}, [100,100]);')
        elif a.action == "flash":
            low = float(a.params.get("opacity_low", 45))
            dur = float(a.params.get("dur_ms", 140)) / 1000.0
            out.append(f'    {op_prop}.setValueAtTime({t:.4f}, 100);')
            out.append(f'    {op_prop}.setValueAtTime({t + dur * 0.3:.4f}, {low:.0f});')
            out.append(f'    {op_prop}.setValueAtTime({t + dur:.4f}, 100);')
        elif a.action == "shake":
            amp = float(a.params.get("amp_px", 8.0))
            step = float(a.params.get("step_ms", 40)) / 1000.0
            dur = float(a.params.get("dur_ms", 400)) / 1000.0
            cx, cy = (tree.width / 2.0 if tree else 960.0), \
                     (tree.height / 2.0 if tree else 540.0)
            i = 0
            tt = t
            while tt <= t + dur + 1e-6:
                sx = amp if i % 2 == 0 else -amp
                sy = -amp if i % 2 == 0 else amp
                out.append(f'    {pos_prop}.setValueAtTime({tt:.4f}, [{cx + sx:.1f},{cy + sy:.1f}]);')
                tt += step
                i += 1
            out.append(f'    {pos_prop}.setValueAtTime({t + dur + step:.4f}, [{cx:.1f},{cy:.1f}]);')
        elif a.action == "freeze":
            out.append(f"    // freeze@t={t:.3f}s: timeRemap 占位（M1c 后接入）")
        return out

    # ── 契约注入 ───────────────────────────────────────────────
    @staticmethod
    def merge_jsx(base_jsx: str, fragment: str) -> str:
        """把 BeatLock 片段注入 JsxProjectBuilder 产出的工程脚本。

        契约注入点：`_result = {status:"success"` 赋值行之前（该行是
        JsxProjectBuilder.build() 的固定结尾，M1b 已提交，两边约定不动）。
        """
        pattern = re.compile(r'(?m)^(\s*)_result = \{status:"success"')
        m = pattern.search(base_jsx)
        if not m:
            raise ValueError(
                "未找到 JsxProjectBuilder 契约注入点 `_result = {status:\"success\"`；"
                "base_jsx 必须由 core.synthesis_orchestrator.JsxProjectBuilder.build() 生成")
        indent = m.group(1)
        indented = "\n".join((indent + ln if ln.strip() else ln)
                             for ln in fragment.splitlines())
        return base_jsx[:m.start()] + indented + "\n" + base_jsx[m.start():]


def compose(tree: CompositionTree, grid: BeatGrid, fps: int = 30,
            intensity: float = 1.0) -> tuple:
    """便捷入口：锚定 + 生成 + 与 JsxProjectBuilder 合并。

    Returns:
        (merged_jsx, BeatLockResult) — merged_jsx 可直接交给
        SynthesisOrchestrator 的 Bridge 客户端执行（M1c 链路）。
    """
    from core.synthesis_orchestrator import JsxProjectBuilder  # 惰性导入（只读复用）

    lock = BeatLock(fps=fps, intensity=intensity)
    result = lock.apply(tree, grid)
    base = JsxProjectBuilder().build(result.tree)
    merged = BeatLock.merge_jsx(base, result.jsx_fragment)
    return merged, result


__all__ = [
    "BeatGrid", "BeatAnchor", "BeatLockResult", "BeatLock", "compose",
    "BEAT_TYPES", "ACTION_TYPES",
]

# -*- coding: utf-8 -*-
"""文字打击感调用入口（P4-B 实测验证版）。

对应 JSX: ae_additive_scripts/textImpactMaster.jsx（2026-08 真机验证 PASS）。
大白话：把"高燃砸字、卡点脉冲、故障字"三种打击感封装成一行函数调用。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "ae_additive_scripts"))

import run_additive_jsx  # noqa: E402
from core.fx.particle_presets import _send_raw  # noqa: E402

# 调用历史持久化目录（仅供记录/审计，不参与 AE 执行）
TEXT_IMPACT_HISTORY_DIR = os.path.join(PROJECT_ROOT, "data", "fx", "text_impact")

IMPACT_CAPABILITIES = {
    "impact": {"desc": "打击感入场（缩放砸入+抖动表达式+白闪）", "key_params": ["time", "startScale", "flash"]},
    "beat_sync": {"desc": "beat 卡点缩放脉冲", "key_params": ["beats", "peakScale", "decay"]},
    "rgb_glitch": {"desc": "RGB 故障字（错位+跳切+辉光）", "key_params": ["startTime", "endTime", "glitchKeys"]},
}


def _build_jsx(action: str, **params) -> str:
    args = {"action": action}
    args.update(params)
    content, _ = run_additive_jsx.build_script_content("textImpactMaster", args)
    return (
        "(function(){try{" + content
        + ";return String($.global.__aeAdditiveResult||'null');"
        + "}catch(e){return JSON.stringify({status:'error',message:e.toString()});}})();"
    )


class TextImpactClient:
    """文字打击感客户端：语义化调用 → AE 真实执行。

    每次调用会写入 data/fx/text_impact/history.jsonl 供审计/评测。
    """

    def __init__(self, history_dir: str = TEXT_IMPACT_HISTORY_DIR):
        self._history_dir = Path(history_dir)
        self._history_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 调用历史持久化 ----------
    def record_call(self, action: str, params: Dict[str, Any],
                    result: Dict[str, Any]) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "action": action,
            "params": params,
            "status": result.get("status") if isinstance(result, dict) else "unknown",
        }
        try:
            with open(self._history_dir / "history.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        path = self._history_dir / "history.jsonl"
        if not path.is_file():
            return []
        lines: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(json.loads(line))
                except ValueError:
                    continue
        return lines[-limit:]

    def clear_history(self) -> None:
        path = self._history_dir / "history.jsonl"
        if path.is_file():
            path.unlink()

    # ---------- 真机执行 ----------
    def impact(self, comp_name: str, layer_name: str, time: float = 0.0,
               start_scale: float = 160.0, flash: bool = True,
               timeout: float = 40.0) -> Dict[str, Any]:
        result = _send_raw(_build_jsx(
            "impact", compName=comp_name, layerName=layer_name,
            time=time, startScale=start_scale, flash=flash), timeout)
        self.record_call("impact", {"compName": comp_name, "layerName": layer_name,
                                    "time": time, "startScale": start_scale,
                                    "flash": flash}, result)
        return result

    def beat_sync(self, comp_name: str, layer_name: str, beats: List[float],
                  peak_scale: float = 118.0, decay: float = 0.15,
                  timeout: float = 40.0) -> Dict[str, Any]:
        if not beats:
            result = {"status": "error", "message": "beats 不能为空"}
        else:
            result = _send_raw(_build_jsx(
                "beat_sync", compName=comp_name, layerName=layer_name,
                beats=beats, peakScale=peak_scale, decay=decay), timeout)
        self.record_call("beat_sync", {"compName": comp_name, "layerName": layer_name,
                                       "beats": beats, "peakScale": peak_scale,
                                       "decay": decay}, result)
        return result

    def rgb_glitch(self, comp_name: str, layer_name: str,
                   start_time: Optional[float] = None, end_time: Optional[float] = None,
                   glitch_keys: int = 10, offset_max: float = 12.0,
                   timeout: float = 40.0) -> Dict[str, Any]:
        params = {"compName": comp_name, "layerName": layer_name,
                  "glitchKeys": glitch_keys, "offsetMax": offset_max}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        result = _send_raw(_build_jsx("rgb_glitch", **params), timeout)
        self.record_call("rgb_glitch", params, result)
        return result


# ============================================================
# 全局单例
# ============================================================

_text_impact_client: Optional[TextImpactClient] = None


def get_text_impact_client() -> TextImpactClient:
    """获取全局文字打击感客户端单例。"""
    global _text_impact_client
    if _text_impact_client is None:
        _text_impact_client = TextImpactClient()
    return _text_impact_client

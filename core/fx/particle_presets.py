# -*- coding: utf-8 -*-
"""粒子特效参数库与调用入口（P4-A 实测验证版）。

对应 JSX: ae_additive_scripts/particleFXMaster.jsx（全部 matchName 已实测）。
本模块提供：
- PARTICLE_TYPES / LAYERED_PRESETS / ATMOSPHERE_MOODS 元数据（供 planner/评测引用）
- MATCHNAMES 已验证 matchName 表（中文 AE 实测，2026-08）
- build_particle_jsx() 组装附加式 scriptContent（经 run_additive_jsx 内联 _lib）
- ParticleFXClient 走 .ae-mcp-bridge 文件轮询协议真实下发命令

大白话：JSX 是"军火"，这个模块是"发射器"——把粒子需求变成 AE 能执行的命令。
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

BRIDGE_DIR = os.path.join(PROJECT_ROOT, ".ae-mcp-bridge")
CMD_PATH = os.path.join(BRIDGE_DIR, "ae_command.json")
RES_PATH = os.path.join(BRIDGE_DIR, "ae_result.json")

# 调用历史持久化目录（仅供记录/审计，不参与 AE 执行）
PARTICLE_HISTORY_DIR = os.path.join(PROJECT_ROOT, "data", "fx", "particle_presets")

# ============================================================
# 已验证 matchName 表（2026-08 中文 AE 实测，详见 docs/ae_bridge_lessons.md）
# ============================================================
MATCHNAMES = {
    # 效果本体（addProperty 用）
    "cc_particle_world": "CC Particle World",
    "cc_particle_systems_2": "CC Particle Systems II",
    "cc_rainfall": "CSRainfall",        # 注意：真实 matchName ≠ 显示名！
    "cc_snowfall": "CSSnowfall",        # 同上
    "fractal_noise": "ADBE Fractal Noise",
    "glow": "ADBE Glo2",
    "tint": "ADBE Tint",
    # CC Particle World 关键参数（扁平排列 -00xx）
    "pw_birth_rate": "CC Particle World-0004",
    "pw_longevity": "CC Particle World-0005",
    "pw_pos_x": "CC Particle World-0007",
    "pw_pos_y": "CC Particle World-0008",
    "pw_velocity": "CC Particle World-0016",
    "pw_gravity": "CC Particle World-0018",
    "pw_particle_type": "CC Particle World-0023",
    "pw_birth_size": "CC Particle World-0024",
    "pw_death_size": "CC Particle World-0025",
    "pw_size_var": "CC Particle World-0026",      # 单位 0-100（百分数）
    "pw_max_opacity": "CC Particle World-0027",   # 单位 0-100
    "pw_birth_color": "CC Particle World-0029",
    "pw_death_color": "CC Particle World-0030",
    "pw_transfer_mode": "CC Particle World-0039",
    "pw_random_seed": "CC Particle World-0104",
    # CC Particle Systems II 关键参数
    "ps2_birth_rate": "CC Particle Systems II-0001",
    "ps2_longevity": "CC Particle Systems II-0002",
    "ps2_position": "CC Particle Systems II-0004",
    "ps2_radius_x": "CC Particle Systems II-0005",
    "ps2_radius_y": "CC Particle Systems II-0006",
    "ps2_velocity": "CC Particle Systems II-0010",
    "ps2_gravity": "CC Particle Systems II-0012",
    "ps2_particle_type": "CC Particle Systems II-0018",
    "ps2_size_var": "CC Particle Systems II-0021",   # 单位 0-1（小数！与 PW 不同）
    "ps2_max_opacity": "CC Particle Systems II-0023",
    "ps2_birth_color": "CC Particle Systems II-0025",
    "ps2_death_color": "CC Particle Systems II-0026",
    "ps2_random_seed": "CC Particle Systems II-0030",
    # 图层
    "effect_parade": "ADBE Effect Parade",
}

# ============================================================
# 粒子类型元数据（供 planner / benchmark / 评测引用）
# ============================================================
PARTICLE_TYPES = {
    "spark":    {"desc": "火花喷射（爆炸式，黄→红）", "engine": "cc_particle_world", "blend": "add",
                 "use_case": ["高燃", "打击感", "beat爆发"]},
    "dust":     {"desc": "漂浮微尘（全屏弱光）", "engine": "cc_particle_systems_2", "blend": "screen",
                 "use_case": ["电影感", "氛围", "背景层"]},
    "energy":   {"desc": "能量流光（粘性汇聚，青→品）", "engine": "cc_particle_world", "blend": "add",
                 "use_case": ["赛博朋克", "霓虹", "科技感"]},
    "embers":   {"desc": "上升火星（橙红渐暗）", "engine": "cc_particle_systems_2", "blend": "add",
                 "use_case": ["高燃", "战争", "火焰氛围"]},
    "dissolve": {"desc": "粒子消散（中心爆裂四散）", "engine": "cc_particle_systems_2", "blend": "screen",
                 "use_case": ["粒子转场", "文字消散"]},
    "rain":     {"desc": "雨（CC Rainfall）", "engine": "cc_rainfall", "blend": "normal",
                 "use_case": ["赛博朋克", "忧郁", "夜景"]},
    "snow":     {"desc": "雪（CC Snowfall）", "engine": "cc_snowfall", "blend": "normal",
                 "use_case": ["唯美", "冬日", "静谧"]},
}

LAYERED_PRESETS = {
    "amv_highenergy": ["dust(screen)", "embers(add)", "spark(add+beat)"],
    "cinematic": ["dust(screen)", "dust(screen)", "snow(normal)"],
    "cyberpunk": ["dust(screen)", "energy(add)", "rain(normal)"],
}

ATMOSPHERE_MOODS = {
    "smoke":   {"desc": "烟雾（灰蓝，慢演化）", "blend": "screen"},
    "ink":     {"desc": "水墨（深墨色，大尺度扰动）", "blend": "normal"},
    "neonfog": {"desc": "霓虹雾（青色，加色）", "blend": "add"},
}


# ============================================================
# 命令组装与下发
# ============================================================

_last_cmd_mtime = 0.0


def build_particle_jsx(action: str, **params) -> str:
    """组装 particleFXMaster 附加式 scriptContent（已内联 _lib）。"""
    args = {"action": action}
    args.update(params)
    content, _ = run_additive_jsx.build_script_content("particleFXMaster", args)
    return (
        "(function(){try{" + content
        + ";return String($.global.__aeAdditiveResult||'null');"
        + "}catch(e){return JSON.stringify({status:'error',message:e.toString()});}})();"
    )


def _send_raw(jsx_body: str, timeout: float = 60.0) -> dict[str, Any]:
    """走 .ae-mcp-bridge 文件轮询协议发送 executeAtomScript（对齐 execution.py 防竞态实现）。"""
    global _last_cmd_mtime
    # 竞态防护：结果文件基准 mtime 必须在写命令之前取，否则快速响应会被误判为旧结果
    try:
        prev_mtime = os.path.getmtime(RES_PATH) if os.path.isfile(RES_PATH) else -1.0
    except OSError:
        prev_mtime = -1.0
    ts = time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
    cmd = {
        "command": "executeAtomScript",
        "args": {"script": "return " + jsx_body},
        "timestamp": ts,
        "processed": False,
    }
    with open(CMD_PATH, "w", encoding="utf-8") as f:
        json.dump(cmd, f, ensure_ascii=False)
    _last_cmd_mtime = max(time.time(), _last_cmd_mtime + 1.0)
    os.utime(CMD_PATH, (_last_cmd_mtime, _last_cmd_mtime))

    deadline = time.time() + timeout
    retried = False
    while True:
        while time.time() < deadline:
            time.sleep(0.3)
            try:
                with open(CMD_PATH, "r", encoding="utf-8") as f:
                    cur = json.load(f)
                if not cur.get("processed"):
                    continue
                if not os.path.isfile(RES_PATH) or os.path.getmtime(RES_PATH) <= prev_mtime:
                    continue
                with open(RES_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") != "success":
                    return {"status": "error", "message": str(data)}
                payload = data.get("result", {})
                if isinstance(payload, dict) and "result" in payload:
                    payload = payload["result"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (ValueError, TypeError):
                        payload = {"raw": payload}
                return payload if isinstance(payload, dict) else {"raw": payload}
            except (OSError, ValueError):
                continue
        # 超时后防丢单：若 listener 从未拣到命令（processed 仍 false），
        # 重顶 mtime 再等一轮（不重写内容，无重复执行风险）
        if retried:
            break
        try:
            with open(CMD_PATH, "r", encoding="utf-8") as f:
                cur = json.load(f)
            if cur.get("processed"):
                break  # 已执行但结果未更新，重试无意义
        except (OSError, ValueError):
            break
        retried = True
        _last_cmd_mtime = max(time.time(), _last_cmd_mtime + 1.0)
        os.utime(CMD_PATH, (_last_cmd_mtime, _last_cmd_mtime))
        deadline = time.time() + max(30.0, timeout / 2)
    return {"status": "error", "message": f"bridge timeout {timeout}s"}


class ParticleFXClient:
    """粒子特效客户端：把语义化调用转成 AE 真实执行。

    注意：渲染到已存在文件会弹模态覆盖框阻塞 listener，
    输出文件名必须唯一（带时间戳）或渲染前删除旧文件。

    每次调用会写入 data/fx/particle_presets/history.jsonl 供审计/评测。
    """

    def __init__(self, history_dir: str = PARTICLE_HISTORY_DIR):
        self._history_dir = Path(history_dir)
        self._history_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 调用历史持久化 ----------
    def record_call(self, action: str, params: dict[str, Any],
                    result: dict[str, Any]) -> None:
        """把一次语义化调用追加写盘（JSON Lines）。"""
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

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """读取最近 limit 条调用历史（最新在后）。"""
        path = self._history_dir / "history.jsonl"
        if not path.is_file():
            return []
        lines: list[dict[str, Any]] = []
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
        """清空调用历史。"""
        path = self._history_dir / "history.jsonl"
        if path.is_file():
            path.unlink()

    # ---------- 真机执行 ----------
    def generate(self, comp_name: str, particle_type: str,
                 options: dict[str, Any] | None = None, timeout: float = 60.0) -> dict[str, Any]:
        if particle_type not in PARTICLE_TYPES:
            result = {"status": "error", "message": f"unknown particle type: {particle_type}"}
        else:
            result = _send_raw(build_particle_jsx(
                "generate", compName=comp_name, type=particle_type, options=options or {}), timeout)
        self.record_call("generate", {"compName": comp_name, "type": particle_type,
                                      "options": options or {}}, result)
        return result

    def layered(self, comp_name: str, preset: str = "amv_highenergy",
                timeout: float = 90.0) -> dict[str, Any]:
        result = _send_raw(build_particle_jsx(
            "layered", compName=comp_name, preset=preset), timeout)
        self.record_call("layered", {"compName": comp_name, "preset": preset}, result)
        return result

    def beat_burst(self, comp_name: str, layer_name: str, beats: list[float],
                   base_rate: float = 3.0, peak_rate: float = 20.0,
                   decay: float = 0.12, timeout: float = 60.0) -> dict[str, Any]:
        result = _send_raw(build_particle_jsx(
            "beat_burst", compName=comp_name, layerName=layer_name, beats=beats,
            baseRate=base_rate, peakRate=peak_rate, decay=decay), timeout)
        self.record_call("beat_burst", {"compName": comp_name, "layerName": layer_name,
                                        "beats": beats, "baseRate": base_rate,
                                        "peakRate": peak_rate, "decay": decay}, result)
        return result

    def atmosphere(self, comp_name: str, mood: str = "smoke",
                   timeout: float = 60.0) -> dict[str, Any]:
        result = _send_raw(build_particle_jsx(
            "atmosphere", compName=comp_name, mood=mood), timeout)
        self.record_call("atmosphere", {"compName": comp_name, "mood": mood}, result)
        return result


# ============================================================
# 全局单例
# ============================================================

_particle_fx_client: ParticleFXClient | None = None


def get_particle_fx_client() -> ParticleFXClient:
    """获取全局粒子特效客户端单例。"""
    global _particle_fx_client
    if _particle_fx_client is None:
        _particle_fx_client = ParticleFXClient()
    return _particle_fx_client

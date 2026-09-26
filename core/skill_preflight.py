# -*- coding: utf-8 -*-
"""skill_preflight.py — 主管线的技能注册表预检（P2 真融入，2026-09-25）。

回答"卡片库是否真的进了编排"：不是摆设——主管线（unified_edit 等）每次运行
开工前自动执行本预检：
  1. 管线声明依赖的 skill_id 清单 -> registry 查卡（卡不存在=警告，脱节暴露）
  2. stage 闸门：非 active 卡进入生产管线 -> 警告（治理闸门在运行时的另一半）
  3. 宿主就绪探测：requires_host 逐个探测可用性（exe 存在/listener 在线）
     -> 输出"需要先启动什么"清单，requires_running_host 不再是隐性前提
  4. 成本预算：sum(typical_duration_sec) + gpu_local/api_paid 计数 -> 排期与预算前置

用法:
  from core.skill_preflight import preflight_for_pipeline
  report = preflight_for_pipeline("unified_edit")   # 返回 dict，不抛异常
"""
from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "schemas" / "skill_cards" / "registry.json"

# 各主管线声明依赖的技能（融入点：管线改依赖必须同步改这里，预检会暴露脱节）
PIPELINE_SKILLS: dict[str, list[str]] = {
    "unified_edit": [
        "vrs_beat_analysis",        # stage1 节拍
        "beat_sync_edit",           # stage3 编排渲染
        "ext_ffmpeg_skill_pack",    # 媒体处理兜底工具面
        # 字体走 schemas/font_registry.json 数据文件，不经 resource_find_font 网关工具
        #（预检首跑即暴露该过度声明，2026-09-25 删除——融入生效的实证）
        "cdl_grade_lua_bridge",     # 可选调色下游
    ],
    "word_cut": [
        "word_rough_cut",
        "otio_convert",
    ],
}

# 宿主可用性探测（轻量、离线、毫秒级）
def _host_available(app: str) -> tuple[bool, str]:
    try:
        if app == "ffmpeg":
            return (shutil.which("ffmpeg") is not None, "which ffmpeg")
        if app == "blender":
            for p in (r"D:\Blender", "blender"):
                if p == "blender" and shutil.which("blender"):
                    return (True, "which blender")
                bp = Path(p)
                if bp.exists() and any(bp.rglob("blender.exe")):
                    return (True, str(next(bp.rglob("blender.exe"))))
            return (False, "blender.exe 未找到")
        if app == "resolve":
            rp = Path(r"D:\app\Resolve.exe")
            if rp.exists():
                return (True, str(rp))
            return (False, "Resolve.exe 未找到（RESOLVE_INSTALL_DIR?）")
        if app == "ae":
            rp = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")
            return (rp.exists(), str(rp))
        if app in ("local_python", "any"):
            return (True, "n/a")
        if app == "comfyui":
            return (_tcp_open("127.0.0.1", 8188), "127.0.0.1:8188")
        # 其余宿主（topaz/media_encoder/silhouette/cinema4d/photoshop/premiere/audition）：
        # 只登记不探测（v0.1 边界，探测清单见 requires_host 原文）
        return (True, f"未探测 {app}（视为登记）")
    except OSError:
        return (False, "探测异常")


def _tcp_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ae_listener_online() -> bool:
    """AE 桥就绪 = listener 在轮询（结果文件 60s 内有写动作为准过于间接，
    v0.1 用 Startup 日志新鲜度做轻量信号）。"""
    log = ROOT / ".ae-mcp-bridge" / "startup.log"
    if not log.exists():
        return False
    import time
    return (time.time() - log.stat().st_mtime) < 7 * 86400  # 7 天内启动过


def preflight(pipeline: str, skill_ids: list[str] | None = None) -> dict:
    reg_path = REGISTRY_PATH
    out: dict = {"pipeline": pipeline, "ready": True, "warnings": [],
                 "hosts_to_start": [], "budget": {}}
    if not reg_path.exists():
        out["ready"] = False
        out["warnings"].append("registry.json 不存在——先跑 scripts/skill_cli.py build-registry")
        return out
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    skills = reg.get("skills", {})
    ids = skill_ids or PIPELINE_SKILLS.get(pipeline, [])
    if not ids:
        out["warnings"].append(f"管线 {pipeline} 未声明技能依赖（PIPELINE_SKILLS）")
    total_sec = 0.0
    gpu = paid = 0
    for sid in ids:
        e = skills.get(sid)
        if not e:
            out["ready"] = False
            out["warnings"].append(f"[{sid}] 不在卡片库——管线依赖与注册表脱节")
            continue
        if e["stage"] != "active":
            out["warnings"].append(f"[{sid}] stage={e['stage']} 非 active——投产需先补实测证据")
        total_sec += float(e.get("cost_sec", 0))
        if e["cost_class"] == "gpu_local":
            gpu += 1
        elif e["cost_class"] == "api_paid":
            paid += 1
        for h in e.get("hosts", []):
            ok, why = _host_available(h)
            if not ok and e["headless"] != "headless":
                msg = f"[{sid}] 宿主 {h} 不可用（{why}），该卡 headless={e['headless']}"
                if msg not in out["hosts_to_start"]:
                    out["hosts_to_start"].append(msg)
    out["budget"] = {"total_typical_sec": round(total_sec, 1),
                     "gpu_local_skills": gpu, "api_paid_skills": paid}
    # headless 分布（编排决策依据：需要预启动宿主的任务数）
    hd = {}
    for sid in ids:
        e = skills.get(sid)
        if e:
            hd[e["headless"]] = hd.get(e["headless"], 0) + 1
    out["headless_matrix"] = hd
    if out["warnings"]:
        out["ready"] = False
    return out


def preflight_for_pipeline(pipeline: str) -> dict:
    """主管线入口用的安全封装：永不抛异常（预检失败不阻断出片，只报告）。"""
    try:
        return preflight(pipeline)
    except Exception as e:  # noqa: BLE001
        return {"pipeline": pipeline, "ready": True, "warnings": [f"预检自身异常（不阻断）: {e}"],
                "hosts_to_start": [], "budget": {}}


def format_report(r: dict) -> str:
    lines = [f"  技能预检[{r['pipeline']}]: "
             + ("READY" if r["ready"] else "NEEDS-ATTENTION"),
             f"  预算: {r['budget'].get('total_typical_sec', 0)}s 典型耗时, "
             f"GPU {r['budget'].get('gpu_local_skills', 0)} 项, API计费 {r['budget'].get('api_paid_skills', 0)} 项, "
             f"矩阵 {r.get('headless_matrix', {})}"]
    for w in r["warnings"]:
        lines.append(f"  ⚠ {w}")
    for h in r["hosts_to_start"]:
        lines.append(f"  ◇ {h}")
    return "\n".join(lines)

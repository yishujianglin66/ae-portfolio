# -*- coding: utf-8 -*-
"""skill_cli.py — Skill 卡片体系 CLI（P1: Skill schema v0.1）

用法:
  python scripts/skill_cli.py validate            # 校验全部卡片 against schema
  python scripts/skill_cli.py gen-tool-cards      # 从 gateway.py 自动生成 tool_wrapper 卡片
  python scripts/skill_cli.py build-registry      # 扫描卡片 -> schemas/skill_cards/registry.json
  python scripts/skill_cli.py list [--domain X] [--stage X] [--headless X]
  python scripts/skill_cli.py show <skill_id>

设计源: 09-计划文件/2026-09-11_管线集成与Skill封装落地方案.md §二/§三
       03-阶段报告/CutLedger调研对标评测与集成计划修订-20260924.md P1（headless 矩阵+成本计量并入）
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import date
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "skill_card_schema_v0.1.json"
CARDS_DIR = ROOT / "schemas" / "skill_cards"
GATEWAY_PY = ROOT / "puppet-automation" / "src" / "mcp_gateway" / "gateway.py"
REGISTRY_PATH = CARDS_DIR / "registry.json"

# ---------------------------------------------------------------- tool 元数据
# 工具名 -> (domain, headless, cost_class, typical_duration_sec, 宿主app, 版本)
# headless 取值依据 2026-09-24 实测（全系统实战跑通记录）:
#   headless                = 无界面可全自动（ffmpeg/blender -b/AME CLI）
#   requires_running_host   = 宿主进程须在（AE listener / ResolveMCP+Resolve / ComfyUI /AME 队列）
TODAY = "2026-09-25"
TOOL_META: dict[str, tuple] = {
    # ---- ffmpeg / media: 纯无头
    "ffmpeg_concat_videos":   ("media", "headless", "free_local", 15, "ffmpeg", "*"),
    "ffmpeg_convert_video":   ("media", "headless", "free_local", 20, "ffmpeg", "*"),
    "ffmpeg_extract_audio":   ("media", "headless", "free_local", 5, "ffmpeg", "*"),
    "ffmpeg_extract_frames":  ("media", "headless", "free_local", 8, "ffmpeg", "*"),
    "media_encoder_encode":   ("render", "headless", "free_local", 60, "media_encoder", "*"),
    "media_encoder_batch_encode": ("render", "headless", "free_local", 180, "media_encoder", "*"),
    "media_encoder_list_presets": ("render", "headless", "free_local", 1, "media_encoder", "*"),
    # ---- AE: listener 在运行的 AE 进程内轮询（09-24 自动拉起已闭环）
    "ae_run_script":          ("render", "requires_running_host", "free_local", 10, "ae", ">=25.0"),
    "ae_render_composition":  ("render", "requires_running_host", "free_local", 60, "ae", ">=25.0"),
    # ---- Resolve: 官方 MCP 可 launch_resolve 拉起，脚本在应用内执行
    "davinci_run_script":     ("edit", "requires_running_host", "free_local", 15, "resolve", ">=19.0"),
    "davinci_mcp_status":     ("edit", "headless", "free_local", 3, "resolve", ">=19.0"),
    "davinci_mcp_call":       ("edit", "requires_running_host", "free_local", 15, "resolve", ">=19.0"),
    "davinci_apply_grade":    ("color", "requires_running_host", "free_local", 20, "resolve", ">=19.0"),
    "davinci_export_lut":     ("color", "requires_running_host", "free_local", 10, "resolve", ">=19.0"),
    # ---- Blender: headless bpy 5.1.0 实证 (-b -P)
    "blender_run_script":     ("render", "headless", "free_local", 30, "blender", ">=4.0"),
    "blender_create_stage":   ("render", "headless", "free_local", 10, "blender", ">=4.0"),
    "blender_render_animation": ("render", "headless", "gpu_local", 300, "blender", ">=4.0"),
    # ---- ComfyUI: 本地服务 + GPU
    "comfyui_run_workflow":   ("render", "requires_running_host", "gpu_local", 120, "comfyui", "*"),
    "comfyui_upload_image":   ("media", "requires_running_host", "free_local", 3, "comfyui", "*"),
    "comfyui_get_status":     ("media", "headless", "free_local", 2, "comfyui", "*"),
    # ---- Topaz: GPU 增强
    "topaz_enhance_video":    ("render", "requires_running_host", "gpu_local", 240, "topaz", "*"),
    # ---- 宿主插件: 都在运行中的 AE 内生效
    "plugin_apply_saber":     ("plugin", "requires_running_host", "free_local", 15, "ae", ">=25.0"),
    "plugin_apply_particular": ("plugin", "requires_running_host", "free_local", 20, "ae", ">=25.0"),
    "plugin_apply_optical_flares": ("plugin", "requires_running_host", "free_local", 15, "ae", ">=25.0"),
    "plugin_apply_twitch":    ("plugin", "requires_running_host", "free_local", 10, "ae", ">=25.0"),
    # ---- Silhouette roto
    "silhouette_roto_video":  ("roto", "requires_running_host", "gpu_local", 180, "silhouette", "*"),
    "silhouette_track_points": ("roto", "requires_running_host", "free_local", 30, "silhouette", "*"),
    # ---- 资源检索/配置: 纯本地
    "resource_find_audio":    ("resource", "headless", "free_local", 1, "local_python", "*"),
    "resource_find_effect_image": ("resource", "headless", "free_local", 1, "local_python", "*"),
    "resource_find_font":     ("resource", "headless", "free_local", 1, "local_python", "*"),
    "resource_find_lut":      ("resource", "headless", "free_local", 1, "local_python", "*"),
    "resource_find_script":   ("resource", "headless", "free_local", 1, "local_python", "*"),
    "resource_find_template": ("resource", "headless", "free_local", 1, "local_python", "*"),
    "resource_get_stats":     ("resource", "headless", "free_local", 1, "local_python", "*"),
    "resource_list_by_type":  ("resource", "headless", "free_local", 1, "local_python", "*"),
    "config_get_paths":       ("resource", "headless", "free_local", 1, "local_python", "*"),
    "config_get_settings":    ("resource", "headless", "free_local", 1, "local_python", "*"),
}


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _iter_cards():
    return sorted(CARDS_DIR.rglob("*.yaml"))


# ---------------------------------------------------------------- gateway 解析
def _extract_gateway_tools() -> list[dict]:
    """AST 定位 gateway.py 中工具定义 dict 列表（不 import，避免依赖链）。"""
    src = GATEWAY_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    found: list[dict] = []

    class Visitor(ast.NodeVisitor):
        def visit_Dict(self, node: ast.Dict):  # noqa: N802
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            if {"name", "input_schema"} <= keys or {"name", "description", "inputSchema"} <= keys:
                try:
                    val = ast.literal_eval(node)
                    if isinstance(val, dict) and "name" in val:
                        found.append(val)
                except (ValueError, SyntaxError):
                    pass
            self.generic_visit(node)

    Visitor().visit(tree)
    # 去重（同名取首个）并剔除占位（tool_name 是 MCP schema 示例占位，非真实能力）
    seen, out = set(), []
    for t in found:
        n = t.get("name", "")
        if n and n != "tool_name" and n not in seen:
            seen.add(n)
            out.append(t)
    return out


# ---------------------------------------------------------------- commands
def cmd_gen_tool_cards(force: bool) -> int:
    tools = _extract_gateway_tools()
    made, skipped = [], []
    for t in tools:
        name = t["name"]
        domain, headless, cost_class, dur, app, ver = TOOL_META.get(
            name, ("pipeline", "headless", "free_local", 10, "local_python", "*"))
        if domain == "pipeline" and name not in TOOL_META:
            print(f"  [兜底默认] {name} 未在 TOOL_META 登记，用保守默认值（请人工复核）")
        out = CARDS_DIR / domain / f"{name}.yaml"
        if out.exists() and not force:
            skipped.append(name)
            continue
        card = {
            "skill_id": name,
            "domain": domain,
            "skill_type": "tool_wrapper",
            "version": "1.0.0",
            "stage": "validated" if headless == "headless" else "experimental",
            "requires_host": [{"app": app, "version": ver}],
            "headless": headless,
            "cost": {"class": cost_class, "typical_duration_sec": dur},
            "contract": {
                "inputs": t.get("input_schema") or t.get("inputSchema") or {"type": "object"},
                "outputs": {"type": "object", "description": "网关统一响应 {status, result|message}"},
            },
            "tool_ref": {"gateway_tool": name, "action": t.get("action", "")},
            "intended_use": t.get("description", name),
            "out_of_scope": "（auto-generated，待补）",
            "evidence_chain": {
                "validated_at": TODAY,
                "status": "auto_generated",
                "was_generated_by": {"tool": "skill_cli gen-tool-cards", "source": "gateway.py AST"},
            },
            "version_history": [{"version": "1.0.0", "date": TODAY, "note": "自网关工具定义自动生成"}],
            "tags": ["auto-generated", "mcp-gateway"],
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            yaml.safe_dump(card, allow_unicode=True, sort_keys=False, width=110),
            encoding="utf-8")
        made.append(name)
    print(f"生成 {len(made)} 张 tool_wrapper 卡片，跳过已存在 {len(skipped)} 张")
    unknown = [t["name"] for t in tools if t["name"] not in TOOL_META]
    if unknown:
        print(f"未登记 TOOL_META 的工具（需人工补矩阵）: {unknown}")
    return 0


def cmd_validate() -> int:
    schema = _load_schema()
    validator_cls = jsonschema.Draft7Validator
    v = validator_cls(schema)
    files = _iter_cards()
    if not files:
        print("无卡片可校验"); return 1
    bad = 0
    ids: dict[str, Path] = {}
    for f in files:
        try:
            card = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            print(f"YAML 解析失败 {f.name}: {e}"); bad += 1; continue
        errs = sorted(v.iter_errors(card), key=lambda e: e.path)
        sid = str(card.get("skill_id", ""))
        if sid in ids:
            print(f"skill_id 重复: {sid} ({ids[sid].name} vs {f.name})"); bad += 1
        else:
            ids[sid] = f
        if sid and f.stem != sid:
            print(f"文件名与 skill_id 不一致: {f.name} != {sid}"); bad += 1
        for e in errs:
            path = "/".join(str(p) for p in e.path) or "<root>"
            print(f"校验失败 {f.name} [{path}]: {e.message[:160]}")
            bad += 1
    print(f"共 {len(files)} 张卡片，问题 {bad} 项")
    return 1 if bad else 0


def cmd_build_registry() -> int:
    entries = {}
    for f in _iter_cards():
        card = yaml.safe_load(f.read_text(encoding="utf-8"))
        sid = card["skill_id"]
        entries[sid] = {
            "domain": card["domain"],
            "skill_type": card["skill_type"],
            "version": card["version"],
            "stage": card["stage"],
            "headless": card["headless"],
            "cost_class": card["cost"]["class"],
            "cost_sec": card["cost"]["typical_duration_sec"],
            "hosts": [h["app"] for h in card["requires_host"]],
            "path": str(f.relative_to(ROOT)).replace("\\", "/"),
        }
    reg = {
        "registry": "skill_cards",
        "schema_version": "0.1",
        "built_at": TODAY,
        "count": len(entries),
        "summary": {
            "by_stage": _count(entries, "stage"),
            "by_headless": _count(entries, "headless"),
            "by_cost": _count(entries, "cost_class"),
            "by_domain": _count(entries, "domain"),
        },
        "skills": entries,
    }
    REGISTRY_PATH.write_text(
        json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"registry.json 已生成：{len(entries)} 项")
    for k, v in reg["summary"].items():
        print(f"  {k}: {v}")
    return 0


def _count(entries, field):
    out: dict[str, int] = {}
    for e in entries.values():
        key = e[field] if not isinstance(e[field], list) else None
        if key is None:
            for h in e[field]:
                out[h] = out.get(h, 0) + 1
        else:
            out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda x: -x[1]))


def cmd_list(domain=None, stage=None, headless=None) -> int:
    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    rows = [(sid, e) for sid, e in reg["skills"].items()
            if (not domain or e["domain"] == domain)
            and (not stage or e["stage"] == stage)
            and (not headless or e["headless"] == headless)]
    for sid, e in sorted(rows, key=lambda r: (r[1]["domain"], r[0])):
        print(f"  {e['domain']:<10} {sid:<32} {e['skill_type']:<14} {e['stage']:<12} "
              f"{e['headless']:<22} {e['cost_class']:<11} {e['cost_sec']}s")
    print(f"共 {len(rows)} 项")
    return 0


def cmd_show(skill_id: str) -> int:
    hits = list(CARDS_DIR.rglob(f"{skill_id}.yaml"))
    if not hits:
        print(f"未找到 {skill_id}"); return 1
    print(hits[0].read_text(encoding="utf-8"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    g = sub.add_parser("gen-tool-cards")
    g.add_argument("--force", action="store_true")
    sub.add_parser("build-registry")
    l = sub.add_parser("list")
    l.add_argument("--domain"); l.add_argument("--stage"); l.add_argument("--headless")
    s = sub.add_parser("show")
    s.add_argument("skill_id")
    a = ap.parse_args()
    if a.cmd == "validate":
        return cmd_validate()
    if a.cmd == "gen-tool-cards":
        return cmd_gen_tool_cards(a.force)
    if a.cmd == "build-registry":
        return cmd_build_registry()
    if a.cmd == "list":
        return cmd_list(a.domain, a.stage, a.headless)
    if a.cmd == "show":
        return cmd_show(a.skill_id)
    return 2


if __name__ == "__main__":
    sys.exit(main())

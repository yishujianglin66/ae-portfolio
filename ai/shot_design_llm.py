# -*- coding: utf-8 -*-
"""LLM 镜头设计助手 — 用 API 模型编排"镜头剧本" (2026-08-15).

背景: 用户三次反馈"每个镜头都是晃动、推拉、闪回, 根本没有编排好镜头剧本"。
规则引擎只能给出均匀的稀疏化 (T4.5/T4.6), 而真正的剧本编排需要判断:
哪些弧段该静、哪些该动、撞击/闪回该落在哪几个强拍上。

本模块让 DeepSeek V4 (原生 api.deepseek.com, 经 ai.ai_agent.V4Agent) 以
剪辑导演身份, 基于音乐弧段表输出结构化镜头设计:
  - 每个弧段的运动预算 motion_per_10 (每10镜最多几镜运动, 0-3);
  - 每个弧段的运镜词表 cameras;
  - 全片撞击(拉进-闪回)点 punch_points: 只允许落在爆发段强拍, ≤6次,
    间隔 ≥20s;
  - 每个弧段一句镜头思路 notes (供人工审查).

结果缓存于 cache_dir (按弧段签名+模型名), 保证重复渲染确定性。
任何失败都返回 None → production_director 规则兜底, 不中断渲染。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_ALLOWED_CAMERAS = ["static", "pan_left", "pan_right", "diag_pan",
                    "zoom_back", "orbit", "push", "zoom_in"]

_PROMPT_TEMPLATE = """你是资深AMV/燃向混剪剪辑导演, 精通镜头语言与音乐情绪编排。

用户(甲方)三次反馈同一问题, 必须严格遵守其铁律:
1. "每个镜头都是晃动、推拉、闪回, 看起来特别别扭, 很晃眼睛" — 静态持机
   是默认, 推拉/摇移/撞击闪回是稀缺强调手段, 只属于爆发段强拍;
2. "那只是那一个段落适合这个效果, 为什么要应用到每一个镜头" — 效果必须
   由剧本决定, 落在具体弧段的具体强拍上, 绝不均匀铺开;
3. 专业AMV: 大部分镜头固定硬切, 动势来自剪辑节奏而非镜头自身乱动。

音乐弧段表 (start/end 秒, mood 段落情绪, level 能量级, n_cuts 段内切点数):
{arcs_json}

运动预算参考基线 (没有明确理由不要上调):
- intro/outro/break: motion_per_10 = 0 (纯静态, 固定机位硬切);
- build: motion_per_10 = 1 (偶发缓摇建立空间感);
- drop: motion_per_10 = 2 (爆发段适度强调);
- 全片运动镜头占比应控制在 10% 左右 (加权 motion_per_10 ≈ 1)。

请输出严格 JSON (不要 markdown 代码围栏, 不要注释):
{{
  "global": {{
    "punch_budget": <全片撞击总数, 4-6>,
    "punch_spacing_sec": 20
  }},
  "arcs": [
    {{
      "start": <与输入一致, 数字>,
      "end": <与输入一致, 数字>,
      "mood": "<与输入一致>",
      "motion_per_10": <0-3 整数: intro/outro/break<=1, build<=2,
                         drop/climax<=3; 全片整体应<=2>,
      "cameras": ["static", "<该段允许的运镜, 从词表选, static 必须排第一>"],
      "punch_points": [<撞击秒数, 只允许落在本段内且 mood 为 drop/climax,
                        每点必须是强拍附近, 整表合计<=6, 相邻>=20s>],
      "notes": "<一句镜头思路, 15字内>"
    }}
  ]
}}

运镜词表: {cameras}

硬性约束 (违反即返工):
- punch_points 合计不得超过 global.punch_budget;
- 同一弧段内 punch_points 至多 1 个;
- punch_points 相邻两点间隔 >= 20 秒 (跨弧段同样适用, 两个爆发段
  之间的间隔也要 >=20s);
- punch_points 只能落在 mood 为 drop 或 climax 的弧段;
- intro/outro/break 弧段的 punch_points 必须为空数组;
- 全片 motion_per_10 的加权平均 <= 2 (即运动镜头全片占比 <=20%);
- static 在 cameras 中必须出现且排第一。
"""


def _clean_json(text: str) -> dict[str, Any] | None:
    """剥离围栏/注释后解析 JSON, 失败返回 None"""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    # 去掉可能的行内注释 (// 之后)
    t = re.sub(r"//[^\n]*", "", t)
    try:
        return json.loads(t)
    except Exception:
        # 截取第一个 { 到最后一个 }
        s, e = t.find("{"), t.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(t[s:e + 1])
            except Exception:
                return None
        return None


def _validate_plan(plan: dict[str, Any], arcs: list[dict[str, Any]]) -> str | None:
    """校验 LLM 输出, 返回错误描述 (None=通过)"""
    if not isinstance(plan, dict) or "arcs" not in plan:
        return "缺少 arcs 字段"
    if not isinstance(plan["arcs"], list) or len(plan["arcs"]) != len(arcs):
        return f"arcs 数量 {len(plan.get('arcs', []))} != 输入 {len(arcs)}"
    punches: list[float] = []
    for a in plan["arcs"]:
        if a.get("start") is None or a.get("end") is None:
            return "弧段缺 start/end"
        mp10 = a.get("motion_per_10")
        if not isinstance(mp10, int) or not 0 <= mp10 <= 3:
            return f"motion_per_10 非法: {mp10}"
        cams = a.get("cameras") or []
        if not cams or cams[0] != "static":
            return "cameras 缺失或 static 未排第一"
        bad = [c for c in cams if c not in _ALLOWED_CAMERAS]
        if bad:
            return f"非法运镜: {bad}"
        if a.get("mood") in ("intro", "outro", "break") and a.get("punch_points"):
            return f"{a.get('mood')} 弧段不允许 punch_points"
        _arc_punches = a.get("punch_points") or []
        if len(_arc_punches) > 1:
            return f"弧段[{a['start']},{a['end']}] 撞击点>1"
        for p in _arc_punches:
            if not isinstance(p, (int, float)):
                return f"punch 非法值 {p}"
            if not (a["start"] - 0.01 <= p <= a["end"] + 0.01):
                return f"punch {p} 超出弧段 [{a['start']},{a['end']}]"
            if a.get("mood") not in ("drop", "climax"):
                return f"punch {p} 不在爆发段"
            punches.append(float(p))
    g = plan.get("global", {}) or {}
    budget = g.get("punch_budget", 6)
    if len(punches) > budget:
        return f"punch 数 {len(punches)} > budget {budget}"
    sp = sorted(punches)
    for i in range(1, len(sp)):
        if sp[i] - sp[i - 1] < 20.0:
            return f"punch 间隔不足20s: {sp[i-1]:.1f} / {sp[i]:.1f}"
    w = sum(a["end"] - a["start"] for a in plan["arcs"]) or 1.0
    wm = sum((a.get("motion_per_10", 0) * (a["end"] - a["start"])) for a in plan["arcs"]) / w
    if wm > 2.0:
        return f"全片加权 motion_per_10={wm:.2f} > 2"
    return None


def design_shot_plan(
    arcs: list[dict[str, Any]],
    cache_dir: Path | None = None,
    bgm_stem: str = "bgm",
    model: str = "pro",
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    """调用 API 模型生成镜头设计计划; 失败返回 None (规则兜底)。

    Args:
        arcs: [{start, end, type, level, n_cuts}] 音乐弧段表
        cache_dir: 计划缓存目录 (None → 项目 data/shot_design)
        bgm_stem: BGM 文件名主干 (缓存键)
        model: "pro" | "flash" — 首选模型 (pro 判断更克制), 失败自动换档
        force_refresh: True 跳过缓存重新生成
    """
    if not arcs:
        return None
    cache_dir = Path(cache_dir) if cache_dir else (
        Path(__file__).resolve().parent.parent / "data" / "shot_design")
    cache_dir.mkdir(parents=True, exist_ok=True)

    arcs_json = json.dumps(
        [{"start": round(a["start"], 3), "end": round(a["end"], 3),
          "mood": a.get("type", "build"), "level": a.get("level", "mid"),
          "n_cuts": int(a.get("n_cuts", 0))}
         for a in arcs],
        ensure_ascii=False)
    sig = hashlib.md5((arcs_json + model).encode("utf-8")).hexdigest()[:12]
    cache_file = cache_dir / f"shot_plan_{bgm_stem}_{sig}.json"
    if cache_file.exists() and not force_refresh:
        try:
            plan = json.loads(cache_file.read_text(encoding="utf-8"))
            if _validate_plan(plan, arcs) is None:
                print(f"  [LLM镜头设计] 命中缓存 {cache_file.name}")
                return plan
        except Exception:
            pass

    try:
        from ai.ai_agent import V4Agent
        agent = V4Agent()
    except Exception as e:  # noqa: BLE001
        print(f"  [LLM镜头设计] V4Agent 不可用({e}) → 规则兜底")
        return None

    prompt = _PROMPT_TEMPLATE.format(
        arcs_json=arcs_json, cameras=", ".join(_ALLOWED_CAMERAS))
    # 推理模型(reasoning)会先烧 token 链再输出 content: 实测 pro 推理链
    # 吃掉 8192+ token 后 content 为空。2026-08-15 起强制
    # reasoning_effort="none" (原生端点支持, reasoning_tokens=0, content
    # 直接输出), 彻底规避"JSON 解析失败"。
    attempts = [(model, 4096)]
    if model != "flash":
        attempts.append(("flash", 4096))
    attempts.append(("pro", 8192))
    attempts = attempts[:3]
    seen = set()
    _feedback = ""
    for _mdl, _mtok in attempts:
        if (_mdl, _mtok) in seen:
            continue
        seen.add((_mdl, _mtok))
        try:
            _prompt = prompt
            if _feedback:
                _prompt += (f"\n\n注意: 你上一次的输出被程序校验拒绝, 原因: {_feedback}"
                            "\n请修正问题后重新输出完整 JSON (同样不要围栏)。")
            raw = agent.ask(_prompt, model=_mdl, max_tokens=_mtok,
                            reasoning_effort="none")
            plan = _clean_json(raw or "")
            err = _validate_plan(plan, arcs) if plan else "JSON 解析失败"
            if plan and err is None:
                cache_file.write_text(
                    json.dumps(plan, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                n_p = sum(len(a.get("punch_points") or []) for a in plan["arcs"])
                print(f"  [LLM镜头设计] 生成成功({_mdl}): {len(plan['arcs'])}弧段, "
                      f"撞击点{n_p}个 → {cache_file.name}")
                return plan
            _feedback = err or "JSON 解析失败"
            print(f"  [LLM镜头设计] {_mdl} 校验失败: {_feedback}, 带反馈重试...")
        except Exception as e:  # noqa: BLE001
            print(f"  [LLM镜头设计] {_mdl} 调用异常: {e}")
            _feedback = f"调用异常 {type(e).__name__}"
    return None

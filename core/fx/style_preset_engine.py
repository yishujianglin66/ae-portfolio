# -*- coding: utf-8 -*-
"""风格预设引擎（P4-C）：把风格模板变成可执行的 AE 生产步骤。

数据源: data/style_templates/templates.json（全部 matchName 已实测）。
执行器:
- color_grade → 调整图层 + Lumetri/Glo2 参数（matchName 直写）
- particles   → particleFXMaster（core.fx.particle_presets）
- text_fx     → textFXMaster / textImpactMaster

大白话：模板是"菜谱"，这个引擎是"厨师"——按菜谱一步步在 AE 里真实做菜。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from core.fx.particle_presets import ParticleFXClient, _send_raw  # noqa: E402
from core.fx.text_impact import TextImpactClient  # noqa: E402
from core.fx.text_impact import _build_jsx as _build_impact_jsx

TEMPLATES_PATH = os.path.join(PROJECT_ROOT, "data", "style_templates", "templates.json")
EXECUTION_LOG_PATH = os.path.join(PROJECT_ROOT, "data", "fx", "style_preset_engine", "executions.jsonl")

_VALID_PARTICLE_ACTIONS = {"generate", "layered", "beat_burst", "atmosphere"}
_VALID_TEXT_ENGINES = {"textFXMaster", "textImpactMaster"}


class StylePresetEngine:
    """风格模板加载/校验/执行。

    每次 execute() 会把执行结果追加写入 data/fx/style_preset_engine/executions.jsonl。
    """

    def __init__(self, templates_path: str = TEMPLATES_PATH,
                 execution_log_path: str = EXECUTION_LOG_PATH):
        with open(templates_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.templates: dict[str, dict[str, Any]] = raw.get("templates", {})
        self.meta = raw.get("_meta", {})
        self._execution_log_path = Path(execution_log_path)
        self._execution_log_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------- 执行记录持久化 ----------
    def record_execution(self, style_id: str, comp_name: str,
                         result: dict[str, Any]) -> None:
        """把一次 execute() 结果追加写盘（JSON Lines）。"""
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "style": style_id,
            "comp": comp_name,
            "summary": result.get("summary", {}) if isinstance(result, dict) else {},
        }
        try:
            with open(self._execution_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def get_executions(self, limit: int = 100) -> list[dict[str, Any]]:
        path = self._execution_log_path
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

    def clear_executions(self) -> None:
        path = self._execution_log_path
        if path.is_file():
            path.unlink()

    # ---------- 查询 ----------
    def list_styles(self) -> list[dict[str, Any]]:
        return [
            {"id": sid, "name": t.get("name"), "desc": t.get("desc"),
             "mood": t.get("mood", [])}
            for sid, t in self.templates.items()
        ]

    def get(self, style_id: str) -> dict[str, Any]:
        if style_id not in self.templates:
            raise KeyError(f"未知风格模板: {style_id}，可选: {list(self.templates)}")
        return self.templates[style_id]

    # ---------- 校验 ----------
    def validate(self, style_id: str) -> list[str]:
        """返回问题列表，空列表 = 模板合法。"""
        problems: list[str] = []
        try:
            t = self.get(style_id)
        except KeyError as e:
            return [str(e)]
        for i, g in enumerate(t.get("color_grade", [])):
            if not g.get("effect"):
                problems.append(f"color_grade[{i}] 缺 effect")
            if not isinstance(g.get("params", {}), dict):
                problems.append(f"color_grade[{i}].params 必须是 dict")
        for i, p in enumerate(t.get("particles", [])):
            if p.get("action") not in _VALID_PARTICLE_ACTIONS:
                problems.append(f"particles[{i}] 未知 action: {p.get('action')}")
        for i, x in enumerate(t.get("text_fx", [])):
            if x.get("engine") not in _VALID_TEXT_ENGINES:
                problems.append(f"text_fx[{i}] 未知 engine: {x.get('engine')}")
            if not x.get("action"):
                problems.append(f"text_fx[{i}] 缺 action")
        return problems

    # ---------- 执行计划 ----------
    def build_plan(self, style_id: str, comp_name: str,
                   beats: list[float] | None = None) -> list[dict[str, Any]]:
        """把模板展开成有序步骤列表（不执行，供审查/测试）。"""
        t = self.get(style_id)
        plan: list[dict[str, Any]] = []
        for g in t.get("color_grade", []):
            plan.append({"step": "color_grade", "effect": g["effect"],
                         "params": g.get("params", {}), "comp": comp_name})
        pfx = ParticleFXClient()
        for p in t.get("particles", []):
            act = p.get("action")
            if act == "beat_burst" and not p.get("on_beats") and not beats:
                continue  # 无 beat 信息时跳过 beat 爆发
            plan.append({"step": "particles", "action": act, "raw": p, "comp": comp_name})
        for x in t.get("text_fx", []):
            plan.append({"step": "text_fx", "engine": x.get("engine"),
                         "action": x.get("action"), "raw": x, "comp": comp_name})
        return plan

    # ---------- 真机执行 ----------
    @staticmethod
    def warmup_effects(timeout: float = 400.0) -> dict[str, Any]:
        """预热重效果引擎：AE 首次 addProperty Lumetri/Glo2 会同步初始化效果引擎，
        实测可达 120s+，会打穿任何客户端超时。必须在正式作业前预热一次。
        """
        jsx = (
            "(function(){try{var c=app.project.items.addComp('__fx_warmup__',64,64,1,1,30);"
            "var s=c.layers.addSolid([0.5,0.5,0.5],'w',64,64,1);"
            "var warmed=[];var names=['ADBE Lumetri','ADBE Glo2'];"
            "for(var i=0;i<names.length;i++){"
            "try{s.property('ADBE Effect Parade').addProperty(names[i]);warmed.push(names[i]);}"
            "catch(e){warmed.push(names[i]+':ERR');}}"
            "c.remove();return JSON.stringify({status:'success',warmed:warmed});"
            "}catch(e){return JSON.stringify({status:'error',message:e.toString()});}})();"
        )
        return _send_raw(jsx, timeout=timeout)

    def resolve_layer_index(self, comp_name: str, layer_name: str) -> int:
        """按名解析图层索引（textFXMaster 只认 layerIndex，不认 layerName）。找不到返回 1。"""
        jsx = (
            "(function(){try{var c=null;"
            "for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);"
            "if(it instanceof CompItem&&it.name==='" + comp_name + "'){c=it;break;}}"
            "if(!c)return JSON.stringify({status:'error',message:'comp_not_found'});"
            "for(var j=1;j<=c.numLayers;j++){if(c.layer(j).name==='" + layer_name + "')"
            "return JSON.stringify({status:'success',index:j});}"
            "return JSON.stringify({status:'success',index:1});"
            "}catch(e){return JSON.stringify({status:'error',message:e.toString()});}})();"
        )
        r = _send_raw(jsx, timeout=30)
        return int(r.get("index", 1)) if isinstance(r, dict) else 1

    def apply_color_grade(self, comp_name: str, grade: dict[str, Any]) -> dict[str, Any]:
        """新建调整图层并按 matchName 直写效果参数。"""
        params_js = "".join(
            f"try{{ef.property('{k}').setValue({json.dumps(v)});}}catch(ep){{bad.push('{k}:'+ep.toString());}}"
            for k, v in grade.get("params", {}).items()
        )
        jsx = (
            "(function(){try{"
            "var c=null;for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);"
            "if(it instanceof CompItem&&it.name==='" + comp_name + "'){c=it;break;}}"
            "if(!c)return JSON.stringify({status:'error',message:'comp_not_found'});"
            "var adj=null;for(var j=1;j<=c.numLayers;j++){var l=c.layer(j);"
            "if(l.adjustmentLayer&&l.name.indexOf('Grade_')===0){adj=l;break;}}"
            "if(!adj){adj=c.layers.addSolid([0.5,0.5,0.5],'Grade_" + comp_name + "',c.width,c.height,1);"
            "adj.adjustmentLayer=true;}"
            "var bad=[];var ef;"
            "try{ef=adj.property('ADBE Effect Parade').addProperty('" + grade["effect"] + "');}"
            "catch(ea){return JSON.stringify({status:'error',message:'effect_add_fail:'+ea.toString()});}"
            + params_js +
            "return JSON.stringify({status:'success',effect:'" + grade["effect"] + "',"
            "layer:adj.name,failed:bad});"
            "}catch(e){return JSON.stringify({status:'error',message:e.toString()});}})();"
        )
        # Lumetri addProperty 首次加载可达 60s+（AE 初始化效果引擎），超时必须给足
        return _send_raw(jsx, timeout=150)

    def execute(self, style_id: str, comp_name: str,
                text_layer: str | None = None, particle_layer: str | None = None,
                beats: list[float] | None = None,
                skip: list[str] | None = None) -> dict[str, Any]:
        """按模板顺序真机执行。skip 可跳过 ['color_grade'|'particles'|'text_fx']。"""
        skip = set(skip or [])
        t = self.get(style_id)
        results: dict[str, Any] = {"style": style_id, "comp": comp_name, "steps": []}
        pfx = ParticleFXClient()
        tfx = TextImpactClient()

        if "color_grade" not in skip:
            for g in t.get("color_grade", []):
                results["steps"].append({"kind": "color_grade",
                                         "result": self.apply_color_grade(comp_name, g)})

        if "particles" not in skip:
            for p in t.get("particles", []):
                act = p.get("action")
                if act == "layered":
                    r = pfx.layered(comp_name, preset=p.get("preset", "amv_highenergy"))
                elif act == "generate":
                    r = pfx.generate(comp_name, p.get("type", "dust"))
                elif act == "atmosphere":
                    r = pfx.atmosphere(comp_name, mood=p.get("mood", "smoke"))
                elif act == "beat_burst":
                    if not beats:
                        r = {"status": "skipped", "message": "无 beat 信息"}
                    else:
                        r = pfx.beat_burst(comp_name, particle_layer or "", beats,
                                           base_rate=p.get("baseRate", 3),
                                           peak_rate=p.get("peakRate", 20),
                                           decay=p.get("decay", 0.12))
                else:
                    r = {"status": "error", "message": f"未知粒子 action: {act}"}
                results["steps"].append({"kind": "particles", "action": act, "result": r})

        if "text_fx" not in skip and text_layer:
            layer_index = self.resolve_layer_index(comp_name, text_layer)
            for x in t.get("text_fx", []):
                engine = x.get("engine")
                act = x.get("action")
                if engine == "textImpactMaster":
                    if act == "impact":
                        r = tfx.impact(comp_name, text_layer, time=x.get("time", 0.5),
                                       start_scale=x.get("startScale", 160),
                                       flash=x.get("flash", True))
                    elif act == "beat_sync":
                        r = tfx.beat_sync(comp_name, text_layer, beats or [0.5, 1.0, 1.5],
                                          peak_scale=x.get("peakScale", 118))
                    elif act == "rgb_glitch":
                        r = tfx.rgb_glitch(comp_name, text_layer,
                                           glitch_keys=x.get("glitchKeys", 10),
                                           offset_max=x.get("offsetMax", 12))
                    else:
                        r = {"status": "error", "message": f"未知打击感 action: {act}"}
                else:  # textFXMaster：通用附加式调用（只认 layerIndex）
                    params = {k: v for k, v in x.items() if k not in ("engine",)}
                    params["compName"] = comp_name
                    params["layerIndex"] = layer_index
                    import run_additive_jsx as _raj
                    content, _ = _raj.build_script_content("textFXMaster", params)
                    jsx = ("(function(){try{" + content
                           + ";return String($.global.__aeAdditiveResult||'null');"
                           + "}catch(e){return JSON.stringify({status:'error',message:e.toString()});}})();")
                    r = _send_raw(jsx, timeout=60)
                results["steps"].append({"kind": "text_fx", "engine": engine,
                                         "action": act, "result": r})

        ok = sum(1 for s in results["steps"]
                 if isinstance(s.get("result"), dict)
                 and (s["result"].get("status") in ("success", "skipped")
                      or s["result"].get("success")))
        results["summary"] = {"total": len(results["steps"]), "ok": ok}
        self.record_execution(style_id, comp_name, results)
        return results


# ============================================================
# 全局单例
# ============================================================

_style_preset_engine: StylePresetEngine | None = None


def get_style_preset_engine() -> StylePresetEngine:
    """获取全局风格预设引擎单例。"""
    global _style_preset_engine
    if _style_preset_engine is None:
        _style_preset_engine = StylePresetEngine()
    return _style_preset_engine

# -*- coding: utf-8 -*-
"""表达式生成 + 预检闸门（P5）：正式下发前先预检，失败即阻断。

流程（对齐用户需求）：
1. generate_expression(kind, **opts) 生成目标表达式（内置已实测模板，也可传原始字符串）
2. preflight_expression() 通过 Bridge 下发带异常捕获的 JSX 预检脚本：
   - 按 comp / layer / property path 定位目标属性
   - 备份原表达式 → 试设新表达式 → 强制求值（p.value + p.expressionError）
   - 捕获：合成/图层/属性不存在、属性不可设表达式、赋值失败、语法/运行时错误
   - 无论成败一律恢复原表达式（不产生脏状态）
3. apply_expression() = 预检通过才正式写入，并读回表达式核验

大白话：表达式是"新代码"，这个模块是"安检门"——先在 AE 里试跑一遍，
没问题才放行；试跑留下的痕迹当场擦干净。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.fx.particle_presets import _send_raw  # noqa: E402

# 表达式预检/写入日志持久化目录
EXPRESSION_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "fx", "expression_preflight")

# ============================================================
# 一、表达式生成（已实测模板，参考 textFXMaster expressionAnimLib）
# ============================================================
EXPRESSION_KINDS = ["shake", "pulse", "flicker", "wiggle", "spin"]


def generate_expression(kind: str, **opts: Any) -> str:
    """按类型生成表达式字符串。未知类型抛 KeyError。"""
    if kind == "shake":
        # 位置衰减抖动（急停冲击感）
        t0 = float(opts.get("start", 0.0))
        amp = float(opts.get("amp", 30.0))
        freq = float(opts.get("freq", 8.0))
        decay = float(opts.get("decay", 3.0))
        return (
            "t0=%g;amp=%g;\n"
            "if(time>t0){var tt=time-t0;var n=amp*Math.sin(tt*%g*6.2832)/Math.exp(tt*%g);"
            "[value[0]+n,value[1]+n*0.6];}else{value;}" % (t0, amp, freq, decay)
        )
    if kind == "pulse":
        # 缩放周期脉冲（卡点用）
        base = float(opts.get("base", 100.0))
        amp = float(opts.get("amp", 12.0))
        freq = float(opts.get("freq", 2.0))
        return (
            "var s=%g+%g*Math.abs(Math.sin(time*%g*3.1416));[s,s];" % (base, amp, freq)
        )
    if kind == "flicker":
        # 透明度闪烁（霓虹/故障感）
        lo = float(opts.get("lo", 30.0))
        hi = float(opts.get("hi", 100.0))
        fps = float(opts.get("fps", 12.0))
        return (
            "seedRandom(Math.floor(time*%g),true);random(%g,%g);" % (fps, lo, hi)
        )
    if kind == "wiggle":
        amp = float(opts.get("amp", 20.0))
        freq = float(opts.get("freq", 2.0))
        return "wiggle(%g,%g);" % (amp, freq)
    if kind == "spin":
        speed = float(opts.get("speed", 90.0))
        return "time*%g;" % speed
    raise KeyError(f"未知表达式类型: {kind}，可选: {EXPRESSION_KINDS}")


# ============================================================
# 二、JSX 组装（预检 / 正式写入共用定位逻辑）
# ============================================================

def _normalize_path(property_path: Union[str, list[str]]) -> list[str]:
    if isinstance(property_path, str):
        segs = [s for s in property_path.replace("\\", "/").split("/") if s]
    else:
        segs = [str(s) for s in property_path]
    if not segs:
        raise ValueError("属性路径不能为空")
    return segs


_LOCATE_JS = """var compName=%COMP%;var layerSpec=%LAYER%;var segs=%SEGS%;
var c=null;
for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);
if(it instanceof CompItem&&it.name===compName){c=it;break;}}
if(!c){return JSON.stringify({ok:false,error_type:"comp_not_found",comp:compName,layer:"",property:"",message:"合成未找到: "+compName});}
var l=null;
if(typeof layerSpec==="number"){try{l=c.layer(layerSpec);}catch(eL){l=null;}}
else{for(var j=1;j<=c.numLayers;j++){if(c.layer(j).name===layerSpec){l=c.layer(j);break;}}}
if(!l){return JSON.stringify({ok:false,error_type:"layer_not_found",comp:compName,layer:String(layerSpec),property:"",message:"图层未找到: "+layerSpec});}
var p=l;var trail="";
for(var k=0;k<segs.length;k++){var s=segs[k];var nx=null;
try{nx=p.property(s);}catch(eP){nx=null;}
if(!nx){return JSON.stringify({ok:false,error_type:"property_not_found",comp:compName,layer:l.name,property:trail+"/"+s,message:"属性路径未找到: "+s});}
p=nx;trail=trail+"/"+s;}"""


def _locate_js(comp_name: str, layer: Union[str, int], property_path: Union[str, list[str]]) -> str:
    js = _LOCATE_JS
    js = js.replace("%COMP%", json.dumps(comp_name))
    js = js.replace("%LAYER%", json.dumps(layer))
    js = js.replace("%SEGS%", json.dumps(_normalize_path(property_path)))
    return js


def _build_preflight_jsx(comp_name: str, layer: Union[str, int],
                         property_path: Union[str, list[str]], expression: str) -> str:
    return (
        "(function(){try{"
        + _locate_js(comp_name, layer, property_path)
        + """
if(p.propertyType!==PropertyType.PROPERTY){return JSON.stringify({ok:false,error_type:"cannot_set_expression",comp:compName,layer:l.name,property:trail,message:"目标不是可设表达式的属性(propertyType="+p.propertyType+")"});}
if(p.canSetExpression===false){return JSON.stringify({ok:false,error_type:"cannot_set_expression",comp:compName,layer:l.name,property:trail,message:"属性 canSetExpression=false"});}
var orig="";try{orig=p.expression||"";}catch(eO){orig="";}
var setErr=null;try{p.expression=%EXPR%;}catch(eS){setErr=eS.toString();}
if(setErr){try{p.expression=orig;}catch(eR){}
return JSON.stringify({ok:false,error_type:"set_failed",comp:compName,layer:l.name,property:trail,message:setErr});}
var evalErr="";
try{var _v=p.value;}catch(eV){evalErr=eV.toString();}
try{if(!evalErr&&p.expressionError){evalErr=String(p.expressionError);}}catch(eE){}
try{p.expression=orig;}catch(eR2){return JSON.stringify({ok:false,error_type:"restore_failed",comp:compName,layer:l.name,property:trail,message:"恢复原表达式失败: "+eR2.toString()});}
if(evalErr){return JSON.stringify({ok:false,error_type:"expression_error",comp:compName,layer:l.name,property:trail,message:evalErr});}
return JSON.stringify({ok:true,comp:compName,layer:l.name,property:trail,message:"预检通过",restored:true});
}catch(e){return JSON.stringify({ok:false,error_type:"unexpected",comp:"",layer:"",property:"",message:e.toString()});}})();"""
    ).replace("%EXPR%", json.dumps(expression))


def _build_write_jsx(comp_name: str, layer: Union[str, int],
                     property_path: Union[str, list[str]], expression: str) -> str:
    return (
        "(function(){try{"
        + _locate_js(comp_name, layer, property_path)
        + """
if(p.propertyType!==PropertyType.PROPERTY){return JSON.stringify({ok:false,error_type:"cannot_set_expression",comp:compName,layer:l.name,property:trail,message:"目标不是可设表达式的属性"});}
try{p.expression=%EXPR%;}catch(eS){return JSON.stringify({ok:false,error_type:"set_failed",comp:compName,layer:l.name,property:trail,message:eS.toString()});}
var rb="";try{rb=p.expression||"";}catch(eB){}
return JSON.stringify({ok:true,comp:compName,layer:l.name,property:trail,message:"写入成功",expression_readback:rb});
}catch(e){return JSON.stringify({ok:false,error_type:"unexpected",comp:"",layer:"",property:"",message:e.toString()});}})();"""
    ).replace("%EXPR%", json.dumps(expression))


# ============================================================
# 三、对外 API
# ============================================================

def _interpret(res: dict[str, Any], comp_name: str, layer: Union[str, int],
               property_path: Union[str, list[str]]) -> dict[str, Any]:
    """_send_raw 直接返回解包后的 dict：含 error_type 即预检结果；status=error 即传输失败。"""
    if isinstance(res, dict) and "error_type" in res:
        return res
    if isinstance(res, dict) and res.get("ok"):
        return res
    return {"ok": False, "error_type": "transport_error", "comp": comp_name,
            "layer": str(layer), "property": str(property_path),
            "message": f"Bridge 返回无法解析或传输失败: {res!r}", "raw": res}


def preflight_expression(comp_name: str, layer: Union[str, int],
                         property_path: Union[str, list[str]], expression: str,
                         timeout: float = 60.0) -> dict[str, Any]:
    """预检：试设表达式并立即恢复原值。

    返回 dict：
    - ok: bool
    - error_type: comp_not_found / layer_not_found / property_not_found /
                  cannot_set_expression / set_failed / expression_error /
                  restore_failed / unexpected / transport_error
    - comp / layer / property / message：结构化定位与错误信息
    """
    if not isinstance(expression, str) or not expression.strip():
        return {"ok": False, "error_type": "invalid_expression", "comp": comp_name,
                "layer": str(layer), "property": str(property_path),
                "message": "表达式为空或非字符串"}
    jsx = _build_preflight_jsx(comp_name, layer, property_path, expression)
    return _interpret(_send_raw(jsx, timeout=timeout), comp_name, layer, property_path)


def apply_expression(comp_name: str, layer: Union[str, int],
                     property_path: Union[str, list[str]], expression: str,
                     timeout: float = 60.0) -> dict[str, Any]:
    """预检 → 通过后正式写入 → 读回核验。预检失败直接阻断（blocked=True）。"""
    pf = preflight_expression(comp_name, layer, property_path, expression, timeout)
    if not pf.get("ok"):
        pf.update({"blocked": True, "written": False})
        return pf
    jsx = _build_write_jsx(comp_name, layer, property_path, expression)
    out = _interpret(_send_raw(jsx, timeout=timeout), comp_name, layer, property_path)
    if not out.get("ok"):
        out.update({"blocked": False, "written": False, "comp": comp_name,
                    "layer": str(layer), "property": str(property_path)})
        out.setdefault("error_type", "write_failed")
        return out
    rb = (out.get("expression_readback") or "").strip()
    verified = rb == expression.strip()
    out.update({"blocked": False, "written": True, "readback_verified": verified})
    if not verified:
        out["ok"] = False
        out["error_type"] = "readback_mismatch"
        out["message"] = "写入后读回内容与目标表达式不一致"
    return out


class ExpressionGate:
    """表达式预检闸门（面向管线的对象封装）。

    每次 preflight/apply 结果会追加写入 data/fx/expression_preflight/gate_log.jsonl。
    """

    def __init__(self, log_dir: str = EXPRESSION_LOG_DIR):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 日志持久化 ----------
    def record(self, kind: str, comp_name: str, layer: Union[str, int],
               property_path: Union[str, list[str]], result: dict[str, Any],
               expression: str | None = None) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "kind": kind,
            "comp": comp_name,
            "layer": str(layer),
            "property": str(property_path),
            "expression": expression,
            "ok": bool(result.get("ok")),
            "error_type": result.get("error_type"),
        }
        try:
            with open(self._log_dir / "gate_log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def get_log(self, limit: int = 100) -> list[dict[str, Any]]:
        path = self._log_dir / "gate_log.jsonl"
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

    def clear_log(self) -> None:
        path = self._log_dir / "gate_log.jsonl"
        if path.is_file():
            path.unlink()

    # ---------- 生成 / 预检 / 写入 ----------
    def generate(self, kind: str, **opts: Any) -> str:
        return generate_expression(kind, **opts)

    def preflight(self, comp_name: str, layer: Union[str, int],
                  property_path: Union[str, list[str]], expression: str,
                  timeout: float = 60.0) -> dict[str, Any]:
        result = preflight_expression(comp_name, layer, property_path, expression, timeout)
        self.record("preflight", comp_name, layer, property_path, result, expression)
        return result

    def apply(self, comp_name: str, layer: Union[str, int],
              property_path: Union[str, list[str]],
              expression: str | None = None, kind: str | None = None,
              opts: dict[str, Any] | None = None,
              timeout: float = 60.0) -> dict[str, Any]:
        """expression 与 kind 二选一；kind 时自动生成。"""
        expr = expression if expression is not None else generate_expression(kind, **(opts or {}))
        result = apply_expression(comp_name, layer, property_path, expr, timeout)
        self.record("apply", comp_name, layer, property_path, result, expr)
        return result


# ============================================================
# 全局单例
# ============================================================

_expression_gate: ExpressionGate | None = None


def get_expression_gate() -> ExpressionGate:
    """获取全局表达式预检闸门单例。"""
    global _expression_gate
    if _expression_gate is None:
        _expression_gate = ExpressionGate()
    return _expression_gate

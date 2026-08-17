"""probe_fx_registry — AE 效果注册表真机探针（P1）

分批枚举 app.effects 全表（上次一次性遍历卡死 AE 线程, 改为 200/批 + 落盘续跑）。
产出: fx_registry.json — 关键插件的效果清单(matchName + displayName)
      可供语汇系统/效果模板直接引用。

用法:
  py -3.12 scripts/probe_fx_registry.py          # 续跑(自动从断点继续)
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
BRIDGE = PROJECT / ".ae-mcp-bridge"
OUT = PROJECT / "data" / "fx_registry.json"
BATCH = 200


def send(code: str, wait: float = 20.0) -> dict:
    cmd_id = str(uuid.uuid4())[:8]
    cmd = {"id": cmd_id, "command": "runScript", "args": {"code": code}, "timestamp": time.time()}
    tmp = BRIDGE / f"ae_command_{cmd_id}.tmp"
    tmp.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    (BRIDGE / "ae_command.json").write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    res = BRIDGE / "ae_result.json"
    res.unlink(missing_ok=True)
    time.sleep(wait)
    if not res.exists():
        return {"err": "timeout"}
    return json.loads(res.read_text(encoding="utf-8"))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.parent.mkdir(exist_ok=True)
    state = {"offset": 0, "total": 0, "effects": []}
    if OUT.exists():
        state = json.loads(OUT.read_text(encoding="utf-8"))

    if not state["total"]:
        r = send("(function(){ return String(app.effects.length); })()", 8)
        n = str(r.get("result", {}).get("result", "0"))
        try:
            state["total"] = int(float(n))
        except ValueError:
            print("获取总数失败:", r)
            return 1
        print(f"AE 效果总数: {state['total']}")

    while state["offset"] < state["total"]:
        off = state["offset"]
        end = min(off + BATCH, state["total"])
        code = ("(function(){var out=[];for(var i=" + str(off + 1) +
                ";i<=" + str(end) + ";i++){var e=app.effects[i];"
                "out.push(e.matchName+'|'+e.displayName);}return out.join(';;');})()")
        r = send(code, 25)
        raw = str(r.get("result", {}).get("result", ""))
        if not raw or raw == "None":
            print(f"[{off}] 批次失败, 5s 后重试")
            time.sleep(5)
            continue
        batch = [x.split("|", 1) for x in raw.split(";;") if "|" in x]
        state["effects"].extend([{"match": m, "name": d} for m, d in batch])
        state["offset"] += len(batch)
        OUT.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        print(f"[{state['offset']}/{state['total']}] 已落盘")
    print(f"=== 枚举完成: {len(state['effects'])} 效果 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

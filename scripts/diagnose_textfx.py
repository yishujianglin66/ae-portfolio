#!/usr/bin/env python3
"""TextFX Showcase 工程诊断脚本 - 通过 Bridge 检查工程内部状态"""
import json, time, sys
from pathlib import Path
from datetime import datetime

BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")
COMP_NAME = "TextFX_Showcase"

# 诊断 JSX：返回工程结构、所有图层信息、合成属性
DIAG_JSX = r"""
(function(){
  try {
    var result = {status:"ok", project:null, comp:null, layers:[]};
    // 工程信息
    var proj = app.project;
    if (!proj) { result.status="error"; result.error="no project"; return JSON.stringify(result); }
    result.project = {
      path: proj.file ? proj.file.fsName : "(unsaved)",
      bitsPerChannel: proj.bitsPerChannel,
      numItems: proj.numItems
    };
    // 查找目标合成
    var comp = null;
    for (var i=1; i<=proj.numItems; i++) {
      var it = proj.item(i);
      if (it instanceof CompItem && it.name === "%COMP_NAME%") { comp = it; break; }
    }
    if (!comp) {
      // 列出所有合成名
      var names = [];
      for (var j=1; j<=proj.numItems; j++) {
        var ij = proj.item(j);
        if (ij instanceof CompItem) names.push(ij.name);
      }
      result.status = "error";
      result.error = "comp not found: " + "%COMP_NAME%";
      result.allComps = names;
      return JSON.stringify(result);
    }
    result.comp = {
      name: comp.name,
      width: comp.width,
      height: comp.height,
      duration: comp.duration,
      frameRate: comp.frameRate,
      bgColor: [comp.bgColor[0], comp.bgColor[1], comp.bgColor[2]],
      numLayers: comp.numLayers,
      frameDuration: comp.frameDuration,
      displayStartTime: comp.displayStartTime,
      workAreaStart: comp.workAreaStart,
      workAreaDuration: comp.workAreaDuration,
      hideShyLayer: comp.hideShyLayer
    };
    // 遍历图层
    for (var k=1; k<=comp.numLayers; k++) {
      var L = comp.layer(k);
      var info = {
        index: k,
        name: L.name,
        enabled: L.enabled,
        isVideo: L.isVideo,
        isText: false,
        inPoint: L.inPoint,
        outPoint: L.outPoint,
        startTime: L.startTime,
        duration: L.outPoint - L.inPoint,
        shy: L.shy,
        solo: L.solo,
        parent: L.parent ? L.parent.name : null,
        opacityNow: null,
        scaleNow: null,
        positionNow: null,
        effects: []
      };
      // 检查是否为文字图层
      try {
        var srcText = L.property("Source Text");
        if (srcText) {
          info.isText = true;
          var td = srcText.value;
          info.text = {
            text: td.text,
            font: td.font,
            fontSize: td.fontSize,
            fillColor: td.fillColor ? [td.fillColor[0],td.fillColor[1],td.fillColor[2]] : null,
            applyFill: td.applyFill
          };
        }
      } catch(e) {}
      // 在第 0 帧和合成中点采样属性值
      try {
        info.opacityNow = L.property("Transform").property("Opacity").valueAtTime(comp.workAreaStart, false);
        info.scaleNow = L.property("Transform").property("Scale").valueAtTime(comp.workAreaStart, false);
        info.positionNow = L.property("Transform").property("Position").valueAtTime(comp.workAreaStart, false);
        var midT = comp.workAreaStart + comp.workAreaDuration/2;
        info.opacityMid = L.property("Transform").property("Opacity").valueAtTime(midT, false);
        info.scaleMid = L.property("Transform").property("Scale").valueAtTime(midT, false);
      } catch(e) { info.transformErr = e.toString(); }
      // 检查效果
      try {
        var fx = L.property("Effects");
        if (fx && fx.numProperties > 0) {
          for (var m=1; m<=fx.numProperties; m++) {
            info.effects.push(fx.property(m).name);
          }
        }
      } catch(e) {}
      result.layers.push(info);
    }
    return JSON.stringify(result);
  } catch(e) {
    return JSON.stringify({status:"error", error:e.toString(), line:e.line});
  }
})();
""".replace("%COMP_NAME%", COMP_NAME)


def send_bridge(code, wait=60):
    """发送 JSX 到 Bridge 并等待结果。
    Bridge 结果文件格式: {"command":"runScript","status":"success","result":{...},"timestamp":...}
    """
    import time as _time
    # 用唯一时间戳标记本次命令，避免读到旧结果
    ts = datetime.now().isoformat()
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": ts, "status": "pending"}
    # 先清空旧结果文件，再写命令
    try: BRIDGE_RESULT.unlink()
    except: pass
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    for i in range(wait):
        _time.sleep(1)
        try:
            raw = BRIDGE_RESULT.read_text(encoding="utf-8")
            r = json.loads(raw)
            # Bridge 返回格式有两种可能：
            # 1. {"command":"runScript","status":"success","result":{"success":true,"data":{...}}}
            # 2. {"success":true,"data":{...}}
            status = r.get("status")
            has_success = "success" in r
            has_error = "error" in r or status == "error"
            if status == "success" or has_success or has_error:
                # 统一格式：把 result 内的内容提升到顶层
                if "result" in r and isinstance(r["result"], dict):
                    inner = r["result"]
                    # 把 inner 的字段合并到 r
                    for k, v in inner.items():
                        if k not in r:
                            r[k] = v
                return r
        except: pass
        if i % 5 == 4: print(f"  等待... ({i+1}s)")
    return {"success": False, "error": "timeout"}


def main():
    print("=" * 60)
    print("TextFX Showcase 工程诊断")
    print("=" * 60)
    r = send_bridge(DIAG_JSX, 60)
    print(f"\n[原始返回]: {json.dumps(r, ensure_ascii=False)[:300]}")
    # 兼容两种格式
    ok = r.get("success") or r.get("status") == "success"
    if not ok:
        print(f"诊断失败: {r.get('error', 'unknown')}")
        sys.exit(1)
    # 解析内部 JSX 返回值
    # 优先尝试 r.data.result（旧格式），再尝试 r.result（新格式）
    inner = r.get("data", {}).get("result") if isinstance(r.get("data"), dict) else None
    if not inner and isinstance(r.get("result"), dict):
        inner = r["result"].get("result", "{}")
    if not inner:
        inner = "{}"
    try:
        d = json.loads(inner)
    except Exception as e:
        print(f"解析 JSX 返回失败: {e}\n内容: {inner[:500]}")
        sys.exit(1)
    if d.get("status") != "ok":
        print(f"JSX 报错: {d.get('error')}")
        if d.get("allComps"):
            print(f"  可用合成: {d['allComps']}")
        sys.exit(1)
    print("\n[工程]")
    print(json.dumps(d["project"], indent=2, ensure_ascii=False))
    print("\n[合成]")
    print(json.dumps(d["comp"], indent=2, ensure_ascii=False))
    print(f"\n[图层] 共 {len(d['layers'])} 个")
    for L in d["layers"]:
        print(f"\n--- Layer {L['index']}: {L['name']} ---")
        print(f"  enabled={L['enabled']} isVideo={L['isVideo']} isText={L['isText']} shy={L['shy']} solo={L['solo']}")
        print(f"  时间: inPoint={L['inPoint']:.2f}s outPoint={L['outPoint']:.2f}s startTime={L['startTime']:.2f}s duration={L['duration']:.2f}s")
        print(f"  @0s:  opacity={L.get('opacityNow')} scale={L.get('scaleNow')} pos={L.get('positionNow')}")
        print(f"  @mid: opacity={L.get('opacityMid')} scale={L.get('scaleMid')}")
        if L.get("text"):
            t = L["text"]
            print(f"  文本: '{t['text']}' font={t['font']} size={t['fontSize']} fillColor={t['fillColor']} applyFill={t['applyFill']}")
        if L.get("effects"):
            print(f"  效果: {L['effects']}")
        if L.get("transformErr"):
            print(f"  ⚠ 变换属性错误: {L['transformErr']}")


if __name__ == "__main__":
    main()

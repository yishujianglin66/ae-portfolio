#!/usr/bin/env python3
"""AE 效果扫描器 V3 - 使用 layer.effects.add() 方式扫描"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")


def send_bridge(code, wait=120):
    ts = datetime.now().isoformat()
    cmd = {"command": "runScript", "args": {"code": code}, "timestamp": ts, "status": "pending"}
    try: BRIDGE_RESULT.unlink()
    except: pass
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            status = r.get("status")
            if status == "success" or "success" in r or status == "error":
                if isinstance(r.get("result"), dict):
                    for k, v in r["result"].items():
                        if k not in r: r[k] = v
                return r
        except: pass
        if i % 10 == 9: print(f"  等待... ({i+1}s)")
    return {"success": False, "error": "timeout"}


def extract_inner(r):
    if isinstance(r.get("data"), dict) and r["data"].get("result"):
        return r["data"]["result"]
    if isinstance(r.get("result"), dict) and r["result"].get("result"):
        return r["result"]["result"]
    return "{}"


EFFECTS_TO_SCAN = [
    {"name":"Gaussian Blur", "pkg":"Adobe Built-in"},
    {"name":"Fast Blur", "pkg":"Adobe Built-in"},
    {"name":"Box Blur", "pkg":"Adobe Built-in"},
    {"name":"Compound Blur", "pkg":"Adobe Built-in"},
    {"name":"Camera Lens Blur", "pkg":"Adobe Built-in"},
    {"name":"Directional Blur", "pkg":"Adobe Built-in"},
    {"name":"Radial Fast Blur", "pkg":"Adobe Built-in"},
    {"name":"Smart Blur", "pkg":"Adobe Built-in"},
    {"name":"Channel Blur", "pkg":"Adobe Built-in"},
    {"name":"Motion Blur", "pkg":"Adobe Built-in"},
    {"name":"Glow", "pkg":"Adobe Built-in"},
    {"name":"Inner Glow", "pkg":"Adobe Built-in"},
    {"name":"Starglow", "pkg":"Adobe Built-in"},
    {"name":"Lens Flare", "pkg":"Adobe Built-in"},
    {"name":"Drop Shadow", "pkg":"Adobe Built-in"},
    {"name":"Bevel Alpha", "pkg":"Adobe Built-in"},
    {"name":"Bevel Edges", "pkg":"Adobe Built-in"},
    {"name":"Emboss", "pkg":"Adobe Built-in"},
    {"name":"Levels", "pkg":"Adobe Built-in"},
    {"name":"Curves", "pkg":"Adobe Built-in"},
    {"name":"Color Balance", "pkg":"Adobe Built-in"},
    {"name":"Hue/Saturation", "pkg":"Adobe Built-in"},
    {"name":"Color Finesse", "pkg":"Adobe Built-in"},
    {"name":"Shadow/Highlight", "pkg":"Adobe Built-in"},
    {"name":"Broadcast Colors", "pkg":"Adobe Built-in"},
    {"name":"Posterize", "pkg":"Adobe Built-in"},
    {"name":"Threshold", "pkg":"Adobe Built-in"},
    {"name":"Twirl", "pkg":"Adobe Built-in"},
    {"name":"Bulge", "pkg":"Adobe Built-in"},
    {"name":"Spherize", "pkg":"Adobe Built-in"},
    {"name":"Ripple", "pkg":"Adobe Built-in"},
    {"name":"Displacement Map", "pkg":"Adobe Built-in"},
    {"name":"Polar Coordinates", "pkg":"Adobe Built-in"},
    {"name":"Transform", "pkg":"Adobe Built-in"},
    {"name":"Corner Pin", "pkg":"Adobe Built-in"},
    {"name":"Perspective", "pkg":"Adobe Built-in"},
    {"name":"Warp", "pkg":"Adobe Built-in"},
    {"name":"Fractal Noise", "pkg":"Adobe Built-in"},
    {"name":"Turbulent Noise", "pkg":"Adobe Built-in"},
    {"name":"Ramp", "pkg":"Adobe Built-in"},
    {"name":"4-Color Gradient", "pkg":"Adobe Built-in"},
    {"name":"Checkerboard", "pkg":"Adobe Built-in"},
    {"name":"Cell Pattern", "pkg":"Adobe Built-in"},
    {"name":"Grid", "pkg":"Adobe Built-in"},
    {"name":"Circle", "pkg":"Adobe Built-in"},
    {"name":"Ellipse", "pkg":"Adobe Built-in"},
    {"name":"Fill", "pkg":"Adobe Built-in"},
    {"name":"Roughen Edges", "pkg":"Adobe Built-in"},
    {"name":"Mosaic", "pkg":"Adobe Built-in"},
    {"name":"Noise", "pkg":"Adobe Built-in"},
    {"name":"Noise Alpha", "pkg":"Adobe Built-in"},
    {"name":"Solarize", "pkg":"Adobe Built-in"},
    {"name":"Find Edges", "pkg":"Adobe Built-in"},
    {"name":"Edge Detect", "pkg":"Adobe Built-in"},
    {"name":"Smooth", "pkg":"Adobe Built-in"},
    {"name":"Median", "pkg":"Adobe Built-in"},
    {"name":"High Pass", "pkg":"Adobe Built-in"},
    {"name":"Card Wipe", "pkg":"Adobe Built-in"},
    {"name":"Radial Wipe", "pkg":"Adobe Built-in"},
    {"name":"Linear Wipe", "pkg":"Adobe Built-in"},
    {"name":"Cross Dissolve", "pkg":"Adobe Built-in"},
    {"name":"Dissolve", "pkg":"Adobe Built-in"},
    {"name":"Audio Spectrum", "pkg":"Adobe Built-in"},
    {"name":"Audio Waveform", "pkg":"Adobe Built-in"},
    {"name":"Shake", "pkg":"Adobe Built-in"},
    {"name":"Timecode", "pkg":"Adobe Built-in"},
    {"name":"Number", "pkg":"Adobe Built-in"},
    {"name":"CC Ball Action", "pkg":"Adobe Cycore FX"},
    {"name":"CC Blobbylize", "pkg":"Adobe Cycore FX"},
    {"name":"CC Bokeh", "pkg":"Adobe Cycore FX"},
    {"name":"CC Color Offset", "pkg":"Adobe Cycore FX"},
    {"name":"CC Composite", "pkg":"Adobe Cycore FX"},
    {"name":"CC Glass", "pkg":"Adobe Cycore FX"},
    {"name":"CC Grid", "pkg":"Adobe Cycore FX"},
    {"name":"CC Kaleida", "pkg":"Adobe Cycore FX"},
    {"name":"CC Lens Flare", "pkg":"Adobe Cycore FX"},
    {"name":"CC Light Burst 2.5", "pkg":"Adobe Cycore FX"},
    {"name":"CC Light Rays", "pkg":"Adobe Cycore FX"},
    {"name":"CC Particle Systems II", "pkg":"Adobe Cycore FX"},
    {"name":"CC Particle World", "pkg":"Adobe Cycore FX"},
    {"name":"CC Pixel Polly", "pkg":"Adobe Cycore FX"},
    {"name":"CC Rain", "pkg":"Adobe Cycore FX"},
    {"name":"CC Radial Fast Blur", "pkg":"Adobe Cycore FX"},
    {"name":"CC RepeTile", "pkg":"Adobe Cycore FX"},
    {"name":"CC Scatterize", "pkg":"Adobe Cycore FX"},
    {"name":"CC Snow", "pkg":"Adobe Cycore FX"},
    {"name":"CC Star Burst", "pkg":"Adobe Cycore FX"},
    {"name":"CC Threshold", "pkg":"Adobe Cycore FX"},
    {"name":"CC Toner", "pkg":"Adobe Cycore FX"},
    {"name":"CC Vector Blur", "pkg":"Adobe Cycore FX"},
    {"name":"CC Warp", "pkg":"Adobe Cycore FX"},
    {"name":"Saber", "pkg":"Video Copilot"},
    {"name":"Optical Flares", "pkg":"Video Copilot"},
    {"name":"Element 3D", "pkg":"Video Copilot"},
    {"name":"Particular", "pkg":"Red Giant Trapcode"},
    {"name":"Form", "pkg":"Red Giant Trapcode"},
    {"name":"Shine", "pkg":"Red Giant Trapcode"},
    {"name":"Mir", "pkg":"Red Giant Trapcode"},
    {"name":"Lux", "pkg":"Red Giant Trapcode"},
    {"name":"Sound Keys", "pkg":"Red Giant Trapcode"},
    {"name":"Magic Bullet Looks", "pkg":"Red Giant Magic Bullet"},
    {"name":"Magic Bullet Colorista", "pkg":"Red Giant Magic Bullet"},
    {"name":"RG Glitch", "pkg":"Red Giant Universe"},
    {"name":"RG VHS", "pkg":"Red Giant Universe"},
    {"name":"RG Chromatic Aberration", "pkg":"Red Giant Universe"},
    {"name":"S_Glow", "pkg":"Sapphire"},
    {"name":"S_LensFlare", "pkg":"Sapphire"},
    {"name":"S_RackDefocus", "pkg":"Sapphire"},
    {"name":"BCC Lens Flare", "pkg":"Boris Continuum"},
    {"name":"BCC S_Glow", "pkg":"Boris Continuum"},
    {"name":"Deep Glow", "pkg":"Deep Glow"},
]


def main():
    print("=" * 60)
    print("AE 效果扫描器 V3")
    print("=" * 60)
    
    installed = []
    batch_size = 10
    
    for i in range(0, len(EFFECTS_TO_SCAN), batch_size):
        batch = EFFECTS_TO_SCAN[i:i+batch_size]
        batch_idx = i // batch_size + 1
        total_batches = (len(EFFECTS_TO_SCAN) + batch_size - 1) // batch_size
        print(f"\n--- Batch {batch_idx}/{total_batches} ---")
        
        effects_json = json.dumps(batch, ensure_ascii=False)
        batch_jsx = f"""(function(){{
          try {{
            var comp = null;
            for (var i = 1; i <= app.project.numItems; i++) {{
              if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "ScanComp") {{
                comp = app.project.item(i);
                break;
              }}
            }}
            var layer = comp.layer(1);
            var results = [];
            var effectsToTry = {effects_json};
            for (var j = 0; j < effectsToTry.length; j++) {{
              var eff = effectsToTry[j];
              try {{
                var added = layer.effects.add(eff.name);
                var params = [];
                for (var k = 1; k <= added.numProperties; k++) {{
                  try {{
                    params.push({{name:added.property(k).name, matchName:added.property(k).propertyMatchName, type:added.property(k).propertyValueType.toString()}});
                  }} catch(e) {{}}
                }}
                results.push({{name:added.name, matchName:added.matchName, pkg:eff.pkg, success:true, numProps:added.numProperties, params:params}});
                layer.effects.remove(added);
              }} catch(e) {{
                results.push({{name:eff.name, pkg:eff.pkg, success:false, error:e.toString().substring(0,60)}});
              }}
            }}
            return JSON.stringify({{results:results}});
          }} catch(e) {{
            return JSON.stringify({{error:e.toString()}});
          }}
        }})();"""
        
        r = send_bridge(batch_jsx, 60)
        inner = extract_inner(r)
        try:
            d = json.loads(inner)
            if d.get("error"):
                print(f"  ERROR: {d['error']}")
                continue
            for res in d["results"]:
                if res["success"]:
                    installed.append(res)
                    print(f"  ✅ {res['name']} ({res['pkg']}) - {res['numProps']} params")
                else:
                    print(f"  ❌ {res['name']} ({res['pkg']})")
        except Exception as e:
            print(f"  解析失败: {e}, inner={inner[:200]}")
    
    print(f"\n{'='*60}")
    print(f"扫描完成: 共 {len(installed)} 个效果可用")
    by_pkg = {}
    for eff in installed:
        p = eff["pkg"]
        if p not in by_pkg: by_pkg[p] = 0
        by_pkg[p] += 1
    print("\n按插件包统计:")
    for pkg, count in sorted(by_pkg.items(), key=lambda x: -x[1]):
        print(f"  {pkg}: {count}")
    
    output = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\config\installed_effects.json")
    output.write_text(json.dumps({
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_effects": len(installed),
        "stats": {"byPluginPackage": by_pkg},
        "installed": installed
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n详细清单已保存到: {output}")


if __name__ == "__main__":
    print("创建扫描合成...")
    setup_jsx = """(function(){
      try {
        for (var i = app.project.numItems; i >= 1; i--) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "ScanComp") {
            app.project.item(i).remove();
            break;
          }
        }
        var comp = app.project.items.addComp("ScanComp", 1920, 1080, 1, 10, 30);
        comp.layers.addText("Scan");
        return JSON.stringify({ok:true});
      } catch(e) {
        return JSON.stringify({ok:false, error:e.toString()});
      }
    })();"""
    r = send_bridge(setup_jsx, 30)
    inner = extract_inner(r)
    print(f"  {inner}")
    
    main()
    
    print("\n清理...")
    cleanup_jsx = """(function(){
      try {
        for (var i = app.project.numItems; i >= 1; i--) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "ScanComp") {
            app.project.item(i).remove();
            break;
          }
        }
        return JSON.stringify({ok:true});
      } catch(e) {
        return JSON.stringify({ok:false, error:e.toString()});
      }
    })();"""
    r = send_bridge(cleanup_jsx, 30)
    inner = extract_inner(r)
    print(f"  {inner}")

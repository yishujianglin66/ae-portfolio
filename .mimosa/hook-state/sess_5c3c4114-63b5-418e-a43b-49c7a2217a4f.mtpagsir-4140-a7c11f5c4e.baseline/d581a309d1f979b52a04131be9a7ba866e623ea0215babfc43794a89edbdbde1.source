#!/usr/bin/env python3
"""
定向测试高价值插件可用性 + 参数枚举
====================================
只测试组合系统需要的核心插件:
- Sapphire (光效/风格化/扭曲)
- RG Trapcode (Particular等粒子)
- Video Copilot (Element 3D, Optical Flares)
- BCC (粒子/灯光)
- Red Giant (Stylize/Transitions)
"""
import json, time, sys, uuid
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
OUTPUT = ROOT / "config" / "ae_key_plugins_test.json"

# 高价值插件matchName列表(从扫描结果中提取关键插件)
KEY_PLUGINS = {
    "Sapphire_光照": ["S_LightRays", "S_LensFlare", "S_Glow", "S_LightLeak", "S_Sun", "S_Lighting"],
    "Sapphire_风格化": ["S_EdgeFlash", "S_Neon", "S_DreamGlow", "S_FilmEffect", "S_Grain"],
    "Sapphire_扭曲": ["S_Shake", "S_Warp", "S_Inertia", "S_CameraShake"],
    "Sapphire_渲染": ["S_Rays", "S_Lightning", "S_Sparkles", "S_Particles"],
    "RG_Trapcode": ["Trapcode Particular", "Trapcode Form", "Trapcode Starglow", "Trapcode Shine", "Trapcode 3D Stroke"],
    "RG_VFX": ["RSMB", "Optical Flares", "Element"],
    "RG_Stylize": ["Magic Bullet Looks", "Knoll Light Factory"],
    "VideoCopilot": ["Element", "Optical Flares"],
    "BCC_粒子": ["BCC Particle System", "BCC Wild Cards"],
    "BCC_灯光": ["BCC Lens Flare", "BCC Light Rays", "BCC Volumetric Light"],
    "RedGiant_Motion": ["Text Anarchy", "Psunami"],
}


def send_bridge(code, wait=45):
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge not found"}
    BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    time.sleep(1)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") not in ("waiting", "pending") and "result" in r:
                return r
        except:
            pass
    return {"success": False, "error": "timeout"}


def parse_result(r):
    inner = r.get("result", {})
    if isinstance(inner, dict):
        if inner.get("success") and "data" in inner:
            result_str = inner["data"].get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    if parsed.get("status") == "success":
                        return True, parsed
                except:
                    pass
            return True, result_str
    return False, str(r)[:200]


def test_plugins_by_search():
    """通过app.effects搜索关键插件的真实matchName"""
    # 搜索关键词
    search_terms = ["Sapphire", "Trapcode", "Particular", "Element", "Optical",
                    "Shine", "Starglow", "Form", "RSMB", "Magic Bullet",
                    "BCC Particle", "BCC Light", "BCC Lens", "Text Anarchy",
                    "S_Glow", "S_Shake", "S_Rays", "S_LightRays", "S_Neon",
                    "S_LensFlare", "S_Sparkles", "S_FilmEffect", "S_CameraShake",
                    "Knoll", "Psunami", "S_Warp", "S_Inertia"]
    
    terms_json = json.dumps(search_terms)
    
    jsx = f'''(function() {{
    try {{
        var terms = {terms_json};
        var found = [];
        var fxNames = app.effects;
        
        for (var i = 0; i < fxNames.length; i++) {{
            var fx = fxNames[i];
            var dn = fx.displayName.toLowerCase();
            var mn = fx.matchName.toLowerCase();
            var cat = fx.category.toLowerCase();
            
            for (var t = 0; t < terms.length; t++) {{
                var term = terms[t].toLowerCase();
                if (dn.indexOf(term) >= 0 || mn.indexOf(term) >= 0 || cat.indexOf(term) >= 0) {{
                    found.push(fx.category + "|||" + fx.matchName + "|||" + fx.displayName);
                    break;
                }}
            }}
        }}
        
        return JSON.stringify({{status:"success", count: found.length, data: found.join("\\n")}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg: e.toString()}});
    }}
}})();'''
    
    print("[1/2] 搜索高价值插件...")
    r = send_bridge(jsx, wait=30)
    ok, data = parse_result(r)
    if not ok:
        print(f"  ✗ 搜索失败: {data}")
        return []
    
    plugins = []
    if isinstance(data, dict) and "data" in data:
        for line in data["data"].split("\n"):
            parts = line.split("|||")
            if len(parts) == 3:
                plugins.append({"category": parts[0], "matchName": parts[1], "displayName": parts[2]})
    
    print(f"  ✓ 找到 {len(plugins)} 个高价值插件")
    return plugins


def test_availability(plugins):
    """测试插件可用性并获取参数"""
    print(f"\n[2/2] 测试 {len(plugins)} 个插件可用性...")
    
    results = []
    batch_size = 10
    
    for i in range(0, len(plugins), batch_size):
        batch = plugins[i:i+batch_size]
        names = [p["matchName"] for p in batch]
        names_json = json.dumps(names)
        
        jsx = f'''(function() {{
    try {{
        var comp = app.project.items.addComp("_KEY_FX_TEST", 200, 200, 1, 1, 30);
        var solid = comp.layers.addSolid([0,0,0], "test", 200, 200, 1);
        var names = {names_json};
        var results = [];
        
        for (var i = 0; i < names.length; i++) {{
            try {{
                var e = solid.property("Effects").addProperty(names[i]);
                if (e) {{
                    var params = [];
                    for (var p = 1; p <= Math.min(e.numProperties, 15); p++) {{
                        try {{
                            var prop = e.property(p);
                            if (prop.propertyType == PropertyType.PROPERTY) {{
                                var val = "";
                                try {{ val = String(prop.value).substring(0, 30); }} catch(ve) {{ val = "N/A"; }}
                                params.push(prop.name + "=" + val);
                            }}
                        }} catch(pe) {{}}
                    }}
                    results.push("OK|||" + names[i] + "|||" + params.join(";"));
                    e.remove();
                }} else {{
                    results.push("FAIL|||" + names[i] + "|||");
                }}
            }} catch(e) {{
                results.push("ERR|||" + names[i] + "|||" + e.toString().substring(0, 50));
            }}
        }}
        
        comp.remove();
        return JSON.stringify({{status:"success", data: results.join("\\n")}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg: e.toString()}});
    }}
}})();'''
        
        r = send_bridge(jsx, wait=30)
        ok, data = parse_result(r)
        if ok and isinstance(data, dict) and "data" in data:
            for line in data["data"].split("\n"):
                parts = line.split("|||", 2)
                if len(parts) >= 2:
                    results.append({
                        "status": parts[0],
                        "matchName": parts[1],
                        "params": parts[2] if len(parts) > 2 else ""
                    })
        
        avail = len([x for x in results if x["status"] == "OK"])
        print(f"  批次 {i//batch_size+1}: 累计可用 {avail}")
        time.sleep(0.5)
    
    return results


def main():
    print("=" * 60)
    print("高价值插件定向测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 搜索
    plugins = test_plugins_by_search()
    if not plugins:
        print("✗ 未找到高价值插件")
        return
    
    # 测试可用性
    results = test_availability(plugins)
    
    # 整理
    available = [r for r in results if r["status"] == "OK"]
    unavailable = [r for r in results if r["status"] != "OK"]
    
    # 按类别分组
    name_map = {p["matchName"]: p for p in plugins}
    by_category = {}
    for r in available:
        info = name_map.get(r["matchName"], {})
        cat = info.get("category", "Unknown")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r)
    
    report = {
        "test_time": datetime.now().isoformat(),
        "total_tested": len(results),
        "available": len(available),
        "unavailable": len(unavailable),
        "by_category": {k: [{"matchName": v2["matchName"], "params": v2["params"]} for v2 in v] 
                       for k, v in by_category.items()},
        "available_list": [{"matchName": r["matchName"], "params": r["params"]} for r in available],
        "unavailable_list": [r["matchName"] for r in unavailable],
        "search_results": plugins
    }
    
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n{'='*60}")
    print(f"✓ 测试完成!")
    print(f"  测试: {len(results)}, 可用: {len(available)}, 不可用: {len(unavailable)}")
    print(f"\n  可用插件按类别:")
    for cat, items in sorted(by_category.items()):
        print(f"    [{cat}] ({len(items)}个)")
        for item in items[:3]:
            params_preview = item["params"][:60] if item["params"] else "无参数"
            print(f"      ✓ {item['matchName']}: {params_preview}")
        if len(items) > 3:
            print(f"      ... +{len(items)-3}个")
    
    if unavailable:
        print(f"\n  不可用插件:")
        for r in unavailable[:10]:
            print(f"    ✗ {r['matchName']}")
    
    print(f"\n  保存: {OUTPUT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

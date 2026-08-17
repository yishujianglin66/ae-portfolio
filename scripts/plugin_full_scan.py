#!/usr/bin/env python3
"""
AE已安装插件全量扫描 v2 (修复Bridge响应检测)
=============================================
"""
import json, time, sys, os, uuid
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
OUTPUT_DIR = ROOT / "config"
SCAN_RESULT = OUTPUT_DIR / "ae_installed_plugins.json"


def send_bridge(code, wait=60):
    """发送JSX到AE Bridge并等待响应 - 使用唯一ID检测"""
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge not found"}
    
    # 使用唯一请求ID
    req_id = str(uuid.uuid4())[:8]
    
    # 清除旧结果
    BRIDGE_RESULT.write_text(json.dumps({"status": "waiting", "req_id": req_id}), encoding="utf-8")
    
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending", "req_id": req_id}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    
    time.sleep(1)
    for i in range(wait):
        time.sleep(1)
        try:
            content = BRIDGE_RESULT.read_text(encoding="utf-8")
            r = json.loads(content)
            # 检测: 状态不是waiting 且有result字段
            status = r.get("status", "")
            if status not in ("waiting", "pending") and "result" in r:
                return r
        except Exception as e:
            pass
    return {"success": False, "error": "timeout"}


def parse_result(r):
    """解析Bridge响应"""
    if r.get("error"):
        return False, r["error"]
    
    inner = r.get("result", {})
    if isinstance(inner, dict):
        if inner.get("success") and "data" in inner:
            result_str = inner["data"].get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    if parsed.get("status") == "success":
                        return True, parsed
                    elif parsed.get("status") == "error":
                        return False, parsed.get("msg", parsed.get("error", "unknown"))
                except:
                    pass
            return True, result_str
        elif inner.get("success"):
            return True, "ok"
        elif "error" in inner:
            return False, inner["error"]
    return False, str(r)[:300]


def scan_all_effects():
    """扫描AE所有已安装效果"""
    jsx = '''(function() {
    try {
        var comp = app.project.items.addComp("_FX_SCAN_TEMP", 100, 100, 1, 1, 30);
        var solid = comp.layers.addSolid([0,0,0], "scan", 100, 100, 1);
        
        var allFX = [];
        var fxNames = app.effects;
        var count = fxNames.length;
        
        for (var i = 0; i < count; i++) {
            var fx = fxNames[i];
            allFX.push(fx.category + "|||" + fx.matchName + "|||" + fx.displayName);
        }
        
        comp.remove();
        return JSON.stringify({status:"success", count: count, data: allFX.join("\\n")});
    } catch(e) {
        return JSON.stringify({status:"error", msg: e.toString()});
    }
})();'''
    
    print("[1/3] 扫描所有已安装效果...")
    r = send_bridge(jsx, wait=45)
    ok, data = parse_result(r)
    if not ok:
        print(f"  ✗ 扫描失败: {data}")
        return None
    
    if isinstance(data, dict) and "data" in data:
        lines = data["data"].split("\n")
        effects = []
        for line in lines:
            parts = line.split("|||")
            if len(parts) == 3:
                effects.append({
                    "category": parts[0],
                    "matchName": parts[1],
                    "displayName": parts[2]
                })
        print(f"  ✓ 共发现 {len(effects)} 个效果")
        return effects
    
    print(f"  ? 返回格式异常: {str(data)[:200]}")
    return None


def test_plugin_batch(match_names):
    """批量测试插件可用性"""
    names_json = json.dumps(match_names)
    jsx = f'''(function() {{
    try {{
        var comp = app.project.items.addComp("_FX_TEST", 100, 100, 1, 1, 30);
        var solid = comp.layers.addSolid([0,0,0], "test", 100, 100, 1);
        var names = {names_json};
        var results = [];
        
        for (var i = 0; i < names.length; i++) {{
            try {{
                var e = solid.property("Effects").addProperty(names[i]);
                if (e) {{
                    var pc = e.numProperties;
                    results.push(names[i] + "|||OK|||" + pc);
                    e.remove();
                }} else {{
                    results.push(names[i] + "|||FAIL|||0");
                }}
            }} catch(e) {{
                results.push(names[i] + "|||ERR|||" + e.toString().substring(0, 40));
            }}
        }}
        
        comp.remove();
        return JSON.stringify({{status:"success", data: results.join("\\n")}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg: e.toString()}});
    }}
}})();'''
    
    r = send_bridge(jsx, wait=45)
    ok, data = parse_result(r)
    if not ok:
        return []
    
    results = []
    if isinstance(data, dict) and "data" in data:
        for line in data["data"].split("\n"):
            parts = line.split("|||")
            if len(parts) >= 2:
                results.append({
                    "matchName": parts[0],
                    "available": parts[1] == "OK",
                    "info": parts[2] if len(parts) > 2 else ""
                })
    return results


def main():
    print("=" * 60)
    print("AE 已安装插件全量扫描 v2")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Step 1: 全量扫描
    effects = scan_all_effects()
    if not effects:
        print("\n✗ 无法获取效果列表")
        return
    
    # 分类统计
    categories = {}
    for e in effects:
        cat = e["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(e)
    
    print(f"\n  分类统计 ({len(categories)} 个类别):")
    for cat in sorted(categories.keys()):
        print(f"    {cat}: {len(categories[cat])}个")
    
    # Step 2: 第三方插件可用性测试
    third_party = [e for e in effects if not e["matchName"].startswith("ADBE")]
    print(f"\n[2/3] 测试 {len(third_party)} 个第三方插件...")
    
    all_results = []
    batch_size = 15
    for i in range(0, len(third_party), batch_size):
        batch = third_party[i:i+batch_size]
        names = [e["matchName"] for e in batch]
        results = test_plugin_batch(names)
        all_results.extend(results)
        avail_count = len([r for r in results if r["available"]])
        print(f"  批次 {i//batch_size + 1}/{(len(third_party)-1)//batch_size + 1}: "
              f"{avail_count}/{len(batch)} 可用")
        time.sleep(1)
    
    # Step 3: 整理输出
    print(f"\n[3/3] 整理输出...")
    
    available_plugins = [r for r in all_results if r["available"]]
    unavailable_plugins = [r for r in all_results if not r["available"]]
    
    # 按类别整理可用插件
    cat_details = {}
    name_map = {e["matchName"]: e for e in effects}
    for r in available_plugins:
        mn = r["matchName"]
        info = name_map.get(mn, {})
        cat = info.get("category", "Unknown")
        if cat not in cat_details:
            cat_details[cat] = []
        cat_details[cat].append({
            "matchName": mn,
            "displayName": info.get("displayName", mn),
            "paramCount": r.get("info", "0")
        })
    
    report = {
        "scan_time": datetime.now().isoformat(),
        "ae_version": "25.3x71",
        "total_effects": len(effects),
        "builtin_count": len(effects) - len(third_party),
        "third_party_total": len(third_party),
        "third_party_available": len(available_plugins),
        "third_party_unavailable": len(unavailable_plugins),
        "categories_summary": {k: len(v) for k, v in sorted(categories.items())},
        "available_by_category": cat_details,
        "unavailable_list": [r["matchName"] for r in unavailable_plugins],
        "full_effect_list": effects
    }
    
    SCAN_RESULT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n{'='*60}")
    print(f"✓ 扫描完成!")
    print(f"  总效果: {report['total_effects']}")
    print(f"  内置: {report['builtin_count']}")
    print(f"  第三方: {report['third_party_total']} (可用: {report['third_party_available']})")
    print(f"\n  可用插件分类:")
    for cat, plugins in sorted(cat_details.items(), key=lambda x: -len(x[1])):
        print(f"    [{cat}] ({len(plugins)}个)")
        for p in plugins[:5]:
            print(f"      - {p['displayName']} ({p['matchName']})")
        if len(plugins) > 5:
            print(f"      ... 还有 {len(plugins)-5} 个")
    print(f"\n  保存: {SCAN_RESULT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
AE已安装插件全量扫描 + 能力清单生成
====================================
通过AE Bridge查询本机所有第三方/内置效果,
分类整理并输出结构化JSON供组合引擎使用。

用法: py -3.12 scripts/plugin_full_scan.py
"""
import json, time, sys, os
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
OUTPUT_DIR = ROOT / "config"
SCAN_RESULT = OUTPUT_DIR / "ae_installed_plugins.json"


def send_bridge(code, wait=60):
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge not found"}
    BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.5)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") != "waiting" and "result" in r:
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
                    elif parsed.get("status") == "error":
                        return False, parsed.get("msg", parsed.get("error", "unknown"))
                except:
                    pass
            return True, result_str
        elif inner.get("success"):
            return True, "ok"
        elif "error" in inner:
            return False, inner["error"]
    return False, str(r)[:200]


def scan_all_effects():
    """扫描AE所有已安装效果(含第三方插件)"""
    jsx = '''(function() {
    try {
        // 创建临时合成来枚举效果
        var comp = app.project.items.addComp("_FX_SCAN_TEMP", 100, 100, 1, 1, 30);
        var solid = comp.layers.addSolid([0,0,0], "scan", 100, 100, 1);
        
        // 获取所有可用效果
        var allFX = [];
        var effectList = solid.Effects;
        
        // 通过 app.effects 获取完整列表
        var fxNames = app.effects;
        var count = fxNames.length;
        
        for (var i = 0; i < count; i++) {
            var fx = fxNames[i];
            allFX.push({
                displayName: fx.displayName,
                matchName: fx.matchName,
                category: fx.category
            });
        }
        
        // 清理
        comp.remove();
        
        return JSON.stringify({status:"success", count: count, effects: allFX});
    } catch(e) {
        return JSON.stringify({status:"error", msg: e.toString()});
    }
})();'''
    
    print("[1/3] 扫描所有已安装效果...")
    r = send_bridge(jsx, wait=60)
    ok, data = parse_result(r)
    if not ok:
        print(f"  ✗ 扫描失败: {data}")
        return None
    
    if isinstance(data, dict) and "effects" in data:
        effects = data["effects"]
        print(f"  ✓ 共发现 {len(effects)} 个效果")
        return effects
    elif isinstance(data, str):
        try:
            parsed = json.loads(data)
            if "effects" in parsed:
                print(f"  ✓ 共发现 {len(parsed['effects'])} 个效果")
                return parsed["effects"]
        except:
            pass
    print(f"  ? 返回格式异常: {str(data)[:200]}")
    return None


def scan_third_party_details(effects):
    """对第三方插件逐个检测可用性(尝试addProperty)"""
    # 筛选第三方插件(非ADBE前缀)
    third_party = [e for e in effects if not e.get("matchName", "").startswith("ADBE")]
    print(f"\n[2/3] 检测 {len(third_party)} 个第三方插件可用性...")
    
    # 分批检测(每批20个)
    available = []
    unavailable = []
    batch_size = 20
    
    for batch_start in range(0, len(third_party), batch_size):
        batch = third_party[batch_start:batch_start + batch_size]
        match_names = [e["matchName"] for e in batch]
        names_json = json.dumps(match_names)
        
        jsx = f'''(function() {{
    try {{
        var comp = app.project.items.addComp("_FX_TEST_TEMP", 100, 100, 1, 1, 30);
        var solid = comp.layers.addSolid([0,0,0], "test", 100, 100, 1);
        var names = {names_json};
        var results = [];
        
        for (var i = 0; i < names.length; i++) {{
            var ok = false;
            try {{
                var e = solid.property("Effects").addProperty(names[i]);
                if (e) {{
                    ok = true;
                    // 获取参数列表
                    var params = [];
                    for (var p = 1; p <= e.numProperties; p++) {{
                        try {{
                            var prop = e.property(p);
                            if (prop.propertyType == PropertyType.PROPERTY) {{
                                params.push({{
                                    name: prop.name,
                                    matchName: prop.matchName,
                                    value: String(prop.value).substring(0, 50)
                                }});
                            }}
                        }} catch(pe) {{}}
                    }}
                    results.push({{matchName: names[i], available: true, params: params}});
                    e.remove();
                }} else {{
                    results.push({{matchName: names[i], available: false}});
                }}
            }} catch(e) {{
                results.push({{matchName: names[i], available: false, error: e.toString()}});
            }}
        }}
        
        comp.remove();
        return JSON.stringify({{status:"success", results: results}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg: e.toString()}});
    }}
}})();'''
        
        r = send_bridge(jsx, wait=45)
        ok, data = parse_result(r)
        if ok and isinstance(data, dict) and "results" in data:
            for item in data["results"]:
                if item.get("available"):
                    available.append(item)
                else:
                    unavailable.append(item)
        
        print(f"  批次 {batch_start//batch_size + 1}: "
              f"可用 {len([x for x in data.get('results',[]) if x.get('available')])}/"
              f"{len(batch)}")
        time.sleep(0.5)
    
    print(f"  ✓ 可用: {len(available)}, 不可用: {len(unavailable)}")
    return available, unavailable


def categorize_plugins(effects, available):
    """将插件按类别分组"""
    categories = {}
    
    # 建立matchName→displayName映射
    name_map = {e["matchName"]: e for e in effects}
    
    for item in available:
        mn = item["matchName"]
        info = name_map.get(mn, {})
        cat = info.get("category", "Unknown")
        display = info.get("displayName", mn)
        
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            "matchName": mn,
            "displayName": display,
            "category": cat,
            "params": item.get("params", []),
            "param_count": len(item.get("params", []))
        })
    
    return categories


def main():
    print("=" * 60)
    print("AE 已安装插件全量扫描")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Step 1: 全量扫描
    effects = scan_all_effects()
    if not effects:
        print("\n✗ 无法获取效果列表，请确认AE Bridge已连接")
        return
    
    # Step 2: 第三方插件可用性检测
    available, unavailable = scan_third_party_details(effects)
    
    # Step 3: 分类整理
    print(f"\n[3/3] 分类整理...")
    categories = categorize_plugins(effects, available)
    
    # 输出报告
    report = {
        "scan_time": datetime.now().isoformat(),
        "total_effects": len(effects),
        "builtin_count": len([e for e in effects if e.get("matchName","").startswith("ADBE")]),
        "third_party_total": len([e for e in effects if not e.get("matchName","").startswith("ADBE")]),
        "third_party_available": len(available),
        "third_party_unavailable": len(unavailable),
        "categories": {k: len(v) for k, v in sorted(categories.items())},
        "category_details": categories,
        "unavailable_plugins": [u["matchName"] for u in unavailable],
        "all_effects_index": [
            {"displayName": e["displayName"], "matchName": e["matchName"], "category": e["category"]}
            for e in effects
        ]
    }
    
    # 保存
    SCAN_RESULT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"✓ 扫描完成! 结果保存: {SCAN_RESULT}")
    print(f"  总效果数: {report['total_effects']}")
    print(f"  内置(ADBE): {report['builtin_count']}")
    print(f"  第三方: {report['third_party_total']} (可用: {report['third_party_available']})")
    print(f"\n  分类统计:")
    for cat, count in sorted(report['categories'].items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}个")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

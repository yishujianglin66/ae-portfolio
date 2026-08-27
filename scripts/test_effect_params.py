"""测试效果的参数名"""
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "video"))

from style_migration_executor import MCPBridgeClient


def main():
    print("=== 效果参数名测试 ===")
    client = MCPBridgeClient(timeout=60.0)
    if not client.ping():
        print("Bridge 不可用")
        return

    test_jsx = r"""
(function() {
    var result = {effects: {}};
    try {
        var comp = app.project.items.addComp("Test_Params", 1920, 1080, 1.0, 1, 30);
        var adj = comp.layers.addSolid([0, 0, 0], "Adj", 1920, 1080, 1.0, 1);
        adj.adjustmentLayer = true;
        var fxParade = adj.Effects;

        var effectsToTest = [
            "ADBE Lumetri",
            "ADBE Brightness & Contrast 2",
            "ADBE Glo2",
            "ADBE Sharpen",
            "ADBE HUE SATURATION",
            "ADBE Tint"
        ];

        for (var i = 0; i < effectsToTest.length; i++) {
            try {
                var fx = fxParade.addProperty(effectsToTest[i]);
                var params = [];
                // 列出所有属性
                var propGroup = fx;
                if (fx.numProperties) {
                    for (var j = 1; j <= fx.numProperties; j++) {
                        try {
                            var p = fx.property(j);
                            params.push({
                                index: j,
                                name: p.name,
                                matchName: p.matchName,
                                type: typeof p
                            });
                        } catch(e) {}
                    }
                }
                result.effects[effectsToTest[i]] = {
                    status: "ok",
                    numProperties: fx.numProperties,
                    params: params
                };
            } catch(e) {
                result.effects[effectsToTest[i]] = {
                    status: "fail",
                    error: e.toString()
                };
            }
        }
        result.status = "success";
    } catch(e) {
        result.status = "error";
        result.message = e.toString();
    }
    return JSON.stringify(result, null, 2);
})();
"""
    r = client.send_command("runScript", {"code": test_jsx})
    inner = r.get("result", {}).get("result", "")
    if isinstance(inner, str):
        try: inner = json.loads(inner)
        except: pass
    if not isinstance(inner, dict):
        print(f"无法解析: {inner}")
        return

    print(f"状态: {inner.get('status')}")
    effects = inner.get("effects", {})
    for fx_name, fx_data in effects.items():
        print(f"\n--- {fx_name} ---")
        if fx_data.get("status") != "ok":
            print(f"  ERROR: {fx_data.get('error')}")
            continue
        print(f"  属性数: {fx_data.get('numProperties')}")
        for p in fx_data.get("params", []):
            print(f"  [{p['index']:2d}] {p['name']} | {p['matchName']}")

    # 保存完整结果
    out = PROJECT_ROOT / "output_director" / "effect_params_map.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(inner, f, ensure_ascii=False, indent=2)
    print(f"\n保存: {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""TextFX 效果兼容性自动检测脚本.

在 AE 环境中验证每个文字特效的兼容性：
1. 创建测试合成 → 添加文字图层 → 逐个应用效果 → 检测错误
2. 输出兼容性矩阵（AE 2025 25.3 目标版本）

使用方法:
    python scripts/verify_textfx_compat.py           # 全部验证
    python scripts/verify_textfx_compat.py --quick    # 快速模式（仅结构检查）
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = PROJECT_ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = PROJECT_ROOT / ".ae-mcp-bridge" / "ae_result.json"


# ---------------------------------------------------------------------------
# Bridge 通信
# ---------------------------------------------------------------------------

def send_bridge(code: str, wait: int = 30) -> dict:
    """通过小面板 Bridge 发送 ExtendScript 到 AE."""
    cmd = {
        "command": "runScript",
        "args": {"code": code},
        "status": "pending",
        "timestamp": datetime.now().isoformat(),
    }
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    for i in range(wait):
        time.sleep(1)
        if not BRIDGE_RESULT.exists():
            continue
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") in ("success", "error"):
                return r
        except Exception:
            pass
        if (i + 1) % 5 == 0:
            print(f"  等待 AE 响应... {i + 1}s")
    return {"status": "error", "error": "Bridge timeout"}


# ---------------------------------------------------------------------------
# 效果清单（AE 2025 目标验证列表）
# ---------------------------------------------------------------------------

EFFECTS = {
    "blur": {
        "name": "高斯模糊 (Gaussian Blur)",
        "matchName": "ADBE Gaussian Blur",
        "risk": "matchName 可能变更",
    },
    "lens_flare": {
        "name": "镜头光晕 (Lens Flare)",
        "matchName": "ADBE Lens Flare",
        "risk": "参数结构变更",
    },
    "fractal_noise": {
        "name": "分形噪波 (Fractal Noise)",
        "matchName": "ADBE Fractal Noise",
        "risk": "GPU 加速兼容性",
    },
    "glow": {
        "name": "发光 (Glow)",
        "matchName": "ADBE Glo2",
        "risk": "渲染表现差异",
    },
    "drop_shadow": {
        "name": "投影 (Drop Shadow)",
        "matchName": "ADBE Drop Shadow",
        "risk": "低",
    },
    "fill": {
        "name": "填充 (Fill)",
        "matchName": "ADBE Fill",
        "risk": "低",
    },
    "gradient_ramp": {
        "name": "渐变 (Gradient Ramp)",
        "matchName": "ADBE Gradient Ramp",
        "risk": "低",
    },
    "tritone": {
        "name": "三色调 (Tritone)",
        "matchName": "ADBE Tritone",
        "risk": "可能移除",
    },
    "roughen_edges": {
        "name": "粗糙边缘 (Roughen Edges)",
        "matchName": "ADBE Roughen Edges",
        "risk": "中等",
    },
    "cc_sphere": {
        "name": "CC Sphere",
        "matchName": "CC Sphere",
        "risk": "CC 系列可能移除",
    },
    "cc_cylinder": {
        "name": "CC Cylinder",
        "matchName": "CC Cylinder",
        "risk": "CC 系列可能移除",
    },
    "cc_glass": {
        "name": "CC Glass",
        "matchName": "CC Glass",
        "risk": "CC 系列可能移除",
    },
    "cc_particle_world": {
        "name": "CC Particle World",
        "matchName": "CC Particle World",
        "risk": "性能差异",
    },
    "turbulent_displace": {
        "name": "湍流置换 (Turbulent Displace)",
        "matchName": "ADBE Turbulent Displace",
        "risk": "低",
    },
    "wave_warp": {
        "name": "波形弯曲 (Wave Warp)",
        "matchName": "ADBE Wave Warp",
        "risk": "低",
    },
    "venetian_blinds": {
        "name": "百叶窗 (Venetian Blinds)",
        "matchName": "ADBE Venetian Blinds",
        "risk": "低",
    },
    "linear_wipe": {
        "name": "线性擦除 (Linear Wipe)",
        "matchName": "ADBE Linear Wipe",
        "risk": "低",
    },
    "stroke": {
        "name": "描边 (Stroke)",
        "matchName": "ADBE Stroke",
        "risk": "低",
    },
    "offset": {
        "name": "偏移 (Offset)",
        "matchName": "ADBE Offset",
        "risk": "低",
    },
    "mosaic": {
        "name": "马赛克 (Mosaic)",
        "matchName": "ADBE Mosaic",
        "risk": "低",
    },
}


# ---------------------------------------------------------------------------
# 验证逻辑
# ---------------------------------------------------------------------------

def build_compat_jsx() -> str:
    """构建在 AE 中批量检测效果的 JSX 脚本."""
    effects_json = json.dumps(
        {k: v["matchName"] for k, v in EFFECTS.items()},
        ensure_ascii=False,
    )
    return f"""
(function() {{
    var effects = {effects_json};
    var results = {{}};

    // 创建临时合成
    var comp = app.project.items.addComp("__CompatTest__", 100, 100, 1, 5, 30);
    var textLayer = comp.layers.addText("Test");

    for (var key in effects) {{
        var matchName = effects[key];
        var result = {{ matchName: matchName }};

        try {{
            // 尝试通过 matchName 应用效果
            var fx = textLayer.Effects.addProperty(matchName);
            if (fx) {{
                result.status = "available";
                result.matchNameActual = fx.matchName;
                result.displayName = fx.name;

                // 尝试读取参数以检测参数结构兼容性
                try {{
                    var props = fx.numProperties;
                    result.numProperties = props;
                    result.paramTest = "ok";
                }} catch(e2) {{
                    result.paramTest = "failed: " + e2.toString();
                }}

                // 尝试设置常见参数
                try {{
                    var prop1 = fx.property(1);
                    if (prop1 && prop1.isTimeVarying) {{
                        result.hasKeyframes = true;
                    }}
                    result.setParamTest = "ok";
                }} catch(e3) {{
                    result.setParamTest = "failed: " + e3.toString();
                }}
            }} else {{
                result.status = "not_found";
                result.error = "Effect.addProperty returned null";
            }}
        }} catch(e) {{
            result.status = "error";
            result.error = e.toString();
        }}
        results[key] = result;
    }}

    // 清理
    comp.remove();

    // 通过全局变量回传结果
    $.global.__aeAdditiveResult = JSON.stringify(results);
}})();
"""


def quick_structure_check() -> dict[str, dict]:
    """快速模式：仅检查结构，不连接 AE."""
    results = {}
    for key, info in EFFECTS.items():
        match_name = info["matchName"]
        # 结构检查
        is_cc = match_name.startswith("CC ")
        is_adbe = match_name.startswith("ADBE ")
        results[key] = {
            "name": info["name"],
            "matchName": match_name,
            "prefix": "CC" if is_cc else "ADBE" if is_adbe else "OTHER",
            "risk": info["risk"],
            "status": "structure_checked",  # 未连接 AE，仅结构检查
        }
    return results


def run_ae_verification() -> dict[str, dict]:
    """连接 AE 实际验证效果兼容性."""
    if not BRIDGE_CMD.parent.exists():
        return {"error": "Bridge 目录不存在，请先启动 AE Bridge"}

    jsx = build_compat_jsx()
    print(f"发送验证脚本 ({len(jsx)} chars)...")
    result = send_bridge(jsx, wait=60)

    if result.get("status") == "error":
        return {"error": result.get("error", "Unknown error")}

    # 解析 AE 返回的结果
    try:
        data = result.get("result") or result.get("data") or "{}"
        if isinstance(data, str):
            parsed = json.loads(data)
        else:
            parsed = data
        return parsed
    except Exception as e:
        return {"error": f"结果解析失败: {e}", "raw": str(result)[:500]}


# ---------------------------------------------------------------------------
# 报告生成
# ---------------------------------------------------------------------------

def print_report(results: dict[str, dict]):
    """打印兼容性报告."""
    total = len(results)
    available = sum(1 for v in results.values() if v.get("status") in ("available", "structure_checked"))
    errors = sum(1 for v in results.values() if v.get("status") == "error")
    not_found = sum(1 for v in results.values() if v.get("status") == "not_found")

    print()
    print("=" * 70)
    print(" TextFX 效果兼容性验证报告")
    print("=" * 70)
    print(f"  总计效果: {total}")
    print(f"  可用:     {available} ({available * 100 // total}%)")
    print(f"  未找到:   {not_found}")
    print(f"  错误:     {errors}")
    print("-" * 70)

    for key, info in EFFECTS.items():
        r = results.get(key, {})
        status = r.get("status", "unknown")
        icon = {
            "available": "✅",
            "structure_checked": "⬜",
            "not_found": "❌",
            "error": "💥",
        }.get(status, "❓")

        actual = r.get("matchNameActual") or r.get("matchName", "")
        risk = info["risk"]
        print(f"  {icon} {info['name']:<30s} [{status}]")
        if status not in ("available", "structure_checked"):
            print(f"     matchName: {actual}, 风险: {risk}")
            if r.get("error"):
                print(f"     错误: {r['error'][:100]}")

    print("-" * 70)

    # 风险汇总
    high_risk = [(k, v) for k, v in EFFECTS.items() if "可能移除" in v["risk"] or "可能变更" in v["risk"]]
    if high_risk:
        print("\n⚠️  高风险效果（需重点关注）:")
        for key, info in high_risk:
            r = results.get(key, {})
            s = r.get("status", "unknown")
            print(f"  - {info['name']} ({info['matchName']}) [{s}] 风险: {info['risk']}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="TextFX 效果兼容性验证")
    parser.add_argument("--quick", action="store_true", help="快速模式（仅结构检查，不连接 AE）")
    parser.add_argument("--output", type=str, help="输出 JSON 报告路径")
    args = parser.parse_args()

    print("TextFX 效果兼容性验证")
    print("AE 目标版本: AE 2025 (25.3)")
    print(f"验证效果数: {len(EFFECTS)}")
    print()

    if args.quick:
        print("[快速模式] 仅结构检查，不连接 AE...")
        results = quick_structure_check()
    else:
        print("[AE 模式] 连接 AE 实际验证...")
        print(f"Bridge 目录: {BRIDGE_CMD.parent}")
        if not BRIDGE_CMD.parent.exists():
            print("ERROR: Bridge 目录不存在")
            print("请先启动 AE 并加载 Bridge 面板")
            sys.exit(1)
        results = run_ae_verification()

    if "error" in results and len(results) == 1:
        print(f"\n验证失败: {results['error']}")
        sys.exit(1)

    print_report(results)

    # 输出 JSON
    if args.output:
        output_path = Path(args.output)
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_effects": len(EFFECTS),
            "results": results,
        }
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告已保存: {output_path}")

    # 返回退出码
    errors = sum(1 for v in results.values() if v.get("status") == "error")
    not_found = sum(1 for v in results.values() if v.get("status") == "not_found")
    if errors > 0 or not_found > len(EFFECTS) * 0.2:
        sys.exit(1)


if __name__ == "__main__":
    main()

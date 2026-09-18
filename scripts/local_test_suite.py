#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AE-Knowledge-Vault 本地测试套件
在本地有AE 2025的环境中运行，一键执行V2验证和效果测试

用法:
    py -3.12 scripts/local_test_suite.py --all
    py -3.12 scripts/local_test_suite.py --v2
    py -3.12 scripts/local_test_suite.py --combo
    py -3.12 scripts/local_test_suite.py --effects
    py -3.12 scripts/local_test_suite.py --render
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# 配置
AE_EXE = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
AERENDER = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe"
PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
OUTPUT_DIR = Path(r"D:\AE-Work")

# 使用小面板 Bridge 路径（2_mcp_bridge_loader.jsx）
BRIDGE_DIR = PROJECT_ROOT / ".ae-mcp-bridge"
COMMAND_FILE = BRIDGE_DIR / "ae_command.json"
RESULT_FILE = BRIDGE_DIR / "ae_result.json"

# 确保目录存在
BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def is_ae_running():
    """检查AE是否在运行"""
    result = subprocess.run(
        ["powershell", "-Command", "Get-Process -Name AfterFX -ErrorAction SilentlyContinue"],
        capture_output=True, text=True
    )
    return "AfterFX" in result.stdout


def start_ae():
    """启动AE并等待Bridge加载"""
    if is_ae_running():
        print("✅ AE 已在运行")
        return True

    print("🚀 启动 AE 2025...")
    subprocess.Popen([AE_EXE], creationflags=subprocess.CREATE_NEW_CONSOLE)

    # 等待AE加载（最多60秒）
    for i in range(60):
        time.sleep(1)
        if is_ae_running():
            print(f"✅ AE 已启动（等待 {i+1} 秒）")
            print("⏳ 等待 Bridge 自动加载（Startup脚本）...")
            time.sleep(5)  # 额外等待Bridge加载
            return True
        if (i + 1) % 10 == 0:
            print(f"  已等待 {i+1} 秒...")

    print("❌ AE 启动超时")
    return False


def send_bridge_command(script_path, args_dict=None):
    """通过小面板 Bridge 发送命令到 AE。
    
    小面板协议 (2_mcp_bridge_loader.jsx):
    - 命令格式: {"command": "runScript", "args": {"code": jsxContent}, ...}
    - 监听目录: {项目根}/.ae-mcp-bridge/
    """
    args_dict = args_dict or {}

    # 读取 JSX 文件内容（runScript 方式发送代码字符串）
    script_path = Path(script_path)
    jsx_code = script_path.read_text(encoding="utf-8")

    # 如果有额外参数，注入到代码前面
    if args_dict:
        args_json = json.dumps(args_dict, ensure_ascii=False)
        jsx_code = f"var __bridgeArgs = {args_json};\n" + jsx_code

    command = {
        "command": "runScript",
        "args": {"code": jsx_code},
        "status": "pending",
        "timestamp": time.time()
    }

    # 写入命令文件
    with open(COMMAND_FILE, "w", encoding="utf-8") as f:
        json.dump(command, f, ensure_ascii=False)

    print(f"📤 发送命令: {script_path.name}")

    # 等待结果（最多60秒，AE 操作可能较慢）
    for i in range(60):
        time.sleep(1)
        if RESULT_FILE.exists():
            try:
                with open(RESULT_FILE, "r", encoding="utf-8") as f:
                    result = json.load(f)
                # 检查是否有有效结果（success/error 状态）
                if result.get("status") in ("success", "error"):
                    return result
            except Exception as e:
                print(f"  读取结果出错: {e}")
                continue
        if (i + 1) % 10 == 0:
            print(f"  等待结果... {i+1}秒")

    return {"status": "error", "message": "等待结果超时（60s）"}


def test_v2_project():
    """测试V2增强版工程"""
    print("\n" + "=" * 60)
    print("🎬 测试 V2 增强版工程")
    print("=" * 60)

    script_path = PROJECT_ROOT / "temp" / "textfx_showcase_v2_enhanced.jsx"
    result = send_bridge_command(script_path)

    if result.get("status") == "success":
        print("✅ V2 工程创建成功")
        print(f"   合成名称: {result.get('compName')}")
        print(f"   图层数量: {result.get('layerCount')}")
        print(f"   场景数量: {result.get('scenes')}")
        print("   增强功能:")
        for feat in result.get("enhancedFeatures", []):
            print(f"      - {feat}")
    else:
        print(f"❌ V2 工程创建失败: {result.get('message')}")

    return result


def test_effect_combos():
    """测试5个特效组合"""
    print("\n" + "=" * 60)
    print("✨ 测试特效组合生成器")
    print("=" * 60)

    # 先创建测试合成
    test_script = PROJECT_ROOT / "mcp-extension" / "scripts" / "addTextLayer.jsx"
    test_result = send_bridge_command(test_script, {
        "compName": "TestCombo",
        "text": "TEST",
        "fontSize": 100
    })

    if test_result.get("status") != "success":
        print("❌ 测试合成创建失败，跳过组合测试")
        return []

    combos = [
        ("cyberGlow", "赛博朋克"),
        ("neonEffect", "霓虹发光"),
        ("hologramEffect", "全息投影"),
        ("fireIceEffect", "冰火对比"),
        ("colorGrade", "调色预设"),
    ]

    results = []
    combo_script = PROJECT_ROOT / "mcp-extension" / "scripts" / "applyEffectCombo.jsx"

    for combo_type, name in combos:
        print(f"\n🧪 测试 {name} ({combo_type})...")
        result = send_bridge_command(combo_script, {
            "compName": "TestCombo",
            "layerIndex": 1,
            "comboType": combo_type
        })

        if result.get("status") == "success":
            print(f"✅ {name} 成功")
            applied = result.get("appliedEffects", [])
            for effect in applied:
                print(f"   - {effect}")
        else:
            print(f"❌ {name} 失败: {result.get('message')}")

        results.append({
            "type": combo_type,
            "name": name,
            "success": result.get("status") == "success",
            "result": result
        })

    return results


def test_ae_effects():
    """验证8个待测AE 2025效果"""
    print("\n" + "=" * 60)
    print("🔍 验证 AE 2025 效果兼容性")
    print("=" * 60)

    effects_to_test = [
        ("ADBE Gaussian Blur 2", "高斯模糊"),
        ("ADBE Lens Flare", "镜头光晕"),
        ("ADBE Fractal Noise", "分形噪波"),
        ("ADBE Easy Levels2", "色阶"),
        ("ADBE HUE SATURATION", "色相/饱和度"),
        ("ADBE Grid", "网格"),
        ("ADBE Roughen Edges", "粗糙边缘"),
        ("ADBE Turbulent Displace", "扭曲"),
    ]

    # 创建测试脚本
    test_jsx = BRIDGE_DIR / "temp" / "test_effects.jsx"
    test_jsx.parent.mkdir(parents=True, exist_ok=True)

    jsx_code = '''
#include "''' + str(PROJECT_ROOT / "mcp-extension" / "scripts" / "_lib" / "args_loader.jsx") + '''";
#include "''' + str(PROJECT_ROOT / "mcp-extension" / "scripts" / "_lib" / "response_utils.jsx") + '''";

function main() {
    var comp = app.project.items.addComp("EffectTest", 1920, 1080, 1, 5, 30);
    var layer = comp.layers.addSolid([0.5,0.5,0.5], "TestLayer", 1920, 1080, 1, 5);

    var effects = [
        ["ADBE Gaussian Blur 2", "高斯模糊"],
        ["ADBE Lens Flare", "镜头光晕"],
        ["ADBE Fractal Noise", "分形噪波"],
        ["ADBE Easy Levels2", "色阶"],
        ["ADBE HUE SATURATION", "色相/饱和度"],
        ["ADBE Grid", "网格"],
        ["ADBE Roughen Edges", "粗糙边缘"],
        ["ADBE Turbulent Displace", "扭曲"]
    ];

    var results = [];
    for (var i = 0; i < effects.length; i++) {
        var matchName = effects[i][0];
        var cnName = effects[i][1];
        var success = false;
        var error = "";
        try {
            var effect = layer.property("ADBE Effect Parade").addProperty(matchName);
            success = (effect != null);
        } catch (e) {
            error = e.toString();
        }
        results.push({
            matchName: matchName,
            name: cnName,
            success: success,
            error: error
        });
    }

    // 清理
    comp.remove();

    return buildSuccess({results: results});
}

main();
'''

    with open(test_jsx, "w", encoding="utf-8") as f:
        f.write(jsx_code)

    result = send_bridge_command(test_jsx)

    tested = []
    if result.get("status") == "success":
        for item in result.get("results", []):
            status = "✅" if item.get("success") else "❌"
            print(f"{status} {item.get('name')} ({item.get('matchName')})")
            if not item.get("success"):
                print(f"   错误: {item.get('error', '未知')}")
            tested.append(item)
    else:
        print(f"❌ 效果测试失败: {result.get('message')}")

    return tested


def render_v2():
    """渲染V2工程"""
    print("\n" + "=" * 60)
    print("🎞️ 渲染 V2 工程")
    print("=" * 60)

    aep_path = OUTPUT_DIR / "TextFX_Showcase_V2.aep"
    output_path = OUTPUT_DIR / "TextFX_Showcase_V2_Test.mp4"

    if not aep_path.exists():
        print(f"❌ 工程文件不存在: {aep_path}")
        return False

    print("🎬 开始渲染...")
    print(f"   输入: {aep_path}")
    print(f"   输出: {output_path}")

    result = subprocess.run([
        AERENDER,
        "-project", str(aep_path),
        "-comp", "TextFX_Showcase_V2",
        "-output", str(output_path)
    ], capture_output=True, text=True)

    if result.returncode == 0:
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"✅ 渲染成功: {output_path} ({size_mb:.2f} MB)")
            return True
        else:
            print("⚠️ 渲染命令成功但输出文件不存在")
            return False
    else:
        print("❌ 渲染失败:")
        print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="AE-Knowledge-Vault 本地测试套件")
    parser.add_argument("--all", action="store_true", help="执行全部测试")
    parser.add_argument("--v2", action="store_true", help="测试V2工程")
    parser.add_argument("--combo", action="store_true", help="测试特效组合")
    parser.add_argument("--effects", action="store_true", help="验证AE效果兼容性")
    parser.add_argument("--render", action="store_true", help="渲染V2工程")
    args = parser.parse_args()

    if not any([args.all, args.v2, args.combo, args.effects, args.render]):
        parser.print_help()
        return

    # 启动AE
    if not start_ae():
        print("❌ 无法启动AE，测试中止")
        return

    results = {}

    # 执行测试
    if args.all or args.v2:
        results["v2"] = test_v2_project()

    if args.all or args.combo:
        results["combos"] = test_effect_combos()

    if args.all or args.effects:
        results["effects"] = test_ae_effects()

    if args.all or args.render:
        results["render"] = render_v2()

    # 输出总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)

    if "v2" in results:
        r = results["v2"]
        status = "✅" if r.get("status") == "success" else "❌"
        print(f"{status} V2工程: {r.get('message', 'N/A')}")

    if "combos" in results:
        combos = results["combos"]
        success_count = sum(1 for c in combos if c["success"])
        print(f"{'✅' if success_count == 5 else '⚠️'} 特效组合: {success_count}/5 成功")

    if "effects" in results:
        effects = results["effects"]
        success_count = sum(1 for e in effects if e.get("success"))
        print(f"{'✅' if success_count == 8 else '⚠️'} 效果兼容: {success_count}/8 可用")

    if "render" in results:
        print(f"{'✅' if results['render'] else '❌'} 渲染输出")

    print("\n测试完成。请在本地AE环境中运行此脚本。")


if __name__ == "__main__":
    main()

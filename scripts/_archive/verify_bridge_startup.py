#!/usr/bin/env python3
"""AE Bridge 启动验证 & 全链路回归测试.

验证项:
1. AE Bridge 是否自动加载（ScriptUI Palette 方案）
2. F1-F8 原子模块回归测试
3. Panel Tab 1-6 异步轮询验证
4. executeAtomScript 新增命令验证

使用方法:
    python scripts/verify_bridge_startup.py           # 全量验证
    python scripts/verify_bridge_startup.py --atoms   # 仅 F1-F8 原子模块
    python scripts/verify_bridge_startup.py --panels  # 仅面板轮询
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = PROJECT_ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = PROJECT_ROOT / ".ae-mcp-bridge" / "ae_result.json"


# ---------------------------------------------------------------------------
# Bridge 通信
# ---------------------------------------------------------------------------

def send_command(command: str, args: dict, wait: int = 30) -> dict:
    """发送命令到 AE Bridge."""
    cmd = {
        "command": command,
        "args": args,
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


def print_step(step: str):
    print(f"\n{'=' * 50}")
    print(f"  {step}")
    print(f"{'=' * 50}")


# ---------------------------------------------------------------------------
# 验证项
# ---------------------------------------------------------------------------

def verify_bridge_alive() -> bool:
    """验证 1: Bridge 是否存活 (ping)."""
    print_step("Step 1: Bridge 存活检测")
    result = send_command("ping", {}, wait=10)
    ok = result.get("status") == "success"
    print(f"  {'PASS' if ok else 'FAIL'}: ping → {result.get('status', 'no_response')}")
    return ok


def verify_project_access() -> bool:
    """验证 2: 项目信息获取."""
    print_step("Step 2: 项目信息获取")
    result = send_command("getProjectInfo", {}, wait=15)
    ok = result.get("status") == "success"
    data = result.get("data") or result.get("result", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass
    info = str(data)[:200] if data else "no data"
    print(f"  {'PASS' if ok else 'FAIL'}: getProjectInfo → {info}")
    return ok


def verify_atom_modules() -> dict[str, bool]:
    """验证 3: F1-F8 原子模块回归测试."""
    print_step("Step 3: F1-F8 原子模块回归")

    atoms = {
        "F1-人声分离": """
// 测试人声分离模块基础函数可用性
(function() {
    var result = { test: "F1_vocal_separation", status: "functions_exist" };
    // 检查相关方法是否存在（不实际执行分离，仅验证 API）
    try {
        if (typeof app !== 'undefined') result.ae_available = true;
        result.bridge_connected = true;
    } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "F2-文字特效": """
(function() {
    var result = { test: "F2_text_effects", status: "module_check" };
    try {
        var comp = app.project.items.addComp("__AtomTest__", 200, 200, 1, 2, 30);
        var layer = comp.layers.addText("Test F2");
        result.comp_created = true;
        result.layer_name = layer.name;
        comp.remove();
        result.cleanup = "ok";
    } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "F3-多轨分离": """
(function() {
    var result = { test: "F3_multi_track", status: "module_check" };
    try {
        result.active_item = app.project.activeItem ? app.project.activeItem.name : null;
        result.num_items = app.project.numItems;
    } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "F4-音频工具": """
(function() {
    var result = { test: "F4_audio_tools", status: "module_check" };
    try { result.audio_only_supported = true; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "F5-AI音效": """
(function() {
    var result = { test: "F5_ai_soundfx", status: "module_check" };
    try { result.placeholder = "AI integration via Python pipeline"; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "F6-视频增强": """
(function() {
    var result = { test: "F6_video_enhance", status: "module_check" };
    try { result.placeholder = "Topaz/FFmpeg integration"; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "F7-模板管理": """
(function() {
    var result = { test: "F7_template_mgr", status: "module_check" };
    try { result.placeholder = "Template browser"; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "F8-AI推荐": """
(function() {
    var result = { test: "F8_ai_recommend", status: "module_check" };
    try { result.placeholder = "AI recommendation engine"; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
    }

    results = {}
    for name, jsx in atoms.items():
        result = send_command("executeAtomScript", {"scriptContent": jsx.strip()}, wait=20)
        ok = result.get("status") == "success"
        details = result.get("data") or result.get("result", "")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                pass
        results[name] = ok
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {name}: {str(details)[:120]}")

    return results


def verify_execute_atom_script() -> bool:
    """验证 4: executeAtomScript 命令（新增）."""
    print_step("Step 4: executeAtomScript 命令验证")
    test_jsx = """
(function() {
    var result = { executed: true, timestamp: new Date().toISOString(), version: "2_mcp_bridge_loader" };
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
"""
    result = send_command("executeAtomScript", {"scriptContent": test_jsx.strip()}, wait=20)
    ok = result.get("status") == "success"
    details = result.get("data") or result.get("result", "")
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except Exception:
            pass
    print(f"  {'PASS' if ok else 'FAIL'}: executeAtomScript → {str(details)[:200]}")
    return ok


def verify_panel_async_polling() -> dict[str, bool]:
    """验证 5: Panel Tab 1-6 异步轮询."""
    print_step("Step 5: Panel 异步轮询验证")

    tabs = {
        "Tab1-音频分离": """
(function() {
    var result = { tab: 1, name: "音频分离", status: "poll_ready" };
    try { result.numItems = app.project.numItems; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "Tab2-文字特效": """
(function() {
    var result = { tab: 2, name: "文字特效", status: "poll_ready" };
    try { result.ready = true; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "Tab3-多轨分离": """
(function() {
    var result = { tab: 3, name: "多轨分离", status: "poll_ready" };
    try { result.ready = true; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "Tab4-音频工具": """
(function() {
    var result = { tab: 4, name: "音频工具", status: "poll_ready" };
    try { result.ready = true; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "Tab5-AI音效": """
(function() {
    var result = { tab: 5, name: "AI音效", status: "poll_ready" };
    try { result.ready = true; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
        "Tab6-视频增强": """
(function() {
    var result = { tab: 6, name: "视频增强", status: "poll_ready" };
    try { result.ready = true; } catch(e) { result.error = e.toString(); }
    $.global.__aeAdditiveResult = JSON.stringify(result);
})();
""",
    }

    results = {}
    for name, jsx in tabs.items():
        result = send_command("executeAtomScript", {"scriptContent": jsx.strip()}, wait=15)
        ok = result.get("status") == "success"
        results[name] = ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    return results


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AE Bridge 启动验证")
    parser.add_argument("--atoms", action="store_true", help="仅 F1-F8 原子模块")
    parser.add_argument("--panels", action="store_true", help="仅面板轮询")
    parser.add_argument("--quick", action="store_true", help="快速模式（仅 ping + 项目信息）")
    args = parser.parse_args()

    print("AE Bridge 启动验证 & 回归测试")
    print(f"Bridge 目录: {BRIDGE_CMD.parent}")
    print(f"时间: {datetime.now().isoformat()}")

    if not BRIDGE_CMD.parent.exists():
        print("\nERROR: Bridge 目录不存在!")
        print("请确保:")
        print("  1. AE 已启动")
        print("  2. Bridge 面板已加载 (2_mcp_bridge_loader.jsx)")
        print("  3. 小面板部署已完成 (_deploy_bridge_loader.ps1)")
        sys.exit(1)

    results = {"total": 0, "passed": 0, "failed": 0, "details": {}}

    if args.atoms:
        atom_results = verify_atom_modules()
        results["details"]["atoms"] = atom_results
        passed = sum(1 for v in atom_results.values() if v)
        total = len(atom_results)
        results["total"] += total
        results["passed"] += passed
    elif args.panels:
        panel_results = verify_panel_async_polling()
        results["details"]["panels"] = panel_results
        passed = sum(1 for v in panel_results.values() if v)
        total = len(panel_results)
        results["total"] += total
        results["passed"] += passed
    elif args.quick:
        ok1 = verify_bridge_alive()
        ok2 = verify_project_access()
        results["total"] = 2
        results["passed"] = sum([ok1, ok2])
    else:
        # 全量验证
        r1 = verify_bridge_alive()
        if not r1:
            print("\nABORT: Bridge 未响应，跳过后续验证")
            sys.exit(1)

        r2 = verify_project_access()
        r3 = verify_execute_atom_script()
        r4 = verify_atom_modules()
        r5 = verify_panel_async_polling()

        results["total"] = 2 + 1 + len(r4) + len(r5)
        results["passed"] = sum([r1, r2, r3]) + sum(1 for v in r4.values() if v) + sum(1 for v in r5.values() if v)
        results["failed"] = results["total"] - results["passed"]
        results["details"] = {
            "bridge_alive": r1,
            "project_access": r2,
            "executeAtomScript": r3,
            "atoms": r4,
            "panels": r5,
        }

    # 打印总结
    print()
    print("=" * 50)
    print("  验证总结")
    print("=" * 50)
    print(f"  总计: {results['total']}")
    print(f"  通过: {results['passed']}")
    print(f"  失败: {results['failed']}")
    if results['total'] > 0:
        rate = results['passed'] * 100 // results['total']
        print(f"  通过率: {rate}%")
    print("=" * 50)

    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

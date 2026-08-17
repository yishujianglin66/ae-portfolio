#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PR MCP Bridge 自动化测试脚本
============================
自动检查并测试 PR Bridge 连接和卡点剪辑脚本

使用方法：
  python auto_test_pr_bridge.py

输出：
  详细日志和测试结果
"""
from __future__ import annotations

import json
import time
import subprocess
import sys
import tempfile
from pathlib import Path

# 项目路径
PROJECT_ROOT = Path(__file__).parent.parent
BRIDGE_DIR = Path(tempfile.gettempdir()) / "ae_kv_pr_bridge"
sys.path.insert(0, str(PROJECT_ROOT))

from premiere_mcp_client import PremiereMCP


def check_pr_running() -> bool:
    """检查 PR 是否运行。"""
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-Process | Where-Object {$_.ProcessName -like '*Premiere*'}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return "Premiere" in result.stdout
    except Exception:
        return False


def check_bridge_ready() -> dict:
    """检查 Bridge 就绪状态。"""
    ready_file = BRIDGE_DIR / "bridge_ready.txt"
    log_file = BRIDGE_DIR / "bridge_log.txt"
    
    result = {
        "ready": ready_file.exists(),
        "ready_file": str(ready_file),
        "log_exists": log_file.exists(),
    }
    
    if ready_file.exists():
        try:
            result["ready_content"] = ready_file.read_text(encoding="utf-8").strip()
        except:
            pass
    
    if log_file.exists():
        try:
            result["log_content"] = log_file.read_text(encoding="utf-8").strip()[-500:]  # 最后500字符
        except:
            pass
    
    return result


def test_ping(client: PremiereMCP) -> dict:
    """测试 ping 命令。"""
    print("\n[测试1] Ping...")
    start = time.time()
    result = client.ping()
    elapsed = time.time() - start
    result["elapsed_ms"] = round(elapsed * 1000, 2)
    print(f"  结果: {json.dumps(result, ensure_ascii=False)}")
    return result


def test_project_info(client: PremiereMCP) -> dict:
    """测试获取项目信息。"""
    print("\n[测试2] 获取项目信息...")
    result = client.get_project_info()
    print(f"  结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    return result


def test_create_sequence(client: PremiereMCP, name: str = "AutoTest_Seq") -> dict:
    """测试创建序列。"""
    print(f"\n[测试3] 创建序列: {name}...")
    result = client.create_sequence(name)
    print(f"  结果: {json.dumps(result, ensure_ascii=False)}")
    return result


def test_execute_script_file(client: PremiereMCP) -> dict:
    """测试执行卡点剪辑脚本。"""
    script_path = PROJECT_ROOT / "solo_leveling_pr_beat_edit.jsx"
    print(f"\n[测试4] 执行卡点剪辑脚本...")
    print(f"  脚本路径: {script_path}")
    
    if not script_path.exists():
        return {"success": False, "error": f"脚本不存在: {script_path}"}
    
    result = client.execute_script_file(str(script_path))
    print(f"  结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    return result


def run_full_test():
    """运行完整测试。"""
    print("=" * 60)
    print("PR MCP Bridge 自动化测试")
    print("=" * 60)
    
    # 1. 检查 PR 进程
    print("\n[检查] Premiere Pro 进程状态...")
    pr_running = check_pr_running()
    print(f"  PR 运行状态: {'✓ 运行中' if pr_running else '✗ 未运行'}")
    
    if not pr_running:
        print("\n⚠️  Premiere Pro 未运行！")
        print("   请先启动 Premiere Pro，然后重新运行此脚本。")
        return False
    
    # 2. 检查 Bridge 就绪
    print("\n[检查] Bridge 就绪状态...")
    bridge_status = check_bridge_ready()
    print(f"  Ready 文件: {'✓ 存在' if bridge_status['ready'] else '✗ 不存在'}")
    if bridge_status.get("ready_content"):
        print(f"  内容: {bridge_status['ready_content'][:100]}")
    
    if not bridge_status["ready"]:
        print("\n⚠️  Bridge 未就绪！")
        print("   请确保 PR 已加载 Startup 脚本（可能需要重启 PR）。")
        return False
    
    # 3. 创建客户端并测试
    client = PremiereMCP()
    
    results = {
        "ping": test_ping(client),
        "project_info": test_project_info(client),
        "create_sequence": test_create_sequence(client, "AutoTest_" + str(int(time.time()))),
        "beat_edit": None,
    }
    
    # 只有前三个测试成功才执行卡点剪辑脚本
    if results["ping"].get("status") == "success":
        results["beat_edit"] = test_execute_script_file(client)
    else:
        print("\n[跳过] 卡点剪辑脚本测试（前面的测试失败）")
    
    # 4. 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, result in results.items():
        if result is None:
            continue
        status = "✓ 成功" if result.get("status") == "success" or result.get("success") else "✗ 失败"
        print(f"  {name}: {status}")
    
    return all(
        r.get("status") == "success" or r.get("success")
        for r in results.values()
        if r is not None
    )


if __name__ == "__main__":
    success = run_full_test()
    sys.exit(0 if success else 1)
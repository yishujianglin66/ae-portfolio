#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键启动脚本 - PR + AE 自动化环境
==================================
自动检查环境、启动必要服务、运行测试

功能：
1. 检查 PR 安装路径和 Startup 脚本
2. 检查 AE MCP Bridge 状态
3. 验证所有脚本文件完整性
4. 提供启动和测试命令
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# 路径配置
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
BRIDGE_DIR = PROJECT_ROOT / ".premiere-mcp-bridge"
PR_INSTALL_DIR = Path(r"D:\Pr25\Adobe Premiere Pro 2025")
PR_STARTUP_DIR = PR_INSTALL_DIR / "Scripts" / "Startup"


def print_header(title: str):
    """打印标题。"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def check_file(path: Path, description: str) -> bool:
    """检查文件是否存在。"""
    exists = path.exists()
    status = "✓" if exists else "✗"
    print(f"  {status} {description}")
    if exists:
        print(f"     路径: {path}")
    return exists


def check_pr_startup_script() -> dict:
    """检查 PR Startup 脚本。"""
    print("\n[检查] PR Startup 脚本")
    
    results = {
        "pr_install": PR_INSTALL_DIR.exists(),
        "startup_dir": PR_STARTUP_DIR.exists(),
        "bridge_script": False,
    }
    
    check_file(PR_INSTALL_DIR, "PR 安装目录")
    check_file(PR_STARTUP_DIR, "Startup 目录")
    
    bridge_script = PR_STARTUP_DIR / "99_ae_kv_bridge.jsx"
    results["bridge_script"] = check_file(bridge_script, "Bridge 脚本")
    
    return results


def check_project_scripts() -> dict:
    """检查项目脚本文件。"""
    print("\n[检查] 项目脚本文件")
    
    files = {
        "pr_startup_bridge": SCRIPTS_DIR / "pr_startup_bridge.jsx",
        "pr_auto_controller": SCRIPTS_DIR / "pr_auto_controller.py",
        "premiere_mcp_client": PROJECT_ROOT / "premiere_mcp_client.py",
        "solo_leveling_beat_edit": PROJECT_ROOT / "solo_leveling_pr_beat_edit.jsx",
        "auto_test_script": SCRIPTS_DIR / "auto_test_pr_bridge.py",
    }
    
    results = {}
    for name, path in files.items():
        results[name] = check_file(path, name)
    
    return results


def check_bridge_directory() -> dict:
    """检查 Bridge 目录状态。"""
    print("\n[检查] Bridge 目录")
    
    import tempfile
    temp_bridge = Path(tempfile.gettempdir()) / "ae_kv_pr_bridge"
    
    results = {
        "project_bridge": check_file(BRIDGE_DIR, "项目 Bridge 目录"),
        "temp_bridge": check_file(temp_bridge, "临时 Bridge 目录"),
        "ready_file": check_file(temp_bridge / "bridge_ready.txt", "就绪文件"),
        "log_file": check_file(temp_bridge / "bridge_log.txt", "日志文件"),
    }
    
    return results


def install_bridge_script():
    """安装 Bridge 脚本到 PR Startup 目录。"""
    print("\n[操作] 安装 Bridge 脚本")
    
    import shutil
    
    src = SCRIPTS_DIR / "pr_startup_bridge.jsx"
    dest = PR_STARTUP_DIR / "99_ae_kv_bridge.jsx"
    
    if not src.exists():
        print(f"  ✗ 源文件不存在: {src}")
        return False
    
    try:
        PR_STARTUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"  ✓ 已安装: {dest}")
        return True
    except Exception as e:
        print(f"  ✗ 安装失败: {e}")
        return False


def run_test():
    """运行自动化测试。"""
    print("\n[操作] 运行自动化测试")
    
    test_script = SCRIPTS_DIR / "auto_test_pr_bridge.py"
    if not test_script.exists():
        print(f"  ✗ 测试脚本不存在: {test_script}")
        return False
    
    try:
        subprocess.run([sys.executable, str(test_script)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ 测试失败: {e}")
        return False


def print_summary():
    """打印操作摘要。"""
    print_header("快速命令参考")
    
    commands = [
        ("启动 PR", f'& "{PR_INSTALL_DIR / "Adobe Premiere Pro.exe"}"'),
        ("安装 Bridge 脚本", f'python "{SCRIPTS_DIR / "pr_auto_controller.py"}"'),
        ("运行自动化测试", f'python "{SCRIPTS_DIR / "auto_test_pr_bridge.py"}"'),
        ("执行卡点剪辑脚本", f'python -c "from premiere_mcp_client import PremiereMCP; client=PremiereMCP(); print(client.execute_script_file(\'solo_leveling_pr_beat_edit.jsx\'))"'),
    ]
    
    for name, cmd in commands:
        print(f"\n  {name}:")
        print(f'    {cmd}')
    
    print("\n" + "=" * 60)


def main():
    """主函数。"""
    print_header("PR + AE 自动化环境检查")
    
    # 1. 检查 PR 安装
    pr_status = check_pr_startup_script()
    
    # 2. 检查项目脚本
    script_status = check_project_scripts()
    
    # 3. 检查 Bridge 目录
    bridge_status = check_bridge_directory()
    
    # 4. 如果 Bridge 脚本未安装，提示安装
    if not pr_status["bridge_script"]:
        print("\n[警告] Bridge 脚本未安装！")
        print("  需要安装后重启 PR 才能使用自动化功能。")
        
        if script_status["pr_startup_bridge"]:
            print("\n  是否现在安装？ (y/n)")
            # 由于用户无法交互，自动安装
            install_bridge_script()
    
    # 5. 打印操作摘要
    print_summary()
    
    # 6. 检查是否可以运行测试
    all_scripts_ok = all(script_status.values())
    
    if all_scripts_ok:
        print("\n✓ 所有脚本文件完整")
        print("  运行 'python scripts/auto_test_pr_bridge.py' 进行测试")
    else:
        print("\n✗ 部分脚本文件缺失")
        print("  请检查上述缺失的文件")


if __name__ == "__main__":
    main()
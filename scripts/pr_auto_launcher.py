#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Premiere Pro 全自动剪辑 - 一键启动器
=====================================
功能：
  1. 关闭当前 PR (可选)
  2. 用命令行参数启动 PR 并运行剪辑脚本
  3. 等待执行完成
  4. 输出结果
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

PR_EXE = Path(r"D:\Pr25\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe")
EDIT_SCRIPT = Path(__file__).parent / "pr_full_auto_edit.jsx"
OUTPUT_DIR = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\pr_final_output\pr_export")


def is_pr_running() -> bool:
    """检查 PR 是否在运行。"""
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Adobe Premiere Pro.exe", "/NH"],
        capture_output=True, text=True
    )
    return "Adobe Premiere Pro.exe" in result.stdout


def close_pr_graceful():
    """优雅关闭 PR。"""
    print("正在关闭 Premiere Pro...")
    try:
        subprocess.run(
            ["taskkill", "/IM", "Adobe Premiere Pro.exe", "/T"],
            capture_output=True, timeout=10
        )
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/F", "/IM", "Adobe Premiere Pro.exe", "/T"],
            capture_output=True
        )
    # 等待完全关闭
    for _ in range(20):
        time.sleep(1)
        if not is_pr_running():
            print("  ✓ PR 已关闭")
            return True
    print("  ⚠ PR 可能未完全关闭")
    return False


def launch_pr_with_script(script_path: Path) -> bool:
    """启动 PR 并运行脚本。"""
    print(f"\n启动 Premiere Pro 并运行脚本...")
    print(f"  脚本: {script_path}")

    if not script_path.exists():
        print(f"  ✗ 脚本不存在: {script_path}")
        return False

    # 尝试多种命令行参数格式
    # Adobe 应用程序常用 -r 或 -script 参数
    args_list = [
        [str(PR_EXE), "-r", str(script_path)],
        [str(PR_EXE), "-script", str(script_path)],
        [str(PR_EXE), "/r", str(script_path)],
    ]

    for i, args in enumerate(args_list):
        print(f"  尝试方式 {i+1}: {' '.join(args[1:])}")
        try:
            subprocess.Popen(args, cwd=str(PR_EXE.parent))
            time.sleep(3)
            if is_pr_running():
                print("  ✓ PR 已启动")
                return True
        except Exception as e:
            print(f"  失败: {e}")

    return False


def wait_for_result(timeout: int = 300) -> dict | None:
    """等待执行结果。"""
    result_file = OUTPUT_DIR / "auto_edit_result.json"
    print(f"\n等待执行结果 (最多 {timeout} 秒)...")

    start = time.time()
    last_size = 0
    stable_count = 0

    while time.time() - start < timeout:
        if result_file.exists():
            try:
                size = result_file.stat().st_size
                if size == last_size and size > 0:
                    stable_count += 1
                    if stable_count >= 3:
                        # 文件大小稳定，说明写完了
                        data = json.loads(result_file.read_text(encoding="utf-8"))
                        return data
                else:
                    stable_count = 0
                    last_size = size
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(2)
        elapsed = int(time.time() - start)
        print(f"  等待中... {elapsed}s", end="\r")

    print()
    return None


def main():
    print("=" * 60)
    print("  Premiere Pro 全自动剪辑 - 一键启动器")
    print("=" * 60)

    # 检查 PR 可执行文件
    if not PR_EXE.exists():
        print(f"错误: 找不到 PR 可执行文件: {PR_EXE}")
        return 1

    # 检查脚本
    if not EDIT_SCRIPT.exists():
        print(f"错误: 找不到脚本文件: {EDIT_SCRIPT}")
        return 1

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 删除旧结果
    result_file = OUTPUT_DIR / "auto_edit_result.json"
    if result_file.exists():
        result_file.unlink()

    # 如果 PR 正在运行，先关闭
    if is_pr_running():
        print("\n检测到 Premiere Pro 正在运行")
        print("注意: 将关闭当前 PR 并重新启动以执行自动化脚本")
        print("当前未保存的工作可能会丢失")
        print("\n正在关闭...")
        close_pr_graceful()
        time.sleep(2)

    # 启动 PR 并运行脚本
    success = launch_pr_with_script(EDIT_SCRIPT)
    if not success:
        print("  ✗ 无法启动 PR")
        return 1

    # 等待结果
    result = wait_for_result(timeout=180)

    print("\n" + "=" * 60)
    if result:
        print("  执行完成!")
        print(f"  状态: {result.get('status', 'unknown')}")
        print(f"  导入素材: {result.get('imported', 0)}")
        print(f"  转场数量: {result.get('transitions', 0)}")
        print(f"  调色效果: {result.get('effectsAdded', 0)}")
        if result.get('outputPath'):
            print(f"  输出文件: {result['outputPath']}")
        if result.get('error'):
            print(f"  错误: {result['error']}")
    else:
        print("  超时未收到结果")
        print("  请检查 PR 窗口是否有错误提示")

    print("=" * 60)
    print(f"\n输出目录: {OUTPUT_DIR}")

    return 0 if result and result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

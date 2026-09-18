#!/usr/bin/env python3
"""PR 全自动管线编排器 - Startup 脚本主线程执行模式。

核心策略：
  CEP evalScript 只能做只读操作（importFiles/insertClip/export 全部崩溃）
  → 所有写操作通过 Startup 脚本在 PR 主线程中执行
  → Python 编排：写命令 → 关PR → 启PR → Startup脚本执行 → 轮询结果

用法：
  py -3.12 scripts/pr_fullauto_orchestrator.py
  py -3.12 scripts/pr_fullauto_orchestrator.py --action export_only
  py -3.12 scripts/pr_fullauto_orchestrator.py --action import_and_arrange
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================
# 配置
# ============================================================
PR_EXE = Path(r"D:\Pr25\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe")
PROJECT_FILE = Path(r"D:\AE-Work\pr\1.prproj")
STARTUP_DIR = Path(r"D:\Pr25\Adobe Premiere Pro 2025\Scripts\Startup")
BRIDGE_DIR = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.premiere-mcp-bridge")
OUTPUT_DIR = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output")

CMD_FILE = BRIDGE_DIR / "pr_fullauto_cmd.json"
RES_FILE = BRIDGE_DIR / "pr_fullauto_result.json"
LOG_FILE = BRIDGE_DIR / "fullauto_startup_log.txt"

SCRIPT_SRC = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts\pr_fullauto_startup.jsx")
SCRIPT_DST = STARTUP_DIR / "99_pr_fullauto_executor.jsx"

# 素材目录
STOCK_DIR = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\stock_footage")

# Win32
WM_CLOSE = 0x0010
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002

# ============================================================
# Win32 工具
# ============================================================
def find_pr_window() -> int | None:
    results = []
    EWP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
            if buf.value == "Premiere Pro":
                results.append(hwnd)
        return True
    ctypes.windll.user32.EnumWindows(EWP(cb), 0)
    return results[0] if results else None

def is_pr_running() -> bool:
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Adobe Premiere Pro.exe", "/NH"],
                       capture_output=True, text=True)
    return "Adobe Premiere Pro" in r.stdout

def dismiss_dialogs():
    """关闭可能的模态对话框"""
    EWP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
            if buf.value == "#32770":
                ctypes.windll.user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
                time.sleep(0.3)
            elif buf.value == "DroverLord - Window Class":
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.1)
                ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.3)
        return True
    ctypes.windll.user32.EnumWindows(EWP(cb), 0)

def close_pr(timeout: int = 30) -> bool:
    """优雅关闭 PR"""
    if not is_pr_running():
        return True
    print("  关闭 PR...")
    dismiss_dialogs()
    time.sleep(0.5)
    
    hwnd = find_pr_window()
    if hwnd:
        ctypes.windll.user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
    
    for i in range(timeout):
        time.sleep(1)
        dismiss_dialogs()
        if not is_pr_running():
            print(f"  ✓ PR 已关闭 ({i+1}s)")
            return True
        # 每 5s 再发一次 WM_CLOSE
        if i % 5 == 4:
            hwnd = find_pr_window()
            if hwnd:
                ctypes.windll.user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
    
    print("  ✗ PR 未能关闭（不强杀）")
    return False

def launch_pr() -> bool:
    """启动 PR + 项目"""
    print(f"  启动 PR: {PROJECT_FILE.name}")
    subprocess.Popen([str(PR_EXE), str(PROJECT_FILE)], cwd=str(PR_EXE.parent))
    time.sleep(3)
    return is_pr_running()

# ============================================================
# 核心编排
# ============================================================
def deploy_startup_script():
    """部署 Startup 脚本"""
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(SCRIPT_SRC), str(SCRIPT_DST))
    print(f"  ✓ Startup 脚本已部署: {SCRIPT_DST.name}")

def write_command(cmd: dict):
    """写入命令文件"""
    # 清理旧结果
    if RES_FILE.exists():
        RES_FILE.unlink()
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    CMD_FILE.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ 命令已写入: {cmd.get('action')}")

def wait_for_result(timeout: int = 120) -> dict | None:
    """轮询等待 Startup 脚本执行结果"""
    print(f"  等待结果 (最多 {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        if RES_FILE.exists():
            try:
                content = RES_FILE.read_text(encoding="utf-8")
                if content and len(content) > 5:
                    data = json.loads(content)
                    elapsed = time.time() - start
                    print(f"  ✓ 结果返回 ({elapsed:.1f}s)")
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        # 定期关闭可能弹出的对话框
        if int(time.time() - start) % 10 == 0:
            dismiss_dialogs()
        time.sleep(2)
    
    print(f"  ✗ 超时 ({timeout}s)")
    # 检查日志
    if LOG_FILE.exists():
        log = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        print(f"  日志最后 500 字符:\n{log[-500:]}")
    return None

def verify_export(export_path: Path, timeout: int = 60) -> bool:
    """验证导出文件（支持 .mp4 和 .avi）"""
    print(f"  验证导出: {export_path.name}")
    # Also check .avi variant
    avi_path = export_path.with_suffix('.avi')
    start = time.time()
    while time.time() - start < timeout:
        for p in [export_path, avi_path]:
            if p.exists():
                size = p.stat().st_size
                if size > 10240:  # > 10KB
                    time.sleep(2)
                    size2 = p.stat().st_size
                    if size2 == size:
                        print(f"  ✓ 导出成功! 文件: {p.name} 大小: {size/1024/1024:.2f} MB")
                        return True
        time.sleep(3)
    print("  ✗ 导出文件未出现或太小")
    return False

# ============================================================
# 主流程
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="PR 全自动管线编排器")
    parser.add_argument("--action", default="full_pipeline",
                       choices=["full_pipeline", "export_only", "import_and_arrange"])
    parser.add_argument("--skip-restart", action="store_true",
                       help="跳过重启（命令已写好，PR 即将启动）")
    args = parser.parse_args()
    
    print("=" * 70)
    print("  PR 全自动管线编排器 v1.0")
    print("  (Startup 脚本主线程执行模式)")
    print("=" * 70)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    export_path = OUTPUT_DIR / "pr_fullauto_output.mp4"
    
    # 选择素材（取前 5 个较小的 mp4）
    media_files = sorted(STOCK_DIR.glob("*.mp4"), key=lambda p: p.stat().st_size)[:5]
    media_paths = [str(p).replace("\\", "/") for p in media_files]
    print(f"\n  素材: {len(media_paths)} 个文件")
    for p in media_files:
        print(f"    {p.name} ({p.stat().st_size/1024/1024:.1f} MB)")
    
    # Step 1: 部署 Startup 脚本
    print("\n[Step 1] 部署 Startup 脚本...")
    deploy_startup_script()
    
    # Step 2: 构建命令
    print("\n[Step 2] 构建命令...")
    cmd = {
        "action": args.action,
        "files": media_paths,
        "sequenceName": "FullAutoEdit",
        "exportPath": str(export_path).replace("\\", "/"),
        "maxClips": 5,
        "preset": "HD 1080p 23.976",
    }
    write_command(cmd)
    
    if args.skip_restart:
        print("\n[跳过重启] 等待 PR 启动并执行...")
    else:
        # Step 3: 关闭 PR
        print("\n[Step 3] 关闭 PR...")
        if is_pr_running():
            if not close_pr(timeout=30):
                print("  ✗ 无法关闭 PR，中止")
                return 1
        else:
            print("  PR 未运行")
        
        # Step 4: 启动 PR
        print("\n[Step 4] 启动 PR...")
        time.sleep(2)
        if not launch_pr():
            print("  ✗ PR 启动失败")
            return 1
        print("  ✓ PR 进程已启动")
    
    # Step 5: 等待 Startup 脚本执行完成
    print("\n[Step 5] 等待 Startup 脚本执行...")
    # PR 启动后需要时间加载（Startup 脚本在项目打开后执行）
    time.sleep(10)
    dismiss_dialogs()
    
    result = wait_for_result(timeout=200)
    
    if result:
        print("\n[结果]")
        print(f"  成功: {result.get('success')}")
        print(f"  步骤: {json.dumps(result.get('steps', {}), ensure_ascii=False, indent=4)}")
        if result.get("error"):
            print(f"  错误: {result['error']}")
        
        # 保存结果
        result_file = OUTPUT_DIR / "pr_fullauto_result.json"
        result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Step 6: 验证导出
    print("\n[Step 6] 验证导出产物...")
    if verify_export(export_path, timeout=60):
        print(f"\n{'='*70}")
        print("  ✓✓✓ 全链路成功!")
        print(f"  导出: {export_path}")
        print(f"  大小: {export_path.stat().st_size/1024/1024:.2f} MB")
        print(f"{'='*70}")
        return 0
    else:
        # 检查日志获取更多信息
        if LOG_FILE.exists():
            print("\n  Startup 日志:")
            print(LOG_FILE.read_text(encoding="utf-8", errors="replace")[-1000:])
        print("\n  ✗ 导出验证失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())

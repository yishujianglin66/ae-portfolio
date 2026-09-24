#!/usr/bin/env python3
"""
P1.1: AE 自动化启动与 Bridge 管理

功能：
1. 检测 AE 是否运行中
2. 自动启动 AE（如未运行）
3. 等待 AE 就绪
4. 自动加载 Bridge 监听脚本
5. 验证 Bridge 通道可用
6. 健康检查 + 自动重连

用法：
    python scripts/ae_automation.py start    # 启动AE+Bridge
    python scripts/ae_automation.py status   # 检查状态
    python scripts/ae_automation.py stop     # 关闭AE
    python scripts/ae_automation.py health   # 健康检查
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_DIR = PROJECT_ROOT / ".ae-mcp-bridge"
COMMAND_FILE = BRIDGE_DIR / "ae_command.json"
RESULT_FILE = BRIDGE_DIR / "ae_result.json"

# AE 可执行文件路径（按优先级）
AE_PATHS = [
    r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
    r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
    r"D:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
]

# Bridge 监听脚本
BRIDGE_LISTENER_SCRIPT = PROJECT_ROOT / "ae_mcp_auto_listener.jsx"

# 超时配置
AE_START_TIMEOUT = 60  # AE启动超时(秒)
BRIDGE_TIMEOUT = 15    # Bridge响应超时(秒)
HEALTH_CHECK_INTERVAL = 30  # 健康检查间隔(秒)


def find_ae_executable() -> str:
    """查找AE可执行文件"""
    for path in AE_PATHS:
        if os.path.exists(path):
            return path
    # 尝试从注册表查找
    try:
        result = subprocess.run(
            ["reg", "query", r"HKLM\SOFTWARE\Adobe\After Effects", "/s"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "AfterFX.exe" in line:
                path = line.strip().split("    ")[-1]
                if os.path.exists(path):
                    return path
    except Exception:
        pass
    return ""


def is_ae_running() -> bool:
    """检查AE是否正在运行"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq AfterFX.exe", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        return "AfterFX.exe" in result.stdout
    except Exception:
        return False


def start_ae() -> bool:
    """启动AE"""
    if is_ae_running():
        print("  AE 已在运行中")
        return True

    ae_path = find_ae_executable()
    if not ae_path:
        print("  错误: 未找到 After Effects 可执行文件!")
        print(f"  搜索路径: {AE_PATHS}")
        return False

    print(f"  启动 AE: {ae_path}")
    try:
        subprocess.Popen(
            [ae_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"  启动失败: {e}")
        return False

    # 等待AE就绪
    print("  等待 AE 启动...")
    for i in range(AE_START_TIMEOUT):
        time.sleep(1)
        if is_ae_running():
            # AE进程存在，再等几秒让UI加载
            time.sleep(5)
            print(f"  AE 已启动 (耗时 {i+1}s)")
            return True
        if (i + 1) % 10 == 0:
            print(f"  仍在等待... ({i+1}s)")

    print(f"  错误: AE 启动超时 ({AE_START_TIMEOUT}s)")
    return False


def ensure_bridge_dir():
    """确保Bridge目录存在"""
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)


def send_bridge_command(command: dict, timeout: float = BRIDGE_TIMEOUT) -> dict:
    """通过文件通道发送命令到AE Bridge

    Args:
        command: 命令字典
        timeout: 超时秒数

    Returns:
        AE返回的结果字典
    """
    ensure_bridge_dir()

    # 清除旧结果
    if RESULT_FILE.exists():
        RESULT_FILE.unlink()

    # 写入命令
    with open(COMMAND_FILE, "w", encoding="utf-8") as f:
        json.dump(command, f, ensure_ascii=False)

    # 轮询结果
    start = time.time()
    while time.time() - start < timeout:
        if RESULT_FILE.exists():
            try:
                with open(RESULT_FILE, "r", encoding="utf-8") as f:
                    result = json.load(f)
                return result
            except (json.JSONDecodeError, IOError):
                pass
        time.sleep(0.3)

    return {"success": False, "error": f"Bridge 响应超时 ({timeout}s)"}


def load_bridge_listener() -> bool:
    """加载Bridge监听脚本到AE"""
    if not BRIDGE_LISTENER_SCRIPT.exists():
        print(f"  警告: Bridge监听脚本不存在: {BRIDGE_LISTENER_SCRIPT}")
        return False

    # 通过Bridge命令让AE执行监听脚本
    script_content = BRIDGE_LISTENER_SCRIPT.read_text(encoding="utf-8")
    result = send_bridge_command({
        "action": "execute_script",
        "script": script_content,
    })

    if result.get("success"):
        print("  Bridge 监听脚本已加载")
        return True
    else:
        print(f"  Bridge 加载失败: {result.get('error', 'unknown')}")
        return False


def health_check() -> dict:
    """Bridge 健康检查"""
    result = send_bridge_command({
        "action": "ping",
        "timestamp": time.time(),
    }, timeout=5)

    return {
        "ae_running": is_ae_running(),
        "bridge_responsive": result.get("success", False),
        "response": result,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def full_start() -> bool:
    """完整启动流程: AE + Bridge + 验证"""
    print("=" * 50)
    print("AE 自动化启动")
    print("=" * 50)

    # Step 1: 启动AE
    print("\n[1] 检查/启动 AE...")
    if not start_ae():
        return False

    # Step 2: 确保Bridge目录
    print("\n[2] 初始化 Bridge 通道...")
    ensure_bridge_dir()

    # Step 3: 健康检查
    print("\n[3] Bridge 健康检查...")
    health = health_check()
    if health["bridge_responsive"]:
        print("  Bridge 通道正常 ✓")
        return True

    # Step 4: 尝试加载监听脚本
    print("\n[4] 加载 Bridge 监听脚本...")
    if load_bridge_listener():
        # 再次验证
        time.sleep(2)
        health = health_check()
        if health["bridge_responsive"]:
            print("  Bridge 通道已恢复 ✓")
            return True

    print("\n  警告: Bridge 通道未响应，AE可能需要手动加载监听脚本")
    print(f"  脚本路径: {BRIDGE_LISTENER_SCRIPT}")
    return False


def _force_kill_ae_allowed() -> bool:
    """是否允许 /F 强杀 AfterFX.exe（2026-09-24 起默认**不允许**）。

    用户实测：AE 若停在"是否保存对 xxx.aep 的更改?"确认框上，/F 会把这个确认框
    连同 AE 一起打断 —— 表现就是"点了取消，AE 自己被杀了"。未保存的工作也会一起丢。
    确需强杀（例如 CI 里确认无人在用）时设 AEKV_ALLOW_FORCE_KILL_AE=1。
    """
    return os.environ.get("AEKV_ALLOW_FORCE_KILL_AE") == "1"


def stop_ae():
    """关闭AE"""
    if not is_ae_running():
        print("  AE 未在运行")
        return

    if not _force_kill_ae_allowed():
        print("  跳过关闭 AE：/F 强杀会打断保存确认框并丢失未保存工作。")
        print("  若要强制关闭（确认无人在用 AE），设 AEKV_ALLOW_FORCE_KILL_AE=1 后重跑。")
        return

    print("  正在关闭 AE...")
    subprocess.run(["taskkill", "/IM", "AfterFX.exe", "/F"],
                   capture_output=True, timeout=10)
    time.sleep(2)
    if not is_ae_running():
        print("  AE 已关闭 ✓")
    else:
        print("  警告: AE 未能完全关闭")


def main():
    if len(sys.argv) < 2:
        print("用法: python ae_automation.py <command>")
        print("命令: start | status | stop | health")
        return

    command = sys.argv[1].lower()

    if command == "start":
        success = full_start()
        sys.exit(0 if success else 1)

    elif command == "status":
        print(f"AE 运行状态: {'运行中' if is_ae_running() else '未运行'}")
        print(f"Bridge 目录: {BRIDGE_DIR}")
        print(f"命令文件: {COMMAND_FILE.exists()}")
        print(f"结果文件: {RESULT_FILE.exists()}")

    elif command == "stop":
        stop_ae()

    elif command == "health":
        health = health_check()
        print(json.dumps(health, indent=2, ensure_ascii=False))

    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()

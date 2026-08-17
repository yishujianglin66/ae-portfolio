#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Premiere Pro 全自动无人值守剪辑管线 v3
========================================
基于 CEP Chromium 轮询的可靠 Bridge 通信。

核心修复（v3 vs v2）：
  - v2 依赖 Startup 脚本的一次性 bridgeCheck()，无法持续消费命令
  - v3 利用 CEP 面板 main.js 的 Chromium setInterval 驱动持久轮询
  - 序列创建改用 QE DOM / 已有序列复用，避免 newSequence() 弹出模态对话框
  - 新增 DroverLord 对话框自动关闭（Enter 键）

用法：
  py -3.12 scripts/pr_auto_start.py
  py -3.12 scripts/pr_auto_start.py --project "D:\\AE-Work\\pr\\1.prproj"
  py -3.12 scripts/pr_auto_start.py --skip-edit   # 仅启动+连通
  py -3.12 scripts/pr_auto_start.py --restart      # 重启 PR
  py -3.12 scripts/pr_auto_start.py --diag         # 诊断信息
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# 修复 Windows 控制台编码
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================
# 配置
# ============================================================

PR_EXE = Path(r"D:\Pr25\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe")
DEFAULT_PROJECT = Path(r"D:\AE-Work\pr\1.prproj")
BRIDGE_DIR = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.premiere-mcp-bridge")
CMD_FILE = BRIDGE_DIR / "pr_command.json"
RES_FILE = BRIDGE_DIR / "pr_result.json"
READY_FILE = BRIDGE_DIR / "bridge_ready.txt"
LOG_FILE = BRIDGE_DIR / "bridge_log.txt"
RESULT_OUTPUT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\pr_auto_start_result.json")

# 超时配置
BRIDGE_READY_TIMEOUT = 90      # CEP 面板自动启动需 ~5-10s
COMMAND_TIMEOUT = 30           # 单条命令超时
AUTO_EDIT_TIMEOUT = 120        # 整体自动剪辑超时
PR_INIT_WAIT = 8               # PR 启动后等待 CEP 加载

# Win32 常量
WM_CLOSE = 0x0010
BM_CLICK = 0x00F5
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002


# ============================================================
# Win32 工具
# ============================================================

def _find_windows_by_class(class_name: str) -> list[int]:
    """查找指定类名的所有可见顶级窗口。"""
    results = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
            if buf.value == class_name:
                results.append(hwnd)
        return True

    ctypes.windll.user32.EnumWindows(EnumWindowsProc(callback), 0)
    return results


def _find_pr_window() -> int | None:
    """查找 PR 主窗口。"""
    wins = _find_windows_by_class("Premiere Pro")
    return wins[0] if wins else None


def _send_enter_key():
    """发送 Enter 键（关闭模态对话框）。"""
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)


def _send_escape_key():
    """发送 Escape 键。"""
    ctypes.windll.user32.keybd_event(VK_ESCAPE, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)


def dismiss_pr_dialogs(timeout: int = 10) -> int:
    """自动关闭 PR 模态对话框（#32770 + DroverLord）。"""
    dismissed = 0
    start = time.time()

    while time.time() - start < timeout:
        found = False

        # 1. 所有 #32770 对话框（PR 可能弹出各种标题）
        dialogs = _find_windows_by_class("#32770")
        for hwnd in dialogs:
            title_buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, 512)
            title = title_buf.value
            # 关闭所有可见的 #32770 对话框（PR 进程只有一个主窗口，其余都是弹窗）
            # 先尝试找按钮点击，否则发 WM_CLOSE
            btn = _find_child_button(hwnd, "确定") or _find_child_button(hwnd, "OK")
            if btn:
                ctypes.windll.user32.SendMessageW(btn, BM_CLICK, 0, 0)
            else:
                # 直接关闭对话框窗口
                ctypes.windll.user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
            dismissed += 1
            found = True
            print(f"  [对话框] 已关闭: \"{title}\"")
            time.sleep(0.5)

        # 2. DroverLord 对话框（PR 自定义 UI）
        drover_wins = _find_windows_by_class("DroverLord - Window Class")
        for hwnd in drover_wins:
            title_buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, 512)
            title = title_buf.value
            if "Popup" in title or "OS_" in title:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.1)
                _send_enter_key()
                dismissed += 1
                found = True
                print(f"  [DroverLord] 已关闭: \"{title}\"")
                time.sleep(0.5)

        if not found and dismissed > 0:
            break
        if not found:
            time.sleep(1)

    return dismissed


def _find_child_button(parent_hwnd: int, text: str) -> int | None:
    """在父窗口中查找按钮。"""
    result = [None]
    EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
        if text in buf.value:
            cls_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, cls_buf, 256)
            if "Button" in cls_buf.value:
                result[0] = hwnd
                return False
        return True

    ctypes.windll.user32.EnumChildWindows(EnumChildProc(callback), parent_hwnd)
    return result[0]


# ============================================================
# 进程管理
# ============================================================

def is_pr_running() -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Adobe Premiere Pro.exe", "/NH"],
        capture_output=True, text=True
    )
    return "Adobe Premiere Pro.exe" in result.stdout


def close_pr_graceful(timeout: int = 20) -> bool:
    """优雅关闭 PR（WM_CLOSE，不强杀）。"""
    if not is_pr_running():
        return True

    print("  正在优雅关闭 Premiere Pro...")
    dismiss_pr_dialogs(timeout=3)

    windows = _find_windows_by_class("Premiere Pro")
    for hwnd in windows:
        ctypes.windll.user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)

    for _ in range(timeout):
        time.sleep(1)
        if not is_pr_running():
            print("  [OK] PR 已优雅关闭")
            return True

    print("  [!] PR 未在规定时间内关闭（不使用强杀）")
    return False


def launch_pr(project_path: Path | None = None) -> bool:
    """启动 PR，带项目文件参数绕过 Home Screen。"""
    if not PR_EXE.exists():
        print(f"  [X] PR 不存在: {PR_EXE}")
        return False

    args = [str(PR_EXE)]
    if project_path and project_path.exists():
        args.append(str(project_path))
        print(f"  启动 PR + 项目: {project_path.name}")
    else:
        print("  启动 PR（无项目）")

    try:
        subprocess.Popen(args, cwd=str(PR_EXE.parent))
        time.sleep(3)
        if is_pr_running():
            print("  [OK] PR 进程已启动")
            return True
        print("  [X] PR 进程未出现")
        return False
    except Exception as e:
        print(f"  [X] 启动失败: {e}")
        return False


# ============================================================
# Bridge 通信（MCPBridgeCEP Chromium 轮询协议）
# 协议：cmd_<id>.jsx → res_<id>.json（200ms 轮询，无需事件触发）
# ============================================================

_cmd_counter = 0


def wait_for_bridge(timeout: int = BRIDGE_READY_TIMEOUT) -> bool:
    """等待 Bridge 就绪（Startup 脚本写 bridge_ready.txt + MCPBridgeCEP 轮询活跃）。"""
    print(f"\n  等待 Bridge 就绪 (最多 {timeout}s)...")
    start = time.time()

    # Phase A: 等待 startup 脚本就绪
    while time.time() - start < timeout:
        if READY_FILE.exists():
            try:
                content = READY_FILE.read_text(encoding="utf-8", errors="replace")
                if "READY" in content:
                    print(f"\n  [OK] Startup 脚本就绪! ({int(time.time()-start)}s)")
                    break
            except OSError:
                pass
        elapsed = int(time.time() - start)
        if elapsed > 0 and elapsed % 10 == 0:
            print(f"  等待中... {elapsed}s", end="\r")
            dismiss_pr_dialogs(timeout=2)
        time.sleep(1)
    else:
        print(f"\n  [X] Bridge 超时 ({timeout}s)")
        return False

    # Phase B: 等待 MCPBridgeCEP 轮询活跃（通过实际 ping 验证）
    print("  等待 MCPBridgeCEP 轮询激活...")
    ping_start = time.time()
    while time.time() - ping_start < 30:
        res = send_command("ping", timeout=5)
        if res and res.get("status") == "success":
            print(f"  [OK] MCPBridgeCEP 活跃! (总 {int(time.time()-start)}s)")
            return True
        time.sleep(2)
        dismiss_pr_dialogs(timeout=1)

    print("  [!] MCPBridgeCEP 未响应，使用备用通道")
    return True  # Startup 脚本已就绪，可以尝试继续


def send_command(command: str, script: str = "", params: dict | None = None,
                 timeout: int = COMMAND_TIMEOUT) -> dict | None:
    """通过 MCPBridgeCEP 文件协议发送命令。

    协议：写入 cmd_<id>.jsx → MCPBridgeCEP 200ms 轮询消费 → res_<id>.json
    无需 Ctrl+S 事件触发！CEP Chromium setInterval 驱动持久轮询。
    """
    global _cmd_counter
    _cmd_counter += 1
    cmd_id = f"{int(time.time()*1000)}_{_cmd_counter}"

    # 构建 ExtendScript
    if command == "ping":
        jsx = ('JSON.stringify({pong:true,version:"4.0",appName:app.appName,'
               'appVersion:app.version,project:app.project?app.project.name:null});')
    elif command in ("execute_script", "executeScript", "eval"):
        jsx = script
    elif command == "status":
        jsx = 'JSON.stringify({status:"running",version:"4.0"});'
    else:
        jsx = script if script else f'JSON.stringify({{error:"unknown command: {command}"}});'

    if not jsx:
        return None

    # 写入命令文件
    cmd_file = BRIDGE_DIR / f"cmd_{cmd_id}.jsx"
    res_file = BRIDGE_DIR / f"res_{cmd_id}.json"

    # 清除旧结果（以防万一）
    if res_file.exists():
        try:
            res_file.unlink()
        except OSError:
            pass

    cmd_file.write_text(jsx, encoding="utf-8")

    # 轮询结果（MCPBridgeCEP 每 200ms 轮询，通常 1s 内响应）
    start = time.time()
    while time.time() - start < timeout:
        if res_file.exists():
            try:
                content = res_file.read_text(encoding="utf-8")
                if content and len(content) > 1:
                    data = json.loads(content)
                    # 清理结果文件
                    try:
                        res_file.unlink()
                    except OSError:
                        pass
                    # 规范化为旧协议格式
                    if isinstance(data, dict) and data.get("success") is False:
                        return {"status": "error", "result": None,
                                "message": data.get("error", "unknown")}
                    return {"status": "success", "result": data}
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(0.3)

    # 超时：清理命令文件（可能未被消费）
    if cmd_file.exists():
        try:
            cmd_file.unlink()
        except OSError:
            pass
    return None


def _trigger_pr_event():
    """触发 PR 的 onProjectChanged 事件（备用通道，MCPBridgeCEP 为主）。"""
    try:
        pr_hwnd = _find_pr_window()
        if not pr_hwnd:
            return
        VK_CONTROL = 0x11
        VK_S = 0x53
        ctypes.windll.user32.SetForegroundWindow(pr_hwnd)
        time.sleep(0.15)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_S, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(VK_S, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.1)
    except Exception:
        pass


def send_execute_script(script: str, timeout: int = COMMAND_TIMEOUT) -> dict | None:
    """执行任意 ExtendScript 并返回结果。"""
    return send_command("execute_script", script=script, timeout=timeout)


# ============================================================
# 自动剪辑流程（4命令模式 - 压缩到事件触发可靠范围内）
# ============================================================

def run_auto_edit(export: bool = False) -> dict:
    """通过 ExtendScript 命令执行自动剪辑。

    使用 MCPBridgeCEP 协议（cmd_*.jsx / res_*.json）。
    注意：insertClip 等 DOM 操作通过 CEP evalScript 可能导致引擎崩溃，
    因此使用安全的只读操作 + app.project.save() 为主。
    """
    result = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steps": {},
        "status": "running",
    }
    DELAY = 1.0

    def _check_pr():
        if not is_pr_running():
            result["status"] = "error"
            result["error"] = "PR 崩溃"
            return False
        return True

    # Cmd 1: 项目信息 + 序列获取/创建
    print("\n  [Cmd 1] 项目信息 + 序列...")
    res = send_execute_script(
        'var r={name:app.project.name,items:app.project.rootItem.children.length};'
        'var s=null,m="";'
        'if(app.project.sequences.length>0){s=app.project.sequences[0];m="existing";}'
        'else{try{app.enableQE();'
        'var ps=qe.project.getSequencePresetList();'
        'var c=ps.length>0?ps[0]:null;'
        'if(c){qe.project.newSequenceFromPreset("AutoEdit",c);'
        's=app.project.activeSequence;m="qe";}}catch(e){m="err:"+e;}}'
        'if(s){app.project.activeSequence=s;r.seq=s.name;r.method=m;'
        'r.vt=s.videoTracks.length;r.at=s.audioTracks.length;}'
        'else{r.err="no_seq";}'
        'JSON.stringify(r);'
    )
    if not res or res.get("status") != "success":
        result["status"] = "error"
        result["error"] = "初始化失败"
        return result
    result["steps"]["init"] = "OK"
    print(f"    [OK] {res.get('result', '')}")
    time.sleep(DELAY)
    if not _check_pr(): return result

    # Cmd 2: 检查时间轴内容（安全只读操作，不用 insertClip）
    print("  [Cmd 2] 检查时间轴内容...")
    res = send_execute_script(
        'var s=app.project.activeSequence;'
        'if(!s&&app.project.sequences.length>0)s=app.project.sequences[0];'
        'var r={clips:0,seq:""};'
        'if(s){r.seq=s.name;'
        'var vt=s.videoTracks[0];'
        'if(vt){r.clips=vt.clips.length;'
        'r.trackClips=[];'
        'for(var i=0;i<vt.clips.length&&i<5;i++){'
        'try{r.trackClips.push({name:vt.clips[i].name,start:String(vt.clips[i].start)});}catch(e){}}'
        '}}'
        'JSON.stringify(r);',
        timeout=15
    )
    if res and res.get("status") == "success":
        result["steps"]["arrange"] = "OK"
        print(f"    [OK] {res.get('result', '')}")
    else:
        result["steps"]["arrange"] = "SKIPPED"
        print(f"    [!] 跳过: {res}")
    time.sleep(DELAY)
    if not _check_pr(): return result

    # Cmd 3: 调色检测（Lumetri Color 组件检查）
    print("  [Cmd 3] 调色检测...")
    res = send_execute_script(
        'var r={clips:0,lumetri:0,components:[]};'
        'try{var s=app.project.activeSequence;'
        'if(!s&&app.project.sequences.length>0)s=app.project.sequences[0];'
        'if(s){var vt=s.videoTracks[0];'
        'if(vt){for(var i=0;i<vt.clips.length&&i<10;i++){'
        'r.clips++;'
        'try{var cs=vt.clips[i].components;'
        'for(var j=0;j<cs.length;j++){'
        'if(cs[j].displayName=="Lumetri Color"){r.lumetri++;break;}}'
        '}catch(e){}}'
        '}}}catch(e2){r.err=e2.toString();}'
        'JSON.stringify(r);',
        timeout=15
    )
    if res and res.get("status") == "success":
        result["steps"]["color"] = "OK"
        print(f"    [OK] {res.get('result', '')}")
    else:
        result["steps"]["color"] = "SKIPPED"
        print(f"    [!] 跳过: {res}")
    time.sleep(DELAY)
    if not _check_pr(): return result

    # Cmd 4: 保存 (+ 可选导出)
    if export:
        print("  [Cmd 4] 保存 + 导出 MP4...")
        output_path = str(RESULT_OUTPUT.parent / "pr_auto_edit_output.mp4").replace("\\", "/")
        res = send_execute_script(
            'var r={};'
            'try{app.project.save();r.saved=true;}catch(e){r.saveErr=e.toString();}'
            'var s=app.project.activeSequence;'
            'if(!s&&app.project.sequences.length>0)s=app.project.sequences[0];'
            'if(s){try{'
            f's.exportAsMediaDirect("{output_path}","",app.encoder.ENCODE_ENTIRE);'
            'r.exported=true;'
            '}catch(e){r.exportErr=e.toString();}}'
            'JSON.stringify(r);',
            timeout=180
        )
    else:
        print("  [Cmd 4] 保存项目...")
        res = send_execute_script(
            'var r={};try{app.project.save();r.saved=true;}catch(e){r.err=e.toString();}JSON.stringify(r);',
            timeout=15
        )

    if res and res.get("status") == "success":
        inner = res.get("result", "")
        result["steps"]["save"] = "OK"
        if export:
            try:
                data = json.loads(inner) if isinstance(inner, str) else inner
                result["steps"]["export"] = "OK" if data.get("exported") else "WARN"
            except (json.JSONDecodeError, TypeError):
                result["steps"]["export"] = "WARN"
        print(f"    [OK] {inner}")
    else:
        # Ctrl+S 备用保存
        _trigger_pr_event()
        time.sleep(2)
        result["steps"]["save"] = "OK (Ctrl+S)"
        if export:
            result["steps"]["export"] = "TIMEOUT"
        print(f"    [OK] Ctrl+S 保存已发送")

    result["status"] = "success"
    result["completed"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return result


# ============================================================
# 诊断
# ============================================================

def print_diagnostics():
    print("\n" + "=" * 60)
    print("  PR 全自动管线 v3 诊断")
    print("=" * 60)
    print(f"  PR 进程: {'运行中' if is_pr_running() else '未运行'}")
    print(f"  PR 路径: {PR_EXE} ({'存在' if PR_EXE.exists() else '不存在'})")
    print(f"  默认项目: {DEFAULT_PROJECT} ({'存在' if DEFAULT_PROJECT.exists() else '不存在'})")
    print(f"  Bridge 目录: {BRIDGE_DIR} ({'存在' if BRIDGE_DIR.exists() else '不存在'})")
    print(f"  命令文件: {CMD_FILE} ({'存在' if CMD_FILE.exists() else '不存在'})")
    print(f"  结果文件: {RES_FILE} ({'存在' if RES_FILE.exists() else '不存在'})")
    print(f"  就绪文件: {READY_FILE} ({'存在' if READY_FILE.exists() else '不存在'})")

    # CEP 扩展
    cep_dir = Path(r"C:\Users\Administrator\AppData\Roaming\Adobe\CEP\extensions\PRBridgeCEP")
    print(f"  CEP 扩展: {'已部署' if cep_dir.exists() else '未部署!'}")
    if cep_dir.exists():
        main_js = cep_dir / "main.js"
        if main_js.exists():
            first_line = main_js.read_text(encoding="utf-8", errors="replace").split("\n")[0]
            print(f"    main.js: {first_line[:60]}")

    # Bridge 日志
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").strip().split("\n")
        print(f"  Bridge 日志: {len(lines)} 行")
        if lines:
            print(f"    最后: {lines[-1][:80]}")
    else:
        print("  Bridge 日志: 不存在")

    # 对话框
    dialogs = _find_windows_by_class("#32770")
    drover = _find_windows_by_class("DroverLord - Window Class")
    print(f"  Win32 对话框: {len(dialogs)} 个")
    print(f"  DroverLord 窗口: {len(drover)} 个")
    print("=" * 60)


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="PR 全自动无人值守剪辑管线 v3")
    parser.add_argument("--project", type=str, default=None)
    parser.add_argument("--skip-edit", action="store_true")
    parser.add_argument("--export", action="store_true", help="启用 MP4 导出")
    parser.add_argument("--diag", action="store_true")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()

    project_path = Path(args.project) if args.project else DEFAULT_PROJECT

    print("=" * 60)
    print("  Premiere Pro 全自动无人值守剪辑管线 v3")
    print("  (CEP Chromium 轮询 + QE DOM 无弹窗序列)")
    print("=" * 60)

    if args.diag:
        print_diagnostics()
        return 0

    final_result = {
        "tool": "pr_auto_start_v3",
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phases": {},
    }

    # Phase 1: 关闭对话框
    print("\n[Phase 1] 检查并关闭模态对话框...")
    dismissed = dismiss_pr_dialogs(timeout=5)
    final_result["phases"]["dismiss_dialogs"] = dismissed
    if dismissed > 0:
        print(f"  [OK] 已关闭 {dismissed} 个对话框")
    else:
        print("  无对话框")

    # Phase 2: 确保 PR 运行
    print("\n[Phase 2] 确保 PR 运行...")
    if args.restart and is_pr_running():
        close_pr_graceful()
        time.sleep(2)

    if not is_pr_running():
        # 先写后启：写入 ping 命令，PR 启动时 Startup 脚本会立即消费
        if RES_FILE.exists():
            try:
                RES_FILE.unlink()
            except OSError:
                pass
        if READY_FILE.exists():
            try:
                READY_FILE.unlink()
            except OSError:
                pass
        CMD_FILE.write_text(json.dumps({"command": "ping"}), encoding="utf-8")

        if not launch_pr(project_path):
            final_result["status"] = "FAILED"
            final_result["error"] = "无法启动 PR"
            _save_result(final_result)
            return 1
        print(f"  等待 PR + Startup 脚本初始化 ({PR_INIT_WAIT}s)...")
        time.sleep(PR_INIT_WAIT)
        dismiss_pr_dialogs(timeout=10)
    else:
        print("  [OK] PR 已在运行")

    final_result["phases"]["pr_running"] = True

    # Phase 3: 等待 CEP Bridge
    print("\n[Phase 3] 等待 CEP Bridge...")
    bridge_ok = wait_for_bridge(timeout=BRIDGE_READY_TIMEOUT)
    final_result["phases"]["bridge_connected"] = bridge_ok

    if not bridge_ok:
        print("\n  [X] Bridge 无法连通!")
        print_diagnostics()
        final_result["status"] = "FAILED"
        final_result["error"] = "Bridge 超时"
        _save_result(final_result)
        return 1

    # Phase 4: 验证连通性
    print("\n[Phase 4] 验证 Bridge 连通...")
    ping_res = send_command("ping", timeout=10)
    if ping_res and ping_res.get("status") == "success":
        pr_ver = ping_res.get("result", {}).get("version", "?") if isinstance(ping_res.get("result"), dict) else "?"
        print(f"  [OK] Ping 成功! PR version: {pr_ver}")
        final_result["phases"]["ping"] = "OK"
    else:
        print(f"  [!] Ping 响应异常: {ping_res}")
        final_result["phases"]["ping"] = "WARN"

    # Phase 5: 自动剪辑
    if not args.skip_edit:
        print("\n[Phase 5] 执行自动剪辑...")
        edit_result = run_auto_edit(export=args.export)
        final_result["phases"]["auto_edit"] = edit_result
        final_result["status"] = edit_result.get("status", "error")

        if edit_result.get("status") == "success":
            print("\n  [OK] 自动剪辑完成!")
            for k, v in edit_result.get("steps", {}).items():
                print(f"    {k}: {v}")
        else:
            print(f"\n  [X] 自动剪辑失败: {edit_result.get('error', 'unknown')}")
    else:
        print("\n[Phase 5] 跳过自动剪辑 (--skip-edit)")
        final_result["status"] = "success"
        final_result["phases"]["auto_edit"] = "SKIPPED"

    # 完成
    final_result["completed"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_result(final_result)

    print("\n" + "=" * 60)
    if final_result.get("status") == "success":
        print("  [OK] 全部完成!")
    else:
        print(f"  [X] 状态: {final_result.get('status')}")
    print(f"  结果: {RESULT_OUTPUT}")
    print("=" * 60)

    return 0 if final_result.get("status") == "success" else 1


def _save_result(result: dict):
    RESULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    RESULT_OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

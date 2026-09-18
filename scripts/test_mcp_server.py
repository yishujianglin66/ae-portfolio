#!/usr/bin/env python3
"""测试 AE MCP Server 启动和基本功能（简化版，Windows 兼容）。"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue

SERVER_PATH = Path(__file__).resolve().parent.parent / "ae-mcp-server" / "dist" / "index.js"


def read_stream(stream, queue):
    """后台线程读取流。"""
    for line in iter(stream.readline, ""):
        if line:
            queue.put(line.strip())
    stream.close()


def main() -> int:
    print("=" * 60)
    print("🧪 AE MCP Server 启动测试 (Windows)")
    print("=" * 60)
    print()

    if not SERVER_PATH.exists():
        print(f"❌ Server 不存在: {SERVER_PATH}")
        return 1

    print(f"📁 Server 路径: {SERVER_PATH}")
    print()

    print("🚀 启动 MCP Server...")
    try:
        proc = subprocess.Popen(
            ["node", str(SERVER_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
    except FileNotFoundError:
        print("❌ Node.js 未安装或不在 PATH 中")
        return 1

    stdout_q: Queue[str] = Queue()
    stderr_q: Queue[str] = Queue()

    t1 = threading.Thread(target=read_stream, args=(proc.stdout, stdout_q), daemon=True)
    t2 = threading.Thread(target=read_stream, args=(proc.stderr, stderr_q), daemon=True)
    t1.start()
    t2.start()

    time.sleep(1.5)

    if proc.poll() is not None:
        print(f"❌ 进程已退出，code={proc.returncode}")
        time.sleep(0.5)
        while not stderr_q.empty():
            print(f"  stderr: {stderr_q.get()}")
        return 1

    print("✅ 进程启动成功")
    print()

    # 发送 initialize
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }

    print("📤 发送 initialize 请求...")
    proc.stdin.write(json.dumps(init_req, ensure_ascii=False) + "\n")
    proc.stdin.flush()

    time.sleep(2)

    responses = []
    while not stdout_q.empty():
        try:
            responses.append(stdout_q.get_nowait())
        except Empty:
            break

    print(f"📥 收到 {len(responses)} 行响应")
    init_ok = False
    for line in responses:
        if line:
            try:
                data = json.loads(line)
                if "result" in data and "capabilities" in data.get("result", {}):
                    caps = data["result"]["capabilities"]
                    print(f"  ✅ initialize 成功，capabilities: {list(caps.keys())}")
                    init_ok = True
                elif "error" in data:
                    print(f"  ❌ 错误: {data['error']}")
            except json.JSONDecodeError:
                if len(line) < 200:
                    print(f"  {line}")

    if not init_ok:
        # 打印 stderr 看有啥错误
        print()
        print("  stderr 输出:")
        while not stderr_q.empty():
            try:
                print(f"    {stderr_q.get_nowait()[:300]}")
            except Empty:
                break
        print()
        print("  stdout 输出:")
        for line in responses[:10]:
            print(f"    {line[:300]}")
        proc.terminate()
        return 1

    # 发送 initialized 通知
    notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    proc.stdin.write(json.dumps(notif) + "\n")
    proc.stdin.flush()
    time.sleep(0.5)

    # 清空缓存
    while not stdout_q.empty():
        try:
            stdout_q.get_nowait()
        except Empty:
            break

    # 发送 tools/list
    print()
    print("📤 发送 tools/list 请求...")
    tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    proc.stdin.write(json.dumps(tools_req) + "\n")
    proc.stdin.flush()

    time.sleep(2)

    tool_lines = []
    while not stdout_q.empty():
        try:
            tool_lines.append(stdout_q.get_nowait())
        except Empty:
            break

    tool_count = 0
    for line in tool_lines:
        if line:
            try:
                data = json.loads(line)
                result = data.get("result", {})
                tools = result.get("tools", [])
                tool_count = len(tools)
                print(f"  ✅ 注册工具数: {tool_count}")
                for i, t in enumerate(tools[:8]):
                    print(f"    {i+1}. {t.get('name', '?')}")
                if len(tools) > 8:
                    print(f"    ... 还有 {len(tools) - 8} 个")
            except json.JSONDecodeError:
                pass

    # 关闭
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    print()
    print("=" * 60)
    if tool_count > 0:
        print(f"✅ 测试通过！MCP Server 正常，{tool_count} 个工具已注册")
        return 0
    else:
        print("⚠️  未获取到工具列表")
        return 1


if __name__ == "__main__":
    sys.exit(main())

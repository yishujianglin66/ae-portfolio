"""通过 premiere-pro-mcp MCP 服务器连接 PR 并测试。

这个脚本直接启动 MCP 服务器并通过 stdio 通信，不依赖 CEP 插件状态。
"""
import sys
import pathlib
import json
import asyncio
import subprocess

NODE_PATH = r"C:\Users\Administrator\AppData\Roaming\npm\node_modules\premiere-pro-mcp\dist\index.js"
BRIDGE_DIR = r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.premiere-mcp-bridge"


async def test():
    print("=" * 60)
    print("通过 premiere-pro-mcp MCP 服务器连接测试")
    print("=" * 60)
    print()

    # 1. 清理 bridge 目录
    import shutil
    for f in pathlib.Path(BRIDGE_DIR).glob("cmd_*"):
        f.unlink(missing_ok=True)
    for f in pathlib.Path(BRIDGE_DIR).glob("res_*"):
        f.unlink(missing_ok=True)
    print("✅ 桥接目录已清理")

    # 2. 启动 MCP 服务器
    print(f"\n启动 MCP 服务器...")
    env = {
        "PREMIERE_TEMP_DIR": BRIDGE_DIR,
        "PREMIERE_TIMEOUT_MS": "30000",
        "PATH": r"C:\Users\Administrator\AppData\Roaming\npm;C:\Program Files\nodejs;" + 
                r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312;" +
                r"C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem",
    }

    proc = await asyncio.create_subprocess_exec(
        NODE_PATH,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault",
    )

    # 3. 发送初始化请求
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pr-test", "version": "1.0.0"},
        },
    }

    proc.stdin.write((json.dumps(init_msg) + "\n").encode("utf-8"))
    await proc.stdin.drain()

    # 读取初始化响应
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
    response = json.loads(line)
    print(f"初始化响应: {json.dumps(response, indent=2)[:200]}")

    # 4. 发送 initialized 通知
    notified = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    proc.stdin.write((json.dumps(notified) + "\n").encode("utf-8"))
    await proc.stdin.drain()

    # 5. 列出工具
    list_tools = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    proc.stdin.write((json.dumps(list_tools) + "\n").encode("utf-8"))
    await proc.stdin.drain()

    line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
    tools_resp = json.loads(line)
    tools = tools_resp.get("result", {}).get("tools", [])
    print(f"\n可用工具: {len(tools)} 个")
    for t in tools[:5]:
        print(f"  - {t['name']}: {t['description'][:60]}")

    # 6. 调用 import_media
    import_tool = next((t for t in tools if t["name"] == "import_media"), None)
    if import_tool:
        print(f"\n调用 import_media...")
        call_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "import_media",
                "arguments": {
                    "file_paths": [
                        r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\stock_footage\pexels_3150392.mp4"
                    ],
                },
            },
        }
        proc.stdin.write((json.dumps(call_msg) + "\n").encode("utf-8"))
        await proc.stdin.drain()

        line = await asyncio.wait_for(proc.stdout.readline(), timeout=30.0)
        result = json.loads(line)
        print(f"  结果: {json.dumps(result, indent=2)[:300]}")

    # 7. 关闭
    proc.terminate()
    print("\n✅ 测试完成")


if __name__ == "__main__":
    asyncio.run(test())
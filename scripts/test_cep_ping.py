"""快速测试 CEP 是否还活着"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "puppet-automation"))
from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError


async def main():
    c = PRBridgeClient()
    c._preferred_protocol = "cep"
    try:
        r = await c._send_via_cep("return __result({msg:'ping'});", timeout=5.0)
        print(f"CEP 在线: {r}")
    except PRBridgeError as e:
        print(f"CEP 离线: {e}")
        print("请打开 PR 中的 Window > Extensions > MCP Bridge 面板")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
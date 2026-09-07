"""测试 PR 创建序列。"""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path("puppet-automation").resolve()))

import asyncio
from src.engines.premiere.pr_bridge_client import PRBridgeClient


async def test():
    c = PRBridgeClient()
    r = await c.create_sequence("TestSeq2025")
    print(r)
    return r


if __name__ == "__main__":
    result = asyncio.run(test())
    print("Success:", result.get("data", {}).get("created"))
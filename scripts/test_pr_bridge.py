"""PR 桥接连接测试脚本 — 验证 CEP 插件桥接是否在线。"""
import sys
import pathlib

# 添加路径
sys.path.insert(0, str(pathlib.Path("puppet-automation").resolve()))

import asyncio
from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError


async def test():
    client = PRBridgeClient()
    print("=" * 60)
    print("PR Bridge 连接测试")
    print("=" * 60)
    print(f"桥接目录: {client._bridge_dir}")
    print(f"目录存在: {client._bridge_dir.exists()}")
    print()

    print("正在检测桥接...")
    try:
        info = await client.ping()
        data = info.get("data", {})
        print(f"✅ 桥接在线!")
        print(f"   PR 版本: {data.get('appVersion', 'unknown')}")
        print(f"   项目: {data.get('project', '无')}")
        print(f"   序列: {data.get('sequence', '无')}")
        print()

        # 获取详细信息
        print("获取引擎信息...")
        info_result = await client.get_info()
        info_data = info_result.get("data", {})
        print(f"   项目名: {info_data.get('project', '无')}")
        seqs = info_data.get("sequences", [])
        if seqs:
            print(f"   序列 ({len(seqs)}):")
            for s in seqs:
                print(f"     - {s['name']} (V{s['videoTracks']} A{s['audioTracks']})")
        else:
            print(f"   序列: 无")

        return True

    except PRBridgeError as e:
        print(f"❌ 桥接离线: {e}")
        print()
        print("请确保:")
        print("  1. Premiere Pro 已启动并打开了一个项目")
        print("  2. MCP Bridge CEP 插件已自动运行")
        print("     (窗口 > 扩展 > MCP Bridge 应显示 'Running')")
        print(f"  3. 桥接目录存在: {client._bridge_dir}")
        return False
    except Exception as e:
        print(f"❌ 未预期错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
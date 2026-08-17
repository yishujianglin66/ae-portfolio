"""测试完整桥接通信 (ping + get_info)"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "puppet-automation"))
from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError

async def test():
    c = PRBridgeClient()
    print("=" * 60)
    print("PR Bridge 完整通信测试")
    print("=" * 60)
    print(f"桥接目录: {c._bridge_dir}")
    print(f"首选协议: {c._preferred_protocol}")
    print()

    # 1. ping
    print("1. 测试 ping...")
    try:
        r = await c.ping()
        d = r.get("data", {})
        print(f"   ✅ ping 成功!")
        print(f"   PR 版本: {d.get('appVersion', '?')}")
        print(f"   项目: {d.get('project', '无')}")
        print(f"   序列: {d.get('sequence', '无')}")
    except PRBridgeError as e:
        print(f"   ❌ ping 失败: {e}")
        return False

    # 2. get_info
    print()
    print("2. 测试 get_info...")
    try:
        r = await c.get_info()
        d = r.get("data", {})
        print(f"   ✅ get_info 成功!")
        print(f"   应用: {d.get('appName', '?')} v{d.get('appVersion', '?')}")
        print(f"   项目: {d.get('project', '无')}")
        bins = d.get("binCount", 0)
        print(f"   素材箱: {bins} 项")
        seqs = d.get("sequences", [])
        print(f"   序列: {len(seqs)} 个")
        for s in seqs:
            print(f"     - {s['name']} (V{s['videoTracks']} A{s['audioTracks']})")
    except PRBridgeError as e:
        print(f"   ❌ get_info 失败: {e}")
        return False

    print()
    print("=" * 60)
    print("所有测试通过!")
    return True

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test())
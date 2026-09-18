"""PR 简单操作测试 - 逐步测试每个操作。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path("puppet-automation").resolve()))

import asyncio

from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError


async def test():
    c = PRBridgeClient()
    print("=" * 60)
    print("PR 逐步操作测试")
    print("=" * 60)

    # 1. Ping
    print("\n1. Ping...")
    try:
        r = await c.ping()
        print(f"   ✅ {r.get('data', {})}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")
        # 尝试清理后重试
        print("   清理桥接目录...")
        import shutil
        for f in c._bridge_dir.glob("cmd_*"):
            f.unlink(missing_ok=True)
        for f in c._bridge_dir.glob("res_*"):
            f.unlink(missing_ok=True)
        for f in c._bridge_dir.glob("pr_*"):
            f.unlink(missing_ok=True)
        return

    # 2. 创建序列 - 最简单方式
    print("\n2. 创建序列...")
    try:
        # 最简方式：只传 name
        script = """
        try {
            app.project.createNewSequence("SimpleTest");
        } catch(e) {
            // 如果已有同名序列，跳过
        }
        var seq = app.project.activeSequence;
        if (!seq) {
            // 尝试找已有序列
            if (app.project.sequences.numSequences > 0) {
                app.project.activeSequence = app.project.sequences[0];
                seq = app.project.activeSequence;
            }
        }
        if (seq) {
            __result({created: true, name: seq.name, id: seq.sequenceID});
        } else {
            __error("No sequence available");
        }
        """
        r = await c._send_script(script, timeout=10.0)
        print(f"   ✅ {r}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")

    # 3. 获取信息
    print("\n3. 获取信息...")
    try:
        r = await c.get_info()
        print(f"   ✅ {r}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")

    # 4. 添加素材到时间线
    print("\n4. 添加素材到时间线...")
    try:
        # 找第一个导入的素材
        r = await c.add_to_timeline(
            item_name="pexels_3150392.mp4",
            track_index=0,
            start_seconds=0,
        )
        print(f"   ✅ {r}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")

    # 5. 添加转场
    print("\n5. 添加转场...")
    print("   (跳过，需要两个片段)")

    # 6. 导出
    print("\n6. 导出测试...")
    print("   (跳过完整导出，仅测试连接)")


if __name__ == "__main__":
    asyncio.run(test())
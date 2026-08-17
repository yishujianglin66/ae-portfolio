"""
测试 PR MCPBridgeCEP 扩展是否正常工作
直接测试 CEP 协议（cmd_<id>.jsx → res_<id>.json）
"""
import sys
import asyncio
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "puppet-automation"))

from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError


async def test_cep_protocol():
    """测试 CEP 协议是否正常工作。"""
    client = PRBridgeClient()
    bridge_dir = client._bridge_dir

    print("=" * 70)
    print("PR MCPBridgeCEP 扩展连接测试")
    print("=" * 70)
    print(f"桥接目录: {bridge_dir}")
    print(f"桥接目录存在: {bridge_dir.exists()}")
    print()

    # 列出桥接目录内容
    files = list(bridge_dir.iterdir())
    if files:
        print(f"桥接目录文件 ({len(files)}):")
        for f in files:
            print(f"  - {f.name} ({f.stat().st_size} bytes)")
    else:
        print("桥接目录为空")

    # 检查 PR 是否运行
    import subprocess
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Adobe Premiere Pro.exe", "/FO", "CSV"],
        capture_output=True, text=True, timeout=5
    )
    pr_running = "Adobe Premiere Pro.exe" in result.stdout
    print(f"\nPR 运行状态: {'✅ 运行中' if pr_running else '❌ 未运行'}")

    if not pr_running:
        print("\n请先启动 Premiere Pro 并打开一个项目")
        print("然后在 PR 中打开 Window > Extensions > MCP Bridge")
        return

    print()
    print("1. 测试桥接连接 (ping)...")
    print(f"   (等待 CEP 扩展响应，最长 10 秒)")
    print()

    try:
        # 尝试 ping
        r = await client.ping()
        print(f"   ✅ 桥接在线!")
        data = r.get("data", {})
        print(f"      PR 版本: {data.get('appVersion', 'unknown')}")
        print(f"      项目: {data.get('project', '无')}")
        print(f"      序列: {data.get('sequence', '无')}")
        return True
    except PRBridgeError as e:
        print(f"   ❌ 桥接离线: {e}")
        print()

        # 分析原因
        print("可能的原因:")
        print("  1. MCPBridgeCEP 扩展未加载")
        print("     请在 PR 中打开: Window > Extensions > MCP Bridge")
        print("     然后点击 'Start Bridge' 按钮")
        print()
        print("  2. 或者使用 Standalone 协议:")
        print("     在 PR 中运行: File > Scripts > Run Script File...")
        jsx_path = Path(__file__).parent.parent / "puppet-automation" / "src" / "engines" / "premiere" / "pr_mcp_bridge.jsx"
        print(f"     选择: {jsx_path}")
        print()
        return False


async def test_standalone_protocol():
    """测试 Standalone JSX 协议 (pr_command.json)。"""
    client = PRBridgeClient()
    # 强制使用 standalone 协议
    client._preferred_protocol = "standalone"

    print("2. 测试 Standalone 协议 (pr_command.json)...")
    print(f"   (等待 pr_mcp_bridge.jsx 响应，最长 10 秒)")
    print()

    try:
        r = await client.ping()
        print(f"   ✅ Standalone 桥接在线!")
        data = r.get("data", {})
        print(f"      PR 版本: {data.get('appVersion', 'unknown')}")
        print(f"      项目: {data.get('project', '无')}")
        return True
    except PRBridgeError as e:
        print(f"   ❌ Standalone 桥接离线: {e}")
        print()
        print("需要在 PR 中运行 pr_mcp_bridge.jsx:")
        jsx_path = Path(__file__).parent.parent / "puppet-automation" / "src" / "engines" / "premiere" / "pr_mcp_bridge.jsx"
        print(f"   File > Scripts > Run Script File... > {jsx_path}")
        return False


async def test_create_sequence():
    """测试创建序列。"""
    client = PRBridgeClient()

    print("3. 测试创建序列...")
    print()

    try:
        r = await client.create_sequence("TestSeq_1")
        print(f"   ✅ 序列创建成功: {r}")
        return True
    except PRBridgeError as e:
        print(f"   ❌ 序列创建失败: {e}")
        return False


async def test_import_media():
    """测试导入素材。"""
    client = PRBridgeClient()
    stock_footage = Path(__file__).parent.parent / "data" / "stock_footage"

    if not stock_footage.exists():
        print(f"   ⚠️ 素材目录不存在: {stock_footage}")
        return False

    video_files = sorted([
        str(f) for f in stock_footage.iterdir()
        if f.suffix.lower() in {".mp4", ".mov", ".avi"}
    ])

    if not video_files:
        print(f"   ⚠️ 没有找到素材文件")
        return False

    print(f"4. 测试导入素材 ({len(video_files)} 个文件)...")
    print(f"   首文件: {Path(video_files[0]).name}")
    print()

    try:
        r = await client.import_media(video_files[:2])
        print(f"   ✅ 素材导入成功: {r}")
        return True
    except PRBridgeError as e:
        print(f"   ❌ 素材导入失败: {e}")
        return False


async def test_add_to_timeline():
    """测试添加素材到时间线。"""
    client = PRBridgeClient()

    print("5. 测试添加素材到时间线...")
    print()

    # 先获取项目信息，找到已导入的素材
    try:
        info = await client.get_info()
        bins = info.get("data", {}).get("sequences", [])
        print(f"   当前序列: {len(bins)} 个")
    except PRBridgeError as e:
        print(f"   ⚠️ 获取信息失败: {e}")

    # 尝试添加素材
    try:
        r = await client.add_to_timeline("TestSeq_1", track_index=0, start_seconds=0)
        print(f"   ✅ 素材上轨成功: {r}")
        return True
    except PRBridgeError as e:
        print(f"   ❌ 素材上轨失败: {e}")
        print(f"   (可能因为素材名不是 TestSeq_1)")
        return False


async def main():
    # 先测试 CEP 协议
    cep_ok = await test_cep_protocol()
    print()

    if not cep_ok:
        # 测试 standalone 协议
        await test_standalone_protocol()
        print()
        print("=" * 70)
        print("建议: 打开 PR 后，依次尝试:")
        print("  1. Window > Extensions > MCP Bridge 检查是否自动运行")
        print("  2. 如果未运行，点击 Start Bridge 按钮")
        print("  3. 或者运行 pr_mcp_bridge.jsx (File > Scripts > Run Script File...)")
        print("=" * 70)
        return

    # 测试序列创建
    print()
    seq_ok = await test_create_sequence()
    print()

    # 测试素材导入
    print()
    await test_import_media()
    print()

    print()
    print("=" * 70)
    print("测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
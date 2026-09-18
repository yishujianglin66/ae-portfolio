"""测试 CEP 协议是否仍然可用"""
import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "puppet-automation"))

from src.engines.premiere.pr_bridge_client import PRBridgeClient


async def test_cep():
    """强制使用 CEP 协议测试"""
    from src.engines.premiere.pr_bridge_client import PRBridgeError
    
    client = PRBridgeClient()
    client._preferred_protocol = "cep"  # 强制 CEP
    
    # 测试1: 简单 ping
    print("测试1: 简单 ping")
    try:
        r = await client._send_via_cep("return __result({msg:'hello'});", timeout=10.0)
        print(f"  ✅ 成功: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")
    
    # 测试2: 探测 API
    client2 = PRBridgeClient()
    client2._preferred_protocol = "cep"
    print("\n测试2: 探测 createNewSequence 方法")
    try:
        r = await client2._send_via_cep("""
        var info = {};
        info.hasCreateNewSequence = typeof app.project.createNewSequence;
        info.hasSequences = typeof app.project.sequences;
        info.seqCount = app.project.sequences.numSequences;
        return __result(info);
        """, timeout=10.0)
        print(f"  ✅ 成功: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")
    
    # 测试3: 尝试创建序列（最简单方式）
    client3 = PRBridgeClient()
    client3._preferred_protocol = "cep"
    print("\n测试3: createNewSequence 无预设")
    try:
        r = await client3._send_via_cep("""
        app.project.createNewSequence("TestSeq1");
        var seq = app.project.activeSequence;
        return __result({created: true, name: seq ? seq.name : null, id: seq ? seq.sequenceID : null});
        """, timeout=20.0)
        print(f"  ✅ 成功: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")
    
    # 测试4: 尝试 QE 创建序列
    client4 = PRBridgeClient()
    client4._preferred_protocol = "cep"
    print("\n测试4: QE 创建序列")
    try:
        r = await client4._send_via_cep("""
        app.enableQE();
        var presets = qe.project.getSequencePresetList();
        var hdPreset = null;
        for (var i = 0; i < presets.length; i++) {
            if (presets[i].indexOf('1080') >= 0) { hdPreset = presets[i]; break; }
        }
        return __result({presetCount: presets.length, hdPreset: hdPreset, firstPreset: presets[0]});
        """, timeout=20.0)
        print(f"  ✅ 成功: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test_cep())
"""探索 PR 2025 ExtendScript API - 探测可用的序列创建方法（CEP 协议）"""
import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "puppet-automation"))

from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError


async def test_cep_safe():
    """使用 CEP 协议安全探测（每个脚本用新实例，保证 CEP 优先）"""
    
    def make_client():
        c = PRBridgeClient()
        c._preferred_protocol = "cep"
        return c

    # 测试1: 简单 ping
    print("测试1: CEP 简单 ping")
    try:
        c = make_client()
        r = await c._send_via_cep("return __result({msg:'hello', time: 'ok'});", timeout=10.0)
        print(f"  ✅ 成功: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")

    # 测试2: 探测 app.project 基本信息
    print("\n测试2: 探测项目基本信息")
    try:
        c = make_client()
        r = await c._send_via_cep("""
        var info = {};
        info.hasCreateNewSeq = typeof app.project.createNewSequence;
        info.hasSequences = typeof app.project.sequences;
        info.seqCount = 0;
        try { info.seqCount = app.project.sequences.numSequences; } catch(e) {}
        info.seqNames = [];
        try {
            for (var i = 0; i < app.project.sequences.numSequences; i++) {
                info.seqNames.push(app.project.sequences[i].name);
            }
        } catch(e) {}
        info.projectName = app.project ? app.project.name : null;
        return __result(info);
        """, timeout=10.0)
        print(f"  ✅ 成功: {r}")
        data = r.get('data', {})
        if data.get('seqCount', 0) > 0:
            print(f"  → 已有序列: {data['seqNames']}")
        else:
            print("  → 项目无序列，需要创建")
            print(f"  → createNewSequence 方法: {data.get('hasCreateNewSeq', 'undefined')}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")

    # 测试3: 尝试创建序列（最简单方式）
    print("\n测试3: 尝试创建新序列")
    try:
        c = make_client()
        r = await c._send_via_cep("""
        try {
            app.project.createNewSequence("AutoEdit_Test");
            var seq = app.project.activeSequence;
            if (seq) {
                return __result({created: true, name: seq.name, id: seq.sequenceID});
            }
        } catch(e) {}
        // 尝试 QE
        try {
            app.enableQE();
            var presets = qe.project.getSequencePresetList();
            var chosen = null;
            for (var i = 0; i < presets.length; i++) {
                if (presets[i].indexOf('1080') >= 0) { chosen = presets[i]; break; }
            }
            if (!chosen && presets.length > 0) chosen = presets[0];
            return __result({presetCount: presets.length, firstPreset: presets[0], chosenPreset: chosen});
        } catch(e2) {
            return __error("Both methods failed: " + e2.toString());
        }
        """, timeout=30.0)
        print(f"  ✅ 成功: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")

    # 测试4: 检查 QE 预设列表
    print("\n测试4: QE 预设列表（前20个）")
    try:
        c = make_client()
        r = await c._send_via_cep("""
        app.enableQE();
        var presets = qe.project.getSequencePresetList();
        var list = [];
        for (var i = 0; i < Math.min(presets.length, 20); i++) {
            list.push(presets[i]);
        }
        return __result({count: presets.length, presets: list});
        """, timeout=10.0)
        print(f"  ✅ 成功: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test_cep_safe())
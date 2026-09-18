"""测试序列创建 - 各种方法"""
import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "puppet-automation"))

from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError


def make_client():
    c = PRBridgeClient()
    c._preferred_protocol = "cep"
    return c

async def main():
    # 测试1: 用预设名创建序列
    print("测试1: createNewSequence(name, 'HD 1080p 30')")
    try:
        c = make_client()
        r = await c._send_via_cep("""
        try {
            app.project.createNewSequence("Seq1", "HD 1080p 30");
            var seq = app.project.activeSequence;
            return __result({method: 'with preset', seqName: seq ? seq.name : null, seqId: seq ? seq.sequenceID : null});
        } catch(e) {
            return __error("Method1 error: " + e.toString());
        }
        """, timeout=30.0)
        print(f"  ✅ 结果: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 超时/失败: {e}")

    # 测试2: 无预设创建
    print("\n测试2: createNewSequence(name) 无预设")
    try:
        c = make_client()
        r = await c._send_via_cep("""
        try {
            app.project.createNewSequence("Seq2");
            var seq = app.project.activeSequence;
            return __result({method: 'no preset', seqName: seq ? seq.name : null, seqId: seq ? seq.sequenceID : null});
        } catch(e) {
            return __error("Method2 error: " + e.toString());
        }
        """, timeout=30.0)
        print(f"  ✅ 结果: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 超时/失败: {e}")

    # 测试3: 用 QE 创建
    print("\n测试3: QE createNewSequence")
    try:
        c = make_client()
        r = await c._send_via_cep("""
        try {
            app.enableQE();
            // Check available QE methods
            var info = {};
            info.hasQECreateNewSeq = typeof qe.project.createNewSequence;
            info.hasQESequenceList = typeof qe.project.getSequenceList;
            info.qeVersion = typeof qe.version;
            
            // Try to create with QE - use a hardcoded preset name
            try {
                qe.project.createNewSequence("Seq3", "HD 1080p 30");
                var seq = app.project.activeSequence;
                info.qeResult = seq ? seq.name : "no seq";
            } catch(e) {
                info.qeError = e.toString();
            }
            
            return __result(info);
        } catch(e) {
            return __error("QE error: " + e.toString());
        }
        """, timeout=30.0)
        print(f"  ✅ 结果: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 超时/失败: {e}")

    # 测试4: 检查当前序列状态
    print("\n测试4: 当前序列状态")
    try:
        c = make_client()
        r = await c._send_via_cep("""
        var info = {};
        info.seqCount = app.project.sequences.numSequences;
        info.seqNames = [];
        for (var i = 0; i < app.project.sequences.numSequences; i++) {
            info.seqNames.push(app.project.sequences[i].name);
        }
        info.activeSeq = app.project.activeSequence ? app.project.activeSequence.name : null;
        return __result(info);
        """, timeout=10.0)
        print(f"  ✅ 结果: {r}")
    except PRBridgeError as e:
        print(f"  ❌ 失败: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
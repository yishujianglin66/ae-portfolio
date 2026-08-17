"""测试不同的序列创建方法"""
import asyncio, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "puppet-automation"))
from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError

async def test():
    c = PRBridgeClient()
    c._preferred_protocol = "cep"
    print("=" * 60)
    print("测试不同的序列创建方法")
    print("=" * 60)

    # 方法1: 无预设名
    print("\n1. 方法1: createNewSequence 无预设名...")
    t0 = time.monotonic()
    try:
        r = await c._send_via_cep("""
        try {
            app.project.createNewSequence("TestSeq1");
            var seq = app.project.activeSequence;
            if (seq) {
                return __result({method: "no_preset", name: seq.name, id: seq.sequenceID});
            }
            // 尝试通过 sequences 获取
            var allSeqs = app.project.sequences;
            if (allSeqs.numSequences > 0) {
                seq = allSeqs[allSeqs.numSequences - 1];
                return __result({method: "no_preset_fallback", name: seq.name});
            }
            return __error("No sequence created");
        } catch(e) {
            return __error("createNewSequence failed: " + e.toString() + " line:" + e.line);
        }
        """, timeout=10.0)
        elapsed = time.monotonic() - t0
        print(f"   ✅ ({elapsed:.1f}s): {r}")
    except PRBridgeError as e:
        elapsed = time.monotonic() - t0
        print(f"   ❌ ({elapsed:.1f}s): {e}")

    # 方法2: QE 接口
    print("\n2. 方法2: QE createNewSequence...")
    t0 = time.monotonic()
    try:
        r = await c._send_via_cep("""
        try {
            app.enableQE();
            var qeProj = qe.project;
            var newSeq = qeProj.createNewSequence("TestSeq2", "DSLR 1080p29.97");
            if (newSeq) {
                // 设置活动序列
                app.project.activeSequence = app.project.sequences[app.project.sequences.numSequences - 1];
                return __result({method: "qe", name: newSeq.name});
            }
            return __error("QE createNewSequence returned null");
        } catch(e) {
            return __error("QE failed: " + e.toString() + " line:" + e.line);
        }
        """, timeout=10.0)
        elapsed = time.monotonic() - t0
        print(f"   ✅ ({elapsed:.1f}s): {r}")
    except PRBridgeError as e:
        elapsed = time.monotonic() - t0
        print(f"   ❌ ({elapsed:.1f}s): {e}")

    # 方法3: 先检查已有序列
    print("\n3. 获取当前序列列表...")
    try:
        r = await c._send_via_cep("""
        var info = {seqCount: 0, names: []};
        try {
            info.seqCount = app.project.sequences.numSequences;
            for (var i = 0; i < app.project.sequences.numSequences; i++) {
                info.names.push(app.project.sequences[i].name);
            }
        } catch(e) {
            return __error("Error: " + e.toString());
        }
        return __result(info);
        """, timeout=5.0)
        print(f"   ✅ 序列列表: {r}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test())
"""测试带预设名的序列创建"""
import asyncio, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "puppet-automation"))
from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError

async def test():
    c = PRBridgeClient()
    c._preferred_protocol = "cep"
    print("=" * 60)
    print("测试带预设名的序列创建")
    print("=" * 60)

    # 先获取可用预设列表
    print("\n1. 获取可用序列预设...")
    try:
        r = await c._send_via_cep("""
        try {
            var presets = app.project.getSequencePresets();
            var names = [];
            for (var i = 0; i < presets.length; i++) {
                names.push(presets[i].name);
            }
            return __result({count: names.length, names: names});
        } catch(e) {
            // 尝试通过 QE 获取
            try {
                app.enableQE();
                var qePresets = qe.project.getSequencePresets();
                var names = [];
                for (var i = 0; i < qePresets.length; i++) {
                    names.push(qePresets[i].name);
                }
                return __result({method: "qe", count: names.length, names: names});
            } catch(e2) {
                // 尝试 app.project.getPresets
                try {
                    var presets2 = app.project.getPresets();
                    return __result({method: "getPresets", count: presets2.length, names: presets2});
                } catch(e3) {
                    return __error("All methods failed: " + e.toString() + " | " + e2.toString() + " | " + e3.toString());
                }
            }
        }
        """, timeout=10.0)
        print(f"   ✅ {r}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")

    # 方法2: 带预设名创建（常用预设名）
    print("\n2. 方法2: createNewSequence 带预设名 'DSLR 1080p29.97'...")
    t0 = time.monotonic()
    try:
        r = await c._send_via_cep("""
        try {
            app.project.createNewSequence("TestSeq2", "DSLR 1080p29.97");
            var seq = app.project.activeSequence;
            if (seq) {
                return __result({method: "with_preset", name: seq.name, id: seq.sequenceID});
            }
            var allSeqs = app.project.sequences;
            if (allSeqs.numSequences > 0) {
                seq = allSeqs[allSeqs.numSequences - 1];
                return __result({method: "with_preset_fallback", name: seq.name});
            }
            return __error("No sequence created");
        } catch(e) {
            return __error("createNewSequence failed: " + e.toString() + " line:" + e.line);
        }
        """, timeout=15.0)
        elapsed = time.monotonic() - t0
        print(f"   ✅ ({elapsed:.1f}s): {r}")
    except PRBridgeError as e:
        elapsed = time.monotonic() - t0
        print(f"   ❌ ({elapsed:.1f}s): {e}")

    # 方法3: 尝试不同的预设名
    print("\n3. 方法3: createNewSequence 带 'HD 1080p'...")
    t0 = time.monotonic()
    try:
        r = await c._send_via_cep("""
        try {
            app.project.createNewSequence("TestSeq3", "HD 1080p");
            var seq = app.project.activeSequence;
            if (seq) {
                return __result({method: "hd1080", name: seq.name});
            }
            var allSeqs = app.project.sequences;
            if (allSeqs.numSequences > 0) {
                seq = allSeqs[allSeqs.numSequences - 1];
                return __result({method: "hd1080_fallback", name: seq.name});
            }
            return __error("No sequence created");
        } catch(e) {
            return __error("createNewSequence failed: " + e.toString() + " line:" + e.line);
        }
        """, timeout=15.0)
        elapsed = time.monotonic() - t0
        print(f"   ✅ ({elapsed:.1f}s): {r}")
    except PRBridgeError as e:
        elapsed = time.monotonic() - t0
        print(f"   ❌ ({elapsed:.1f}s): {e}")

    # 方法4: 查看当前序列列表
    print("\n4. 当前序列列表...")
    try:
        r = await c._send_via_cep("""
        var info = {seqCount: 0, names: []};
        try {
            info.seqCount = app.project.sequences.numSequences;
            for (var i = 0; i < app.project.sequences.numSequences; i++) {
                info.names.push(app.project.sequences[i].name);
            }
        } catch(e) {}
        return __result(info);
        """, timeout=5.0)
        print(f"   ✅ {r}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test())
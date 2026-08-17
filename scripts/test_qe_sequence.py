"""测试 QE 接口创建序列（需要先重启 CEP 面板）"""
import asyncio, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "puppet-automation"))
from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError

async def test():
    c = PRBridgeClient()
    c._preferred_protocol = "cep"
    print("=" * 60)
    print("QE 接口创建序列测试")
    print("注意: 如果 CEP 引擎已死锁，请在 PR 中关闭并重新打开 MCP Bridge 面板")
    print("=" * 60)

    # 先测试 ping 看 CEP 是否活着
    print("\n1. 检查 CEP 是否在线...")
    try:
        r = await c._send_via_cep("return __result({msg:'ping'});", timeout=3.0)
        print(f"   ✅ CEP 在线: {r}")
    except PRBridgeError as e:
        print(f"   ❌ CEP 离线: {e}")
        print("   请在 PR 中: Window > Extensions > MCP Bridge 关闭并重新打开")
        return

    # 方法1: QE 创建序列
    print("\n2. QE enable + createNewSequence...")
    t0 = time.monotonic()
    try:
        r = await c._send_via_cep("""
        try {
            app.enableQE();
            // 检查 QE 是否初始化成功
            if (typeof qe === 'undefined' || !qe.project) {
                return __error("QE not initialized");
            }
            // 尝试 qe.project.createNewSequence(name, presetName)
            var newSeq = null;
            try {
                newSeq = qe.project.createNewSequence("QETest", "DVCPRO50 720p29.97");
            } catch(e1) {
                try {
                    newSeq = qe.project.createNewSequence("QETest", "DSLR 1080p29.97");
                } catch(e2) {
                    return __error("Both preset names failed: " + e1.toString() + " | " + e2.toString());
                }
            }
            if (newSeq) {
                app.project.activeSequence = app.project.sequences[app.project.sequences.numSequences - 1];
                return __result({method: "qe", name: newSeq.name, id: newSeq.sequenceID});
            }
            return __error("QE returned null");
        } catch(e) {
            return __error("QE error: " + e.toString() + " line:" + e.line);
        }
        """, timeout=10.0)
        elapsed = time.monotonic() - t0
        print(f"   ✅ ({elapsed:.1f}s): {r}")
    except PRBridgeError as e:
        elapsed = time.monotonic() - t0
        print(f"   ❌ ({elapsed:.1f}s): {e}")

    # 方法2: 检查 QE 项目属性
    print("\n3. QE 项目属性探测...")
    try:
        r = await c._send_via_cep("""
        app.enableQE();
        var info = {methods: []};
        try { info.qeExists = typeof qe !== 'undefined'; } catch(e) {}
        try { info.qeProjectExists = typeof qe.project !== 'undefined'; } catch(e) {}
        // 枚举 qe.project 的方法
        try {
            var methods = [];
            for (var key in qe.project) {
                try {
                    if (typeof qe.project[key] === 'function') {
                        methods.push(key);
                    }
                } catch(e) {}
            }
            info.qeProjectMethods = methods;
        } catch(e) {}
        // 检查 app.project.sequences 是否有 add 方法
        try {
            var seqMethods = [];
            for (var key in app.project.sequences) {
                try {
                    if (typeof app.project.sequences[key] === 'function') {
                        seqMethods.push(key);
                    }
                } catch(e) {}
            }
            info.sequencesMethods = seqMethods;
        } catch(e) {}
        return __result(info);
        """, timeout=10.0)
        print(f"   ✅ {r}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")

    # 方法3: 检查是否有 createNewSequence 的替代方法
    print("\n4. 检查 app.project 方法...")
    try:
        r = await c._send_via_cep("""
        var relevant = [];
        for (var key in app.project) {
            try {
                if (typeof app.project[key] === 'function' && (
                    key.toLowerCase().indexOf('sequence') >= 0 ||
                    key.toLowerCase().indexOf('seq') >= 0 ||
                    key.toLowerCase().indexOf('create') >= 0 ||
                    key.toLowerCase().indexOf('new') >= 0 ||
                    key.toLowerCase().indexOf('add') >= 0
                )) {
                    relevant.push(key);
                }
            } catch(e) {}
        }
        return __result({relevantMethods: relevant});
        """, timeout=10.0)
        print(f"   ✅ {r}")
    except PRBridgeError as e:
        print(f"   ❌ {e}")

    # 方法4: 检查序列列表
    print("\n5. 当前序列列表...")
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
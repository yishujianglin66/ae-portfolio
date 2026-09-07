#!/usr/bin/env python3
"""
Silhouette 集成测试 v2.0
基于真实 Silhouette 2026 fx API 验证。
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import silhouette_fx_emulator as fx
from silhouette_executor import SilhouetteExecutor


def test_fx_emulator():
    print("=" * 60)
    print("Test 1: fx_emulator API 一致性")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    tests = [
        ("Point", lambda: fx.Point(100, 200)),
        ("Size", lambda: fx.Size(1920, 1080)),
        ("Recti", lambda: fx.Recti(0, 0, 1920, 1080)),
        ("Property + setValue", lambda: _test_property()),
        ("Node('SourceNode')", lambda: fx.Node("SourceNode")),
        ("Node('RotoNode')", lambda: fx.Node("RotoNode")),
        ("Node('OutputNode')", lambda: fx.Node("OutputNode")),
        ("Port.connect()", lambda: _test_connect()),
        ("Port.source 只读", lambda: _test_port_readonly()),
        ("Project + Session", lambda: _test_project()),
        ("sess.addNode()", lambda: _test_add_node()),
        ("version 是变量", lambda: fx.version == 2026.0),
        ("activeProject/activeSession", lambda: _test_active()),
        ("getNodes()", lambda: "RotoNode" in fx.getNodes()),
        ("node.properties (dict)", lambda: isinstance(fx.Node("RotoNode").properties, dict)),
        ("node.property(name)", lambda: fx.Node("RotoNode").property("alpha.blur") is not None),
    ]
    
    for name, test_fn in tests:
        try:
            result = test_fn()
            if result is False:
                raise AssertionError("返回 False")
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
    
    print(f"\n  Result: {passed}/{passed+failed} passed")
    return failed == 0


def _test_property():
    p = fx.Property("test", "number")
    p.setValue(42, 0)
    return p.getValue(0) == 42


def _test_connect():
    src = fx.Node("SourceNode")
    roto = fx.Node("RotoNode")
    src.outputs[0].connect(roto.inputs[1])
    return roto.inputs[1].source is src.outputs[0]


def _test_port_readonly():
    src = fx.Node("SourceNode")
    roto = fx.Node("RotoNode")
    try:
        roto.inputs[0].source = src.outputs[0]
        return False
    except AttributeError:
        return True


def _test_project():
    proj = fx.Project()
    fx.activate(proj)
    sess = fx.Session("TestSession")
    fx.activate(sess)
    proj.addItem(sess)
    return fx.activeProject() is proj and fx.activeSession() is sess


def _test_add_node():
    sess = fx.Session("Test")
    src = fx.Node("SourceNode")
    roto = fx.Node("RotoNode")
    out = fx.Node("OutputNode")
    sess.addNode(src)
    sess.addNode(roto)
    sess.addNode(out)
    return len(sess.nodes) == 3


def _test_active():
    proj = fx.Project()
    fx.activate(proj)
    sess = fx.Session("Test")
    fx.activate(sess)
    return fx.activeProject() is proj and fx.activeSession() is sess


def test_executor_script_generation():
    print("\n" + "=" * 60)
    print("Test 2: Executor 脚本生成（真实 API 标准）")
    print("=" * 60)
    
    executor = SilhouetteExecutor()
    
    test_cases = [
        {
            "name": "Roto 基础命令",
            "command": "silhouette_roto",
            "params": {
                "source_path": r"C:\Temp\silhouette_test\roto_test_person.png",
                "shape_type": "bezier",
                "tolerance": 1.5,
            },
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n  Case: {test['name']}")
        
        try:
            script = executor._generate_roto_script(
                source=test["params"]["source_path"],
                output=r"D:\AE-Work\output.png",
                shape_type=test["params"].get("shape_type", "x-spline"),
                tolerance=test["params"].get("tolerance", 1.0),
            )
            
            checks = [
                ("from fx import *", "from fx import *" in script),
                ('Node("SourceNode")', 'Node("SourceNode")' in script),
                ('Node("RotoNode")', 'Node("RotoNode")' in script),
                ('Node("OutputNode")', 'Node("OutputNode")' in script),
                (".connect()", ".connect(" in script),
                ("roto.inputs[1] (foreground)", "roto.inputs[1]" in script),
                ("roto.outputs[0] (output)", "roto.outputs[0]" in script),
                ("session.addNode()", "session.addNode" in script),
                ("alpha.blur property", "alpha.blur" in script),
                ("activeProject/activeSession", "activeProject" in script),
            ]
            
            for check_name, passed_check in checks:
                status = "PASS" if passed_check else "FAIL"
                print(f"    [{status}] {check_name}")
                if passed_check:
                    passed += 1
                else:
                    failed += 1
            
        except Exception as e:
            print(f"    [FAIL] 执行失败: {e}")
            failed += 1
    
    print(f"\n  Result: {passed}/{passed+failed} passed")
    return failed == 0


def test_roto_pipeline_emulation():
    print("\n" + "=" * 60)
    print("Test 3: 完整 Roto 管线模拟（真实 API 流程）")
    print("=" * 60)
    
    try:
        # 1. 创建 Project + Session
        proj = fx.Project()
        fx.activate(proj)
        
        sess = fx.Session("TestPipeline")
        fx.activate(sess)
        proj.addItem(sess)
        print("  [PASS] Project + Session 创建")
        
        # 2. 创建节点
        src = fx.Node("SourceNode")
        roto = fx.Node("RotoNode")
        out_node = fx.Node("OutputNode")
        print("  [PASS] Source/Roto/Output 节点创建")
        
        # 3. 验证端口
        assert len(src.outputs) == 1
        assert len(roto.inputs) == 5
        assert len(roto.outputs) == 5
        assert roto.inputs[1].name == "foreground"
        print("  [PASS] 端口数量和名称正确")
        
        # 4. 连接管线
        src.outputs[0].connect(roto.inputs[1])
        roto.outputs[0].connect(out_node.inputs[0])
        print("  [PASS] 节点连接成功")
        
        # 5. 验证连接
        assert roto.inputs[1].source is src.outputs[0]
        assert out_node.inputs[0].source is roto.outputs[0]
        print("  [PASS] 连接状态验证")
        
        # 6. 添加到 Session
        sess.addNode(src)
        sess.addNode(roto)
        sess.addNode(out_node)
        assert len(sess.nodes) == 3
        print("  [PASS] 添加到 Session")
        
        # 7. 设置属性
        roto.property("alpha.blur").setValue(1.5, 0)
        assert roto.property("alpha.blur").getValue(0) == 1.5
        print("  [PASS] 属性设置")
        
        # 8. 管线结构
        print("\n  Pipeline Structure:")
        print(f"    Source ({src.label})")
        print(f"      output → Roto.foreground")
        print(f"    Roto ({roto.label})")
        print(f"      output → Output.input")
        print(f"    Output ({out_node.label})")
        
        print("\n  Result: 8/8 passed")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "♦" * 60)
    print("  Silhouette 集成测试 v2.0")
    print("  基于 Silhouette 2026 真实 API 验证")
    print("♦" * 60)
    
    results = []
    
    results.append(("fx_emulator API 一致性", test_fx_emulator()))
    results.append(("Executor 脚本生成", test_executor_script_generation()))
    results.append(("Roto 管线模拟", test_roto_pipeline_emulation()))
    
    print("\n" + "=" * 60)
    print("总结果")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("❌ 部分测试失败")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

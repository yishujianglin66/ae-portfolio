# Silhouette 基础测试脚本 v1.0
# 把结果输出到文件以便验证

import fx
import sys
import os

output_lines = []

def log(msg):
    output_lines.append(msg)
    print(msg)

log("=" * 60)
log("Silhouette fx 模块基础测试")
log("=" * 60)

try:
    log("\n[1] 检查 fx 模块...")
    log(f"  fx 模块: {fx}")

    log("\n[2] 测试基础类型...")
    p = fx.Point(100, 200)
    log(f"  Point(100,200): ({p.x}, {p.y})")

    s = fx.Size(1920, 1080)
    log(f"  Size(1920,1080): ({s.width}, {s.height})")

    log("\n[3] 测试 Object...")
    obj = fx.Object(type="Test", label="MyObject")
    log(f"  Object: type={obj.type}, label={obj.label}")

    log("\n[4] 测试 Property...")
    prop = fx.Property("test", 42)
    log(f"  Property: name={prop.name}, value={prop.value}")

    obj.addProperty(prop)
    p2 = obj.property("test")
    log(f"  property() 返回: {p2.value}")

    log("\n[5] 测试 Node...")
    node = fx.Node(type="BlurNode", label="Blur1")
    log(f"  Node: type={node.type}, label={node.label}")
    log(f"  inputs: {len(node.inputs)}, outputs: {len(node.outputs)}")

    log("\n[6] 测试 SourceNode...")
    src = fx.Node(type="SourceNode", label="Source1")
    log(f"  SourceNode: inputs={len(src.inputs)}, outputs={len(src.outputs)}")

    log("\n[7] 测试 OutputNode...")
    out = fx.Node(type="OutputNode", label="Output1")
    log(f"  OutputNode: inputs={len(out.inputs)}, outputs={len(out.outputs)}")

    log("\n[8] 测试 Pipe...")
    pipe = fx.Pipe(source=src.outputs[0], target=node.inputs[0])
    log(f"  Pipe 创建成功: source={pipe.source.name}, target={pipe.target.name}")

    log("\n[9] 测试 Project...")
    try:
        proj = fx.Project()
        log(f"  Project 创建成功")
    except Exception as e:
        log(f"  Project 创建失败: {e}")

    log("\n[10] 测试 Session...")
    try:
        session = fx.Session(label="TestSession")
        log(f"  Session 创建成功: label={session.label}")
    except Exception as e:
        log(f"  Session 创建失败: {e}")

except Exception as e:
    import traceback
    log(f"\n[ERROR] 执行失败: {e}")
    log(f"  Traceback:\n{traceback.format_exc()}")

log("\n" + "=" * 60)
log("测试完成!")
log("=" * 60)

# 输出到文件
output_dir = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "silhouette_script_result.txt")
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

log(f"\n结果已保存到: {output_path}")

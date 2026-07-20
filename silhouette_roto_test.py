# ============================================================================
# Silhouette Roto 端到端测试脚本 v1.0
# 适用于 Silhouette 2026.0.2 英文版本
#
# 功能：创建一个简单的 Roto 项目并测试完整流程
# 步骤：
#   1. 创建 Project 和 Session
#   2. 添加 Source（测试用纯色图）
#   3. 添加 Roto 节点
#   4. 添加 Output 节点
#   5. 连接节点管线
#   6. 输出结果验证
#
# 使用方法：
#   1. 准备一张测试图片（PNG 格式）放到指定路径
#   2. 修改 TEST_IMAGE_PATH 指向你的测试图片
#   3. 在 Silhouette Script Editor 中打开并运行
# ============================================================================

import fx
import os

# ============================================================================
# 配置 - 请根据实际情况修改
# ============================================================================

# 测试图片路径（请替换为你的实际测试图片）
# 建议使用 1920x1080 PNG 格式，主体与背景对比明显的图片
TEST_IMAGE_PATH = r"C:\Temp\silhouette_test_image.png"

# 输出目录
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge", "roto_output")

# Roto 配置
ROTO_SETTINGS = {
    "shape_type": "x-spline",    # "x-spline" 或 "bezier"
    "tolerance": 1.0,              # 边缘容差
    "feather": 5.0,                # 羽化值
    "output_format": "png",        # 输出格式
}

# ============================================================================
# 主流程
# ============================================================================

def run_roto_test():
    print("=" * 70)
    print("SILHOUETTE ROTO END-TO-END TEST")
    print("=" * 70)

    # Step 1: 创建 Project
    print("\n[Step 1] Creating Project...")
    proj = fx.Project()
    fx.activate(proj)
    print(f"  Project created: {proj}")

    # Step 2: 创建 Session
    print("\n[Step 2] Creating Session...")
    session = fx.Session(
        label="Roto_Test_Session",
        width=1920,
        height=1080,
        frameRate=30.0,
        duration=1.0  # 1秒测试
    )
    fx.activate(session)
    proj.addItem(session)
    print(f"  Session: {session.label} ({session.width}x{session.height})")

    # Step 3: 添加 Source 节点
    print("\n[Step 3] Adding Source node...")
    if os.path.exists(TEST_IMAGE_PATH):
        src = fx.Source(path=TEST_IMAGE_PATH)
        print(f"  Source from file: {TEST_IMAGE_PATH}")
    else:
        print(f"  [WARNING] Test image not found: {TEST_IMAGE_PATH}")
        print(f"  Using placeholder source...")
        src = fx.Node(type="SourceNode", label="Placeholder_Source")
    session.addNode(src)
    print(f"  Source label: {src.label}")
    print(f"  Output ports: {len(src.outputs)}")

    # Step 4: 添加 Roto 节点
    print("\n[Step 4] Adding Roto node...")
    roto = fx.Node(type="RotoNode", label="Auto_Roto")
    roto.addProperty(fx.Property("shape_type", ROTO_SETTINGS["shape_type"]))
    roto.addProperty(fx.Property("tolerance", ROTO_SETTINGS["tolerance"]))
    roto.addProperty(fx.Property("feather", ROTO_SETTINGS["feather"]))
    session.addNode(roto)
    print(f"  Roto label: {roto.label}")
    print(f"  Shape type: {ROTO_SETTINGS['shape_type']}")
    print(f"  Tolerance: {ROTO_SETTINGS['tolerance']}")

    # Step 5: 添加 Output 节点
    print("\n[Step 5] Adding Output node...")
    out = fx.Node(type="OutputNode", label="Matte_Output")
    out.addProperty(fx.Property("format", ROTO_SETTINGS["output_format"]))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out.addProperty(fx.Property("output_dir", OUTPUT_DIR))
    session.addNode(out)
    print(f"  Output label: {out.label}")
    print(f"  Output dir: {OUTPUT_DIR}")

    # Step 6: 连接节点
    print("\n[Step 6] Connecting pipeline...")
    if len(src.outputs) > 0 and len(roto.inputs) > 0:
        pipe1 = fx.Pipe(source=src.outputs[0], target=roto.inputs[0])
        print(f"  Source -> Roto: connected")
    else:
        print(f"  [WARNING] Cannot connect Source -> Roto (ports mismatch)")

    if len(roto.outputs) > 0 and len(out.inputs) > 0:
        pipe2 = fx.Pipe(source=roto.outputs[0], target=out.inputs[0])
        print(f"  Roto -> Output: connected")
    else:
        print(f"  [WARNING] Cannot connect Roto -> Output (ports mismatch)")

    # Step 7: 项目信息汇总
    print("\n[Step 7] Project summary:")
    print(f"  Project items: {len(proj.items)}")
    print(f"  Session nodes: {len(session.nodes)}")
    print(f"  Roto properties: {len(roto.properties)}")

    # Step 8: 导出配置信息
    print("\n[Step 8] Exporting configuration...")
    config_file = os.path.join(OUTPUT_DIR, "roto_config.txt")
    with open(config_file, "w") as f:
        f.write("Silhouette Roto Test Configuration\n")
        f.write("=" * 40 + "\n")
        f.write(f"Version: 2026.0.2\n")
        f.write(f"Source: {TEST_IMAGE_PATH}\n")
        f.write(f"Shape type: {ROTO_SETTINGS['shape_type']}\n")
        f.write(f"Tolerance: {ROTO_SETTINGS['tolerance']}\n")
        f.write(f"Feather: {ROTO_SETTINGS['feather']}\n")
        f.write(f"Output format: {ROTO_SETTINGS['output_format']}\n")
        f.write(f"Session: {session.label}\n")
        f.write(f"Resolution: {session.width}x{session.height}\n")
        f.write(f"Frame rate: {session.frameRate}\n")
    print(f"  Config saved: {config_file}")

    print("\n" + "=" * 70)
    print("ROTO TEST COMPLETE")
    print("=" * 70)
    print("\nNotes:")
    print("  - 检查节点图（Node Graph）中是否正确连接")
    print("  - 检查 Viewer 中是否显示 Roto 结果")
    print("  - 如果需要渲染，在 Output 节点右键选择 Render")
    print(f"  - 输出目录: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        run_roto_test()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()

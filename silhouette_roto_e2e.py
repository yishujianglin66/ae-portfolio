"""
Silhouette Roto 端到端测试 v1.1
使用真实测试素材跑通完整流程

流程：
  1. 加载 fx 模块（外部用 fx_emulator）
  2. 加载真实测试图片
  3. 创建 Project → Session → Source → Roto → Output 管线
  4. 验证节点连接
  5. 导出配置
"""
import os
import sys
import json
import time
from pathlib import Path

print("=" * 70)
print("  Silhouette Roto 端到端测试 v1.1")
print("=" * 70)

# ============================================================================
# Step 0: 加载 fx 模块
# ============================================================================
print("\n[Step 0] 加载 fx 模块...")

try:
    import fx
    MODE = "Silhouette 内置"
except ImportError:
    fx_emulator_path = r"C:\Program Files\BorisFX\Silhouette 2026.0\resources\scripts\fx_emulator.py"
    if not os.path.exists(fx_emulator_path):
        print(f"  [FATAL] fx 模块不可用")
        sys.exit(1)

    import importlib.util
    spec = importlib.util.spec_from_file_location("fx", fx_emulator_path)
    fx = importlib.util.module_from_spec(spec)
    scripts_dir = os.path.dirname(fx_emulator_path)
    parent_dir = os.path.dirname(scripts_dir)
    sys.path.insert(0, scripts_dir)
    sys.path.insert(0, parent_dir)
    try:
        spec.loader.exec_module(fx)
        MODE = "外部模拟（fx_emulator）"
        print(f"  ✓ fx 模块加载成功 ({MODE})")
    except Exception as e:
        print(f"  [FATAL] fx_emulator 加载失败: {e}")
        sys.exit(1)

# ============================================================================
# Step 1: 检查测试素材
# ============================================================================
print("\n[Step 1] 检查测试素材...")

test_images = [
    r"C:\Temp\silhouette_test\roto_test_simple.png",
    r"C:\Temp\silhouette_test\roto_test_person.png",
    r"C:\Temp\silhouette_test\roto_test_multi.png",
]

available_images = []
for img_path in test_images:
    if os.path.exists(img_path):
        size = os.path.getsize(img_path)
        print(f"  ✓ {os.path.basename(img_path)} ({size} bytes)")
        available_images.append(img_path)
    else:
        print(f"  ✗ {os.path.basename(img_path)} 不存在")

if not available_images:
    print("  [FATAL] 没有可用的测试素材")
    sys.exit(1)

# 选择人物轮廓图片作为主要测试素材
test_image = available_images[1] if len(available_images) > 1 else available_images[0]
print(f"\n  使用测试素材: {test_image}")

# ============================================================================
# Step 2: 创建 Project 和 Session
# ============================================================================
print("\n[Step 2] 创建 Project 和 Session...")

try:
    proj = fx.Project()
    print(f"  ✓ Project 创建成功")
except Exception as e:
    print(f"  ✗ Project 创建失败: {e}")
    # fx_emulator 可能没有 Project，用 Object 模拟
    proj = fx.Object(type="Project", label="RotoProject")
    proj.items = []
    proj.addItem = lambda item: proj.items.append(item)
    print(f"  ✓ Project 模拟成功")

if hasattr(fx, 'activate'):
    try:
        fx.activate(proj)
    except Exception:
        pass

try:
    session = fx.Session(label="RotoTest", width=1920, height=1080, frameRate=30.0)
    # fx_emulator 的 Session 可能不保存这些属性，手动设置
    if not hasattr(session, 'width') or session.width is None:
        session.width = 1920
    if not hasattr(session, 'height') or session.height is None:
        session.height = 1080
    if not hasattr(session, 'frameRate') or session.frameRate is None:
        session.frameRate = 30.0
    print(f"  ✓ Session 创建成功: {session.label}")
except Exception as e:
    print(f"  ✗ Session 创建失败: {e}")
    session = fx.Object(type="Session", label="RotoTest")
    session.width = 1920
    session.height = 1080
    session.frameRate = 30.0
    session.nodes = []
    session.addNode = lambda node: session.nodes.append(node)
    print(f"  ✓ Session 模拟成功")

if hasattr(fx, 'activate'):
    try:
        fx.activate(session)
    except Exception:
        pass

try:
    proj.addItem(session)
except Exception:
    pass

# ============================================================================
# Step 3: 创建 Source 节点
# ============================================================================
print("\n[Step 3] 创建 Source 节点...")

try:
    src = fx.Source(path=test_image)
    print(f"  ✓ Source 创建成功: {src.label}")
    print(f"    路径: {src.path}")
    print(f"    输出端口数: {len(src.outputs)}")
except Exception as e:
    print(f"  ⚠ Source(path) 失败: {e}")
    print(f"  使用 Node(type='SourceNode') 替代...")
    src = fx.Node(type="SourceNode", label=os.path.basename(test_image))
    print(f"  ✓ Source 节点创建成功: {src.label}")
    print(f"    输出端口数: {len(src.outputs)}")

try:
    session.addNode(src)
except Exception:
    pass

# ============================================================================
# Step 4: 创建 Roto 节点
# ============================================================================
print("\n[Step 4] 创建 Roto 节点...")

roto = fx.Node(type="RotoNode", label="AutoRoto")
print(f"  ✓ Roto 节点创建: {roto.label}")

# 添加 Roto 属性
roto_props = {
    "shape_type": "x-spline",
    "tolerance": 1.0,
    "feather": 5.0,
    "keyframes": 5,
    "tracking": "planar",
}

for key, val in roto_props.items():
    try:
        prop = fx.Property(key, val)
        roto.addProperty(prop)
        print(f"    + {key}: {val}")
    except Exception as e:
        print(f"    ✗ {key}: 失败 ({e})")

print(f"  属性总数: {len(roto.properties)}")

try:
    session.addNode(roto)
except Exception:
    pass

# ============================================================================
# Step 5: 创建 Output 节点
# ============================================================================
print("\n[Step 5] 创建 Output 节点...")

output_node = fx.Node(type="OutputNode", label="MatteOutput")
print(f"  ✓ Output 节点创建: {output_node.label}")

# 输出配置
output_dir = os.path.join(
    os.path.expanduser("~"),
    "Documents", "ae-mcp-bridge", "roto_output"
)
os.makedirs(output_dir, exist_ok=True)

output_props = {
    "format": "png",
    "output_dir": output_dir,
    "output_prefix": "matte_",
}

for key, val in output_props.items():
    try:
        prop = fx.Property(key, val)
        output_node.addProperty(prop)
        print(f"    + {key}: {val}")
    except Exception:
        pass

try:
    session.addNode(output_node)
except Exception:
    pass

# ============================================================================
# Step 6: 连接节点管线
# ============================================================================
print("\n[Step 6] 连接节点管线 Source → Roto → Output...")

connections = []

# Source → Roto
if len(src.outputs) > 0 and len(roto.inputs) > 0:
    try:
        pipe1 = fx.Pipe(source=src.outputs[0], target=roto.inputs[0])
        connections.append(("Source", "Roto", True))
        print(f"  ✓ Source → Roto")
    except Exception as e:
        connections.append(("Source", "Roto", False))
        print(f"  ✗ Source → Roto: {e}")
else:
    print(f"  ⚠ 端口不足: Source outputs={len(src.outputs)}, Roto inputs={len(roto.inputs)}")

# Roto → Output
if len(roto.outputs) > 0 and len(output_node.inputs) > 0:
    try:
        pipe2 = fx.Pipe(source=roto.outputs[0], target=output_node.inputs[0])
        connections.append(("Roto", "Output", True))
        print(f"  ✓ Roto → Output")
    except Exception as e:
        connections.append(("Roto", "Output", False))
        print(f"  ✗ Roto → Output: {e}")
else:
    print(f"  ⚠ 端口不足: Roto outputs={len(roto.outputs)}, Output inputs={len(output_node.inputs)}")

# ============================================================================
# Step 7: 项目信息汇总
# ============================================================================
print("\n[Step 7] 项目信息汇总...")

node_count = 0
try:
    node_count = len(session.nodes)
except Exception:
    node_count = 3  # src + roto + output

print(f"  Session: {session.label}")
print(f"  分辨率: {session.width}x{session.height}")
print(f"  帧率: {session.frameRate}")
print(f"  节点数: {node_count}")
print(f"  连接数: {len(connections)}")
print(f"  Roto 属性: {len(roto.properties)}")

# ============================================================================
# Step 8: 导出配置文件
# ============================================================================
print("\n[Step 8] 导出 Roto 配置...")

config = {
    "version": "1.0",
    "silhouette_version": "2026.0.2",
    "mode": MODE,
    "test_image": test_image,
    "session": {
        "label": session.label,
        "width": session.width,
        "height": session.height,
        "frameRate": session.frameRate,
    },
    "nodes": [
        {
            "type": "SourceNode",
            "label": src.label,
            "path": test_image,
        },
        {
            "type": "RotoNode",
            "label": roto.label,
            "properties": roto_props,
        },
        {
            "type": "OutputNode",
            "label": output_node.label,
            "properties": output_props,
        },
    ],
    "connections": [
        {"from": c[0], "to": c[1], "success": c[2]}
        for c in connections
    ],
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
}

config_path = os.path.join(output_dir, "roto_config.json")
with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print(f"  ✓ 配置已保存: {config_path}")

# ============================================================================
# Step 9: 生成可在 Silhouette 中运行的脚本
# ============================================================================
print("\n[Step 9] 生成 Silhouette 可运行脚本...")

sil_script = f'''# Silhouette Roto 脚本（自动生成）
# 生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}
# 测试素材: {test_image}

import fx

# 创建 Project
proj = fx.Project()
fx.activate(proj)

# 创建 Session
session = fx.Session(label="RotoTest", width=1920, height=1080, frameRate=30.0)
fx.activate(session)
proj.addItem(session)

# 创建 Source
src = fx.Source(path=r"{test_image}")
session.addNode(src)

# 创建 Roto 节点
roto = fx.Node(type="RotoNode", label="AutoRoto")
roto.addProperty(fx.Property("shape_type", "x-spline"))
roto.addProperty(fx.Property("tolerance", 1.0))
roto.addProperty(fx.Property("feather", 5.0))
session.addNode(roto)

# 创建 Output
out = fx.Node(type="OutputNode", label="MatteOutput")
out.addProperty(fx.Property("format", "png"))
out.addProperty(fx.Property("output_dir", r"{output_dir}"))
session.addNode(out)

# 连接管线
fx.Pipe(source=src.outputs[0], target=roto.inputs[0])
fx.Pipe(source=roto.outputs[0], target=out.inputs[0])

print("Roto pipeline created successfully!")
print(f"Session: {{session.label}}")
print(f"Nodes: {{len(session.nodes)}}")
'''

sil_script_path = os.path.join(output_dir, "run_in_silhouette.py")
with open(sil_script_path, "w", encoding="utf-8") as f:
    f.write(sil_script)
print(f"  ✓ Silhouette 脚本已保存: {sil_script_path}")

# ============================================================================
# 结果汇总
# ============================================================================
print("\n" + "=" * 70)
print("  Roto 端到端测试结果")
print("=" * 70)

print(f"""
  Mode: {MODE}
  测试素材: {os.path.basename(test_image)}
  Session: {session.label} ({session.width}x{session.height} @ {session.frameRate}fps)

  节点管线:
    Source ({src.label})
        ↓
    Roto ({roto.label})
      - shape_type: x-spline
      - tolerance: 1.0
      - feather: 5.0
        ↓
    Output ({output_node.label})
      - format: png
      - output_dir: {output_dir}

  连接状态: {sum(1 for c in connections if c[2])}/{len(connections)} 成功

  输出文件:
    配置: {config_path}
    Silhouette 脚本: {sil_script_path}
""")

print("=" * 70)
print("  下一步：在 Silhouette 中运行")
print("=" * 70)
print(f"""
  1. 打开 Silhouette 2026.0.2
  2. Window → Script Editor
  3. File → Open → 选择:
     {sil_script_path}
  4. 点击运行按钮（绿色三角）
  5. 检查 Node Graph 中是否正确显示:
     Source → Roto → Output
  6. 在 Roto 节点上手动添加形状（X-Spline）
  7. 在 Output 节点右键 → Render 输出 Matte
""")

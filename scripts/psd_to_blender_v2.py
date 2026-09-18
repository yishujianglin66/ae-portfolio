"""
psd_to_blender_v2.py - 修复版：从 PSD 提取图层并生成 Blender 图像平面导入脚本
"""
import json
import os
import sys
from pathlib import Path

from PIL import Image
from psd_tools import PSDImage


def extract_psd_layers(psd_path: str, output_dir: str) -> list:
    """提取 PSD 文件中的所有图层为 PNG。"""
    os.makedirs(output_dir, exist_ok=True)
    psd = PSDImage.open(psd_path)

    layers_info = []

    def process_layer(layer, group_name=""):
        if layer.is_group():
            group = layer.name
            for child in layer:
                process_layer(child, group)
        elif layer.kind in ("pixel", "smartobject", "shape"):
            try:
                safe_name = f"{group_name}_{layer.name}" if group_name else layer.name
                safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in safe_name)
                png_path = os.path.join(output_dir, f"{safe_name}.png")
                pil_image = layer.composite()
                if pil_image:
                    pil_image.save(png_path, "PNG")
                    layers_info.append({
                        "name": layer.name,
                        "group": group_name,
                        "path": png_path,
                        "width": pil_image.width,
                        "height": pil_image.height,
                    })
                    print(f"  OK: {safe_name} ({pil_image.width}x{pil_image.height})")
            except Exception as e:
                print(f"  Skip: {layer.name} - {e}")

    print(f"PSD: {psd_path}")
    print(f"Size: {psd.width}x{psd.height}")
    print()

    for layer in psd:
        process_layer(layer)

    return layers_info


def generate_blender_import_script(
    layers_info: list,
    blend_file_path: str,
    output_script_path: str,
) -> str:
    """生成 Blender 脚本 - 使用更兼容的方式创建材质。"""
    lines = [
        '"""Auto-generated: Import PSD layers as image planes (v2)"""',
        "import bpy",
        "import os",
        "",
        '# 打开已有 blend 文件',
        f'bpy.ops.wm.open_mainfile(filepath=r"{blend_file_path}")',
        "",
        "# === 导入图像平面 ===",
        "",
    ]

    for i, info in enumerate(layers_info):
        png_path = info["path"].replace("\\", "\\\\")
        name = info["name"].replace('"', '\\"')
        group = info["group"].replace('"', '\\"')
        w = info["width"]
        h = info["height"]

        lines.extend([
            f"# Layer {i}: {group}/{name} ({w}x{h})",
            f'img_path = r"{png_path}"',
            "if os.path.isfile(img_path):",
            "    try:",
            "        img = bpy.data.images.load(img_path, check_existing=True)",
            f"        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, {-i * 0.01:.3f}))",
            "        plane = bpy.context.active_object",
            f'        plane.name = "{name}"',
            f"        sx = {w / max(w, h):.4f}",
            f"        sy = {h / max(w, h):.4f}",
            "        plane.scale = (sx, sy, 1)",
            "",
            "        # 创建材质",
            f'        mat = bpy.data.materials.new("mat_{i}")',
            "        mat.use_nodes = True",
            "        nodes = mat.node_tree.nodes",
            "        links = mat.node_tree.links",
            "",
            "        # 清除默认节点",
            "        nodes.clear()",
            "",
            "        # 创建输出节点",
            '        output_node = nodes.new("ShaderNodeOutputMaterial")',
            "        output_node.location = (300, 0)",
            "",
            "        # 创建 BSDF 节点",
            '        bsdf = nodes.new("ShaderNodeBsdfPrincipled")',
            "        bsdf.location = (0, 0)",
            "",
            "        # 创建纹理节点",
            '        tex = nodes.new("ShaderNodeTexImage")',
            "        tex.location = (-300, 0)",
            "        tex.image = img",
            "",
            "        # 连接",
            "        links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])",
            "        links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])",
            "",
            "        # 透明混合",
            "        mat.blend_method = 'CLIP'",
            "        plane.data.materials.append(mat)",
            "",
            f'        plane["ae_layer_name"] = "{name}"',
            f'        plane["ae_group"] = "{group}"',
            "    except Exception as e:",
            f'        print(f"Error importing layer {i}: {{e}}")',
            "",
        ])

    lines.extend([
        "# === 完成 ===",
        "mesh_count = len([o for o in bpy.data.objects if o.type == 'MESH'])",
        'print(f"Imported {mesh_count} image planes")',
        "",
        "# 保存",
        f'bpy.ops.wm.save_as_mainfile(filepath=r"{blend_file_path}")',
        'print("Saved!")',
        "",
    ])

    script = "\n".join(lines)
    with open(output_script_path, "w", encoding="utf-8") as f:
        f.write(script)

    return script


def main():
    """主流程。"""
    psd_path = r"D:\AE-Work\resources\psd\动漫人物.psd"
    if not os.path.isfile(psd_path):
        psd_path = r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\resources\psd\动漫人物.psd"

    output_dir = r"C:\Users\Administrator\Desktop\psd_layers"
    blend_file = r"C:\Users\Administrator\Desktop\ae_project.blend"
    output_script = r"C:\Users\Administrator\Desktop\ae_blender_with_images.py"

    if not os.path.isfile(psd_path):
        print("PSD file not found!")
        return

    print("=" * 60)
    print("Step 1: Extract PSD layers")
    print("=" * 60)
    layers = extract_psd_layers(psd_path, output_dir)
    print(f"\nExported {len(layers)} layers")

    print("\n" + "=" * 60)
    print("Step 2: Generate Blender import script")
    print("=" * 60)
    script = generate_blender_import_script(layers, blend_file, output_script)
    print(f"Generated: {output_script}")

    print("\nRun in Blender:")
    print(f'  blender --background --python "{output_script}"')


if __name__ == "__main__":
    main()

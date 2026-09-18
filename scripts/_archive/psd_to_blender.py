"""
psd_to_blender.py - 从 PSD 提取图层并生成 Blender 图像平面导入脚本

流程：
1. 用 psd-tools 解析 PSD 文件
2. 导出各图层为 PNG
3. 生成 Blender Python 脚本，将 PNG 作为图像平面导入
4. 匹配 AE 分析中的图层名称
"""
import json
import os
import sys
from pathlib import Path

from PIL import Image

# psd-tools
from psd_tools import PSDImage


def extract_psd_layers(psd_path: str, output_dir: str) -> list:
    """提取 PSD 文件中的所有图层为 PNG。

    Args:
        psd_path: PSD 文件路径
        output_dir: PNG 输出目录

    Returns:
        图层信息列表 [{name, path, width, height, group}, ...]
    """
    os.makedirs(output_dir, exist_ok=True)
    psd = PSDImage.open(psd_path)

    layers_info = []

    def process_layer(layer, group_name=""):
        """递归处理图层。"""
        if layer.is_group():
            group = layer.name
            for child in layer:
                process_layer(child, group)
        elif layer.kind in ("pixel", "smartobject", "shape"):
            try:
                # 生成安全的文件名
                safe_name = f"{group_name}_{layer.name}" if group_name else layer.name
                safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in safe_name)

                png_path = os.path.join(output_dir, f"{safe_name}.png")

                # 尝试导出图层图像
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
                    print(f"  Exported: {safe_name} ({pil_image.width}x{pil_image.height})")
            except Exception as e:
                print(f"  Skip: {layer.name} - {e}")

    print(f"PSD: {psd_path}")
    print(f"Size: {psd.width}x{psd.height}")
    print(f"Layers: {len(list(psd.descendants()))}")
    print()

    for layer in psd:
        process_layer(layer)

    return layers_info


def generate_blender_import_script(
    layers_info: list,
    blend_file_path: str,
    output_script_path: str,
) -> str:
    """生成 Blender 脚本，将 PNG 作为图像平面导入。

    Args:
        layers_info: 图层信息列表
        blend_file_path: 已有 blend 文件路径
        output_script_path: 输出脚本路径

    Returns:
        脚本内容
    """
    lines = [
        '"""Auto-generated: Import PSD layers as image planes"""',
        "import bpy",
        "import os",
        "",
        "# 打开已有 blend 文件",
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
            f"# Layer: {group}/{name} ({w}x{h})",
            f'img_path_{i} = r"{png_path}"',
            f"if os.path.isfile(img_path_{i}):",
            f'    img_{i} = bpy.data.images.load(img_path_{i})',
            f'    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, {-i * 0.01}))',
            f'    plane_{i} = bpy.context.active_object',
            f'    plane_{i}.name = "{name}"',
            f'    plane_{i}.scale = ({w / max(w, h):.4f}, {h / max(w, h):.4f}, 1)',
            f'    mat_{i} = bpy.data.materials.new("mat_{name}")',
            f"    mat_{i}.use_nodes = True",
            f"    bsdf_{i} = mat_{i}.node_tree.nodes.get('Principled BSDF')",
            f'    tex_{i} = mat_{i}.node_tree.nodes.new("ShaderNodeTexImage")',
            f"    tex_{i}.image = img_{i}",
            f"    mat_{i}.node_tree.links.new(tex_{i}.outputs['Color'], bsdf_{i}.inputs['Base Color'])",
            f"    mat_{i}.blend_method = 'CLIP'  # 透明支持",
            f"    plane_{i}.data.materials.append(mat_{i})",
            f'    plane_{i}["ae_layer_name"] = "{name}"',
            f'    plane_{i}["ae_group"] = "{group}"',
            "",
        ])

    lines.extend([
        "# === 完成 ===",
        'print(f"Imported {len([o for o in bpy.data.objects if o.type == \'MESH\'])} image planes")',
        "",
        "# 保存",
        'bpy.ops.wm.save_as_mainfile(filepath=r"' + blend_file_path + '")',
        'print("Saved!")',
        "",
    ])

    script = "\n".join(lines)
    with open(output_script_path, "w", encoding="utf-8") as f:
        f.write(script)

    return script


def main():
    """主流程。"""
    # 路径配置
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
    print(f"\nExported {len(layers)} layers to {output_dir}")

    print("\n" + "=" * 60)
    print("Step 2: Generate Blender import script")
    print("=" * 60)
    script = generate_blender_import_script(layers, blend_file, output_script)
    print(f"Generated: {output_script}")
    print(f"Script size: {len(script)} bytes")

    print("\nDone! Run in Blender:")
    print(f'  blender --background --python "{output_script}"')


if __name__ == "__main__":
    main()

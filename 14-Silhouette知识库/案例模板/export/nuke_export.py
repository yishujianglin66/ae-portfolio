# Nuke Export Template
# Nuke格式导出模板 - 生成Nuke兼容的遮罩与跟踪数据
# 适用于Silhouette到Nuke的工作流对接

import json
import os
import time

from fx import *


def create_pipeline(
    source_path,
    output_dir,
    frame_rate=24.0,
    export_mattes=True,
    export_tracking=True,
    export_shapes=True,
    matte_format="exr",
    compression="ZIP",
    color_space="ACEScg"
):
    """
    创建Nuke导出管线

    参数:
        source_path (str): 源素材路径
        output_dir (str): 输出目录
        frame_rate (float): 帧率
        export_mattes (bool): 是否导出遮罩序列
        export_tracking (bool): 是否导出跟踪数据
        export_shapes (bool): 是否导出形状数据（Nuke兼容格式）
        matte_format (str): 遮罩格式 exr/dpx/png
        compression (str): EXR压缩格式
        color_space (str): 色彩空间
    """

    # 确保输出目录存在
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # ===== 1. 创建项目与会话 =====
    print("=== 步骤1: 创建项目 ===")
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Nuke_Export"
    activate(session)
    proj.addItem(session)

    # ===== 2. 加载源素材 =====
    print("=== 步骤2: 加载素材 ===")
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 获取素材信息
    src_width = session.width
    src_height = session.height
    start_frame = src.property("startFrame").value
    end_frame = src.property("endFrame").value

    print(f"  分辨率: {src_width}x{src_height}")
    print(f"  帧范围: {start_frame}-{end_frame}")

    # ===== 3. 配置色彩管理 =====
    print("=== 步骤3: 配置色彩管理 ===")
    color = proj.property("colorManagement")
    color.setValue("enabled", True)
    color.setValue("config", "ACES 1.3")
    color.setValue("workingSpace", color_space)

    # ===== 4. 创建Roto节点（用于遮罩） =====
    print("=== 步骤4: 创建Roto节点 ===")
    roto_layers = [
        {"label": "Main_Roto", "name": "main", "blur": 0.3},
        {"label": "Detail_Roto", "name": "detail", "blur": 0.5}
    ]

    roto_nodes = []
    for layer in roto_layers:
        roto = Node("RotoNode")
        roto.label = layer["label"]
        roto.property("shapeType").setValue("x-spline", 0)
        roto.property("alpha.blur").setValue(layer["blur"], 0)
        roto.property("motionBlur").setValue(True, 0)
        roto.property("motionBlurAmount").setValue(1.2, 0)
        session.addNode(roto)
        src.outputs[0].connect(roto.inputs[1])
        roto_nodes.append(roto)
        print(f"  创建Roto层: {layer['label']}")

    # ===== 5. 创建跟踪节点 =====
    print("=== 步骤5: 创建跟踪节点 ===")
    tracker = Node("TrackerNode")
    tracker.label = "Nuke_Track"
    tracker.property("trackMode").setValue("sub_pixel", 0)
    tracker.property("searchSize").setValue(32, 0)
    session.addNode(tracker)
    src.outputs[0].connect(tracker.inputs[1])

    # ===== 6. 配置遮罩输出 =====
    output_nodes = []
    if export_mattes:
        print("=== 步骤6: 配置遮罩输出 ===")
        for i, (layer, roto) in enumerate(zip(roto_layers, roto_nodes)):
            matte_out = Node("OutputNode")
            matte_out.label = f"Matte_Output_{layer['name']}"
            matte_path = os.path.join(
                output_dir,
                "mattes",
                layer["name"],
                f"matte_{layer['name']}_v001.####.{matte_format}"
            ).replace("\\", "/")
            os.makedirs(os.path.dirname(matte_path), exist_ok=True)

            matte_out.property("path").setValue(matte_path, 0)
            matte_out.property("format").setValue(matte_format, 0)
            matte_out.property("compression").setValue(compression, 0)
            matte_out.property("bitDepth").setValue("half", 0)
            matte_out.property("colorSpace").setValue(color_space, 0)
            matte_out.property("startFrame").setValue(start_frame, 0)
            matte_out.property("endFrame").setValue(end_frame, 0)

            session.addNode(matte_out)
            roto.outputs[0].connect(matte_out.inputs[0])
            output_nodes.append(matte_out)
            print(f"  遮罩输出: {matte_path}")

    # ===== 7. 导出Nuke跟踪数据 =====
    if export_tracking:
        print("=== 步骤7: 导出Nuke跟踪数据 ===")
        tracking_dir = os.path.join(output_dir, "tracking")
        os.makedirs(tracking_dir, exist_ok=True)

        # Nuke原生格式
        nuke_track_path = os.path.join(tracking_dir, "nuke_tracker.nk").replace("\\", "/")
        tracker.property("exportFormat").setValue("nuke_tracker", 0)
        tracker.property("exportPath").setValue(nuke_track_path, 0)
        tracker.export()
        print(f"  Nuke跟踪数据: {nuke_track_path}")

        # 同时导出JSON格式（便于程序读取）
        nuke_json_path = os.path.join(tracking_dir, "track_data.json")
        export_tracking_json(tracker, nuke_json_path, frame_rate)
        print(f"  JSON跟踪数据: {nuke_json_path}")

    # ===== 8. 导出Nuke形状数据 =====
    if export_shapes:
        print("=== 步骤8: 导出形状数据 ===")
        shapes_dir = os.path.join(output_dir, "shapes")
        os.makedirs(shapes_dir, exist_ok=True)

        for roto in roto_nodes:
            shapes_path = os.path.join(
                shapes_dir,
                f"{roto.label}_shapes.nk"
            ).replace("\\", "/")
            roto.property("exportFormat").setValue("nuke_shapes", 0)
            roto.property("exportPath").setValue(shapes_path, 0)
            roto.export()
            print(f"  形状数据: {shapes_path}")

    # ===== 9. 生成Nuke脚本模板 =====
    print("=== 步骤9: 生成Nuke脚本模板 ===")
    nuke_script_path = os.path.join(output_dir, "nuke_setup.nk")
    generate_nuke_script(
        nuke_script_path,
        source_path,
        output_dir,
        roto_layers,
        start_frame,
        end_frame,
        frame_rate,
        src_width,
        src_height,
        color_space
    )
    print(f"  Nuke脚本: {nuke_script_path}")

    # ===== 10. 生成交接清单 =====
    print("=== 步骤10: 生成交接清单 ===")
    manifest = {
        "version": "1.0",
        "source": "silhouette",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "shot": os.path.basename(output_dir),
        "outputDir": output_dir,
        "frameRate": frame_rate,
        "resolution": [src_width, src_height],
        "frameRange": [start_frame, end_frame],
        "colorSpace": color_space,
        "deliverables": {
            "mattes": export_mattes,
            "tracking": export_tracking,
            "shapes": export_shapes,
            "nuke_script": True
        },
        "matteLayers": [
            {
                "name": layer["name"],
                "label": layer["label"],
                "path": f"mattes/{layer['name']}/matte_{layer['name']}_v001.####.{matte_format}"
            }
            for layer in roto_layers
        ] if export_mattes else [],
        "nukeIntegration": {
            "scriptPath": "nuke_setup.nk",
            "trackPath": "tracking/nuke_tracker.nk" if export_tracking else None,
            "shapesDir": "shapes/" if export_shapes else None
        }
    }

    manifest_path = os.path.join(output_dir, "nuke_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n=== Nuke导出管线创建完成 ===")
    print(f"输出目录: {output_dir}")
    print(f"遮罩层: {len(roto_layers)}")
    print(f"跟踪: {'是' if export_tracking else '否'}")
    print(f"形状: {'是' if export_shapes else '否'}")
    print(f"清单: {manifest_path}")
    print("\n下一步: 绘制Roto形状，执行跟踪，渲染输出")

    return proj, session


def export_tracking_json(tracker, output_path, frame_rate):
    """导出JSON格式的跟踪数据"""
    data = {
        "version": "1.0",
        "frameRate": frame_rate,
        "trackers": []
    }

    for i in range(tracker.numTrackers):
        track = tracker.getTracker(i)
        track_data = {
            "name": track.name,
            "startFrame": track.startFrame,
            "endFrame": track.endFrame,
            "keyframes": []
        }

        for frame in range(track.startFrame, track.endFrame + 1):
            pos = track.getPosition(frame)
            if pos:
                track_data["keyframes"].append({
                    "frame": frame,
                    "x": pos[0],
                    "y": pos[1]
                })

        data["trackers"].append(track_data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def generate_nuke_script(
    script_path,
    source_path,
    output_dir,
    roto_layers,
    start_frame,
    end_frame,
    frame_rate,
    width,
    height,
    color_space
):
    """生成Nuke脚本模板"""
    script = f"""# Nuke Script - Generated by Silhouette
# 时间: {time.strftime("%Y-%m-%d %H:%M:%S")}
# 源: {source_path}

# ===== Read Plate =====
Read {{
  file "{source_path.replace(chr(92), '/')}"
  first {start_frame}
  last {end_frame}
  frame {frame_rate}
  format "{width} {height}"
  colorspace "{color_space}"
  name Plate_Read
}}

# ===== Matte Reads =====
"""

    for layer in roto_layers:
        matte_path = f"{output_dir}/mattes/{layer['name']}/matte_{layer['name']}_v001.####.exr"
        script += f"""Read {{
  file "{matte_path}"
  first {start_frame}
  last {end_frame}
  name {layer['label']}_Read
}}

"""

    script += """# ===== Composite =====
# 将遮罩应用到合成中
# 示例: 使用遮罩控制前景
# ContactSheet or Merge nodes can be added here

# ===== Write Output =====
Write {
  file "output/final.####.exr"
  first """ + str(start_frame) + """
  last """ + str(end_frame) + """
  colorspace "ACEScg"
  name Final_Write
}
"""

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        source = sys.argv[1]
        output = sys.argv[2]
    else:
        source = "D:/footage/sample_plate.exr"
        output = "D:/output/nuke_export"

    create_pipeline(
        source_path=source,
        output_dir=output,
        frame_rate=24.0,
        export_mattes=True,
        export_tracking=True,
        export_shapes=True,
        matte_format="exr",
        compression="ZIP",
        color_space="ACEScg"
    )

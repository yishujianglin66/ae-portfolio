# Clone Repair Template
# Clone修复模板 - 移除水印、Logo

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=30.0):
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Clone_Repair"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    paint = Node("PaintNode")
    paint.label = "Clone_Paint"
    paint.property("brush.size").setValue(30.0, 0)
    paint.property("brush.hardness").setValue(0.3, 0)
    paint.property("brush.flow").setValue(1.0, 0)
    paint.property("mode").setValue("clone", 0)
    paint.property("sampleOffset").setValue([50, 0], 0)
    session.addNode(paint)

    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(paint.inputs[0])
    paint.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] Clone repair pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: clone_repair.py <source_path> <output_path>")

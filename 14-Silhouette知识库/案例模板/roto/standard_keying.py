# Standard Keying Template
# 标准抠像模板 - 适用于大多数场景

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=30.0):
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Standard_Keying"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Main_Roto"
    roto.property("alpha.blur").setValue(0.5, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("fill").setValue(true, 0)
    roto.property("stroke").setValue(false, 0)
    roto.property("matte.mode").setValue("alpha", 0)
    roto.property("matte.invert").setValue(false, 0)
    session.addNode(roto)

    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] Standard keying pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: standard_keying.py <source_path> <output_path>")

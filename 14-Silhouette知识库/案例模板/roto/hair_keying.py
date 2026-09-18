# Hair Keying Template
# 毛发抠像模板 - 适用于毛发、半透明物体

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=30.0):
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Hair_Keying"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto_body = Node("RotoNode")
    roto_body.label = "Body_Roto"
    roto_body.property("alpha.blur").setValue(0.3, 0)
    roto_body.property("antialias").setValue(1.0, 0)
    roto_body.property("fill").setValue(true, 0)
    session.addNode(roto_body)

    roto_hair = Node("RotoNode")
    roto_hair.label = "Hair_Roto"
    roto_hair.property("alpha.blur").setValue(1.5, 0)
    roto_hair.property("antialias").setValue(1.0, 0)
    roto_hair.property("fill").setValue(true, 0)
    roto_hair.property("motionBlur").setValue(true, 0)
    roto_hair.property("motionBlur.shutter").setValue(0.7, 0)
    session.addNode(roto_hair)

    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto_body.inputs[1])
    roto_body.outputs[0].connect(roto_hair.inputs[1])
    roto_hair.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] Hair keying pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: hair_keying.py <source_path> <output_path>")

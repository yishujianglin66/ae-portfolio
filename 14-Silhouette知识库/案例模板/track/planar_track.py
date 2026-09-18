# Planar Tracking Template
# 平面跟踪模板

import json
import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=30.0):
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Planar_Tracking"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    track = Node("TrackerNode")
    track.label = "Planar_Track"
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(21, 0)
    track.property("accuracy").setValue("medium", 0)
    track.property("patternSize").setValue(11, 0)
    track.property("keyframes").setValue(1, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(false, 0)
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    src.outputs[0].connect(track.inputs[0])

    tracking_data = {
        "version": "2026.0.2",
        "track_type": "planar",
        "source": source_path.replace("\\", "/"),
        "search_area": 21,
        "accuracy": "medium",
        "frames": [],
        "trackers": [],
        "fps": frame_rate
    }

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    json_path = output_path.replace("[####].exr", "tracking_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tracking_data, f, indent=2)

    print("[SILHOUETTE] Planar tracking pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: planar_track.py <source_path> <output_path>")
